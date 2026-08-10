"""runs_safety_snapshot

A run's actual guards - the effective ceiling, allowlist, rate window, and
daily budget it was governed by - were never recorded anywhere. `resolve_safety_settings()`
merges an organisation's `org_safety_settings` row onto the deployment defaults fresh on
every read, so once an organisation's settings change, no past run's real guards can be
reconstructed - not even a non-overridden run's. For a product whose entire premise is that
the guards are real and enforced, that is an audit gap: nothing could answer "what ceiling
actually governed this run" after the fact.

Five nullable columns on `public.runs`, one per `EffectiveSafety` field (matching
`org_safety_settings`'s own column names/types exactly). Nullable, not backfilled: a run
created before this migration genuinely has no recorded snapshot, and defaulting it to
today's settings would fabricate history rather than admit the gap. Every run created from
here on always gets a real, non-null snapshot - `start_run()` stores the exact `effective`
object that governed its own dial gate and rate-limit check, so there is no way for what's
recorded to drift from what was actually enforced.

Revision ID: a3f7c9e2b6d8
Revises: f2a8c6e1d9b4
Created: 2026-08-09 15:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a3f7c9e2b6d8"
down_revision: str | None = "f2a8c6e1d9b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs", sa.Column("max_calls_per_run", sa.Integer(), nullable=True), schema="public"
    )
    op.add_column(
        "runs",
        sa.Column("allowlist", postgresql.ARRAY(sa.Text()), nullable=True),
        schema="public",
    )
    op.add_column(
        "runs", sa.Column("calls_per_window", sa.Integer(), nullable=True), schema="public"
    )
    op.add_column(
        "runs", sa.Column("window_minutes", sa.Integer(), nullable=True), schema="public"
    )
    op.add_column(
        "runs", sa.Column("daily_budget", sa.Integer(), nullable=True), schema="public"
    )


def downgrade() -> None:
    op.drop_column("runs", "daily_budget", schema="public")
    op.drop_column("runs", "window_minutes", schema="public")
    op.drop_column("runs", "calls_per_window", schema="public")
    op.drop_column("runs", "allowlist", schema="public")
    op.drop_column("runs", "max_calls_per_run", schema="public")
