"""SQL for org-owned Twilio/Plivo credentials. RLS restricts every query to owner/admin.

Encryption happens in the route layer (`app/core/crypto.py`), not here — this
module only ever sees ciphertext, so a bug here can leak a row, not a secret.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def list_for_org(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select provider, label, phone_number, created_at, updated_at
        from public.provider_credentials
        where org_id = $1
        order by provider
        """,
        org_id,
    )


async def upsert(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    created_by: UUID,
    provider: str,
    label: str | None,
    identifier_encrypted: str,
    secret_encrypted: str,
    phone_number: str | None,
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        insert into public.provider_credentials
            (org_id, created_by, provider, label, identifier_encrypted, secret_encrypted, phone_number)
        values ($1, $2, $3, $4, $5, $6, $7)
        on conflict (org_id, provider) do update set
            label = excluded.label,
            identifier_encrypted = excluded.identifier_encrypted,
            secret_encrypted = excluded.secret_encrypted,
            phone_number = excluded.phone_number,
            updated_at = now()
        returning provider, label, phone_number, created_at, updated_at
        """,
        org_id,
        created_by,
        provider,
        label,
        identifier_encrypted,
        secret_encrypted,
        phone_number,
    )


async def remove(conn: asyncpg.Connection, org_id: UUID, provider: str) -> str | None:
    return await conn.fetchval(
        "delete from public.provider_credentials where org_id = $1 and provider = $2 returning provider",
        org_id,
        provider,
    )
