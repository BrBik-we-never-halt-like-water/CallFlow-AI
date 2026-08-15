"""SQL for chat messages. RLS (`messages_select`/`messages_insert`/
`messages_update`) does the actual per-channel-membership and per-sender
narrowing; every query here just runs on the caller's RLS-scoped connection."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg

# A default page is generous enough that most channels never paginate at all;
# the cap exists so a caller can't ask for the whole history in one round trip.
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


async def list_messages(
    conn: asyncpg.Connection,
    channel_id: UUID,
    *,
    before: datetime | None = None,
    before_id: UUID | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> list[asyncpg.Record]:
    """Cursor pagination on `messages_channel_created_idx` (`channel_id,
    created_at`): `before` is the `created_at` of the oldest message already
    loaded, so the next page is everything strictly older than that. Fetched
    newest-first (so `LIMIT` takes the *right* page, not the oldest messages
    in the whole channel) then reversed before returning, so the response is
    always oldest-first regardless of whether `before` was supplied - matching
    how the message view scrolls, unchanged from before pagination existed.
    Soft-deleted rows are excluded here too, not just client-side - belt and
    braces against a lagging Realtime event re-displaying one.

    `before_id` breaks a tie on `created_at` itself - two messages can share
    the exact same timestamp (`now()` is transaction-start time, and two
    concurrent sends can start in the same instant), and a bare `created_at <
    $before` would silently skip whichever of a tied pair doesn't come back
    on the earlier page. Optional and additive: a caller that doesn't send it
    keeps the old (theoretically gappy, practically never-observed) behaviour
    rather than being forced to upgrade in lockstep."""
    limit = min(max(limit, 1), MAX_PAGE_SIZE)
    rows = await conn.fetch(
        """
        select m.id, m.channel_id, m.sender_id, u.name as sender_name,
               m.body, m.created_at, m.edited_at
        from public.messages m
        left join public.users u on u.id = m.sender_id
        where m.channel_id = $1 and m.deleted_at is null
          and (
            $2::timestamptz is null
            or m.created_at < $2
            or (m.created_at = $2 and $4::uuid is not null and m.id < $4)
          )
        order by m.created_at desc, m.id desc
        limit $3
        """,
        channel_id,
        before,
        limit,
        before_id,
    )
    return list(reversed(rows))


async def send_message(
    conn: asyncpg.Connection, *, org_id: UUID, channel_id: UUID, sender_id: UUID, body: str
) -> asyncpg.Record | None:
    """Plain insert with `RETURNING` - safe here, unlike channel creation:
    `messages_insert`'s check (`sender_id = current_user_id() and
    is_channel_member(channel_id)`) is already satisfiable at insert time, since
    the sender is by definition already a channel member. No chicken-and-egg.

    `None` means the caller isn't a member of `channel_id` - surfaced as an RLS
    violation on the INSERT (`messages_insert`'s `WITH CHECK` failing) rather
    than a silently-filtered row. Caught inside a nested transaction (asyncpg
    issues a SAVEPOINT, same as `organisations_repo.set_member_role()`): once
    Postgres aborts a transaction, every statement other than ROLLBACK raises
    `InFailedSqlTransactionError` until one runs, including `as_user()`'s own
    cleanup on the way out - so catching the error alone, without a savepoint
    to roll back to, would turn a clean 403 into an unhandled 500.
    """
    try:
        async with conn.transaction():
            return await conn.fetchrow(
                """
                insert into public.messages (org_id, channel_id, sender_id, body)
                values ($1, $2, $3, $4)
                returning id, channel_id, sender_id, body, created_at, edited_at
                """,
                org_id,
                channel_id,
                sender_id,
                body,
            )
    except asyncpg.exceptions.InsufficientPrivilegeError:
        return None


async def edit_message(
    conn: asyncpg.Connection, *, message_id: UUID, sender_id: UUID, body: str
) -> asyncpg.Record | None:
    """`None` means either the message doesn't exist or `messages_update`
    rejected it - `sender_id` in the `WHERE` is belt and braces for a clearer
    "no rows" result; `messages_update`'s `USING (sender_id = current_user_id())`
    is the actual guard, so a forged `sender_id` here changes nothing."""
    return await conn.fetchrow(
        """
        update public.messages set body = $3, edited_at = now()
        where id = $1 and sender_id = $2 and deleted_at is null
        returning id, channel_id, sender_id, body, created_at, edited_at
        """,
        message_id,
        sender_id,
        body,
    )


async def delete_message(conn: asyncpg.Connection, *, message_id: UUID, sender_id: UUID) -> bool:
    """Soft delete - sets `deleted_at`, never a real `DELETE`. Same RLS shape
    as `edit_message`: `messages_update`'s policy is the real guard."""
    result = await conn.execute(
        "update public.messages set deleted_at = now() "
        "where id = $1 and sender_id = $2 and deleted_at is null",
        message_id,
        sender_id,
    )
    return result != "UPDATE 0"
