"""call_outcome_completion_signals

Module 6 of the CALL-E integration rebuild. `task_completed`,
`completion_confidence` ({score, label}), and `evidence[]` are CALL-E's own
holistic judgment of whether a call actually accomplished its task -
confirmed against the live OpenAPI spec (task-level only, never
per-recipient) - computed by CALL-E on every terminal call and, until now,
discarded on arrival (`CALLE_INTEGRATION_STATUS.md` §2.2). `attempts` keeps
the full per-attempt retry history CALL-E already tracks in
`recipients[0].attempts[]`; `campaign_runner.py` previously kept only the one
attempt `_final_attempt()` picked for its transcript, discarding the rest.

None of these live in `extracted` (the existing JSONB column) - that column
holds what a *campaign's own* `result_schema` asked for; these are CALL-E's
own meta-judgment about the call, a different concern that would collide in
meaning (and potentially in field name) with a campaign-defined field.

Revision ID: 67574042fc85
Revises: d16508451884
Created: 2026-08-09 16:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "67574042fc85"
down_revision: str | None = "d16508451884"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "call_outcomes",
        sa.Column("task_completed", sa.Boolean(), nullable=True),
        schema="public",
    )
    op.add_column(
        "call_outcomes",
        sa.Column("completion_confidence_score", sa.Float(), nullable=True),
        schema="public",
    )
    op.add_column(
        "call_outcomes",
        sa.Column("completion_confidence_label", sa.Text(), nullable=True),
        schema="public",
    )
    op.add_column(
        "call_outcomes",
        sa.Column(
            "evidence", postgresql.JSONB(), server_default="[]", nullable=False
        ),
        schema="public",
    )
    op.add_column(
        "call_outcomes",
        sa.Column(
            "attempts", postgresql.JSONB(), server_default="[]", nullable=False
        ),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("call_outcomes", "attempts", schema="public")
    op.drop_column("call_outcomes", "evidence", schema="public")
    op.drop_column("call_outcomes", "completion_confidence_label", schema="public")
    op.drop_column("call_outcomes", "completion_confidence_score", schema="public")
    op.drop_column("call_outcomes", "task_completed", schema="public")
