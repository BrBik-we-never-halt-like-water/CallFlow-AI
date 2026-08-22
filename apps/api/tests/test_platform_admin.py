"""The first cross-tenant privilege boundary in the application.

CLAUDE.md calls cross-tenant access the most severe bug class this product can
ship, so these are the tests that matter most in the platform surface - and the
first assertion is the one that would be missing from a route-only design:

**Postgres grants function EXECUTE to PUBLIC unless revoked.** An ordinary
authenticated user can therefore call `platform_set_org_entitlements` directly over
SQL, with no route and no dependency involved. If that succeeds, every FastAPI
dependency in `auth/platform.py` is decoration. It is asserted first here for the
same reason it is checked first in each function.

Every write below goes through raw SQL as the *user*, never through a repository,
because a repository is the layer these tests exist to bypass.

Skipped when DATABASE_URL is unset, so the suite still runs offline.
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

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not config.database_url, reason="DATABASE_URL is not configured"),
]

ALL_CAPABILITIES = [
    "orgs:read",
    "data:read",
    "pii:reveal",
    "entitlements:write",
    "data:write",
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
        f"plat-{label}-{auth_user_id.hex[:8]}@brbik.com",
        {"full_name": f"Plat {label}"},
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
    conn: asyncpg.Connection, auth_user_id: uuid.UUID, *, platform_session: str | None = None
) -> AsyncIterator[asyncpg.Connection]:
    """One signed-in user, RLS in force, always rolled back.

    The transaction is not optional: `set_config(..., true)` is transaction-local, so
    outside one the role switch lasts a single statement and everything after it runs
    as `postgres`, which holds BYPASSRLS. A test written that way does not fail - it
    passes for the wrong reason, proving only that a superuser can do something
    nobody doubted.

    Rolled back unconditionally because most assertions here are that a write is
    *refused*. If a boundary regresses, the write succeeds, and committing it would
    corrupt the fixtures for every later test in the run.
    """
    claims = json.dumps({"sub": str(auth_user_id), "role": "authenticated"})
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute("select set_config('request.jwt.claims', $1, true)", claims)
        await conn.execute("select set_config('role', 'authenticated', true)")
        if platform_session is not None:
            await conn.execute(
                "select set_config('callflow.platform_session', $1, true)", platform_session
            )
        yield conn
    finally:
        await tx.rollback()


@asynccontextmanager
async def _refused(conn: asyncpg.Connection) -> AsyncIterator[None]:
    """A savepoint around one expected refusal.

    Postgres aborts the whole transaction on a failed statement, so a test making
    two "this is refused" assertions in one block would see the second die with
    `InFailedSQLTransactionError` - passing or failing for a reason unrelated to the
    boundary under test. A savepoint scopes the abort to the one statement.
    """
    await conn.execute("savepoint expect_refusal")
    try:
        yield
    finally:
        await conn.execute("rollback to savepoint expect_refusal")


async def _as_postgres(conn: asyncpg.Connection) -> None:
    await conn.execute("select set_config('role', 'postgres', true)")
    await conn.execute("select set_config('request.jwt.claims', '', true)")
    await conn.execute("select set_config('callflow.platform_session', '', true)")


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
    """An ordinary customer. Never a platform admin."""
    created = await _create_tenant(db, "cust")
    try:
        yield created
    finally:
        await _cleanup(db, created)


@pytest_asyncio.fixture
async def other(db: asyncpg.Connection) -> AsyncIterator[Tenant]:
    created = await _create_tenant(db, "other")
    try:
        yield created
    finally:
        await _cleanup(db, created)


@pytest_asyncio.fixture
async def admin(db: asyncpg.Connection) -> AsyncIterator[Tenant]:
    """A platform admin holding every capability."""
    created = await _create_tenant(db, "admin")
    await db.execute(
        "insert into public.platform_admins (user_id, capabilities) values ($1, $2::text[])",
        created.user_id,
        ALL_CAPABILITIES,
    )
    try:
        yield created
    finally:
        await _as_postgres(db)
        await db.execute(
            "delete from public.platform_admins where user_id = $1", created.user_id
        )
        await _cleanup(db, created)


async def _cleanup(conn: asyncpg.Connection, t: Tenant) -> None:
    await _as_postgres(conn)
    await conn.execute("delete from public.platform_audit_log where target_org_id = $1", t.org_id)
    await conn.execute("delete from public.org_entitlement_overrides where org_id = $1", t.org_id)
    await conn.execute("delete from auth.users where id = $1", t.auth_user_id)
    await conn.execute(
        """
        delete from public.organisations o
         where not exists (select 1 from public.memberships m where m.org_id = o.id)
        """
    )


# --- the hole a route-only check would leave ------------------------------------


async def test_an_ordinary_user_calling_the_write_function_directly_is_refused(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """The single most important assertion in this file.

    Function EXECUTE defaults to PUBLIC, so this call needs no route, no dependency
    and no permission. If the check inside the function were missing, every
    customer could grant themselves unlimited entitlements over SQL and the FastAPI
    layer would never see it.
    """
    async with _acting_as(db, tenant.auth_user_id):
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await db.execute(
                """
                select public.platform_set_org_entitlements(
                  $1, 9999, 9999, 9999, 9999, 9999, 9999, '{}'::text[], null, 'self-serve')
                """,
                tenant.org_id,
            )


async def test_an_ordinary_user_cannot_set_their_own_plan(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    async with _acting_as(db, tenant.auth_user_id):
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await db.execute(
                "select public.platform_set_org_plan($1, 'growth', 'free upgrade')",
                tenant.org_id,
            )


async def test_setting_the_session_flag_alone_grants_nothing(
    db: asyncpg.Connection, tenant: Tenant, other: Tenant
) -> None:
    """Both halves are required. The flag is the opt-in; the `platform_admins` row
    is the authority. A customer who discovers the variable name and sets it must
    gain nothing at all."""
    async with _acting_as(db, tenant.auth_user_id, platform_session="pretending"):
        assert await db.fetchval("select public.platform_can_read($1)", other.org_id) is False
        assert (
            await db.fetchval(
                "select count(*) from public.organisations where id = $1", other.org_id
            )
            == 0
        )


async def test_a_platform_admin_browsing_normally_sees_only_their_own_orgs(
    db: asyncpg.Connection, admin: Tenant, other: Tenant
) -> None:
    """Elevation is per-session and explicit, never ambient. Without the flag, a
    platform admin is the ordinary org member they are - which is what makes it safe
    for staff to hold a standing grant."""
    async with _acting_as(db, admin.auth_user_id):
        assert (
            await db.fetchval(
                "select count(*) from public.organisations where id = $1", other.org_id
            )
            == 0
        )


# --- the read path ---------------------------------------------------------------


async def test_an_elevated_session_reads_across_organisations(
    db: asyncpg.Connection, admin: Tenant, other: Tenant
) -> None:
    async with _acting_as(db, admin.auth_user_id, platform_session="ticket #412"):
        assert (
            await db.fetchval(
                "select count(*) from public.organisations where id = $1", other.org_id
            )
            == 1
        )


async def test_team_chat_stays_invisible_even_to_an_elevated_session(
    db: asyncpg.Connection, admin: Tenant
) -> None:
    """`channels`, `channel_members` and `messages` are deliberately out of scope: a
    customer's internal team chat is the most privacy-sensitive table in the schema
    and the least useful for debugging a call (`docs/PLATFORM_ADMIN.md` §4). This
    fails if someone adds them to `READ_SCOPE` without deciding to."""
    async with _acting_as(db, admin.auth_user_id, platform_session="ticket #412"):
        for table in ("channels", "channel_members", "messages"):
            widened = await db.fetchval(
                """
                select exists (
                  select 1 from pg_policies
                   where schemaname = 'public' and tablename = $1
                     and qual like '%platform_can_read%'
                )
                """,
                table,
            )
            assert widened is False, f"{table} should not be platform-readable"


async def test_no_write_policy_anywhere_references_the_platform_predicate(
    db: asyncpg.Connection,
) -> None:
    """The structural guarantee behind "this is not a write bypass".

    `platform_can_read` may appear only on `select` policies. One appearance in an
    insert, update or delete policy - or in a `with check` clause - would hand a
    platform admin cross-tenant write access as a side effect, which is exactly the
    trap that ruled out extending `has_org_role` (`docs/PLATFORM_ADMIN.md` §3).
    """
    leaked = await db.fetch(
        """
        select tablename, policyname, cmd
          from pg_policies
         where schemaname = 'public'
           and (cmd <> 'SELECT' or with_check like '%platform_can_read%')
           and (qual like '%platform_can_read%' or with_check like '%platform_can_read%')
        """
    )
    assert leaked == [], f"platform_can_read leaked into: {[dict(r) for r in leaked]}"


async def test_the_elevated_session_cannot_write(
    db: asyncpg.Connection, admin: Tenant, other: Tenant
) -> None:
    """`readonly=True` on the transaction, asserted here rather than trusted.

    With all-orgs visibility this is the only thing between a platform admin and a
    cross-tenant write, which is why it lives in `as_platform_reader` and never at a
    call site. Postgres refuses regardless of what any policy would have permitted.
    """
    tx = db.transaction(readonly=True)
    await tx.start()
    try:
        claims = json.dumps({"sub": str(admin.auth_user_id), "role": "authenticated"})
        await db.execute("select set_config('request.jwt.claims', $1, true)", claims)
        await db.execute("select set_config('role', 'authenticated', true)")
        await db.execute("select set_config('callflow.platform_session', 'ticket', true)")
        with pytest.raises(asyncpg.exceptions.ReadOnlySQLTransactionError):
            await db.execute(
                "update public.organisations set name = 'seized' where id = $1", other.org_id
            )
    finally:
        await tx.rollback()
        await _as_postgres(db)


# --- the identity table itself ---------------------------------------------------


async def test_platform_admins_is_unreachable_as_an_authenticated_user(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """No policies and no grant, so it is invisible and unwritable through the API
    entirely. This is what makes "no endpoint anywhere creates a platform_admins
    row" structural rather than a convention someone can forget."""
    async with _acting_as(db, tenant.auth_user_id):
        async with _refused(db):
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                await db.fetch("select * from public.platform_admins")
        async with _refused(db):
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                await db.execute(
                    "insert into public.platform_admins (user_id, capabilities) "
                    "values ($1, '{entitlements:write}'::text[])",
                    tenant.user_id,
                )


