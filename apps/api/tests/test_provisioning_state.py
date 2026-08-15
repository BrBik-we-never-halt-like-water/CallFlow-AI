"""The provisioning state machine: every legal move, and every illegal one.

Pure - no database, so this runs in CI where the RLS tests cannot.
"""

from __future__ import annotations

import pytest

from app.domain.provisioning import (
    TERMINAL,
    InvalidTransition,
    ProvisioningStatus,
    can_transition,
    check_transition,
    is_terminal,
)

S = ProvisioningStatus

LEGAL = [
    (S.PENDING, S.PROVISIONING),
    (S.PENDING, S.FAILED),
    (S.PROVISIONING, S.VERIFIED),
    (S.PROVISIONING, S.FAILED),
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
    """Exhaustive over the whole 4x4 grid, so adding a status without deciding
    its edges fails here rather than silently defaulting to permitted."""
    assert not can_transition(current, target)
    with pytest.raises(InvalidTransition):
        check_transition(current, target)


def test_a_status_cannot_transition_to_itself() -> None:
    """Re-writing the same status would let a second worker "advance" an attempt
    that is already there, which is the double-write this machine exists to stop."""
    for status in S:
        assert not can_transition(status, status)


def test_terminal_states_are_exactly_verified_and_failed() -> None:
    assert TERMINAL == {S.VERIFIED, S.FAILED}
    assert is_terminal(S.VERIFIED)
    assert is_terminal(S.FAILED)
    assert not is_terminal(S.PENDING)
    assert not is_terminal(S.PROVISIONING)


def test_a_failed_attempt_cannot_be_revived() -> None:
    """"Try again" starts a new attempt with a new key. Reviving this row would
    resume a half-built attempt whose trunk ids are already set."""
    with pytest.raises(InvalidTransition):
        check_transition(S.FAILED, S.PROVISIONING)


def test_a_verified_attempt_cannot_be_failed_afterwards() -> None:
    with pytest.raises(InvalidTransition):
        check_transition(S.VERIFIED, S.FAILED)


def test_the_error_names_both_ends_and_what_was_possible() -> None:
    """CLAUDE.md §5: an error says what happened and what to do next."""
    with pytest.raises(InvalidTransition) as caught:
        check_transition(S.PENDING, S.VERIFIED)

    message = str(caught.value)
    assert "verified" in message
    assert "pending" in message
    # Names the legal alternatives rather than just refusing.
    assert "provisioning" in message and "failed" in message


def test_a_terminal_error_says_to_start_a_new_attempt() -> None:
    with pytest.raises(InvalidTransition) as caught:
        check_transition(S.FAILED, S.VERIFIED)

    assert "start a new attempt" in str(caught.value)


def test_status_values_match_the_database_check_constraint() -> None:
    """The enum and `telephony_provisioning_status_check` must not drift - the
    database rejects an unknown value, but only the enum rejects a known value
    reached illegally, so a mismatch disables one guard silently."""
    assert {s.value for s in S} == {"pending", "provisioning", "verified", "failed"}
