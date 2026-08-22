"""runs_outcomes_realtime

Adds `runs` and `call_outcomes` to Supabase's Realtime publication - same
reasoning as `escalations` (migration `aebc05c817cf`) and `share_requests`
(`bf7c636e014d`).

Every number on the dashboard - the credit count, all four KPI cards, the
monthly chart, the activity table - is derived from these two tables. Until
now they reached the client only through a 4s poll that ran *while a run's
status was `running`* and stopped the moment it settled, so a call landing
after a run finished, or any run started by a teammate, did not appear until
something else forced a refetch.

Each table's own `_select` RLS policy is what scopes which rows a subscriber
receives events for; the client's `org_id` filter is a bandwidth
optimisation, not the security boundary (see `use-org-realtime.ts`).

`replica identity full` is required for Realtime to deliver the old row on an
update or delete, matching what the two migrations above already do.

Revision ID: c8a1f5d3b704
Revises: d7e4c1b9f682
Created: 2026-08-20 05:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c8a1f5d3b704"
down_revision: str | None = "d7e4c1b9f682"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("alter table public.runs replica identity full;")
    op.execute("alter table public.call_outcomes replica identity full;")
    op.execute("alter publication supabase_realtime add table public.runs;")
    op.execute("alter publication supabase_realtime add table public.call_outcomes;")


def downgrade() -> None:
    op.execute("alter publication supabase_realtime drop table public.call_outcomes;")
    op.execute("alter publication supabase_realtime drop table public.runs;")
    op.execute("alter table public.call_outcomes replica identity default;")
    op.execute("alter table public.runs replica identity default;")
