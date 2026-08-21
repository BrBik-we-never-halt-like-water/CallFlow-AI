"""The subscription state machine, and which statuses actually grant a plan.

Pure: no I/O, no vendor, no database. `subscriptions`' repository calls
`check_transition()` before it writes, so an out-of-order webhook raises instead
of quietly persisting - CLAUDE.md non-negotiable #7, and the same shape
`provisioning.py` already uses.

Statuses mirror the payment gateway's own vocabulary rather than inventing a
parallel one, so a webhook handler never has to guess which of two spellings it
is holding. What is *not* borrowed is the gateway's advice to revoke access on
`on_hold`: see `grants_paid_plan`.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from app.domain.plans import PlanId


class SubscriptionStatus(str, Enum):
    """Mirrors `org_subscriptions.status`'s check constraint exactly.

    Keep the two in step: the database rejects an unknown value, but only this
    enum rejects a *known* value reached by an illegal route.
    """

    PENDING = "pending"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


# Every legal move, declared rather than implied by scattered `if` statements.
# An empty set is a terminal state.
#
# Renewal is deliberately absent: `subscription.renewed` extends
# `current_period_end` while the status stays ACTIVE, so it is a period change
# rather than a transition. Modelling it as ACTIVE -> ACTIVE would mean
# permitting a self-transition, which `check_transition` rejects on purpose.
_TRANSITIONS: dict[SubscriptionStatus, frozenset[SubscriptionStatus]] = {
    SubscriptionStatus.PENDING: frozenset(
        {SubscriptionStatus.ACTIVE, SubscriptionStatus.FAILED, SubscriptionStatus.CANCELLED}
    ),
    SubscriptionStatus.ACTIVE: frozenset(
        {SubscriptionStatus.ON_HOLD, SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED}
    ),
    SubscriptionStatus.ON_HOLD: frozenset(
        {SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED}
    ),
    SubscriptionStatus.CANCELLED: frozenset(),
    SubscriptionStatus.EXPIRED: frozenset(),
    SubscriptionStatus.FAILED: frozenset(),
}

TERMINAL: frozenset[SubscriptionStatus] = frozenset(
    {status for status, onward in _TRANSITIONS.items() if not onward}
)

# The two statuses that still hold what the organisation paid for. ON_HOLD is
# here against the gateway's own guidance, which says to revoke on a failed
# renewal. ON_HOLD is *precisely* when a renewal fails, so revoking there stops
# a running campaign at the worst possible moment. Bounding it by
# `current_period_end` instead gives one rule that covers cancel, downgrade and
# payment failure alike, and it is still fail-closed because it expires.
_PAID_WHILE_IN_PERIOD: frozenset[SubscriptionStatus] = frozenset(
    {SubscriptionStatus.ACTIVE, SubscriptionStatus.ON_HOLD, SubscriptionStatus.CANCELLED}
)


class PaymentFailure(str, Enum):
    """A vendor-neutral reason a charge or mandate failed.

    Retry policy keys off these names, never a gateway's own error string, so a
    second provider slots in without every caller re-learning a new vocabulary -
    the same job `DialFailure` does for call attempts.
    """

    CARD_DECLINED = "card_declined"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    MANDATE_FAILED = "mandate_failed"
    UNAUTHORIZED = "unauthorized"
    INVALID_REQUEST = "invalid_request"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TIMED_OUT = "timed_out"
    INTERNAL = "internal"


# Worth retrying later; everything else is a decision, not a hiccup. INTERNAL is
# absent deliberately, so a failure this code has never seen stops rather than
# being retried on the assumption it is transient.
_RETRYABLE: frozenset[PaymentFailure] = frozenset(
    {
        PaymentFailure.PROVIDER_UNAVAILABLE,
        PaymentFailure.TIMED_OUT,
        PaymentFailure.INSUFFICIENT_FUNDS,
    }
)


class InvalidTransition(Exception):
    """Raised instead of writing a status the machine does not allow.

    Carries both ends of the attempted move so the message names what actually
    happened rather than "invalid state" - CLAUDE.md §5.
    """

    def __init__(self, current: SubscriptionStatus, target: SubscriptionStatus) -> None:
        self.current = current
        self.target = target
        if current in TERMINAL:
            detail = f"{current.value} is final - a new subscription starts a new row."
        else:
            allowed = ", ".join(sorted(s.value for s in _TRANSITIONS[current]))
            detail = f"from {current.value} the only moves are: {allowed}."
        super().__init__(f"Cannot move a subscription to {target.value}: {detail}")


def can_transition(current: SubscriptionStatus, target: SubscriptionStatus) -> bool:
    return target in _TRANSITIONS[current]


def check_transition(current: SubscriptionStatus, target: SubscriptionStatus) -> None:
    """Raise unless `current -> target` is a declared move."""
    if not can_transition(current, target):
        raise InvalidTransition(current, target)


def is_terminal(status: SubscriptionStatus) -> bool:
    return status in TERMINAL


def is_live(status: SubscriptionStatus) -> bool:
    """Whether this row is the organisation's current subscription.

    Mirrors the partial unique index that permits one live subscription per
    organisation, so Python and the database agree on what "live" means.
    """
    return status in {
        SubscriptionStatus.PENDING,
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.ON_HOLD,
    }


def is_retryable(failure: PaymentFailure) -> bool:
    return failure in _RETRYABLE


def grants_via_subscription(status: SubscriptionStatus | None) -> bool:
    """Whether a subscription in this status is the reason usage credit should
    arrive from `services.credit.grant_for_period` rather than the lazy,
    unsubscribed-org path (`ensure_period_credit`).

    Narrower than `is_live()`: a `pending` checkout is live (it holds the
    one-per-org slot) but has never been activated, so nothing has granted
    against it yet and the lazy path must still cover the organisation. Once a
    subscription reaches a terminal status - `cancelled`, `expired`, `failed` -
    or is abandoned at `pending` forever, this returns `False` again, which is
    what lets the lazy path pick the organisation back up rather than leaving it
    stuck believing a subscription will grant on its behalf indefinitely.
    """
    return status in {SubscriptionStatus.ACTIVE, SubscriptionStatus.ON_HOLD}


def effective_plan_id(
    *,
    status: SubscriptionStatus | None,
    plan_id: str,
    current_period_end: datetime | None,
    now: datetime,
) -> str:
    """Which plan an organisation is actually entitled to, right now.

    The single rule behind cancel, downgrade and payment failure: a paid plan
    survives to the end of the period already paid for, then falls back to Free.

    `status is None` returns `plan_id` unchanged, because an enterprise
    organisation on an invoiced deal has no gateway subscription at all and must
    not be demoted for lacking one. `current_period_end is None` on an otherwise
    paid status means the gateway has not told us when the period ends yet;
    trusting the status is right for the few seconds that lasts, and the
    scheduled reconciliation is what corrects it if it lasts longer.
    """
    if status is None:
        return plan_id
    if status not in _PAID_WHILE_IN_PERIOD:
        return PlanId.FREE.value
    if current_period_end is not None and current_period_end <= now:
        return PlanId.FREE.value
    return plan_id


__all__ = [
    "TERMINAL",
    "InvalidTransition",
    "PaymentFailure",
    "SubscriptionStatus",
    "can_transition",
    "check_transition",
    "effective_plan_id",
    "is_live",
    "is_retryable",
    "is_terminal",
]
