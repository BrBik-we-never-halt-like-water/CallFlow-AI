"""The voice runtime's completion callback, against the real database.

This closes the loop origination opens: without it every outcome sits at
IN_FLIGHT and no run ever finishes. The parts worth asserting are the trust
boundary (a shared secret is the *only* thing standing between a stranger and
writing a transcript onto someone's run), the row addressing (a completion must
resolve the in-flight row, not add a second one beside it), and run closing
(which must not happen while any contact is still talking).

Calls the route function directly rather than going through `TestClient`,
following `test_organisations_routes.py` - the handler is what FastAPI would
dispatch to anyway, and a sync test client would run the app in its own event
loop, fighting the one holding the asyncpg connection these assertions read
back through.

Skipped when DATABASE_URL is unset - see `tests/local_postgres/README.md`.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.api.v1.routes import internal as internal_module
from app.api.v1.routes.internal import CallCompletion, complete_call
from app.core.config import config
from app.database import database
from app.database.repositories import runs as runs_repo

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not config.database_url, reason="DATABASE_URL is not configured"),
]

SECRET = "internal-test-secret"
CONTACT = "Aditi"
MASKED = "+15******100"
OTHER_CONTACT = "Rahul"
OTHER_MASKED = "+15******101"


@pytest.fixture(autouse=True)
def _configured_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        internal_module, "config", dataclasses.replace(config, internal_api_secret=SECRET)
    )


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[None]:
    """The route uses `database.as_user()`/`anonymous()`, which need a live pool."""
    await database.connect()
    try:
        yield
    finally:
        await database.disconnect()


@pytest_asyncio.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(config.database_url, timeout=30)
    # The same jsonb codec `database.Database` installs on every pooled
    # connection. Without it a raw test connection hands asyncpg a Python list
    # for a jsonb column and fails with "expected str, got list" - a failure the
    # repository never sees at runtime, so the test would be lying about it.
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
        format="text",
    )
    try:
        yield conn
    finally:
        await conn.execute("select set_config('role', 'postgres', true)")
        await conn.close()


class Run:
    def __init__(self, run_id: str, org_id: uuid.UUID, auth_user_id: uuid.UUID) -> None:
        self.id = run_id
        self.org_id = org_id
        self.auth_user_id = auth_user_id


@pytest_asyncio.fixture
async def started_run(db: asyncpg.Connection, pool: None) -> AsyncIterator[Run]:
    """A real run with two contacts in flight, created through the signup trigger."""
    auth_user_id = uuid.uuid4()
    await db.execute(
        """
        insert into auth.users (id, instance_id, aud, role, email, encrypted_password,
                                email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
                                created_at, updated_at)
        values ($1, '00000000-0000-0000-0000-000000000000', 'authenticated',
                'authenticated', $2, crypt('x', gen_salt('bf')), now(),
                '{"provider":"email"}', $3::jsonb, now(), now())
        """,
        auth_user_id,
        f"internal-{auth_user_id.hex[:8]}@brbik.com",
        json.dumps({"full_name": "Internal Test"}),
    )
    row = await db.fetchrow(
        """
        select u.id as user_id, m.org_id from public.users u
        join public.memberships m on m.user_id = u.id
        where u.auth_user_id = $1
        """,
        auth_user_id,
    )
    # A real agent row: `runs.voice_agent_id` is a foreign key now, and the
    # completion handler resolves it to read `collect_fields` - which is what
    # decides whether a call came back complete. `destination` is required so
    # the missing-field path is reachable from these tests.
    agent_id = await db.fetchval(
        """
        insert into public.voice_agents
            (org_id, created_by, name, kind, stt_provider, tts_provider,
             llm_provider, llm_model, collect_fields)
        values ($1, $2, 'Completion test agent', 'custom', 'deepgram', 'elevenlabs',
                'openrouter', 'openai/gpt-4o', $3::jsonb)
        returning id
        """,
        row["org_id"],
        row["user_id"],
        [{"key": "destination", "type": "string", "description": "Where to", "required": True}],
    )

    run_id = uuid.uuid4().hex[:12]
    await db.execute(
        """
        insert into public.runs (id, org_id, voice_agent_id, total, status, started_by)
        values ($1, $2, $3, 2, 'running', $4)
        """,
        run_id,
        row["org_id"],
        agent_id,
        row["user_id"],
    )
    for name, masked in ((CONTACT, MASKED), (OTHER_CONTACT, OTHER_MASKED)):
        await db.execute(
            """
            insert into public.call_outcomes
                (run_id, org_id, contact_name, phone_masked, status, disposition,
                 disposition_reason, sentiment)
            values ($1, $2, $3, $4, 'IN_PROGRESS', 'in_flight', 'In conversation…', 'unknown')
            """,
            run_id,
            row["org_id"],
            name,
            masked,
        )

    try:
        yield Run(run_id, row["org_id"], auth_user_id)
    finally:
        await db.execute("select set_config('role', 'postgres', true)")
        await db.execute("delete from auth.users where id = $1", auth_user_id)
        await db.execute(
            """
            delete from public.organisations o
            where not exists (select 1 from public.memberships m where m.org_id = o.id)
            """
        )


def _payload(**overrides: Any) -> CallCompletion:
    body: dict[str, Any] = {
        "contact_name": CONTACT,
        "phone_masked": MASKED,
        "status": "COMPLETED",
        "provider_call_id": "SCL_1",
        "transcript": "Agent: Hello. Contact: Yes, I'm interested.",
        "extracted": {"outcome": "interested", "sentiment": "positive", "summary": "Wants Bali."},
        "duration_seconds": 42,
    }
    body.update(overrides)
    return CallCompletion(**body)


async def _complete(run_id: str, key: str | None = SECRET, **overrides: Any) -> dict[str, bool]:
    return await complete_call(run_id, _payload(**overrides), x_callflow_internal_key=key)


# --- the trust boundary -------------------------------------------------------


async def test_a_request_with_no_key_is_refused(started_run: Run) -> None:
    with pytest.raises(HTTPException) as caught:
        await _complete(started_run.id, key=None)
    assert caught.value.status_code == 404


async def test_a_request_with_the_wrong_key_is_refused(started_run: Run) -> None:
    with pytest.raises(HTTPException) as caught:
        await _complete(started_run.id, key="not-the-secret")
    assert caught.value.status_code == 404


async def test_an_unset_secret_refuses_everything_rather_than_accepting_anything(
    started_run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fails closed. An empty secret must not mean "no check needed"."""
    monkeypatch.setattr(
        internal_module, "config", dataclasses.replace(config, internal_api_secret="")
    )
    with pytest.raises(HTTPException) as caught:
        await _complete(started_run.id, key="")
    assert caught.value.status_code == 404


