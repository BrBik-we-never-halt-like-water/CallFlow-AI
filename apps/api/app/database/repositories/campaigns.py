"""SQL for org-owned campaigns. Built-in campaigns are Python constants
(app/domain/campaigns.py) and never live here - see the migration docstring
for why."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg


async def list_org_campaigns(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select id, name, goal_template, outcome_fields, result_schema, region, language,
               escalate_on_negative, created_at
        from public.campaigns
        where org_id = $1
        order by created_at desc
        """,
        org_id,
    )


async def get_org_campaign(
    conn: asyncpg.Connection, org_id: UUID, campaign_id: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        select id, name, goal_template, outcome_fields, result_schema, region, language,
               escalate_on_negative, created_at
        from public.campaigns
        where org_id = $1 and id = $2
        """,
        org_id,
        campaign_id,
    )


async def create_campaign(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    created_by: UUID,
    campaign_id: str,
    name: str,
    goal_template: str,
    outcome_fields: dict[str, str],
    result_schema: dict[str, Any],
    region: str | None,
    language: str | None,
    escalate_on_negative: bool,
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        insert into public.campaigns
            (id, org_id, name, goal_template, outcome_fields, result_schema,
             region, language, escalate_on_negative, created_by)
        values ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9, $10)
        returning id, name, goal_template, outcome_fields, result_schema, region, language,
                  escalate_on_negative, created_at
        """,
        campaign_id,
        org_id,
        name,
        goal_template,
        outcome_fields,
        result_schema,
        region,
        language,
        escalate_on_negative,
        created_by,
    )


async def update_campaign(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    campaign_id: str,
    name: str,
    goal_template: str,
    outcome_fields: dict[str, str],
    result_schema: dict[str, Any],
    region: str | None,
    language: str | None,
    escalate_on_negative: bool,
) -> asyncpg.Record | None:
    """The id/slug never changes on update - only what a run reads."""
    return await conn.fetchrow(
        """
        update public.campaigns
        set name = $3, goal_template = $4, outcome_fields = $5::jsonb,
            result_schema = $6::jsonb, region = $7, language = $8,
            escalate_on_negative = $9
        where org_id = $1 and id = $2
        returning id, name, goal_template, outcome_fields, result_schema, region, language,
                  escalate_on_negative, created_at
        """,
        org_id,
        campaign_id,
        name,
        goal_template,
        outcome_fields,
        result_schema,
        region,
        language,
        escalate_on_negative,
    )


async def delete_campaign(conn: asyncpg.Connection, org_id: UUID, campaign_id: str) -> str | None:
    return await conn.fetchval(
        "delete from public.campaigns where org_id = $1 and id = $2 returning id",
        org_id,
        campaign_id,
    )
