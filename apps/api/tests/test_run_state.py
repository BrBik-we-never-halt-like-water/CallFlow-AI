"""The run state machine, and the rule that decides how a run closes.

Pure, so this needs no database and no carrier - the same reason
`test_number_state.py` and `test_safety.py` can be read on their own.

The case worth stating: `test_a_stopped_run_never_reads_completed` is the one
that would catch a regression somebody could ship without noticing. Every other
assertion here fails loudly; that one would fail as a run quietly claiming it
finished a list it was halted halfway through.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.run_state import (
    TERMINAL,
    InvalidRunTransition,
    RunStatus,
    can_request_stop,
    can_transition,
    check_transition,
    closing_status,
    is_stopping,
    is_terminal,
)

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


# --- the transition table ------------------------------------------------


def test_running_is_the_only_non_terminal_state() -> None:
    assert TERMINAL == {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.STOPPED}
    assert not is_terminal(RunStatus.RUNNING)


@pytest.mark.parametrize(
    "target",
    [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.STOPPED],
)
def test_a_running_run_can_reach_every_ending(target: RunStatus) -> None:
    assert can_transition(RunStatus.RUNNING, target)
    check_transition(RunStatus.RUNNING, target)


@pytest.mark.parametrize("start", sorted(TERMINAL, key=lambda s: s.value))
@pytest.mark.parametrize(
    "target", [RunStatus.RUNNING, RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.STOPPED]
)
def test_a_finished_run_never_moves_again(start: RunStatus, target: RunStatus) -> None:
    """A run is a record of one batch of calls, so re-opening one would be
    claiming a conversation happened inside it that did not."""
    assert not can_transition(start, target)
    with pytest.raises(InvalidRunTransition):
        check_transition(start, target)


def test_the_refusal_names_both_states() -> None:
    with pytest.raises(InvalidRunTransition) as caught:
        check_transition(RunStatus.COMPLETED, RunStatus.RUNNING)
    assert "completed" in str(caught.value)
    assert "running" in str(caught.value)


# --- how a run closes ----------------------------------------------------


def test_a_stopped_run_never_reads_completed() -> None:
    """CLAUDE.md non-negotiable #9, at the exact point it would be broken.

    A halted run settles every contact it was ever going to settle, which is the
    same condition an untouched run closes on - so the *only* thing separating
    "dialled all 50" from "dialled 12 and was stopped" is this branch.
    """
    assert closing_status(stop_requested=True) is RunStatus.STOPPED
    assert closing_status(stop_requested=False) is RunStatus.COMPLETED


def test_the_sql_and_the_domain_agree_on_the_closing_status() -> None:
    """`finish_if_all_settled` decides this in SQL because it has to be one
    atomic statement; this module is the readable copy. The two are only in step
    because something asserts it, which is this."""
    from pathlib import Path

    sql = Path(__file__).resolve().parents[1] / "app/database/repositories/runs.py"
    body = sql.read_text(encoding="utf-8")
    assert "when r.stop_requested_at is null then 'completed'" in body
    assert "else 'stopped'" in body
    assert closing_status(stop_requested=False).value == "completed"
    assert closing_status(stop_requested=True).value == "stopped"


def test_the_enum_matches_the_check_constraint() -> None:
    """The database rejects an unknown value; only the enum rejects a known one
    reached illegally. They have to list the same four."""
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/202608230900_stop_a_run_and_opt_out_suppression.py"
    )
    body = migration.read_text(encoding="utf-8")
    for status in RunStatus:
        assert f'"{status.value}"' in body, f"{status.value} missing from the migration"


# --- the derived "stopping" state ----------------------------------------


def test_stopping_is_running_plus_a_request() -> None:
    assert is_stopping(RunStatus.RUNNING, NOW)


def test_a_running_run_nobody_touched_is_not_stopping() -> None:
    assert not is_stopping(RunStatus.RUNNING, None)


@pytest.mark.parametrize("status", sorted(TERMINAL, key=lambda s: s.value))
def test_a_finished_run_is_never_stopping(status: RunStatus) -> None:
    """Winding down is over once the run closes - a stopped run is stopped, not
    stopping, and the button must not keep saying otherwise."""
    assert not is_stopping(status, NOW)


# --- whether Stop is offered at all --------------------------------------


def test_stop_is_offered_only_while_running() -> None:
    assert can_request_stop(RunStatus.RUNNING)


@pytest.mark.parametrize("status", sorted(TERMINAL, key=lambda s: s.value))
def test_stop_is_refused_on_a_finished_run(status: RunStatus) -> None:
    """Not a harmless no-op to accept quietly: answering 200 would make the
    interface report "Run stopped" for a run that stopped itself ten minutes
    ago, which is a success state for an action that did not happen."""
    assert not can_request_stop(status)
