"""remove_member_reassigns_data_then_deletes_account

Product decision (confirmed with the user): when an admin/owner removes a
teammate, that is no longer just a membership deletion. Two things happen,
atomically:

1. Whatever the removed teammate created *in this organisation*
   (`campaigns.created_by`, `runs.started_by`) is reassigned to whoever
   performed the removal, so their work survives them leaving instead of
   falling back to `created_by is null` the moment their account goes away.
2. The removed teammate's account is deleted entirely - not just their
   membership in this one org. Deleting `auth.users` cascades through every
   membership they hold, in every organisation, via the existing FK chain
   (`public.users.auth_user_id references auth.users(id) on delete cascade`,
   `memberships.user_id references users(id) on delete cascade`) - the same
   cascade `ISSUES.md` #13/#14/#17 already hardened for a self-deleted
   account, just triggered by an admin acting on someone else instead of a
   user acting on themselves. Any *other* organisation the removed teammate
   belongs to is unaffected by step 1 above - this admin has no relationship
   to that org's data, so its campaigns/runs fall back to the ordinary
   `on delete set null`, exactly as a self-deletion already behaves today.

Same reasoning as `create_organisation()`/`create_or_refresh_invitation()`
for why this needs to be a `SECURITY DEFINER` function rather than living in
the request handler (CLAUDE.md §4b: `privileged.acquire()` must never appear
in a request handler - "a request has a user... that path is
`database.as_user()`"), and deleting `auth.users` needs privileges the
`authenticated` role never holds. Authorisation is re-checked inside the
function itself (`has_org_role`, `can_act_on_member`) exactly like those two
functions do, since bypassing RLS means enforcing those checks explicitly -
the route's own Python-side checks (`Permission.TEAM_REMOVE`,
`_ensure_can_act_on`) already prevent a normal user from reaching this in an
unauthorised state; the checks in here are the same defense-in-depth
backstop `create_or_refresh_invitation()` has for its own checks, not the
primary gate.

Revision ID: f3d8a1c6e492
Revises: e2a6f8c4b719
Created: 2026-08-09 22:15:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f3d8a1c6e492"
down_revision: str | None = "e2a6f8c4b719"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_FUNCTION = """
create function public.remove_member_and_reassign_data(target_org uuid, target_user_id uuid)
returns void
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  caller_id uuid := public.current_user_id();
  caller_role public.org_role;
  target_current_role public.org_role;
  target_auth_id uuid;
begin
  if caller_id is null then
    raise exception 'Not signed in.' using errcode = '28000';
  end if;

  if caller_id = target_user_id then
    raise exception 'Use "Leave organisation" to remove yourself.'
      using errcode = 'insufficient_privilege';
  end if;

  if not public.has_org_role(target_org, array['owner','admin']::public.org_role[]) then
    raise exception 'Your role cannot remove members from this organisation.'
      using errcode = 'insufficient_privilege';
  end if;

  select role into target_current_role
    from public.memberships
    where org_id = target_org and user_id = target_user_id;

  if target_current_role is null then
    return; -- not a member of this org - nothing to do, route treats as already-gone
  end if;

  caller_role := public.current_org_role(target_org);
  if not public.can_act_on_member(caller_role, target_current_role) then
    raise exception 'Your role cannot remove a member with that role.'
      using errcode = 'insufficient_privilege';
  end if;

  update public.campaigns set created_by = caller_id
    where org_id = target_org and created_by = target_user_id;
  update public.runs set started_by = caller_id
    where org_id = target_org and started_by = target_user_id;

  select auth_user_id into target_auth_id
    from public.users where id = target_user_id;

  delete from auth.users where id = target_auth_id;
end;
$$;
"""

DROP_FUNCTION = "drop function if exists public.remove_member_and_reassign_data(uuid, uuid)"


def upgrade() -> None:
    op.execute(CREATE_FUNCTION)


def downgrade() -> None:
    op.execute(DROP_FUNCTION)
