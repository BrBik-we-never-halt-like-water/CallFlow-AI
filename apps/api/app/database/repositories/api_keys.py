"""SQL for org-scoped API keys. RLS restricts every query below to owner/admin."""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def list_for_org(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select id, name, key_prefix, last_used_at, created_at
        from public.api_keys
        where org_id = $1
        order by created_at desc
        """,
        org_id,
    )


async def create(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    created_by: UUID,
    name: str,
    key_prefix: str,
    key_hash: str,
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        insert into public.api_keys (org_id, created_by, name, key_prefix, key_hash)
        values ($1, $2, $3, $4, $5)
        returning id, name, key_prefix, last_used_at, created_at
        """,
        org_id,
        created_by,
        name,
        key_prefix,
        key_hash,
    )


async def revoke(conn: asyncpg.Connection, org_id: UUID, key_id: UUID) -> str | None:
    return await conn.fetchval(
        "delete from public.api_keys where id = $1 and org_id = $2 returning id",
        key_id,
        org_id,
    )
