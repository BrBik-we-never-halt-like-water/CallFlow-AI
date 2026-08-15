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
from app.database.repositories import campaigns as campaigns_repo
from app.database.repositories import credits as credits_repo
from app.database.repositories import escalations as escalations_repo
from app.database.repositories import invitations as invitations_repo
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
# Role-based UI roadmap, Phase 1: `campaigns_select`/`runs_select`/
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


async def _insert_campaign(
    db: asyncpg.Connection, *, org_id: uuid.UUID, created_by: uuid.UUID
) -> str:
    campaign_id = f"silo-campaign-{uuid.uuid4().hex[:8]}"
    await db.execute(
        """
        insert into public.campaigns (id, org_id, name, goal_template, created_by)
        values ($1, $2, 'silo test campaign', $3, $4)
        """,
        campaign_id,
        org_id,
        "x" * 40,
        created_by,
    )
    return campaign_id


async def _insert_run(
    db: asyncpg.Connection, *, org_id: uuid.UUID, started_by: uuid.UUID
) -> str:
    run_id = f"silo-run-{uuid.uuid4().hex[:8]}"
    await db.execute(
        """
        insert into public.runs (id, org_id, campaign_id, total, started_by)
        values ($1, $2, 'travel_discovery', 1, $3)
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


async def test_operator_cannot_see_a_teammates_campaign(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "silo-op1")
    op2 = await _create_tenant(db, "silo-op2")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")
    await _insert_campaign(db, org_id=a.org_id, created_by=op1.user_id)

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        rows = await db.fetch(
            "select created_by from public.campaigns where org_id = $1", a.org_id
        )
    assert rows == [], "operator can see a teammate's campaign"

    async with db.transaction():
        await _as_user(db, op1.auth_user_id)
        rows = await db.fetch(
            "select created_by from public.campaigns where org_id = $1", a.org_id
        )
    assert [r["created_by"] for r in rows] == [op1.user_id]

    await _as_postgres(db)
    await db.execute("delete from public.campaigns where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


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


async def test_admin_and_viewer_see_every_operators_campaigns_and_runs(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "silo-admin")
    viewer = await _create_tenant(db, "silo-viewer")
    op1 = await _create_tenant(db, "silo-seen-op1")
    op2 = await _create_tenant(db, "silo-seen-op2")
    await _seat(db, a.org_id, admin, "admin")
    await _seat(db, a.org_id, viewer, "viewer")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")

    await _insert_campaign(db, org_id=a.org_id, created_by=op1.user_id)
    await _insert_campaign(db, org_id=a.org_id, created_by=op2.user_id)
    run1 = await _insert_run(db, org_id=a.org_id, started_by=op1.user_id)
    run2 = await _insert_run(db, org_id=a.org_id, started_by=op2.user_id)
    await _insert_call_outcome(db, org_id=a.org_id, run_id=run1)
    await _insert_call_outcome(db, org_id=a.org_id, run_id=run2)

    for viewer_tenant in (admin, viewer):
        async with db.transaction():
            await _as_user(db, viewer_tenant.auth_user_id)
            campaigns = await db.fetch(
                "select created_by from public.campaigns where org_id = $1", a.org_id
            )
            runs = await db.fetch(
                "select started_by from public.runs where org_id = $1", a.org_id
            )
            outcomes = await db.fetch(
                "select id from public.call_outcomes where org_id = $1", a.org_id
            )
        assert {r["created_by"] for r in campaigns} == {op1.user_id, op2.user_id}
        assert {r["started_by"] for r in runs} == {op1.user_id, op2.user_id}
        assert len(outcomes) == 2

    await _as_postgres(db)
    await db.execute("delete from public.campaigns where org_id = $1", a.org_id)
    await db.execute("delete from public.runs where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, viewer.auth_user_id, op1.auth_user_id, op2.auth_user_id],
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
    shared_campaign = await _insert_campaign(db, org_id=a.org_id, created_by=op1.user_id)

    # op1's own auto-created org from signup - unrelated to `a`, should be
    # untouched by the reassignment `a`'s removal triggers.
    own_org_id = await db.fetchval(
        "select org_id from public.memberships where user_id = $1 and role = 'owner'",
        op1.user_id,
    )
    own_campaign = await _insert_campaign(db, org_id=own_org_id, created_by=op1.user_id)

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        await db.execute(
            "select public.remove_member_and_reassign_data($1, $2)", a.org_id, op1.user_id
        )

    await _as_postgres(db)
    creator = await db.fetchval(
        "select created_by from public.campaigns where id = $1", shared_campaign
    )
    assert creator == a.user_id, "the removed teammate's campaign was not reassigned to the admin"

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

    own_campaign_creator = await db.fetchval(
        "select created_by from public.campaigns where id = $1", own_campaign
    )
    assert own_campaign_creator is None, "an unrelated org's data was touched by this removal"

    await db.execute(
        "delete from public.campaigns where id = any($1::text[])",
        [shared_campaign, own_campaign],
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
        await credits_repo.set_allocation(
            db, org_id=a.org_id, user_id=op1.user_id, daily_allocation=50, updated_by=admin.user_id
        )

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        rows = await credits_repo.list_allocations(db, a.org_id)
    assert rows == [], "operator can see a teammate's credit allocation"

    async with db.transaction():
        await _as_user(db, op1.auth_user_id)
        rows = await credits_repo.list_allocations(db, a.org_id)
    assert [r["daily_allocation"] for r in rows] == [50], "operator cannot see their own allocation"

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        rows = await credits_repo.list_allocations(db, a.org_id)
    assert len(rows) == 1, "admin cannot see the team's credit allocations"

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
            await credits_repo.set_allocation(
                db, org_id=a.org_id, user_id=op2.user_id, daily_allocation=99, updated_by=op1.user_id
            )

    await _as_postgres(db)
    await db.execute("delete from public.member_credit_allocations where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_used_today_counts_only_connected_calls_and_ceiling_distinguishes_unset_from_zero(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """`used_today()` now backs credit *enforcement*
    (`check_dial_allowed`'s `credits_remaining`, wired up in
    `CampaignRunner`), not just display - it must count a connected call
    (`status = 'COMPLETED'`), not merely an attempted one, or setting
    someone's daily allocation to N would start blocking them after N dial
    *attempts*, most of which never actually spent anything.
    `get_enforced_ceiling()` must also tell "no row at all" (no per-teammate
    limit - only the org-wide budget applies) apart from "a row with
    daily_allocation = 0" (deliberately blocked) - `get_allocation()`'s own
    0-default conflates the two for display, which is the right call for the
    UI but would be a real enforcement bug here.
    """
    a, _ = tenants
    await _as_postgres(db)

    admin = await _create_tenant(db, "credits-enforce-admin")
    op1 = await _create_tenant(db, "credits-enforce-op1")
    op2 = await _create_tenant(db, "credits-enforce-op2")
    await _seat(db, a.org_id, admin, "admin")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")

    run_id = await _insert_run(db, org_id=a.org_id, started_by=op1.user_id)
    await db.execute(
        """
        insert into public.call_outcomes (run_id, org_id, contact_name, phone_masked, status, disposition)
        values ($1, $2, 'Connected', '+1 555 0102', 'COMPLETED', 'auto_closed')
        """,
        run_id,
        a.org_id,
    )
    await db.execute(
        """
        insert into public.call_outcomes (run_id, org_id, contact_name, phone_masked, status, disposition)
        values ($1, $2, 'Never answered', '+1 555 0103', 'NO_ANSWER', 'unreachable')
        """,
        run_id,
        a.org_id,
    )

    async with db.transaction():
        await _as_user(db, op1.auth_user_id)
        used = await credits_repo.used_today(db, a.org_id, op1.user_id)
        no_row_ceiling = await credits_repo.get_enforced_ceiling(db, a.org_id, op1.user_id)
    assert used == 1, "used_today counted a call that never connected"
    assert no_row_ceiling is None, "a teammate with no allocation row was treated as having a ceiling"

    async with db.transaction():
        await _as_user(db, admin.auth_user_id)
        await credits_repo.set_allocation(
            db, org_id=a.org_id, user_id=op2.user_id, daily_allocation=0, updated_by=admin.user_id
        )

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        zero_ceiling = await credits_repo.get_enforced_ceiling(db, a.org_id, op2.user_id)
    assert zero_ceiling == 0, "an explicit zero allocation was indistinguishable from no allocation at all"

    await _as_postgres(db)
    await db.execute("delete from public.call_outcomes where run_id = $1", run_id)
    await db.execute("delete from public.runs where id = $1", run_id)
    await db.execute("delete from public.member_credit_allocations where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [admin.auth_user_id, op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- Peer-to-peer campaign/escalation sharing (role-based UI roadmap,
# Phase 4, migration 4cbc5103657f) ------------------------------------------


async def test_resolve_resource_owner_finds_the_real_campaign_creator_past_the_requesters_own_scope(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The whole point of `resolve_resource_owner()` - a plain SELECT under
    op2's own connection can't see op1's campaign at all (Phase 1's RLS), but
    the `SECURITY DEFINER` function still correctly resolves who owns it."""
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "share-owner-op1")
    op2 = await _create_tenant(db, "share-owner-op2")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")
    campaign_id = await _insert_campaign(db, org_id=a.org_id, created_by=op1.user_id)

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        plain_select = await db.fetch(
            "select id from public.campaigns where org_id = $1 and id = $2", a.org_id, campaign_id
        )
        owner = await sharing_repo.resolve_resource_owner(
            db, org_id=a.org_id, resource_type="campaign", resource_id=campaign_id
        )
    assert plain_select == [], "operator's plain query already sees a teammate's campaign"
    assert owner == op1.user_id

    await _as_postgres(db)
    await db.execute("delete from public.campaigns where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_resolve_resource_owner_returns_null_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """A caller who isn't even a member of the target org gets null, not the
    real owner - the internal `is_org_member()` guard every other
    `SECURITY DEFINER` function in this codebase already has."""
    a, b = tenants
    await _as_postgres(db)
    campaign_id = await _insert_campaign(db, org_id=a.org_id, created_by=b.user_id)

    async with db.transaction():
        await _as_user(db, b.auth_user_id)
        owner = await sharing_repo.resolve_resource_owner(
            db, org_id=a.org_id, resource_type="campaign", resource_id=campaign_id
        )
    assert owner is None, "a non-member resolved a real campaign's owner"

    await _as_postgres(db)
    await db.execute("delete from public.campaigns where org_id = $1", a.org_id)


async def test_campaign_directory_lists_names_org_wide_but_plain_select_stays_narrowed(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "share-dir-op1")
    op2 = await _create_tenant(db, "share-dir-op2")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")
    await _insert_campaign(db, org_id=a.org_id, created_by=op1.user_id)

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        directory = await sharing_repo.list_campaign_directory(db, a.org_id)
        plain_select = await db.fetch(
            "select id from public.campaigns where org_id = $1", a.org_id
        )
    assert plain_select == [], "operator's plain query already sees a teammate's campaign"
    assert {r["owner_user_id"] for r in directory} == {op1.user_id}

    await _as_postgres(db)
    await db.execute("delete from public.campaigns where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_directory_functions_return_nothing_across_tenants(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    a, b = tenants
    await _as_postgres(db)
    await _insert_campaign(db, org_id=a.org_id, created_by=b.user_id)

    async with db.transaction():
        await _as_user(db, b.auth_user_id)
        directory = await sharing_repo.list_campaign_directory(db, a.org_id)
    assert directory == [], "a non-member saw another tenant's campaign directory"

    await _as_postgres(db)
    await db.execute("delete from public.campaigns where org_id = $1", a.org_id)


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
    campaign_id = await _insert_campaign(db, org_id=a.org_id, created_by=op2.user_id)
    await _insert_share_request(
        db,
        org_id=a.org_id,
        resource_type="campaign",
        resource_id=campaign_id,
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
    await db.execute("delete from public.campaigns where org_id = $1", a.org_id)
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
    campaign_id = await _insert_campaign(db, org_id=a.org_id, created_by=op2.user_id)
    request_id = await _insert_share_request(
        db,
        org_id=a.org_id,
        resource_type="campaign",
        resource_id=campaign_id,
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
    await db.execute("delete from public.campaigns where org_id = $1", a.org_id)
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
    "decide" it, the actual grant - reading the real campaign to clone it -
    still runs under their own `campaigns_select` scope, which a non-creator
    operator fails. Application code (`sharing.py`'s `_decide`) checks this
    read before marking anything decided; this test pins the repository-
    level fact that makes that check meaningful, not just presumed."""
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "share-forge-creator")
    op3 = await _create_tenant(db, "share-forge-attacker")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op3, "operator")
    campaign_id = await _insert_campaign(db, org_id=a.org_id, created_by=op1.user_id)

    async with db.transaction():
        await _as_user(db, op3.auth_user_id)
        forged = await sharing_repo.get_for_org(
            db,
            a.org_id,
            await _insert_share_request(
                db,
                org_id=a.org_id,
                resource_type="campaign",
                resource_id=campaign_id,
                requested_by=op3.user_id,
                owner_user_id=op3.user_id,
            ),
        )
        # RLS lets this "decide" through - op3 really is `owner_user_id` on
        # this (forged) row.
        assert forged is not None
        # But the read the real grant depends on is still scoped to op3's
        # own campaigns - the actual campaign was never theirs to clone.
        original = await campaigns_repo.get_org_campaign(db, a.org_id, campaign_id)
    assert original is None, "a forged owner_user_id could read the real campaign to clone it"

    await _as_postgres(db)
    await db.execute("delete from public.share_requests where org_id = $1", a.org_id)
    await db.execute("delete from public.campaigns where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op3.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_operator_can_clone_a_teammates_campaign_via_share_approval(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """Regression test: a plain `INSERT ... RETURNING` here used to fail
    with `InsufficientPrivilegeError` for exactly this - the most common -
    case, caught only by manually walking the approve flow end to end, not
    by any earlier automated test. `campaigns_insert`'s `WITH CHECK` is
    role-only and lets an operator insert; but `campaigns_select` for an
    operator is `created_by = self`, and `RETURNING` requires the inserted
    row to pass that too - which it never can here, since the clone's
    `created_by` is the *requester*, not the operator running the insert.
    `clone_for_share()` (backed by the `SECURITY DEFINER` function
    `clone_campaign_for_share()`) is the fix; this pins that it actually
    works for the ordinary operator-approves-operator case, not just for
    admin/owner.
    """
    a, _ = tenants
    await _as_postgres(db)

    op1 = await _create_tenant(db, "share-clone-owner")
    op2 = await _create_tenant(db, "share-clone-requester")
    await _seat(db, a.org_id, op1, "operator")
    await _seat(db, a.org_id, op2, "operator")
    campaign_id = await _insert_campaign(db, org_id=a.org_id, created_by=op1.user_id)

    async with db.transaction():
        await _as_user(db, op1.auth_user_id)
        await campaigns_repo.clone_for_share(
            db,
            org_id=a.org_id,
            source_campaign_id=campaign_id,
            new_campaign_id=f"{campaign_id}-clone",
            new_owner=op2.user_id,
        )

    async with db.transaction():
        await _as_user(db, op2.auth_user_id)
        cloned = await campaigns_repo.get_org_campaign(db, a.org_id, f"{campaign_id}-clone")
    assert cloned is not None, "the clone did not land, or the new owner cannot see it"
    assert cloned["created_by"] == op2.user_id
    assert cloned["id"] != campaign_id, "the clone reused the original's id instead of a new one"

    await _as_postgres(db)
    await db.execute("delete from public.campaigns where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op2.auth_user_id],
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
    campaign_id = await _insert_campaign(db, org_id=a.org_id, created_by=op2.user_id)

    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with db.transaction():
            await _as_user(db, op1.auth_user_id)
            await _insert_share_request(
                db,
                org_id=a.org_id,
                resource_type="campaign",
                resource_id=campaign_id,
                requested_by=op2.user_id,
                owner_user_id=op2.user_id,
            )

    await _as_postgres(db)
    await db.execute("delete from public.campaigns where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [op1.auth_user_id, op2.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


# --- Agentic tab: voice agents + AI provider credentials (migration
# `a1c48e7f2b93`) -------------------------------------------------------------
#
# `voice_agents` is deliberately org-wide readable (`voice_agents_select` is
# plain `is_org_member`, not per-creator like `campaigns`) because an agent
# configuration is org infrastructure any teammate needs to see to run or
# share a campaign against it. Write is operator+ (day-to-day, same tier as
# campaigns); delete is admin/owner only. `ai_provider_credentials` is a real
# costed vendor secret, so every operation - including plain read - is
# admin/owner only, a stricter shape than any other table these tests cover.


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
        telephony_provider="twilio",
    )


async def test_voice_agents_are_invisible_across_tenants(
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


async def test_voice_agents_are_org_wide_readable_not_per_creator(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
    """The deliberate contrast with campaigns/runs (per-creator visibility
    silo, migration `202608092000`): any org member, including a viewer,
    must see an agent created by someone else entirely. A regression here -
    accidentally narrowing this to per-creator - would be a silent behavior
    change nothing else in this suite would catch."""
    a, _ = tenants
    await _as_postgres(db)

    operator = await _create_tenant(db, "agents-read-operator")
    viewer = await _create_tenant(db, "agents-read-viewer")
    await _seat(db, a.org_id, operator, "operator")
    await _seat(db, a.org_id, viewer, "viewer")

    async with db.transaction():
        await _as_user(db, a.auth_user_id)
        created = await _insert_voice_agent(db, org_id=a.org_id, created_by=a.user_id)

    for member in (operator, viewer):
        async with db.transaction():
            await _as_user(db, member.auth_user_id)
            rows = await voice_agents_repo.list_org_agents(db, a.org_id)
        assert [r["id"] for r in rows] == [created["id"]], (
            f"member {member.user_id} cannot see an agent created by another org member"
        )

    await _as_postgres(db)
    await db.execute("delete from public.voice_agents where org_id = $1", a.org_id)
    await db.execute(
        "delete from auth.users where id = any($1::uuid[])",
        [operator.auth_user_id, viewer.auth_user_id],
    )
    await db.execute("delete from public.organisations where deleted_at is not null")


async def test_only_operator_or_above_can_create_voice_agents_and_only_admin_or_above_can_delete(
    db: asyncpg.Connection, tenants: tuple[Tenant, Tenant]
) -> None:
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
        created = await _insert_voice_agent(
            db, org_id=a.org_id, created_by=operator.user_id, name="Operator Agent"
        )
    assert created is not None, "operator could not create a voice agent"

    # RLS's `voice_agents_delete` policy is a `USING` clause (admin/owner
    # only) - same shape as `test_admin_cannot_demote_an_owner_via_direct_update`
    # above: it filters the row out of the delete rather than raising, so an
    # operator's delete is silently a no-op, not a rejection.
    async with db.transaction():
        await _as_user(db, operator.auth_user_id)
        deleted = await voice_agents_repo.delete_agent(db, a.org_id, created["id"])
    assert deleted is None, "operator deleted a voice agent - delete should be admin/owner only"

    await _as_postgres(db)
    still_there = await db.fetchval(
        "select exists(select 1 from public.voice_agents where id = $1)", created["id"]
    )
    assert still_there, "the voice agent was actually deleted by an operator"

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