async def test_an_unknown_run_is_a_404_not_a_different_error(pool: None) -> None:
    """Same status as a bad key, so a caller holding the secret still cannot
    enumerate which run ids exist by watching the response change."""
    with pytest.raises(HTTPException) as caught:
        await _complete("does-not-exist")
    assert caught.value.status_code == 404


# --- recording the call -------------------------------------------------------


async def test_a_completion_resolves_the_in_flight_row_rather_than_adding_one(
    started_run: Run, db: asyncpg.Connection
) -> None:
    assert (await _complete(started_run.id))["ok"] is True

    await db.execute("select set_config('role', 'postgres', true)")
    rows = await db.fetch(
        "select contact_name, status, disposition, transcript, duration_seconds"
        " from public.call_outcomes where run_id = $1 order by contact_name",
        started_run.id,
    )
    assert len(rows) == 2, "a completion must not create a second row for the same contact"
    settled = next(r for r in rows if r["contact_name"] == CONTACT)
    assert settled["status"] == "COMPLETED"
    assert settled["disposition"] != "in_flight"
    assert settled["transcript"] is not None
    assert settled["duration_seconds"] == 42


async def test_the_completion_is_triaged_not_stored_raw(
    started_run: Run, db: asyncpg.Connection
) -> None:
    """A do-not-call request has to escalate, whatever the worker called it."""
    await _complete(
        started_run.id, extracted={"do_not_call": True, "sentiment": "negative"}
    )

    await db.execute("select set_config('role', 'postgres', true)")
    disposition = await db.fetchval(
        "select disposition from public.call_outcomes where run_id = $1 and contact_name = $2",
        started_run.id,
        CONTACT,
    )
    assert disposition == "escalated"


