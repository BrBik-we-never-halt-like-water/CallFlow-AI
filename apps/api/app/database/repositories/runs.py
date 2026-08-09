"""SQL for org-owned runs and their per-contact call outcomes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg


async def create_run(
    conn: asyncpg.Connection,
    *,
    run_id: str,
    org_id: UUID,
    campaign_id: str,
    total: int,
    started_by: UUID,
    idempotency_key: str | None = None,
) -> bool:
    """Insert a new run row. Returns False, without inserting, if a run with
    the same (org_id, idempotency_key) already exists - the caller is then
    expected to fetch and return that run instead of starting a second one.

    The partial unique index only covers non-null keys, so a caller that
    never sends one (nothing requires it) always inserts normally.
    """
    row = await conn.fetchrow(
        """
        insert into public.runs (id, org_id, campaign_id, total, started_by, idempotency_key)
        values ($1, $2, $3, $4, $5, $6)
        on conflict (org_id, idempotency_key) where idempotency_key is not null do nothing
        returning id
        """,
        run_id,
        org_id,
        campaign_id,
        total,
        started_by,
        idempotency_key,
    )
    return row is not None


async def get_run_by_idempotency_key(
    conn: asyncpg.Connection, org_id: UUID, idempotency_key: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        select id, total from public.runs where org_id = $1 and idempotency_key = $2
        """,
        org_id,
        idempotency_key,
    )


async def append_outcome(
    conn: asyncpg.Connection, *, run_id: str, org_id: UUID, outcome: dict[str, Any]
) -> None:
    """Insert or update a contact's row.

    A live call reports several times as it progresses (queued → ringing →
    completed), so this matches on the contact rather than appending - one call
    produces one row across all its status transitions, not a row per change.
    """
    await conn.execute(
        """
        insert into public.call_outcomes
            (run_id, org_id, contact_name, phone_masked, status, provider_call_id,
             transcript, summary, sentiment, sentiment_reason, extracted,
             disposition, disposition_reason, error, duration_seconds)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        on conflict (run_id, contact_name, phone_masked) do update set
            status = excluded.status,
            provider_call_id = excluded.provider_call_id,
            transcript = excluded.transcript,
            summary = excluded.summary,
            sentiment = excluded.sentiment,
            sentiment_reason = excluded.sentiment_reason,
            extracted = excluded.extracted,
            disposition = excluded.disposition,
            disposition_reason = excluded.disposition_reason,
            error = excluded.error,
            duration_seconds = excluded.duration_seconds
        """,
        run_id,
        org_id,
        outcome["contact_name"],
        outcome["phone_masked"],
        outcome["status"],
        outcome.get("provider_call_id"),
        outcome.get("transcript"),
        outcome.get("summary"),
        outcome["sentiment"],
        outcome.get("sentiment_reason"),
        outcome.get("extracted", {}),
        outcome["disposition"],
        outcome.get("disposition_reason"),
        outcome.get("error"),
        outcome.get("duration_seconds"),
    )


async def finish_run(
    conn: asyncpg.Connection,
    run_id: str,
    error: str | None = None,
    *,
    status: str | None = None,
) -> None:
    """Mark a run terminal. `status` overrides the error-based default (used
    for `canceled`, since stopping a run early is neither a completion nor a
    failure)."""
    resolved_status = status if status is not None else ("failed" if error is not None else "completed")
    await conn.execute(
        """
        update public.runs
           set status = $2,
               finished_at = now(),
               error = $3
         where id = $1
        """,
        run_id,
        resolved_status,
        error,
    )


async def request_cancel(conn: asyncpg.Connection, org_id: UUID, run_id: str) -> str | None:
    """Marks a run as canceling. Returns the resulting status, or None if the
    run doesn't exist for this org, or isn't in a cancellable state.

    Idempotent: calling this twice on an already-canceling run just re-confirms
    the same state (`coalesce` keeps the original request time) rather than
    erroring on a second click.
    """
    row = await conn.fetchrow(
        """
        update public.runs
           set status = 'canceling',
               cancel_requested_at = coalesce(cancel_requested_at, now())
         where org_id = $1 and id = $2 and status in ('running', 'canceling')
        returning status
        """,
        org_id,
        run_id,
    )
    return row["status"] if row else None


async def is_cancel_requested(conn: asyncpg.Connection, run_id: str) -> bool:
    row = await conn.fetchrow(
        "select cancel_requested_at is not null as requested from public.runs where id = $1",
        run_id,
    )
    return bool(row and row["requested"])


async def reap_orphaned_runs(conn: asyncpg.Connection) -> int:
    """Fail every run still 'running'/'canceling' at process boot.

    A run's dial loop lives entirely inside one `BackgroundTasks` coroutine in
    one process (F18) - there is no queue, no worker, nothing that could have
    kept it going across a restart. If this process is only just starting,
    any row still marked running was being driven by the *previous* process,
    which is now gone: it is orphaned by definition, not by a timeout guess.
    Called once, cross-org, before the app accepts any new run - the reason
    this needs `privileged.acquire()` rather than `as_user()`.
    """
    result = await conn.execute(
        """
        update public.runs
           set status = 'failed',
               finished_at = now(),
               error = 'The service restarted before this run finished.'
         where status in ('running', 'canceling')
        """
    )
    # asyncpg's Connection.execute() returns a tag string like "UPDATE 3".
    return int(result.rsplit(" ", 1)[-1]) if result else 0


async def get_run(conn: asyncpg.Connection, org_id: UUID, run_id: str) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        select id, org_id, campaign_id, total, status, started_at, finished_at, error
        from public.runs
        where org_id = $1 and id = $2
        """,
        org_id,
        run_id,
    )


async def list_outcomes(conn: asyncpg.Connection, run_id: str) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select contact_name, phone_masked, status, provider_call_id, transcript, summary,
               sentiment, sentiment_reason, extracted, disposition, disposition_reason,
               error, duration_seconds, created_at
        from public.call_outcomes
        where run_id = $1
        order by created_at
        """,
        run_id,
    )


async def list_runs(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select r.id, r.campaign_id, r.total, r.status, r.started_at, r.finished_at, r.error,
               count(c.id) as completed
        from public.runs r
        left join public.call_outcomes c
          on c.run_id = r.id and c.disposition <> 'in_flight'
        where r.org_id = $1
        group by r.id
        order by r.started_at desc
        """,
        org_id,
    )
