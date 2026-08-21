"""Which of an organisation's numbers places the next call.

Pure: no I/O, no vendor, no database - so the distribution is unit-testable
without a carrier, the same standard `safety.py` holds itself to.

A run may be given one number, several, or every verified number the
organisation owns. The reason to hold several is that carriers and recipients
both treat a single number placing hundreds of calls as spam, so the default
strategy spreads the run evenly rather than exhausting one line.

`Allocator` is a protocol rather than an `if strategy == ...` inside the dialer:
a second strategy is a new class the dialer never learns about (CLAUDE.md §3,
open-for-extension). `RoundRobin` is the only one implemented today; the
`runs.allocation_strategy` column exists so a second is additive.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DialLine:
    """One number a run may dial from, and the trunk that reaches it.

    `outbound_trunk_id` is what LiveKit needs and is only ever set on a verified
    number, so holding it here means the dialer cannot accidentally originate
    from a number that was never pointed at a carrier - there would be nothing
    to originate through.
    """

    number_id: str
    phone_e164: str
    outbound_trunk_id: str

    @property
    def country_code(self) -> str:
        """The dialling prefix, for a strategy that wants to match regions.

        Deliberately naive - the first one to four digits after the plus, with no
        attempt to parse a national numbering plan. A real prefix table is what
        `area_affinity` would need, and guessing one here would be worse than
        not offering it (see the module docstring).
        """
        return self.phone_e164.lstrip("+")[:4]


class Allocator(Protocol):
    """Hands out lines. One call per contact, in dial order."""

    def next_for(self, contact_phone: str) -> DialLine: ...


class NoLinesAvailable(Exception):
    """Raised when a run reaches allocation with nothing to dial from.

    A run should never get this far - `resolve_run_plan` refuses first, with a
    message naming what to connect. This exists so that if it ever does, it
    fails loudly here rather than dialling from an unverified number.
    """

    def __init__(self) -> None:
        super().__init__(
            "This run has no verified number to call from. Connect one in "
            "Integrations, then pick it when you start the run."
        )


class RoundRobin:
    """Each dial takes the next line, wrapping at the end.

    Even distribution is the whole point, so the cycle is over the lines rather
    than a random choice: random assignment clusters, and a run of thirty calls
    across three numbers should be ten each, not eleven-twelve-seven.

    `contact_phone` is accepted and ignored. It is part of the protocol so a
    region-matching strategy can be dropped in without the dialer changing, and
    a parameter that exists for the interface rather than the implementation is
    worth saying out loud.
    """

    def __init__(self, lines: Sequence[DialLine]) -> None:
        if not lines:
            raise NoLinesAvailable()
        self._lines = tuple(lines)
        # An iterator, advanced by `next()` below. Stored as the iterator itself
        # rather than re-wrapped per call: `iter()` on an iterator returns the
        # same object, so `next(iter(self._cycle))` would also work - but only by
        # accident of that rule, and a reader shouldn't have to know it to see
        # that the position survives between calls.
        self._cycle: Iterator[DialLine] = itertools.cycle(self._lines)

    def next_for(self, contact_phone: str) -> DialLine:
        return next(self._cycle)

    @property
    def lines(self) -> tuple[DialLine, ...]:
        return self._lines


def build_allocator(strategy: str, lines: Sequence[DialLine]) -> Allocator:
    """The allocator named by `runs.allocation_strategy`.

    Falls back to round-robin for an unknown name rather than raising: the column
    has a check constraint, so an unknown value means the constraint and this
    function have drifted, and refusing to dial a legitimate run is a worse
    outcome than distributing it the default way. The fallback is logged by the
    caller, which has the run id to log it against.
    """
    return RoundRobin(lines)


__all__ = [
    "Allocator",
    "DialLine",
    "NoLinesAvailable",
    "RoundRobin",
    "build_allocator",
]
