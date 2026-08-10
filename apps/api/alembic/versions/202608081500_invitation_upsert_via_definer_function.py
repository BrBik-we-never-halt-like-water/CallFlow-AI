"""invitation_upsert_via_definer_function

Fixes a regression migration `d94b2c8f1a67` introduced: locking `invitations`
down to `grant update (accepted_at) ... to authenticated` (closing the
invitee-can-mutate-their-own-role hole) broke *every* invitation, not just a
re-invite. `create_invitation()`'s
`insert ... on conflict (...) do update set role = excluded.role, ...` needs
UPDATE privilege on those columns for the whole statement to plan, checked at
executor start regardless of whether a conflict actually occurs at runtime -
so a first-time invite (no conflict) failed identically to a re-invite,
`InsufficientPrivilegeError: permission denied for table invitations`.

Re-granting broader UPDATE is not an option - that reopens the original hole
verbatim. The fix is the same shape as `create_organisation()`
(migration `a7c2e5f9b184`): a `SECURITY DEFINER` function that does the write
with the function owner's privileges (the migration-running role, which holds
`BYPASSRLS` and full table access) rather than the caller's, and - because it
bypasses both RLS and the column grant - enforces the equivalent checks
itself instead of leaning on either: `has_org_role` (may this caller manage
invitations at all) and `can_grant_role` (may this caller invite at this
specific role). `authenticated` keeps its `accepted_at`-only grant; nothing
about the finding-1 fix changes.

This also fixes `ISSUES.md` #44 (a genuine, separate pre-existing bug found
while verifying finding 1, not something finding 1 caused): re-inviting an
already-pending email always failed under RLS because Postgres applies a
table's UPDATE policies - not its INSERT policies - to the `DO UPDATE` branch
of an upsert, and the only UPDATE policy on `invitations` is
`invitations_update_own`, scoped to the invitee's own email, never the
inviter's. Moving the whole upsert inside a definer function sidesteps that
policy entirely (the same way `create_organisation()` sidesteps
`organisations_insert`'s RETURNING re-check), so both the original bug and
this regression are closed by the one change.

Revision ID: e15f3d9a2c78
Revises: d94b2c8f1a67
Created: 2026-08-08 15:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e15f3d9a2c78"
down_revision: str | None = "d94b2c8f1a67"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_OR_REFRESH_INVITATION = """
create or replace function public.create_or_refresh_invitation(
  target_org uuid,
  target_email citext,
  target_role public.org_role,
  target_token text,
  target_invited_by uuid,
  target_expires_at timestamptz
)
returns public.invitations
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  result public.invitations;
begin
  if not public.has_org_role(target_org, array['owner','admin']::public.org_role[]) then
    raise exception 'Your role cannot invite members to this organisation.'
      using errcode = 'insufficient_privilege';
  end if;

  if not public.can_grant_role(public.current_org_role(target_org), target_role) then
    raise exception 'Your role cannot invite someone as %.', target_role
      using errcode = 'insufficient_privilege';
  end if;

  insert into public.invitations (org_id, email, role, token, invited_by, expires_at)
  values (target_org, target_email, target_role, target_token, target_invited_by, target_expires_at)
  on conflict (org_id, (lower(email))) where accepted_at is null
  do update set role = excluded.role,
                token = excluded.token,
                invited_by = excluded.invited_by,
                expires_at = excluded.expires_at,
                created_at = now()
  returning * into result;

  return result;
end;
$$;
"""

DROP_FUNCTION = "drop function if exists public.create_or_refresh_invitation(uuid, citext, public.org_role, text, uuid, timestamptz)"


def upgrade() -> None:
    op.execute(CREATE_OR_REFRESH_INVITATION)


def downgrade() -> None:
    op.execute(DROP_FUNCTION)
