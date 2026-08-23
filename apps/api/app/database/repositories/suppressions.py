"""SQL for the do-not-call list. See ISSUES.md #3 - this is what makes the
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


async def add_opt_out(
    conn: asyncpg.Connection, *, org_id: UUID, phone_hash: str, reason: str
) -> bool:
    """Suppress a number the contact themselves asked to be removed from.

    Returns whether this call created the row - False means they were already
    suppressed, which is the common case on a second call to someone who opted
    out on the first.

    **Takes a hash, never a number, and that is the point.** The completion
    callback that calls this only ever receives a *masked* number, and a masked
    number cannot be hashed. The hash comes from `call_outcomes.phone_hash`,
    written by the dialler at origination, so the do-not-call can be enforced
    without any surface between the carrier and this row holding a dialable
    number (`f3c7b21a9d04`).

    `phone_e164` is left null, unlike `add_suppression`'s manual path. The
    suppression list's own display tolerates that - it is masked there anyway -
    and writing a number this code path does not have would mean inventing one.

    `source = 'opt_out'` rather than `'manual'`: the enum has carried that value
    since the initial schema for exactly this, and it is what lets the
    suppression list tell "somebody typed this in" apart from "the person on the
    call asked". Owner-only removal (`SUPPRESSIONS_REMOVE`) applies to both.
    """
    row = await conn.fetchrow(
        """
        insert into public.suppressions
            (org_id, phone_hash, source, reason, suppressed_by)
        values ($1, $2, 'opt_out', $3, null)
        on conflict (org_id, phone_hash) do nothing
        returning id
        """,
        org_id,
        phone_hash,
        reason,
    )
    return row is not None
