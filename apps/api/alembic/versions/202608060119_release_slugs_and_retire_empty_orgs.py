"""release_slugs_and_retire_empty_orgs

Fixes ISSUES.md #17. An organisation was never removed when its last member left,
so dead organisations accumulated - and because the slug was globally unique, they
held their names forever. A customer who deleted their account and signed up again
from the same domain got `acme-2`.

Two changes:

* slug uniqueness becomes partial on `deleted_at IS NULL`, so a retired
  organisation releases its name;
* an organisation with no members left is soft-deleted automatically, which also
  makes it invisible to every RLS policy rather than merely unreachable.

Revision ID: 4337590dce16
Revises: b08551e6b4f6
Created: 2026-08-06 01:19:39
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4337590dce16"
down_revision: str | None = "b08551e6b4f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# AFTER DELETE, so it runs once protect_last_owner has had its say. The org-exists
# check matters: when the organisation itself is being deleted, its memberships
# cascade through here and there is nothing left to soft-delete.
RETIRE_EMPTY_ORGS = """
create or replace function public.retire_empty_organisation()
returns trigger language plpgsql security definer
set search_path = public, pg_temp as $$
begin
  if not exists (select 1 from public.organisations where id = old.org_id) then
    return old;
  end if;

  if exists (select 1 from public.memberships where org_id = old.org_id) then
    return old;
  end if;

  update public.organisations
     set deleted_at = now()
   where id = old.org_id
     and deleted_at is null;

  return old;
end;
$$;

create trigger memberships_retire_empty_organisation
  after delete on public.memberships
  for each row execute function public.retire_empty_organisation();
"""


def upgrade() -> None:
    # Retire the orphans that already exist before the new index has to enforce
    # anything, so a pre-existing duplicate cannot fail the index creation.
    op.execute(
        """
        update public.organisations o
           set deleted_at = now()
         where o.deleted_at is null
           and not exists (select 1 from public.memberships m where m.org_id = o.id)
        """
    )

    # A soft-deleted organisation must stop holding its slug.
    op.execute("alter table public.organisations drop constraint if exists organisations_slug_key")
    op.create_index(
        "organisations_slug_active_key",
        "organisations",
        ["slug"],
        unique=True,
        schema="public",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.execute(RETIRE_EMPTY_ORGS)


def downgrade() -> None:
    op.execute(
        "drop trigger if exists memberships_retire_empty_organisation on public.memberships"
    )
    op.execute("drop function if exists public.retire_empty_organisation() cascade")
    op.drop_index("organisations_slug_active_key", table_name="organisations", schema="public")
    op.create_unique_constraint(
        "organisations_slug_key", "organisations", ["slug"], schema="public"
    )
