"""SQL for org-owned AI vendor credentials (Sarvam, Deepgram, ElevenLabs, OpenAI,
OpenRouter) used by voice agents. RLS restricts every query to owner/admin.

Encryption happens in the route layer (`app/core/crypto.py`), not here - this
module only ever sees ciphertext, so a bug here can leak a row, not a secret.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def list_for_org(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select provider, label, created_at, updated_at
        from public.ai_provider_credentials
        where org_id = $1
        order by provider
        """,
        org_id,
    )


async def get_credential(
    conn: asyncpg.Connection, org_id: UUID, provider: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        select provider, label, api_key_encrypted, created_at, updated_at
        from public.ai_provider_credentials
        where org_id = $1 and provider = $2
        """,
        org_id,
        provider,
    )


async def upsert(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    created_by: UUID,
    provider: str,
    label: str | None,
    api_key_encrypted: str,
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        insert into public.ai_provider_credentials
            (org_id, created_by, provider, label, api_key_encrypted)
        values ($1, $2, $3, $4, $5)
        on conflict (org_id, provider) do update set
            label = excluded.label,
            api_key_encrypted = excluded.api_key_encrypted,
            updated_at = now()
        returning provider, label, created_at, updated_at
        """,
        org_id,
        created_by,
        provider,
        label,
        api_key_encrypted,
    )


async def remove(conn: asyncpg.Connection, org_id: UUID, provider: str) -> str | None:
    return await conn.fetchval(
        "delete from public.ai_provider_credentials where org_id = $1 and provider = $2 returning provider",
        org_id,
        provider,
    )
