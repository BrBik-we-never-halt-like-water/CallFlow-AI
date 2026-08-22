"""Retire the per-teammate call-count allocation. Usage credit is the one share left.

**The decision.** `member_credit_allocations.daily_allocation` let an owner give
a teammate a slice of the org-wide daily call budget - "13 calls a day" - and
was enforced at dial time (`check_dial_allowed`'s now-removed
`credits_remaining` param, `campaign_runner.py`'s `_credit_ceiling`/
`_credits_reserved` bookkeeping). Calls-per-day stopped being a meaningful
lever once the usage-credit model shipped: the org-wide daily budget is now a
uniform runaway safety rail (`RUNAWAY_CALL_CEILING`) on every plan rather than
a packaging number, and a plan's real flow limit is its usage credit. Keeping
a second, money-blind allocation next to the real one was confusing rather
than useful - a teammate could be told "13 calls a day" and still be capped
by the organisation's usage credit well before reaching it, or the reverse.

The per-teammate **usage-credit** cap (`monthly_credit_cap_paise`, same table,
`ISSUES.md` #144) is the one ceiling that remains, and it is what a teammate's
"share" now means end to end - set via `PATCH .../credit-cap`, enforced at the
run gate alongside the organisation-wide balance.

**What this drops, in Python, ahead of this migration:** `check_dial_allowed`'s
`credits_remaining` param; `CampaignRunner`'s `credit_ceiling`/
`credits_used_before_run` constructor args and its in-run reservation
bookkeeping; `credits_repo.get_allocation`/`get_enforced_ceiling`/`used_today`/
`used_today_by_member`/`list_allocations`/`set_allocation`; the
`PATCH .../members/{id}/credits` route and `CreditAllocationIn`; and the
`daily_allocation`/`used_today` fields on `TeamPerformanceOut`/`MyCreditsOut`.

Revision ID: e5b9c1f74a28
Revises: d2f8a6c93b17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5b9c1f74a28"
down_revision = "d2f8a6c93b17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "member_credit_allocations_non_negative",
        "member_credit_allocations",
        type_="check",
    )
    op.drop_column("member_credit_allocations", "daily_allocation")


def downgrade() -> None:
    op.add_column(
        "member_credit_allocations",
        sa.Column(
            "daily_allocation", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.create_check_constraint(
        "member_credit_allocations_non_negative",
        "member_credit_allocations",
        "daily_allocation >= 0",
    )
