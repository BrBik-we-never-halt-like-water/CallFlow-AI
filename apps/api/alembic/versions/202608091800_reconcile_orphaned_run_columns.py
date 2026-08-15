"""reconcile_orphaned_run_columns

Housekeeping, not a feature. `alembic_version` on the shared Supabase
database was found pointing at revision `f2a8c6e1d9b4` - a revision with no
corresponding file anywhere in this repo's git history (checked across every
branch). The live `runs` table has two columns no migration in this repo
ever added: `idempotency_key text null` with a unique partial index on
`(org_id, idempotency_key) where idempotency_key is not null`, and
`cancel_requested_at timestamptz null`. No application code references
either column (confirmed - `repositories/runs.py::create_run` doesn't set
them, no route reads them) - the schema was applied directly, outside any
committed migration, most likely from an uncommitted file in a since-
discarded worktree, and never finished into an actual feature.

This migration formally adopts what's already live rather than papering
over the gap with a version-table stamp: `if not exists` throughout, so it
is a no-op on this database (already has both) and a real, reproducible
step on a fresh one. Chains between `67574042fc85` (the last revision this
repo's history can actually confirm was applied) and the per-creator
visibility work that follows it.

Revision ID: 059d34f56ed6
Revises: 67574042fc85
Created: 2026-08-09 18:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "059d34f56ed6"
down_revision: str | None = "67574042fc85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("alter table public.runs add column if not exists idempotency_key text null")
    op.execute(
        "alter table public.runs add column if not exists cancel_requested_at timestamptz null"
    )
    op.execute(
        """
        create unique index if not exists runs_org_idempotency_key_idx
        on public.runs (org_id, idempotency_key)
        where idempotency_key is not null
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists public.runs_org_idempotency_key_idx")
    op.execute("alter table public.runs drop column if exists cancel_requested_at")
    op.execute("alter table public.runs drop column if exists idempotency_key")
