"""The HTTP surface over connect-a-number.

The workflow it wraps is covered in `test_number_provisioning.py`; what is
asserted here is the route's own job - that a caller cannot reach another
organisation's agent, that carrier credentials come from that org's own stored
row, and that a part-way failure comes back as a readable attempt rather than a
500 the operator can do nothing with.

Calls the route functions directly, following `test_internal_completion.py`.
Skipped when DATABASE_URL is unset - see `tests/local_postgres/README.md`.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any, ClassVar, Self

import asyncpg
import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.api.v1.routes.telephony import (
    ConnectNumberIn,
    connect_number_status,
    start_connect_number,
)
from app.auth.dependencies import CurrentUser
from app.core.config import config
from app.core.crypto import encrypt
from app.database import database
from app.database.models import OrgRole
from app.domain.provisioning import ProvisioningStatus
from app.integrations.telephony import CarrierError, CarrierTrunk

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not config.database_url, reason="DATABASE_URL is not configured"),
    pytest.mark.skipif(
        not config.provider_credentials_key, reason="PROVIDER_CREDENTIALS_KEY is not configured"
    ),
]

NUMBER = "+15555550100"


@dataclasses.dataclass(frozen=True)
class Tenant:
    user: CurrentUser
    agent_id: uuid.UUID


class StubGateway:
    def __init__(self) -> None:
        self.created: list[str] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def create_inbound_trunk(self, **_kw: Any) -> str:
        self.created.append("inbound")
        return "ST_in_1"

    async def create_dispatch_rule(self, **_kw: Any) -> str:
        self.created.append("dispatch")
        return "SDR_1"

    async def create_outbound_trunk(self, **_kw: Any) -> str:
        self.created.append("outbound")
        return "ST_out_1"


class StubCarrier:
    """Records the credentials it was constructed with, so the route's own
    lookup-and-decrypt step is observable."""

    seen: ClassVar[list[dict[str, str]]] = []
    fail: ClassVar[bool] = False
    # Every carrier declares which SIP transport its outbound trunk must name;
    # `_run_steps` reads it off the class, not off a returned `CarrierTrunk`.
    outbound_transport: ClassVar[str | None] = None

    def __init__(self, **credentials: str) -> None:
        StubCarrier.seen.append(credentials)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def configure_number(self, **_kw: Any) -> CarrierTrunk:
        if StubCarrier.fail:
            raise CarrierError("StubCarrier", "attach the number", "the number is not yours.")
        return CarrierTrunk(
            provider="twilio",
            trunk_id="TK1",
            termination_domain="stub.example.com",
            auth_username="u",
            auth_password="p",
        )

    @staticmethod
    def allowed_addresses() -> list[str]:
        return []


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[None]:
    await database.connect()
    try:
        yield None
    finally:
        await database.disconnect()


@pytest_asyncio.fixture
async def db(pool: None) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(config.database_url, timeout=30)
    try:
        yield conn
    finally:
        await conn.close()


async def _make_tenant(db: asyncpg.Connection, label: str) -> Tenant:
    auth_user_id = uuid.uuid4()
    await db.execute(
        """
        insert into auth.users (id, email, raw_user_meta_data, raw_app_meta_data,
                                created_at, updated_at)
        values ($1, $2, $3::jsonb, '{"provider":"email"}', now(), now())
        """,
        auth_user_id,
        f"tel-{auth_user_id.hex[:8]}@brbik.com",
        json.dumps({"full_name": f"Telephony {label}"}),
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
        "insert into public.voice_agents (org_id, name, kind)"
        " values ($1, $2, 'custom') returning id",
        row["org_id"],
        f"agent-{label}",
    )
    await db.execute(
        """
        insert into public.provider_credentials
            (org_id, created_by, provider, label, identifier_encrypted, secret_encrypted)
        values ($1, $2, 'twilio', 'Office', $3, $4)
        """,
        row["org_id"],
        row["user_id"],
        encrypt(f"AC-{label}"),
        encrypt(f"token-{label}"),
    )
    return Tenant(
        user=CurrentUser(
            id=row["user_id"],
            org_id=row["org_id"],
            auth_user_id=str(auth_user_id),
            role=OrgRole.OWNER,
            email=f"tel-{auth_user_id.hex[:8]}@brbik.com",
            name=f"Telephony {label}",
            avatar_url=None,
            org_name=f"Org {label}",
            org_slug=f"org-{label}",
            org_logo_url=None,
            org_onboarded_at=None,
            org_plan_id=None,
        ),
        agent_id=agent_id,
    )


@pytest_asyncio.fixture(autouse=True)
async def _reset_stub() -> AsyncIterator[None]:
    StubCarrier.seen = []
    StubCarrier.fail = False
    yield
    StubCarrier.fail = False


@pytest_asyncio.fixture
async def tenants(db: asyncpg.Connection) -> AsyncIterator[tuple[Tenant, Tenant]]:
    a = await _make_tenant(db, "a")
    b = await _make_tenant(db, "b")
    try:
        yield a, b
    finally:
        await db.execute("select set_config('role', 'postgres', true)")
        await db.execute(
            "delete from auth.users where id = any($1::uuid[])",
            [uuid.UUID(a.user.auth_user_id), uuid.UUID(b.user.auth_user_id)],
        )
        await db.execute(
            "delete from public.organisations o where not exists"
            " (select 1 from public.memberships m where m.org_id = o.id)"
        )


def _body(**overrides: Any) -> ConnectNumberIn:
    payload: dict[str, Any] = {
        "provider": "twilio",
        "phone_number": NUMBER,
        "number_ref": "PN123",
        "label": "office-line",
        "idempotency_key": "connect-attempt-1",
    }
    payload.update(overrides)
    return ConnectNumberIn(**payload)


@pytest.fixture(autouse=True)
def _stub_vendors(monkeypatch: pytest.MonkeyPatch) -> None:
    """No LiveKit account and no Twilio account, on purpose (CLAUDE.md §7)."""
    monkeypatch.setattr(
        "app.services.number_provisioning.CARRIERS", {"twilio": StubCarrier, "plivo": StubCarrier}
    )
    monkeypatch.setattr(
        "app.services.number_provisioning.LiveKitGateway", lambda *a, **k: StubGateway()
    )
    # `Config` is a frozen dataclass read once at import, so the whole object is
    # replaced rather than one field mutated.
    monkeypatch.setattr(
        "app.services.number_provisioning.config",
        dataclasses.replace(config, livekit_sip_host="sip.livekit.test"),
    )


async def test_connecting_a_number_records_a_verified_attempt(
    tenants: tuple[Tenant, Tenant],
) -> None:
    a, _b = tenants

    result = await start_connect_number(a.agent_id, _body(), a.user)

    assert result.status == ProvisioningStatus.VERIFIED.value
    assert result.voice_agent_id == str(a.agent_id)
    assert result.last_error is None


async def test_the_orgs_own_stored_credentials_are_what_reach_the_carrier(
    tenants: tuple[Tenant, Tenant],
) -> None:
    """Decrypted here rather than passed in by the caller - an endpoint that
    accepted credentials in its body would be a way to make CallFlow configure
    an account nobody proved they own."""
    a, _b = tenants

    await start_connect_number(a.agent_id, _body(), a.user)

    assert StubCarrier.seen[0] == {"account_sid": "AC-a", "auth_token": "token-a"}


async def test_another_tenants_agent_is_not_found(tenants: tuple[Tenant, Tenant]) -> None:
    """The check that stops a caller pairing their own org_id with someone
    else's agent - which the insert policy alone would allow."""
    a, b = tenants

    with pytest.raises(HTTPException) as caught:
        await start_connect_number(b.agent_id, _body(), a.user)

    assert caught.value.status_code == 404


