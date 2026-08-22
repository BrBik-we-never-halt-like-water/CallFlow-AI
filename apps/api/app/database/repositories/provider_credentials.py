"""SQL for an org's own third-party credentials. RLS restricts every query to owner/admin.

Encryption happens in the route layer (`app/core/crypto.py`), not here - this
module only ever sees ciphertext, so a bug here can leak a row, not a secret.

Reads carry `identifier_encrypted`/`secret_encrypted` alongside
`fields_encrypted` purely so the caller can upgrade a row written before
`c8e1f4a29b76`. New writes only ever set `fields_encrypted`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg


async def list_for_org(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    """Every connected provider, without any ciphertext.

    Deliberately selects no encrypted column: this feeds a settings page that
    has no business holding a secret it will not use.
    """
    return await conn.fetch(
        """
        select provider, label, phone_number, verified_at, created_at, updated_at
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
    fields_encrypted: str,
    phone_number: str | None,
    verified_at: datetime | None,
) -> asyncpg.Record:
    """Store one provider's credentials, replacing whatever was there.

    `verified_at` is written from the caller's check result rather than
    preserved, and that is the point: credentials replacing verified ones are
    unverified until *they* are checked. Carrying the old timestamp forward
    would let a working key vouch for the typo that replaced it.

    The two superseded columns are nulled on write, not left alone: a row that
    kept stale `secret_encrypted` ciphertext beside a fresh `fields_encrypted`
    would give the read fallback something plausible and wrong to return if the
    precedence were ever changed. One row, one live copy of the secret.
    """
    return await conn.fetchrow(
        """
        insert into public.provider_credentials
            (org_id, created_by, provider, label, fields_encrypted, phone_number,
             verified_at)
        values ($1, $2, $3, $4, $5, $6, $7)
        on conflict (org_id, provider) do update set
            label = excluded.label,
            fields_encrypted = excluded.fields_encrypted,
            identifier_encrypted = null,
            secret_encrypted = null,
            phone_number = excluded.phone_number,
            verified_at = excluded.verified_at,
            updated_at = now()
        returning provider, label, phone_number, verified_at, created_at, updated_at
        """,
        org_id,
        created_by,
        provider,
        label,
        fields_encrypted,
        phone_number,
        verified_at,
    )


async def mark_verified(
    conn: asyncpg.Connection, org_id: UUID, provider: str, *, at: datetime | None
) -> asyncpg.Record | None:
    """Record what re-checking an already-stored credential found.

    `updated_at` is deliberately left alone: nothing about the credential
    changed, only what we know about it. Moving it would make a read-only
    check look like an edit everywhere that shows when a provider was last
    touched.
    """
    return await conn.fetchrow(
        """
        update public.provider_credentials
        set verified_at = $3
        where org_id = $1 and provider = $2
        returning provider, label, phone_number, verified_at, created_at, updated_at
        """,
        org_id,
        provider,
        at,
    )


async def get_for_provider(
    conn: asyncpg.Connection, org_id: UUID, provider: str
) -> asyncpg.Record | None:
    """One provider's row, *including* the ciphertext.

    Separate from `list_for_org` on purpose - see its docstring. This one exists
    for the call paths that genuinely have to authenticate with the vendor, and
    the caller decrypts (`app/core/crypto.py`); this module still only ever sees
    ciphertext.
    """
    return await conn.fetchrow(
        """
        select provider, label, fields_encrypted, identifier_encrypted, secret_encrypted,
               phone_number
        from public.provider_credentials
        where org_id = $1 and provider = $2
        """,
        org_id,
        provider,
    )


async def remove(conn: asyncpg.Connection, org_id: UUID, provider: str) -> str | None:
    return await conn.fetchval(
        "delete from public.provider_credentials where org_id = $1 and provider = $2 returning provider",
        org_id,
        provider,
    )
