"""The `telephony_numbers` status machine.

Pure, so this needs no database and no mocks - the same standard
`test_provisioning_state.py` holds its own machine to. What is worth pinning is
not that the declared moves work, but that **everything else is refused**: a
machine is only a machine if the illegal edges raise, and those are the ones no
feature test would ever exercise.
"""

from __future__ import annotations

import itertools

import pytest

from app.domain.numbers import (
    DIALLABLE,
    TERMINAL,
    InvalidTransition,
    NumberStatus,
    can_transition,
    check_transition,
    is_diallable,
    is_terminal,
)

LEGAL: set[tuple[NumberStatus, NumberStatus]] = {
    (NumberStatus.DISCOVERED, NumberStatus.PROVISIONING),
    (NumberStatus.DISCOVERED, NumberStatus.DISABLED),
    (NumberStatus.PROVISIONING, NumberStatus.VERIFIED),
    (NumberStatus.PROVISIONING, NumberStatus.FAILED),
    (NumberStatus.FAILED, NumberStatus.PROVISIONING),
    (NumberStatus.FAILED, NumberStatus.DISABLED),
    (NumberStatus.VERIFIED, NumberStatus.DISABLED),
    (NumberStatus.DISABLED, NumberStatus.VERIFIED),
    (NumberStatus.DISABLED, NumberStatus.PROVISIONING),
}


@pytest.mark.parametrize(("current", "target"), sorted(LEGAL, key=lambda p: (p[0].value, p[1].value)))
def test_every_declared_move_is_allowed(
    current: NumberStatus, target: NumberStatus
) -> None:
    assert can_transition(current, target)
    check_transition(current, target)  # must not raise


@pytest.mark.parametrize(
    ("current", "target"),
    sorted(
        set(itertools.product(NumberStatus, NumberStatus)) - LEGAL,
        key=lambda p: (p[0].value, p[1].value),
    ),
)
def test_every_other_move_is_refused(
    current: NumberStatus, target: NumberStatus
) -> None:
    """The half that matters. Includes every self-transition, which is what a
    naive `set_status(same)` would attempt on a double-submitted request."""
    assert not can_transition(current, target)
    with pytest.raises(InvalidTransition):
        check_transition(current, target)


def test_a_number_is_never_finished() -> None:
    """Unlike a provisioning attempt, every number status has somewhere to go - a
    number outlives any single thing that happened to it."""
    assert TERMINAL == frozenset()
    for status in NumberStatus:
        assert is_terminal(status) is False


def test_a_failed_number_can_be_retried() -> None:
    """The deliberate difference from `provisioning.py`: an attempt that failed
    stays failed because a new attempt records the retry, but a number failed
    because a carrier was unreachable or a credential was wrong - neither is a
    property of the number."""
    assert can_transition(NumberStatus.FAILED, NumberStatus.PROVISIONING)


def test_a_retired_number_comes_back_verified_not_rediscovered() -> None:
    """Re-enabling is not re-provisioning: the trunks still exist at LiveKit and
    at the carrier, so sending it back to `discovered` would claim work has to be
    redone that has not been undone."""
    assert can_transition(NumberStatus.DISABLED, NumberStatus.VERIFIED)
    assert not can_transition(NumberStatus.DISABLED, NumberStatus.DISCOVERED)


def test_a_discovered_number_cannot_jump_straight_to_verified() -> None:
    """Verified means "has a working outbound trunk". Reaching it without passing
    through `provisioning` would mark a number diallable that nothing ever
    pointed at LiveKit - a run would then fail at the carrier with the phone
    already ringing."""
    assert not can_transition(NumberStatus.DISCOVERED, NumberStatus.VERIFIED)


def test_only_a_verified_number_may_be_dialled_from() -> None:
    """Fail closed: the dial gate asks this rather than comparing to a string, so
    a new status added later is undiallable until it is named."""
    assert DIALLABLE == frozenset({NumberStatus.VERIFIED})
    assert is_diallable(NumberStatus.VERIFIED) is True
    for status in NumberStatus:
        if status is not NumberStatus.VERIFIED:
            assert is_diallable(status) is False


def test_the_refusal_names_both_ends_and_what_was_possible() -> None:
    """CLAUDE.md §5: an error says what happened and what to do next."""
    with pytest.raises(InvalidTransition) as excinfo:
        check_transition(NumberStatus.DISCOVERED, NumberStatus.VERIFIED)

    message = str(excinfo.value)
    assert "verified" in message
    assert "discovered" in message
    # And it lists the moves that would have worked.
    assert "provisioning" in message


def test_a_self_transition_says_it_is_already_there() -> None:
    """A distinct message from "that move does not exist": a double-submitted
    disable is a no-op to explain, not a mistake to correct."""
    with pytest.raises(InvalidTransition) as excinfo:
        check_transition(NumberStatus.VERIFIED, NumberStatus.VERIFIED)

    assert "already verified" in str(excinfo.value)


def test_enum_values_match_what_the_check_constraint_will_allow() -> None:
    """The migration writes these five strings into a check constraint. If the
    enum drifts, the database rejects a value this module considers legal."""
    assert {s.value for s in NumberStatus} == {
        "discovered",
        "provisioning",
        "verified",
        "failed",
        "disabled",
    }
