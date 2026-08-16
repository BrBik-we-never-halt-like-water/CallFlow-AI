"""The connect-a-number workflow, against the real database and stub vendors.

The property this exists to prove is the one ADR-4 singled out: a retry of the
same attempt must **not** re-create a LiveKit trunk it already made. Nothing
here is transactional - LiveKit and the carrier have no shared commit - so the
row is the only ledger, and a bug here leaves orphaned trunks that nobody ever
cleans up and no error ever mentions.

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

from app.core.config import config
from app.database.repositories import telephony_provisioning as provisioning_repo
from app.domain.provisioning import ProvisioningStatus
from app.integrations.telephony import CarrierError, CarrierTrunk
from app.services.number_provisioning import ProvisioningRefused, connect_number

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not config.database_url, reason="DATABASE_URL is not configured"),
]

SIP_HOST = "abc123.sip.livekit.cloud"
NUMBER = "+15555550100"


class StubGateway:
    """Counts every LiveKit object it is asked to create."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.created: list[str] = []
        self._fail_on = fail_on

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    def _maybe_fail(self, what: str) -> None:
        if self._fail_on == what:
            raise RuntimeError(f"LiveKit refused to create the {what}")

    async def create_inbound_trunk(self, **_: Any) -> str:
        self._maybe_fail("inbound")
        self.created.append("inbound")
        return "ST_in_1"

    async def create_dispatch_rule(self, **_: Any) -> str:
        self._maybe_fail("dispatch")
        self.created.append("dispatch")
        return "SDR_1"

    async def create_outbound_trunk(self, **_: Any) -> str:
        self._maybe_fail("outbound")
        self.created.append("outbound")
        return "ST_out_1"


class StubCarrier:
    """A carrier that records the credentials it was told to expect."""

    calls: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, fail: bool = False, **credentials: Any) -> None:
        self._fail = fail
        self._credentials = credentials

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    @staticmethod
    def allowed_addresses() -> list[str]:
        return ["1.2.3.4/32"]

    async def configure_number(self, **kwargs: Any) -> CarrierTrunk:
        StubCarrier.calls.append(kwargs)
        if self._fail:
            raise CarrierError("StubCarrier", "attach the phone number", "the number is not yours.")
        return CarrierTrunk(
            provider="stub",
            trunk_id="CT_1",
            termination_domain="stub.example.com",
            auth_username=kwargs["auth_username"],
            auth_password=kwargs["auth_password"],
        )


def _carrier_factory(fail: bool = False) -> Any:
    class _Bound(StubCarrier):
        def __init__(self, **credentials: Any) -> None:
            super().__init__(fail=fail, **credentials)

    return _Bound


@pytest.fixture(autouse=True)
def _reset_carrier_calls() -> None:
    StubCarrier.calls = []


