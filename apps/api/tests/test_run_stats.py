"""`_compute_stats` (ISSUES.md #8): every rate must be over resolved outcomes
only, not diluted by in-flight ones. Pure function, plain dicts - no database.
"""

from __future__ import annotations

from app.api.v1.routes.runs import _compute_stats


def _outcome(disposition: str) -> dict:
    return {"disposition": disposition}


def test_in_flight_outcomes_do_not_dilute_needs_human_pct() -> None:
    outcomes = [
        _outcome("escalated"),
        _outcome("auto_closed"),
        _outcome("in_flight"),
        _outcome("in_flight"),
    ]
    stats = _compute_stats(outcomes, total=4)

    # 1 of 2 *resolved* outcomes escalated - not 1 of 4 total.
    assert stats["completed"] == 2
    assert stats["escalated"] == 1
    assert stats["auto_closed"] == 1
    assert stats["needs_human_pct"] == 50
    assert stats["in_flight"] == 2


def test_auto_closed_excludes_in_flight_rows() -> None:
    outcomes = [_outcome("auto_closed"), _outcome("in_flight")]
    stats = _compute_stats(outcomes, total=2)
    # Previously counted over *all* outcomes, so an in-flight row (which is
    # never auto_closed) silently diluted this rate too.
    assert stats["auto_closed"] == 1
    assert stats["completed"] == 1


def test_no_outcomes_yet_is_zero_not_a_division_error() -> None:
    stats = _compute_stats([], total=5)
    assert stats == {
        "completed": 0,
        "total": 5,
        "escalated": 0,
        "auto_closed": 0,
        "needs_human_pct": 0,
        "in_flight": 0,
    }


def test_no_resolved_outcomes_yet_needs_human_pct_is_zero() -> None:
    # All in-flight: len(resolved) == 0 - must not divide by zero.
    outcomes = [_outcome("in_flight"), _outcome("in_flight")]
    stats = _compute_stats(outcomes, total=2)
    assert stats["needs_human_pct"] == 0
    assert stats["in_flight"] == 2
