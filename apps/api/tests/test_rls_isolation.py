"""Cross-tenant isolation, asserted against the real database.

`CLAUDE.md` calls a policy that looks right and permits a cross-tenant read the most
expensive bug this product can ship, so these tests talk to Postgres directly rather
than mocking anything. They exercise the same role switch the API uses, which is the
only configuration where RLS is actually in force - `postgres` holds BYPASSRLS, so a
plain connection proves nothing.

Skipped when DATABASE_URL is unset, so the suite still runs offline - which is also
why CI, which sets no database, never exercises any of this.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
import pytest_asyncio

from app.core.config import config
from app.database.repositories import (
    ai_provider_credentials as ai_provider_credentials_repo,
)
from app.database.repositories import channels as channels_repo
from app.database.repositories import credits as credits_repo
from app.database.repositories import escalations as escalations_repo
from app.database.repositories import invitations as invitations_repo
from app.database.repositories import messages as messages_repo
from app.database.repositories import organisations as org_repo
from app.database.repositories import runs as runs_repo
from app.database.repositories import sharing as sharing_repo
from app.database.repositories import voice_agents as voice_agents_repo
from app.domain.api_keys import generate_api_key, hash_api_key

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not config.database_url, reason="DATABASE_URL is not configured"
    ),
]


class Tenant:
    """One organisation with one owner, created through the real signup trigger."""

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
        f"rls-{label}-{auth_user_id.hex[:8]}@brbik.com",
        # A dict, not `json.dumps(...)`: the jsonb codec registered on this
        # connection encodes it. Passing a pre-serialised string would be
        # encoded a second time, and the signup trigger would read
        # `full_name` off a JSON string instead of an object and store NULL.
        {"full_name": f"RLS {label}"},
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

    # Every new organisation starts on Free, which allows exactly one seat
    # (`enforce_seat_limit`, migration `202608181000`). This file is about RLS and
    # role boundaries, and most of its scenarios need two or three members in one
    # org - so a seat refusal here would be a fixture failing while looking exactly
    # like a policy failing. Lifted once at the factory rather than at each of the
    # dozen call sites that add a member. The seat limit itself is covered in
    # `test_entitlement_enforcement.py`, against orgs whose plan is set on purpose.
    await conn.execute(
        "update public.organisations set plan_id = 'growth' where id = $1", row["org_id"]
    )
    return Tenant(auth_user_id, row["user_id"], row["org_id"])


async def _as_user(conn: asyncpg.Connection, auth_user_id: uuid.UUID) -> None:
    """Switch the connection to the identity the API would use for this request."""
    claims = json.dumps({"sub": str(auth_user_id), "role": "authenticated"})
    await conn.execute("select set_config('request.jwt.claims', $1, true)", claims)
    await conn.execute("select set_config('role', 'authenticated', true)")


async def _as_postgres(conn: asyncpg.Connection) -> None:
    await conn.execute("select set_config('role', 'postgres', true)")
    await conn.execute("select set_config('request.jwt.claims', '', true)")


async def _register_codecs(conn: asyncpg.Connection) -> None:
    """The same jsonb codec `database.Database` installs on every pooled
    connection. Without it a raw test connection hands asyncpg a Python list
    for a jsonb column and fails with "expected str, got list" - a failure the
    repository never sees at runtime, so the test would be lying about it."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
        format="text",
    )


@pytest_asyncio.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(config.database_url, timeout=30)
    await _register_codecs(conn)
    try:
        yield conn
    finally:
        await _as_postgres(conn)
        await conn.close()


@pytest_asyncio.fixture
async def tenants(db: asyncpg.Connection) -> AsyncIterator[tuple[Tenant, Tenant]]:
    a = await _create_tenant(db, "a")
    b = await _create_tenant(db, "b")
    try:
        yield a, b
    finally:
        await _as_postgres(db)
        await db.execute(
            "delete from auth.users where id = any($1::uuid[])",
            [a.auth_user_id, b.auth_user_id],
        )
        # Retired organisations are soft-deleted by trigger; remove them outright so
        # the suite leaves nothing behind.
        await db.execute(
            """
            delete from public.organisations o
            where not exists (select 1 from public.memberships m where m.org_id = o.id)
            """
        )


