"""The state machine for a phone number the organisation owns.

Pure: no I/O, no vendor, no database. `telephony_numbers`' repository calls
`check_transition()` before it writes, so an invalid move raises instead of
quietly persisting - CLAUDE.md non-negotiable #7.

Deliberately **not** the same shape as `provisioning.py`'s machine, and the two
differences are the whole reason this is a separate module rather than a reused
enum:

- **`verified` is not terminal.** A provisioning *attempt* is a historical
  record and is finished forever once it lands. A *number* is a live piece of
  infrastructure an organisation keeps: it is retired (`disabled`) when it is
  handed back or stops being used, and a retired number can be brought back
  without inventing a new row and losing which calls came from it.
- **`failed` is retryable.** An attempt that failed stays failed because a new
  attempt records the retry. A number that failed to provision failed because a
  carrier was unreachable or a credential was wrong - neither is a permanent
  property of the number, and both are fixed by trying again once the cause is
  addressed.

Retirement is the only way a number leaves circulation, because
`telephony_numbers` carries no delete grant (see
`202608161700_revoke_delete_on_append_only_tables.py` for the same reasoning
applied to provisioning attempts): a number that carried real calls is the
record of who was dialled from where, and deleting it would erase that.
"""

from __future__ import annotations

from enum import Enum


class NumberStatus(str, Enum):
    """Mirrors `telephony_numbers.status`'s check constraint exactly.

    Keep the two in step: the database rejects an unknown value, but only this
    enum rejects a *known* value reached by an illegal route.
    """

    #: Listed from the carrier, not yet pointed at LiveKit. Cannot be dialled from.
    DISCOVERED = "discovered"
    #: Trunks and dispatch rule being created, at LiveKit and at the carrier.
    PROVISIONING = "provisioning"
    #: Has a verified outbound trunk. The only status a run may dial from.
    VERIFIED = "verified"
    #: Provisioning did not complete. Fixable, and retryable.
    FAILED = "failed"
    #: Retired by an operator. Kept so past calls still say where they came from.
    DISABLED = "disabled"


# Every legal move, declared rather than implied by scattered `if` statements.
_TRANSITIONS: dict[NumberStatus, frozenset[NumberStatus]] = {
    NumberStatus.DISCOVERED: frozenset({NumberStatus.PROVISIONING, NumberStatus.DISABLED}),
    NumberStatus.PROVISIONING: frozenset({NumberStatus.VERIFIED, NumberStatus.FAILED}),
    # Retryable: a carrier outage or a wrong credential is not a property of the
    # number. Also disable-able, so an operator can stop offering a number whose
    # provisioning keeps failing without first having to make it work.
    NumberStatus.FAILED: frozenset({NumberStatus.PROVISIONING, NumberStatus.DISABLED}),
    NumberStatus.VERIFIED: frozenset({NumberStatus.DISABLED}),
    # Back to `verified`, not to `discovered`: the trunks still exist at LiveKit
    # and the carrier, so re-enabling is not re-provisioning. An operator who
    # genuinely wants it rebuilt disables it and starts a new provisioning
    # attempt, which is the `provisioning` edge below.
    NumberStatus.DISABLED: frozenset({NumberStatus.VERIFIED, NumberStatus.PROVISIONING}),
}

#: Empty by design. Unlike a provisioning attempt, no number status is final -
#: every one of them has somewhere to go, because a number outlives any single
#: thing that happened to it. Kept as a name so a caller asking "is this over?"
#: gets a definite `False` rather than an AttributeError.
TERMINAL: frozenset[NumberStatus] = frozenset(
    {status for status, onward in _TRANSITIONS.items() if not onward}
)

#: What a run may dial from. One value today, named rather than inlined so the
#: dial gate reads as a rule instead of a string comparison.
DIALLABLE: frozenset[NumberStatus] = frozenset({NumberStatus.VERIFIED})


class InvalidTransition(Exception):
    """Raised instead of writing a status the machine does not allow.

    Carries both ends of the attempted move so the message names what actually
    happened rather than "invalid state" - CLAUDE.md §5.
    """

    def __init__(self, current: NumberStatus, target: NumberStatus) -> None:
        self.current = current
        self.target = target
        if current is target:
            detail = f"it is already {current.value}."
        else:
            allowed = ", ".join(sorted(s.value for s in _TRANSITIONS[current]))
            detail = f"from {current.value} the only moves are: {allowed}."
        super().__init__(f"Cannot move this number to {target.value}: {detail}")


def can_transition(current: NumberStatus, target: NumberStatus) -> bool:
    return target in _TRANSITIONS[current]


def check_transition(current: NumberStatus, target: NumberStatus) -> None:
    """Raise unless `current -> target` is a declared move."""
    if not can_transition(current, target):
        raise InvalidTransition(current, target)


def is_terminal(status: NumberStatus) -> bool:
    return status in TERMINAL


def is_diallable(status: NumberStatus) -> bool:
    """Whether a run may originate from a number in this status.

    The dial gate reads this rather than comparing to `verified` directly, so
    "which statuses can place a call" is answered in one place. Fail closed:
    anything not named in `DIALLABLE` cannot dial.
    """
    return status in DIALLABLE


__all__ = [
    "DIALLABLE",
    "TERMINAL",
    "InvalidTransition",
    "NumberStatus",
    "can_transition",
    "check_transition",
    "is_diallable",
    "is_terminal",
]
