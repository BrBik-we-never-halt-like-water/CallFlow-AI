"""The usage-credit ledger's SQL functions, against the real database.

`tests/test_rates.py` proves the pure arithmetic is right. `services/credit.py`
is exercised indirectly by `test_entitlements.py` and `test_payment_gating.py`.
Neither ever drives `credit_append`/`credit_settle`/`credit_release_stale_holds`
against real Postgres, or proves the append-only guard - and the caller check
added alongside it (migration `202608221000`, closing a real cross-tenant hole:
`credit_append` took `target_org_id` as a plain argument with nothing checking
the caller belonged to it) - actually hold. The same gap
`test_entitlement_enforcement.py`'s own docstring warns about for any tenant
table: a limit enforced only in Python is decoration against anyone holding a
database connection (CLAUDE.md §4b).

Every call below goes through `_acting_as`/`_as_anon` rather than the bare
`db` connection, which connects with the database owner's own credentials
(effectively `postgres`) - calling a credit function that way is neither the
`authenticated` nor the `anon` path production ever uses, and since
`202608221000` it is not authorized either: `current_user` would be
`postgres`, which is not `anon` and (having no `auth.uid()`) is never an org
member, so every call would raise. Acting as a real tenant or as `anon` is
what exercises the actual, intended paths.

Skipped when DATABASE_URL is unset, so the suite still runs offline - which is
also why CI, which sets no database, never exercises any of this.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
import pytest
import pytest_asyncio

from app.core.config import config
from app.database.repositories import credits as credits_repo

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
        f"credit-{label}-{auth_user_id.hex[:8]}@brbik.com",
        json.dumps({"full_name": f"Credit {label}"}),
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
    """Run a block as one signed-in user, with RLS in force - `database.as_user()`'s
    shape. See `test_entitlement_enforcement.py`'s copy of this helper for why the
    transaction is not optional."""
    claims = json.dumps({"sub": str(auth_user_id), "role": "authenticated"})
    async with conn.transaction():
        await conn.execute("select set_config('request.jwt.claims', $1, true)", claims)
        await conn.execute("select set_config('role', 'authenticated', true)")
        yield conn


@asynccontextmanager
async def _refused_as(
    conn: asyncpg.Connection, auth_user_id: uuid.UUID
) -> AsyncIterator[asyncpg.Connection]:
    """`_acting_as`, but always rolled back - for the tests that assert a write
    is refused, so a regression cannot commit a row a later test then trips
    over."""
    claims = json.dumps({"sub": str(auth_user_id), "role": "authenticated"})
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute("select set_config('request.jwt.claims', $1, true)", claims)
        await conn.execute("select set_config('role', 'authenticated', true)")
        yield conn
    finally:
        await tx.rollback()


@asynccontextmanager
async def _as_anon(conn: asyncpg.Connection) -> AsyncIterator[asyncpg.Connection]:
    """`database.anonymous()`'s shape - the one other role a credit function
    trusts unconditionally, because the webhook path has already verified the
    gateway's signature in Python before it ever reaches SQL."""
    async with conn.transaction():
        await conn.execute("select set_config('role', 'anon', true)")
        yield conn


async def _as_postgres(conn: asyncpg.Connection) -> None:
    await conn.execute("select set_config('role', 'postgres', true)")
    await conn.execute("select set_config('request.jwt.claims', '', true)")


@pytest_asyncio.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(config.database_url, timeout=30)
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


@pytest_asyncio.fixture
async def other_tenant(db: asyncpg.Connection) -> AsyncIterator[Tenant]:
    created = await _create_tenant(db, "two")
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


# --- the ledger is append-only, and org-scoped, from the API's perspective -----


