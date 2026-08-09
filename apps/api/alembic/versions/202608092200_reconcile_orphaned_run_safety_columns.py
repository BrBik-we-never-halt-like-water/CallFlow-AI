"""reconcile_orphaned_run_safety_columns

Same failure mode as `202608091800_reconcile_orphaned_run_columns`, a second
time in one session: `alembic_version` on the shared database had advanced to
`a3f7c9e2b6d8`, a revision with no corresponding file anywhere in this repo's
git history (checked across every local and remote branch, not just this
one) - almost certainly another uncommitted/discarded worktree or branch
applying a migration directly against the shared Supabase instance, same as
before.

Live-schema inspection found five orphaned columns on `public.runs`, mirroring
`public.org_safety_settings`'s own columns exactly:

    max_calls_per_run integer null
    allowlist         text[] null
    calls_per_window  integer null
    window_minutes    integer null
    daily_budget      integer null

All five are `null` on every existing row (6 runs, all null), and no
application code selects, inserts, or updates any of them - confirmed by
searching the whole `apps/api/app` tree, not just `repositories/runs.py`.
This reads as an in-progress "snapshot the org's safety settings onto the
run at the moment it starts" feature (so a run's own history stays accurate
even if the org's settings change later) - a reasonable direction, but
schema-only and not wired to anything yet, so there is nothing here for this
migration to risk breaking.

As with the first orphan, this migration formally adopts the columns (idempotent
`add column if not exists`, so it's a no-op on the already-patched live database
and a real step on a fresh one) rather than silently re-stamping past them - the
alternative would leave a fresh database unable to reach the same schema this
one already has.

Revision ID: c8e2f4a1b7d3
Revises: 9b6e1c3a7f42
Created: 2026-08-09 22:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c8e2f4a1b7d3"
down_revision: str | None = "9b6e1c3a7f42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("alter table public.runs add column if not exists max_calls_per_run integer null")
    op.execute("alter table public.runs add column if not exists allowlist text[] null")
    op.execute("alter table public.runs add column if not exists calls_per_window integer null")
    op.execute("alter table public.runs add column if not exists window_minutes integer null")
    op.execute("alter table public.runs add column if not exists daily_budget integer null")


def downgrade() -> None:
    op.execute("alter table public.runs drop column if exists daily_budget")
    op.execute("alter table public.runs drop column if exists window_minutes")
    op.execute("alter table public.runs drop column if exists calls_per_window")
    op.execute("alter table public.runs drop column if exists allowlist")
    op.execute("alter table public.runs drop column if exists max_calls_per_run")
