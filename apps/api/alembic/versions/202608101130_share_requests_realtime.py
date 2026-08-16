"""share_requests_realtime

Adds `share_requests` to Supabase's Realtime publication - same reasoning
as `escalations` (migration `aebc05c817cf`): a request appearing, or being
approved/rejected, should reach both the requester and the resource's owner
live, not on their next poll. `escalations_select`'s RLS is what actually
scopes escalation events; `share_requests_select` does the identical job
here.

Revision ID: bf7c636e014d
Revises: 4cbc5103657f
Created: 2026-08-10 11:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "bf7c636e014d"
down_revision: str | None = "4cbc5103657f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("alter table public.share_requests replica identity full;")
    op.execute("alter publication supabase_realtime add table public.share_requests;")


def downgrade() -> None:
    op.execute("alter publication supabase_realtime drop table public.share_requests;")
    op.execute("alter table public.share_requests replica identity default;")
