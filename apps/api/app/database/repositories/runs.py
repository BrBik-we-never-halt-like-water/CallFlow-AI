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
             disposition, disposition_reason, error, duration_seconds,
             task_completed, completion_confidence_score, completion_confidence_label,
             evidence, attempts)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                $16, $17, $18, $19, $20)
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
            duration_seconds = excluded.duration_seconds,
            task_completed = excluded.task_completed,
            completion_confidence_score = excluded.completion_confidence_score,
            completion_confidence_label = excluded.completion_confidence_label,
            evidence = excluded.evidence,
            attempts = excluded.attempts
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
        outcome.get("task_completed"),
        outcome.get("completion_confidence_score"),
        outcome.get("completion_confidence_label"),
        outcome.get("evidence", []),
        outcome.get("attempts", []),
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


async def finish_if_all_settled(conn: asyncpg.Connection, run_id: str) -> bool:
    """Mark the run completed only once every contact has actually settled.

    Origination returns when a call is *answered*, not when it ends, so the
    background task that started the run finishes long before the conversations
    do. Marking the run completed there would show a finished run alongside rows
    still reading "In conversation…" - a success state for something that has
    not happened (CLAUDE.md non-negotiable #9). Instead each worker callback
    asks this, and whichever one settles the last contact closes the run.

    Idempotent by the `finished_at is null` guard, and safe under the
    concurrent callbacks a multi-contact run produces: the `update` is a single
    statement, so two callbacks racing cannot both see an unfinished run and
    both write. Returns whether *this* call was the one that closed it.
    """
    row = await conn.fetchrow(
        """
        update public.runs r
           set status = 'completed', finished_at = now()
         where r.id = $1
           and r.finished_at is null
           and (
             select count(*) from public.call_outcomes o
              where o.run_id = r.id and o.disposition <> 'in_flight'
           ) >= r.total
        returning r.id
        """,
        run_id,
    )
    return row is not None


async def lookup_owner_for_webhook(conn: asyncpg.Connection, run_id: str) -> asyncpg.Record | None:
    """Unauthenticated resolution, via the SECURITY DEFINER
    `lookup_run_owner_for_webhook` function - the CALL-E webhook receiver has
    no signed-in user to scope a plain query with. Runs on a
    `database.anonymous()` connection, same shape as `invitations_repo.lookup_public`.

    Returns the run's *starter*, not just any org member - see the migration's
    own docstring for why that's the deliberate choice.
    """
    return await conn.fetchrow(
        "select org_id, campaign_id, auth_user_id from public.lookup_run_owner_for_webhook($1)",
        run_id,
    )


async def get_run(conn: asyncpg.Connection, org_id: UUID, run_id: str) -> asyncpg.Record | None:
    # `started_by` was write-only until the role-based UI roadmap's Phase 1 -
    # RLS (`runs_select`, migration 202608092000) already narrows *which* runs
    # an operator's plain org-member query returns; this join is what lets an
    # admin/owner/viewer (who see every run) tell whose run each one is.
    return await conn.fetchrow(
        """
        select r.id, r.org_id, r.campaign_id, r.total, r.status, r.started_at, r.finished_at,
               r.error, r.started_by, u.name as started_by_name,
               u.avatar_url as started_by_avatar_url
        from public.runs r
        left join public.users u on u.id = r.started_by
        where r.org_id = $1 and r.id = $2
        """,
        org_id,
        run_id,
    )


async def list_outcomes(conn: asyncpg.Connection, run_id: str) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select contact_name, phone_masked, status, provider_call_id, transcript, summary,
               sentiment, sentiment_reason, extracted, disposition, disposition_reason,
               error, duration_seconds, created_at, task_completed,
               completion_confidence_score, completion_confidence_label, evidence, attempts
        from public.call_outcomes
        where run_id = $1
        order by created_at
        """,
        run_id,
    )


async def summarize_by_member(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    """Call volume per teammate, for the admin/owner dashboard breakdown.

    Relies on RLS (`runs_select`) to do the actual narrowing: an admin/owner/
    viewer's connection sees every run in the org, so the aggregate below
    covers the whole team; an operator's connection would only ever see
    their own runs here too, which is why the route this backs is gated on
    `Permission.RUNS_READ_TEAM` rather than trusting the query alone.
    """
    return await conn.fetch(
        """
        select r.started_by, u.name as started_by_name, u.avatar_url as started_by_avatar_url,
               count(distinct r.id) as total_runs,
               count(c.id) filter (where c.disposition <> 'in_flight') as total_calls
        from public.runs r
        left join public.call_outcomes c on c.run_id = r.id
        left join public.users u on u.id = r.started_by
        where r.org_id = $1
        group by r.started_by, u.name, u.avatar_url
        order by total_calls desc
        """,
        org_id,
    )


async def list_runs(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select r.id, r.campaign_id, r.total, r.status, r.started_at, r.finished_at, r.error,
               r.started_by, u.name as started_by_name, u.avatar_url as started_by_avatar_url,
               count(c.id) as completed
        from public.runs r
        left join public.call_outcomes c
          on c.run_id = r.id and c.disposition <> 'in_flight'
        left join public.users u on u.id = r.started_by
        where r.org_id = $1
        group by r.id, r.started_by, u.name, u.avatar_url
        order by r.started_at desc
        """,
        org_id,
    )
