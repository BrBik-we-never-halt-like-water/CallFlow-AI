"""The state machine for a run, and the rule that decides how one closes.

Pure: no I/O, no vendor, no database - the same standard `safety.py`,
`numbers.py` and `provisioning.py` hold themselves to, and the reason the
closing rule below can be tested without dialling anything.

`runs.status` was a bare text column with no constraint for its whole life,
which was tolerable while three values were written from two call sites. Adding
`stopped` made it not tolerable: "did this run finish, or was it halted?" is a
question the product answers differently in the list, in the lamp strip and in
the sentence under it, and a fourth value maintained by convention is how one of
those three quietly disagrees with the other two.

**A stop is a request, not a state.** That is the design decision this module
encodes. `stop_requested_at` is set the moment somebody presses Stop, but the
run stays RUNNING until the last live conversation settles - so there is a real
interval where a run is stopping and neither RUNNING nor STOPPED describes it.
Rather than invent a fifth status that the database would have to hold and every
reader would have to learn, `is_stopping()` derives it from the two facts that
are already true. Derived, so it cannot drift from them.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum


class RunStatus(str, Enum):
    """Mirrors `runs.status`'s check constraint exactly (`f3c7b21a9d04`).

    Keep the two in step: the database rejects an unknown value, but only this
    enum rejects a *known* value reached by an illegal route.
    """

    #: Dialling, or waiting on conversations that have not reported yet.
    RUNNING = "running"
    #: Every contact settled and no stop was asked for.
    COMPLETED = "completed"
    #: The dispatcher itself raised. Distinct from a run whose *calls* failed -
    #: those settle as unreachable outcomes inside a run that completed fine.
    FAILED = "failed"
    #: Halted by a person. Some contacts were never dialled, on purpose.
    STOPPED = "stopped"


#: Every legal move, declared rather than implied by scattered `if` statements.
#: A run only ever leaves RUNNING, and never comes back - unlike a phone number
#: (`domain/numbers.py`), a run is a historical record of one batch of calls, so
#: re-opening one would be claiming a conversation happened inside it that did
#: not.
_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.RUNNING: frozenset(
        {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.STOPPED}
    ),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.STOPPED: frozenset(),
}

#: The three ways a run ends. Non-empty here, unlike `domain/numbers.py`'s, and
#: that difference is the point: a number outlives what happened to it, a run is
#: what happened.
TERMINAL: frozenset[RunStatus] = frozenset(
    status for status, onward in _TRANSITIONS.items() if not onward
)


class InvalidRunTransition(Exception):
    """A run was asked to move somewhere it cannot go.

    Raised rather than silently ignored (CLAUDE.md non-negotiable #7). The
    realistic trigger is a second writer trying to close an already-closed run,
    which the SQL guards against with `finished_at is null` - this is the check
    for anything that reaches the domain without passing through that.
    """

    def __init__(self, current: RunStatus, requested: RunStatus) -> None:
        super().__init__(
            f"A run that is already {current.value} cannot become {requested.value}."
        )
        self.current = current
        self.requested = requested


def is_terminal(status: RunStatus) -> bool:
    return status in TERMINAL


def can_transition(current: RunStatus, requested: RunStatus) -> bool:
    return requested in _TRANSITIONS[current]


def check_transition(current: RunStatus, requested: RunStatus) -> None:
    if not can_transition(current, requested):
        raise InvalidRunTransition(current, requested)


def is_stopping(status: RunStatus, stop_requested_at: datetime | None) -> bool:
    """Somebody pressed Stop and the run has not finished winding down.

    Derived rather than stored, so it cannot contradict the two values it is
    read from. This is what the interface renders as "Stopping…" - dialling has
    ceased, but conversations already in progress are still being held and their
    results are still arriving.
    """
    return status is RunStatus.RUNNING and stop_requested_at is not None


def closing_status(*, stop_requested: bool) -> RunStatus:
    """Which terminal status a run that has settled every contact takes.

    The whole of CLAUDE.md non-negotiable #9 in one branch: a run that was
    halted after 12 of 50 contacts must not read "Completed". It settled every
    contact it was ever going to settle, which is the condition for closing -
    but 38 people were deliberately not called, and the status is the only place
    that fact survives once the outcome rows all look alike.
    """
    return RunStatus.STOPPED if stop_requested else RunStatus.COMPLETED


def can_request_stop(status: RunStatus) -> bool:
    """Whether Stop is a meaningful action on a run in this state.

    False for anything terminal. Stopping a finished run is not a harmless
    no-op to accept quietly: the interface would report "Run stopped" for
    something that stopped itself minutes ago, which is a success state for an
    action that did not happen.
    """
    return status is RunStatus.RUNNING


__all__ = [
    "TERMINAL",
    "InvalidRunTransition",
    "RunStatus",
    "can_request_stop",
    "can_transition",
    "check_transition",
    "closing_status",
    "is_stopping",
    "is_terminal",
]