async def test_a_direct_insert_as_authenticated_raises(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """`credit_append` is the only write path - `insert` is revoked from
    `authenticated`. If this ever passes, every grant/hold/settle in this file
    is decoration: anyone with a connection could credit their own account by
    hand."""
    async with _refused_as(db, tenant.auth_user_id):
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await db.execute(
                """
                insert into public.credit_ledger
                    (org_id, entry_kind, amount_minor, currency, dedupe_key)
                values ($1, 'grant', 100000, 'INR', 'forged')
                """,
                tenant.org_id,
            )


async def test_cannot_forge_a_grant_into_another_organisation(
    db: asyncpg.Connection, tenant: Tenant, other_tenant: Tenant
) -> None:
    """The hole migration `202608221000` closes: before it, any authenticated
    user could call `credit_append` with someone else's `org_id` and grant
    themselves that organisation's credit. Proven here against a *real* other
    organisation, not just a random id nothing owns."""
    async with _refused_as(db, tenant.auth_user_id):
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await db.fetchval(
                "select public.credit_append($1, null, 'grant', 100000, $2, null, null, null)",
                other_tenant.org_id,
                f"forged:{uuid.uuid4()}",
            )


async def test_cannot_read_another_organisations_balance(
    db: asyncpg.Connection, tenant: Tenant, other_tenant: Tenant
) -> None:
    """The read-direction half of the same hole: `credit_balance` took
    `target_org_id` with no check either, so any signed-in user could read any
    other organisation's balance."""
    async with _acting_as(db, other_tenant.auth_user_id):
        await credits_repo.grant(
            db, org_id=other_tenant.org_id, amount_paise=75_000, dedupe_key="other-org-grant"
        )
    async with _acting_as(db, tenant.auth_user_id):
        leaked = await credits_repo.balance(db, other_tenant.org_id)
    assert leaked == 0


async def test_cross_tenant_read_is_filtered_by_rls(
    db: asyncpg.Connection, tenant: Tenant, other_tenant: Tenant
) -> None:
    """A grant on one organisation must not be visible to another, even though
    both connections share the same underlying table."""
    async with _acting_as(db, tenant.auth_user_id):
        await credits_repo.grant(
            db, org_id=tenant.org_id, amount_paise=50_000, dedupe_key="visibility-check"
        )
    async with _acting_as(db, other_tenant.auth_user_id):
        rows = await db.fetch(
            "select * from public.credit_ledger where dedupe_key = 'visibility-check'"
        )
    assert rows == []


# --- hold, settle, and the reaper -----------------------------------------------


async def test_settle_releases_the_hold_and_charges_the_duration(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    call_key = f"run-x:Asha:{uuid.uuid4().hex[:6]}"
    async with _acting_as(db, tenant.auth_user_id):
        placed = await credits_repo.hold(
            db,
            org_id=tenant.org_id,
            user_id=tenant.user_id,
            call_key=call_key,
            amount_paise=900,
            rate_paise_per_minute=150,
        )
        assert placed is True
        assert await credits_repo.balance(db, tenant.org_id) == -900

        settled = await credits_repo.settle(
            db,
            org_id=tenant.org_id,
            user_id=tenant.user_id,
            call_key=call_key,
            spend_paise=613,
            rate_paise_per_minute=150,
        )
        assert settled is True
        # The hold (-900) is released (+900) and the actual spend (-613) charged,
        # in the same statement - net -613, not -900 and not -1513.
        assert await credits_repo.balance(db, tenant.org_id) == -613


async def test_replaying_a_settle_does_not_spend_twice(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """The exact guarantee a retried worker callback depends on: `dedupe_key`
    makes a second delivery of the same completion a no-op, not a second
    charge."""
    call_key = f"run-y:Rahul:{uuid.uuid4().hex[:6]}"
    async with _acting_as(db, tenant.auth_user_id):
        await credits_repo.hold(
            db,
            org_id=tenant.org_id,
            user_id=tenant.user_id,
            call_key=call_key,
            amount_paise=900,
            rate_paise_per_minute=150,
        )
        first = await credits_repo.settle(
            db,
            org_id=tenant.org_id,
            user_id=tenant.user_id,
            call_key=call_key,
            spend_paise=613,
            rate_paise_per_minute=150,
        )
        balance_after_first = await credits_repo.balance(db, tenant.org_id)
        assert first is True
        assert balance_after_first == -613

        second = await credits_repo.settle(
            db,
            org_id=tenant.org_id,
            user_id=tenant.user_id,
            call_key=call_key,
            spend_paise=613,
            rate_paise_per_minute=150,
        )
        assert second is False
        assert await credits_repo.balance(db, tenant.org_id) == balance_after_first


async def test_a_call_that_never_connects_releases_its_hold_in_full(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    call_key = f"run-z:Meera:{uuid.uuid4().hex[:6]}"
    async with _acting_as(db, tenant.auth_user_id):
        await credits_repo.hold(
            db,
            org_id=tenant.org_id,
            user_id=tenant.user_id,
            call_key=call_key,
            amount_paise=900,
            rate_paise_per_minute=150,
        )
        settled = await credits_repo.settle(
            db,
            org_id=tenant.org_id,
            user_id=tenant.user_id,
            call_key=call_key,
            spend_paise=0,
            rate_paise_per_minute=150,
        )
        assert settled is True
        assert await credits_repo.balance(db, tenant.org_id) == 0


async def test_release_stale_holds_gives_back_an_abandoned_hold(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """A worker that dies mid-call leaves a hold nobody ever settles. The
    reaper - `sweep_stale_holds` in production, `release_stale_holds` here at
    the repository layer - is what gives it back rather than pinning that
    credit forever.

    Run as `anon`: the reaper sweeps every organisation's stale holds in one
    pass, and no single authenticated session is ever a member of every
    organisation - `anon` is the only role `credit_append` trusts for a row it
    was not asked about by its own org's session, which is also why this
    reaper can only ever run from the same anonymous, system-level context the
    webhook path uses (or a future `privileged.acquire()` call), never from an
    ordinary user session.
    """
    call_key = f"run-stale:Zoya:{uuid.uuid4().hex[:6]}"
    async with _acting_as(db, tenant.auth_user_id):
        await credits_repo.hold(
            db,
            org_id=tenant.org_id,
            user_id=tenant.user_id,
            call_key=call_key,
            amount_paise=900,
            rate_paise_per_minute=150,
        )
        assert await credits_repo.balance(db, tenant.org_id) == -900

    async with _as_anon(db):
        # `older_than_seconds=0` treats every hold, however fresh, as stale -
        # the simplest way to exercise the reaper without actually waiting.
        released = await credits_repo.release_stale_holds(db, older_than_seconds=0)
    assert released >= 1

    async with _acting_as(db, tenant.auth_user_id):
        assert await credits_repo.balance(db, tenant.org_id) == 0
