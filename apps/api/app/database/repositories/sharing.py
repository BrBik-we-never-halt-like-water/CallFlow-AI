"""SQL for peer-to-peer escalation sharing - the role-based UI
roadmap's Phase 4. `resolve_resource_owner`/`list_*_directory` are
`SECURITY DEFINER` Postgres functions (migration `4cbc5103657f`), not
regular queries - they deliberately bypass the requester's own RLS scope,
which by design hides exactly the resource they're trying to request."""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def resolve_resource_owner(
    conn: asyncpg.Connection, *, org_id: UUID, resource_type: str, resource_id: str
) -> UUID | None:
    return await conn.fetchval(
        "select public.resolve_resource_owner($1, $2, $3)",
        org_id,
        resource_type,
        resource_id,
    )


async def list_escalation_directory(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch("select * from public.list_escalation_directory($1)", org_id)


async def create_request(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    resource_type: str,
    resource_id: str,
    requested_by: UUID,
    owner_user_id: UUID,
    message: str | None,
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        insert into public.share_requests
            (org_id, resource_type, resource_id, requested_by, owner_user_id, message)
        values ($1, $2, $3, $4, $5, $6)
        returning id, org_id, resource_type, resource_id, requested_by, owner_user_id,
                  status, message, created_at, decided_at
        """,
        org_id,
        resource_type,
        resource_id,
        requested_by,
        owner_user_id,
        message,
    )


async def list_for_org(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    """Every request RLS lets this connection see - the caller's own sent
    requests, plus any directed at them to decide (or, for admin/owner,
    every request in the org).

    `resource_name` is a best-effort label (the escalation's contact name) via a
    plain join - not the `SECURITY DEFINER` directory functions. That's
    deliberate: this connection's own RLS already lets the resource's *owner* see
    it directly, so the join resolves for them; for the *requester*'s own sent
    rows it resolves to null (the exact resource they don't have access to yet),
    which the frontend falls back to showing the raw id for.

    The `campaign` arm is gone with campaigns (ADR-8). `case` is kept rather than
    reduced to `co.contact_name` because `resource_type` is still a column with a
    check constraint, and a second shareable resource type should have to add its
    own arm here rather than silently render an escalation's name.
    """
    return await conn.fetch(
        """
        select sr.id, sr.org_id, sr.resource_type, sr.resource_id, sr.message,
               sr.status, sr.created_at, sr.decided_at,
               sr.requested_by, req.name as requested_by_name,
               sr.owner_user_id, own.name as owner_name,
               case sr.resource_type
                 when 'escalation' then co.contact_name
               end as resource_name
        from public.share_requests sr
        left join public.users req on req.id = sr.requested_by
        left join public.users own on own.id = sr.owner_user_id
        left join public.escalations e
          on sr.resource_type = 'escalation' and e.org_id = sr.org_id
          and e.id = (case when sr.resource_type = 'escalation' then sr.resource_id::uuid end)
        left join public.call_outcomes co on co.id = e.call_outcome_id
        where sr.org_id = $1
        order by sr.created_at desc
        """,
        org_id,
    )


async def get_for_org(
    conn: asyncpg.Connection, org_id: UUID, request_id: UUID
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        select id, org_id, resource_type, resource_id, requested_by, owner_user_id, status
        from public.share_requests
        where org_id = $1 and id = $2
        """,
        org_id,
        request_id,
    )


async def decide(
    conn: asyncpg.Connection, *, org_id: UUID, request_id: UUID, approve: bool
) -> asyncpg.Record | None:
    """Marks the request decided. RLS (`share_requests_update`, owner-only)
    is what actually stops anyone but the resource's owner from calling this
    at all - `status = 'pending'` in the WHERE guards against deciding twice."""
    return await conn.fetchrow(
        """
        update public.share_requests
           set status = $3, decided_at = now()
         where org_id = $1 and id = $2 and status = 'pending'
        returning id, resource_type, resource_id, requested_by, owner_user_id
        """,
        org_id,
        request_id,
        "approved" if approve else "rejected",
    )
