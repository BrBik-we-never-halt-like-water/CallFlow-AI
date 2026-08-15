"""escalations_and_credit_allocations

Two new tables for the role-based UI + teammate collaboration roadmap's
Phase 2 (real, persisted, assignable escalations) and a minimal slice of
Phase 5 (per-teammate credit allocation).

`escalations` replaces the computed, unpersisted "needs a person" state
ISSUES.md #7 already flagged: today a "flare" outcome (`Disposition.ESCALATED`
or `Disposition.UNREACHABLE` - the same two dispositions `lib/lamp.ts` groups
into the "Needs a person" lamp everywhere in the UI) is never stored as its
own row, and "resolving" one is local React state that reverts on reload.
One row per `call_outcomes` id (enforced by the unique constraint on
`call_outcome_id`), inserted by application code alongside the existing
`append_outcome()` call, not a trigger - this codebase's established
convention for business logic (`campaign_runner.py`'s own outcome-resolution
path is the only writer).

`member_credit_allocations` is a subdivision of the org's existing
`org_safety_settings.daily_budget`, not a parallel system - the org-wide
ceiling still applies on top; this table only tracks how an admin/owner has
chosen to split that budget's *display* across teammates today, not a
separate spending limit enforced at dial time (that enforcement is
out of scope for this slice - see the roadmap doc, Phase 5).

Revision ID: 43a7b26f6038
Revises: f3d8a1c6e492
Created: 2026-08-10 09:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "43a7b26f6038"
down_revision: str | None = "f3d8a1c6e492"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


POLICIES = """
alter table public.escalations enable row level security;
alter table public.escalations force  row level security;

-- Same breadth as runs_select's owner/admin/viewer branch (migration
-- 202608092000), plus the escalation's own assignee - an operator sees
-- their own run's escalations via the third clause even without
-- runs:read_team, matching how they already see their own runs.
create policy escalations_select on public.escalations for select
  using (
    public.has_org_role(org_id, array['owner','admin','viewer']::public.org_role[])
    or assigned_to = public.current_user_id()
    or exists (
      select 1 from public.runs r
      where r.id = escalations.run_id and r.started_by = public.current_user_id()
    )
  );

-- Inserted by application code from inside the same `database.as_user()`
-- context that writes the triggering call_outcome - always the run's own
-- starter's identity (CampaignRunner's poll path and the CALL-E webhook
-- path both resolve to `owner.auth_user_id`), never a plain org-role check.
create policy escalations_insert on public.escalations for insert
  with check (
    exists (
      select 1 from public.runs r
      where r.id = escalations.run_id
        and r.org_id = escalations.org_id
        and r.started_by = public.current_user_id()
    )
  );

-- One policy covers both assign and resolve - which *fields* a given route
-- may actually change is the application's job (Permission.ESCALATIONS_ASSIGN
-- vs ESCALATIONS_RESOLVE), this is only "can you touch this row at all."
create policy escalations_update on public.escalations for update
  using (
    public.has_org_role(org_id, array['owner','admin']::public.org_role[])
    or assigned_to = public.current_user_id()
    or exists (
      select 1 from public.runs r
      where r.id = escalations.run_id and r.started_by = public.current_user_id()
    )
  )
  with check (
    public.has_org_role(org_id, array['owner','admin']::public.org_role[])
    or assigned_to = public.current_user_id()
    or exists (
      select 1 from public.runs r
      where r.id = escalations.run_id and r.started_by = public.current_user_id()
    )
  );

alter table public.member_credit_allocations enable row level security;
alter table public.member_credit_allocations force  row level security;

create policy member_credit_allocations_select on public.member_credit_allocations for select
  using (
    user_id = public.current_user_id()
    or public.has_org_role(org_id, array['owner','admin','viewer']::public.org_role[])
  );

create policy member_credit_allocations_insert on public.member_credit_allocations for insert
  with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy member_credit_allocations_update on public.member_credit_allocations for update
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));
"""

GRANTS = """
grant select, insert, update on public.escalations                to authenticated;
grant select, insert, update on public.member_credit_allocations  to authenticated;
"""


def upgrade() -> None:
    op.create_table(
        "escalations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("call_outcome_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("assigned_to", sa.UUID(), nullable=True),
        sa.Column("assigned_by", sa.UUID(), nullable=True),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status in ('open', 'resolved')", name="escalations_status_valid"),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["public.runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["call_outcome_id"], ["public.call_outcomes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to"], ["public.users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_by"], ["public.users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by"], ["public.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_outcome_id", name="escalations_call_outcome_id_key"),
        schema="public",
    )
    op.create_index("escalations_org_idx", "escalations", ["org_id"], schema="public")
    op.create_index("escalations_run_idx", "escalations", ["run_id"], schema="public")
    op.create_index("escalations_assigned_to_idx", "escalations", ["assigned_to"], schema="public")
    op.create_index(
        "escalations_org_open_idx",
        "escalations",
        ["org_id"],
        schema="public",
        postgresql_where=sa.text("status = 'open'"),
    )

    op.create_table(
        "member_credit_allocations",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("daily_allocation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("daily_allocation >= 0", name="member_credit_allocations_non_negative"),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["public.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("org_id", "user_id"),
        schema="public",
    )

    op.execute(POLICIES)
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute("drop policy if exists escalations_select on public.escalations")
    op.execute("drop policy if exists escalations_insert on public.escalations")
    op.execute("drop policy if exists escalations_update on public.escalations")
    op.execute(
        "drop policy if exists member_credit_allocations_select on public.member_credit_allocations"
    )
    op.execute(
        "drop policy if exists member_credit_allocations_insert on public.member_credit_allocations"
    )
    op.execute(
        "drop policy if exists member_credit_allocations_update on public.member_credit_allocations"
    )
    op.drop_table("member_credit_allocations", schema="public")
    op.drop_table("escalations", schema="public")