async def test_a_non_terminal_status_is_rejected(started_run: Run) -> None:
    """A completion callback means the call is over. Accepting a status that
    triages back to in-flight would leave the row unsettled forever and stop the
    run ever closing."""
    with pytest.raises(HTTPException) as caught:
        await _complete(started_run.id, status="RINGING", extracted={})
    assert caught.value.status_code == 400
    assert "not a terminal call status" in caught.value.detail


async def test_replaying_the_same_completion_is_idempotent(
    started_run: Run, db: asyncpg.Connection
) -> None:
    """The worker retries after a dropped response; that must update the row,
    not add a duplicate (CLAUDE.md non-negotiable #6)."""
    for _ in range(3):
        await _complete(started_run.id)

    await db.execute("select set_config('role', 'postgres', true)")
    count = await db.fetchval(
        "select count(*) from public.call_outcomes where run_id = $1 and contact_name = $2",
        started_run.id,
        CONTACT,
    )
    assert count == 1


# --- closing the run ----------------------------------------------------------


async def test_the_run_stays_open_while_another_contact_is_still_talking(
    started_run: Run, db: asyncpg.Connection
) -> None:
    """The bug this guards: origination returns when a call is *answered*, so
    the run's background task finishes long before the conversations do. Closing
    the run then would show it completed with rows reading "In conversation…"."""
    result = await _complete(started_run.id)
    assert result["run_closed"] is False

    await db.execute("select set_config('role', 'postgres', true)")
    row = await db.fetchrow(
        "select status, finished_at from public.runs where id = $1", started_run.id
    )
    assert row["status"] == "running"
    assert row["finished_at"] is None


async def test_the_last_contact_to_settle_closes_the_run(
    started_run: Run, db: asyncpg.Connection
) -> None:
    first = await _complete(started_run.id)
    second = await _complete(
        started_run.id, contact_name=OTHER_CONTACT, phone_masked=OTHER_MASKED
    )

    assert first["run_closed"] is False
    assert second["run_closed"] is True

    await db.execute("select set_config('role', 'postgres', true)")
    row = await db.fetchrow(
        "select status, finished_at from public.runs where id = $1", started_run.id
    )
    assert row["status"] == "completed"
    assert row["finished_at"] is not None


async def test_only_one_callback_ever_reports_closing_the_run(started_run: Run) -> None:
    """Two workers finishing at once must not both close it - the guard is the
    `finished_at is null` condition inside a single statement."""
    await _complete(started_run.id)
    closings = [
        (
            await _complete(
                started_run.id, contact_name=OTHER_CONTACT, phone_masked=OTHER_MASKED
            )
        )["run_closed"]
        for _ in range(3)
    ]

    assert closings.count(True) == 1


# --- escalations, which only a real conversation can raise --------------------


async def test_a_call_needing_a_person_raises_an_escalation(
    started_run: Run, db: asyncpg.Connection
) -> None:
    """The only place this can happen for a call that actually connected.

    `run_one()` returns while the call is still in flight, so the disposition it
    reports is never a needs-a-person one - the escalation check beside the
    run's own progress write can only ever fire for a contact that failed to
    dial. Without this, triage would decide someone has to call back and the
    "Needs a person" worklist would stay empty forever.
    """
    await _complete(
        started_run.id,
        transcript="Contact: Please have a human call me back.",
        extracted={"wants_human_callback": True, "sentiment": "neutral"},
    )

    escalations = await db.fetch(
        """
        select e.status from public.escalations e
        join public.call_outcomes o on o.id = e.call_outcome_id
        where o.run_id = $1 and o.contact_name = $2
        """,
        started_run.id,
        CONTACT,
    )
    assert len(escalations) == 1


