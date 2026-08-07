"""SQL for the do-not-call list. See ISSUES.md #3 — this is what makes the
product's "never dialled again" promise real instead of UI-only."""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def is_suppressed(conn: asyncpg.Connection, org_id: UUID, phone_hash: str) -> bool:
    return await conn.fetchval(
        "select exists(select 1 from public.suppressions where org_id = $1 and phone_hash = $2)",
        org_id,
        phone_hash,
    )


async def list_suppressions(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select id, phone_e164, source, reason, suppressed_by, suppressed_at
        from public.suppressions
        where org_id = $1
        order by suppressed_at desc
        """,
        org_id,
    )


async def add_suppression(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    phone_hash: str,
    phone_e164: str,
    reason: str | None,
    suppressed_by: UUID,
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        insert into public.suppressions (org_id, phone_hash, phone_e164, source, reason, suppressed_by)
        values ($1, $2, $3, 'manual', $4, $5)
        on conflict (org_id, phone_hash) do update set reason = excluded.reason
        returning id, phone_e164, source, reason, suppressed_by, suppressed_at
        """,
        org_id,
        phone_hash,
        phone_e164,
        reason,
        suppressed_by,
    )


async def remove_suppression(conn: asyncpg.Connection, org_id: UUID, suppression_id: UUID) -> str | None:
    return await conn.fetchval(
        "delete from public.suppressions where id = $1 and org_id = $2 returning id",
        suppression_id,
        org_id,
    )
