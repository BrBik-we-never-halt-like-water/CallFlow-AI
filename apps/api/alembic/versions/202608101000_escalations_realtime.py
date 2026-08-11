"""escalations_realtime

Adds `escalations` to Supabase's Realtime publication, so an admin
assigning an escalation - or anyone resolving one - is reflected live on
every other signed-in teammate's screen without a manual refresh, per the
"proper sync and live response" requirement for cross-teammate assignment.
This is the first table in the product to use Supabase Realtime at all
(`SYSTEM.md` F27 - previously 2.5s polling only, no Realtime anywhere).

Postgres Changes authorises every event against the subscriber's own RLS
(confirmed against Supabase's current docs before writing this - "Postgres
Changes authorizes every event against each subscriber," no separate
Realtime-specific RLS setup needed) - `escalations_select` (migration
`43a7b26f6038`) is what actually scopes who receives which row's events,
identically to a normal query. `REPLICA IDENTITY FULL` is set for exactness
even though DELETE isn't part of this feature (escalations are never
deleted, only inserted/updated) - Supabase's own docs note RLS cannot be
applied to DELETE events at all without it, so this avoids that gap ever
becoming a silent problem if a delete path is added later.

Revision ID: aebc05c817cf
Revises: 3ea00413701c
Created: 2026-08-10 10:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aebc05c817cf"
down_revision: str | None = "3ea00413701c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("alter table public.escalations replica identity full;")
    op.execute("alter publication supabase_realtime add table public.escalations;")


def downgrade() -> None:
    op.execute("alter publication supabase_realtime drop table public.escalations;")
    op.execute("alter table public.escalations replica identity default;")
