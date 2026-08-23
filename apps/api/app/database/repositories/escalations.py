"""SQL for real, persisted, assignable escalations.

Replaces the computed "needs a person" state (ISSUES.md #7): one row per
`call_outcomes.id`, inserted by `runs.py`'s/`webhooks.py`'s outcome-resolution
call sites - never a trigger, matching this codebase's convention of keeping
business logic in application code, not the database.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def create_for_outcome(
    conn: asyncpg.Connection, *, org_id: UUID, run_id: str, call_outcome_id: UUID
) -> None:
    """Insert the escalation row for a newly-resolved outcome.

    `call_outcome_id` is unique - `append_outcome` upserts on
    `(run_id, contact_name, phone_masked)`, so a call that later moves *out*
    of an escalating disposition (a retry that eventually completes cleanly)
    would otherwise leave a stale escalation behind pointing at the same row.
    `on conflict do nothing` here is intentionally silent: if the call is
    re-classified as escalating again after a status flip, the original
    escalation (open or already resolved) is left exactly as it was rather
    than duplicated or reset.
    """
    await conn.execute(
        """
        insert into public.escalations (org_id, run_id, call_outcome_id)
        values ($1, $2, $3)
        on conflict (call_outcome_id) do nothing
        """,
        org_id,
        run_id,
        call_outcome_id,
    )


async def list_for_org(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    """Every escalation RLS lets this connection see, newest first, joined to
    the call outcome for display (contact, transcript, the reasoning chain, and
    what the call did or did not collect) and to the run for the agent that
    held the conversation."""
    return await conn.fetch(
        """
        select e.id, e.org_id, e.run_id, e.call_outcome_id,
               e.status as escalation_status,
               e.assigned_to, au.name as assigned_to_name,
               e.assigned_by, ab.name as assigned_by_name,
               e.resolved_by, rb.name as resolved_by_name, e.resolved_at,
               c.contact_name, c.phone_masked, c.status, c.provider_call_id,
               c.disposition, c.disposition_reason, c.sentiment, c.sentiment_reason,
               c.transcript, c.summary, c.duration_seconds, c.error, c.extracted,
               c.created_at,
               -- What the call did and did not get. `handoff_questions` is the
               -- point of this queue: a person picking an item up needs to know
               -- what is still outstanding, not just that something was.
               c.collected, c.missing_required_fields, c.handoff_questions,
               c.from_number_masked,
               r.voice_agent_id, va.name as agent_name,
               r.started_by as run_started_by
        from public.escalations e
        join public.call_outcomes c on c.id = e.call_outcome_id
        join public.runs r on r.id = e.run_id
        left join public.voice_agents va on va.id = r.voice_agent_id
        left join public.users au on au.id = e.assigned_to
        left join public.users ab on ab.id = e.assigned_by
        left join public.users rb on rb.id = e.resolved_by
        where e.org_id = $1
        order by c.created_at desc
        """,
        org_id,
    )


async def get_for_org(conn: asyncpg.Connection, org_id: UUID, escalation_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "select id, org_id, run_id, status from public.escalations where org_id = $1 and id = $2",
        org_id,
        escalation_id,
    )


async def assign(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    escalation_id: UUID,
    assigned_to: UUID,
    assigned_by: UUID,
) -> asyncpg.Record | None:
    """Only an *open* escalation can be (re)assigned - matches `resolve()`'s
    own guard below. Without this, a resolved item could silently pick up a
    new `assigned_to` with no visible effect anywhere (the worklist only
    ever shows `status = 'open'`), which would read as "nothing happened"
    even though the row changed underneath."""
    return await conn.fetchrow(
        """
        update public.escalations
           set assigned_to = $3, assigned_by = $4
         where org_id = $1 and id = $2 and status = 'open'
        returning id
        """,
        org_id,
        escalation_id,
        assigned_to,
        assigned_by,
    )


async def resolve(
    conn: asyncpg.Connection, *, org_id: UUID, escalation_id: UUID, resolved_by: UUID
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        update public.escalations
           set status = 'resolved', resolved_by = $3, resolved_at = now()
         where org_id = $1 and id = $2 and status = 'open'
        returning id
        """,
        org_id,
        escalation_id,
        resolved_by,
    )


async def open_counts_by_member(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    """Open escalations per teammate, attributed to whoever it's assigned to,
    falling back to whoever started the underlying run when unassigned - the
    same "assignment first, ownership as fallback" rule the team-performance
    view uses everywhere else."""
    return await conn.fetch(
        """
        select coalesce(e.assigned_to, r.started_by) as member_id,
               count(*) as open_escalations
        from public.escalations e
        join public.runs r on r.id = e.run_id
        where e.org_id = $1 and e.status = 'open'
        group by coalesce(e.assigned_to, r.started_by)
        """,
        org_id,
    )


async def resolve_many(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    escalation_ids: list[UUID],
    resolved_by: UUID,
) -> list[UUID]:
    """Resolve several at once. Returns the ids that actually changed.

    One statement, not a loop: clearing twenty unreachable calls after a bad run
    is the case this exists for, and twenty round trips would each be able to
    fail separately, leaving the caller to explain a half-applied action.

    Partial success is the contract rather than an error. `status = 'open'`
    filters out anything a teammate resolved a second earlier - a real race on a
    shared worklist, not an edge case - and the caller reports how many landed.
    Refusing the whole batch because one item was already handled would be worse
    for the person clicking it and no safer.
    """
    if not escalation_ids:
        return []
    rows = await conn.fetch(
        """
        update public.escalations
           set status = 'resolved', resolved_by = $3, resolved_at = now()
         where org_id = $1 and id = any($2::uuid[]) and status = 'open'
        returning id
        """,
        org_id,
        escalation_ids,
        resolved_by,
    )
    return [row["id"] for row in rows]
