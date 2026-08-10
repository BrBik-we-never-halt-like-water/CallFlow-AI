"""per_creator_visibility_silo

Role-based UI roadmap, Phase 1: campaigns, runs, and call_outcomes were
visible to *every* member of an org equally (`is_org_member(org_id)` on
every SELECT policy) - an operator could already see a teammate's campaigns,
runs, and call outcomes, not just their own. The product decision (confirmed
with the user): operators should see only what they created; owner, admin,
and viewer keep seeing everything in the org.

`campaigns.created_by` and `runs.started_by` already existed (set on every
insert since 202608070900) but were write-only - no policy read them, no
query selected them, no API response returned them. This migration is the
first time either column's value actually does anything.

`call_outcomes` has no owner column of its own - a call outcome's owner is
whoever started the run it belongs to, so its policy joins to `runs`
instead of adding a new column.

Write policies (`campaigns_write`, `runs_insert`/`_update`,
`call_outcomes_insert`/`_update`) are unchanged: an operator's role already
grants them write access to their own rows, and this migration only narrows
*visibility*, not the write surface.

Revision ID: d4bcc27a2b70
Revises: 059d34f56ed6
Created: 2026-08-09 20:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d4bcc27a2b70"
down_revision: str | None = "059d34f56ed6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_POLICIES = """
drop policy if exists campaigns_select on public.campaigns;
create policy campaigns_select on public.campaigns for select
  using (
    public.has_org_role(org_id, array['owner','admin','viewer']::public.org_role[])
    or created_by = public.current_user_id()
  );

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

OLD_POLICIES = """
drop policy if exists campaigns_select on public.campaigns;
create policy campaigns_select on public.campaigns for select
  using (public.is_org_member(org_id));

drop policy if exists runs_select on public.runs;
create policy runs_select on public.runs for select
  using (public.is_org_member(org_id));

drop policy if exists call_outcomes_select on public.call_outcomes;
create policy call_outcomes_select on public.call_outcomes for select
  using (public.is_org_member(org_id));
"""


def upgrade() -> None:
    op.execute(NEW_POLICIES)


def downgrade() -> None:
    op.execute(OLD_POLICIES)
