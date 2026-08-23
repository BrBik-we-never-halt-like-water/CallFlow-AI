"""SQL for org-owned runs and their per-contact call outcomes."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import asyncpg

log = logging.getLogger("app.database.repositories.runs")


async def create_run(
    conn: asyncpg.Connection,
    *,
    run_id: str,
    org_id: UUID,
    voice_agent_id: UUID | None,
    total: int,
    started_by: UUID,
    name: str | None = None,
    run_instruction: str | None = None,
    allocation_strategy: str = "round_robin",
) -> None:
    await conn.execute(
        """
        insert into public.runs
            (id, org_id, voice_agent_id, total, started_by, name,
             run_instruction, allocation_strategy)
        values ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        run_id,
        org_id,
        voice_agent_id,
        total,
        started_by,
        name,
        run_instruction,
        allocation_strategy,
    )


async def append_outcome(
    conn: asyncpg.Connection, *, run_id: str, org_id: UUID, outcome: dict[str, Any]
) -> UUID:
    """Insert or update a contact's row. Returns the row's stable id, needed
    to link a real `escalations` row to the outcome that triggered it - this
    was write-only until the role-based UI roadmap's Phase 2.

    A live call reports several times as it progresses (queued → ringing →
    completed), so this matches on the contact rather than appending - one call
    produces one row across all its status transitions, not a row per change.

    **A settled row is never downgraded back to in-flight.** The two writers
    race by design: origination writes IN_FLIGHT once a call is answered, and
    the worker's completion callback writes the terminal row when it ends. A
    short call finishes before the first write lands, and without the guard
    below the in-flight row would overwrite the terminal one - discarding the
    transcript and leaving `finish_if_all_settled` permanently unable to close
    the run.
    """
    row = await conn.fetchrow(
        """
        insert into public.call_outcomes
            (run_id, org_id, contact_name, phone_masked, status, provider_call_id,
             transcript, summary, sentiment, sentiment_reason, extracted,
             disposition, disposition_reason, error, duration_seconds,
             task_completed, completion_confidence_score, completion_confidence_label,
             evidence, attempts, collected, missing_required_fields,
             handoff_questions, from_number_masked, phone_hash)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                $16, $17, $18, $19, $20, $21, $22, $23, $24, $25)
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
            attempts = excluded.attempts,
            collected = excluded.collected,
            missing_required_fields = excluded.missing_required_fields,
            handoff_questions = excluded.handoff_questions,
            -- The dialler knows the line; the worker does not. Coalesced so the
            -- terminal write cannot blank what origination recorded.
            from_number_masked = coalesce(
                excluded.from_number_masked, public.call_outcomes.from_number_masked),
            -- Same coalesce, same reason: only the dialler ever knows the real
            -- number, so the worker's terminal write must not blank the hash
            -- that an opt-out on this call will be suppressed by.
            phone_hash = coalesce(
                excluded.phone_hash, public.call_outcomes.phone_hash)
        where public.call_outcomes.disposition = 'in_flight'
           or excluded.disposition <> 'in_flight'
        returning id
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
        outcome.get("collected", {}),
        outcome.get("missing_required_fields", []),
        outcome.get("handoff_questions", []),
        outcome.get("from_number_masked"),
        outcome.get("phone_hash"),
    )
    if row is not None:
        return row["id"]

    # The guard above suppressed the update, so nothing was returned. The row
    # exists and is already terminal - the caller still needs its id to link an
    # escalation to it.
    return await conn.fetchval(
        """
        select id from public.call_outcomes
        where run_id = $1 and contact_name = $2 and phone_masked = $3
        """,
        run_id,
        outcome["contact_name"],
        outcome["phone_masked"],
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


async def expire_stale_in_flight(
    conn: asyncpg.Connection, run_id: str, *, stale_after_seconds: int
) -> int:
    """Settle rows whose worker never reported. Returns how many.

    Every call carries a hard `max_call_duration` the carrier itself enforces,
    so an in-flight row older than that ceiling cannot still be a live call -
    the worker died, or its callback never got through. Left alone the row
    blocks `finish_if_all_settled` forever and the run reads "running" for good.

    Recorded as a real failure rather than quietly closed: nobody knows what
    was said, and showing that as a completed call would be a success state for
    something that did not happen (CLAUDE.md non-negotiable #9).
    """
    rows = await conn.fetch(
        """
        update public.call_outcomes
           set status = 'FAILED',
               disposition = 'unreachable',
               disposition_reason = 'The call ended without reporting a result.',
               error = 'timed_out'
         where run_id = $1
           and disposition = 'in_flight'
           and created_at < now() - make_interval(secs => $2::int)
        returning id, org_id
        """,
        run_id,
        stale_after_seconds,
    )
    if not rows:
        return 0

    # These rows have to reach the "needs a person" queue, and this is the only
    # place that can put them there. Every other escalation is raised by an
    # application call site reacting to a result it was handed
    # (`routes/internal.py`, the dialler's progress hook) - but by definition
    # nothing ever reported these, so no such call site is ever reached. Without
    # this insert they take a needs-a-person disposition (`unreachable`) and
    # silently never appear in the queue that disposition exists to fill.
    #
    # They are the escalations that most deserve a person: the call connected,
    # somebody had a conversation with an agent, and nobody knows what was said
    # or what they were told.
    await conn.executemany(
        """
        insert into public.escalations (org_id, run_id, call_outcome_id)
        values ($1, $2, $3)
        on conflict (call_outcome_id) do nothing
        """,
        [(row["org_id"], run_id, row["id"]) for row in rows],
    )
    return len(rows)


async def abandon_undialled(
    conn: asyncpg.Connection, run_id: str, *, stale_after_seconds: int
) -> int:
    """Account for contacts that never got a row at all. Returns how many.

    `expire_stale_in_flight` rescues a call that started and never reported.
    This is the other half: a run dispatched into `BackgroundTasks` lives on the
    uvicorn worker that served the request, so a restart or redeploy mid-run
    kills it, and every contact it had not reached yet is never dialled. Those
    contacts have no `call_outcomes` row, so `count(*) >= r.total` can never be
    satisfied - the run reads "running" forever, and the detail page polls it
    forever (`ISSUES.md` #156).

    Recorded as a real failure with its own reason rather than silently reducing
    `total`: nobody called these people, and a run that quietly shrinks its own
    target is a success state for something that did not happen.

    **`skipped`, not `unreachable`, and the difference is not cosmetic.**
    `unreachable` is a needs-a-person disposition, so a crashed run of five
    hundred contacts would have posted five hundred items into the escalation
    queue - burying the handful of real ones under a wall of people nobody ever
    dialled. It is also just untrue: these contacts were not unreachable, they
    were never tried, which is exactly what `skipped` means everywhere else in
    this codebase (a suppressed contact, a stopped run). The run's own status
    and these rows' own reason already say what happened.

    **Silence is measured from the last sign of life, not from the run's start.**
    Keying off `started_at` would fire on any run that simply takes longer than
    the window: origination holds a concurrency slot until the carrier answers or
    times out, so a large run legitimately has contacts with no row yet half an
    hour in. Fabricating failures for those would close a run whose calls are
    still being placed, and their real outcomes would then land as extra rows
    past `total`. `max(created_at)` is the dialler's own heartbeat - it writes a
    row per contact as origination resolves - so this fires only when nothing has
    happened for the whole window, which is what a dead dispatcher looks like.
    """
    row = await conn.fetchrow(
        """
        select r.total - count(o.id) as unaccounted
          from public.runs r
          left join public.call_outcomes o on o.run_id = r.id
         where r.id = $1
           and r.finished_at is null
         group by r.total, r.started_at
        having coalesce(max(o.created_at), r.started_at)
                 < now() - make_interval(secs => $2::int)
        """,
        run_id,
        stale_after_seconds,
    )
    if row is None or row["unaccounted"] <= 0:
        return 0

    missing = int(row["unaccounted"])
    await conn.executemany(
        """
        insert into public.call_outcomes
            (run_id, org_id, contact_name, phone_masked, status, disposition,
             disposition_reason, sentiment, error)
        select $1, r.org_id, $2, '', 'FAILED', 'skipped',
               'The run ended before this contact was dialled.', 'unknown',
               'never_dialled'
          from public.runs r where r.id = $1
        on conflict (run_id, contact_name, phone_masked) do nothing
        """,
        [(run_id, f"Not dialled ({i + 1})") for i in range(missing)],
    )
    log.warning("run %s: %d contact(s) were never dialled and were closed", run_id, missing)
    return missing


async def finish_if_all_settled(
    conn: asyncpg.Connection, run_id: str, *, stale_after_seconds: int | None = None
) -> bool:
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

    `stale_after_seconds` sweeps abandoned rows first, so one dead worker
    cannot hold a whole run open. It only runs when something asks - a run
    whose *every* worker dies has nobody left to ask, and stays open until the
    next callback or run-completion check touches it (`ISSUES.md` #117).
    """
    if stale_after_seconds is not None:
        expired = await expire_stale_in_flight(
            conn, run_id, stale_after_seconds=stale_after_seconds
        )
        if expired:
            log.warning(
                "run %s: %d call(s) never reported a result and were closed as unreachable",
                run_id,
                expired,
            )
        # Both sweeps, because they catch different failures: the one above
        # settles a call that started and never reported, this one accounts for
        # a contact that was never dialled at all because the dispatching
        # process died. Only the pair of them can guarantee the count below is
        # reachable.
        await abandon_undialled(conn, run_id, stale_after_seconds=stale_after_seconds)

    # The closing status is decided here, in SQL, and mirrored by
    # `domain.run_state.closing_status()` - `tests/test_run_state.py` asserts the
    # two agree. It cannot be delegated to the domain and applied afterwards: the
    # single-statement update is what makes two concurrent callbacks unable to
    # both close the run, and reading the flag first would reintroduce exactly
    # that race.
    row = await conn.fetchrow(
        """
        update public.runs r
           set status = case
                          when r.stop_requested_at is null then 'completed'
                          else 'stopped'
                        end,
               finished_at = now()
         where r.id = $1
           and r.finished_at is null
           and (
             select count(*) from public.call_outcomes o
              where o.run_id = r.id and o.disposition <> 'in_flight'
           ) >= r.total
        returning r.id, r.status
        """,
        run_id,
    )
    return row is not None


async def lookup_owner_for_webhook(conn: asyncpg.Connection, run_id: str) -> asyncpg.Record | None:
    """Unauthenticated resolution, via the SECURITY DEFINER
    `lookup_run_owner_for_webhook` function - the voice runtime's completion
    callback (`routes/internal.py`) is CallFlow's own worker, not a person with
    a session, so it has no signed-in user to scope a plain query with. Runs on
    a `database.anonymous()` connection, same shape as
    `invitations_repo.lookup_public`. Named for CALL-E's webhook receiver,
    which was the original caller; the function is unchanged, the caller is not.

    Returns the run's *starter*, not just any org member - see the migration's
    own docstring for why that's the deliberate choice.
    """
    return await conn.fetchrow(
        "select org_id, voice_agent_id, auth_user_id "
        "from public.lookup_run_owner_for_webhook($1)",
        run_id,
    )


async def get_run(conn: asyncpg.Connection, org_id: UUID, run_id: str) -> asyncpg.Record | None:
    # `started_by` was write-only until the role-based UI roadmap's Phase 1 -
    # RLS (`runs_select`, migration 202608092000) already narrows *which* runs
    # an operator's plain org-member query returns; this join is what lets an
    # admin/owner/viewer (who see every run) tell whose run each one is.
    return await conn.fetchrow(
        """
        select r.id, r.org_id, r.voice_agent_id, r.total, r.status, r.started_at,
               r.finished_at, r.error, r.started_by, r.name, r.run_instruction,
               r.allocation_strategy, r.stop_requested_at, r.stopped_by,
               u.name as started_by_name, u.avatar_url as started_by_avatar_url,
               sb.name as stopped_by_name,
               va.name as agent_name
        from public.runs r
        left join public.users u on u.id = r.started_by
        left join public.users sb on sb.id = r.stopped_by
        -- Left join, and the name is resolved here rather than in the client: a
        -- run whose agent was removed still has to list, and nothing above this
        -- keeps an agent list to look the name up in.
        left join public.voice_agents va on va.id = r.voice_agent_id
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
               completion_confidence_score, completion_confidence_label, evidence, attempts,
               collected, missing_required_fields, handoff_questions, from_number_masked
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


async def team_performance(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    """`summarize_by_member`, plus a run-status breakdown - the richer view
    behind the team-performance dashboard panel. Same RLS reasoning as
    `summarize_by_member`: this only returns something wider than "my own
    row" for a connection RLS already lets see the whole org.
    """
    return await conn.fetch(
        """
        select r.started_by, u.name as started_by_name, u.avatar_url as started_by_avatar_url,
               count(distinct r.id) as total_runs,
               count(distinct r.id) filter (where r.status = 'running') as runs_active,
               count(distinct r.id) filter (where r.status = 'completed') as runs_completed,
               count(distinct r.id) filter (where r.status in ('failed', 'stopped'))
                 as runs_failed,
               count(c.id) filter (where c.disposition <> 'in_flight') as total_calls,
               count(c.id) filter (where c.disposition = 'auto_closed') as calls_closed
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
        select r.id, r.voice_agent_id, r.name, r.total, r.status, r.started_at,
               r.finished_at, r.error, r.started_by, r.stop_requested_at,
               u.name as started_by_name, u.avatar_url as started_by_avatar_url,
               va.name as agent_name,
               count(c.id) as completed
        from public.runs r
        left join public.call_outcomes c
          on c.run_id = r.id and c.disposition <> 'in_flight'
        left join public.users u on u.id = r.started_by
        left join public.voice_agents va on va.id = r.voice_agent_id
        where r.org_id = $1
        -- `va.name` has to be grouped too: it is selected but not aggregated, and
        -- leaving it out is a query that fails rather than a wrong answer.
        group by r.id, r.started_by, u.name, u.avatar_url, va.name
        order by r.started_at desc
        """,
        org_id,
    )


async def request_stop(
    conn: asyncpg.Connection, *, org_id: UUID, run_id: str, stopped_by: UUID
) -> asyncpg.Record | None:
    """Ask a run to stop dialling. Returns the run's new state, or None.

    Idempotent (CLAUDE.md non-negotiable #6): `stop_requested_at` is written
    with `coalesce`, so pressing Stop twice keeps the first timestamp rather
    than moving the record of when somebody actually decided.

    **Does not change `status`.** A stop is a request - conversations already in
    progress keep going and report back, and the run closes as `stopped` when
    the last of them settles (`finish_if_all_settled`). Flipping the status here
    would show a stopped run beside rows still reading "In conversation…", which
    is the same untruth `finish_if_all_settled` exists to avoid at the other end.

    **Visibility is re-stated rather than inherited.** `runs_update`'s RLS
    policy allows any owner/admin/operator in the organisation, which is wider
    than `runs_select` - that one narrows an operator to runs they started. So
    an operator who guessed another operator's run id could otherwise stop a run
    they cannot see. The predicate below is `runs_select`'s own rule, applied to
    a write.
    """
    return await conn.fetchrow(
        """
        update public.runs r
           set stop_requested_at = coalesce(r.stop_requested_at, now()),
               stopped_by = coalesce(r.stopped_by, $3)
         where r.id = $2
           and r.org_id = $1
           and r.finished_at is null
           and (
             public.has_org_role(r.org_id, array['owner','admin']::public.org_role[])
             or r.started_by = public.current_user_id()
           )
        returning r.id, r.status, r.stop_requested_at, r.stopped_by
        """,
        org_id,
        run_id,
        stopped_by,
    )


async def stop_requested(conn: asyncpg.Connection, run_id: str) -> bool:
    """Whether this run has been asked to stop.

    The dialler's own poll, and deliberately the narrowest possible query: it
    runs once every few seconds for the length of a run, so it reads one boolean
    off the primary key and nothing else.
    """
    return bool(
        await conn.fetchval(
            "select stop_requested_at is not null from public.runs where id = $1",
            run_id,
        )
    )


async def list_open_runs(
    conn: asyncpg.Connection, *, quiet_for_seconds: int, limit: int = 200
) -> list[asyncpg.Record]:
    """Runs that are still open and have shown no sign of life for a while.

    The reconciler's input (`services/run_reconciler.py`). "Quiet" is measured
    from the newest outcome row rather than from `started_at`, for the same
    reason `abandon_undialled` measures it that way: origination holds a slot
    until the carrier answers, so a large run legitimately has contacts with no
    row yet a long way in. `max(created_at)` is the dialler's own heartbeat.

    Bounded by `limit` so one very broken deployment cannot turn a background
    sweep into an unbounded scan; the next tick picks up whatever it missed.
    """
    return await conn.fetch(
        """
        select r.id, r.org_id
          from public.runs r
          left join public.call_outcomes o on o.run_id = r.id
         where r.finished_at is null
         group by r.id, r.org_id, r.started_at
        having coalesce(max(o.created_at), r.started_at)
                 < now() - make_interval(secs => $1::int)
         order by r.started_at
         limit $2
        """,
        quiet_for_seconds,
        limit,
    )


async def phone_hash_for_outcome(
    conn: asyncpg.Connection, call_outcome_id: UUID
) -> str | None:
    """The suppression key for one call, if the dialler recorded it.

    Null for any row written before `f3c7b21a9d04`, and for a contact that was
    never dialled. The caller turns that into "we could not auto-suppress this
    one" rather than guessing - there is no way back to a phone number from a
    masked one, which is the whole reason this column exists.
    """
    return await conn.fetchval(
        "select phone_hash from public.call_outcomes where id = $1",
        call_outcome_id,
    )


async def count_reached(conn: asyncpg.Connection, run_id: str) -> int:
    """How many of a run's contacts the dialler has already got to.

    **Every outcome row, including in-flight ones** - deliberately not the
    settled count `finish_if_all_settled` uses. The question this answers is
    "how many people will a stop now spare", and somebody currently mid-
    conversation is not one of them: their call was placed and a stop
    explicitly lets it finish. Counting them as un-dialled would tell an
    operator a stop prevents more calls than it does, which is the wrong
    direction to be wrong in.

    A contact with no row at all is one the dialler has not reached, which is
    exactly the set a stop still protects.
    """
    return int(
        await conn.fetchval(
            "select count(*) from public.call_outcomes where run_id = $1",
            run_id,
        )
        or 0
    )
