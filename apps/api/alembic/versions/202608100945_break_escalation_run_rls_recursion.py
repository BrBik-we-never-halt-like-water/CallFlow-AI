"""break_escalation_run_rls_recursion

The previous migration's own new policies caused
`asyncpg.exceptions.InvalidObjectDefinitionError: infinite recursion detected
in policy for relation "runs"` on every second read (caught immediately by
running the test suite before moving on, not by the earlier migration's own
review): `runs_select` now queries `public.escalations`, whose own
`escalations_select` policy queries `public.runs` right back -
`initial_schema`'s own documented lesson ("a policy on memberships that
queried memberships directly would recurse infinitely... running inside a
[security definer] function bypasses RLS and breaks the cycle") applies
identically here, just across two tables instead of one.

Fixes it the same way that comment already prescribes: the two new
cross-table checks this feature added go through `SECURITY DEFINER` helper
functions instead of a plain correlated subquery, so evaluating them never
re-triggers the calling policy.

Revision ID: 3ea00413701c
Revises: 922eac1810fc
Created: 2026-08-10 09:45:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "3ea00413701c"
down_revision: str | None = "922eac1810fc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
create or replace function public.is_assigned_to_run_escalation(target_run text)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
  select exists (
    select 1 from public.escalations e
    where e.run_id = target_run and e.assigned_to = public.current_user_id()
  );
$$;

create or replace function public.is_assigned_to_call_outcome_escalation(target_call_outcome uuid)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
  select exists (
    select 1 from public.escalations e
    where e.call_outcome_id = target_call_outcome and e.assigned_to = public.current_user_id()
  );
$$;

drop policy if exists runs_select on public.runs;
create policy runs_select on public.runs for select
  using (
    public.has_org_role(org_id, array['owner','admin','viewer']::public.org_role[])
    or started_by = public.current_user_id()
    or public.is_assigned_to_run_escalation(id)
  );

drop policy if exists call_outcomes_select on public.call_outcomes;
create policy call_outcomes_select on public.call_outcomes for select
  using (
    public.has_org_role(org_id, array['owner','admin','viewer']::public.org_role[])
    or exists (
      select 1 from public.runs r
      where r.id = call_outcomes.run_id and r.started_by = public.current_user_id()
    )
    or public.is_assigned_to_call_outcome_escalation(id)
  );
"""

DOWNGRADE_SQL = """
drop policy if exists runs_select on public.runs;
create policy runs_select on public.runs for select
  using (
    public.has_org_role(org_id, array['owner','admin','viewer']::public.org_role[])
    or started_by = public.current_user_id()
    or exists (
      select 1 from public.escalations e
      where e.run_id = runs.id and e.assigned_to = public.current_user_id()
    )
  );

drop policy if exists call_outcomes_select on public.call_outcomes;
create policy call_outcomes_select on public.call_outcomes for select
  using (
    public.has_org_role(org_id, array['owner','admin','viewer']::public.org_role[])
    or exists (
      select 1 from public.runs r
      where r.id = call_outcomes.run_id and r.started_by = public.current_user_id()
    )
    or exists (
      select 1 from public.escalations e
      where e.call_outcome_id = call_outcomes.id and e.assigned_to = public.current_user_id()
    )
  );

drop function if exists public.is_assigned_to_run_escalation(text);
drop function if exists public.is_assigned_to_call_outcome_escalation(uuid);
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
