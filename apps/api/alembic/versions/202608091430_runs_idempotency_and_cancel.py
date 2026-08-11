"""runs_idempotency_and_cancel

Two independent additions to `public.runs`, both from the runs-feature audit:

`idempotency_key` closes a real gap against CLAUDE.md non-negotiable #6
("every mutating endpoint safe to run twice"): `POST /api/v1/runs` had no way
to make a retried or double-submitted request safe, and a duplicate here means
a second real phone call to a real person, not just a duplicate row. A caller
may send an `Idempotency-Key` header; replaying the same key returns the
original run instead of starting a second one. The partial unique index only
applies where the key is actually set, so callers that omit it (nothing
requires it) are completely unaffected.

`cancel_requested_at` backs a real cancel endpoint. Previously "Pause run" only
stopped the browser from polling - there was no way to actually stop a run
once started. The column is a request marker, not a status by itself: the
background loop checks it between contacts and stops dialling further ones,
but cannot un-ring a phone already in conversation.

Revision ID: f2a8c6e1d9b4
Revises: e15f3d9a2c78
Created: 2026-08-09 14:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2a8c6e1d9b4"
down_revision: str | None = "e15f3d9a2c78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs", sa.Column("idempotency_key", sa.Text(), nullable=True), schema="public"
    )
    op.add_column(
        "runs",
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        schema="public",
    )
    op.create_index(
        "runs_org_idempotency_key_idx",
        "runs",
        ["org_id", "idempotency_key"],
        unique=True,
        schema="public",
        postgresql_where=sa.text("idempotency_key is not null"),
    )


def downgrade() -> None:
    op.drop_index("runs_org_idempotency_key_idx", table_name="runs", schema="public")
    op.drop_column("runs", "cancel_requested_at", schema="public")
    op.drop_column("runs", "idempotency_key", schema="public")
