"""Usage credit: granting it, pricing a call, and spending it.

Sits between the pure arithmetic in `domain/rates.py` and the SQL in
`repositories/credits.py`. Its job is the lookups neither of those may do: read
the card, resolve each leg's tier, decide whose key paid, and turn a plan into a
grant.

Kept out of `services/billing.py` deliberately. That module is about the
subscription - checkout, webhooks, state transitions - and this one is about
consumption. They meet in exactly one place (`grant_for_period`, called when a
subscription activates or renews), and one import is cheaper than one module
doing two jobs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from app.core.config import config
from app.database.repositories import credits as credits_repo
from app.database.repositories import usage_rates as rates_repo
from app.domain.plans import Entitlements
from app.domain.rates import (
    UNKNOWN_PROVIDER_TIER,
    CallRate,
    Leg,
    LegUsage,
    estimated_minutes,
    reserve_for,
    resolve_rate,
    spend_for,
)

log = logging.getLogger("callflow.credit")

#: What a hold assumes a call will last. Deliberately far below the carrier's own
#: 900-second ceiling - see `domain.rates.reserve_for` for why holding the worst
#: case would exhaust a month's credit on calls that had not happened.
TYPICAL_CALL_SECONDS = 180

#: How long past the carrier ceiling a hold may sit before the reaper takes it
#: back. Twice the ceiling, matching `internal._STALE_AFTER_SECONDS`: anything
#: older than that never reported and never will.
STALE_HOLD_SECONDS = int(config.poll_timeout_seconds) * 2


@dataclass(frozen=True)
class PipelineLeg:
    """One leg of an agent's pipeline as the product configured it."""

    leg: Leg
    provider_id: str | None
    #: True when CallFlow's own vendor account paid for this leg.
    #:
    #: **Always false today**, and that is not a placeholder - it is the truth.
    #: Every key a call uses is read from `ai_provider_credentials`, the
    #: organisation's own table; there is no platform credential in `config`, no
    #: fallback in the worker's `AgentSpec`, and no path that could supply one. So
    #: every call is bring-your-own by necessity and every rate is the platform
    #: fee alone. The tier add-ons are seeded and tested but unreachable until
    #: CallFlow holds vendor accounts of its own.
    on_platform_key: bool = False


async def rate_for(conn: asyncpg.Connection, legs: tuple[PipelineLeg, ...]) -> CallRate:
    """What a minute of this pipeline costs.

    A leg with no provider, or one nobody tiered, resolves to premium
    (`UNKNOWN_PROVIDER_TIER`). Only legs on CallFlow's key are charged at all, so
    for a bring-your-own pipeline the tier is irrelevant and this returns the
    platform fee - which is the whole shape of the model.
    """
    card = await rates_repo.load_rate_card(conn)
    if card.platform_fee <= 0:
        # Not raised: a call must not fail because a price is unset, and the
        # ledger records what was actually charged either way. Logged loudly
        # because it means the deployment is giving the product away.
        log.error("usage_rates has no platform fee - calls are being priced at zero")

    billable = tuple(leg for leg in legs if leg.on_platform_key and leg.provider_id)
    tiers = await rates_repo.tiers_for(
        conn, tuple((leg.leg, leg.provider_id) for leg in billable if leg.provider_id)
    )

    return resolve_rate(
        card,
        tuple(
            LegUsage(
                leg=leg.leg,
                tier=(
                    tiers.get((leg.leg, leg.provider_id or ""), UNKNOWN_PROVIDER_TIER)
                    if leg.on_platform_key
                    else UNKNOWN_PROVIDER_TIER
                ),
                on_platform_key=leg.on_platform_key,
            )
            for leg in legs
        ),
    )


