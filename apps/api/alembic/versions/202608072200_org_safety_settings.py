"""org_safety_settings

Real, org-scoped persistence for the four safety controls Settings -> Safety
already displays but could never save (`notSaved()` on every button — the values
were always the deployment's env vars, shared by every organisation on it).

That sharing was also a real cross-tenant bug, not just an honesty gap: the daily
call budget lived in one process-global counter keyed by nothing but IP address,
so two unrelated organisations on the same deployment drained the same budget and
could rate-limit each other. This gives every organisation its own row, with every
column nullable — null means "use the deployment default", so an org that has never
touched Safety behaves exactly as before.

Revision ID: b9d4f1a6c832
Revises: a7c2e5f9b184
Created: 2026-08-07 22:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b9d4f1a6c832"
down_revision: str | None = "a7c2e5f9b184"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POLICIES = """
alter table public.org_safety_settings enable row level security;
alter table public.org_safety_settings force  row level security;

create policy org_safety_settings_select on public.org_safety_settings for select
  using (public.is_org_member(org_id));

create policy org_safety_settings_upsert on public.org_safety_settings for insert
  with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy org_safety_settings_update on public.org_safety_settings for update
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));
"""

GRANTS = "grant select, insert, update on public.org_safety_settings to authenticated;"


def upgrade() -> None:
    op.create_table(
        "org_safety_settings",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column(
            "allowlist",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("max_calls_per_run", sa.Integer(), nullable=True),
        sa.Column("calls_per_window", sa.Integer(), nullable=True),
        sa.Column("window_minutes", sa.Integer(), nullable=True),
        sa.Column("daily_budget", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("max_calls_per_run is null or max_calls_per_run > 0",
                            name="org_safety_settings_ceiling_positive"),
        sa.CheckConstraint("calls_per_window is null or calls_per_window > 0",
                            name="org_safety_settings_rate_positive"),
        sa.CheckConstraint("window_minutes is null or window_minutes > 0",
                            name="org_safety_settings_window_positive"),
        sa.CheckConstraint("daily_budget is null or daily_budget > 0",
                            name="org_safety_settings_budget_positive"),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("org_id"),
        schema="public",
    )
    op.execute(POLICIES)
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute("drop policy if exists org_safety_settings_select on public.org_safety_settings")
    op.execute("drop policy if exists org_safety_settings_upsert on public.org_safety_settings")
    op.execute("drop policy if exists org_safety_settings_update on public.org_safety_settings")
    op.drop_table("org_safety_settings", schema="public")
