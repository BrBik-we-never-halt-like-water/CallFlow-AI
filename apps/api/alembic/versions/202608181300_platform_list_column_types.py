"""Cast the platform org list's columns to their declared types.

`organisations.slug` is `citext` and `plan_id` is `varchar(32)`, but
`platform_list_organisations` declared both as `text`. Postgres does not check a
`returns table` signature against the query at creation time - it raises at *call*
time with "structure of query does not match function result type", so the function
created cleanly and failed the first time anyone actually ran it.

Cast explicitly rather than widening the declaration to match: `citext` in a
returns-table signature would make every caller's column comparison
case-insensitive, which is right for a slug lookup and wrong for everything else
reading it.

Revision ID: a4d1f8c93e26
Revises: f3c9d5e72b18
"""

from __future__ import annotations

from alembic import op

revision = "a4d1f8c93e26"
down_revision = "f3c9d5e72b18"
branch_labels = None
depends_on = None


LIST_ORGS = """
create or replace function public.platform_list_organisations(search text)
returns table (
  org_id uuid,
  name text,
  slug text,
  plan_id text,
  has_override boolean,
  member_count bigint,
  agent_count bigint,
  run_count bigint,
  created_at timestamptz
)
language plpgsql stable security definer
set search_path = public, pg_temp as $$
begin
  if not public.platform_has_capability('orgs:read') then
    raise exception 'Not permitted.' using errcode = '42501';
  end if;

  return query
    select o.id, o.name::text, o.slug::text, o.plan_id::text,
           exists (select 1 from public.org_entitlement_overrides x where x.org_id = o.id),
           (select count(*) from public.memberships m where m.org_id = o.id),
           (select count(*) from public.voice_agents v where v.org_id = o.id),
           (select count(*) from public.runs r where r.org_id = o.id),
           o.created_at
      from public.organisations o
     where o.deleted_at is null
       and (coalesce(trim(search), '') = ''
            or o.name ilike '%' || trim(search) || '%'
            or o.slug::text ilike '%' || trim(search) || '%')
     order by o.created_at desc
     limit 200;
end;
$$;
"""


def upgrade() -> None:
    op.execute(LIST_ORGS)


def downgrade() -> None:
    # Left as the working version deliberately: the previous definition raises on
    # every call, so restoring it would only reinstate the bug.
    pass