async def grant_for_period(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    entitlements: Entitlements,
    period_key: str,
    expire_remainder: bool,
) -> bool:
    """Give an organisation its plan's credit for one period.

    `period_key` is what makes this idempotent, so it must identify the *period* -
    a subscription id plus a period end, never a timestamp taken here. A renewal
    webhook delivered twice must grant once.

    `expire_remainder` is true on a renewal and false on a first activation. Plan
    credit does not roll over, and writing the unused part off as an explicit
    ledger entry is what lets a customer see where it went, rather than watching a
    number quietly reset.
    """
    allowance = entitlements.monthly_credit_paise
    if allowance is None:
        # Uncapped. Nothing to grant, and nothing should be spending against a
        # balance either - the dial gate treats an uncapped plan as ungated.
        return False
    if allowance <= 0:
        return False

    if expire_remainder:
        await credits_repo.expire_remainder(
            conn,
            org_id=org_id,
            dedupe_key=f"expiry:{period_key}",
            reason="unused credit does not roll over",
        )

    return await credits_repo.grant(
        conn,
        org_id=org_id,
        amount_paise=allowance,
        dedupe_key=f"grant:{period_key}",
        reason="plan credit for this period",
    )


async def grant_for_topup(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    amount_paise: int,
    gateway_payment_id: str,
) -> bool:
    """Grant usage credit for one settled credit-pack purchase.

    A top-up is not a subscription period, so it has no `period_key` - the
    dedupe key is the payment id itself, already unique per payment (it is the
    unique index `payments` is keyed on), which is exactly what a redelivered
    `payment.succeeded` needs to grant once. One paise of credit per one paise
    paid: `docs/PRICING_DECISIONS.md` §7's model, and the simplest one that
    needs no separate price-to-credit table.
    """
    if amount_paise <= 0:
        return False
    return await credits_repo.grant(
        conn,
        org_id=org_id,
        amount_paise=amount_paise,
        dedupe_key=f"topup:{gateway_payment_id}",
        reason="usage credit top-up",
    )


async def ensure_period_credit(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    entitlements: Entitlements,
    has_subscription: bool,
    now: datetime | None = None,
) -> bool:
    """Give an unsubscribed organisation its plan's credit for this calendar month.

    **Why this exists.** `grant_for_period` is driven by subscription webhooks, and
    a Free organisation has no subscription - so without this it would never
    receive the credit its plan advertises, its balance would sit at zero, and the
    dial gate would refuse every call. Free would be undialable while the pricing
    page promised otherwise.

    Only for organisations *without* a live subscription. A subscribed one is
    granted by its own renewal, keyed on the gateway period, and granting here too
    would hand it two allowances a month.

    Idempotent on a calendar-month key, so calling it on every read is safe and
    the month rolls over on its own. Deliberately lazy rather than a scheduled
    job: there is no scheduler in this deployment, and a grant that only happens
    when someone looks is still a grant that happens before they can spend it.
    """
    if has_subscription:
        return False
    if entitlements.monthly_credit_paise is None:
        return False

    stamp = (now or datetime.now(UTC)).strftime("%Y-%m")
    return await credits_repo.grant(
        conn,
        org_id=org_id,
        amount_paise=entitlements.monthly_credit_paise,
        # Keyed on the plan too: an organisation that moves between unsubscribed
        # plans inside one month gets the new plan's allowance rather than being
        # told it already had one.
        dedupe_key=f"grant:plan:{entitlements.monthly_credit_paise}:{stamp}",
        reason=f"plan credit for {stamp}",
    )


async def reserve_for_call(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    user_id: UUID | None,
    call_key: str,
    rate: CallRate,
) -> int:
    """Hold a typical call's worth before dialling. Returns what was held.

    Zero means the hold was already placed for this call - a retry, not a
    failure. The caller should proceed either way: the money is committed.
    """
    amount = reserve_for(rate, TYPICAL_CALL_SECONDS)
    if amount <= 0:
        return 0
    placed = await credits_repo.hold(
        conn,
        org_id=org_id,
        user_id=user_id,
        call_key=call_key,
        amount_paise=amount,
        rate_paise_per_minute=rate.paise_per_minute,
    )
    return amount if placed else 0


