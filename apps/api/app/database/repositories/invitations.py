"""SQL for resolving and accepting an invitation by its token."""

from __future__ import annotations

import asyncpg


class SeatLimitReached(Exception):
    """The organisation has no seat free for this invitation.

    Distinct from `accept()` returning `None`, which means the token itself is no
    good. This one says the token is fine and the plan is not, so the route can
    answer 402 with an upgrade path instead of 400 "this invitation isn't valid" -
    which would send someone to ask for a fresh invite that will fail identically.

    Carries the trigger's own message because it names the plan's actual numbers.
    """

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


async def lookup_public(conn: asyncpg.Connection, token: str) -> asyncpg.Record:
    """Unauthenticated preview, via the SECURITY DEFINER `lookup_invitation` function.

    Runs on a `database.anonymous()` connection - there is no user yet, so this is
    the one place a plain table SELECT would not work even with the right grants.
    """
    return await conn.fetchrow(
        "select org_name, role, email, valid, reason, account_exists "
        "from public.lookup_invitation($1)",
        token,
    )


async def accept(conn: asyncpg.Connection, token: str) -> asyncpg.Record | None:
    """Insert the caller's own membership and mark the invitation accepted.

    The lookup goes through `public.lookup_invitation_for_accept()` (migration
    `202608092400`) rather than a plain `select ... join organisations` under
    this connection's own RLS-scoped role: `organisations_select` is plain
    `is_org_member(id)`, and a brand-new invitee - someone accepting their
    very first invitation, with no memberships yet - fails that check by
    definition, so the join silently dropped the row and no one could ever
    actually accept a first invitation. The `SECURITY DEFINER` function
    bypasses that one read; the membership INSERT below still goes through
    the ordinary RLS-scoped connection, so `memberships_insert`'s
    `has_valid_invitation()` check still applies as an independent guard on
    the operation that actually grants access.

    Returns `None` when the token doesn't exist, is already used or expired, or
    addressed to a different email - the last surfaces as an RLS violation on
    the INSERT (`memberships_insert`'s invitation branch failing its
    `WITH CHECK`) rather than a silently-filtered row, so that's caught here and
    folded into the same "couldn't accept" outcome the route reports. Same
    outcome for a concurrent accept of the same invitation racing this one - the
    loser's INSERT hits the `memberships` primary key instead of the RLS check,
    but it's still just "couldn't accept", not an error.

    The INSERT runs inside a nested transaction (asyncpg issues a `SAVEPOINT`,
    same reasoning as `organisations_repo.set_member_role()`): once Postgres
    aborts a transaction, every statement other than `ROLLBACK` raises
    `InFailedSqlTransactionError` until one runs - including the `UPDATE`
    below and `database.as_user()`'s own cleanup on the way out. Catching the
    error alone, without a savepoint to roll back to, would turn this
    function's clean `None` into an unhandled 500 instead.
    """
    invitation = await conn.fetchrow(
        "select * from public.lookup_invitation_for_accept($1)", token
    )
    if invitation is None or invitation["accepted_at"] is not None or invitation["expired"]:
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
            async with conn.transaction():
                await conn.execute(
                    """
                    insert into public.memberships (org_id, user_id, role, invited_by)
                    values ($1, public.current_user_id(), $2, $3)
                    """,
                    invitation["org_id"],
                    invitation["role"],
                    invitation["invited_by"],
                )
        except asyncpg.exceptions.CheckViolationError as exc:
            # `enforce_seat_limit` (migration `202608181000`). A downgrade landed
            # between the invitation and this click, so the seat the invitation was
            # counted against no longer exists.
            raise SeatLimitReached(_seat_limit_detail(exc)) from exc
        except (asyncpg.exceptions.InsufficientPrivilegeError, asyncpg.exceptions.UniqueViolationError):
            return None

    await conn.execute(
        "update public.invitations set accepted_at = now() where id = $1", invitation["id"]
    )

    return invitation


def _seat_limit_detail(exc: asyncpg.exceptions.CheckViolationError) -> str:
    """The trigger's sentence, or a plain one if Postgres sent none.

    Never the raw exception: `str(exc)` on an asyncpg error can carry the statement
    that failed, and a route must not hand that to a browser.
    """
    message = getattr(exc, "message", None)
    return message or "This organisation has no free seats on its current plan."
