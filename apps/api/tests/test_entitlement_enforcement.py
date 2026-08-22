"""Plan limits, asserted against the real database.

`tests/test_entitlements.py` proves the *decisions* are right. This file proves
they cannot be walked around, which is a different claim: `insert` on
`voice_agents` and `ai_provider_credentials` is granted straight to
`authenticated`, and `create_organisation()` is SECURITY DEFINER with EXECUTE
defaulting to PUBLIC. A limit enforced only in a route handler is decoration
against anyone holding a database connection (CLAUDE.md §4b).

Every insert here therefore goes through raw SQL as the *user*, never through a
repository, because a repository is exactly the layer these tests need to bypass.

Skipped when DATABASE_URL is unset, so the suite still runs offline - which is
also why CI, which sets no database, never exercises any of this.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
import pytest
import pytest_asyncio

from app.core.config import config
from app.domain.plans import Entitlements, PlanId, ladder

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not config.database_url, reason="DATABASE_URL is not configured"),
]


class Tenant:
    def __init__(self, auth_user_id: uuid.UUID, user_id: uuid.UUID, org_id: uuid.UUID) -> None:
        self.auth_user_id = auth_user_id
        self.user_id = user_id
        self.org_id = org_id


async def _create_tenant(conn: asyncpg.Connection, label: str) -> Tenant:
    auth_user_id = uuid.uuid4()
    # `extensions.crypt`: pgcrypto is installed into the `extensions` schema, not
    # `public`, so an unqualified `gen_salt` fails with "function does not exist".
    await conn.execute(
        """
        insert into auth.users (id, instance_id, aud, role, email, encrypted_password,
                                email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
                                created_at, updated_at)
        values ($1, '00000000-0000-0000-0000-000000000000', 'authenticated',
                'authenticated', $2, extensions.crypt('x', extensions.gen_salt('bf')), now(),
                '{"provider":"email"}', $3::jsonb, now(), now())
        """,
        auth_user_id,
        f"ent-{label}-{auth_user_id.hex[:8]}@brbik.com",
        {"full_name": f"Ent {label}"},
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


@asynccontextmanager
async def _acting_as(
    conn: asyncpg.Connection, auth_user_id: uuid.UUID
) -> AsyncIterator[asyncpg.Connection]:
    """Run a block as one signed-in user, with RLS in force.

    The transaction is not optional. `set_config(..., true)` is transaction-local,
    so outside one the role switch lasts a single statement and everything after
    it runs as `postgres` - which holds BYPASSRLS and every grant. A test written
    that way does not fail; it *passes for the wrong reason*, proving only that a
    superuser can do something nobody doubted. This is the same shape
    `database.as_user()` uses in production and `test_rls_isolation.py` uses here,
    for exactly this reason.

    On exit the transaction ends and the connection is back to `postgres` with no
    explicit reset needed - the settings were scoped to it.
    """
    claims = json.dumps({"sub": str(auth_user_id), "role": "authenticated"})
    async with conn.transaction():
        await conn.execute("select set_config('request.jwt.claims', $1, true)", claims)
        await conn.execute("select set_config('role', 'authenticated', true)")
        yield conn


@asynccontextmanager
async def _refused_as(
    conn: asyncpg.Connection, auth_user_id: uuid.UUID
) -> AsyncIterator[asyncpg.Connection]:
    """`_acting_as`, but the transaction is always rolled back.

    For the tests that assert a write is *refused*. If the guard ever regresses,
    the write succeeds and `_acting_as` would commit it - so the first run of a
    broken build silently corrupts the fixture data, and every later test then
    fails for a reason that has nothing to do with the code under it.

    That is not hypothetical. An earlier version of this file switched roles
    outside a transaction, so `update plan_entitlements set max_voice_agents =
    999` ran as `postgres`, succeeded, and committed - after which the ladder-drift
    test and the agent-ceiling test both failed against a catalogue nobody had
    knowingly edited. Rolling back unconditionally is what makes a failing
    assertion here cost only the assertion.
    """
    claims = json.dumps({"sub": str(auth_user_id), "role": "authenticated"})
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute("select set_config('request.jwt.claims', $1, true)", claims)
        await conn.execute("select set_config('role', 'authenticated', true)")
        yield conn
    finally:
        await tx.rollback()


async def _as_postgres(conn: asyncpg.Connection) -> None:
    await conn.execute("select set_config('role', 'postgres', true)")
    await conn.execute("select set_config('request.jwt.claims', '', true)")


async def _set_plan(conn: asyncpg.Connection, org_id: uuid.UUID, plan_id: str) -> None:
    await conn.execute("update public.organisations set plan_id = $2 where id = $1", org_id, plan_id)


@pytest_asyncio.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(config.database_url, timeout=30)
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog", format="text"
    )
    try:
        yield conn
    finally:
        await _as_postgres(conn)
        await conn.close()


@pytest_asyncio.fixture
async def tenant(db: asyncpg.Connection) -> AsyncIterator[Tenant]:
    created = await _create_tenant(db, "one")
    try:
        yield created
    finally:
        await _as_postgres(db)
        await db.execute("delete from auth.users where id = $1", created.auth_user_id)
        await db.execute(
            """
            delete from public.organisations o
            where not exists (select 1 from public.memberships m where m.org_id = o.id)
            """
        )


# --- the seeded table and the Python ladder must not drift ---


async def test_plan_entitlements_matches_the_python_ladder(db: asyncpg.Connection) -> None:
    """The whole reason the numbers live in a table as well as in Python. If these
    disagree, one of the two guards is enforcing a limit the product does not
    believe in - and which one wins depends on whether the caller came through
    the API or through SQL."""
    rows = await db.fetch("select * from public.plan_entitlements")
    by_plan = {r["plan_id"]: r for r in rows}

    assert set(by_plan) == {p.value for p in PlanId}

    for plan, expected in ladder().items():
        row = by_plan[plan.value]
        for field in dataclasses.fields(Entitlements):
            seeded = row[field.name]
            wanted = getattr(expected, field.name)
            if field.name == "llm_spend_limit_usd":
                seeded = float(seeded)
            assert seeded == wanted, f"{plan.value}.{field.name}: table={seeded} python={wanted}"


async def test_signup_lands_on_the_free_plan(db: asyncpg.Connection, tenant: Tenant) -> None:
    plan = await db.fetchval("select plan_id from public.organisations where id = $1", tenant.org_id)
    assert plan == PlanId.FREE.value


async def test_the_signup_trigger_is_not_subject_to_the_org_limit(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """Free allows one organisation and the trigger just created it. A second
    signup must still work - a plan limit reachable from the signup path is an
    outage, not a paywall."""
    second = await _create_tenant(db, "two")
    try:
        assert second.org_id != tenant.org_id
    finally:
        await _as_postgres(db)
        await db.execute("delete from auth.users where id = $1", second.auth_user_id)


# --- effective_limit ---


async def test_effective_limit_reads_the_plan(db: asyncpg.Connection, tenant: Tenant) -> None:
    await _set_plan(db, tenant.org_id, "starter")
    assert (
        await db.fetchval(
            "select public.effective_limit($1, 'max_voice_agents')", tenant.org_id
        )
        == ladder()[PlanId.STARTER].max_voice_agents
    )


async def test_effective_limit_returns_null_for_unlimited(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    await _set_plan(db, tenant.org_id, "growth")
    assert (
        await db.fetchval(
            "select public.effective_limit($1, 'max_ai_integrations')", tenant.org_id
        )
        is None
    )


async def test_effective_limit_raises_on_an_unknown_limit_name(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """Null means unlimited here, so a typo'd column name returning null would
    fail *open*. This is the one failure mode the function must not have."""
    with pytest.raises(asyncpg.exceptions.PostgresError):
        await db.fetchval("select public.effective_limit($1, 'max_agents')", tenant.org_id)


async def test_effective_limit_fails_closed_for_an_unknown_org(
    db: asyncpg.Connection,
) -> None:
    assert (
        await db.fetchval(
            "select public.effective_limit($1, 'max_voice_agents')", uuid.uuid4()
        )
        == 0
    )


# --- the voice-agent ceiling, against raw SQL ---


async def _insert_agent(conn: asyncpg.Connection, tenant: Tenant, name: str) -> None:
    async with _acting_as(conn, tenant.auth_user_id):
        await conn.execute(
            "insert into public.voice_agents (org_id, name, kind) values ($1, $2, 'custom')",
            tenant.org_id,
            name,
        )


async def test_the_agent_ceiling_holds_against_raw_sql(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """Free allows one. The second insert must be refused by the trigger, with no
    route and no repository involved."""
    await _insert_agent(db, tenant, "first")

    with pytest.raises(asyncpg.exceptions.CheckViolationError) as caught:
        await _insert_agent(db, tenant, "second")

    message = str(caught.value)
    # Reads as an instruction, not a constraint name (CLAUDE.md §5).
    assert "Settings" in message and "Billing" in message


async def test_raising_the_plan_raises_the_ceiling(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    await _insert_agent(db, tenant, "first")
    await _set_plan(db, tenant.org_id, "starter")
    await _insert_agent(db, tenant, "second")

    count = await db.fetchval(
        "select count(*) from public.voice_agents where org_id = $1", tenant.org_id
    )
    assert count == 2


async def test_an_unlimited_plan_has_no_agent_ceiling(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    await db.execute(
        "update public.plan_entitlements set max_voice_agents = null where plan_id = 'growth'"
    )
    try:
        await _set_plan(db, tenant.org_id, "growth")
        for n in range(12):  # past growth's real limit of 10
            await _insert_agent(db, tenant, f"agent {n}")
    finally:
        await db.execute(
            "update public.plan_entitlements set max_voice_agents = $1 where plan_id = 'growth'",
            ladder()[PlanId.GROWTH].max_voice_agents,
        )


# --- the model-provider ceiling ---


async def _insert_ai_key(conn: asyncpg.Connection, tenant: Tenant, provider: str) -> None:
    async with _acting_as(conn, tenant.auth_user_id):
        await conn.execute(
            """
            insert into public.ai_provider_credentials
              (org_id, created_by, provider, api_key_encrypted)
            values ($1, $2, $3, 'ciphertext')
            """,
            tenant.org_id,
            tenant.user_id,
            provider,
        )


async def test_the_ai_key_ceiling_holds_against_raw_sql(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """Free allows two."""
    await _insert_ai_key(db, tenant, "sarvam")
    await _insert_ai_key(db, tenant, "deepgram")

    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await _insert_ai_key(db, tenant, "elevenlabs")


async def test_an_existing_ai_key_stays_rotatable_at_the_ceiling(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """The downgrade rule, and the reason the trigger is `before insert` only: a
    credential already stored must stay updatable, or a failed renewal strands a
    secret nobody can replace."""
    await _insert_ai_key(db, tenant, "sarvam")
    await _insert_ai_key(db, tenant, "deepgram")

    async with _acting_as(db, tenant.auth_user_id):
        await db.execute(
            """
            update public.ai_provider_credentials set api_key_encrypted = 'rotated'
            where org_id = $1 and provider = 'sarvam'
            """,
            tenant.org_id,
        )

    assert (
        await db.fetchval(
            """
            select api_key_encrypted from public.ai_provider_credentials
            where org_id = $1 and provider = 'sarvam'
            """,
            tenant.org_id,
        )
        == "rotated"
    )


# --- the workspace ceiling, inside the SECURITY DEFINER function ---


async def test_create_organisation_enforces_the_workspace_ceiling(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """Called directly, the way EXECUTE-defaults-to-PUBLIC allows. Free allows one
    organisation and signup already made it."""
    with pytest.raises(asyncpg.exceptions.CheckViolationError) as caught:
        async with _refused_as(db, tenant.auth_user_id):
            await db.fetch("select * from public.create_organisation($1)", "Second Workspace")

    assert "organisation" in str(caught.value)


async def test_a_higher_plan_permits_a_second_workspace(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    await _set_plan(db, tenant.org_id, "growth")

    async with _acting_as(db, tenant.auth_user_id):
        rows = await db.fetch("select * from public.create_organisation($1)", "Second Workspace")

    assert len(rows) == 1
    await db.execute("delete from public.organisations where id = $1", rows[0]["id"])


# --- the append-only and platform-internal tables ---


async def test_a_user_cannot_write_a_payment_row(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """Payments are written by the webhook through a definer function. A session
    forging one would be inventing a receipt."""
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with _refused_as(db, tenant.auth_user_id):
            await db.execute(
                """
                insert into public.payments
                  (org_id, gateway, gateway_payment_id, amount_minor, currency, status)
                values ($1, 'dodo', 'pay_forged', 1, 'INR', 'succeeded')
                """,
                tenant.org_id,
            )


async def test_a_user_cannot_read_the_webhook_event_log(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """A raw gateway payload can carry another organisation's data before we know
    whose it is, so this table has no policies and no grant at all."""
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with _refused_as(db, tenant.auth_user_id):
            await db.fetch("select * from public.payment_webhook_events")


async def test_a_user_cannot_edit_the_plan_catalogue(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """Reference data. Writable here would mean granting yourself any plan."""
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with _refused_as(db, tenant.auth_user_id):
            await db.execute(
                "update public.plan_entitlements set max_voice_agents = 999 where plan_id = 'free'"
            )


async def test_a_user_can_read_the_plan_catalogue(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """The plans page renders for everyone, so select must be permitted."""
    async with _acting_as(db, tenant.auth_user_id):
        rows = await db.fetch("select plan_id from public.plan_entitlements")
    assert len(rows) == len(PlanId)


# --- seats: the guard is on the membership insert, not the invitation -----------


async def _invite(
    conn: asyncpg.Connection, *, org_id: uuid.UUID, invited_by: uuid.UUID, email: str
) -> None:
    """A pending invitation, written as `postgres`. The point of these tests is the
    seat trigger, not the invitation route's own permission checks."""
    await conn.execute(
        """
        insert into public.invitations (org_id, email, role, token, invited_by, expires_at)
        values ($1, $2, 'operator', $3, $4, now() + interval '7 days')
        """,
        org_id,
        email,
        uuid.uuid4().hex,
        invited_by,
    )


