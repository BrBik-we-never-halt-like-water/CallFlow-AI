"""The daily call cap stops being a plan feature and becomes a runaway bound.

Usage credit is now the economic limit, and it binds first by a wide margin. At
90-second calls Free's Rs 100 allows 44 calls a *month* against a cap of 600, and
Growth's Rs 4,250 allows about 63 a day against 1,000. So 20/200/1,000 were
numbers no customer could reach - they looked like limits and were not, and they
described neither of the two real answers (44 calls at 90 seconds, 11 at six
minutes).

Worse, with both limits live, whichever one binds depends on the customer's
average call length rather than on anything either number says. A caller averaging
90 seconds would have hit the call cap with credit unspent; one averaging six
minutes runs out of credit at a fraction of the cap.

So the cap is levelled to one value on every plan and removed from the pricing
page. It is **not** removed from the product: credit limits money spent, not how
many people a loop can disturb in an hour, and that is a different guard worth
keeping (CLAUDE.md §4 #8). An organisation may still set itself lower in
Settings -> Safety, and `resolve_safety_settings` takes the `min()`.

500 is chosen to sit far above what any plan's credit permits, so it can never be
the commercially binding limit - only the bound on something going wrong.

Revision ID: f1b6a3d94c72
Revises: e8a4d1c72b56
"""

from __future__ import annotations

from alembic import op

revision = "f1b6a3d94c72"
down_revision = "e8a4d1c72b56"
branch_labels = None
depends_on = None

RUNAWAY_CALL_CEILING = 500


def upgrade() -> None:
    op.execute(
        f"update public.plan_entitlements set daily_call_budget = {RUNAWAY_CALL_CEILING}"
    )


def downgrade() -> None:
    # The per-plan values as they were, so a rollback restores the old packaging
    # rather than leaving every plan on a number that was never seeded.
    for plan_id, budget in (
        ("free", 20),
        ("starter", 200),
        ("growth", 1000),
        ("enterprise", 1000),
    ):
        op.execute(
            f"update public.plan_entitlements set daily_call_budget = {budget} "
            f"where plan_id = '{plan_id}'"
        )
