"""Closing runs whose dispatcher died, so nothing reads "Running" forever.

The gap this fills, stated plainly: a run lives in `BackgroundTasks` on the
uvicorn worker that served `POST /api/v1/runs`, so a restart, a redeploy or a
crash mid-run kills it. The two sweeps that would settle its abandoned rows
(`expire_stale_in_flight`, `abandon_undialled`) already exist and are correct -
but both only run when *something asks*, and the only two things that ask are a
worker completion callback and the run's own dispatcher. A run whose dispatcher
is gone and whose workers all died has nobody left to ask, so it stays open
permanently, the detail page polls it forever, and the operator has no way to
tell a stuck run from a slow one (`ISSUES.md` #117).

**A loop rather than a startup-only pass.** A startup sweep would fix a run
stranded by the redeploy that just happened and nothing else. The failure this
is actually for - the voice runtime dying while the API stays up - produces a
stranded run with no restart anywhere near it, so a pass that only runs at boot
would leave it open until the next unrelated deploy.

**Why `privileged`, and why that is allowed here.** Reconciliation is
cross-organisation by nature: it does not act for a signed-in person, so there
is no `auth_user_id` to scope `as_user` with, and no request whose caller could
be trusted. CLAUDE.md permits the bypass outside a request handler and requires
a reason string, which `acquire()` logs. This is that case - a background task
owned by the process, never reachable from HTTP.

**Idempotent and safe to run in every worker.** Each worker starts its own loop,
so N workers reconcile the same run concurrently. That is harmless by
construction: `finish_if_all_settled` closes on a single guarded statement
(`finished_at is null`), so exactly one of them wins and the rest change
nothing.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import config
from app.database import privileged
from app.database.repositories import runs as runs_repo

log = logging.getLogger("app.services.run_reconciler")


def _quiet_after_seconds() -> int:
    """How long a run may show no sign of life before it is presumed dead.

    Twice the carrier-enforced call ceiling, the same margin
    `routes/internal.py` uses for a single in-flight row and for the same
    reason: past that, a call cannot still be live, so silence means the
    dispatcher or the worker is gone rather than busy. Deriving it from the same
    config value keeps the two from drifting into disagreeing about what "too
    long" means.
    """
    return int(config.poll_timeout_seconds) * 2


async def reconcile_once() -> int:
    """Settle every stranded run this pass can see. Returns how many closed.

    Each run is handled in its own statement rather than one bulk update: the
    sweeps are per-run by nature (they insert one row per undialled contact),
    and one run that fails to reconcile must not abandon the rest of the batch.
    """
    quiet_for = _quiet_after_seconds()
    closed = 0

    async with privileged.acquire("reconcile runs abandoned by a dead dispatcher") as conn:
        stale = await runs_repo.list_open_runs(conn, quiet_for_seconds=quiet_for)
        for row in stale:
            run_id = row["id"]
            try:
                if await runs_repo.finish_if_all_settled(
                    conn, run_id, stale_after_seconds=quiet_for
                ):
                    closed += 1
                    log.warning(
                        "run %s was closed by reconciliation - its dispatcher never finished",
                        run_id,
                    )
            except Exception:  # one bad run must not abandon the rest of the batch
                log.exception("could not reconcile run %s", run_id)

    return closed


async def run_forever(interval_seconds: int = 60) -> None:
    """The background loop. Cancelled on shutdown by the lifespan that starts it.

    A failure is logged and the loop continues: this is a self-healing pass, and
    a reconciler that dies on the first transient database error is a reconciler
    that is not running when the outage it was meant to clean up after ends.
    """
    log.info("run reconciler started - every %ds", interval_seconds)
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await reconcile_once()
        except asyncio.CancelledError:
            log.info("run reconciler stopped")
            raise
        except Exception:  # the loop has to outlive any single failed pass
            log.exception("run reconciliation pass failed")


__all__ = ["reconcile_once", "run_forever"]