async def test_a_membership_past_the_seat_limit_is_refused(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """The hole this closes: seats were counted when an invitation was *sent* and
    never again, so a downgrade between the invitation and the click let an
    organisation past its own limit one accept at a time."""
    await _set_plan(db, tenant.org_id, PlanId.FREE.value)  # 1 seat, already used

    joiner = await _create_tenant(db, "seat-over")
    try:
        with pytest.raises(asyncpg.exceptions.CheckViolationError, match="seat"):
            await db.execute(
                "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'operator')",
                tenant.org_id,
                joiner.user_id,
            )
    finally:
        await _as_postgres(db)
        await db.execute("delete from auth.users where id = $1", joiner.auth_user_id)


async def test_the_last_seat_is_actually_usable(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """The off-by-one worth a test of its own.

    The invitation being accepted is itself pending, so counting it against the
    seat it is claiming would make the final seat of every plan unreachable - the
    limit would silently be one lower than sold. Starter allows 3; with 1 member
    and this person's own pending invitation, the insert must succeed.
    """
    await _set_plan(db, tenant.org_id, PlanId.STARTER.value)

    joiner = await _create_tenant(db, "seat-last")
    try:
        email = await db.fetchval(
            "select email from public.users where id = $1", joiner.user_id
        )
        await _invite(db, org_id=tenant.org_id, invited_by=tenant.user_id, email=email)

        await db.execute(
            "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'operator')",
            tenant.org_id,
            joiner.user_id,
        )
        assert (
            await db.fetchval(
                "select count(*) from public.memberships where org_id = $1", tenant.org_id
            )
            == 2
        )
    finally:
        await _as_postgres(db)
        await db.execute("delete from auth.users where id = $1", joiner.auth_user_id)


async def test_someone_elses_pending_invitation_still_holds_a_seat(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """Two invitations into one free seat must not both be acceptable. Free allows
    1 seat and the owner holds it, so any outstanding invitation is already over."""
    await _set_plan(db, tenant.org_id, PlanId.STARTER.value)  # 3 seats
    await _invite(db, org_id=tenant.org_id, invited_by=tenant.user_id, email="a@brbik.com")
    await _invite(db, org_id=tenant.org_id, invited_by=tenant.user_id, email="b@brbik.com")

    # 1 member + 2 pending invitations for other people = 3 of 3 taken.
    joiner = await _create_tenant(db, "seat-third")
    try:
        with pytest.raises(asyncpg.exceptions.CheckViolationError, match="seat"):
            await db.execute(
                "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'operator')",
                tenant.org_id,
                joiner.user_id,
            )
    finally:
        await _as_postgres(db)
        await db.execute("delete from auth.users where id = $1", joiner.auth_user_id)


async def test_signup_still_creates_a_first_organisation_on_every_plan(
    db: asyncpg.Connection,
) -> None:
    """The exemption that must never regress. `handle_new_auth_user()` inserts the
    first membership of a brand-new organisation, and a seat limit that can fail
    there is an outage, not a limit - nobody could sign up at all."""
    fresh = await _create_tenant(db, "seat-signup")
    try:
        assert fresh.org_id is not None
    finally:
        await _as_postgres(db)
        await db.execute("delete from auth.users where id = $1", fresh.auth_user_id)
