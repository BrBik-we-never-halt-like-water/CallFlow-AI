"""organisation_create_function

Fixes a real bug found in production use: creating a second organisation from the
dashboard always failed with `InsufficientPrivilegeError: new row violates row-level
security policy for table "organisations"`, even though `current_user_id()` resolved
correctly and the `organisations_insert` policy's own check (`current_user_id() is not
null`) was satisfied.

The actual cause is `RETURNING` on an RLS-protected, force-enabled table: Postgres
re-checks the newly inserted row against the table's `SELECT` policy
(`organisations_select`, which requires `is_org_member(id)`) before it can hand the row
back via `RETURNING`. `org_repo.create()` inserted into `organisations` - with
`RETURNING` - *before* the follow-up insert into `memberships` that would make the
caller an actual member. At the moment of that first `RETURNING`, no membership row
exists yet for the brand-new org, so `is_org_member(id)` is false and Postgres raises
rather than silently returning nothing.

This is the exact chicken-and-egg problem the signup trigger already solves, just not
through a route the dashboard's own "create organisation" button went through: the
trigger is `SECURITY DEFINER`, owned by a role with `BYPASSRLS`, so its inserts never
hit a policy check at all. `create_organisation()` gives the API the same escape hatch
for a user-initiated create, instead of duplicating the trigger's logic under a
regular RLS-scoped connection where this bug can recur.

Revision ID: a7c2e5f9b184
Revises: f6a3c9d1b527
Created: 2026-08-07 20:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a7c2e5f9b184"
down_revision: str | None = "f6a3c9d1b527"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_ORGANISATION_FUNCTION = """
create or replace function public.create_organisation(org_name text)
returns table(id uuid, name text, slug citext, logo_url text)
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  new_org_id uuid;
  new_slug   text;
  owner_id   uuid := public.current_user_id();
begin
  if owner_id is null then
    raise exception 'Not signed in.' using errcode = '28000';
  end if;

  new_slug := public.unique_org_slug(org_name);

  insert into public.organisations (name, slug, country, timezone, onboarded_at)
  values (org_name, new_slug, 'IN', 'Asia/Kolkata', now())
  returning organisations.id into new_org_id;

  insert into public.memberships (org_id, user_id, role)
  values (new_org_id, owner_id, 'owner');

  return query
    select o.id, o.name, o.slug, o.logo_url
    from public.organisations o
    where o.id = new_org_id;
end;
$$;
"""

DROP_FUNCTION = "drop function if exists public.create_organisation(text)"


def upgrade() -> None:
    op.execute(CREATE_ORGANISATION_FUNCTION)


def downgrade() -> None:
    op.execute(DROP_FUNCTION)
