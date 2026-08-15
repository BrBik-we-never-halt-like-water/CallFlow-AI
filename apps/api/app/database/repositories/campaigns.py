"""SQL for org-owned campaigns. Built-in campaigns are Python constants
(app/domain/campaigns.py) and never live here - see the migration docstring
for why."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

# Role-based UI roadmap, Phase 1: `created_by` was write-only until now - RLS
# (`campaigns_select`, migration 202608092000) already narrows *which* rows an
# operator's plain org-member query returns; this join is what lets an
# admin/owner/viewer (who see every row) tell whose campaign each one is.
_LIST_COLUMNS = """
    c.id, c.name, c.goal_template, c.outcome_fields, c.result_schema, c.region, c.language,
    c.escalate_on_negative, c.created_at, c.created_by,
    u.name as created_by_name, u.avatar_url as created_by_avatar_url
"""


async def list_org_campaigns(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        f"""
        select {_LIST_COLUMNS}
        from public.campaigns c
        left join public.users u on u.id = c.created_by
        where c.org_id = $1
        order by c.created_at desc
        """,
        org_id,
    )


async def get_org_campaign(
    conn: asyncpg.Connection, org_id: UUID, campaign_id: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"""
        select {_LIST_COLUMNS}
        from public.campaigns c
        left join public.users u on u.id = c.created_by
        where c.org_id = $1 and c.id = $2
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
                  escalate_on_negative, created_at, created_by
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
                  escalate_on_negative, created_at, created_by
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


async def clone_for_share(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    source_campaign_id: str,
    new_campaign_id: str,
    new_owner: UUID,
) -> None:
    """Approving a campaign share request (`sharing.py`) - goes through the
    `SECURITY DEFINER` function `clone_campaign_for_share()` (migration
    `b938fa82e54d`), not a plain `INSERT ... RETURNING`. A plain insert
    fails under RLS whenever the approver isn't owner/admin/viewer: the
    insert policy is role-only and would allow it, but `RETURNING` also
    requires the *select* policy to pass, and an operator's select policy
    is `created_by = self` - never true here, since the clone's owner is
    the *requester*, not the approver running this.
    """
    await conn.execute(
        "select public.clone_campaign_for_share($1, $2, $3, $4)",
        org_id,
        source_campaign_id,
        new_campaign_id,
        new_owner,
    )