async def test_replaying_the_same_key_does_not_create_a_second_trunk(
    tenants: tuple[Tenant, Tenant], db: asyncpg.Connection
) -> None:
    """A double-clicked button is the ordinary case, and a second LiveKit trunk
    pair is an orphan nobody ever cleans up."""
    a, _b = tenants

    first = await start_connect_number(a.agent_id, _body(), a.user)
    second = await start_connect_number(a.agent_id, _body(), a.user)

    assert first.id == second.id
    count = await db.fetchval(
        "select count(*) from public.telephony_provisioning where voice_agent_id = $1",
        a.agent_id,
    )
    assert count == 1


async def test_a_carrier_failure_comes_back_as_a_readable_attempt(
    tenants: tuple[Tenant, Tenant],
) -> None:
    """Not a 500: the vendor's own wording is the only part that says what to
    fix, and the attempt stays resumable with the same key."""
    a, _b = tenants
    StubCarrier.fail = True

    result = await start_connect_number(a.agent_id, _body(), a.user)

    assert result.status == ProvisioningStatus.PROVISIONING.value
    assert "the number is not yours." in (result.last_error or "")


async def test_an_unsupported_carrier_is_refused_by_name(
    tenants: tuple[Tenant, Tenant],
) -> None:
    a, _b = tenants

    with pytest.raises(HTTPException) as caught:
        await start_connect_number(a.agent_id, _body(provider="vonage"), a.user)

    assert caught.value.status_code == 400
    assert "vonage" in caught.value.detail


async def test_a_carrier_with_no_stored_credentials_says_where_to_add_them(
    tenants: tuple[Tenant, Tenant],
) -> None:
    a, _b = tenants

    with pytest.raises(HTTPException) as caught:
        await start_connect_number(a.agent_id, _body(provider="plivo"), a.user)

    assert caught.value.status_code == 400
    assert "Integrations" in caught.value.detail


async def test_the_status_poll_reports_the_newest_attempt(
    tenants: tuple[Tenant, Tenant],
) -> None:
    a, _b = tenants
    await start_connect_number(a.agent_id, _body(), a.user)
    await start_connect_number(a.agent_id, _body(idempotency_key="connect-attempt-2"), a.user)

    latest = await connect_number_status(a.agent_id, a.user)

    assert latest.status == ProvisioningStatus.VERIFIED.value


async def test_polling_an_agent_that_was_never_connected_is_a_404(
    tenants: tuple[Tenant, Tenant],
) -> None:
    a, _b = tenants

    with pytest.raises(HTTPException) as caught:
        await connect_number_status(a.agent_id, a.user)

    assert caught.value.status_code == 404


async def test_the_response_never_carries_a_trunk_id(
    tenants: tuple[Tenant, Tenant],
) -> None:
    """LiveKit's internal handles are not something an operator can act on, and
    every field a response declares is a field somebody starts depending on."""
    a, _b = tenants

    result = await start_connect_number(a.agent_id, _body(), a.user)

    assert "ST_in_1" not in result.model_dump_json()