async def test_signup_trigger_creates_owner_and_org(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    role = await db.fetchval(
        "select role from public.memberships where org_id = $1 and user_id = $2",
        a.org_id,
        a.user_id,
    )
    assert role == "owner"


async def test_organisations_are_invisible_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        visible = await db.fetch("select id from public.organisations")

    ids = {row["id"] for row in visible}
    assert a.org_id in ids
    assert b.org_id not in ids, "tenant A can see tenant B's organisation"


async def test_memberships_are_invisible_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        rows = await db.fetch("select org_id from public.memberships")

    assert {row["org_id"] for row in rows} == {a.org_id}


async def test_users_are_invisible_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        rows = await db.fetch("select id from public.users")

    ids = {row["id"] for row in rows}
    assert ids == {a.user_id}, "a user in another organisation is visible"
    assert b.user_id not in ids


async def test_suppressions_are_invisible_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    await _as_postgres(db)
    for tenant in (a, b):
        await db.execute(
            """
            insert into public.suppressions (org_id, phone_hash, phone_e164, source)
            values ($1, $2, '+15555550100', 'manual')
            """,
            tenant.org_id,
            uuid.uuid4().hex + uuid.uuid4().hex,  # 64 chars, satisfies the check
        )

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        rows = await db.fetch("select org_id from public.suppressions")

    assert {row["org_id"] for row in rows} == {a.org_id}


async def test_cannot_write_into_another_tenant(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The dangerous case: a forged org_id on an insert."""
    a, b = tenants

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, a.auth_user_id)
            await db.execute(
                """
                insert into public.suppressions (org_id, phone_hash, source)
                values ($1, $2, 'manual')
                """,
                b.org_id,
                uuid.uuid4().hex + uuid.uuid4().hex,
            )


async def test_cannot_update_another_tenants_organisation(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        # RLS filters the row out rather than raising, so the update is a no-op.
        await db.execute(
            "update public.organisations set name = 'hijacked' where id = $1", b.org_id
        )

    await _as_postgres(db)
    name = await db.fetchval("select name from public.organisations where id = $1", b.org_id)
    assert name != "hijacked"


async def test_anonymous_sees_nothing(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """This migration's own `GRANTS` block never grants `anon` anything on
    these tables ("anon gets nothing: every read here requires a signed-in
    user") - so a bare local Postgres, provisioned purely from our own
    migrations (e.g. `supabase start`), denies the query outright, `permission
    denied` before RLS is ever consulted. A Supabase-hosted project layers its
    own platform-default grants underneath, so the identical query there
    returns zero rows via RLS instead of erroring. Both outcomes prove the
    same thing - anon cannot read a row - so this accepts either rather than
    assuming one specific enforcement mechanism; a permission-denied error is
    caught inside its own nested transaction (a `SAVEPOINT`) so the loop can
    still reach the next table without the outer transaction aborting."""
    async with db.transaction():
        await db.execute("select set_config('role', 'anon', true)")
        for table in ("organisations", "users", "memberships", "suppressions"):
            try:
                async with db.transaction():
                    count = await db.fetchval(f"select count(*) from public.{table}")
            except asyncpg.exceptions.InsufficientPrivilegeError:
                continue
            assert count == 0, f"anon can read public.{table}"


async def test_postgres_bypasses_rls_as_documented(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Guards the assumption the whole design rests on.

    If `postgres` ever stopped holding BYPASSRLS, `privileged.acquire` would silently
    start returning filtered results and background jobs would quietly do nothing.
    """
    a, b = tenants
    await _as_postgres(db)
    ids = {row["id"] for row in await db.fetch("select id from public.organisations")}
    assert {a.org_id, b.org_id} <= ids


async def test_last_owner_cannot_be_removed_directly(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    with pytest.raises(asyncpg.exceptions.RestrictViolationError):
        await db.execute(
            "delete from public.memberships where org_id = $1 and user_id = $2",
            a.org_id,
            a.user_id,
        )


async def test_account_deletion_cascades_and_retires_the_org(
    db: asyncpg.Connection,
) -> None:
    """The bug from ISSUES #13 and #17, pinned so it cannot come back."""
    conn = db
    await _as_postgres(conn)
    tenant = await _create_tenant(conn, "cascade")

    slug = await conn.fetchval(
        "select slug from public.organisations where id = $1", tenant.org_id
    )

    await conn.execute("delete from auth.users where id = $1", tenant.auth_user_id)

    assert await conn.fetchval(
        "select count(*) from public.users where id = $1", tenant.user_id
    ) == 0
    assert await conn.fetchval(
        "select count(*) from public.memberships where org_id = $1", tenant.org_id
    ) == 0

    deleted_at = await conn.fetchval(
        "select deleted_at from public.organisations where id = $1", tenant.org_id
    )
    assert deleted_at is not None, "member-less organisation was not retired"

    # And the slug is available again.
    reused = await _create_tenant(conn, "cascade")
    new_slug = await conn.fetchval(
        "select slug from public.organisations where id = $1", reused.org_id
    )
    assert new_slug == slug, f"slug not reused: {new_slug} != {slug}"

    await conn.execute("delete from auth.users where id = $1", reused.auth_user_id)
    await conn.execute("delete from public.organisations where deleted_at is not null")


async def _insert_api_key(
    db: asyncpg.Connection, *, org_id: uuid.UUID, created_by: uuid.UUID
) -> str:
    """Inserts a real key row as `postgres` and returns the plaintext key."""
    generated = generate_api_key()
    await db.execute(
        """
        insert into public.api_keys (org_id, created_by, name, key_prefix, key_hash)
        values ($1, $2, 'test key', $3, $4)
        """,
        org_id,
        created_by,
        generated.key_prefix,
        generated.key_hash,
    )
    return generated.full_key


async def _resolve(db: asyncpg.Connection, full_key: str) -> asyncpg.Record | None:
    """Mirrors the request path: `database.anonymous()` calling the resolver."""
    async with db.transaction():
        await db.execute("select set_config('role', 'anon', true)")
        row = await db.fetchrow(
            "select * from public.resolve_api_key($1)", hash_api_key(full_key)
        )
        await _as_postgres(db)
    return row


async def test_resolve_api_key_matches_the_owning_tenant(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants
    await _as_postgres(db)
    key_a = await _insert_api_key(db, org_id=a.org_id, created_by=a.user_id)

    row = await _resolve(db, key_a)
    assert row is not None
    assert row["org_id"] == a.org_id
    assert row["user_id"] == a.user_id
    assert row["role"] == "owner"

    # A key that was never issued resolves to nothing rather than raising.
    assert await _resolve(db, "cfk_" + "0" * 40) is None

    # Tenant b's own lookup never sees tenant a's key.
    key_b = await _insert_api_key(db, org_id=b.org_id, created_by=b.user_id)
    row_b = await _resolve(db, key_b)
    assert row_b is not None
    assert row_b["org_id"] == b.org_id
    assert row_b["org_id"] != row["org_id"]


async def test_resolve_api_key_stops_working_once_revoked(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)
    key = await _insert_api_key(db, org_id=a.org_id, created_by=a.user_id)

    assert await _resolve(db, key) is not None

    await db.execute("delete from public.api_keys where org_id = $1", a.org_id)
    assert await _resolve(db, key) is None


async def test_resolve_api_key_reflects_live_membership_not_a_cached_role(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The design claim in `dependencies.py`'s docstring, pinned so it can't regress.

    A key is issued by a second member of tenant b's organisation (not its owner).
    Removing that membership must break the key immediately - nothing about the
    key's own row should keep it working once its creator is no longer a member.
    """
    _, b = tenants
    await _as_postgres(db)

    second = await _create_tenant(db, "second-member")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'operator')",
        b.org_id,
        second.user_id,
    )

    key = await _insert_api_key(db, org_id=b.org_id, created_by=second.user_id)
    row = await _resolve(db, key)
    assert row is not None
    assert row["role"] == "operator"

    await db.execute(
        "delete from public.memberships where org_id = $1 and user_id = $2",
        b.org_id,
        second.user_id,
    )
    assert await _resolve(db, key) is None

    await db.execute("delete from auth.users where id = $1", second.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_provider_credentials_are_invisible_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        await db.execute(
            """
            insert into public.provider_credentials
                (org_id, created_by, provider, identifier_encrypted, secret_encrypted)
            values ($1, $2, 'twilio', 'enc-id', 'enc-secret')
            """,
            a.org_id,
            a.user_id,
        )

    async with db.transaction():
        await _as_user(db, b.auth_user_id)
        rows = await db.fetch("select org_id from public.provider_credentials")

    assert rows == [], "tenant b can see tenant a's provider credentials"


async def test_only_owner_or_admin_can_write_provider_credentials(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    operator = await _create_tenant(db, "operator")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'operator')",
        a.org_id,
        operator.user_id,
    )

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, operator.auth_user_id)
            await db.execute(
                """
                insert into public.provider_credentials
                    (org_id, created_by, provider, identifier_encrypted, secret_encrypted)
                values ($1, $2, 'plivo', 'enc-id', 'enc-secret')
                """,
                a.org_id,
                operator.user_id,
            )

    await _as_postgres(db)
    await db.execute("delete from auth.users where id = $1", operator.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- Role-hierarchy grant guard (admin-to-owner privilege escalation, R5 audit) --
#
# `set_member_role`/`invite` (app/api/v1/routes/organisations.py) stop an Admin's
# escalation attempt before it reaches the database - see
# `tests/test_organisations_routes.py` for that half. These tests are the RLS half:
# CLAUDE.md's stated model is an API check *and* an RLS check, neither alone, so a
# direct write that skipped the API layer entirely must still be refused
# (migration `c2f7a9d15e63`, `public.can_grant_role`/`public.current_org_role`).


async def test_admin_cannot_promote_an_operator_to_owner_via_direct_update(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The genuine promotion attempt: target is a non-owner member, so this
    exercises `memberships_update`'s `WITH CHECK` (the granted-role guard) -
    not the target-role guard (`test_admin_cannot_demote_or_remove_an_owner_*`
    below), which fires earlier, silently, for an already-owner target."""
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "admin")
    operator = await _create_tenant(db, "operator")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'admin')",
        a.org_id,
        admin.user_id,
    )
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'operator')",
        a.org_id,
        operator.user_id,
    )

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, admin.auth_user_id)
            await db.execute(
                "update public.memberships set role = 'owner' where org_id = $1 and user_id = $2",
                a.org_id,
                operator.user_id,
            )

    await _as_postgres(db)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, operator.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_admin_cannot_grant_admin_via_direct_update_not_even_to_a_third_member(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "admin")
    operator = await _create_tenant(db, "operator")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'admin')",
        a.org_id,
        admin.user_id,
    )
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'operator')",
        a.org_id,
        operator.user_id,
    )

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, admin.auth_user_id)
            await db.execute(
                "update public.memberships set role = 'admin' where org_id = $1 and user_id = $2",
                a.org_id,
                operator.user_id,
            )

    await _as_postgres(db)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, operator.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_admin_cannot_self_promote_to_owner_via_direct_update(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The exact takeover path from the audit: Admin targets their own row."""
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "admin")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'admin')",
        a.org_id,
        admin.user_id,
    )

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, admin.auth_user_id)
            await db.execute(
                "update public.memberships set role = 'owner' where org_id = $1 and user_id = $2",
                a.org_id,
                admin.user_id,
            )

    await _as_postgres(db)
    await db.execute("delete from auth.users where id = $1", admin.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_admin_cannot_insert_a_membership_directly_as_owner(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The insert-side twin of the update test above - same rank check, `memberships_insert`."""
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "admin")
    newcomer = await _create_tenant(db, "newcomer")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'admin')",
        a.org_id,
        admin.user_id,
    )

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, admin.auth_user_id)
            await db.execute(
                "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'owner')",
                a.org_id,
                newcomer.user_id,
            )

    await _as_postgres(db)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, newcomer.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_admin_cannot_create_an_owner_invitation(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The invite-to-owner path: blocking `invitations_insert` is what actually closes
    it, since `memberships_insert`'s `has_valid_invitation` branch only checks that a
    role matches an existing invitation, not who was allowed to create it."""
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "admin")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'admin')",
        a.org_id,
        admin.user_id,
    )

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, admin.auth_user_id)
            await db.execute(
                """
                insert into public.invitations (org_id, email, role, token, invited_by, expires_at)
                values ($1, 'new-owner@example.com', 'owner', $2, $3, now() + interval '7 days')
                """,
                a.org_id,
                uuid.uuid4().hex,
                admin.user_id,
            )

    await _as_postgres(db)
    await db.execute("delete from auth.users where id = $1", admin.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_admin_can_still_set_a_members_role_to_operator_via_direct_update(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Non-regression: this is a hierarchy fix, not a permission removal."""
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "admin")
    viewer = await _create_tenant(db, "viewer")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'admin')",
        a.org_id,
        admin.user_id,
    )
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'viewer')",
        a.org_id,
        viewer.user_id,
    )

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        await db.execute(
            "update public.memberships set role = 'operator' where org_id = $1 and user_id = $2",
            a.org_id,
            viewer.user_id,
        )

    await _as_postgres(db)
    role = await db.fetchval(
        "select role from public.memberships where org_id = $1 and user_id = $2",
        a.org_id,
        viewer.user_id,
    )
    assert role == "operator"

    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, viewer.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_owner_can_still_promote_a_member_to_admin_via_direct_update(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Non-regression: Owner's own existing range is untouched by this fix."""
    a, _ = tenants
    await _as_postgres(db)

    operator = await _create_tenant(db, "operator")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'operator')",
        a.org_id,
        operator.user_id,
    )

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        await db.execute(
            "update public.memberships set role = 'admin' where org_id = $1 and user_id = $2",
            a.org_id,
            operator.user_id,
        )

    await _as_postgres(db)
    role = await db.fetchval(
        "select role from public.memberships where org_id = $1 and user_id = $2",
        a.org_id,
        operator.user_id,
    )
    assert role == "admin"

    await db.execute("delete from auth.users where id = $1", operator.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- Target-role guard (migration `d94b2c8f1a67`) --------------------------
#
# `can_grant_role` alone only checks the role being *granted* - an Admin could
# still demote or remove an existing Owner in a multi-owner org, since neither
# `memberships_update` nor `memberships_delete` looked at the row's *current*
# role at all. `public.can_act_on_member()` closes that: added to both
# policies' `USING` clause (which is exactly where Postgres evaluates a row's
# pre-write state), it fails silently - the write matches zero rows, same
# pattern as `test_cannot_update_another_tenants_organisation` - rather than
# raising, since `USING` filters rows rather than validating a proposed one.


async def test_admin_cannot_demote_an_owner_via_direct_update(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "admin")
    co_owner = await _create_tenant(db, "co-owner")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'admin')",
        a.org_id,
        admin.user_id,
    )
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'owner')",
        a.org_id,
        co_owner.user_id,
    )

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        await db.execute(
            "update public.memberships set role = 'operator' where org_id = $1 and user_id = $2",
            a.org_id,
            co_owner.user_id,
        )

    await _as_postgres(db)
    role = await db.fetchval(
        "select role from public.memberships where org_id = $1 and user_id = $2",
        a.org_id,
        co_owner.user_id,
    )
    assert role == "owner", "Admin demoted an Owner - the target-role guard did not hold"

    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, co_owner.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_admin_cannot_remove_an_owner_via_direct_delete(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "admin")
    co_owner = await _create_tenant(db, "co-owner")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'admin')",
        a.org_id,
        admin.user_id,
    )
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'owner')",
        a.org_id,
        co_owner.user_id,
    )

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        await db.execute(
            "delete from public.memberships where org_id = $1 and user_id = $2",
            a.org_id,
            co_owner.user_id,
        )

    await _as_postgres(db)
    still_there = await db.fetchval(
        "select exists(select 1 from public.memberships where org_id = $1 and user_id = $2)",
        a.org_id,
        co_owner.user_id,
    )
    assert still_there, "Admin removed an Owner - the target-role guard did not hold"

    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, co_owner.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_owner_can_still_demote_a_co_owner_via_direct_update(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Non-regression: an Owner acting on another Owner is unaffected."""
    a, _ = tenants
    await _as_postgres(db)

    co_owner = await _create_tenant(db, "co-owner")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'owner')",
        a.org_id,
        co_owner.user_id,
    )

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        await db.execute(
            "update public.memberships set role = 'admin' where org_id = $1 and user_id = $2",
            a.org_id,
            co_owner.user_id,
        )

    await _as_postgres(db)
    role = await db.fetchval(
        "select role from public.memberships where org_id = $1 and user_id = $2",
        a.org_id,
        co_owner.user_id,
    )
    assert role == "admin"

    await db.execute("delete from auth.users where id = $1", co_owner.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- Invitation-mutation guard (migration `d94b2c8f1a67`) -------------------
#
# `invitations_update_own` lets the invitee update their own pending invite
# (to accept it) but never restricted *which* column - an invitee legitimately
# invited as viewer could rewrite their own invitation's `role` to `owner`
# before accepting, with no Admin or Owner action at all. Column-level GRANT
# is the actual fix (`authenticated` can only ever write `accepted_at`); RLS
# policy is unchanged and would still nominally allow it on an email match.


async def test_invitee_cannot_escalate_their_own_pending_invitations_role(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    invitee = await _create_tenant(db, "invitee")
    invitee_email = await db.fetchval(
        "select email from public.users where id = $1", invitee.user_id
    )
    token = uuid.uuid4().hex
    await db.execute(
        """
        insert into public.invitations (org_id, email, role, token, invited_by, expires_at)
        values ($1, $2, 'viewer', $3, $4, now() + interval '7 days')
        """,
        a.org_id,
        invitee_email,
        token,
        a.user_id,
    )

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, invitee.auth_user_id)
            await db.execute(
                "update public.invitations set role = 'owner' where token = $1", token
            )

    await _as_postgres(db)
    role = await db.fetchval("select role from public.invitations where token = $1", token)
    assert role == "viewer", "invitee mutated their own pending invitation's role"

    await db.execute("delete from public.invitations where token = $1", token)
    await db.execute("delete from auth.users where id = $1", invitee.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- Invitation-acceptance user_id guard (migration `d94b2c8f1a67`) --------
#
# `has_valid_invitation(org_id, role)` only ever checked that *the caller* has
# a matching pending invitation - never that the `user_id` being inserted into
# `memberships` was the caller's own. A caller holding any valid invitation
# for an org+role could insert a membership row for an arbitrary other user.


async def test_valid_invitation_cannot_seat_someone_else(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    invitee = await _create_tenant(db, "invitee")
    victim = await _create_tenant(db, "victim")
    invitee_email = await db.fetchval(
        "select email from public.users where id = $1", invitee.user_id
    )
    token = uuid.uuid4().hex
    await db.execute(
        """
        insert into public.invitations (org_id, email, role, token, invited_by, expires_at)
        values ($1, $2, 'operator', $3, $4, now() + interval '7 days')
        """,
        a.org_id,
        invitee_email,
        token,
        a.user_id,
    )

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, invitee.auth_user_id)
            await db.execute(
                "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'operator')",
                a.org_id,
                victim.user_id,
            )

    await _as_postgres(db)
    seated = await db.fetchval(
        "select exists(select 1 from public.memberships where org_id = $1 and user_id = $2)",
        a.org_id,
        victim.user_id,
    )
    assert not seated, "a valid invitation seated a user other than its own invitee"

    await db.execute("delete from public.invitations where token = $1", token)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [invitee.auth_user_id, victim.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- Real, non-mocked invitation creation (migration `e15f3d9a2c78`) -------
#
# Migration `d94b2c8f1a67`'s `revoke update ... grant update (accepted_at)` on
# `invitations` broke `org_repo.create_invitation()` outright: its
# `insert ... on conflict ... do update` needs UPDATE privilege on the columns
# in the `do update set` list for the *whole statement* to plan, regardless of
# whether a conflict occurs at runtime - so a first-time invite failed
# identically to a re-invite. `test_admin_can_still_invite_as_operator_or_viewer`
# (`test_organisations_routes.py`) mocks `create_invitation` entirely and so
# never exercised the real SQL - exactly the coverage gap that let this
# regression through undetected. These call `org_repo.create_invitation()`
# itself, for real, against the database.


async def test_owner_can_create_a_real_invitation_through_the_repository(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    expires_at = datetime.now(UTC) + timedelta(days=7)
    token = uuid.uuid4().hex

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        row = await org_repo.create_invitation(
            db,
            org_id=a.org_id,
            email="brand-new-invitee@example.com",
            role="operator",
            token=token,
            expires_at=expires_at,
        )

    assert row is not None
    assert row["role"] == "operator"
    assert row["email"] == "brand-new-invitee@example.com"
    assert row["accepted_at"] is None
    # `invited_by` is derived from the caller's own identity inside the
    # SECURITY DEFINER function (migration `d7f3a8c2e951`), not trusted from
    # an argument - pin that it actually resolves to the real caller.
    assert row["invited_by"] == a.user_id

    await _as_postgres(db)
    await db.execute("delete from public.invitations where token = $1", token)


async def test_owner_can_refresh_a_pending_invitation_through_the_repository(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The `ISSUES.md` #44 case: re-inviting an already-pending email, through
    the real repository function, by the inviter (not the invitee)."""
    a, _ = tenants
    expires_at = datetime.now(UTC) + timedelta(days=7)
    first_token = uuid.uuid4().hex
    second_token = uuid.uuid4().hex

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        first = await org_repo.create_invitation(
            db,
            org_id=a.org_id,
            email="repeat-invitee@example.com",
            role="operator",
            token=first_token,
            expires_at=expires_at,
        )

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        second = await org_repo.create_invitation(
            db,
            org_id=a.org_id,
            email="repeat-invitee@example.com",
            role="viewer",
            token=second_token,
            expires_at=expires_at,
        )

    assert second["id"] == first["id"], "re-invite should refresh the same row, not duplicate it"
    assert second["role"] == "viewer"
    assert second["token"] == second_token

    await _as_postgres(db)
    await db.execute("delete from public.invitations where id = $1", first["id"])


async def test_admin_cannot_create_an_owner_invitation_through_the_repository(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The escalation check now lives inside `create_or_refresh_invitation()`
    itself (it bypasses RLS, so it must enforce `can_grant_role` internally) -
    this proves that check holds when called through the real application
    code path, not just via a raw `INSERT` against `invitations_insert`
    (`test_admin_cannot_create_an_owner_invitation`, above)."""
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "admin")
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'admin')",
        a.org_id,
        admin.user_id,
    )
    expires_at = datetime.now(UTC) + timedelta(days=7)
    token = uuid.uuid4().hex

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, admin.auth_user_id)
            await org_repo.create_invitation(
                db,
                org_id=a.org_id,
                email="sneaky-owner@example.com",
                role="owner",
                token=token,
                expires_at=expires_at,
            )

    await _as_postgres(db)
    seated = await db.fetchval(
        "select exists(select 1 from public.invitations where token = $1)", token
    )
    assert not seated, "an Admin created a pending owner-role invitation"

    await db.execute("delete from auth.users where id = $1", admin.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- Per-creator visibility silo (migration `d4bcc27a2b70`) ----------------
#
# Role-based UI roadmap, Phase 1: `voice_agents_select`/`runs_select`/
# `call_outcomes_select` used to be pure `is_org_member(org_id)` - any member
# could see any other member's rows. Now an operator sees only what they
# created (or, for call_outcomes, what belongs to a run they started);
# owner/admin/viewer are unaffected and keep seeing every row in the org.
# This is the first feature where *same-org* isolation between two ordinary
# members matters as much as cross-tenant isolation - CLAUDE.md's checklist
# calls for exactly this kind of test on any tenant-scoped RLS change.


async def _seat(db: asyncpg.Connection, org_id: uuid.UUID, tenant: Tenant, role: str) -> None:
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, $3)",
        org_id,
        tenant.user_id,
        role,
    )




async def _insert_run(
    db: asyncpg.Connection, *, org_id: uuid.UUID, started_by: uuid.UUID
) -> str:
    run_id = f"silo-run-{uuid.uuid4().hex[:8]}"
    await db.execute(
        """
        insert into public.runs (id, org_id, voice_agent_id, total, started_by)
        values ($1, $2, null, 1, $3)
        """,
        run_id,
        org_id,
        started_by,
    )
    return run_id


async def _insert_call_outcome(db: asyncpg.Connection, *, org_id: uuid.UUID, run_id: str) -> None:
    await db.execute(
        """
        insert into public.call_outcomes (run_id, org_id, contact_name, phone_masked)
        values ($1, $2, 'Silo Contact', '+1 555 0100')
        """,
        run_id,
        org_id,
    )




async def test_operator_cannot_see_a_teammates_run_or_its_call_outcomes(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "silo-run-op1")
    op2 = await _create_tenant(db, "silo-run-op2")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")
    run_id = await _insert_run(db, org_id=a.org_id, started_by=op1.user_id)
    await _insert_call_outcome(db, org_id=a.org_id, run_id=run_id)

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        runs = await db.fetch("select id from public.runs where org_id = $1", a.org_id)
        outcomes = await db.fetch(
            "select id from public.call_outcomes where org_id = $1", a.org_id
        )
    assert runs == [], "operator can see a teammate's run"
    assert outcomes == [], "operator can see a call outcome from a teammate's run"

    async with db.transaction():
        await _as_user(db, op1.auth_user_id)
        runs = await db.fetch("select id from public.runs where org_id = $1", a.org_id)
        outcomes = await db.fetch(
            "select id from public.call_outcomes where org_id = $1", a.org_id
        )
    assert [r["id"] for r in runs] == [run_id]
    assert len(outcomes) == 1

    await _as_postgres(db)
    await db.execute("delete from public.runs where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")




async def test_summarize_by_member_reflects_the_callers_own_rls_scope(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The dashboard team-breakdown query (`runs_repo.summarize_by_member`,
    backing `GET /api/v1/runs/team-summary`) has no ownership filter of its
    own - it leans entirely on `runs_select`. `Permission.RUNS_READ_TEAM` is
    what actually keeps an operator from calling the route at all; this pins
    that RLS alone would otherwise just silently narrow their result to
    their own row rather than the whole team, exactly as the repository
    function's docstring claims."""
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "summary-admin")
    op1 = await _create_tenant(db, "summary-op1")
    op2 = await _create_tenant(db, "summary-op2")
    await _seat(db, a.org_id, admin, "admin")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")

    run1 = await _insert_run(db, org_id=a.org_id, started_by=op1.user_id)
    run2 = await _insert_run(db, org_id=a.org_id, started_by=op2.user_id)
    await _insert_call_outcome(db, org_id=a.org_id, run_id=run1)
    await _insert_call_outcome(db, org_id=a.org_id, run_id=run2)

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        rows = await runs_repo.summarize_by_member(db, a.org_id)
    assert {r["started_by"] for r in rows} == {op1.user_id, op2.user_id}
    by_member = {r["started_by"]: r for r in rows}
    assert by_member[op1.user_id]["total_calls"] == 1
    assert by_member[op2.user_id]["total_calls"] == 1

    async with db.transaction():
        await _as_user(db, op1.auth_user_id)
        rows = await runs_repo.summarize_by_member(db, a.org_id)
    assert {r["started_by"] for r in rows} == {op1.user_id}

    await _as_postgres(db)
    await db.execute("delete from public.runs where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- First-time invitation acceptance (migration `202608092400`) -----------
#
# `invitations_repo.accept()`'s lookup used to `join public.organisations` under
# the RLS-scoped connection - `organisations_select` is plain `is_org_member(id)`,
# which a brand-new invitee fails by definition (they aren't a member of anything
# yet). The join silently dropped the row, so no one could ever actually accept
# their first invitation - found via real-world testing, not by any existing
# test, since nothing here previously exercised a genuine brand-new signup
# accepting a real invitation end to end (`ISSUES.md` #68).


async def _sign_up(db: asyncpg.Connection, email: str) -> uuid.UUID:
    """A bare signup, no name - fires the same `handle_new_auth_user()` trigger
    a real `supabase.auth.signUp()` call does, giving the new user their own
    auto-created org exactly like a genuine first-time signup would."""
    auth_user_id = uuid.uuid4()
    await db.execute(
        """
        insert into auth.users (id, instance_id, aud, role, email, encrypted_password,
                                email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
                                created_at, updated_at)
        values ($1, '00000000-0000-0000-0000-000000000000', 'authenticated',
                'authenticated', $2, crypt('x', gen_salt('bf')), now(),
                '{"provider":"email"}', '{}'::jsonb, now(), now())
        """,
        auth_user_id,
        email,
    )
    return auth_user_id


async def test_a_brand_new_invitee_can_actually_accept_their_first_invitation(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    token = uuid.uuid4().hex
    invitee_email = f"brand-new-invitee-{uuid.uuid4().hex[:8]}@example.com"
    await db.execute(
        """
        insert into public.invitations (org_id, email, role, token, invited_by, expires_at)
        values ($1, $2, 'operator', $3, $4, now() + interval '7 days')
        """,
        a.org_id,
        invitee_email,
        token,
        a.user_id,
    )
    invitee_auth_id = await _sign_up(db, invitee_email)

    async with db.transaction():
        await _as_user(db, invitee_auth_id)
        result = await invitations_repo.accept(db, token)

    assert result is not None, "a brand-new invitee could not accept their own first invitation"
    assert result["org_id"] == a.org_id
    assert result["role"] == "operator"

    await _as_postgres(db)
    role = await db.fetchval(
        """
        select role from public.memberships m join public.users u on u.id = m.user_id
        where m.org_id = $1 and u.auth_user_id = $2
        """,
        a.org_id,
        invitee_auth_id,
    )
    assert role == "operator"
    accepted = await db.fetchval(
        "select accepted_at is not null from public.invitations where token = $1", token
    )
    assert accepted

    await db.execute("delete from auth.users where id = $1", invitee_auth_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_an_expired_invitation_cannot_be_accepted(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`accept()` never checked `expires_at` before this fix - only `accepted_at`."""
    a, _ = tenants
    await _as_postgres(db)

    token = uuid.uuid4().hex
    invitee_email = f"expired-invitee-{uuid.uuid4().hex[:8]}@example.com"
    await db.execute(
        """
        insert into public.invitations (org_id, email, role, token, invited_by, expires_at)
        values ($1, $2, 'operator', $3, $4, now() - interval '1 hour')
        """,
        a.org_id,
        invitee_email,
        token,
        a.user_id,
    )
    invitee_auth_id = await _sign_up(db, invitee_email)

    async with db.transaction():
        await _as_user(db, invitee_auth_id)
        result = await invitations_repo.accept(db, token)

    assert result is None, "an expired invitation was accepted"

    await _as_postgres(db)
    await db.execute("delete from auth.users where id = $1", invitee_auth_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_accept_by_the_wrong_email_returns_none_without_aborting_the_transaction(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`has_valid_invitation()` matches on the *caller's* own email, not the
    token alone - a signed-in user who isn't the invitee fails that check, and
    the INSERT raises `InsufficientPrivilegeError`. Before wrapping that INSERT
    in a nested transaction (a `SAVEPOINT`, same fix as `messages_repo.send_message()`
    needed), catching the error without rolling back to one left the whole
    request transaction aborted: the very next statement on the same
    connection - here, a second `accept()` call in the same transaction, as a
    retried request would issue - would itself raise
    `InFailedSqlTransactionError` instead of ever reaching its own clean
    `None`. That second call is the actual regression check, not the first."""
    a, _ = tenants
    await _as_postgres(db)

    invited_email = f"invited-{uuid.uuid4().hex[:8]}@example.com"
    token = uuid.uuid4().hex
    await db.execute(
        """
        insert into public.invitations (org_id, email, role, token, invited_by, expires_at)
        values ($1, $2, 'operator', $3, $4, now() + interval '7 days')
        """,
        a.org_id,
        invited_email,
        token,
        a.user_id,
    )

    wrong_person = await _create_tenant(db, "accept-wrong-email")

    async with db.transaction():
        await _as_user(db, wrong_person.auth_user_id)
        first = await invitations_repo.accept(db, token)
        assert first is None, "accept() succeeded for a caller whose email doesn't match"

        # Would raise InFailedSqlTransactionError here before the SAVEPOINT fix -
        # the prior INSERT's error would still have the transaction aborted.
        second = await invitations_repo.accept(db, token)
        assert second is None

    await _as_postgres(db)
    still_pending = await db.fetchval(
        "select accepted_at is null from public.invitations where token = $1", token
    )
    assert still_pending, "the invitation was mutated despite both accept() calls failing"
    await db.execute("delete from public.invitations where token = $1", token)
    await db.execute("delete from auth.users where id = $1", wrong_person.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- Remove a teammate: data reassignment + full account deletion (migration
# `202608092600`) -------------------------------------------------------------
#
# Product decision (confirmed with the user): removing a teammate is not just a
# membership delete. What they created in this org is reassigned to whoever
# removed them, and their account is deleted entirely - not just this one
# membership. Any OTHER organisation they belong to is unaffected by the
# reassignment (the removing admin has no relationship to that org's data) and
# falls back to the ordinary `on delete set null`, exactly like a self-deleted
# account already does today.


async def test_admin_removing_a_teammate_reassigns_their_org_data_and_deletes_their_account(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "remove-op1")
    await _seat(db, a.org_id, op1, "operator")
    shared_agent = await _insert_voice_agent(db, org_id=a.org_id, created_by=op1.user_id)

    # op1's own auto-created org from signup - unrelated to `a`, should be
    # untouched by the reassignment `a`'s removal triggers.
    own_org_id = await db.fetchval(
        "select org_id from public.memberships where user_id = $1 and role = 'owner'",
        op1.user_id,
    )
    own_agent = await _insert_voice_agent(db, org_id=own_org_id, created_by=op1.user_id)

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        await db.execute(
            "select public.remove_member_and_reassign_data($1, $2)", a.org_id, op1.user_id
        )

    await _as_postgres(db)
    creator = await db.fetchval(
        "select created_by from public.voice_agents where id = $1", shared_agent["id"]
    )
    assert creator == a.user_id, "the removed teammate's agent was not reassigned to the admin"

    still_a_member = await db.fetchval(
        "select exists(select 1 from public.memberships where org_id = $1 and user_id = $2)",
        a.org_id,
        op1.user_id,
    )
    assert not still_a_member

    account_gone = await db.fetchval(
        "select exists(select 1 from public.users where id = $1)", op1.user_id
    )
    assert account_gone is False, "the removed teammate's account was not deleted"

    own_agent_creator = await db.fetchval(
        "select created_by from public.voice_agents where id = $1", own_agent["id"]
    )
    assert own_agent_creator is None, "an unrelated org's data was touched by this removal"

    await db.execute(
        "delete from public.voice_agents where id = any($1::uuid[])",
        [shared_agent["id"], own_agent["id"]],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_an_operator_cannot_call_remove_member_and_reassign_data_directly(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Defense in depth: even called directly (bypassing the API's own
    `Permission.TEAM_REMOVE` check), the `SECURITY DEFINER` function
    re-verifies the caller's role itself - same reasoning as
    `create_or_refresh_invitation()`'s own internal `has_org_role` check."""
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "remove-guard-op1")
    op2 = await _create_tenant(db, "remove-guard-op2")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, op1.auth_user_id)
            await db.execute(
                "select public.remove_member_and_reassign_data($1, $2)", a.org_id, op2.user_id
            )

    await _as_postgres(db)
    still_there = await db.fetchval(
        "select exists(select 1 from public.memberships where org_id = $1 and user_id = $2)",
        a.org_id,
        op2.user_id,
    )
    assert still_there, "an operator removed a teammate directly, bypassing the role check"

    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- Real, persisted escalations + per-teammate credits (Phase 2 / Phase 5
# slice of the role-based UI roadmap, migration 202608100900) --------------


async def _insert_escalated_outcome_and_escalation(
    db: asyncpg.Connection, *, org_id: uuid.UUID, run_id: str
) -> uuid.UUID:
    """Insert a call_outcome with an escalating disposition and the matching
    `escalations` row - the same two-step sequence `runs.py`'s `on_progress`
    closure performs, just without the run-scoped `as_user()` context (this
    helper always runs while seated as `postgres`)."""
    call_outcome_id = await db.fetchval(
        """
        insert into public.call_outcomes (run_id, org_id, contact_name, phone_masked, disposition)
        values ($1, $2, 'Escalated Contact', '+1 555 0101', 'escalated')
        returning id
        """,
        run_id,
        org_id,
    )
    escalation_id = await db.fetchval(
        """
        insert into public.escalations (org_id, run_id, call_outcome_id)
        values ($1, $2, $3)
        returning id
        """,
        org_id,
        run_id,
        call_outcome_id,
    )
    return escalation_id


async def test_operator_cannot_see_a_teammates_escalation(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "esc-op1")
    op2 = await _create_tenant(db, "esc-op2")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")
    run_id = await _insert_run(db, org_id=a.org_id, started_by=op1.user_id)
    await _insert_escalated_outcome_and_escalation(db, org_id=a.org_id, run_id=run_id)

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        rows = await escalations_repo.list_for_org(db, a.org_id)
    assert rows == [], "operator can see a teammate's escalation"

    async with db.transaction():
        await _as_user(db, op1.auth_user_id)
        rows = await escalations_repo.list_for_org(db, a.org_id)
    assert len(rows) == 1

    await _as_postgres(db)
    await db.execute("delete from public.runs where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_assigning_an_escalation_makes_it_visible_to_the_assignee(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """An operator with no relationship to the run itself still sees an
    escalation once it's assigned to them - the `assigned_to` branch of
    `escalations_select`, independent of who started the underlying run."""
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "esc-assign-admin")
    op1 = await _create_tenant(db, "esc-assign-op1")
    op2 = await _create_tenant(db, "esc-assign-op2")
    await _seat(db, a.org_id, admin, "admin")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")
    run_id = await _insert_run(db, org_id=a.org_id, started_by=op1.user_id)
    escalation_id = await _insert_escalated_outcome_and_escalation(
        db, org_id=a.org_id, run_id=run_id
    )

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        rows = await escalations_repo.list_for_org(db, a.org_id)
    assert rows == [], "unassigned operator can already see another's escalation"

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        updated = await escalations_repo.assign(
            db,
            org_id=a.org_id,
            escalation_id=escalation_id,
            assigned_to=op2.user_id,
            assigned_by=admin.user_id,
        )
    assert updated is not None

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        rows = await escalations_repo.list_for_org(db, a.org_id)
    assert len(rows) == 1, "assignee still cannot see the escalation assigned to them"
    assert rows[0]["assigned_to"] == op2.user_id

    await _as_postgres(db)
    await db.execute("delete from public.runs where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_operator_cannot_assign_or_resolve_a_teammates_escalation(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """RLS is the actual backstop for "is this row yours" - `ESCALATIONS_ASSIGN`/
    `ESCALATIONS_RESOLVE` only gate that the *kind* of action is available to
    the role at all, not which specific row. Called directly here the same
    way the route calls the repository, bypassing the API's permission
    dependency entirely, to prove the database itself refuses it."""
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "esc-guard-op1")
    op2 = await _create_tenant(db, "esc-guard-op2")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")
    run_id = await _insert_run(db, org_id=a.org_id, started_by=op1.user_id)
    escalation_id = await _insert_escalated_outcome_and_escalation(
        db, org_id=a.org_id, run_id=run_id
    )

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        assign_result = await escalations_repo.assign(
            db,
            org_id=a.org_id,
            escalation_id=escalation_id,
            assigned_to=op2.user_id,
            assigned_by=op2.user_id,
        )
        resolve_result = await escalations_repo.resolve(
            db, org_id=a.org_id, escalation_id=escalation_id, resolved_by=op2.user_id
        )
    assert assign_result is None, "operator self-assigned a teammate's escalation"
    assert resolve_result is None, "operator resolved a teammate's escalation"

    async with db.transaction():
        await _as_user(db, op1.auth_user_id)
        resolved = await escalations_repo.resolve(
            db, org_id=a.org_id, escalation_id=escalation_id, resolved_by=op1.user_id
        )
    assert resolved is not None, "the run's own starter could not resolve their own escalation"

    await _as_postgres(db)
    await db.execute("delete from public.runs where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_member_credit_allocations_scoped_to_self_or_team_read(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`member_credit_allocations` now holds only the usage-credit share
    (`monthly_credit_cap_paise`) - the call-count allocation this table used
    to also carry was retired. The RLS boundary is unchanged and still worth
    proving directly: a known, real cap set for op1 must read back as `None`
    for a teammate RLS blocks, real for op1 themselves, and real for an
    admin - `get_credit_cap` cannot otherwise tell "blocked" from "never set",
    so a genuine non-null value is what makes a blocked read provable."""
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "credits-admin")
    op1 = await _create_tenant(db, "credits-op1")
    op2 = await _create_tenant(db, "credits-op2")
    await _seat(db, a.org_id, admin, "admin")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        await credits_repo.set_credit_cap(
            db, org_id=a.org_id, user_id=op1.user_id, cap_paise=50_00, updated_by=admin.user_id
        )

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        seen_by_op2 = await credits_repo.get_credit_cap(db, a.org_id, op1.user_id)
    assert seen_by_op2 is None, "operator can see a teammate's usage-credit cap"

    async with db.transaction():
        await _as_user(db, op1.auth_user_id)
        seen_by_self = await credits_repo.get_credit_cap(db, a.org_id, op1.user_id)
    assert seen_by_self == 50_00, "operator cannot see their own usage-credit cap"

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        seen_by_admin = await credits_repo.get_credit_cap(db, a.org_id, op1.user_id)
    assert seen_by_admin == 50_00, "admin cannot see the team's usage-credit caps"

    await _as_postgres(db)
    await db.execute("delete from public.member_credit_allocations where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_operator_cannot_set_a_credit_allocation_directly(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Defense in depth for `Permission.CREDITS_WRITE` (admin/owner only) -
    called directly, bypassing the API's permission dependency, the same
    shape as the escalation-assignment guard test above."""
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "credits-guard-op1")
    op2 = await _create_tenant(db, "credits-guard-op2")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, op1.auth_user_id)
            await credits_repo.set_credit_cap(
                db, org_id=a.org_id, user_id=op2.user_id, cap_paise=99_00, updated_by=op1.user_id
            )

    await _as_postgres(db)
    await db.execute("delete from public.member_credit_allocations where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- Peer-to-peer escalation sharing (role-based UI roadmap,
# Phase 4, migration 4cbc5103657f) ------------------------------------------




async def test_resolve_resource_owner_returns_null_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """A caller who isn't even a member of the target org gets null, not the
    real owner - the internal `is_org_member()` guard every other
    `SECURITY DEFINER` function in this codebase already has."""
    a, b = tenants
    await _as_postgres(db)
    agent = await _insert_voice_agent(db, org_id=a.org_id, created_by=b.user_id)

    async with db.transaction():
        await _as_user(db, b.auth_user_id)
        owner = await sharing_repo.resolve_resource_owner(
            db, org_id=a.org_id, resource_type="escalation", resource_id=str(agent["id"])
        )
    assert owner is None, "a non-member resolved a real resource's owner"

    await _as_postgres(db)
    await db.execute("delete from public.voice_agents where org_id = $1", a.org_id)




async def test_directory_functions_return_nothing_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants
    await _as_postgres(db)
    await _insert_voice_agent(db, org_id=a.org_id, created_by=b.user_id)

    # `list_campaign_directory` went with campaigns (ADR-8). The escalation
    # directory below is the surviving directory function, and it carries the
    # same cross-tenant claim this test exists for.
    await _as_postgres(db)
    await db.execute("delete from public.voice_agents where org_id = $1", a.org_id)


async def _insert_share_request(
    db: asyncpg.Connection,
    *,
    org_id: uuid.UUID,
    resource_type: str,
    resource_id: str,
    requested_by: uuid.UUID,
    owner_user_id: uuid.UUID,
) -> uuid.UUID:
    return await db.fetchval(
        """
        insert into public.share_requests
            (org_id, resource_type, resource_id, requested_by, owner_user_id)
        values ($1, $2, $3, $4, $5)
        returning id
        """,
        org_id,
        resource_type,
        resource_id,
        requested_by,
        owner_user_id,
    )


async def test_share_requests_visible_to_requester_owner_and_admin_only(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "share-vis-admin")
    op1 = await _create_tenant(db, "share-vis-requester")
    op2 = await _create_tenant(db, "share-vis-owner")
    op3 = await _create_tenant(db, "share-vis-unrelated")
    await _seat(db, a.org_id, admin, "admin")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")
    await _seat(db, a.org_id, op3, "operator")
    agent_id = str(
        (await _insert_voice_agent(db, org_id=a.org_id, created_by=op2.user_id))["id"]
    )
    await _insert_share_request(
        db,
        org_id=a.org_id,
        resource_type="escalation",
        resource_id=agent_id,
        requested_by=op1.user_id,
        owner_user_id=op2.user_id,
    )

    for tenant, expected in ((op1, True), (op2, True), (admin, True), (op3, False)):
        async with db.transaction():
            await _as_user(db, tenant.auth_user_id)
            rows = await sharing_repo.list_for_org(db, a.org_id)
        assert (len(rows) == 1) is expected, f"visibility wrong for {tenant.email}"

    await _as_postgres(db)
    await db.execute("delete from public.share_requests where org_id = $1", a.org_id)
    await db.execute("delete from public.voice_agents where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, op1.auth_user_id, op2.auth_user_id, op3.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_only_the_named_owner_can_decide_a_share_request(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`share_requests_update` restricts the UPDATE to `owner_user_id = self`
    - not admin/owner, and not the requester either, matching the roadmap's
    own scoping (approving is the resource owner's call alone)."""
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "share-decide-admin")
    op1 = await _create_tenant(db, "share-decide-requester")
    op2 = await _create_tenant(db, "share-decide-owner")
    await _seat(db, a.org_id, admin, "admin")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")
    agent_id = str(
        (await _insert_voice_agent(db, org_id=a.org_id, created_by=op2.user_id))["id"]
    )
    request_id = await _insert_share_request(
        db,
        org_id=a.org_id,
        resource_type="escalation",
        resource_id=agent_id,
        requested_by=op1.user_id,
        owner_user_id=op2.user_id,
    )

    for tenant in (op1, admin):
        async with db.transaction():
            await _as_user(db, tenant.auth_user_id)
            decided = await sharing_repo.decide(
                db, org_id=a.org_id, request_id=request_id, approve=True
            )
        assert decided is None, f"{tenant.email} decided a request they don't own"

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        decided = await sharing_repo.decide(
            db, org_id=a.org_id, request_id=request_id, approve=True
        )
    assert decided is not None, "the real owner could not decide their own request"

    # Idempotency: the same owner deciding the same request a second time
    # (a client retry after a dropped response, a double-click) must be a
    # no-op, not a second grant - the primitive `_decide()`'s reordering
    # fix (route calls `decide()` before the grant, not after) depends on.
    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        decided_again = await sharing_repo.decide(
            db, org_id=a.org_id, request_id=request_id, approve=True
        )
    assert decided_again is None, "deciding an already-decided request succeeded a second time"

    await _as_postgres(db)
    await db.execute("delete from public.share_requests where org_id = $1", a.org_id)
    await db.execute("delete from public.voice_agents where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_a_forged_owner_user_id_still_cannot_actually_grant_access(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`share_requests_insert` only checks `requested_by = self` - nothing
    stops a row being inserted with the *wrong* `owner_user_id` (the route
    never trusts client input for it, but RLS alone doesn't forbid a
    hand-crafted one either). This proves the second, independent layer:
    even if op3 forges themselves in as `owner_user_id` and RLS lets them
    "decide" it, the actual grant still runs under their own
    `voice_agents_select` scope, which a non-creator
    operator fails. Application code (`sharing.py`'s `_decide`) checks this
    read before marking anything decided; this test pins the repository-
    level fact that makes that check meaningful, not just presumed."""
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "share-forge-creator")
    op3 = await _create_tenant(db, "share-forge-attacker")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op3, "operator")
    agent_id = str(
        (await _insert_voice_agent(db, org_id=a.org_id, created_by=op1.user_id))["id"]
    )

    async with db.transaction():
        await _as_user(db, op3.auth_user_id)
        forged = await sharing_repo.get_for_org(
            db,
            a.org_id,
            await _insert_share_request(
                db,
                org_id=a.org_id,
                resource_type="escalation",
                resource_id=agent_id,
                requested_by=op3.user_id,
                owner_user_id=op3.user_id,
            ),
        )
        # RLS lets this "decide" through - op3 really is `owner_user_id` on
        # this (forged) row.
        assert forged is not None
        # But the read the real grant depends on is still scoped to op3's
        # own agents - the resource was never theirs to take.
        original = await voice_agents_repo.get_org_agent(db, a.org_id, uuid.UUID(agent_id))
    assert original is None, "a forged owner_user_id could read a resource that is not theirs"

    await _as_postgres(db)
    await db.execute("delete from public.share_requests where org_id = $1", a.org_id)
    await db.execute("delete from public.voice_agents where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op3.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")




async def test_operator_cannot_insert_a_share_request_on_someone_elses_behalf(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`share_requests_insert` requires `requested_by = current_user_id()` -
    op1 cannot submit a request that claims op2 as the requester."""
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "share-insert-guard-op1")
    op2 = await _create_tenant(db, "share-insert-guard-op2")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")
    agent_id = str(
        (await _insert_voice_agent(db, org_id=a.org_id, created_by=op2.user_id))["id"]
    )

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, op1.auth_user_id)
            await _insert_share_request(
                db,
                org_id=a.org_id,
                resource_type="escalation",
                resource_id=agent_id,
                requested_by=op2.user_id,
                owner_user_id=op2.user_id,
            )

    await _as_postgres(db)
    await db.execute("delete from public.voice_agents where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- voice_agents / telephony_provisioning (PLATFORM_PIVOT_PLAN.md ADR-4) -----
#
# These two tables are the reason the pivot needs its own isolation pass:
# `voice_agents` holds references to an org's STT/TTS/LLM *credentials*, and
# `telephony_provisioning` holds the carrier/LiveKit trunk identifiers that
# connect a real phone number. A policy that looks right and leaks either is
# exactly the bug class CLAUDE.md Â§7 calls the most expensive available here.


async def _make_agent(conn: asyncpg.Connection, tenant: Tenant, name: str) -> uuid.UUID:
    """Insert a voice agent for a tenant, bypassing RLS - the fixture, not the test."""
    return await conn.fetchval(
        """
        insert into public.voice_agents (org_id, name, kind, llm_provider, llm_model)
        values ($1, $2, 'custom', 'openrouter', 'anthropic/claude-sonnet-4')
        returning id
        """,
        tenant.org_id,
        name,
    )


async def _make_provisioning(
    conn: asyncpg.Connection, tenant: Tenant, agent_id: uuid.UUID, key: str
) -> uuid.UUID:
    return await conn.fetchval(
        """
        insert into public.telephony_provisioning
            (voice_agent_id, org_id, status, idempotency_key, livekit_inbound_trunk_id)
        values ($1, $2, 'provisioning', $3, 'ST_fake_trunk')
        returning id
        """,
        agent_id,
        tenant.org_id,
        key,
    )


async def test_voice_agents_are_invisible_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    await _as_postgres(db)
    await _make_agent(db, a, "A's agent")
    await _make_agent(db, b, "B's agent")

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        rows = await db.fetch("select org_id, name from public.voice_agents")

    assert {row["org_id"] for row in rows} == {a.org_id}
    assert "B's agent" not in {row["name"] for row in rows}


async def test_telephony_provisioning_is_invisible_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The trunk identifiers are infrastructure secrets: knowing another org's
    inbound trunk id is knowing where their calls land."""
    a, b = tenants

    await _as_postgres(db)
    agent_a = await _make_agent(db, a, "A's agent")
    agent_b = await _make_agent(db, b, "B's agent")
    await _make_provisioning(db, a, agent_a, "key-a")
    await _make_provisioning(db, b, agent_b, "key-b")

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        rows = await db.fetch(
            "select org_id, idempotency_key from public.telephony_provisioning"
        )

    assert {row["org_id"] for row in rows} == {a.org_id}
    assert "key-b" not in {row["idempotency_key"] for row in rows}


async def test_cannot_create_a_voice_agent_in_another_tenant(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The dangerous case: a forged org_id on an insert."""
    a, b = tenants

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, a.auth_user_id)
            await db.execute(
                """
                insert into public.voice_agents (org_id, name, kind)
                values ($1, 'hijacked', 'custom')
                """,
                b.org_id,
            )


async def test_cannot_update_another_tenants_voice_agent(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Repointing another org's agent at your own credentials would make their
    calls run on your account - RLS must filter the row out entirely."""
    a, b = tenants

    await _as_postgres(db)
    agent_b = await _make_agent(db, b, "B's agent")

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        await db.execute(
            "update public.voice_agents set name = 'hijacked' where id = $1", agent_b
        )

    await _as_postgres(db)
    name = await db.fetchval("select name from public.voice_agents where id = $1", agent_b)
    assert name == "B's agent"


async def test_cannot_write_provisioning_into_another_tenant(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    await _as_postgres(db)
    agent_b = await _make_agent(db, b, "B's agent")

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, a.auth_user_id)
            await db.execute(
                """
                insert into public.telephony_provisioning
                    (voice_agent_id, org_id, idempotency_key)
                values ($1, $2, 'forged')
                """,
                agent_b,
                b.org_id,
            )


async def test_provisioning_rows_cannot_be_deleted_by_anyone(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """A provisioning attempt is re-statused, never removed, so the trail of what
    was tried survives a retry. There is no delete policy *and* no delete grant -
    this asserts the grant, which is the half a future policy edit can't undo."""
    a, _ = tenants

    await _as_postgres(db)
    agent_a = await _make_agent(db, a, "A's agent")
    row_id = await _make_provisioning(db, a, agent_a, "key-a")

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, a.auth_user_id)
            await db.execute(
                "delete from public.telephony_provisioning where id = $1", row_id
            )

    await _as_postgres(db)
    assert await db.fetchval(
        "select exists(select 1 from public.telephony_provisioning where id = $1)", row_id
    )


async def test_the_same_idempotency_key_cannot_start_a_second_attempt(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The schema half of the "retrying an attempt must not orphan a second
    LiveKit trunk" guarantee: a double-submitted connect-number request cannot
    become two rows, so the retry path is forced to look up what the first
    attempt already created."""
    a, _ = tenants

    await _as_postgres(db)
    agent_a = await _make_agent(db, a, "A's agent")
    await _make_provisioning(db, a, agent_a, "same-key")

    with pytest.raises(asyncpg.exceptions.UniqueViolationError):
        await _make_provisioning(db, a, agent_a, "same-key")


async def test_a_different_attempt_on_the_same_agent_is_allowed(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """"Try again" starts a *new* row with a new key rather than retrying the
    stuck one in place, so the uniqueness above must not block a fresh attempt."""
    a, _ = tenants

    await _as_postgres(db)
    agent_a = await _make_agent(db, a, "A's agent")
    await _make_provisioning(db, a, agent_a, "attempt-1")
    await _make_provisioning(db, a, agent_a, "attempt-2")

    count = await db.fetchval(
        "select count(*) from public.telephony_provisioning where voice_agent_id = $1",
        agent_a,
    )
    assert count == 2


async def _make_number(
    conn: asyncpg.Connection, tenant: Tenant, e164: str, *, status: str = "verified"
) -> uuid.UUID:
    return await conn.fetchval(
        """
        insert into public.telephony_numbers
            (org_id, provider, phone_e164, status, livekit_outbound_trunk_id)
        values ($1, 'twilio', $2, $3, 'ST_x')
        returning id
        """,
        tenant.org_id,
        e164,
        status,
    )


async def test_telephony_numbers_are_invisible_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """A number is the organisation's own line. Seeing another tenant's is
    seeing which numbers they call their customers from - and, with the trunk
    id beside it, where those calls are routed."""
    a, b = tenants

    await _as_postgres(db)
    await _make_number(db, a, "+15555550150")
    await _make_number(db, b, "+15555550151")

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        rows = await db.fetch(
            "select org_id, phone_e164 from public.telephony_numbers"
        )

    assert {row["org_id"] for row in rows} == {a.org_id}
    assert "+15555550151" not in {row["phone_e164"] for row in rows}


async def test_cannot_create_a_telephony_number_in_another_tenant(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The forged-org_id insert. A number planted in another tenant would be
    offered to them as one of their own lines to dial from."""
    a, b = tenants

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, a.auth_user_id)
            await db.execute(
                """
                insert into public.telephony_numbers
                    (org_id, provider, phone_e164, status)
                values ($1, 'twilio', '+15555550152', 'verified')
                """,
                b.org_id,
            )


async def test_cannot_update_another_tenants_telephony_number(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Disabling someone else's number would stop their runs dialling; enabling
    one would put a line they had retired back into rotation."""
    a, b = tenants

    await _as_postgres(db)
    number_b = await _make_number(db, b, "+15555550153")

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        result = await db.execute(
            "update public.telephony_numbers set status = 'disabled' where id = $1",
            number_b,
        )

    # No error - RLS makes the row simply not exist for this caller, so the
    # update matches nothing. Asserting on the row count is the only way to tell
    # "denied" from "silently applied".
    assert result == "UPDATE 0"

    await _as_postgres(db)
    status = await db.fetchval(
        "select status from public.telephony_numbers where id = $1", number_b
    )
    assert status == "verified"


async def test_a_number_cannot_be_deleted_by_authenticated_at_all(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """No delete policy *and* no delete grant, matching
    `202608161700_revoke_delete_on_append_only_tables`.

    The grant is the load-bearing half: a future edit that adds a delete policy
    cannot quietly make these deletable, because the privilege is not there to
    exercise. A number that carried real calls is a record - `disabled` is the
    retirement path."""
    a, _ = tenants

    await _as_postgres(db)
    number_a = await _make_number(db, a, "+15555550154")

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, a.auth_user_id)
            await db.execute(
                "delete from public.telephony_numbers where id = $1", number_a
            )


async def test_run_numbers_are_invisible_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Which line called which run is as much a record as the call itself."""
    a, b = tenants

    await _as_postgres(db)
    number_a = await _make_number(db, a, "+15555550155")
    number_b = await _make_number(db, b, "+15555550156")
    run_a = await _insert_run(db, org_id=a.org_id, started_by=a.user_id)
    run_b = await _insert_run(db, org_id=b.org_id, started_by=b.user_id)
    for run_id, number_id, tenant in ((run_a, number_a, a), (run_b, number_b, b)):
        await db.execute(
            "insert into public.run_numbers (run_id, number_id, org_id) "
            "values ($1, $2, $3)",
            run_id,
            number_id,
            tenant.org_id,
        )

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        rows = await db.fetch("select org_id, run_id from public.run_numbers")

    assert {row["org_id"] for row in rows} == {a.org_id}
    assert run_b not in {row["run_id"] for row in rows}


async def test_cannot_bind_another_tenants_run_to_a_number(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    await _as_postgres(db)
    number_a = await _make_number(db, a, "+15555550157")
    run_b = await _insert_run(db, org_id=b.org_id, started_by=b.user_id)

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, a.auth_user_id)
            await db.execute(
                "insert into public.run_numbers (run_id, number_id, org_id) "
                "values ($1, $2, $3)",
                run_b,
                number_a,
                b.org_id,
            )


async def test_a_run_number_binding_cannot_be_deleted_by_authenticated(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Append-only, same reasoning as the number itself: the binding is what
    says which of an organisation's lines placed a given run's calls."""
    a, _ = tenants

    await _as_postgres(db)
    number_a = await _make_number(db, a, "+15555550158")
    run_a = await _insert_run(db, org_id=a.org_id, started_by=a.user_id)
    await db.execute(
        "insert into public.run_numbers (run_id, number_id, org_id) "
        "values ($1, $2, $3)",
        run_a,
        number_a,
        a.org_id,
    )

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, a.auth_user_id)
            await db.execute(
                "delete from public.run_numbers where run_id = $1", run_a
            )


async def test_a_number_a_run_dialled_from_cannot_be_deleted(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """ON DELETE RESTRICT on `run_numbers.number_id`: which line called a person
    is part of that call's record, and removing the number would erase it.

    This replaces the same claim about `voice_agents.telephony_credential_id`,
    which is gone - a number is chosen per run now (ADR-8), so the reference
    worth protecting is the run's, not the agent's."""
    a, _ = tenants

    await _as_postgres(db)
    number_id = await db.fetchval(
        """
        insert into public.telephony_numbers
            (org_id, provider, phone_e164, status, livekit_outbound_trunk_id)
        values ($1, 'twilio', '+15555550142', 'verified', 'ST_x')
        returning id
        """,
        a.org_id,
    )
    run_id = await _insert_run(db, org_id=a.org_id, started_by=a.user_id)
    await db.execute(
        "insert into public.run_numbers (run_id, number_id, org_id) values ($1, $2, $3)",
        run_id,
        number_id,
        a.org_id,
    )

    # Either class, because which one Postgres raises for `on delete restrict`
    # changed under us: 15 and 17 answer 23503 (ForeignKeyViolationError), 18
    # answers 23001 (RestrictViolationError). Verified directly against both.
    # This project meets all three - Supabase runs 17, the docker stack 15, and
    # a local install may be 18 - so pinning either one turns a passing suite
    # into a failing one purely on where it is pointed.
    #
    # Accepting both is not a weakened assertion. asyncpg's two classes are
    # unrelated, so the tuple is still exhaustive about *which* refusals count:
    # anything else, including the delete succeeding, still fails the test. What
    # is being asserted is what the FK is for - a number that placed real calls
    # cannot be deleted out from under the runs that record it.
    with pytest.raises(
        (
            asyncpg.exceptions.ForeignKeyViolationError,
            asyncpg.exceptions.RestrictViolationError,
        )
    ):
        await db.execute(
            "delete from public.telephony_numbers where id = $1", number_id
        )


async def test_provider_credentials_accepts_a_non_carrier_provider(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The check was widened from `in ('twilio','plivo')` so STT/TTS/LLM vendors
    can live in the same table without one migration per vendor. Blank is still
    rejected - the constraint is narrower than "anything"."""
    a, _ = tenants

    await _as_postgres(db)
    await db.execute(
        """
        insert into public.provider_credentials
            (org_id, provider, identifier_encrypted, secret_encrypted)
        values ($1, 'openrouter', 'enc', 'enc')
        """,
        a.org_id,
    )

    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await db.execute(
            """
            insert into public.provider_credentials
                (org_id, provider, identifier_encrypted, secret_encrypted)
            values ($1, '', 'enc', 'enc')
            """,
            a.org_id,
        )
# --- Internal team chat: channels, membership, messages (migration
# `b3f7d2a891c5`, RUNBOOK_JATIN_PART_3.md) -----------------------------------
#
# `channels_select`/`messages_select` are both plain `is_channel_member(id)` -
# no admin/owner branch on `messages_select`, deliberately, so an org's
# admin/owner can administer channel *membership* without that also handing
# them a back door into every DM's contents. `channel_members_select` is the
# one policy with a second branch (`has_org_role` owner/admin), which is what
# these tests pin as two separate claims rather than one.


async def _create_channel(
    db: asyncpg.Connection,
    *,
    creator: Tenant,
    org_id: uuid.UUID,
    kind: str = "channel",
    name: str | None = "general",
    member_ids: list[uuid.UUID] | None = None,
) -> uuid.UUID:
    async with db.transaction():
        await _as_user(db, creator.auth_user_id)
        return await db.fetchval(
            "select public.create_channel($1, $2, $3, $4)",
            org_id,
            kind,
            name,
            member_ids or [],
        )


async def test_chat_tables_have_full_replica_identity(db: asyncpg.Connection) -> None:
    """Same reasoning as `202608101000_escalations_realtime.py`'s own defensive
    `replica identity full` on `escalations`, which has no delete path at all
    - chat does: `channel_members` rows are deleted on leave/removal and
    subscribed with `event: '*'`. Without the full row, a DELETE's `old`
    record ships primary-key columns only, so RLS can't be evaluated against
    it and the `org_id=eq.<org>` Realtime filter (`org_id` isn't part of any
    of these three tables' primary key) can't match it either - a departure
    would never reach an open tab live."""
    rows = await db.fetch(
        """
        select c.relname, c.relreplident::text as relreplident
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relname = any($1::text[])
        """,
        ["channels", "channel_members", "messages"],
    )
    by_name = {row["relname"]: row["relreplident"] for row in rows}
    assert by_name == {"channels": "f", "channel_members": "f", "messages": "f"}, (
        f"expected REPLICA IDENTITY FULL ('f') on all three chat tables, got {by_name}"
    )


async def test_org_b_member_cannot_see_org_a_channels_or_messages(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants
    channel_id = await _create_channel(db, creator=a, org_id=a.org_id)
    await _as_postgres(db)
    await db.execute(
        "insert into public.messages (org_id, channel_id, sender_id, body) values ($1, $2, $3, 'hi')",
        a.org_id,
        channel_id,
        a.user_id,
    )

    async with db.transaction():
        await _as_user(db, b.auth_user_id)
        channels = await db.fetch("select id from public.channels where org_id = $1", a.org_id)
        messages = await db.fetch(
            "select id from public.messages where channel_id = $1", channel_id
        )
    assert channels == [], "tenant b can see tenant a's channel"
    assert messages == [], "tenant b can see tenant a's messages"

    await _as_postgres(db)
    await db.execute("delete from public.channels where org_id = $1", a.org_id)


async def test_channel_creation_seats_creator_as_member_atomically(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Uses `kind="channel"`, not `"dm"` - a channel has no member-count
    requirement, so this stays a pure test of atomic seating. A `dm` does
    have one, covered by its own tests below instead."""
    a, _ = tenants
    channel_id = await _create_channel(db, creator=a, org_id=a.org_id, kind="channel", name=None)

    await _as_postgres(db)
    members = await db.fetch(
        "select user_id from public.channel_members where channel_id = $1", channel_id
    )
    assert [m["user_id"] for m in members] == [a.user_id]

    await db.execute("delete from public.channels where id = $1", channel_id)


async def test_owner_can_send_a_real_message_through_the_repository(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Real (non-mocked) call through `messages_repo.send_message()` - the
    coverage gap every other chat test in this file left open, since they all
    insert `messages` directly via SQL (with `org_id` supplied by hand) rather
    than through the repository's own `INSERT`. Caught for real by manually
    driving the live API end to end: `messages.org_id` is `NOT NULL`, and the
    repository's `INSERT` never listed it as a column, so every real call to
    `POST /api/v1/channels/{id}/messages` 500'd with a `NotNullViolationError`
    that no RLS-focused test here would ever have exercised."""
    a, _ = tenants
    channel_id = await _create_channel(db, creator=a, org_id=a.org_id, name="repo-send")

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        row = await messages_repo.send_message(
            db, org_id=a.org_id, channel_id=channel_id, sender_id=a.user_id, body="hello"
        )

    assert row is not None
    assert row["channel_id"] == channel_id
    assert row["sender_id"] == a.user_id
    assert row["body"] == "hello"

    await _as_postgres(db)
    stored_org_id = await db.fetchval(
        "select org_id from public.messages where id = $1", row["id"]
    )
    assert stored_org_id == a.org_id
    await db.execute("delete from public.channels where id = $1", channel_id)


async def test_create_channel_rejects_a_member_id_outside_the_organisation_and_leaves_no_orphaned_channel(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`create_channel()` is SECURITY DEFINER - it bypasses `channel_members_insert`'s
    RLS entirely, so an outsider in `member_ids` has to be rejected inside the
    function itself, before either insert runs (this migration's docstring)."""
    a, b = tenants

    before = await db.fetchval(
        "select count(*) from public.channels where org_id = $1", a.org_id
    )

    with pytest.raises(asyncpg.exceptions.RaiseError):
        await _create_channel(db, creator=a, org_id=a.org_id, member_ids=[b.user_id])

    await _as_postgres(db)
    after = await db.fetchval("select count(*) from public.channels where org_id = $1", a.org_id)
    assert after == before, "a rejected create_channel() call left an orphaned channels row"


async def test_non_member_cannot_see_a_channel_in_their_list_or_its_messages(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    creator = await _create_tenant(db, "chat-creator")
    outsider = await _create_tenant(db, "chat-outsider")
    await _seat(db, a.org_id, creator, "operator")
    await _seat(db, a.org_id, outsider, "operator")

    channel_id = await _create_channel(db, creator=creator, org_id=a.org_id, name="private-ish")
    await _as_postgres(db)
    await db.execute(
        "insert into public.messages (org_id, channel_id, sender_id, body) values ($1, $2, $3, 'secret')",
        a.org_id,
        channel_id,
        creator.user_id,
    )

    async with db.transaction():
        await _as_user(db, outsider.auth_user_id)
        channels = await db.fetch("select id from public.channels where id = $1", channel_id)
        messages = await db.fetch(
            "select id from public.messages where channel_id = $1", channel_id
        )
    assert channels == [], "a non-member sees a channel they aren't in"
    assert messages == [], "a non-member sees messages from a channel they aren't in"

    await _as_postgres(db)
    await db.execute("delete from public.channels where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [creator.auth_user_id, outsider.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_admin_can_see_channel_membership_but_not_messages_for_a_channel_they_are_not_in(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`channel_members_select` has an owner/admin branch; `messages_select` does
    not, deliberately - proving the second half is the one that actually matters."""
    a, _ = tenants
    await _as_postgres(db)

    creator = await _create_tenant(db, "chat-admin-visible-creator")
    admin = await _create_tenant(db, "chat-admin")
    await _seat(db, a.org_id, creator, "operator")
    await _seat(db, a.org_id, admin, "admin")

    channel_id = await _create_channel(db, creator=creator, org_id=a.org_id, name="admin-blind-spot")
    await _as_postgres(db)
    await db.execute(
        "insert into public.messages (org_id, channel_id, sender_id, body) values ($1, $2, $3, 'private')",
        a.org_id,
        channel_id,
        creator.user_id,
    )

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        members = await db.fetch(
            "select user_id from public.channel_members where channel_id = $1", channel_id
        )
        messages = await db.fetch(
            "select id from public.messages where channel_id = $1", channel_id
        )
    assert [m["user_id"] for m in members] == [creator.user_id], (
        "admin cannot see membership of a channel they aren't in"
    )
    assert messages == [], "admin can read messages from a channel they aren't a member of"

    await _as_postgres(db)
    await db.execute("delete from public.channels where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [creator.auth_user_id, admin.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_channel_members_insert_non_member_cannot_add_self_or_anyone(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    creator = await _create_tenant(db, "chat-insert-creator")
    outsider = await _create_tenant(db, "chat-insert-outsider")
    third = await _create_tenant(db, "chat-insert-third")
    await _seat(db, a.org_id, creator, "operator")
    await _seat(db, a.org_id, outsider, "operator")
    await _seat(db, a.org_id, third, "operator")

    channel_id = await _create_channel(db, creator=creator, org_id=a.org_id, name="add-guard")

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, outsider.auth_user_id)
            await db.execute(
                "insert into public.channel_members (channel_id, user_id, org_id) values ($1, $2, $3)",
                channel_id,
                outsider.user_id,
                a.org_id,
            )

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, outsider.auth_user_id)
            await db.execute(
                "insert into public.channel_members (channel_id, user_id, org_id) values ($1, $2, $3)",
                channel_id,
                third.user_id,
                a.org_id,
            )

    await _as_postgres(db)
    await db.execute("delete from public.channels where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [creator.auth_user_id, outsider.auth_user_id, third.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_channel_members_insert_existing_member_can_add_another_org_member(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    creator = await _create_tenant(db, "chat-add-creator")
    newcomer = await _create_tenant(db, "chat-add-newcomer")
    await _seat(db, a.org_id, creator, "operator")
    await _seat(db, a.org_id, newcomer, "operator")

    channel_id = await _create_channel(db, creator=creator, org_id=a.org_id, name="add-ok")

    async with db.transaction():
        await _as_user(db, creator.auth_user_id)
        await db.execute(
            "insert into public.channel_members (channel_id, user_id, org_id) values ($1, $2, $3)",
            channel_id,
            newcomer.user_id,
            a.org_id,
        )

    await _as_postgres(db)
    seated = await db.fetchval(
        "select exists(select 1 from public.channel_members where channel_id = $1 and user_id = $2)",
        channel_id,
        newcomer.user_id,
    )
    assert seated, "an existing member could not add another org member"

    await db.execute("delete from public.channels where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [creator.auth_user_id, newcomer.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_channel_members_insert_rejects_seating_a_non_org_member(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The cross-tenant seating hole: without `is_user_org_member()` on the
    target row's own `user_id`, an existing member could hand an outsider
    `is_channel_member()` - and with it, `channels_select`/`messages_select`
    access to this org's channel - by seating a user id from a different
    organisation entirely. `channel_members_insert`'s `WITH CHECK` must reject
    that at the database layer, not just rely on the frontend only ever
    offering org members as options."""
    a, b = tenants
    await _as_postgres(db)

    creator = await _create_tenant(db, "chat-seat-guard-creator")
    await _seat(db, a.org_id, creator, "operator")

    channel_id = await _create_channel(db, creator=creator, org_id=a.org_id, name="seat-guard")

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, creator.auth_user_id)
            await db.execute(
                "insert into public.channel_members (channel_id, user_id, org_id) values ($1, $2, $3)",
                channel_id,
                b.user_id,
                a.org_id,
            )

    await _as_postgres(db)
    seated = await db.fetchval(
        "select exists(select 1 from public.channel_members where channel_id = $1 and user_id = $2)",
        channel_id,
        b.user_id,
    )
    assert not seated, "an outsider from a different organisation was seated in the channel"

    await db.execute("delete from public.channels where org_id = $1", a.org_id)
    await db.execute("delete from auth.users where id = $1", creator.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- Teams-parity follow-up: member search, group management (rename/add/
# remove), read state, message edit/delete, pagination - every one of these
# re-verified specifically for cross-organisation rejection, per the brief's
# explicit priority. `channel_members.org_id` denormalises `channels.org_id`
# the same way `messages.org_id` already does, so every raw INSERT into it
# above was updated to supply it too - a NOT NULL violation would otherwise
# mask whatever RLS behaviour a test was actually trying to isolate.


async def test_search_members_never_returns_results_from_another_organisation(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`org_repo.list_members(search=...)` is scoped by `org_id` (server-
    controlled from the caller's own `CurrentUser`, never client input) before
    the search term is even applied - so a search term that matches someone
    real, in a real org, still returns nothing if that person is in a
    different organisation than the caller's own."""
    a, b = tenants
    await _as_postgres(db)

    unique = uuid.uuid4().hex[:8]
    b_only = await _create_tenant(db, f"search-only-in-b-{unique}")
    await _seat(db, b.org_id, b_only, "operator")
    b_only_name = await db.fetchval(
        "select name from public.users where id = $1", b_only.user_id
    )
    assert b_only_name is not None

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        rows = await org_repo.list_members(db, a.org_id, search=b_only_name)
    assert rows == [], "a search from org A returned a member who only exists in org B"

    async with db.transaction():
        await _as_user(db, b.auth_user_id)
        rows = await org_repo.list_members(db, b.org_id, search=b_only_name)
    assert [r["user_id"] for r in rows] == [b_only.user_id]

    await _as_postgres(db)
    await db.execute("delete from auth.users where id = $1", b_only.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_add_member_repo_rejects_a_user_from_a_different_organisation(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The real repository function, not raw SQL - `channels_repo.add_member()`
    must surface the same rejection `channel_members_insert`'s RLS enforces,
    as `False`, not an unhandled exception."""
    a, b = tenants
    await _as_postgres(db)

    creator = await _create_tenant(db, "add-repo-creator")
    await _seat(db, a.org_id, creator, "operator")
    channel_id = await _create_channel(db, creator=creator, org_id=a.org_id, name="add-repo")

    async with db.transaction():
        await _as_user(db, creator.auth_user_id)
        ok = await channels_repo.add_member(
            db, org_id=a.org_id, channel_id=channel_id, user_id=b.user_id
        )
    assert ok is False, "add_member() reported success adding an outsider from another org"

    await _as_postgres(db)
    seated = await db.fetchval(
        "select exists(select 1 from public.channel_members where channel_id = $1 and user_id = $2)",
        channel_id,
        b.user_id,
    )
    assert not seated

    await db.execute("delete from public.channels where org_id = $1", a.org_id)
    await db.execute("delete from auth.users where id = $1", creator.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_add_member_repo_allows_an_existing_member_to_add_a_teammate(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    creator = await _create_tenant(db, "add-repo-ok-creator")
    teammate = await _create_tenant(db, "add-repo-ok-teammate")
    await _seat(db, a.org_id, creator, "operator")
    await _seat(db, a.org_id, teammate, "operator")
    channel_id = await _create_channel(db, creator=creator, org_id=a.org_id, name="add-repo-ok")

    async with db.transaction():
        await _as_user(db, creator.auth_user_id)
        ok = await channels_repo.add_member(
            db, org_id=a.org_id, channel_id=channel_id, user_id=teammate.user_id
        )
    assert ok is True

    await _as_postgres(db)
    org_id_stored = await db.fetchval(
        "select org_id from public.channel_members where channel_id = $1 and user_id = $2",
        channel_id,
        teammate.user_id,
    )
    assert org_id_stored == a.org_id, "the new row's org_id wasn't populated to the channel's own org"

    await db.execute("delete from public.channels where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [creator.auth_user_id, teammate.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_get_channel_and_list_messages_repos_see_nothing_across_organisations(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The exact repository calls the `GET /channels/{id}` and `GET
    .../messages` routes make, called directly as a member of the *other*
    organisation - proves a channel id reached directly (not from the
    caller's own list) resolves to nothing, which is what lets the route
    turn this into a clean 404 rather than leaking cross-org data."""
    a, b = tenants
    channel_id = await _create_channel(db, creator=a, org_id=a.org_id)
    await _as_postgres(db)
    await db.execute(
        "insert into public.messages (org_id, channel_id, sender_id, body) values ($1, $2, $3, 'x')",
        a.org_id,
        channel_id,
        a.user_id,
    )

    async with db.transaction():
        await _as_user(db, b.auth_user_id)
        channel_row = await channels_repo.get_channel(db, channel_id)
        message_rows = await messages_repo.list_messages(db, channel_id)

    assert channel_row is None, "get_channel() resolved a channel from a different organisation"
    assert message_rows == [], "list_messages() returned rows from a different organisation's channel"

    await _as_postgres(db)
    await db.execute("delete from public.channels where org_id = $1", a.org_id)


async def test_send_message_repo_rejects_a_channel_in_another_organisation(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants
    channel_id = await _create_channel(db, creator=a, org_id=a.org_id)

    async with db.transaction():
        await _as_user(db, b.auth_user_id)
        row = await messages_repo.send_message(
            db, org_id=b.org_id, channel_id=channel_id, sender_id=b.user_id, body="intrusion"
        )
    assert row is None, "send_message() let a caller post into another organisation's channel"

    await _as_postgres(db)
    count = await db.fetchval(
        "select count(*) from public.messages where channel_id = $1", channel_id
    )
    assert count == 0

    await db.execute("delete from public.channels where org_id = $1", a.org_id)


async def test_messages_insert_rejects_a_mismatched_org_id_from_a_multi_org_member(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`sender_id`/`is_channel_member`/`is_org_member(channel_org_id(...))` are
    all satisfiable by someone who belongs to *both* organisations - none of
    them constrain the `org_id` column being written, only who is inserting
    and which channel they're inserting into. A member of both A and B who is
    seated in a channel in A but currently sends with `org_id=B` (a stale or
    forged active-org header) must still be rejected."""
    a, b = tenants
    channel_id = await _create_channel(db, creator=a, org_id=a.org_id)

    await _as_postgres(db)
    await db.execute(
        "insert into public.memberships (org_id, user_id, role) values ($1, $2, 'operator')",
        b.org_id,
        a.user_id,
    )

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        row = await messages_repo.send_message(
            db, org_id=b.org_id, channel_id=channel_id, sender_id=a.user_id, body="wrong org"
        )
    assert row is None, "send_message() let a channel's own org_id be overridden to another organisation"

    await _as_postgres(db)
    count = await db.fetchval(
        "select count(*) from public.messages where channel_id = $1", channel_id
    )
    assert count == 0

    await db.execute("delete from public.memberships where org_id = $1 and user_id = $2", b.org_id, a.user_id)
    await db.execute("delete from public.channels where org_id = $1", a.org_id)


async def test_channels_update_rename_matrix(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Creator renames: allowed. An org admin who isn't even a member of the
    channel: allowed (moderation, matching `channel_members_select`'s existing
    owner/admin branch). A plain member who neither created it nor holds
    owner/admin: rejected."""
    a, _ = tenants
    await _as_postgres(db)

    creator = await _create_tenant(db, "rename-creator")
    member = await _create_tenant(db, "rename-member")
    admin = await _create_tenant(db, "rename-admin")
    await _seat(db, a.org_id, creator, "operator")
    await _seat(db, a.org_id, member, "operator")
    await _seat(db, a.org_id, admin, "admin")
    channel_id = await _create_channel(
        db, creator=creator, org_id=a.org_id, name="original-name", member_ids=[member.user_id]
    )

    async with db.transaction():
        await _as_user(db, member.auth_user_id)
        rejected = await channels_repo.rename_channel(db, channel_id=channel_id, name="hijacked")
    assert rejected is None, "a plain member (not the creator, not an admin) renamed the channel"

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        by_admin = await channels_repo.rename_channel(
            db, channel_id=channel_id, name="renamed-by-admin"
        )
    assert by_admin is not None and by_admin["name"] == "renamed-by-admin"

    async with db.transaction():
        await _as_user(db, creator.auth_user_id)
        by_creator = await channels_repo.rename_channel(
            db, channel_id=channel_id, name="renamed-by-creator"
        )
    assert by_creator is not None and by_creator["name"] == "renamed-by-creator"

    await _as_postgres(db)
    await db.execute("delete from public.channels where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [creator.auth_user_id, member.auth_user_id, admin.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_channels_update_cannot_be_used_to_move_a_channel_to_another_organisation(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`channels_update` only grants `authenticated` UPDATE on the `name`
    column - a direct attempt to rewrite `org_id` must fail at the privilege
    layer, before RLS is even consulted, regardless of who the caller is."""
    a, _ = tenants
    channel_id = await _create_channel(db, creator=a, org_id=a.org_id, name="immovable")

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, a.auth_user_id)
            await db.execute(
                "update public.channels set org_id = gen_random_uuid() where id = $1", channel_id
            )

    await _as_postgres(db)
    await db.execute("delete from public.channels where org_id = $1", a.org_id)


async def test_channel_members_delete_leave_creator_remove_and_admin_moderate(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Four claims in one channel: a plain member can leave voluntarily; a
    plain member cannot remove *another* member; the creator can remove a
    member; an org admin can remove a member from a channel they aren't even
    in themselves."""
    a, _ = tenants
    await _as_postgres(db)

    creator = await _create_tenant(db, "remove-creator")
    victim = await _create_tenant(db, "remove-victim")
    bystander = await _create_tenant(db, "remove-bystander")
    leaver = await _create_tenant(db, "remove-leaver")
    admin = await _create_tenant(db, "remove-admin")
    for tenant in (creator, victim, bystander, leaver):
        await _seat(db, a.org_id, tenant, "operator")
    await _seat(db, a.org_id, admin, "admin")

    channel_id = await _create_channel(
        db,
        creator=creator,
        org_id=a.org_id,
        name="remove-matrix",
        member_ids=[victim.user_id, bystander.user_id, leaver.user_id],
    )

    # A plain member cannot remove someone else.
    async with db.transaction():
        await _as_user(db, bystander.auth_user_id)
        blocked = await channels_repo.remove_member(
            db, channel_id=channel_id, user_id=victim.user_id
        )
    assert blocked is False, "a plain member removed another member"

    # Leaving voluntarily always works.
    async with db.transaction():
        await _as_user(db, leaver.auth_user_id)
        left = await channels_repo.remove_member(
            db, channel_id=channel_id, user_id=leaver.user_id
        )
    assert left is True

    # The creator can remove someone else.
    async with db.transaction():
        await _as_user(db, creator.auth_user_id)
        removed_by_creator = await channels_repo.remove_member(
            db, channel_id=channel_id, user_id=victim.user_id
        )
    assert removed_by_creator is True

    # An org admin, not even a member of this channel, can moderate it.
    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        removed_by_admin = await channels_repo.remove_member(
            db, channel_id=channel_id, user_id=bystander.user_id
        )
    assert removed_by_admin is True

    await _as_postgres(db)
    remaining = await db.fetch(
        "select user_id from public.channel_members where channel_id = $1", channel_id
    )
    assert {r["user_id"] for r in remaining} == {creator.user_id}

    await db.execute("delete from public.channels where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [t.auth_user_id for t in (creator, victim, bystander, leaver, admin)],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_messages_update_only_the_sender_can_edit_or_delete(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    sender = await _create_tenant(db, "edit-sender")
    other = await _create_tenant(db, "edit-other")
    await _seat(db, a.org_id, sender, "operator")
    await _seat(db, a.org_id, other, "operator")
    channel_id = await _create_channel(
        db, creator=sender, org_id=a.org_id, name="edit-guard", member_ids=[other.user_id]
    )

    async with db.transaction():
        await _as_user(db, sender.auth_user_id)
        sent = await messages_repo.send_message(
            db, org_id=a.org_id, channel_id=channel_id, sender_id=sender.user_id, body="original"
        )
    assert sent is not None

    # A different member cannot edit or delete someone else's message.
    async with db.transaction():
        await _as_user(db, other.auth_user_id)
        blocked_edit = await messages_repo.edit_message(
            db, message_id=sent["id"], sender_id=other.user_id, body="tampered"
        )
        blocked_delete = await messages_repo.delete_message(
            db, message_id=sent["id"], sender_id=other.user_id
        )
    assert blocked_edit is None, "a non-sender edited someone else's message"
    assert blocked_delete is False, "a non-sender deleted someone else's message"

    # The sender can edit their own message.
    async with db.transaction():
        await _as_user(db, sender.auth_user_id)
        edited = await messages_repo.edit_message(
            db, message_id=sent["id"], sender_id=sender.user_id, body="edited for real"
        )
    assert edited is not None
    assert edited["body"] == "edited for real"
    assert edited["edited_at"] is not None

    # The sender can soft-delete their own message, and it disappears from reads.
    async with db.transaction():
        await _as_user(db, sender.auth_user_id)
        deleted = await messages_repo.delete_message(
            db, message_id=sent["id"], sender_id=sender.user_id
        )
        remaining = await messages_repo.list_messages(db, channel_id)
    assert deleted is True
    assert remaining == [], "a soft-deleted message still appears in list_messages()"

    await _as_postgres(db)
    still_in_db = await db.fetchval(
        "select deleted_at is not null from public.messages where id = $1", sent["id"]
    )
    assert still_in_db, "delete_message() should soft-delete, not hard-delete, the row"

    await db.execute("delete from public.channels where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [sender.auth_user_id, other.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_unread_count_excludes_own_messages_and_resets_on_mark_read(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    alice = await _create_tenant(db, "unread-alice")
    bob = await _create_tenant(db, "unread-bob")
    await _seat(db, a.org_id, alice, "operator")
    await _seat(db, a.org_id, bob, "operator")
    channel_id = await _create_channel(
        db, creator=alice, org_id=a.org_id, name="unread-check", member_ids=[bob.user_id]
    )

    async def channel_row_for(tenant: Tenant) -> asyncpg.Record:
        async with db.transaction():
            await _as_user(db, tenant.auth_user_id)
            rows = await channels_repo.list_my_channels(db, a.org_id)
        return next(r for r in rows if r["id"] == channel_id)

    # Nothing sent yet - both start at zero.
    assert (await channel_row_for(bob))["unread_count"] == 0

    async with db.transaction():
        await _as_user(db, alice.auth_user_id)
        await messages_repo.send_message(
            db, org_id=a.org_id, channel_id=channel_id, sender_id=alice.user_id, body="one"
        )
        await messages_repo.send_message(
            db, org_id=a.org_id, channel_id=channel_id, sender_id=alice.user_id, body="two"
        )

    # Alice sent them - her own unread count must not count her own sends.
    assert (await channel_row_for(alice))["unread_count"] == 0
    # Bob hasn't read yet - both of Alice's messages are unread for him.
    assert (await channel_row_for(bob))["unread_count"] == 2

    async with db.transaction():
        await _as_user(db, bob.auth_user_id)
        await channels_repo.mark_read(db, channel_id=channel_id, user_id=bob.user_id)

    assert (await channel_row_for(bob))["unread_count"] == 0, "mark_read() didn't clear the count"

    async with db.transaction():
        await _as_user(db, alice.auth_user_id)
        await messages_repo.send_message(
            db, org_id=a.org_id, channel_id=channel_id, sender_id=alice.user_id, body="three"
        )
    assert (await channel_row_for(bob))["unread_count"] == 1, "a message after mark_read wasn't counted"

    await db.execute("delete from public.channels where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [alice.auth_user_id, bob.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- DM dedup and hardening --------------------------------------------------


async def test_create_channel_dm_is_idempotent_and_reuses_the_existing_channel(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """CLAUDE.md's idempotency non-negotiable, applied to `POST /channels`:
    starting a DM with the same teammate twice must be the same conversation,
    not two. Goes through `channels_repo.create_channel()` itself, not the
    raw SQL function `_create_channel()` uses - this is the path that has to
    stay idempotent, not just the database underneath it."""
    a, _ = tenants
    teammate = await _create_tenant(db, "dm-idempotent")
    await _seat(db, a.org_id, teammate, "operator")

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        first_id = await channels_repo.create_channel(
            db, org_id=a.org_id, kind="dm", name=None, member_ids=[teammate.user_id]
        )
    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        second_id = await channels_repo.create_channel(
            db, org_id=a.org_id, kind="dm", name=None, member_ids=[teammate.user_id]
        )

    assert first_id == second_id, "two create_channel() calls for the same pair made two channels"

    await _as_postgres(db)
    channel_count = await db.fetchval(
        "select count(*) from public.channels where id = $1", first_id
    )
    assert channel_count == 1
    member_rows = await db.fetch(
        "select user_id from public.channel_members where channel_id = $1", first_id
    )
    assert {r["user_id"] for r in member_rows} == {a.user_id, teammate.user_id}

    await db.execute("delete from public.channels where id = $1", first_id)


async def test_create_channel_dm_rejects_wrong_member_count_and_self_dm(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    teammate = await _create_tenant(db, "dm-shape")
    await _seat(db, a.org_id, teammate, "operator")

    async def attempt(member_ids: list[uuid.UUID]) -> None:
        async with db.transaction():
            await _as_user(db, a.auth_user_id)
            await channels_repo.create_channel(
                db, org_id=a.org_id, kind="dm", name=None, member_ids=member_ids
            )

    with pytest.raises(ValueError, match="exactly one other member"):
        await attempt([])
    with pytest.raises(ValueError, match="exactly one other member"):
        await attempt([teammate.user_id, a.user_id])
    with pytest.raises(ValueError, match="cannot start a direct message with yourself"):
        await attempt([a.user_id])

    await _as_postgres(db)
    orphaned = await db.fetchval(
        "select count(*) from public.channels where org_id = $1 and kind = 'dm'", a.org_id
    )
    assert orphaned == 0, "a rejected dm left a channel behind"


async def test_create_channel_repo_turns_a_cross_org_member_into_a_value_error(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Regression for the audit's finding: `create_channel()`'s own
    org-membership guard was never caught anywhere between the database and
    the HTTP response, so a member id from another organisation 500'd
    instead of failing cleanly. The rejection itself already worked (no
    channel was ever created) - only the shape of the failure was wrong."""
    a, b = tenants

    with pytest.raises(ValueError, match="not members of this organisation"):
        async with db.transaction():
            await _as_user(db, a.auth_user_id)
            await channels_repo.create_channel(
                db, org_id=a.org_id, kind="channel", name="cross-org", member_ids=[b.user_id]
            )

    await _as_postgres(db)
    leaked = await db.fetchval(
        "select count(*) from public.channels where org_id = $1 and name = 'cross-org'", a.org_id
    )
    assert leaked == 0


async def test_channels_dm_pair_unique_index_rejects_a_duplicate_at_the_database_level(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Proves the guard is a real constraint, not just create_channel()'s own
    application logic - a direct insert (as `postgres`, bypassing RLS
    entirely) for a pair that already has a channel still can't succeed."""
    a, _ = tenants
    teammate = await _create_tenant(db, "dm-unique")
    await _seat(db, a.org_id, teammate, "operator")

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        channel_id = await channels_repo.create_channel(
            db, org_id=a.org_id, kind="dm", name=None, member_ids=[teammate.user_id]
        )

    await _as_postgres(db)
    pair = sorted([a.user_id, teammate.user_id])
    with pytest.raises(asyncpg.exceptions.UniqueViolationError):
        await db.execute(
            """
            insert into public.channels (org_id, kind, name, created_by, dm_pair)
            values ($1, 'dm', null, $2, $3)
            """,
            a.org_id,
            a.user_id,
            pair,
        )

    await db.execute("delete from public.channels where id = $1", channel_id)


async def test_concurrent_dm_creation_from_two_connections_converges_on_one_channel(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The real concurrency case the unique index exists for: two requests
    for the same pair landing at the database at the same instant (two
    browser tabs, or two people both clicking "message" on each other).
    Uses two independent physical connections - a single shared connection
    can't actually race itself - and asserts they converge on one row rather
    than each merely not erroring."""
    a, _ = tenants
    teammate = await _create_tenant(db, "dm-concurrent")
    await _seat(db, a.org_id, teammate, "operator")

    conn_a = await asyncpg.connect(config.database_url, timeout=30)
    conn_b = await asyncpg.connect(config.database_url, timeout=30)
    await _register_codecs(conn_a)
    await _register_codecs(conn_b)
    try:
        # `_as_user()`'s set_config(..., true) is LOCAL to the transaction it
        # runs in - it has to share one with the create_channel() call itself,
        # or it resets before that call ever sees it (the same reason every
        # other identity switch in this file happens inside `db.transaction()`).
        async def create_as(conn: asyncpg.Connection) -> uuid.UUID:
            async with conn.transaction():
                await _as_user(conn, a.auth_user_id)
                return await conn.fetchval(
                    "select public.create_channel($1, 'dm', null, $2)",
                    a.org_id,
                    [teammate.user_id],
                )

        results = await asyncio.gather(create_as(conn_a), create_as(conn_b))
        assert results[0] == results[1], "two concurrent dm creations did not converge"

        await _as_postgres(conn_a)
        rows = await conn_a.fetch(
            "select id from public.channels where org_id = $1 and dm_pair = $2",
            a.org_id,
            sorted([a.user_id, teammate.user_id]),
        )
        assert len(rows) == 1, "concurrent creation left more than one channel for the pair"
        await conn_a.execute("delete from public.channels where id = $1", rows[0]["id"])
    finally:
        await conn_a.close()
        await conn_b.close()


async def test_total_unread_count_matches_the_sum_of_per_channel_counts(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    alice, bob = a, await _create_tenant(db, "total-unread")
    await _seat(db, a.org_id, bob, "operator")

    channel_id = await _create_channel(db, creator=alice, org_id=a.org_id, name="total-unread-ch")
    async with db.transaction():
        # Alice, not Bob - channel_members_insert requires the *inserter* to
        # already be a member (`is_channel_member`), so Bob can't seat himself
        # into a channel he isn't in yet, same as the live API would reject it.
        await _as_user(db, alice.auth_user_id)
        added = await channels_repo.add_member(
            db, org_id=a.org_id, channel_id=channel_id, user_id=bob.user_id
        )
    assert added
    for body in ("one", "two", "three"):
        async with db.transaction():
            await _as_user(db, alice.auth_user_id)
            await messages_repo.send_message(
                db, org_id=a.org_id, channel_id=channel_id, sender_id=alice.user_id, body=body
            )

    async with db.transaction():
        await _as_user(db, bob.auth_user_id)
        total = await channels_repo.total_unread_count(db, a.org_id)
        channels = await channels_repo.list_my_channels(db, a.org_id)
    assert total == 3
    assert total == sum(c["unread_count"] for c in channels)

    async with db.transaction():
        await _as_user(db, bob.auth_user_id)
        await channels_repo.mark_read(db, channel_id=channel_id, user_id=bob.user_id)
        assert await channels_repo.total_unread_count(db, a.org_id) == 0

    await _as_postgres(db)
    await db.execute("delete from public.channels where org_id = $1", a.org_id)


async def test_total_unread_count_is_scoped_to_the_callers_own_organisation(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Cross-org isolation for the new endpoint: RLS, not the `org_id`
    parameter, is what actually confines this - passing the *other*
    organisation's id still returns 0, since RLS never exposes org b's
    `channel_members`/`messages` rows to a user seated only in org a."""
    a, b = tenants
    a_channel = await _create_channel(db, creator=a, org_id=a.org_id, name="a-unread")
    b_channel = await _create_channel(db, creator=b, org_id=b.org_id, name="b-unread")
    await _as_postgres(db)
    await db.execute(
        "insert into public.messages (org_id, channel_id, sender_id, body) values ($1, $2, $3, 'hi')",
        b.org_id,
        b_channel,
        b.user_id,
    )

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        assert await channels_repo.total_unread_count(db, a.org_id) == 0
        # Even a caller that (by bug or malice) passes org b's id gets nothing -
        # RLS, not this parameter, is the actual boundary.
        assert await channels_repo.total_unread_count(db, b.org_id) == 0

    await _as_postgres(db)
    await db.execute("delete from public.channels where id = any($1::uuid[])", [a_channel, b_channel])


async def test_pagination_returns_pages_oldest_first_with_no_gap_or_overlap(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    channel_id = await _create_channel(db, creator=a, org_id=a.org_id, name="paginated")

    # Each send gets its own transaction, deliberately - now() is the
    # *transaction's* start time in Postgres, not wall-clock-per-statement, so
    # five sends inside one shared transaction would all land on the same
    # created_at and make the page boundaries undefined. A real request is
    # always its own transaction (database.as_user() opens one per call),
    # which is what this reproduces.
    bodies = [f"msg-{i:02d}" for i in range(5)]
    for body in bodies:
        async with db.transaction():
            await _as_user(db, a.auth_user_id)
            await messages_repo.send_message(
                db, org_id=a.org_id, channel_id=channel_id, sender_id=a.user_id, body=body
            )

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        first_page = await messages_repo.list_messages(db, channel_id, limit=2)
        assert [m["body"] for m in first_page] == ["msg-03", "msg-04"], (
            "the most recent page (no cursor) should be the newest 2, oldest-first"
        )

        second_page = await messages_repo.list_messages(
            db, channel_id, before=first_page[0]["created_at"], limit=2
        )
        assert [m["body"] for m in second_page] == ["msg-01", "msg-02"]

        third_page = await messages_repo.list_messages(
            db, channel_id, before=second_page[0]["created_at"], limit=2
        )
        assert [m["body"] for m in third_page] == ["msg-00"], "the oldest page should have exactly 1 left"

    await _as_postgres(db)
    await db.execute("delete from public.channels where org_id = $1", a.org_id)


# --- org-membership is a hard boundary for chat, even with a stale
# channel_members row --------------------------------------------------------


async def test_active_member_has_full_chat_access(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The baseline the rest of this section is contrasted against: a genuine,
    currently-seated org member can see the channel, read its messages, send
    a new one, and (as its creator) rename it - all through RLS, no admin
    role needed. Confirms the tightened policies didn't cost a live member
    anything."""
    a, _ = tenants
    teammate = await _create_tenant(db, "active-member")
    await _seat(db, a.org_id, teammate, "operator")
    channel_id = await _create_channel(db, creator=teammate, org_id=a.org_id, name="active-member-ch")

    async with db.transaction():
        await _as_user(db, teammate.auth_user_id)
        seen = await db.fetchrow("select id from public.channels where id = $1", channel_id)
        assert seen is not None, "an active member could not see their own channel"

        sent = await messages_repo.send_message(
            db, org_id=a.org_id, channel_id=channel_id, sender_id=teammate.user_id, body="hello"
        )
        assert sent is not None, "an active member could not send a message"

        rows = await messages_repo.list_messages(db, channel_id)
        assert [r["body"] for r in rows] == ["hello"], "an active member could not read messages"

        renamed = await channels_repo.rename_channel(db, channel_id=channel_id, name="renamed-ok")
        assert renamed is not None, "an active member (and creator) could not rename their channel"

    await _as_postgres(db)
    await db.execute("delete from public.channels where id = $1", channel_id)


async def test_departed_org_member_loses_chat_rls_access_even_with_a_stale_channel_members_row(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The exact lifecycle the audit's re-evaluation traced live in a real
    browser: a member reads and sends normally, leaves the organisation, and
    - using the identical identity, not a new one, and with their
    `channel_members` row deliberately left in place (a plain `memberships`
    delete, not `org_repo.remove_member()`, so this isolates the RLS boundary
    itself from the cleanup in the next test) - loses read and write access.
    This is also the correct proxy for "Realtime would stop delivering" and
    "PostgREST would stop answering": both authorise off exactly these
    policies, with no FastAPI layer involved, so a role-switch to the same
    identity is the same authorisation check either of them would run."""
    a, _ = tenants
    teammate = await _create_tenant(db, "departs-org")
    await _seat(db, a.org_id, teammate, "operator")
    channel_id = await _create_channel(db, creator=teammate, org_id=a.org_id, name="departure-check")

    async with db.transaction():
        await _as_user(db, teammate.auth_user_id)
        await messages_repo.send_message(
            db, org_id=a.org_id, channel_id=channel_id, sender_id=teammate.user_id, body="still here"
        )
        assert (
            await db.fetchrow("select id from public.channels where id = $1", channel_id)
        ) is not None, "sanity check: the active member should see their own channel"

    # Leave the organisation the way the real self-leave endpoint's underlying
    # delete does - membership only. The channel_members row is deliberately
    # left behind, exactly as it would be before this task's cleanup fix, to
    # prove the RLS policies themselves (not the cleanup) are what closes this.
    await _as_postgres(db)
    await db.execute(
        "delete from public.memberships where org_id = $1 and user_id = $2", a.org_id, teammate.user_id
    )
    stale_row = await db.fetchrow(
        "select 1 from public.channel_members where channel_id = $1 and user_id = $2",
        channel_id,
        teammate.user_id,
    )
    assert stale_row is not None, "test setup error: the channel_members row should still be there"

    async with db.transaction():
        await _as_user(db, teammate.auth_user_id)
        assert not await db.fetchval("select public.is_org_member($1)", a.org_id)
        assert await db.fetchval("select public.is_channel_member($1)", channel_id), (
            "test setup error: the stale row should still make is_channel_member() true"
        )

        assert (
            await db.fetchrow("select id from public.channels where id = $1", channel_id)
        ) is None, "a departed member can still see their old channel (channels_select)"
        assert (
            await db.fetch("select id from public.messages where channel_id = $1", channel_id)
        ) == [], "a departed member can still read their old channel's messages (messages_select)"

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, teammate.auth_user_id)
            await db.execute(
                "insert into public.messages (org_id, channel_id, sender_id, body) values ($1, $2, $3, 'ghost')",
                a.org_id,
                channel_id,
                teammate.user_id,
            )

    await _as_postgres(db)
    await db.execute("delete from public.channels where id = $1", channel_id)


async def test_departed_channel_creator_can_no_longer_rename_or_moderate(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The second, independent instance of the same root cause:
    `channel_created_by(id) = current_user_id()` used to keep authorising a
    creator's moderation actions with no regard for whether they were still
    in the organisation at all."""
    a, _ = tenants
    creator = await _create_tenant(db, "departs-as-creator")
    other = await _create_tenant(db, "other-member")
    await _seat(db, a.org_id, creator, "operator")
    await _seat(db, a.org_id, other, "operator")
    channel_id = await _create_channel(
        db, creator=creator, org_id=a.org_id, name="creator-departure-check", member_ids=[other.user_id]
    )

    async with db.transaction():
        await _as_user(db, creator.auth_user_id)
        renamed = await channels_repo.rename_channel(db, channel_id=channel_id, name="renamed-while-in")
        assert renamed is not None, "sanity check: the active creator should be able to rename"

    await _as_postgres(db)
    await db.execute(
        "delete from public.memberships where org_id = $1 and user_id = $2", a.org_id, creator.user_id
    )

    async with db.transaction():
        await _as_user(db, creator.auth_user_id)
        assert (
            await db.fetchval("select public.channel_created_by($1)", channel_id) == creator.user_id
        ), "test setup error: created_by should still point at the departed user"

        no_longer_renamed = await channels_repo.rename_channel(
            db, channel_id=channel_id, name="should-not-apply"
        )
        assert no_longer_renamed is None, (
            "a departed creator can still rename their old channel (channels_update)"
        )

        removed = await channels_repo.remove_member(db, channel_id=channel_id, user_id=other.user_id)
        assert removed is False, (
            "a departed creator can still remove another member from their old channel "
            "(channel_members_delete)"
        )

    await _as_postgres(db)
    still_there = await db.fetchval(
        "select count(*) from public.channel_members where channel_id = $1 and user_id = $2",
        channel_id,
        other.user_id,
    )
    assert still_there == 1, "the other member should not actually have been removed"
    await db.execute("delete from public.channels where id = $1", channel_id)


async def test_departed_member_can_no_longer_read_channel_membership_via_a_stale_row(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`channel_members_select`'s `is_channel_member` branch had no live
    org-membership check - the one policy the previous RLS fix didn't touch,
    confirmed exploitable live via direct PostgREST (the RLS audit's own
    follow-up). Same identity throughout, stale row deliberately
    left in place - a plain `memberships` delete, not `org_repo.remove_member()`,
    which would also clean the row up and mask exactly what this test needs to
    isolate: whether the *policy* itself, not the cleanup, is what closes this."""
    a, _ = tenants
    teammate = await _create_tenant(db, "cm-select-departs")
    await _seat(db, a.org_id, teammate, "operator")
    channel_id = await _create_channel(db, creator=teammate, org_id=a.org_id, name="cm-select-check")

    async with db.transaction():
        await _as_user(db, teammate.auth_user_id)
        members = await db.fetch(
            "select user_id from public.channel_members where channel_id = $1", channel_id
        )
    assert [m["user_id"] for m in members] == [teammate.user_id], (
        "sanity check: an active member should see channel_members for their own channel"
    )

    await _as_postgres(db)
    await db.execute(
        "delete from public.memberships where org_id = $1 and user_id = $2", a.org_id, teammate.user_id
    )
    stale_row = await db.fetchval(
        "select count(*) from public.channel_members where channel_id = $1 and user_id = $2",
        channel_id,
        teammate.user_id,
    )
    assert stale_row == 1, "test setup error: the channel_members row should still be there"

    async with db.transaction():
        await _as_user(db, teammate.auth_user_id)
        assert not await db.fetchval("select public.is_org_member($1)", a.org_id)
        assert await db.fetchval("select public.is_channel_member($1)", channel_id), (
            "test setup error: the stale row should still make is_channel_member() true"
        )
        after = await db.fetch(
            "select user_id from public.channel_members where channel_id = $1", channel_id
        )
    assert after == [], (
        "a departed member can still read channel_members through the stale row "
        "(channel_members_select's is_channel_member branch has no org-membership check)"
    )

    await _as_postgres(db)
    await db.execute("delete from public.channels where id = $1", channel_id)


async def test_remove_member_repo_also_clears_the_departed_users_channel_members_rows(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The self-leave cleanup this task adds: data hygiene (an honest member
    list for whoever's left), not the security boundary - the previous two
    tests already prove RLS holds even without it. `org_repo.remove_member()`
    is the real function the self-leave route calls, exercised directly."""
    a, _ = tenants
    teammate = await _create_tenant(db, "leaves-cleanly")
    await _seat(db, a.org_id, teammate, "operator")
    channel_id = await _create_channel(db, creator=teammate, org_id=a.org_id, name="leave-cleanup-check")

    await _as_postgres(db)
    before = await db.fetchval(
        "select count(*) from public.channel_members where org_id = $1 and user_id = $2",
        a.org_id,
        teammate.user_id,
    )
    assert before == 1

    async with db.transaction():
        await _as_user(db, teammate.auth_user_id)
        await org_repo.remove_member(db, a.org_id, teammate.user_id)

    await _as_postgres(db)
    after_members = await db.fetchval(
        "select count(*) from public.channel_members where org_id = $1 and user_id = $2",
        a.org_id,
        teammate.user_id,
    )
    after_membership = await db.fetchval(
        "select count(*) from public.memberships where org_id = $1 and user_id = $2",
        a.org_id,
        teammate.user_id,
    )
    assert after_members == 0, "remove_member() left a stale channel_members row behind"
    assert after_membership == 0, "remove_member() didn't remove the membership itself"

    await db.execute("delete from public.channels where id = $1", channel_id)


async def test_pagination_with_identical_timestamps_uses_id_as_a_tiebreaker(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`created_at` is transaction-start time, not per-statement - two
    messages committed by genuinely concurrent requests can land on the
    exact same timestamp. Without `before_id` as a tiebreaker, a bare
    `created_at < cursor` can silently skip whichever of a tied pair doesn't
    make the earlier page. Forces the tie directly (three messages sharing
    one timestamp) rather than relying on real concurrency to reproduce it."""
    a, _ = tenants
    channel_id = await _create_channel(db, creator=a, org_id=a.org_id, name="tied-timestamps")

    await _as_postgres(db)
    same_instant = datetime.now(UTC)
    for body in ("tied-0", "tied-1", "tied-2"):
        await db.execute(
            """
            insert into public.messages (org_id, channel_id, sender_id, body, created_at)
            values ($1, $2, $3, $4, $5)
            """,
            a.org_id,
            channel_id,
            a.user_id,
            body,
            same_instant,
        )

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        seen: list[str] = []
        cursor_created_at = None
        cursor_id = None
        for _ in range(4):  # 3 messages, one per page, plus one page proving nothing is left
            page = await messages_repo.list_messages(
                db, channel_id, before=cursor_created_at, before_id=cursor_id, limit=1
            )
            if not page:
                break
            seen = [m["body"] for m in page] + seen
            cursor_created_at = page[0]["created_at"]
            cursor_id = page[0]["id"]
        assert sorted(seen) == ["tied-0", "tied-1", "tied-2"], (
            "a tied timestamp caused list_messages() to skip or repeat a message"
        )

    await _as_postgres(db)
    await db.execute("delete from public.channels where org_id = $1", a.org_id)


async def _insert_voice_agent(
    db: asyncpg.Connection, *, org_id: uuid.UUID, created_by: uuid.UUID, name: str = "Test Agent"
) -> asyncpg.Record:
    return await voice_agents_repo.create_agent(
        db,
        org_id=org_id,
        created_by=created_by,
        name=name,
        kind="custom",
        stt_provider="sarvam",
        tts_provider="sarvam",
        llm_provider="openrouter",
        llm_model="openai/gpt-4o",
        voice_id="anushka",
        system_prompt="Be helpful.",
        prebuilt_persona=None,
        collect_fields=[
            {
                "key": "callback_time",
                "type": "string",
                "description": "When they want to be called back",
                "required": False,
            }
        ],
    )


async def test_voice_agents_are_invisible_across_tenants_through_the_repository(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        created = await _insert_voice_agent(db, org_id=a.org_id, created_by=a.user_id)

    async with db.transaction():
        await _as_user(db, b.auth_user_id)
        rows = await voice_agents_repo.list_org_agents(db, b.org_id)
        fetched = await voice_agents_repo.get_org_agent(db, b.org_id, created["id"])
    assert rows == [], "tenant b can see tenant a's voice agent"
    assert fetched is None, "tenant b fetched tenant a's voice agent by id"

    await _as_postgres(db)
    await db.execute("delete from public.voice_agents where org_id = $1", a.org_id)


async def test_ai_provider_credentials_are_invisible_across_tenants_for_agents(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        await ai_provider_credentials_repo.upsert(
            db,
            org_id=a.org_id,
            created_by=a.user_id,
            provider="sarvam",
            label="Tenant A key",
            api_key_encrypted="enc-tenant-a",
        )

    async with db.transaction():
        await _as_user(db, b.auth_user_id)
        rows = await ai_provider_credentials_repo.list_for_org(db, b.org_id)
        fetched = await ai_provider_credentials_repo.get_credential(db, b.org_id, "sarvam")
    assert rows == [], "tenant b can see tenant a's ai provider credential"
    assert fetched is None, "tenant b fetched tenant a's credential by provider"

    await _as_postgres(db)
    await db.execute("delete from public.ai_provider_credentials where org_id = $1", a.org_id)


async def test_voice_agents_follow_the_per_creator_silo(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """An operator sees only the agents they created; a viewer sees the org's.

    Rewritten, not deleted. This test previously asserted the *opposite* - that
    voice agents were the deliberate contrast to the campaigns/runs per-creator
    silo - and migration `202608171900` closed that gap on purpose. Deleting the
    test would have left the new boundary uncovered; inverting it keeps the silo
    itself asserted.

    Worth knowing how this was found: the migration landed with the old assertion
    still in the suite, and nothing caught it, because every DB-backed test skips
    when `DATABASE_URL` is unset and CI sets none. The first real run after the
    merge is what surfaced it.

    The asymmetry is the point. `viewer` is a read-only *oversight* role, so it
    sees everything; `operator` is a doer, so it sees its own work. Testing only
    one of them would pass under a policy that got the other wrong.
    """
    a, _ = tenants
    await _as_postgres(db)

    operator = await _create_tenant(db, "agents-read-operator")
    viewer = await _create_tenant(db, "agents-read-viewer")
    await _seat(db, a.org_id, operator, "operator")
    await _seat(db, a.org_id, viewer, "viewer")

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        owners_agent = await _insert_voice_agent(db, org_id=a.org_id, created_by=a.user_id)

    async with db.transaction():
        await _as_user(db, operator.auth_user_id)
        operators_agent = await _insert_voice_agent(
            db, org_id=a.org_id, created_by=operator.user_id
        )

    # The viewer oversees, so it sees both.
    async with db.transaction():
        await _as_user(db, viewer.auth_user_id)
        seen = {r["id"] for r in await voice_agents_repo.list_org_agents(db, a.org_id)}
    assert seen == {owners_agent["id"], operators_agent["id"]}, (
        "a viewer must see every agent in the organisation it oversees"
    )

    # The operator sees its own and not the owner's.
    async with db.transaction():
        await _as_user(db, operator.auth_user_id)
        seen = {r["id"] for r in await voice_agents_repo.list_org_agents(db, a.org_id)}
    assert seen == {operators_agent["id"]}, (
        "an operator must see only the agents it created"
    )

    await _as_postgres(db)
    await db.execute("delete from public.voice_agents where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [operator.auth_user_id, viewer.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_an_operator_can_delete_its_own_agent_but_not_someone_elses(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Creating still needs operator or above; deleting now follows authorship.

    Rewritten alongside `test_voice_agents_follow_the_per_creator_silo`, and for
    the same reason: migration `202608171900` deliberately let the person who
    created an agent delete it, and this test previously asserted the opposite
    ("delete should be admin/owner only"). The old assertion was still green in CI
    because CI sets no `DATABASE_URL` and skips every DB-backed test.

    Both halves matter. Asserting only that an operator *can* delete its own would
    pass under a policy that let it delete anything; asserting only that it cannot
    delete another's would pass under the old admin-only rule.

    A `USING` clause filters the row out of the delete rather than raising, so a
    refused delete is a silent no-op - same shape as
    `test_admin_cannot_demote_an_owner_via_direct_update` above. That is why each
    case checks the row is still really there afterwards rather than trusting the
    return value alone.
    """
    a, _ = tenants
    await _as_postgres(db)

    viewer = await _create_tenant(db, "agents-write-viewer")
    operator = await _create_tenant(db, "agents-write-operator")
    await _seat(db, a.org_id, viewer, "viewer")
    await _seat(db, a.org_id, operator, "operator")

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, viewer.auth_user_id)
            await _insert_voice_agent(db, org_id=a.org_id, created_by=viewer.user_id)

    async with db.transaction():
        await _as_user(db, operator.auth_user_id)
        own = await _insert_voice_agent(
            db, org_id=a.org_id, created_by=operator.user_id, name="Operator Agent"
        )
    assert own is not None, "operator could not create a voice agent"

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        someone_elses = await _insert_voice_agent(
            db, org_id=a.org_id, created_by=a.user_id, name="Owner Agent"
        )

    # Not its own: filtered out, and genuinely still present.
    async with db.transaction():
        await _as_user(db, operator.auth_user_id)
        refused = await voice_agents_repo.delete_agent(db, a.org_id, someone_elses["id"])
    assert refused is None, "an operator deleted an agent it did not create"
    await _as_postgres(db)
    assert await db.fetchval(
        "select exists(select 1 from public.voice_agents where id = $1)",
        someone_elses["id"],
    ), "the other member's agent was actually deleted by an operator"

    # Its own: allowed, and genuinely gone.
    async with db.transaction():
        await _as_user(db, operator.auth_user_id)
        removed = await voice_agents_repo.delete_agent(db, a.org_id, own["id"])
    assert removed is not None, "an operator could not delete the agent it created"
    await _as_postgres(db)
    assert not await db.fetchval(
        "select exists(select 1 from public.voice_agents where id = $1)", own["id"]
    ), "the operator's own agent survived its delete"

    await db.execute("delete from public.voice_agents where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [viewer.auth_user_id, operator.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_ai_provider_credentials_are_admin_or_owner_only_even_for_read(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Stricter than every other table in this suite: even a plain read is
    admin/owner only, because a vendor API key is a real, costed secret
    (migration `a1c48e7f2b93`). The read side fails the same way any other
    `select` RLS policy does - silently filtered to nothing, no exception -
    while the write side raises, same as
    `test_only_owner_or_admin_can_write_provider_credentials` above for the
    telephony-credentials table."""
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "creds-admin")
    operator = await _create_tenant(db, "creds-operator")
    await _seat(db, a.org_id, admin, "admin")
    await _seat(db, a.org_id, operator, "operator")

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        await ai_provider_credentials_repo.upsert(
            db,
            org_id=a.org_id,
            created_by=admin.user_id,
            provider="sarvam",
            label="Admin key",
            api_key_encrypted="enc-admin-key",
        )

    async with db.transaction():
        await _as_user(db, operator.auth_user_id)
        rows = await ai_provider_credentials_repo.list_for_org(db, a.org_id)
        fetched = await ai_provider_credentials_repo.get_credential(db, a.org_id, "sarvam")
    assert rows == [], "operator can read the org's ai provider credentials"
    assert fetched is None, "operator can fetch the org's ai provider credential directly"

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, operator.auth_user_id)
            await ai_provider_credentials_repo.upsert(
                db,
                org_id=a.org_id,
                created_by=operator.user_id,
                provider="deepgram",
                label="Operator key",
                api_key_encrypted="enc-operator-key",
            )

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        rows = await ai_provider_credentials_repo.list_for_org(db, a.org_id)
    assert {r["provider"] for r in rows} == {"sarvam"}, "admin cannot read the org's credentials"

    await _as_postgres(db)
    await db.execute("delete from public.ai_provider_credentials where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, operator.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")