async def test_a_clean_call_raises_no_escalation(
    started_run: Run, db: asyncpg.Connection
) -> None:
    """Clean calls close themselves - that is the product's whole claim.

    "Clean" now includes *complete*: the fixture agent requires `destination`, so
    a call that never established it escalates however well it went (ADR-5). That
    is the intended behaviour, and it means this test has to answer the question
    the agent was sent to ask.
    """
    await _complete(
        started_run.id,
        transcript="Contact: Yes, Dubai in December, thanks.",
        extracted={"outcome": "interested", "sentiment": "positive"},
        collected={"destination": "Dubai"},
    )

    count = await db.fetchval(
        """
        select count(*) from public.escalations e
        join public.call_outcomes o on o.id = e.call_outcome_id
        where o.run_id = $1
        """,
        started_run.id,
    )
    assert count == 0


# --- the two writers racing ---------------------------------------------------


async def test_a_settled_row_is_not_dragged_back_to_in_flight(
    started_run: Run, db: asyncpg.Connection
) -> None:
    """A short call finishes before origination's own IN_FLIGHT write lands.

    Both writers upsert the same key. Without the guard, the late in-flight
    write overwrites the terminal row - discarding the transcript and leaving
    `finish_if_all_settled` permanently unable to close the run.
    """
    await _complete(started_run.id, transcript="Agent: Hello. Contact: Yes.")

    async with database.as_user(str(started_run.auth_user_id)) as conn:
        await runs_repo.append_outcome(
            conn,
            run_id=started_run.id,
            org_id=started_run.org_id,
            outcome={
                "contact_name": CONTACT,
                "phone_masked": MASKED,
                "status": "IN_PROGRESS",
                "sentiment": "unknown",
                "disposition": "in_flight",
                "disposition_reason": "In conversation…",
            },
        )

    row = await db.fetchrow(
        "select disposition, transcript from public.call_outcomes"
        " where run_id = $1 and contact_name = $2",
        started_run.id,
        CONTACT,
    )
    assert row["disposition"] != "in_flight"
    assert row["transcript"]


async def test_the_late_write_still_returns_the_rows_id(started_run: Run) -> None:
    """The caller needs it to link an escalation, even when its update was
    suppressed."""
    await _complete(started_run.id)

    async with database.as_user(str(started_run.auth_user_id)) as conn:
        outcome_id = await runs_repo.append_outcome(
            conn,
            run_id=started_run.id,
            org_id=started_run.org_id,
            outcome={
                "contact_name": CONTACT,
                "phone_masked": MASKED,
                "status": "IN_PROGRESS",
                "sentiment": "unknown",
                "disposition": "in_flight",
            },
        )

    assert outcome_id is not None


# --- a worker that never reports ----------------------------------------------


async def test_a_call_whose_worker_died_stops_holding_the_run_open(
    started_run: Run, db: asyncpg.Connection
) -> None:
    """Every call carries a hard carrier-enforced ceiling, so an in-flight row
    older than that cannot still be live. Left alone it blocks the run forever."""
    await db.execute(
        "update public.call_outcomes set created_at = now() - interval '2 hours'"
        " where run_id = $1 and contact_name = $2",
        started_run.id,
        OTHER_CONTACT,
    )

    result = await _complete(started_run.id)

    assert result["run_closed"] is True
    abandoned = await db.fetchrow(
        "select status, disposition, error from public.call_outcomes"
        " where run_id = $1 and contact_name = $2",
        started_run.id,
        OTHER_CONTACT,
    )
    # Recorded as a real failure, never as a completed call - nobody knows what
    # was said (CLAUDE.md non-negotiable #9).
    assert abandoned["disposition"] == "unreachable"
    assert abandoned["status"] == "FAILED"
    assert abandoned["error"] == "timed_out"


async def test_a_call_still_within_its_ceiling_is_left_alone(
    started_run: Run, db: asyncpg.Connection
) -> None:
    """The sweep must not cut off a conversation that is simply still going."""
    result = await _complete(started_run.id)

    assert result["run_closed"] is False
    still_live = await db.fetchval(
        "select disposition from public.call_outcomes"
        " where run_id = $1 and contact_name = $2",
        started_run.id,
        OTHER_CONTACT,
    )
    assert still_live == "in_flight"