async def test_a_platform_admin_cannot_read_or_edit_the_admin_table_either(
    db: asyncpg.Connection, admin: Tenant
) -> None:
    """Granting platform admin stays out of band even though *using* it does not. A
    superuser tier that can grant itself through its own API is the classic
    escalation hole."""
    async with _acting_as(db, admin.auth_user_id, platform_session="ticket #412"):
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await db.fetch("select * from public.platform_admins")


async def test_the_audit_log_is_invisible_and_unwritable_to_everyone(
    db: asyncpg.Connection, admin: Tenant
) -> None:
    """The log must not be readable, writable or deletable by the person it
    records - reachable only through `platform_read_audit`, which checks a
    capability."""
    async with _acting_as(db, admin.auth_user_id, platform_session="ticket #412"):
        async with _refused(db):
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                await db.fetch("select * from public.platform_audit_log")
        async with _refused(db):
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                await db.execute("delete from public.platform_audit_log")


async def test_an_unknown_capability_cannot_be_stored(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """A typo'd capability would grant nothing and look like it granted something -
    a grant that silently does not work is worse than one that is refused."""
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await db.execute(
            "insert into public.platform_admins (user_id, capabilities) "
            "values ($1, '{orgs:reed}'::text[])",
            tenant.user_id,
        )


async def test_an_expired_grant_stops_working(
    db: asyncpg.Connection, tenant: Tenant, other: Tenant
) -> None:
    await db.execute(
        """
        insert into public.platform_admins (user_id, capabilities, expires_at)
        values ($1, $2::text[], now() - interval '1 minute')
        """,
        tenant.user_id,
        ALL_CAPABILITIES,
    )
    try:
        async with _acting_as(db, tenant.auth_user_id, platform_session="ticket"):
            assert (
                await db.fetchval("select public.platform_can_read($1)", other.org_id) is False
            )
    finally:
        await _as_postgres(db)
        await db.execute(
            "delete from public.platform_admins where user_id = $1", tenant.user_id
        )


# --- the write path, and the audit trail behind it -------------------------------


async def test_a_platform_write_lands_an_audit_row_with_before_after_and_reason(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant
) -> None:
    async with _acting_as(db, admin.auth_user_id) as conn:
        await conn.execute(
            "select public.platform_set_org_plan($1, 'growth', 'signed order form #88')",
            tenant.org_id,
        )
        # Through `platform_read_audit`, not a direct select: the table grants
        # nothing to `authenticated` (asserted above), so the definer function is
        # the only read path a platform admin has - which this exercises too.
        rows = await conn.fetch("select * from public.platform_read_audit(20)")
        row = next((r for r in rows if r["target_org_id"] == tenant.org_id), None)
        assert row is not None
        assert row["actor_user_id"] == admin.user_id
        assert row["action"] == "org.plan_set"
        assert row["reason"] == "signed order form #88"
        assert row["before_state"]["plan_id"] == "free"
        assert row["after_state"]["plan_id"] == "growth"


async def test_a_platform_write_without_a_reason_is_refused(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant
) -> None:
    """The reason is the only thing that makes an all-orgs session reconstructable
    later, so it is mandatory in the database rather than validated in a route."""
    async with _acting_as(db, admin.auth_user_id) as conn:
        with pytest.raises(asyncpg.exceptions.InvalidParameterValueError, match="reason"):
            await conn.execute(
                "select public.platform_set_org_plan($1, 'growth', '   ')", tenant.org_id
            )


async def test_an_override_raises_the_limit_the_triggers_enforce(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant
) -> None:
    """The whole point of the enterprise tier: the override has to reach the SQL
    guards, not just the Billing display."""
    async with _acting_as(db, admin.auth_user_id) as conn:
        assert await conn.fetchval(
            "select public.effective_limit($1, 'max_voice_agents')", tenant.org_id
        ) == 1  # Free

        await conn.execute(
            """
            select public.platform_set_org_entitlements(
              $1, 42, null, null, null, null, null, '{}'::text[], 'negotiated', 'deal #7')
            """,
            tenant.org_id,
        )
        assert await conn.fetchval(
            "select public.effective_limit($1, 'max_voice_agents')", tenant.org_id
        ) == 42
        # Unset limits still inherit the plan rather than becoming unlimited.
        assert await conn.fetchval(
            "select public.effective_limit($1, 'max_seats')", tenant.org_id
        ) == 1


async def test_unlimited_is_expressible_and_distinct_from_unset(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant
) -> None:
    """A null column means "inherit the plan" and `0` is a real ceiling, so
    "no cap at all" needs its own channel. Without the `unlimited` array an
    enterprise customer could never be given the uncapped allowance they bought."""
    async with _acting_as(db, admin.auth_user_id) as conn:
        await conn.execute(
            """
            select public.platform_set_org_entitlements(
              $1, null, null, null, null, null, null,
              '{max_voice_agents}'::text[], null, 'deal #7 unlimited agents')
            """,
            tenant.org_id,
        )
        assert (
            await conn.fetchval(
                "select public.effective_limit($1, 'max_voice_agents')", tenant.org_id
            )
            is None
        )


async def test_zero_stays_a_real_enforced_ceiling(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant
) -> None:
    """`0` must not be collapsed into "unset" by a falsiness check anywhere in the
    chain - it is the only way to say "this customer may create none"."""
    async with _acting_as(db, admin.auth_user_id) as conn:
        await conn.execute(
            """
            select public.platform_set_org_entitlements(
              $1, 0, null, null, null, null, null, '{}'::text[], null, 'suspended #9')
            """,
            tenant.org_id,
        )
        assert await conn.fetchval(
            "select public.effective_limit($1, 'max_voice_agents')", tenant.org_id
        ) == 0


async def test_an_override_of_nothing_removes_the_row(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant
) -> None:
    """Otherwise Billing reports "limits agreed for this organisation" to a customer
    plainly on their plan's own numbers."""
    async with _acting_as(db, admin.auth_user_id) as conn:
        await conn.execute(
            """
            select public.platform_set_org_entitlements(
              $1, 42, null, null, null, null, null, '{}'::text[], null, 'deal #7')
            """,
            tenant.org_id,
        )
        await conn.execute(
            """
            select public.platform_set_org_entitlements(
              $1, null, null, null, null, null, null, '{}'::text[], null, 'deal #7 ended')
            """,
            tenant.org_id,
        )
        assert (
            await conn.fetchval(
                "select count(*) from public.org_entitlement_overrides where org_id = $1",
                tenant.org_id,
            )
            == 0
        )


async def test_an_override_on_one_org_never_changes_another(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant, other: Tenant
) -> None:
    async with _acting_as(db, admin.auth_user_id) as conn:
        await conn.execute(
            """
            select public.platform_set_org_entitlements(
              $1, 99, null, null, null, null, null, '{}'::text[], null, 'deal #7')
            """,
            tenant.org_id,
        )
        assert await conn.fetchval(
            "select public.effective_limit($1, 'max_voice_agents')", other.org_id
        ) == 1


async def test_a_customer_can_read_their_own_agreed_limits_but_not_write_them(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant, other: Tenant
) -> None:
    """Billing shows "limits agreed for this organisation", so the customer has to
    be able to read the row - and must not be able to edit it, nor see anyone
    else's."""
    await db.execute(
        """
        insert into public.org_entitlement_overrides (org_id, max_voice_agents, note)
        values ($1, 42, 'negotiated')
        """,
        tenant.org_id,
    )
    try:
        async with _acting_as(db, tenant.auth_user_id) as conn:
            assert (
                await conn.fetchval(
                    "select max_voice_agents from public.org_entitlement_overrides "
                    "where org_id = $1",
                    tenant.org_id,
                )
                == 42
            )
            # RLS refuses this *silently*, and the distinction matters enough to
            # assert precisely. `InsufficientPrivilegeError` comes from a missing
            # GRANT, and Supabase grants `authenticated` full DML on every table
            # in `public` - so the grant is there. What stops the write is that
            # `org_entitlement_overrides` has a SELECT policy and no UPDATE one,
            # which makes zero rows visible to update rather than raising.
            #
            # Asserting the row count and the value is also the stronger check:
            # an exception only proves the statement failed, while `UPDATE 0` plus
            # an unchanged 42 proves nothing was written.
            async with _refused(conn):
                assert (
                    await conn.execute(
                        "update public.org_entitlement_overrides set max_voice_agents = 999 "
                        "where org_id = $1",
                        tenant.org_id,
                    )
                    == "UPDATE 0"
                )
                assert (
                    await conn.fetchval(
                        "select max_voice_agents from public.org_entitlement_overrides "
                        "where org_id = $1",
                        tenant.org_id,
                    )
                    == 42
                )

        async with _acting_as(db, other.auth_user_id) as conn:
            assert (
                await conn.fetchval(
                    "select count(*) from public.org_entitlement_overrides where org_id = $1",
                    tenant.org_id,
                )
                == 0
            )
    finally:
        await _as_postgres(db)
        await db.execute(
            "delete from public.org_entitlement_overrides where org_id = $1", tenant.org_id
        )


async def test_a_plan_the_deployment_does_not_offer_is_refused(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant
) -> None:
    """`organisations.plan_id` is free text with a CHECK, and the entitlement
    resolver falls back to Free on anything unrecognised - so a typo'd plan would
    silently *downgrade* a customer who had just signed a contract."""
    async with _acting_as(db, admin.auth_user_id) as conn:
        with pytest.raises(asyncpg.exceptions.InvalidParameterValueError, match="plan"):
            await conn.execute(
                "select public.platform_set_org_plan($1, 'groth', 'typo')", tenant.org_id
            )


async def test_an_unknown_limit_name_in_unlimited_is_refused(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant
) -> None:
    async with _acting_as(db, admin.auth_user_id) as conn:
        with pytest.raises(asyncpg.exceptions.InvalidParameterValueError):
            await conn.execute(
                """
                select public.platform_set_org_entitlements(
                  $1, null, null, null, null, null, null,
                  '{max_wishes}'::text[], null, 'deal #7')
                """,
                tenant.org_id,
            )


# --- the endpoints' own queries, which a policy test does not exercise ----------


async def test_the_org_list_actually_runs_and_counts(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant
) -> None:
    """Calls the function rather than asserting about policies.

    Worth its own test because `returns table` signatures are not checked against
    the query at creation time - a column type mismatch creates cleanly and raises
    only when someone runs it. `organisations.slug` is `citext` against a declared
    `text`, and that is exactly how this shipped broken the first time.
    """
    async with _acting_as(db, admin.auth_user_id) as conn:
        rows = await conn.fetch("select * from public.platform_list_organisations(null)")
        mine = next((r for r in rows if r["org_id"] == tenant.org_id), None)
        assert mine is not None
        assert mine["member_count"] == 1
        assert mine["has_override"] is False
        assert mine["plan_id"] == "free"


async def test_the_org_list_search_filters(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant
) -> None:
    async with _acting_as(db, admin.auth_user_id) as conn:
        name = await conn.fetchval(
            "select name from public.organisations where id = $1", tenant.org_id
        )
        hits = await conn.fetch(
            "select * from public.platform_list_organisations($1)", name
        )
        assert any(r["org_id"] == tenant.org_id for r in hits)

        misses = await conn.fetch(
            "select * from public.platform_list_organisations($1)",
            "zzz-no-such-organisation-zzz",
        )
        assert misses == []


async def test_an_ordinary_user_cannot_list_organisations(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    async with _acting_as(db, tenant.auth_user_id) as conn:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.fetch("select * from public.platform_list_organisations(null)")


async def test_an_ordinary_user_cannot_read_the_audit_function(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    async with _acting_as(db, tenant.auth_user_id) as conn:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.fetch("select * from public.platform_read_audit(10)")


async def test_the_override_getter_runs_and_is_capability_checked(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant
) -> None:
    async with _acting_as(db, admin.auth_user_id) as conn:
        assert await conn.fetch(
            "select * from public.platform_get_override($1)", tenant.org_id
        ) == []
        await conn.execute(
            """
            select public.platform_set_org_entitlements(
              $1, 7, null, null, null, null, null, '{}'::text[], null, 'deal #7')
            """,
            tenant.org_id,
        )
        rows = await conn.fetch(
            "select * from public.platform_get_override($1)", tenant.org_id
        )
        assert len(rows) == 1
        assert rows[0]["max_voice_agents"] == 7

    async with _acting_as(db, tenant.auth_user_id) as conn:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.fetch(
                "select * from public.platform_get_override($1)", tenant.org_id
            )


# --- as_platform_reader: the elevated read, end to end --------------------------


async def test_the_elevated_read_returns_another_tenants_runs(
    db: asyncpg.Connection, admin: Tenant, tenant: Tenant
) -> None:
    """What `as_platform_reader` is for, exercised through the same query the route
    runs - a plain select whose visibility comes from `platform_can_read` on
    `runs_select`, not from a definer function bypassing the policy."""
    # No campaign scaffolding: `d7e4c1b9f682` dropped `campaigns` and
    # `runs.campaign_id` when runs became agent-driven, and this test only ever
    # needed *a* run to exist for the platform reader to find. `voice_agent_id`
    # is nullable, so a bare run is still a valid row.
    run_id = f"plat-run-{uuid.uuid4().hex[:8]}"
    await db.execute(
        """
        insert into public.runs (id, org_id, status, total, started_by)
        values ($1, $2, 'queued', 0, $3)
        """,
        run_id,
        tenant.org_id,
        tenant.user_id,
    )

    async with _acting_as(db, admin.auth_user_id, platform_session="ticket #412") as conn:
        rows = await conn.fetch(
            "select id, org_id from public.runs where org_id = $1", tenant.org_id
        )
        assert [r["id"] for r in rows] == [run_id]

    # And without the flag, the very same query as the very same admin sees nothing.
    async with _acting_as(db, admin.auth_user_id) as conn:
        assert (
            await conn.fetchval(
                "select count(*) from public.runs where org_id = $1", tenant.org_id
            )
            == 0
        )


async def test_as_platform_reader_refuses_a_blank_reason() -> None:
    """Checked in the primitive, not at a call site - the same discipline
    `privileged.acquire` applies, and for the same reason: a reason that can be
    skipped is a reason nobody writes."""
    from app.database import database

    for blank in ("", "   "):
        with pytest.raises(ValueError, match="reason"):
            async with database.as_platform_reader(uuid.uuid4(), reason=blank):
                pass


async def test_a_non_admin_cannot_open_an_elevated_session(
    db: asyncpg.Connection, tenant: Tenant
) -> None:
    """`platform_open_read_session` raises 42501, which is what makes the database -
    not the route dependency - the boundary. A handler that forgot its dependency
    still cannot open an elevated session."""
    async with _acting_as(db, tenant.auth_user_id) as conn:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.execute("select public.platform_open_read_session('sneaking in')")
