"""The CALL-E webhook receiver, against the real database.

Exercises the actual `database.anonymous()` -> `lookup_run_owner_for_webhook`
-> `database.as_user()` -> `append_outcome` path this route uses - the same
reason `test_rls_isolation.py` insists on a real Postgres connection rather
than mocking anything: a SECURITY DEFINER function or an RLS policy that
looks right on paper is the expensive bug to ship.

Skipped when DATABASE_URL is unset, so the suite still runs offline.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from app.api.v1.routes import webhooks as webhooks_module
from app.api.v1.routes.webhooks import CalleWebhookPayload, calle_webhook
from app.core.config import config
from app.database import database
from app.database.repositories import runs as runs_repo
from app.domain.campaigns import TRAVEL_DISCOVERY

pytestmark = pytest.mark.skipif(not config.database_url, reason="DATABASE_URL is not configured")

WEBHOOK_SECRET = "test-webhook-secret-abc123"


class FakeRequest:
    """Just enough of `fastapi.Request` for `request.headers.get(...)`."""

    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}


class Tenant:
    def __init__(self, auth_user_id: uuid.UUID, user_id: uuid.UUID, org_id: uuid.UUID) -> None:
        self.auth_user_id = auth_user_id
        self.user_id = user_id
        self.org_id = org_id


async def _create_tenant(conn: asyncpg.Connection, label: str) -> Tenant:
    """Mirrors `test_rls_isolation.py`'s own helper - a real tenant through the
    real signup trigger, not a fabricated row, so RLS is genuinely exercised."""
    auth_user_id = uuid.uuid4()
    await conn.execute(
        """
        insert into auth.users (id, instance_id, aud, role, email, encrypted_password,
                                email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
                                created_at, updated_at)
        values ($1, '00000000-0000-0000-0000-000000000000', 'authenticated',
                'authenticated', $2, crypt('x', gen_salt('bf')), now(),
                '{"provider":"email"}', $3::jsonb, now(), now())
        """,
        auth_user_id,
        f"webhook-{label}-{auth_user_id.hex[:8]}@brbik.com",
        json.dumps({"full_name": f"Webhook {label}"}),
    )
    row = await conn.fetchrow(
        """
        select u.id as user_id, m.org_id
        from public.users u
        join public.memberships m on m.user_id = u.id
        where u.auth_user_id = $1
        """,
        auth_user_id,
    )
    assert row is not None, "signup trigger did not create a user and organisation"
    return Tenant(auth_user_id, row["user_id"], row["org_id"])


@pytest_asyncio.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(config.database_url, timeout=30)
    try:
        yield conn
    finally:
        await conn.execute("select set_config('role', 'postgres', true)")
        await conn.close()


@pytest_asyncio.fixture
async def tenant(db: asyncpg.Connection) -> AsyncIterator[Tenant]:
    t = await _create_tenant(db, "a")
    try:
        yield t
    finally:
        await db.execute("select set_config('role', 'postgres', true)")
        await db.execute("delete from auth.users where id = $1", t.auth_user_id)
        await db.execute(
            """
            delete from public.organisations o
            where not exists (select 1 from public.memberships m where m.org_id = o.id)
            """
        )


@pytest_asyncio.fixture(autouse=True)
async def _app_database_pool() -> AsyncIterator[None]:
    """The route under test goes through the app's own pooled `database`
    singleton (`anonymous()`/`as_user()`), not the raw `asyncpg.connect()`
    the other RLS tests use directly - it has to be connected for real."""
    await database.connect()
    yield
    await database.disconnect()


@pytest.fixture(autouse=True)
def _configured_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        webhooks_module, "config", dataclasses.replace(config, webhook_secret=WEBHOOK_SECRET)
    )


def _payload(*, run_id: str, campaign_id: str, contact_name: str, phone: str) -> CalleWebhookPayload:
    return CalleWebhookPayload(
        event="call.completed",
        data={
            "id": "call_abc123",
            "status": "completed",
            "metadata": {
                "run_id": run_id,
                "campaign_id": campaign_id,
                "campaign_name": "Travel enquiry follow-up",
                "contact_name": contact_name,
            },
            "task_completed": True,
            "completion_confidence": {"score": 0.92, "label": "high"},
            "evidence": ["Contact confirmed travel dates and budget."],
            "recipients": [
                {
                    "attempts": [
                        {
                            "phone": phone,
                            "status": "no_answer",
                            "started_at": "2026-08-09T09:55:00Z",
                        },
                        {
                            "phone": phone,
                            "status": "completed",
                            "started_at": "2026-08-09T10:00:00Z",
                            "transcript_turns": [
                                {"offset_seconds": 0, "speaker": "bot", "text": "Hello!"},
                                {"offset_seconds": 3, "speaker": "user", "text": "Hi there."},
                            ],
                        },
                    ]
                }
            ],
            "structured_result": {
                "outcome": "interested",
                "sentiment": "positive",
                "frustration_signals": False,
                "summary": "Wants a Bali package.",
            },
        },
    )


async def test_wrong_secret_is_rejected_with_404_not_401() -> None:
    from fastapi import HTTPException

    payload = _payload(run_id="run_x", campaign_id="travel-discovery", contact_name="A", phone="+15555550100")
    with pytest.raises(HTTPException) as exc_info:
        await calle_webhook("not-the-real-secret", payload, FakeRequest())
    assert exc_info.value.status_code == 404


async def test_unconfigured_secret_rejects_every_request(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException

    monkeypatch.setattr(webhooks_module, "config", dataclasses.replace(config, webhook_secret=""))
    payload = _payload(run_id="run_x", campaign_id="travel-discovery", contact_name="A", phone="+15555550100")
    with pytest.raises(HTTPException) as exc_info:
        await calle_webhook("", payload, FakeRequest())
    assert exc_info.value.status_code == 404


async def test_unknown_run_id_is_acknowledged_without_error() -> None:
    payload = _payload(
        run_id="run_does_not_exist", campaign_id="travel-discovery", contact_name="A", phone="+15555550100"
    )
    result = await calle_webhook(WEBHOOK_SECRET, payload, FakeRequest())
    assert result == {"ok": True}


async def test_missing_run_id_in_metadata_is_acknowledged_without_error() -> None:
    payload = CalleWebhookPayload(
        event="call.completed",
        data={"id": "call_abc123", "status": "completed", "metadata": {"campaign_id": "travel-discovery"}},
    )
    result = await calle_webhook(WEBHOOK_SECRET, payload, FakeRequest())
    assert result == {"ok": True}


async def test_happy_path_persists_the_same_outcome_polling_would_have(tenant: Tenant) -> None:
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    async with database.as_user(str(tenant.auth_user_id)) as conn:
        await runs_repo.create_run(
            conn,
            run_id=run_id,
            org_id=tenant.org_id,
            campaign_id=TRAVEL_DISCOVERY.id,
            total=1,
            started_by=tenant.user_id,
        )

    payload = _payload(
        run_id=run_id, campaign_id=TRAVEL_DISCOVERY.id, contact_name="Aditi", phone="+15555550100"
    )
    result = await calle_webhook(
        WEBHOOK_SECRET, payload, FakeRequest({"CALL-E-Event-Id": "evt_1"})
    )
    assert result == {"ok": True}

    async with database.as_user(str(tenant.auth_user_id)) as conn:
        outcomes = await runs_repo.list_outcomes(conn, run_id)

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome["contact_name"] == "Aditi"
    assert "5555550" not in outcome["phone_masked"]
    assert outcome["provider_call_id"] == "call_abc123"
    assert outcome["disposition"] == "auto_closed"
    assert outcome["extracted"]["outcome"] == "interested"
    assert "Hello!" in (outcome["transcript"] or "")
    assert outcome["task_completed"] is True
    assert outcome["completion_confidence_score"] == pytest.approx(0.92)
    assert outcome["completion_confidence_label"] == "high"
    assert outcome["evidence"] == ["Contact confirmed travel dates and budget."]
    assert [a["status"] for a in outcome["attempts"]] == ["no_answer", "completed"]


async def test_webhook_write_uses_the_runs_own_starter_not_a_different_org(
    tenant: Tenant, db: asyncpg.Connection
) -> None:
    """A second tenant must never be able to make its own auth_user_id line up
    with someone else's run - the lookup resolves strictly by run_id, and the
    subsequent write is scoped to whichever org that run actually belongs to."""
    other = await _create_tenant(db, "b")
    try:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        async with database.as_user(str(tenant.auth_user_id)) as conn:
            await runs_repo.create_run(
                conn,
                run_id=run_id,
                org_id=tenant.org_id,
                campaign_id=TRAVEL_DISCOVERY.id,
                total=1,
                started_by=tenant.user_id,
            )

        payload = _payload(
            run_id=run_id, campaign_id=TRAVEL_DISCOVERY.id, contact_name="Aditi", phone="+15555550100"
        )
        await calle_webhook(WEBHOOK_SECRET, payload, FakeRequest())

        async with database.as_user(str(other.auth_user_id)) as conn:
            visible_to_other = await runs_repo.list_outcomes(conn, run_id)
        assert visible_to_other == [], "the other tenant can see this run's outcome"

        async with database.as_user(str(tenant.auth_user_id)) as conn:
            visible_to_owner = await runs_repo.list_outcomes(conn, run_id)
        assert len(visible_to_owner) == 1
    finally:
        await db.execute("select set_config('role', 'postgres', true)")
        await db.execute("delete from auth.users where id = $1", other.auth_user_id)
        await db.execute(
            """
            delete from public.organisations o
            where not exists (select 1 from public.memberships m where m.org_id = o.id)
            """
        )
