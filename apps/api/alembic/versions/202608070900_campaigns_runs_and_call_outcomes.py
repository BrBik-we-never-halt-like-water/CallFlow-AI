"""campaigns_runs_and_call_outcomes

Replaces the in-memory campaign registry and run store (ISSUES.md #1, #2) with
real, org-scoped Postgres tables. Built-in campaigns deliberately stay as Python
constants in app/domain/campaigns.py rather than being seeded here — they are
global templates with no owning tenant, and CLAUDE.md's non-negotiable #1
("every tenant-scoped table has org_id NOT NULL") is easier to honour exactly
than to carve an exception into. `runs.campaign_id` is therefore not a foreign
key: it may reference a built-in id (resolved in code) or a row in
`campaigns` (resolved here) — application code, not the database, decides which.

Also fixes ISSUES.md #4: `CallOutcome.run_id` held the *provider's* call id,
not the run id, because there was nowhere else to put it. Now that an outcome
is a real row with a real `run_id` foreign key, the provider's id gets its own
column (`provider_call_id`) and the app-level rename follows in the same
change (see main.py / campaign_runner.py / the frontend `Outcome` type).

Revision ID: c7a4e9f21b58
Revises: b3f8a1c4e6d2
Created: 2026-08-07 09:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c7a4e9f21b58"
down_revision: str | None = "b3f8a1c4e6d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


POLICIES = """
alter table public.campaigns enable row level security;
alter table public.campaigns force  row level security;
alter table public.runs enable row level security;
alter table public.runs force  row level security;
alter table public.call_outcomes enable row level security;
alter table public.call_outcomes force  row level security;

create policy campaigns_select on public.campaigns for select
  using (public.is_org_member(org_id));
create policy campaigns_write on public.campaigns for all
  using (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

create policy runs_select on public.runs for select
  using (public.is_org_member(org_id));
-- insert/update, not delete: a run is a record, not something anyone edits away.
create policy runs_insert on public.runs for insert
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));
create policy runs_update on public.runs for update
  using (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

create policy call_outcomes_select on public.call_outcomes for select
  using (public.is_org_member(org_id));
create policy call_outcomes_insert on public.call_outcomes for insert
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));
create policy call_outcomes_update on public.call_outcomes for update
  using (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));
"""

GRANTS = """
grant select, insert, update, delete on public.campaigns      to authenticated;
grant select, insert, update         on public.runs           to authenticated;
grant select, insert, update         on public.call_outcomes  to authenticated;
"""

TOUCH_TRIGGER = """
create trigger campaigns_touch_updated_at before update on public.campaigns
  for each row execute function public.touch_updated_at();
"""


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("goal_template", sa.Text(), nullable=False),
        sa.Column("outcome_fields", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("result_schema", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("escalate_on_negative", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["public.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index("campaigns_org_idx", "campaigns", ["org_id"], schema="public")

    op.create_table(
        "runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.Text(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), server_default="running", nullable=False),
        sa.Column("started_by", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["started_by"], ["public.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index(
        "runs_org_started_idx", "runs", ["org_id", sa.text("started_at DESC")], schema="public"
    )

    op.create_table(
        "call_outcomes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("contact_name", sa.Text(), nullable=False),
        sa.Column("phone_masked", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="UNKNOWN", nullable=False),
        # The provider's own call id — was previously smuggled into the domain
        # model's `run_id` field for lack of anywhere else to put it (ISSUES #4).
        sa.Column("provider_call_id", sa.Text(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("sentiment_reason", sa.Text(), nullable=True),
        sa.Column("extracted", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("disposition", sa.Text(), server_default="skipped", nullable=False),
        sa.Column("disposition_reason", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["public.runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "contact_name", "phone_masked", name="call_outcomes_run_contact_key"
        ),
        schema="public",
    )
    op.create_index("call_outcomes_run_idx", "call_outcomes", ["run_id"], schema="public")

    op.execute(POLICIES)
    op.execute(GRANTS)
    op.execute(TOUCH_TRIGGER)


def downgrade() -> None:
    op.execute("drop trigger if exists campaigns_touch_updated_at on public.campaigns")
    op.drop_index("call_outcomes_run_idx", table_name="call_outcomes", schema="public")
    op.drop_table("call_outcomes", schema="public")
    op.drop_index("runs_org_started_idx", table_name="runs", schema="public")
    op.drop_table("runs", schema="public")
    op.drop_index("campaigns_org_idx", table_name="campaigns", schema="public")
    op.drop_table("campaigns", schema="public")
