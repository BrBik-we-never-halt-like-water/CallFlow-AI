"""fix_invitation_accept_lookup_citext_cast

`public.lookup_invitation_for_accept()` (migration `202608092400`) declared
`org_slug text` in its `returns table (...)` but selected `o.slug` with no
cast - `organisations.slug` is `citext`, not `text`, so every call raised
`DatatypeMismatchError: structure of query does not match function result
type` before a single row could come back. Caught immediately by re-running
the same reproduction script that found the original bug, before this ever
reached a real user. `organisations.name` is genuinely `text` already, so
only `slug` needs the cast.

Revision ID: e2a6f8c4b719
Revises: b4e9c7f1a385
Created: 2026-08-09 21:35:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e2a6f8c4b719"
down_revision: str | None = "b4e9c7f1a385"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_FUNCTION = """
create or replace function public.lookup_invitation_for_accept(token_in text)
returns table (
  id uuid,
  org_id uuid,
  role public.org_role,
  invited_by uuid,
  accepted_at timestamptz,
  expired boolean,
  org_name text,
  org_slug text
)
language plpgsql security definer
set search_path = public, pg_temp as $$
begin
  return query
    select i.id, i.org_id, i.role, i.invited_by, i.accepted_at,
           (i.expires_at <= now()) as expired,
           o.name as org_name, o.slug::text as org_slug
    from public.invitations i
    join public.organisations o on o.id = i.org_id
    where i.token = token_in;
end;
$$;
"""

OLD_FUNCTION = """
create or replace function public.lookup_invitation_for_accept(token_in text)
returns table (
  id uuid,
  org_id uuid,
  role public.org_role,
  invited_by uuid,
  accepted_at timestamptz,
  expired boolean,
  org_name text,
  org_slug text
)
language plpgsql security definer
set search_path = public, pg_temp as $$
begin
  return query
    select i.id, i.org_id, i.role, i.invited_by, i.accepted_at,
           (i.expires_at <= now()) as expired,
           o.name as org_name, o.slug as org_slug
    from public.invitations i
    join public.organisations o on o.id = i.org_id
    where i.token = token_in;
end;
$$;
"""


def upgrade() -> None:
    op.execute(NEW_FUNCTION)


def downgrade() -> None:
    op.execute(OLD_FUNCTION)
