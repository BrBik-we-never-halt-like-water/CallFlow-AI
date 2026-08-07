"""SQL for organisations, membership, and pending invitations.

Every query here runs on a connection already scoped by `database.as_user()` —
row-level security decides what is actually visible or writable. This module is
where that SQL lives so the route handlers stay thin.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg


async def list_mine(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select o.id, o.name, o.slug, o.logo_url, m.role
        from public.organisations o
        join public.memberships m on m.org_id = o.id
        where m.user_id = public.current_user_id()
        order by m.joined_at
        """
    )


async def create(conn: asyncpg.Connection, name: str) -> asyncpg.Record:
    slug = await conn.fetchval("select public.unique_org_slug($1)", name)
    row = await conn.fetchrow(
        """
        insert into public.organisations (name, slug, country, timezone, onboarded_at)
        values ($1, $2, 'IN', 'Asia/Kolkata', now())
        returning id, name, slug, logo_url
        """,
        name,
        slug,
    )
    await conn.execute(
        """
        insert into public.memberships (org_id, user_id, role)
        values ($1, public.current_user_id(), 'owner')
        """,
        row["id"],
    )
    return row


async def update_active(
    conn: asyncpg.Connection, org_id: UUID, *, name: str | None, logo_url: str | None
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        update public.organisations
           set name = coalesce($2, name),
               logo_url = coalesce($3, logo_url)
         where id = $1
        returning id, name, slug, logo_url
        """,
        org_id,
        name,
        logo_url,
    )


async def complete_onboarding(conn: asyncpg.Connection, org_id: UUID, name: str) -> asyncpg.Record:
    """Confirm the org's name and mark onboarding done, in one update.

    `coalesce(onboarded_at, now())` makes this safe to call twice — a retry after a
    dropped response doesn't reset the timestamp, it just leaves it as it was.
    """
    return await conn.fetchrow(
        """
        update public.organisations
           set name = $2,
               onboarded_at = coalesce(onboarded_at, now())
         where id = $1
        returning id, name, slug, logo_url, onboarded_at
        """,
        org_id,
        name,
    )


async def count_orgs_for_current_user(conn: asyncpg.Connection) -> int:
    return await conn.fetchval(
        "select count(*) from public.memberships where user_id = public.current_user_id()"
    )


async def delete_active(conn: asyncpg.Connection, org_id: UUID) -> None:
    await conn.execute(
        "update public.organisations set deleted_at = now() where id = $1", org_id
    )


async def list_members(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select u.id as user_id, u.name, u.email, u.avatar_url, m.role, m.joined_at
        from public.memberships m
        join public.users u on u.id = m.user_id
        where m.org_id = $1
        order by m.joined_at
        """,
        org_id,
    )


async def list_pending_invitations(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select id, email, role, invited_by, expires_at, created_at
        from public.invitations
        where org_id = $1 and accepted_at is null
        order by created_at desc
        """,
        org_id,
    )


async def set_member_role(
    conn: asyncpg.Connection, org_id: UUID, user_id: UUID, role: str
) -> None:
    # A nested transaction (asyncpg issues a SAVEPOINT here, since `as_user()` already
    # has one open) so that if `protect_last_owner` raises, only this statement rolls
    # back — the connection stays usable for the route's own error response and for
    # `as_user()`'s cleanup, instead of the whole transaction going into "aborted".
    async with conn.transaction():
        await conn.execute(
            "update public.memberships set role = $3 where org_id = $1 and user_id = $2",
            org_id,
            user_id,
            role,
        )


async def remove_member(conn: asyncpg.Connection, org_id: UUID, user_id: UUID) -> None:
    async with conn.transaction():
        await conn.execute(
            "delete from public.memberships where org_id = $1 and user_id = $2", org_id, user_id
        )


async def create_invitation(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    email: str,
    role: str,
    token: str,
    expires_at: Any,
    invited_by: UUID,
) -> asyncpg.Record:
    """Create a pending invite, or refresh it if one is already outstanding.

    The partial unique index on `(org_id, lower(email)) where accepted_at is null`
    is the conflict target — re-inviting the same address just extends the same
    invitation with a fresh token rather than erroring.
    """
    return await conn.fetchrow(
        """
        insert into public.invitations (org_id, email, role, token, invited_by, expires_at)
        values ($1, $2, $3, $4, $5, $6)
        on conflict (org_id, (lower(email))) where accepted_at is null
        do update set role = excluded.role,
                      token = excluded.token,
                      invited_by = excluded.invited_by,
                      expires_at = excluded.expires_at,
                      created_at = now()
        returning id, org_id, email, role, expires_at, created_at
        """,
        org_id,
        email,
        role,
        token,
        invited_by,
        expires_at,
    )


async def revoke_invitation(conn: asyncpg.Connection, org_id: UUID, invitation_id: UUID) -> str | None:
    return await conn.fetchval(
        "delete from public.invitations where id = $1 and org_id = $2 returning id",
        invitation_id,
        org_id,
    )
