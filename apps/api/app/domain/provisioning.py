"""The state machine for connecting a phone number to a voice agent.

Pure: no I/O, no vendor, no database. `telephony_provisioning`'s repository
calls `check_transition()` before it writes, so an invalid move raises instead
of quietly persisting - CLAUDE.md non-negotiable #7.

The machine is deliberately small and one-way. An attempt is `pending` until
CallFlow starts calling LiveKit and the carrier, `provisioning` while those
calls are in flight, and then either `verified` or `failed` forever. There is
no edge out of a terminal state: "try again" starts a **new** attempt with a
new idempotency key rather than reviving a stuck row, so the record of what was
tried survives (`PLATFORM_PIVOT_PLAN.md` ADR-4).

That one-way shape is what makes the retry rule enforceable. If `failed` could
go back to `provisioning`, a retry could resume a half-built attempt whose
LiveKit trunk ids are already set, and the "did we already create this?" check
would have to distinguish "this attempt made it" from "a previous one did".
Keeping attempts immutable once terminal means that question only ever has one
answer per row.
"""

from __future__ import annotations

from enum import Enum


class ProvisioningStatus(str, Enum):
    """Mirrors `telephony_provisioning.status`'s check constraint exactly.

    Keep the two in step: the database rejects an unknown value, but only this
    enum rejects a *known* value reached by an illegal route.
    """

    PENDING = "pending"
    PROVISIONING = "provisioning"
    VERIFIED = "verified"
    FAILED = "failed"


# Every legal move, declared rather than implied by scattered `if` statements.
# An empty set is a terminal state.
_TRANSITIONS: dict[ProvisioningStatus, frozenset[ProvisioningStatus]] = {
    ProvisioningStatus.PENDING: frozenset(
        {ProvisioningStatus.PROVISIONING, ProvisioningStatus.FAILED}
    ),
    ProvisioningStatus.PROVISIONING: frozenset(
        {ProvisioningStatus.VERIFIED, ProvisioningStatus.FAILED}
    ),
    ProvisioningStatus.VERIFIED: frozenset(),
    ProvisioningStatus.FAILED: frozenset(),
}

TERMINAL: frozenset[ProvisioningStatus] = frozenset(
    {status for status, onward in _TRANSITIONS.items() if not onward}
)


class InvalidTransition(Exception):
    """Raised instead of writing a status the machine does not allow.

    Carries both ends of the attempted move so the message names what actually
    happened rather than "invalid state" - CLAUDE.md §5.
    """

    def __init__(self, current: ProvisioningStatus, target: ProvisioningStatus) -> None:
        self.current = current
        self.target = target
        if current in TERMINAL:
            detail = (
                f"{current.value} is final - start a new attempt instead of reusing this one."
            )
        else:
            allowed = ", ".join(sorted(s.value for s in _TRANSITIONS[current]))
            detail = f"from {current.value} the only moves are: {allowed}."
        super().__init__(f"Cannot move a provisioning attempt to {target.value}: {detail}")


def can_transition(current: ProvisioningStatus, target: ProvisioningStatus) -> bool:
    return target in _TRANSITIONS[current]


def check_transition(current: ProvisioningStatus, target: ProvisioningStatus) -> None:
    """Raise unless `current -> target` is a declared move."""
    if not can_transition(current, target):
        raise InvalidTransition(current, target)


def is_terminal(status: ProvisioningStatus) -> bool:
    return status in TERMINAL


__all__ = [
    "TERMINAL",
    "InvalidTransition",
    "ProvisioningStatus",
    "can_transition",
    "check_transition",
    "is_terminal",
]
