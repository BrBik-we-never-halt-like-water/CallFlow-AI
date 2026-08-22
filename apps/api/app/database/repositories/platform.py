"""SQL for the platform-admin surface.

Every function here goes through a `SECURITY DEFINER` function rather than a plain
statement against the table, and not for convenience: `platform_admins` and
`platform_audit_log` have no policies and no grant to `authenticated`, so a direct
select from an RLS-scoped connection returns nothing and a direct insert fails. The
definer functions are the only path, and each re-checks the caller's capability
itself - which is what makes the boundary hold against someone calling them over
raw SQL, where no route dependency exists (`docs/PLATFORM_ADMIN.md` §5).

Reads use the ordinary `as_user` connection. `as_platform_reader` is for the
cross-tenant *data* surface - a customer's runs and calls - not for this metadata,
which the definer functions already scope.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import asyncpg


async def list_organisations(
    conn: asyncpg.Connection, *, search: str | None = None
) -> list[asyncpg.Record]:
    return await conn.fetch("select * from public.platform_list_organisations($1)", search)


async def get_override(conn: asyncpg.Connection, org_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow("select * from public.platform_get_override($1)", org_id)


async def set_plan(
    conn: asyncpg.Connection, *, org_id: UUID, plan_id: str, reason: str
) -> None:
    await conn.execute(
        "select public.platform_set_org_plan($1, $2, $3)", org_id, plan_id, reason
    )


async def set_entitlements(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    max_voice_agents: int | None,
    max_seats: int | None,
    max_organisations: int | None,
    max_ai_integrations: int | None,
    daily_call_budget: int | None,
    llm_spend_limit_usd: Decimal | None,
    unlimited: list[str],
    note: str | None,
    reason: str,
) -> None:
    """Write or clear the override, in one call.

    Passing every limit as null with an empty `unlimited` deletes the row, because
    an override of nothing is not an override - see the function's own comment.
    """
    await conn.execute(
        """
        select public.platform_set_org_entitlements(
          $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
        )
        """,
        org_id,
        max_voice_agents,
        max_seats,
        max_organisations,
        max_ai_integrations,
        daily_call_budget,
        llm_spend_limit_usd,
        unlimited,
        note,
        reason,
    )


async def read_audit(conn: asyncpg.Connection, *, limit: int = 100) -> list[asyncpg.Record]:
    return await conn.fetch("select * from public.platform_read_audit($1)", limit)


async def get_override_for_org(
    conn: asyncpg.Connection, org_id: UUID
) -> asyncpg.Record | None:
    """The organisation's own agreed limits, read as an ordinary member.

    Unlike everything above, this is not a platform read: `org_entitlement_overrides`
    grants `select` to `authenticated` and its policy is
    `is_org_member(org_id) or platform_can_read(org_id)`, so a customer can see the
    terms they negotiated. `billing.resolve_plan` calls this on every plan
    resolution, which is why it is a plain select rather than a definer function -
    the ordinary path must not pay for a capability check nobody in it will pass.
    """
    return await conn.fetchrow(
        "select * from public.org_entitlement_overrides where org_id = $1", org_id
    )


async def recent_runs(
    conn: asyncpg.Connection, org_id: UUID, *, limit: int = 50
) -> list[asyncpg.Record]:
    """One organisation's recent runs, read through an elevated session.

    A plain select, deliberately - not a definer function. This is the surface
    `platform_can_read` exists for: RLS evaluates every row, and the predicate on
    `runs_select` is what makes another tenant's rows visible at all. Routing it
    through a definer function instead would bypass the policy and lose the one
    guarantee that makes this not a bypass.

    The connection must come from `database.as_platform_reader`, which is read-only
    and sets the elevation flag. Called on an ordinary `as_user` connection this
    returns nothing at all rather than failing loudly - the fast path in
    `platform_can_read` sees no flag and the policy filters every row.
    """
    return await conn.fetch(
        """
        select r.id, r.status, r.created_at, r.finished_at,
               c.name as campaign_name,
               (select count(*) from public.call_outcomes o where o.run_id = r.id) as calls
          from public.runs r
          left join public.campaigns c on c.id = r.campaign_id
         where r.org_id = $1
         order by r.created_at desc
         limit $2
        """,
        org_id,
        limit,
    )
