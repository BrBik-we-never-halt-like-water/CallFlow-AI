"""SQL for org-owned voice agent configurations. Unlike campaigns, read access
is org-wide, not per-creator (migration `a1c48e7f2b93`) - but the UI still
wants to show who built an agent, so `list_org_agents`/`get_org_agent` join to
`public.users` for `created_by_name`/`created_by_avatar_url` the same way
`campaigns.py` does."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

_LIST_COLUMNS = """
    v.id, v.org_id, v.created_by, v.name, v.kind, v.stt_provider, v.tts_provider,
    v.llm_provider, v.llm_model, v.voice_id, v.system_prompt, v.prebuilt_persona,
    v.telephony_provider, v.collect_fields, v.created_at, v.updated_at,
    u.name as created_by_name, u.avatar_url as created_by_avatar_url
"""

_WRITE_RETURNING = """
    id, org_id, name, kind, stt_provider, tts_provider, llm_provider, llm_model,
    voice_id, system_prompt, prebuilt_persona, telephony_provider,
    collect_fields, created_at, updated_at, created_by
"""


async def list_org_agents(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        f"""
        select {_LIST_COLUMNS}
        from public.voice_agents v
        left join public.users u on u.id = v.created_by
        where v.org_id = $1
        order by v.created_at desc
        """,
        org_id,
    )


async def count_for_org(conn: asyncpg.Connection, org_id: UUID) -> int:
    """How many agents this organisation has, for the plan gate.

    Accurate under RLS because `voice_agents_select` is org-wide
    (`is_org_member`), not per-creator - an operator counting does not undercount
    a teammate's agents. The `before insert` trigger counts again as `postgres`,
    which is what makes the limit hold against raw SQL; this count only exists so
    the API can refuse with a readable reason first.
    """
    return await conn.fetchval(
        "select count(*) from public.voice_agents where org_id = $1", org_id
    )


async def get_org_agent(
    conn: asyncpg.Connection, org_id: UUID, agent_id: UUID
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"""
        select {_LIST_COLUMNS}
        from public.voice_agents v
        left join public.users u on u.id = v.created_by
        where v.org_id = $1 and v.id = $2
        """,
        org_id,
        agent_id,
    )


async def create_agent(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    created_by: UUID,
    name: str,
    kind: str,
    stt_provider: str | None,
    tts_provider: str | None,
    llm_provider: str | None,
    llm_model: str | None,
    voice_id: str | None,
    system_prompt: str | None,
    prebuilt_persona: str | None,
    telephony_provider: str | None,
    collect_fields: list[dict[str, Any]],
) -> asyncpg.Record:
    return await conn.fetchrow(
        f"""
        insert into public.voice_agents
            (org_id, created_by, name, kind, stt_provider, tts_provider,
             llm_provider, llm_model, voice_id, system_prompt, prebuilt_persona,
             telephony_provider, collect_fields)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        returning {_WRITE_RETURNING}
        """,
        org_id,
        created_by,
        name,
        kind,
        stt_provider,
        tts_provider,
        llm_provider,
        llm_model,
        voice_id,
        system_prompt,
        prebuilt_persona,
        telephony_provider,
        collect_fields,
    )


async def update_agent(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    agent_id: UUID,
    name: str,
    kind: str,
    stt_provider: str | None,
    tts_provider: str | None,
    llm_provider: str | None,
    llm_model: str | None,
    voice_id: str | None,
    system_prompt: str | None,
    prebuilt_persona: str | None,
    telephony_provider: str | None,
    collect_fields: list[dict[str, Any]],
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"""
        update public.voice_agents
        set name = $3, kind = $4, stt_provider = $5, tts_provider = $6,
            llm_provider = $7, llm_model = $8, voice_id = $9, system_prompt = $10,
            prebuilt_persona = $11, telephony_provider = $12,
            collect_fields = $13, updated_at = now()
        where org_id = $1 and id = $2
        returning {_WRITE_RETURNING}
        """,
        org_id,
        agent_id,
        name,
        kind,
        stt_provider,
        tts_provider,
        llm_provider,
        llm_model,
        voice_id,
        system_prompt,
        prebuilt_persona,
        telephony_provider,
        collect_fields,
    )


async def delete_agent(conn: asyncpg.Connection, org_id: UUID, agent_id: UUID) -> str | None:
    return await conn.fetchval(
        "delete from public.voice_agents where org_id = $1 and id = $2 returning id::text",
        org_id,
        agent_id,
    )
