"""Which number places each call.

Pure, so no database and no mocks - the standard `test_safety.py` sets. The
distribution is the whole reason an org holds several numbers, so that is what
is asserted rather than "a line came back".
"""

from __future__ import annotations

import pytest

from app.domain.number_allocation import (
    DialLine,
    NoLinesAvailable,
    RoundRobin,
    build_allocator,
)

CONTACT = "+919876543210"


def _lines(count: int) -> list[DialLine]:
    return [
        DialLine(
            number_id=f"n{i}",
            phone_e164=f"+1555055{i:04d}",
            outbound_trunk_id=f"ST_{i}",
        )
        for i in range(count)
    ]


def test_one_number_takes_every_call() -> None:
    allocator = RoundRobin(_lines(1))
    assert [allocator.next_for(CONTACT).number_id for _ in range(4)] == ["n0"] * 4


def test_lines_are_handed_out_in_order_and_wrap() -> None:
    allocator = RoundRobin(_lines(3))
    got = [allocator.next_for(CONTACT).number_id for _ in range(7)]
    assert got == ["n0", "n1", "n2", "n0", "n1", "n2", "n0"]


def test_thirty_calls_across_three_numbers_land_ten_each() -> None:
    """The reason to hold several numbers: a carrier and a recipient both treat
    one line placing every call as spam. Random assignment clusters; a cycle does
    not, and this pins the difference."""
    allocator = RoundRobin(_lines(3))
    counts: dict[str, int] = {}
    for _ in range(30):
        line = allocator.next_for(CONTACT)
        counts[line.number_id] = counts.get(line.number_id, 0) + 1

    assert counts == {"n0": 10, "n1": 10, "n2": 10}


def test_the_trunk_travels_with_the_number() -> None:
    """The dialer originates through `outbound_trunk_id`. Pairing it with the
    number in one value is what stops a call being placed from one line through
    another line's trunk."""
    allocator = RoundRobin(_lines(2))
    first = allocator.next_for(CONTACT)
    second = allocator.next_for(CONTACT)

    assert (first.number_id, first.outbound_trunk_id) == ("n0", "ST_0")
    assert (second.number_id, second.outbound_trunk_id) == ("n1", "ST_1")


def test_no_lines_refuses_to_construct() -> None:
    """Fail closed. A run with nothing verified must not reach a state where the
    next call has to invent a line to dial from."""
    with pytest.raises(NoLinesAvailable) as excinfo:
        RoundRobin([])

    # CLAUDE.md §5: the message says what to do next.
    message = str(excinfo.value)
    assert "Integrations" in message
    assert "verified number" in message


def test_an_unknown_strategy_falls_back_rather_than_refusing_the_run() -> None:
    """`runs.allocation_strategy` has a check constraint, so an unknown value
    means the constraint and the factory have drifted. Distributing the run the
    default way beats refusing to dial a legitimate one."""
    allocator = build_allocator("something_nobody_implemented", _lines(2))
    assert allocator.next_for(CONTACT).number_id == "n0"


def test_round_robin_is_the_named_default() -> None:
    allocator = build_allocator("round_robin", _lines(2))
    assert isinstance(allocator, RoundRobin)


def test_the_country_code_is_read_off_the_number() -> None:
    """Deliberately naive, and only useful to a future region-matching strategy.
    Pinned so that strategy starts from a known behaviour rather than guessing."""
    assert DialLine("n", "+919876543210", "T").country_code == "9198"
    assert DialLine("n", "+15555550100", "T").country_code == "1555"


def test_the_contact_argument_exists_for_the_interface_not_the_implementation() -> None:
    """Round-robin ignores who is being called. The parameter is part of the
    protocol so a region-matching strategy drops in without the dialer changing -
    if this ever starts mattering, that is the new strategy's test, not this one."""
    allocator = RoundRobin(_lines(2))
    first = allocator.next_for("+919876543210")
    second = allocator.next_for("+15555550100")
    assert (first.number_id, second.number_id) == ("n0", "n1")
