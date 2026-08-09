"""invitation_invited_by_from_caller_identity

Security audit finding (role-based UI roadmap, Phase 1 follow-up, prompted by
the Supabase Postgres security checklist's SECURITY DEFINER guidance):
`public.create_or_refresh_invitation()` (migration `e15f3d9a2c78`) correctly
anchors *authorisation* to the caller's own identity - `has_org_role` and
`can_grant_role` both resolve through `public.current_user_id()` internally -
but it took `target_invited_by` as a plain argument and wrote it verbatim
into `invitations.invited_by`, never checking it matched the caller at all.

This function is `SECURITY DEFINER` in the exposed `public` schema, and
Postgres grants `EXECUTE` to `PUBLIC` on new functions by default, which
flows to `anon`/`authenticated` - Supabase's Data API exposes every public
function as a callable RPC endpoint unless a project has deliberately turned
that off. The one caller in this codebase (`org_repo.create_invitation()`)
always passed the authenticated user's own id, so nothing in the app itself
was ever affected - but a caller reaching this function directly (bypassing
the FastAPI backend entirely, e.g. via Supabase's REST RPC surface with
nothing more than their own valid session) could forge `invited_by` to any
UUID, corrupting the one field this product uses to answer "who invited
this person" - the same attribution integrity `created_by`/`started_by`
exist to provide elsewhere (migration `202608092000`).

Fix: drop `target_invited_by` as a parameter entirely and derive it from
`public.current_user_id()` inside the function, the same anchor already
used for the authorisation checks right above it. The one real call site is
unaffected - it always passed its own id anyway.

Revision ID: d7f3a8c2e951
Revises: c8e2f4a1b7d3
Created: 2026-08-09 23:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d7f3a8c2e951"
down_revision: str | None = "c8e2f4a1b7d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DROP_OLD_SIGNATURE = (
    "drop function if exists public.create_or_refresh_invitation"
    "(uuid, citext, public.org_role, text, uuid, timestamptz)"
)

CREATE_NEW_SIGNATURE = """
create function public.create_or_refresh_invitation(
  target_org uuid,
  target_email citext,
  target_role public.org_role,
  target_token text,
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
  values (target_org, target_email, target_role, target_token, public.current_user_id(), target_expires_at)
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

DROP_NEW_SIGNATURE = (
    "drop function if exists public.create_or_refresh_invitation"
    "(uuid, citext, public.org_role, text, timestamptz)"
)

RECREATE_OLD_SIGNATURE = """
create function public.create_or_refresh_invitation(
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


def upgrade() -> None:
    op.execute(DROP_OLD_SIGNATURE)
    op.execute(CREATE_NEW_SIGNATURE)


def downgrade() -> None:
    op.execute(DROP_NEW_SIGNATURE)
    op.execute(RECREATE_OLD_SIGNATURE)