async def settle_call(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    user_id: UUID | None,
    call_key: str,
    rate: CallRate,
    duration_seconds: float | None,
) -> int:
    """Charge the actual duration and give the hold back. Returns what was spent.

    A call that never connected spends nothing and has its hold released in full -
    `spend_for` returns zero for a `None` or non-positive duration, and the
    definer function still reverses the hold.
    """
    spend = spend_for(rate, duration_seconds)
    await credits_repo.settle(
        conn,
        org_id=org_id,
        user_id=user_id,
        call_key=call_key,
        spend_paise=spend,
        rate_paise_per_minute=rate.paise_per_minute,
    )
    return spend


@dataclass(frozen=True)
class CreditOverview:
    """What Billing shows. Money is the truth; minutes are an estimate."""

    balance_paise: int
    granted_this_period_paise: int
    rate_paise_per_minute: int
    estimated_minutes_left: int
    is_uncapped: bool


async def overview(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    entitlements: Entitlements,
    rate: CallRate,
) -> CreditOverview:
    """The balance, and how many minutes it buys *at the current rate*.

    The minutes figure is derived and must be labelled an estimate wherever it is
    shown: the next call may use a different pipeline and therefore a different
    rate. With a 23x spread across pipelines there is no single honest conversion,
    which is why money is the headline unit and this is the footnote.
    """
    balance = await credits_repo.balance(conn, org_id)
    allowance = entitlements.monthly_credit_paise
    # What the ledger actually handed over, not what the plan says it would. The
    # two differ before a grant lands and after a top-up, and a meter built on the
    # entitlement reads "all used" in the first case and negative in the second.
    granted = await credits_repo.granted_this_period(conn, org_id)
    return CreditOverview(
        balance_paise=balance,
        granted_this_period_paise=granted,
        rate_paise_per_minute=rate.paise_per_minute,
        estimated_minutes_left=estimated_minutes(balance, rate),
        is_uncapped=allowance is None,
    )


async def member_credit_cap_status(
    conn: asyncpg.Connection, *, org_id: UUID, user_id: UUID, now: datetime | None = None
) -> tuple[int | None, int]:
    """`(cap_paise, spent_paise)` for one teammate's share of this calendar
    month's usage credit.

    The calendar month, not the subscription's own billing period: a per-
    member cap is a governance tool an owner sets, not a metered billing
    boundary, and the organisation may have no subscription at all (Free, or a
    lapsed one - see `services.billing.subscription_grants_credit`). Matches
    the period `ensure_period_credit` already uses for the same reason.
    """
    cap_paise = await credits_repo.get_credit_cap(conn, org_id, user_id)
    since = (now or datetime.now(UTC)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    spent_paise = await credits_repo.member_spend_this_period(
        conn, org_id=org_id, user_id=user_id, since=since
    )
    return cap_paise, spent_paise


async def sweep_stale_holds(conn: asyncpg.Connection) -> int:
    """Release holds whose call never reported. Returns how many.

    Called from the same place a run's stale in-flight rows are swept, so one
    dead worker is cleaned up once rather than leaving credit pinned by a call
    nobody is having.
    """
    released = await credits_repo.release_stale_holds(
        conn, older_than_seconds=STALE_HOLD_SECONDS
    )
    if released:
        log.warning("released %d stale credit hold(s)", released)
    return released


def period_key_for(subscription_id: str, period_end: datetime | None) -> str:
    """A stable identity for one billing period.

    Built from the subscription and its period end rather than a clock, because
    it is the idempotency key for a grant: two deliveries of the same renewal
    must produce the same key, and a clock guarantees they do not.
    """
    stamp = period_end.date().isoformat() if period_end else "open"
    return f"{subscription_id}:{stamp}"
