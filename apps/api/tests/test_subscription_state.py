"""The subscription state machine: every legal move, and every illegal one.

Pure - no database, so this runs in CI where the RLS tests cannot.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.subscriptions import (
    TERMINAL,
    InvalidTransition,
    PaymentFailure,
    SubscriptionStatus,
    can_transition,
    check_transition,
    effective_plan_id,
    is_live,
    is_retryable,
    is_terminal,
)

S = SubscriptionStatus

LEGAL = [
    (S.PENDING, S.ACTIVE),
    (S.PENDING, S.FAILED),
    (S.PENDING, S.CANCELLED),
    (S.ACTIVE, S.ON_HOLD),
    (S.ACTIVE, S.CANCELLED),
    (S.ACTIVE, S.EXPIRED),
    (S.ON_HOLD, S.ACTIVE),
    (S.ON_HOLD, S.CANCELLED),
    (S.ON_HOLD, S.EXPIRED),
]


@pytest.mark.parametrize("current,target", LEGAL)
def test_declared_moves_are_allowed(current: S, target: S) -> None:
    assert can_transition(current, target)
    check_transition(current, target)  # must not raise


@pytest.mark.parametrize(
    "current,target",
    [pair for pair in ((c, t) for c in S for t in S) if pair not in LEGAL],
)
def test_every_other_move_is_rejected(current: S, target: S) -> None:
    """Exhaustive over the whole 6x6 grid, so adding a status without deciding
    its edges fails here rather than silently defaulting to permitted."""
    assert not can_transition(current, target)
    with pytest.raises(InvalidTransition):
        check_transition(current, target)


def test_a_status_cannot_transition_to_itself() -> None:
    """Two deliveries of the same webhook must not both "advance" a subscription.
    This is also why renewal extends the period instead of re-writing ACTIVE."""
    for status in S:
        assert not can_transition(status, status)


def test_terminal_states_are_the_three_that_end_a_subscription() -> None:
    assert TERMINAL == {S.CANCELLED, S.EXPIRED, S.FAILED}
    assert is_terminal(S.CANCELLED)
    assert not is_terminal(S.ON_HOLD)


def test_a_cancelled_subscription_cannot_be_revived() -> None:
    """Resubscribing inserts a new row. Reviving this one would lose the record
    of what was tried and collide with the one-live-per-org index."""
    with pytest.raises(InvalidTransition):
        check_transition(S.CANCELLED, S.ACTIVE)


def test_a_failed_mandate_cannot_become_active() -> None:
    with pytest.raises(InvalidTransition):
        check_transition(S.FAILED, S.ACTIVE)


def test_on_hold_can_recover_when_the_payment_method_is_fixed() -> None:
    """The one non-obvious legal edge: ON_HOLD is recoverable, unlike FAILED."""
    check_transition(S.ON_HOLD, S.ACTIVE)


def test_live_is_exactly_what_the_partial_unique_index_permits() -> None:
    """Python and `org_subscriptions_one_live_per_org` must agree on "live", or
    one of them lets a second subscription exist for an organisation."""
    assert {s for s in S if is_live(s)} == {S.PENDING, S.ACTIVE, S.ON_HOLD}


def test_the_error_names_both_ends_and_what_was_possible() -> None:
    """CLAUDE.md §5: an error says what happened and what to do next."""
    with pytest.raises(InvalidTransition) as caught:
        check_transition(S.PENDING, S.ON_HOLD)

    message = str(caught.value)
    assert "on_hold" in message
    assert "pending" in message
    assert "active" in message and "failed" in message


def test_a_terminal_error_says_a_new_subscription_starts_a_new_row() -> None:
    with pytest.raises(InvalidTransition) as caught:
        check_transition(S.EXPIRED, S.ACTIVE)

    assert "new row" in str(caught.value)


def test_status_values_match_the_database_check_constraint() -> None:
    """The enum and `org_subscriptions_status_check` must not drift - the database
    rejects an unknown value, but only the enum rejects a known value reached
    illegally, so a mismatch disables one guard silently."""
    assert {s.value for s in S} == {
        "pending",
        "active",
        "on_hold",
        "cancelled",
        "expired",
        "failed",
    }


# --- which statuses actually grant the paid plan ---

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=10)
EARLIER = NOW - timedelta(days=1)


@pytest.mark.parametrize("status", [S.ACTIVE, S.ON_HOLD, S.CANCELLED])
def test_a_paid_status_keeps_the_plan_until_the_period_ends(status: S) -> None:
    assert (
        effective_plan_id(
            status=status, plan_id="growth", current_period_end=LATER, now=NOW
        )
        == "growth"
    )


def test_on_hold_does_not_revoke_immediately() -> None:
    """Against the gateway's own guidance, and deliberately: ON_HOLD is exactly
    when a renewal fails, so revoking there stops a running campaign at the worst
    possible moment. One rule now covers cancel, downgrade and payment failure."""
    assert (
        effective_plan_id(
            status=S.ON_HOLD, plan_id="growth", current_period_end=LATER, now=NOW
        )
        == "growth"
    )


@pytest.mark.parametrize("status", [S.ACTIVE, S.ON_HOLD, S.CANCELLED])
def test_a_lapsed_period_falls_back_to_free(status: S) -> None:
    assert (
        effective_plan_id(
            status=status, plan_id="growth", current_period_end=EARLIER, now=NOW
        )
        == "free"
    )


@pytest.mark.parametrize("status", [S.PENDING, S.EXPIRED, S.FAILED])
def test_an_unpaid_status_grants_free_regardless_of_the_period(status: S) -> None:
    assert (
        effective_plan_id(status=status, plan_id="growth", current_period_end=LATER, now=NOW)
        == "free"
    )


def test_no_subscription_at_all_keeps_the_plan() -> None:
    """An enterprise organisation on an invoiced deal has no gateway
    subscription. Demoting it for lacking one would break every such customer."""
    assert (
        effective_plan_id(
            status=None, plan_id="enterprise", current_period_end=None, now=NOW
        )
        == "enterprise"
    )


def test_a_paid_status_with_no_known_period_end_is_trusted() -> None:
    """The gap between `subscription.active` arriving and the period being
    recorded. Trusting the status for those seconds beats demoting a customer who
    just paid; reconciliation corrects it if it lasts longer."""
    assert (
        effective_plan_id(
            status=S.ACTIVE, plan_id="starter", current_period_end=None, now=NOW
        )
        == "starter"
    )


# --- the failure taxonomy ---


def test_internal_is_not_retryable() -> None:
    """Fails closed: a failure this code has never seen stops the attempt rather
    than being retried on the assumption it is transient."""
    assert not is_retryable(PaymentFailure.INTERNAL)


@pytest.mark.parametrize(
    "failure",
    [
        PaymentFailure.PROVIDER_UNAVAILABLE,
        PaymentFailure.TIMED_OUT,
        PaymentFailure.INSUFFICIENT_FUNDS,
    ],
)
def test_transient_failures_are_retryable(failure: PaymentFailure) -> None:
    assert is_retryable(failure)


@pytest.mark.parametrize(
    "failure",
    [
        PaymentFailure.CARD_DECLINED,
        PaymentFailure.MANDATE_FAILED,
        PaymentFailure.UNAUTHORIZED,
        PaymentFailure.INVALID_REQUEST,
    ],
)
def test_a_decision_is_not_retried(failure: PaymentFailure) -> None:
    """A declined card or a refused mandate is an answer, not a hiccup. Retrying
    it burns the customer's bank's fraud budget and changes nothing."""
    assert not is_retryable(failure)