@pytest.fixture(autouse=True)
def _credentials_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_sip_auth` derives the trunk password from this, and refuses without it.

    Set here rather than relying on a developer's `.env`, so the suite behaves
    the same in CI - and so the one test that asserts the refusal has to opt
    out explicitly rather than passing by accident.
    """
    from app.services import number_provisioning as service

    monkeypatch.setattr(
        service,
        "config",
        # `livekit_sip_host` blanked too: the service falls back to config when
        # the argument is empty, so a developer with a real .env would otherwise
        # silently skip the refusal these tests assert.
        dataclasses.replace(config, provider_credentials_key="test-key", livekit_sip_host=""),
    )


@pytest_asyncio.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(config.database_url, timeout=30)
    try:
        yield conn
    finally:
        await conn.execute("select set_config('role', 'postgres', true)")
        await conn.close()


class Agent:
    def __init__(self, agent_id: uuid.UUID, org_id: uuid.UUID, auth_user_id: uuid.UUID) -> None:
        self.id = agent_id
        self.org_id = org_id
        self.auth_user_id = auth_user_id


@pytest_asyncio.fixture
async def agent(db: asyncpg.Connection) -> AsyncIterator[Agent]:
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
        f"prov-{auth_user_id.hex[:8]}@brbik.com",
        json.dumps({"full_name": "Provisioning"}),
    )
    org_id = await db.fetchval(
        """
        select m.org_id from public.users u
        join public.memberships m on m.user_id = u.id where u.auth_user_id = $1
        """,
        auth_user_id,
    )
    agent_id = await db.fetchval(
        "insert into public.voice_agents (org_id, name, kind) values ($1, 'A', 'custom')"
        " returning id",
        org_id,
    )
    try:
        yield Agent(agent_id, org_id, auth_user_id)
    finally:
        await db.execute("select set_config('role', 'postgres', true)")
        await db.execute("delete from auth.users where id = $1", auth_user_id)
        await db.execute(
            "delete from public.organisations o where not exists"
            " (select 1 from public.memberships m where m.org_id = o.id)"
        )


async def _connect(
    db: asyncpg.Connection,
    agent: Agent,
    key: str,
    *,
    gateway: StubGateway | None = None,
    carrier_fails: bool = False,
) -> asyncpg.Record:
    stub = gateway or StubGateway()
    return await connect_number(
        db,
        voice_agent_id=agent.id,
        org_id=agent.org_id,
        idempotency_key=key,
        provider="twilio",
        credentials={"account_sid": "AC1", "auth_token": "tok"},
        phone_number=NUMBER,
        label="org-a",
        livekit_sip_host=SIP_HOST,
        gateway_factory=lambda: stub,
        carrier_factory=_carrier_factory(fail=carrier_fails),
    )


# --- the happy path -----------------------------------------------------------


async def test_a_successful_run_creates_every_piece_and_verifies(
    db: asyncpg.Connection, agent: Agent
) -> None:
    gateway = StubGateway()
    row = await _connect(db, agent, "k1", gateway=gateway)

    assert gateway.created == ["inbound", "dispatch", "outbound"]
    assert row["status"] == ProvisioningStatus.VERIFIED.value
    assert row["livekit_inbound_trunk_id"] == "ST_in_1"
    assert row["livekit_outbound_trunk_id"] == "ST_out_1"
    assert row["carrier_termination_domain"] == "stub.example.com"


async def test_the_outbound_trunk_dials_the_address_the_carrier_returned(
    db: asyncpg.Connection, agent: Agent
) -> None:
    """Step 4 depends on step 3's output - that is why the carrier comes first."""
    row = await _connect(db, agent, "k-order")
    assert row["carrier_termination_domain"] == "stub.example.com"
    assert row["livekit_outbound_trunk_id"]


async def test_the_carrier_is_given_the_livekit_sip_host(
    db: asyncpg.Connection, agent: Agent
) -> None:
    await _connect(db, agent, "k-host")
    assert StubCarrier.calls[0]["livekit_sip_host"] == SIP_HOST


# --- the property this module exists for --------------------------------------


async def test_a_resumed_attempt_does_not_create_a_second_livekit_trunk(
    db: asyncpg.Connection, agent: Agent
) -> None:
    """The failure ADR-4 named. The carrier fails after LiveKit succeeded; the
    retry must pick up from there, not make a second inbound trunk that nothing
    will ever clean up."""
    first = StubGateway()
    failed = await _connect(db, agent, "k-resume", gateway=first, carrier_fails=True)

    # Reported on the row, not raised: the caller's transaction has to commit or
    # the trunk ids below are rolled back and the retry orphans a second pair.
    assert failed["status"] == ProvisioningStatus.PROVISIONING.value
    assert first.created == ["inbound", "dispatch"]

    # Same key, so this resumes rather than starting over. No status reset is
    # needed - a part-way failure deliberately leaves the attempt resumable.
    second = StubGateway()
    row = await _connect(db, agent, "k-resume", gateway=second)

    assert second.created == ["outbound"], "the inbound trunk was created twice"
    assert row["livekit_inbound_trunk_id"] == "ST_in_1"
    assert row["status"] == ProvisioningStatus.VERIFIED.value


async def test_a_partial_failure_records_what_was_already_created(
    db: asyncpg.Connection, agent: Agent
) -> None:
    """Each step writes the moment it succeeds. Batching the writes to the end
    would lose exactly the ids a retry needs."""
    await _connect(db, agent, "k-partial", carrier_fails=True)

    row = await provisioning_repo.latest_for_agent(db, agent.id)
    assert row["livekit_inbound_trunk_id"] == "ST_in_1"
    assert row["livekit_dispatch_rule_id"] == "SDR_1"
    assert row["livekit_outbound_trunk_id"] is None


async def test_a_failure_leaves_the_carriers_own_reason_on_the_row(
    db: asyncpg.Connection, agent: Agent
) -> None:
    """Shown to the operator verbatim, so it has to name what to fix."""
    returned = await _connect(db, agent, "k-error", carrier_fails=True)

    row = await provisioning_repo.latest_for_agent(db, agent.id)
    assert "the number is not yours." in row["last_error"]
    # The same row the caller got back, so a route can render it without
    # re-reading - which is the whole reason failure is returned, not raised.
    assert returned["last_error"] == row["last_error"]


async def test_the_same_credentials_are_used_across_a_resume(
    db: asyncpg.Connection, agent: Agent
) -> None:
    """Regenerating would leave LiveKit dialling with a password the carrier no
    longer expects - a failure that shows up only as silently rejected calls."""
    await _connect(db, agent, "k-creds", carrier_fails=True)
    first_password = StubCarrier.calls[0]["auth_password"]

    StubCarrier.calls = []
    await _connect(db, agent, "k-creds")

    assert StubCarrier.calls[0]["auth_password"] == first_password


# --- refusals -----------------------------------------------------------------


async def test_a_part_way_failure_stays_resumable_rather_than_terminal(
    db: asyncpg.Connection, agent: Agent
) -> None:
    """The distinction ADR-4 draws. Real LiveKit objects exist by now, so the
    only safe path forward is resuming this attempt and skipping them - which
    marking it terminal would make illegal."""
    await _connect(db, agent, "k-partial-status", carrier_fails=True)

    row = await provisioning_repo.latest_for_agent(db, agent.id)
    assert row["status"] == ProvisioningStatus.PROVISIONING.value
    assert row["last_error"]


async def test_a_superseded_attempt_cannot_be_resumed(
    db: asyncpg.Connection, agent: Agent
) -> None:
    """Once a newer attempt exists, the old one is terminal - resuming it would
    configure against objects the newer attempt has moved past."""
    await _connect(db, agent, "k-old", carrier_fails=True)
    await _connect(db, agent, "k-new")

    with pytest.raises(ProvisioningRefused) as caught:
        await _connect(db, agent, "k-old")

    assert "superseded" in str(caught.value)


async def test_a_verified_attempt_replayed_is_a_no_op_not_an_error(
    db: asyncpg.Connection, agent: Agent
) -> None:
    """A double-submitted request should be harmless, not something the UI has
    to explain."""
    await _connect(db, agent, "k-done")
    gateway = StubGateway()
    row = await _connect(db, agent, "k-done", gateway=gateway)

    assert gateway.created == []
    assert row["status"] == ProvisioningStatus.VERIFIED.value


async def test_a_new_key_starts_a_clean_attempt_beside_the_failed_one(
    db: asyncpg.Connection, agent: Agent
) -> None:
    await _connect(db, agent, "attempt-1", carrier_fails=True)
    row = await _connect(db, agent, "attempt-2")

    assert row["status"] == ProvisioningStatus.VERIFIED.value
    count = await db.fetchval(
        "select count(*) from public.telephony_provisioning where voice_agent_id = $1", agent.id
    )
    assert count == 2, "the failed attempt must survive as the record of what went wrong"


async def test_a_carrier_failure_does_not_propagate_out_of_the_workflow(
    db: asyncpg.Connection, agent: Agent
) -> None:
    """The rollback this was written to prevent.

    `as_user()` wraps a request in one transaction. Raising from the error
    handler would discard the note it just wrote *and* every trunk id the
    successful steps recorded - leaving a row claiming nothing exists while two
    real LiveKit trunks do, so the next attempt creates a second pair. The
    ledger has to outlive the failure, which means the failure cannot unwind
    the transaction carrying it.
    """
    row = await _connect(db, agent, "k-no-raise", carrier_fails=True)

    assert row["status"] == ProvisioningStatus.PROVISIONING.value
    assert row["last_error"]
    assert row["livekit_inbound_trunk_id"] == "ST_in_1"
    assert row["livekit_dispatch_rule_id"] == "SDR_1"


async def test_an_unknown_carrier_is_refused_before_anything_is_created(
    db: asyncpg.Connection, agent: Agent
) -> None:
    with pytest.raises(ProvisioningRefused) as caught:
        await connect_number(
            db,
            voice_agent_id=agent.id,
            org_id=agent.org_id,
            idempotency_key="k-bad",
            provider="not-a-carrier",
            credentials={},
            phone_number=NUMBER,
            label="org-a",
            livekit_sip_host=SIP_HOST,
        )

    assert "not a carrier CallFlow can configure" in str(caught.value)
    assert await provisioning_repo.latest_for_agent(db, agent.id) is None


async def test_a_missing_sip_host_is_refused_with_where_to_find_it(
    db: asyncpg.Connection, agent: Agent
) -> None:
    with pytest.raises(ProvisioningRefused) as caught:
        await connect_number(
            db,
            voice_agent_id=agent.id,
            org_id=agent.org_id,
            idempotency_key="k-nohost",
            provider="twilio",
            credentials={},
            phone_number=NUMBER,
            label="org-a",
            livekit_sip_host="",
            carrier_factory=_carrier_factory(),
        )

    assert "LIVEKIT_SIP_HOST" in str(caught.value)
    assert "LiveKit project's SIP settings" in str(caught.value)


async def test_an_unset_credentials_key_refuses_rather_than_deriving_a_guessable_password(
    db: asyncpg.Connection, agent: Agent, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A constant fallback would make every deployment that forgot this key
    derive the same SIP password from the same attempt id - on a trunk that can
    place real calls, and it would work, so nothing would ever reveal it."""
    from app.services import number_provisioning as service

    monkeypatch.setattr(
        service, "config", dataclasses.replace(config, provider_credentials_key="")
    )
    with pytest.raises(ProvisioningRefused) as caught:
        await _connect(db, agent, "k-nokey")

    assert "PROVIDER_CREDENTIALS_KEY" in str(caught.value)
