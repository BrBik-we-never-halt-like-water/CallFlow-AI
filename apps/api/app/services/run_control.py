"""Asking a run in progress to stop, and letting the dialler notice.

`services/`, not `domain/`, because the signal is a database read: the decision
of *what* a stop means is `domain/run_state.py`'s, and this is the plumbing that
carries it to a dispatcher already halfway through a contact list.

**Why the flag lives in the database rather than in memory.** A run is dispatched
into `BackgroundTasks`, which runs it on whichever uvicorn worker served
`POST /api/v1/runs`. The stop request is a separate HTTP call and lands on
whichever worker the load balancer picks - usually a different one. An
`asyncio.Event`, a module-level set, or anything else in process memory would be
invisible to the worker actually holding the calls, so Stop would appear to work
and change nothing. `runs.stop_requested_at` is the one place both workers can
see, and it survives a restart of either.

**Why the dialler does not read it itself.** `RunDialer` is deliberately free of
database access - that is what lets its whole decision surface be tested against
plain values rather than a mock connection, and it is the same split
`domain/prompt_assembly.py` and `domain/number_allocation.py` sit on the other
side of. So the dialler receives an awaitable predicate and never learns where
the answer came from; a test passes a lambda, and this module is the only thing
that knows there is a table involved.
"""

from __future__ import annotations

import logging
import time
from uuid import UUID

from app.database import database
from app.database.repositories import runs as runs_repo
from app.domain.run_state import RunStatus, can_request_stop

log = logging.getLogger("app.services.run_control")


class RunNotStoppable(Exception):
    """A run cannot be stopped, with the sentence to show the person asking.

    Carries user-facing text for the same reason `RunNotDispatchable` does: the
    route would otherwise have to re-derive which of several conditions failed,
    and there is exactly one place that already knows.
    """


#: How long a fetched answer is trusted before the database is asked again.
#:
#: The trade is bounded and small either way. Too short and a hundred-contact run
#: adds a hundred round trips it does not need; too long and Stop feels
#: unresponsive. Two seconds means at most a couple of extra contacts are dialled
#: after the button is pressed - fewer in practice, because a dial takes far
#: longer than the interval - against one query every two seconds for the length
#: of the run.
_POLL_INTERVAL_SECONDS = 2.0


class StopSignal:
    """A cached "has this run been asked to stop?" for one run.

    Latching: once the answer is yes it is never re-queried and never goes back
    to no. A stop is not revocable - there is no resume - so re-asking could only
    ever produce the same answer, and a database hiccup mid-run must not
    resurrect a run somebody deliberately halted.

    Not thread-safe and does not need to be: the dialler's contacts run as tasks
    on one event loop. Two of them arriving here at once may both issue the
    query, which costs one redundant read and cannot produce a wrong answer.
    """

    def __init__(self, run_id: str, auth_user_id: str) -> None:
        self._run_id = run_id
        self._auth_user_id = auth_user_id
        self._stopped = False
        self._checked_at = 0.0

    async def is_stopped(self) -> bool:
        if self._stopped:
            return True

        now = time.monotonic()
        if now - self._checked_at < _POLL_INTERVAL_SECONDS:
            return False
        self._checked_at = now

        try:
            async with database.as_user(self._auth_user_id) as conn:
                self._stopped = await runs_repo.stop_requested(conn, self._run_id)
        except Exception:  # noqa: BLE001 - see below: never fail-closed on this one
            # Deliberately *not* fail-closed, and this is the one place in the
            # dial path where that is right. CLAUDE.md's fail-closed rule is
            # about guards that prevent an action; this is a guard that stops
            # one. Treating an unreachable database as "stopped" would abandon
            # every remaining contact of a legitimate run over a blip, which is
            # the more destructive of the two wrong answers - and the run's real
            # guards (suppression, credit) are unaffected either way.
            log.warning(
                "could not read the stop flag for run %s - continuing to dial",
                self._run_id,
            )
            return False

        if self._stopped:
            log.info("run %s was asked to stop - no further contacts will be dialled", self._run_id)
        return self._stopped


async def request_stop(
    *, org_id: UUID, auth_user_id: str, user_id: UUID, run_id: str
) -> dict[str, object]:
    """Record that a person asked this run to stop.

    Raises `RunNotStoppable` when there is nothing to stop, rather than
    answering 200 for a run that finished on its own five minutes ago - the
    interface would report "Run stopped" for something it did not do (CLAUDE.md
    non-negotiable #9).

    A run this connection cannot see is reported as not found rather than as
    forbidden, matching how the rest of the product answers for a row RLS hides:
    a refusal that confirms the id exists is itself a leak.
    """
    async with database.as_user(auth_user_id) as conn:
        run = await runs_repo.get_run(conn, org_id, run_id)
        if run is None:
            raise RunNotStoppable("That run no longer exists.")

        current = RunStatus(run["status"])
        if not can_request_stop(current):
            raise RunNotStoppable(
                f"This run already {_finished_word(current)}, so there is nothing to stop."
            )

        stopped = await runs_repo.request_stop(
            conn, org_id=org_id, run_id=run_id, stopped_by=user_id
        )
        if stopped is None:
            # `get_run` saw it, `request_stop` did not: either it closed in the
            # gap between the two, or this caller may read the run but not stop
            # it (an operator looking at a run somebody else started, visible to
            # them because an escalation from it is assigned to them).
            raise RunNotStoppable(
                "That run can't be stopped from this account. Ask an admin, or "
                "whoever started it."
            )

        # Re-read so the response carries the same shape every other run
        # endpoint returns, rather than a second, thinner run type the frontend
        # would have to special-case.
        refreshed = await runs_repo.get_run(conn, org_id, run_id)

    log.info("run %s stopped by request", run_id)
    return dict(refreshed) if refreshed is not None else dict(stopped)


def _finished_word(status: RunStatus) -> str:
    return {
        RunStatus.COMPLETED: "finished",
        RunStatus.FAILED: "failed",
        RunStatus.STOPPED: "stopped",
    }.get(status, "finished")


__all__ = ["RunNotStoppable", "StopSignal", "request_stop"]
