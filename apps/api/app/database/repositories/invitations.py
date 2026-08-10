"""SQL for resolving and accepting an invitation by its token."""

from __future__ import annotations

import asyncpg


async def lookup_public(conn: asyncpg.Connection, token: str) -> asyncpg.Record:
    """Unauthenticated preview, via the SECURITY DEFINER `lookup_invitation` function.

    Runs on a `database.anonymous()` connection - there is no user yet, so this is
    the one place a plain table SELECT would not work even with the right grants.
    """
    return await conn.fetchrow(
        "select org_name, role, email, valid, reason from public.lookup_invitation($1)",
        token,
    )


async def accept(conn: asyncpg.Connection, token: str) -> asyncpg.Record | None:
    """Insert the caller's own membership and mark the invitation accepted.

    Returns `None` when the token doesn't exist, is already used, or the invitation
    is expired / addressed to a different email - the last two surface as an RLS
    violation on the INSERT (`memberships_insert`'s invitation branch failing its
    `WITH CHECK`) rather than a silently-filtered row, so that's caught here and
    folded into the same "couldn't accept" outcome the route reports.
    """
    invitation = await conn.fetchrow(
        """
        select i.id, i.org_id, i.role, i.invited_by, i.accepted_at, i.expires_at,
               o.name as org_name, o.slug as org_slug
        from public.invitations i
        join public.organisations o on o.id = i.org_id
        where i.token = $1
        """,
        token,
    )
    if invitation is None or invitation["accepted_at"] is not None:
        return None

    already_member = await conn.fetchval(
        """
        select exists(
          select 1 from public.memberships
          where org_id = $1 and user_id = public.current_user_id()
        )
        """,
        invitation["org_id"],
    )
    if not already_member:
        try:
            await conn.execute(
                """
                insert into public.memberships (org_id, user_id, role, invited_by)
                values ($1, public.current_user_id(), $2, $3)
                """,
                invitation["org_id"],
                invitation["role"],
                invitation["invited_by"],
            )
        except (asyncpg.exceptions.InsufficientPrivilegeError, asyncpg.exceptions.UniqueViolationError):
            return None

    await conn.execute(
        "update public.invitations set accepted_at = now() where id = $1", invitation["id"]
    )

    return invitation
