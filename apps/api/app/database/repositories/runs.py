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
) -> None:
    await conn.execute(
        """
        insert into public.runs (id, org_id, campaign_id, total, started_by)
        values ($1, $2, $3, $4, $5)
        """,
        run_id,
        org_id,
        campaign_id,
        total,
        started_by,
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


async def finish_run(conn: asyncpg.Connection, run_id: str, error: str | None = None) -> None:
    await conn.execute(
        """
        update public.runs
           set status = case when $2::text is null then 'completed' else 'failed' end,
               finished_at = now(),
               error = $2
         where id = $1
        """,
        run_id,
        error,
    )


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
