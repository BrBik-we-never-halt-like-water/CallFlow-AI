"""`telephony_provisioning`'s repository, against the real database.

The idempotency behaviour here is the whole reason the table exists: creating a
LiveKit trunk is not idempotent at the vendor, so a retry that re-runs trunk
creation orphans a second trunk nobody will clean up. `start_attempt()` is what
stands between a double-clicked "Connect number" and that outcome, and the only
honest way to test it is against a real unique index.

Skipped when DATABASE_URL is unset - see `tests/local_postgres/README.md`.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from app.core.config import config
from app.database.repositories import telephony_provisioning as repo
from app.domain.provisioning import InvalidTransition, ProvisioningStatus

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not config.database_url, reason="DATABASE_URL is not configured"),
]

S = ProvisioningStatus


@pytest_asyncio.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(config.database_url, timeout=30)
    try:
        yield conn
    finally:
        await conn.execute("select set_config('role', 'postgres', true)")
        await conn.close()


class Fixture:
    def __init__(self, auth_user_id: uuid.UUID, org_id: uuid.UUID, agent_id: uuid.UUID) -> None:
        self.auth_user_id = auth_user_id
        self.org_id = org_id
        self.agent_id = agent_id


@pytest_asyncio.fixture
async def owned(db: asyncpg.Connection) -> AsyncIterator[Fixture]:
    """One org with one owner and one voice agent, via the real signup trigger."""
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
        json.dumps({"full_name": "Provisioning Owner"}),
    )
    org_id = await db.fetchval(
        """
        select m.org_id from public.users u
        join public.memberships m on m.user_id = u.id
        where u.auth_user_id = $1
        """,
        auth_user_id,
    )
    agent_id = await db.fetchval(
        """
        insert into public.voice_agents (org_id, name, kind)
        values ($1, 'Test agent', 'custom') returning id
        """,
        org_id,
    )
    try:
        yield Fixture(auth_user_id, org_id, agent_id)
    finally:
        await db.execute("select set_config('role', 'postgres', true)")
        await db.execute("delete from auth.users where id = $1", auth_user_id)
        await db.execute(
            """
            delete from public.organisations o
            where not exists (select 1 from public.memberships m where m.org_id = o.id)
            """
        )


async def _as_user(conn: asyncpg.Connection, auth_user_id: uuid.UUID) -> None:
    claims = json.dumps({"sub": str(auth_user_id), "role": "authenticated"})
    await conn.execute("select set_config('request.jwt.claims', $1, true)", claims)
    await conn.execute("select set_config('role', 'authenticated', true)")


async def test_first_attempt_is_created_pending(
    db: asyncpg.Connection, owned: Fixture
) -> None:
    async with db.transaction():
        await _as_user(db, owned.auth_user_id)
        row, created = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="k1"
        )

    assert created is True
    assert row["status"] == S.PENDING.value
    assert row["livekit_inbound_trunk_id"] is None


async def test_replaying_the_same_key_returns_the_original_attempt(
    db: asyncpg.Connection, owned: Fixture
) -> None:
    """The double-click case. A second call with the same key must NOT create a
    second row, or the caller goes on to create a second LiveKit trunk."""
    async with db.transaction():
        await _as_user(db, owned.auth_user_id)
        first, created_first = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="same"
        )
        second, created_second = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="same"
        )

    assert created_first is True
    assert created_second is False
    assert first["id"] == second["id"]

    await db.execute("select set_config('role', 'postgres', true)")
    count = await db.fetchval(
        "select count(*) from public.telephony_provisioning where voice_agent_id = $1",
        owned.agent_id,
    )
    assert count == 1


async def test_a_replay_carries_back_what_the_first_attempt_already_created(
    db: asyncpg.Connection, owned: Fixture
) -> None:
    """This is the property that actually prevents the orphaned trunk: the retry
    must be able to see the trunk id the first attempt recorded, so it knows to
    skip creating one."""
    async with db.transaction():
        await _as_user(db, owned.auth_user_id)
        first, _ = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="partial"
        )
        await repo.set_status(db, first["id"], S.PROVISIONING)
        await repo.record_livekit_ids(db, first["id"], inbound_trunk_id="ST_already_made")

        replay, created = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="partial"
        )

    assert created is False
    assert replay["livekit_inbound_trunk_id"] == "ST_already_made"
    assert replay["status"] == S.PROVISIONING.value


async def test_a_different_key_starts_a_genuinely_new_attempt(
    db: asyncpg.Connection, owned: Fixture
) -> None:
    """"Try again" is a new key, and must not be blocked by the failed one."""
    async with db.transaction():
        await _as_user(db, owned.auth_user_id)
        first, _ = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="try-1"
        )
        await repo.set_status(db, first["id"], S.FAILED, last_error="Carrier rejected the URI.")

        second, created = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="try-2"
        )

    assert created is True
    assert second["id"] != first["id"]
    assert second["status"] == S.PENDING.value


async def test_the_failed_attempts_diagnostic_trail_survives_a_retry(
    db: asyncpg.Connection, owned: Fixture
) -> None:
    async with db.transaction():
        await _as_user(db, owned.auth_user_id)
        failed, _ = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="trail-1"
        )
        await repo.set_status(
            db, failed["id"], S.FAILED, last_error="Twilio rejected the Origination URI."
        )
        await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="trail-2"
        )

        still_there = await repo.get_attempt(db, failed["id"])

    assert still_there is not None
    assert still_there["status"] == S.FAILED.value
    assert still_there["last_error"] == "Twilio rejected the Origination URI."


async def test_latest_for_agent_reports_the_newest_attempt(
    db: asyncpg.Connection, owned: Fixture
) -> None:
    """Both attempts are made in ONE transaction on purpose: that gives them the
    same `created_at` (which is `now()`, the transaction timestamp), so anything
    ordering by `created_at` has to fall back to its tiebreak. With `id desc` as
    that tiebreak - a random uuid - this assertion passed or failed by chance.
    Ordering by the identity column is what makes it a guarantee.
    """
    async with db.transaction():
        await _as_user(db, owned.auth_user_id)
        older, _ = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="old"
        )
        newest, _ = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="new"
        )
        latest = await repo.latest_for_agent(db, owned.agent_id)

    assert older["created_at"] == newest["created_at"], "precondition: the tie is real"
    assert newest["seq"] > older["seq"]
    assert latest is not None
    assert latest["id"] == newest["id"]


async def test_latest_for_agent_is_stable_across_repeated_reads(
    db: asyncpg.Connection, owned: Fixture
) -> None:
    """A status poll runs this every couple of seconds. A non-deterministic
    answer would flip the connect-number page between a live attempt and a dead
    one while nothing had actually changed."""
    async with db.transaction():
        await _as_user(db, owned.auth_user_id)
        for key in ("a", "b", "c", "d"):
            await repo.start_attempt(
                db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key=key
            )
        seen = {
            (await repo.latest_for_agent(db, owned.agent_id))["id"] for _ in range(10)
        }

    assert len(seen) == 1


async def test_recording_one_step_does_not_blank_an_earlier_one(
    db: asyncpg.Connection, owned: Fixture
) -> None:
    """Each step writes only its own id. Without the coalesce, step three would
    null out the trunk ids steps one and two recorded."""
    async with db.transaction():
        await _as_user(db, owned.auth_user_id)
        row, _ = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="steps"
        )
        await repo.record_livekit_ids(db, row["id"], inbound_trunk_id="ST_in")
        await repo.record_livekit_ids(db, row["id"], outbound_trunk_id="ST_out")
        final = await repo.record_livekit_ids(db, row["id"], dispatch_rule_id="SDR_1")

    assert final is not None
    assert final["livekit_inbound_trunk_id"] == "ST_in"
    assert final["livekit_outbound_trunk_id"] == "ST_out"
    assert final["livekit_dispatch_rule_id"] == "SDR_1"


async def test_an_illegal_status_move_raises_instead_of_writing(
    db: asyncpg.Connection, owned: Fixture
) -> None:
    async with db.transaction():
        await _as_user(db, owned.auth_user_id)
        row, _ = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="illegal"
        )
        # pending -> verified skips provisioning entirely.
        with pytest.raises(InvalidTransition):
            await repo.set_status(db, row["id"], S.VERIFIED)

        unchanged = await repo.get_attempt(db, row["id"])

    assert unchanged is not None
    assert unchanged["status"] == S.PENDING.value


async def test_a_terminal_attempt_cannot_be_moved(
    db: asyncpg.Connection, owned: Fixture
) -> None:
    async with db.transaction():
        await _as_user(db, owned.auth_user_id)
        row, _ = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="terminal"
        )
        await repo.set_status(db, row["id"], S.PROVISIONING)
        await repo.set_status(db, row["id"], S.VERIFIED)

        with pytest.raises(InvalidTransition):
            await repo.set_status(db, row["id"], S.FAILED, last_error="too late")


async def test_updated_at_moves_on_a_status_change(
    db: asyncpg.Connection, owned: Fixture
) -> None:
    """The trigger this migration added - `updated_at` that never updates would
    make the status poll unable to tell a stalled attempt from a fresh one.

    Two transactions, not one: `touch_updated_at()` uses `now()`, which is the
    *transaction* timestamp, so a create and an update inside one transaction
    both stamp the same instant. That is standard Postgres and matches every
    other table here - and it mirrors the real flow anyway, where each
    provisioning step is its own request.
    """
    async with db.transaction():
        await _as_user(db, owned.auth_user_id)
        row, _ = await repo.start_attempt(
            db, voice_agent_id=owned.agent_id, org_id=owned.org_id, idempotency_key="touch"
        )
        before = row["updated_at"]

    async with db.transaction():
        await _as_user(db, owned.auth_user_id)
        moved = await repo.set_status(db, row["id"], S.PROVISIONING)

    assert moved is not None
    assert moved["updated_at"] > before


async def test_another_org_cannot_move_this_orgs_attempt(
    db: asyncpg.Connection, owned: Fixture
) -> None:
    """RLS filters the row, so `set_status` reports "not yours" rather than
    silently succeeding against nothing."""
    outsider = uuid.uuid4()
    await db.execute("select set_config('role', 'postgres', true)")
    await db.execute(
        """
        insert into auth.users (id, instance_id, aud, role, email, encrypted_password,
                                email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
                                created_at, updated_at)
        values ($1, '00000000-0000-0000-0000-000000000000', 'authenticated',
                'authenticated', $2, crypt('x', gen_salt('bf')), now(),
                '{"provider":"email"}', '{}'::jsonb, now(), now())
        """,
        outsider,
        f"outsider-{outsider.hex[:8]}@brbik.com",
    )

    attempt_id = await db.fetchval(
        """
        insert into public.telephony_provisioning (voice_agent_id, org_id, idempotency_key)
        values ($1, $2, 'victim') returning id
        """,
        owned.agent_id,
        owned.org_id,
    )

    try:
        async with db.transaction():
            await _as_user(db, outsider)
            assert await repo.set_status(db, attempt_id, S.PROVISIONING) is None

        await db.execute("select set_config('role', 'postgres', true)")
        status = await db.fetchval(
            "select status from public.telephony_provisioning where id = $1", attempt_id
        )
        assert status == S.PENDING.value
    finally:
        await db.execute("select set_config('role', 'postgres', true)")
        await db.execute("delete from auth.users where id = $1", outsider)
