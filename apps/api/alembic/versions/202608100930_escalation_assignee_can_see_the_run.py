"""escalation_assignee_can_see_the_run

Caught by the previous migration's own new RLS test
(`test_assigning_an_escalation_makes_it_visible_to_the_assignee`), which
failed against the real database on first run - the exact "policy that
looks right" trap CLAUDE.md calls out: `escalations_select` correctly grants
an assignee visibility into the `escalations` row itself via its
`assigned_to = current_user_id()` branch, but `escalations_repo.list_for_org()`
joins that row to `public.runs` and `public.call_outcomes` for display
(contact name, transcript, disposition...), and *those* tables' own select
policies (`runs_select`, `call_outcomes_select`, migration
`202608092000_per_creator_visibility_silo`) had no idea escalation assignment
existed - an assignee who didn't start the run themselves failed the INNER
JOIN silently and got zero rows back, despite the escalations row being
theirs to see.

Revision ID: 922eac1810fc
Revises: 43a7b26f6038
Created: 2026-08-10 09:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "922eac1810fc"
down_revision: str | None = "43a7b26f6038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE_SQL = """
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
"""

DOWNGRADE_SQL = """
drop policy if exists runs_select on public.runs;
create policy runs_select on public.runs for select
  using (
    public.has_org_role(org_id, array['owner','admin','viewer']::public.org_role[])
    or started_by = public.current_user_id()
  );

drop policy if exists call_outcomes_select on public.call_outcomes;
create policy call_outcomes_select on public.call_outcomes for select
  using (
    public.has_org_role(org_id, array['owner','admin','viewer']::public.org_role[])
    or exists (
      select 1 from public.runs r
      where r.id = call_outcomes.run_id and r.started_by = public.current_user_id()
    )
  );
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
