"""Join the channel-pin-and-order branch to the credit-allocation-retirement branch.

Empty on purpose. Two lines of work were authored in parallel and both reached
a head:

  - `e5c9d02a7f31` - per-user channel pinning/ordering, channel soft-delete
  - `e5b9c1f74a28` - drops `member_credit_allocations.daily_allocation`, the
    retired per-teammate call-count allocation (`ISSUES.md` #146)

Alembic refuses `upgrade head` with two heads present, so they need an explicit
join. This is that join and nothing else.

**Checked for real conflict before merging.** The two branches touch disjoint
tables - `channel_members`/`channels` on one side, `member_credit_allocations`
on the other - so there is nothing to reconcile.

Revision ID: 0df78584cc38
Revises: e5c9d02a7f31, e5b9c1f74a28
"""

from __future__ import annotations

revision = "0df78584cc38"
down_revision = ("e5c9d02a7f31", "e5b9c1f74a28")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do. The join is the revision."""


def downgrade() -> None:
    """Splitting back into two heads is what dropping this row does."""
