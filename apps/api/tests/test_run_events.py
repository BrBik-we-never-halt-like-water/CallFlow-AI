"""GET /api/v1/runs/{run_id}/calls/{provider_call_id}/events - CALL-E's
developer event log, on demand, against the real database (a run/outcome
must genuinely belong to the caller's own org, the same RLS-relevant
question every other real-database test in this suite insists on verifying
directly rather than assuming from a policy that looks right on paper).
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

from app.api.v1.routes import runs as runs_module
from app.api.v1.routes.runs import get_call_events
from app.auth.dependencies import CurrentUser
from app.core.config import config
from app.database import database
from app.database.models import OrgRole
from app.database.repositories import runs as runs_repo
from app.domain.campaigns import TRAVEL_DISCOVERY
from app.integrations.voice.engine import EngineAPIError

pytestmark = pytest.mark.skipif(not config.database_url, reason="DATABASE_URL is not configured")

PROVIDER_CALL_ID = "call_abc123"


class Tenant:
    def __init__(self, auth_user_id: uuid.UUID, user_id: uuid.UUID, org_id: uuid.UUID) -> None:
        self.auth_user_id = auth_user_id
        self.user_id = user_id
        self.org_id = org_id


async def _create_tenant(conn: asyncpg.Connection, label: str) -> Tenant:
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
        f"events-{label}-{auth_user_id.hex[:8]}@brbik.com",
        json.dumps({"full_name": f"Events {label}"}),
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
    assert row is not None
    return Tenant(auth_user_id, row["user_id"], row["org_id"])


def _current_user(tenant: Tenant) -> CurrentUser:
    return CurrentUser(
        id=tenant.user_id,
        auth_user_id=str(tenant.auth_user_id),
        email="owner@brbik.com",
        name="Owner",
        avatar_url=None,
        org_id=tenant.org_id,
        org_name="Test org",
        org_slug="test-org",
        org_logo_url=None,
        org_onboarded_at=None,
        org_plan_id="free",
        role=OrgRole.OWNER,
    )


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
    await database.connect()
    yield
    await database.disconnect()


@pytest.fixture(autouse=True)
def _api_key_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runs_module, "config", dataclasses.replace(config, api_key="sk_test_dummy"))


class FakeEventsGateway:
    """Stands in for `EngineGateway` - the route constructs one directly, so
    this patches the class the module imported, the same way other tests in
    this suite patch a module-level `config` binding."""

    last_call_id: str | None = None
    last_cursor: str | None = None
    raise_error: bool = False

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    def list_events(self, call_id: str, *, cursor: str | None = None, limit: int | None = None) -> dict[str, Any]:
        FakeEventsGateway.last_call_id = call_id
        FakeEventsGateway.last_cursor = cursor
        if FakeEventsGateway.raise_error:
            raise EngineAPIError(code="provider_unavailable", message="down", status_code=503)
        return {
            "object": "list",
            "data": [
                {
                    "id": "evt_1",
                    "type": "call.queued",
                    "call_id": call_id,
                    "created_at": "2026-08-09T10:00:00Z",
                    "level": "info",
                    "status": "queued",
                    "message": "Call queued.",
                    "details": {},
                },
                {
                    "id": "evt_2",
                    "type": "call.completed",
                    "call_id": call_id,
                    "created_at": "2026-08-09T10:01:00Z",
                    "level": "info",
                    "status": "completed",
                    "message": "Call completed.",
                    "details": {"duration_seconds": 60},
                },
            ],
            "next_cursor": None,
        }

    def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _fake_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeEventsGateway.raise_error = False
    monkeypatch.setattr(runs_module, "EngineGateway", FakeEventsGateway)


async def _seed_run_with_outcome(tenant: Tenant, run_id: str) -> None:
    async with database.as_user(str(tenant.auth_user_id)) as conn:
        await runs_repo.create_run(
            conn,
            run_id=run_id,
            org_id=tenant.org_id,
            campaign_id=TRAVEL_DISCOVERY.id,
            total=1,
            started_by=tenant.user_id,
        )
        await runs_repo.append_outcome(
            conn,
            run_id=run_id,
            org_id=tenant.org_id,
            outcome={
                "contact_name": "Aditi",
                "phone_masked": "+91*******210",
                "status": "COMPLETED",
                "provider_call_id": PROVIDER_CALL_ID,
                "sentiment": "positive",
                "disposition": "auto_closed",
            },
        )


async def test_unknown_run_returns_404(tenant: Tenant) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_call_events("run_does_not_exist", PROVIDER_CALL_ID, _current_user(tenant))
    assert exc_info.value.status_code == 404


async def test_call_id_not_in_this_run_returns_404(tenant: Tenant) -> None:
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    await _seed_run_with_outcome(tenant, run_id)

    with pytest.raises(HTTPException) as exc_info:
        await get_call_events(run_id, "call_some_other_call", _current_user(tenant))
    assert exc_info.value.status_code == 404


async def test_missing_api_key_returns_400(tenant: Tenant, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    await _seed_run_with_outcome(tenant, run_id)
    monkeypatch.setattr(runs_module, "config", dataclasses.replace(config, api_key=""))

    with pytest.raises(HTTPException) as exc_info:
        await get_call_events(run_id, PROVIDER_CALL_ID, _current_user(tenant))
    assert exc_info.value.status_code == 400


async def test_engine_error_becomes_502_not_an_unhandled_exception(tenant: Tenant) -> None:
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    await _seed_run_with_outcome(tenant, run_id)
    FakeEventsGateway.raise_error = True

    with pytest.raises(HTTPException) as exc_info:
        await get_call_events(run_id, PROVIDER_CALL_ID, _current_user(tenant))
    assert exc_info.value.status_code == 502


async def test_happy_path_returns_parsed_events_in_order(tenant: Tenant) -> None:
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    await _seed_run_with_outcome(tenant, run_id)

    result = await get_call_events(run_id, PROVIDER_CALL_ID, _current_user(tenant))

    assert FakeEventsGateway.last_call_id == PROVIDER_CALL_ID
    assert [e.type for e in result.events] == ["call.queued", "call.completed"]
    assert result.events[1].details == {"duration_seconds": 60}
    assert result.next_cursor is None


async def test_cursor_is_forwarded_to_the_engine(tenant: Tenant) -> None:
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    await _seed_run_with_outcome(tenant, run_id)

    await get_call_events(run_id, PROVIDER_CALL_ID, _current_user(tenant), cursor="cur_xyz")

    assert FakeEventsGateway.last_cursor == "cur_xyz"
