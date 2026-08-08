"""Cross-tenant isolation, asserted against the real database.

`CLAUDE.md` calls a policy that looks right and permits a cross-tenant read the most
expensive bug this product can ship, so these tests talk to Postgres directly rather
than mocking anything. They exercise the same role switch the API uses, which is the
only configuration where RLS is actually in force — `postgres` holds BYPASSRLS, so a
plain connection proves nothing.

Skipped when DIRECT_URL is unset, so the suite still runs offline.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
import pytest_asyncio

from app.core.config import config
from app.database.repositories import organisations as org_repo
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
        json.dumps({"full_name": f"RLS {label}"}),
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


async def _as_user(conn: asyncpg.Connection, auth_user_id: uuid.UUID) -> None:
    """Switch the connection to the identity the API would use for this request."""
    claims = json.dumps({"sub": str(auth_user_id), "role": "authenticated"})
    await conn.execute("select set_config('request.jwt.claims', $1, true)", claims)
    await conn.execute("select set_config('role', 'authenticated', true)")


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
    async with db.transaction():
        await db.execute("select set_config('role', 'anon', true)")
        for table in ("organisations", "users", "memberships", "suppressions"):
            count = await db.fetchval(f"select count(*) from public.{table}")
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
    Removing that membership must break the key immediately — nothing about the
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
# escalation attempt before it reaches the database — see
# `tests/test_organisations_routes.py` for that half. These tests are the RLS half:
# CLAUDE.md's stated model is an API check *and* an RLS check, neither alone, so a
# direct write that skipped the API layer entirely must still be refused
# (migration `c2f7a9d15e63`, `public.can_grant_role`/`public.current_org_role`).


async def test_admin_cannot_promote_an_operator_to_owner_via_direct_update(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The genuine promotion attempt: target is a non-owner member, so this
    exercises `memberships_update`'s `WITH CHECK` (the granted-role guard) —
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
    """The insert-side twin of the update test above — same rank check, `memberships_insert`."""
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
# `can_grant_role` alone only checks the role being *granted* — an Admin could
# still demote or remove an existing Owner in a multi-owner org, since neither
# `memberships_update` nor `memberships_delete` looked at the row's *current*
# role at all. `public.can_act_on_member()` closes that: added to both
# policies' `USING` clause (which is exactly where Postgres evaluates a row's
# pre-write state), it fails silently — the write matches zero rows, same
# pattern as `test_cannot_update_another_tenants_organisation` — rather than
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
    assert role == "owner", "Admin demoted an Owner — the target-role guard did not hold"

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
    assert still_there, "Admin removed an Owner — the target-role guard did not hold"

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
# (to accept it) but never restricted *which* column — an invitee legitimately
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
# a matching pending invitation — never that the `user_id` being inserted into
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
# whether a conflict occurs at runtime — so a first-time invite failed
# identically to a re-invite. `test_admin_can_still_invite_as_operator_or_viewer`
# (`test_organisations_routes.py`) mocks `create_invitation` entirely and so
# never exercised the real SQL — exactly the coverage gap that let this
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
            invited_by=a.user_id,
        )

    assert row is not None
    assert row["role"] == "operator"
    assert row["email"] == "brand-new-invitee@example.com"
    assert row["accepted_at"] is None

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
            invited_by=a.user_id,
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
            invited_by=a.user_id,
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
    itself (it bypasses RLS, so it must enforce `can_grant_role` internally) —
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
                invited_by=admin.user_id,
            )

    await _as_postgres(db)
    seated = await db.fetchval(
        "select exists(select 1 from public.invitations where token = $1)", token
    )
    assert not seated, "an Admin created a pending owner-role invitation"

    await db.execute("delete from auth.users where id = $1", admin.auth_user_id)
    await db.execute("delete from public.organisations where deleted_at is not null")
