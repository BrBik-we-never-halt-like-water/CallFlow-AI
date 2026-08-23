"""Stopping a run, and honouring a do-not-call, against the real database.

These are the two paths whose value is entirely in the parts a unit test cannot
reach. `test_orchestrator.py` already proves the dialler skips contacts once its
predicate says stop; what it cannot prove is that the flag survives the trip
through Postgres, that the run then closes as `stopped` rather than `completed`,
or that a suppression written from a stored hash is the same hash the next run's
dial gate will check against. Each of those is a join between two pieces that
were written separately, and each is where this would actually break.

Calls the route functions directly rather than through `TestClient`, following
`test_internal_completion.py` - a sync test client runs the app in its own event
loop, fighting the one holding the asyncpg connection these assertions read back
through.

Skipped when DATABASE_URL is unset. **Point it at a local Postgres, never at a
shared project** - these create and delete `auth.users` rows
(`tests/local_postgres/README.md`).
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.api.v1.routes import internal as internal_module
from app.api.v1.routes.internal import CallCompletion, complete_call
from app.api.v1.routes.runs import stop_run
from app.auth.dependencies import CurrentUser
from app.core.config import config
from app.database import database
from app.database.models import OrgRole
from app.database.repositories import runs as runs_repo
from app.database.repositories import suppressions as suppressions_repo
from app.domain.run_state import RunStatus, is_stopping
from app.domain.safety import check_dial_allowed, phone_hash
from app.services import run_control

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not config.database_url, reason="DATABASE_URL is not configured"),
]

SECRET = "stop-test-secret"

#: A reserved fictional number (CLAUDE.md), so nothing here could reach a person
#: even if a test somehow placed a call.
OPT_OUT_PHONE = "+15555550142"
OPT_OUT_CONTACT = "Priya"
OPT_OUT_MASKED = "+15******142"


@pytest.fixture(autouse=True)
def _configured_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        internal_module, "config", dataclasses.replace(config, internal_api_secret=SECRET)
    )


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[None]:
    await database.connect()
    try:
        yield
    finally:
        await database.disconnect()


@pytest_asyncio.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(config.database_url, timeout=30)
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


class Tenant:
    def __init__(
        self, run_id: str, org_id: uuid.UUID, user_id: uuid.UUID, auth_user_id: uuid.UUID
    ) -> None:
        self.run_id = run_id
        self.org_id = org_id
        self.user_id = user_id
        self.auth_user_id = auth_user_id

    def as_current_user(self) -> CurrentUser:
        """The route dependency's value, built directly.

        The routes take `CurrentUser` and nothing else from the request, so this
        is the whole of what authentication would have produced - and building
        it here keeps the test on the handler rather than on FastAPI.
        """
        return CurrentUser(
            id=self.user_id,
            auth_user_id=str(self.auth_user_id),
            email="stop-test@brbik.com",
            name="Stop Test",
            avatar_url=None,
            org_id=self.org_id,
            org_name="Stop Test Org",
            org_slug="stop-test-org",
            org_logo_url=None,
            org_onboarded_at=None,
            org_plan_id="free",
            role=OrgRole.OWNER,
        )


@pytest_asyncio.fixture
async def running_run(db: asyncpg.Connection, pool: None) -> AsyncIterator[Tenant]:
    """A real run: three contacts, one in flight, two not yet dialled."""
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
        f"stop-{auth_user_id.hex[:8]}@brbik.com",
        json.dumps({"full_name": "Stop Test"}),
    )
    row = await db.fetchrow(
        """
        select u.id as user_id, m.org_id from public.users u
        join public.memberships m on m.user_id = u.id
        where u.auth_user_id = $1
        """,
        auth_user_id,
    )
    agent_id = await db.fetchval(
        """
        insert into public.voice_agents
            (org_id, created_by, name, kind, stt_provider, tts_provider,
             llm_provider, llm_model, collect_fields)
        values ($1, $2, 'Stop test agent', 'custom', 'deepgram', 'elevenlabs',
                'openrouter', 'openai/gpt-4o', '[]'::jsonb)
        returning id
        """,
        row["org_id"],
        row["user_id"],
    )

    run_id = uuid.uuid4().hex[:12]
    await db.execute(
        """
        insert into public.runs (id, org_id, voice_agent_id, total, status, started_by)
        values ($1, $2, $3, 3, 'running', $4)
        """,
        run_id,
        row["org_id"],
        agent_id,
        row["user_id"],
    )
    # One contact already talking. The other two have no row yet, which is what
    # "not dialled" looks like while a run is in progress.
    await db.execute(
        """
        insert into public.call_outcomes
            (run_id, org_id, contact_name, phone_masked, status, disposition,
             disposition_reason, sentiment, phone_hash)
        values ($1, $2, $3, $4, 'IN_PROGRESS', 'in_flight', 'In conversation…',
                'unknown', $5)
        """,
        run_id,
        row["org_id"],
        OPT_OUT_CONTACT,
        OPT_OUT_MASKED,
        phone_hash(OPT_OUT_PHONE),
    )

    try:
        yield Tenant(run_id, row["org_id"], row["user_id"], auth_user_id)
    finally:
        await db.execute("select set_config('role', 'postgres', true)")
        await db.execute("delete from auth.users where id = $1", auth_user_id)
        await db.execute(
            """
            delete from public.organisations o
            where not exists (select 1 from public.memberships m where m.org_id = o.id)
            """
        )


# --- stopping a run ------------------------------------------------------


async def test_stopping_records_the_request_without_ending_the_run(
    db: asyncpg.Connection, running_run: Tenant
) -> None:
    """A stop is a request, not a status flip. Ending the run here would show it
    finished beside a row still reading "In conversation…"."""
    result = await stop_run(running_run.run_id, running_run.as_current_user())

    assert result.stopping is True
    assert result.status == "running"
    # Three contacts; one is already in conversation, and a stop deliberately
    # lets that call finish. So the stop spares the other two, not all three -
    # counting the live call as un-dialled would overstate what Stop prevents.
    assert result.not_yet_dialled == 2

    row = await db.fetchrow(
        "select status, stop_requested_at, stopped_by from public.runs where id = $1",
        running_run.run_id,
    )
    assert row["status"] == "running"
    assert row["stop_requested_at"] is not None
    assert row["stopped_by"] == running_run.user_id
    assert is_stopping(RunStatus(row["status"]), row["stop_requested_at"])


async def test_the_dialler_sees_the_stop_through_the_database(
    running_run: Tenant,
) -> None:
    """The join a unit test cannot make. The dispatcher runs on whichever worker
    served the start request and the stop lands on another, so the flag is only
    useful if it survives the trip through Postgres - this reads it back exactly
    as `StopSignal` does mid-run."""
    signal = run_control.StopSignal(running_run.run_id, str(running_run.auth_user_id))
    assert await signal.is_stopped() is False

    await stop_run(running_run.run_id, running_run.as_current_user())

    # A fresh signal, because the live one caches for a couple of seconds by
    # design - that latency is the deliberate trade, not a bug to assert around.
    assert await run_control.StopSignal(
        running_run.run_id, str(running_run.auth_user_id)
    ).is_stopped() is True


async def test_stopping_twice_keeps_the_first_decision(
    db: asyncpg.Connection, running_run: Tenant
) -> None:
    """Idempotent (CLAUDE.md #6). The second press must not move the record of
    when somebody actually decided."""
    await stop_run(running_run.run_id, running_run.as_current_user())
    first = await db.fetchval(
        "select stop_requested_at from public.runs where id = $1", running_run.run_id
    )

    await stop_run(running_run.run_id, running_run.as_current_user())
    second = await db.fetchval(
        "select stop_requested_at from public.runs where id = $1", running_run.run_id
    )
    assert first == second


async def test_a_stopped_run_closes_as_stopped_not_completed(
    db: asyncpg.Connection, running_run: Tenant
) -> None:
    """The assertion this whole feature exists to make true.

    A halted run settles every contact it was ever going to settle, which is the
    same condition a normal run closes on - so without the stop flag it would
    report "Completed" for a list it never finished.
    """
    await stop_run(running_run.run_id, running_run.as_current_user())

    # The dialler writes these for the two contacts the stop reached first.
    for i in range(2):
        await db.execute(
            """
            insert into public.call_outcomes
                (run_id, org_id, contact_name, phone_masked, status, disposition,
                 disposition_reason, sentiment, error)
            values ($1, $2, $3, '', 'BLOCKED', 'skipped',
                    'The run was stopped before this contact was dialled.',
                    'unknown', 'run_stopped')
            """,
            running_run.run_id,
            running_run.org_id,
            f"Not dialled {i}",
        )
    # The live call finishes naturally, as a stop deliberately allows.
    await complete_call(
        running_run.run_id,
        CallCompletion(
            contact_name=OPT_OUT_CONTACT,
            phone_masked=OPT_OUT_MASKED,
            status="COMPLETED",
            transcript="Agent: Hello. Contact: All good, thanks.",
            extracted={"sentiment": "positive"},
            duration_seconds=30,
        ),
    )

    row = await db.fetchrow(
        "select status, finished_at from public.runs where id = $1", running_run.run_id
    )
    assert row["status"] == RunStatus.STOPPED.value
    assert row["finished_at"] is not None


async def test_an_untouched_run_still_closes_as_completed(
    db: asyncpg.Connection, running_run: Tenant
) -> None:
    """The other half of the same branch - a run nobody stopped is unaffected."""
    for i in range(2):
        await db.execute(
            """
            insert into public.call_outcomes
                (run_id, org_id, contact_name, phone_masked, status, disposition,
                 disposition_reason, sentiment)
            values ($1, $2, $3, '', 'COMPLETED', 'auto_closed', 'Clean.', 'positive')
            """,
            running_run.run_id,
            running_run.org_id,
            f"Contact {i}",
        )
    await complete_call(
        running_run.run_id,
        CallCompletion(
            contact_name=OPT_OUT_CONTACT,
            phone_masked=OPT_OUT_MASKED,
            status="COMPLETED",
            extracted={"sentiment": "positive"},
            duration_seconds=30,
        ),
    )

    status = await db.fetchval(
        "select status from public.runs where id = $1", running_run.run_id
    )
    assert status == RunStatus.COMPLETED.value


async def test_stopping_a_finished_run_is_refused_rather_than_faked(
    db: asyncpg.Connection, running_run: Tenant
) -> None:
    """409, not 200. Answering success would make the interface report "Run
    stopped" for something that stopped itself ten minutes ago."""
    await db.execute(
        "update public.runs set status = 'completed', finished_at = now() where id = $1",
        running_run.run_id,
    )

    with pytest.raises(HTTPException) as caught:
        await stop_run(running_run.run_id, running_run.as_current_user())

    assert caught.value.status_code == 409
    assert "already finished" in str(caught.value.detail)


async def test_stopping_an_unknown_run_is_a_404(running_run: Tenant) -> None:
    """404 rather than a refusal that would confirm which run ids exist."""
    with pytest.raises(HTTPException) as caught:
        await stop_run("no-such-run", running_run.as_current_user())
    assert caught.value.status_code == 404


async def test_the_reconciler_closes_a_run_whose_dispatcher_died(
    db: asyncpg.Connection, running_run: Tenant
) -> None:
    """The stranded-run case. Nothing will ever call back for these rows, so
    without the sweep the run reads "Running" permanently."""
    # Age everything past the ceiling: this is what a dead dispatcher looks like.
    await db.execute(
        """
        update public.call_outcomes
           set created_at = now() - interval '10 hours'
         where run_id = $1
        """,
        running_run.run_id,
    )
    await db.execute(
        "update public.runs set started_at = now() - interval '10 hours' where id = $1",
        running_run.run_id,
    )

    stale = await runs_repo.list_open_runs(db, quiet_for_seconds=60)
    assert running_run.run_id in {r["id"] for r in stale}

    closed = await runs_repo.finish_if_all_settled(
        db, running_run.run_id, stale_after_seconds=60
    )
    assert closed is True

    row = await db.fetchrow(
        "select status, finished_at from public.runs where id = $1", running_run.run_id
    )
    assert row["status"] == RunStatus.COMPLETED.value
    assert row["finished_at"] is not None

    # The in-flight call that never reported is now a real failure *and* reaches
    # the queue - it is the case that most deserves a person, because somebody
    # had a conversation and nobody knows what was said.
    outcome = await db.fetchrow(
        "select id, disposition, error from public.call_outcomes where run_id = $1 and contact_name = $2",
        running_run.run_id,
        OPT_OUT_CONTACT,
    )
    assert outcome["disposition"] == "unreachable"
    assert outcome["error"] == "timed_out"
    assert await db.fetchval(
        "select exists(select 1 from public.escalations where call_outcome_id = $1)",
        outcome["id"],
    )

    # The two never-dialled contacts are `skipped`, not `unreachable` - they were
    # never tried, and marking them needs-a-person would bury the real one above.
    never = await db.fetch(
        "select disposition, error from public.call_outcomes where run_id = $1 and error = 'never_dialled'",
        running_run.run_id,
    )
    assert len(never) == 2
    assert {r["disposition"] for r in never} == {"skipped"}


# --- honouring a do-not-call ---------------------------------------------


async def test_a_do_not_call_suppresses_the_number_for_the_next_run(
    db: asyncpg.Connection, running_run: Tenant
) -> None:
    """The full promise, end to end: the contact says it, the callback records
    it, and the dial gate refuses them next time.

    The last assertion is the one that matters. A suppression row that the gate
    does not match is decoration, and the two halves resolve the hash in
    different processes from different inputs - the dialler from a real number,
    this from a stored column.
    """
    await complete_call(
        running_run.run_id,
        CallCompletion(
            contact_name=OPT_OUT_CONTACT,
            phone_masked=OPT_OUT_MASKED,
            status="COMPLETED",
            transcript="Contact: Take me off your list.",
            extracted={"do_not_call": True, "sentiment": "negative"},
            duration_seconds=12,
        ),
    )

    stored = await db.fetchrow(
        "select phone_hash, source, phone_e164, suppressed_by, reason "
        "from public.suppressions where org_id = $1",
        running_run.org_id,
    )
    assert stored is not None
    assert stored["source"] == "opt_out"
    # Written from a hash, so no new surface holds a dialable number.
    assert stored["phone_e164"] is None
    assert stored["suppressed_by"] is None
    assert OPT_OUT_CONTACT in stored["reason"]

    # The join that matters: the gate the next run runs must refuse this number.
    digest = phone_hash(OPT_OUT_PHONE)
    assert stored["phone_hash"] == digest
    assert await suppressions_repo.is_suppressed(db, running_run.org_id, digest)
    gate = check_dial_allowed(OPT_OUT_PHONE, is_suppressed=True)
    assert gate.allowed is False
    assert "opted out" in gate.reason

    # And it escalates, because somebody should still know it happened.
    assert await db.fetchval(
        "select exists(select 1 from public.escalations e "
        "join public.call_outcomes c on c.id = e.call_outcome_id "
        "where c.run_id = $1)",
        running_run.run_id,
    )


async def test_a_clean_call_suppresses_nobody(
    db: asyncpg.Connection, running_run: Tenant
) -> None:
    await complete_call(
        running_run.run_id,
        CallCompletion(
            contact_name=OPT_OUT_CONTACT,
            phone_masked=OPT_OUT_MASKED,
            status="COMPLETED",
            extracted={"sentiment": "positive"},
            duration_seconds=30,
        ),
    )
    assert (
        await db.fetchval(
            "select count(*) from public.suppressions where org_id = $1",
            running_run.org_id,
        )
        == 0
    )


async def test_replaying_an_opt_out_suppresses_once(
    db: asyncpg.Connection, running_run: Tenant
) -> None:
    """The worker retries its callback on a dropped response, and a second
    suppression for the same number must not be an integrity error."""
    payload = CallCompletion(
        contact_name=OPT_OUT_CONTACT,
        phone_masked=OPT_OUT_MASKED,
        status="COMPLETED",
        extracted={"do_not_call": True},
        duration_seconds=12,
    )
    await complete_call(running_run.run_id, payload)
    await complete_call(running_run.run_id, payload)

    assert (
        await db.fetchval(
            "select count(*) from public.suppressions where org_id = $1",
            running_run.org_id,
        )
        == 1
    )


async def test_an_opt_out_on_a_call_with_no_stored_hash_is_survivable(
    db: asyncpg.Connection, running_run: Tenant
) -> None:
    """Rows dialled before `f3c7b21a9d04` have no suppression key, and there is
    no way back to a number from a masked one. The transcript still has to land -
    losing a customer's call record because an opt-out could not be enforced
    would be the wrong thing to protect."""
    await db.execute(
        "update public.call_outcomes set phone_hash = null where run_id = $1",
        running_run.run_id,
    )

    await complete_call(
        running_run.run_id,
        CallCompletion(
            contact_name=OPT_OUT_CONTACT,
            phone_masked=OPT_OUT_MASKED,
            status="COMPLETED",
            transcript="Contact: Take me off your list.",
            extracted={"do_not_call": True},
            duration_seconds=12,
        ),
    )

    assert (
        await db.fetchval(
            "select count(*) from public.suppressions where org_id = $1",
            running_run.org_id,
        )
        == 0
    )
    # The call itself was still recorded, and still escalated.
    assert await db.fetchval(
        "select transcript is not null from public.call_outcomes "
        "where run_id = $1 and contact_name = $2",
        running_run.run_id,
        OPT_OUT_CONTACT,
    )
