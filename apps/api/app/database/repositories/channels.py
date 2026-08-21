"""SQL for chat channels and their membership.

Every query here runs on a connection already scoped by `database.as_user()` -
row-level security decides what is actually visible or writable.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def create_channel(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    kind: str,
    name: str | None,
    member_ids: list[UUID],
) -> UUID:
    """Create a channel and seat its members as one `SECURITY DEFINER` call.

    Doing this as two plain statements under the caller's RLS-scoped connection
    fails: `RETURNING` on the `channels` insert re-checks the new row against
    `channels_select` (`is_channel_member`), which is false until the membership
    row exists - and that row is the *next* statement. `create_channel()`
    (migration `b3f7d2a891c5`) is the same escape hatch `create_organisation()`
    already uses for this exact chicken-and-egg case.

    For a `dm`, the function is also idempotent: calling it twice for the same
    pair of people returns the same channel id rather than creating a duplicate.

    Raises `ValueError` - not a raw `asyncpg` error - for every rejection the
    function itself can raise: a member id from another organisation, a `dm`
    that isn't exactly one other person, or a `dm` aimed at the caller's own
    id. Before this, none of these were caught anywhere between the database
    and the HTTP response, so a bad request 500'd instead of getting a clean
    400 - the request still failed closed either way, but the route can only
    turn a `ValueError` into a proper 4xx.
    """
    try:
        return await conn.fetchval(
            "select public.create_channel($1, $2, $3, $4)",
            org_id,
            kind,
            name,
            member_ids,
        )
    except asyncpg.exceptions.RaiseError as exc:
        raise ValueError(str(exc)) from exc


# `unread_count` is a correlated scalar subquery, not a joined aggregate - it
# only needs `c.id`, already in the GROUP BY, so it doesn't force every other
# column into it too. Messages from the caller's own sends never count as
# unread; a channel the caller was just seated into starts at their
# `last_read_at` default (now(), set at insert time), not at the dawn of the
# channel's history.
_CHANNEL_COLUMNS = """
    c.id, c.kind, c.name, c.created_at, c.created_by,
    array_agg(m.user_id order by m.user_id) as member_ids,
    (
      select count(*) from public.messages msg
      where msg.channel_id = c.id
        and msg.deleted_at is null
        and msg.sender_id is distinct from public.current_user_id()
        and msg.created_at > coalesce(
          (select cm.last_read_at from public.channel_members cm
           where cm.channel_id = c.id and cm.user_id = public.current_user_id()),
          '-infinity'::timestamptz
        )
    ) as unread_count
"""


async def list_my_channels(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    """Relies on RLS (`channels_select`) to narrow to the caller's own channels -
    same reasoning as `runs_repo.summarize_by_member()` leaning entirely on RLS.

    Ordering is the caller's own: pinned first, then anything they have
    dragged into place, then the rest by recency. `me` is the caller's own
    membership row (joined separately from `m`, which is aggregated for
    `member_ids`) - that is where `pinned_at`/`sort_order` live, because both
    are one person's view and must not move the channel for anyone else.
    """
    return await conn.fetch(
        f"""
        select {_CHANNEL_COLUMNS},
               max(me.pinned_at) as pinned_at,
               max(me.sort_order) as sort_order
        from public.channels c
        join public.channel_members m on m.channel_id = c.id
        join public.channel_members me
          on me.channel_id = c.id and me.user_id = public.current_user_id()
        where c.org_id = $1
          and c.deleted_at is null
        group by c.id, c.kind, c.name, c.created_at, c.created_by
        order by
          max(me.pinned_at) desc nulls last,
          max(me.sort_order) asc nulls last,
          c.created_at desc
        """,
        org_id,
    )


async def total_unread_count(conn: asyncpg.Connection, org_id: UUID) -> int:
    """The nav badge's total - deliberately not `sum(unread_count)` over
    `list_my_channels()`. That query pays for an `array_agg` of every member
    of every channel the caller is in, which is fine once (rendering the chat
    list) but was being re-run, member arrays and all, on every single
    `channels`/`channel_members`/`messages` Realtime event for every
    signed-in tab in the organisation - the badge is mounted app-wide, not
    just on the chat page. This is one join with no per-row fan-out, using
    the same `messages_channel_created_idx` and `channel_members` primary key
    the rest of chat already relies on."""
    return await conn.fetchval(
        """
        select count(*)
        from public.messages msg
        join public.channel_members cm
          on cm.channel_id = msg.channel_id and cm.user_id = public.current_user_id()
        where cm.org_id = $1
          and msg.deleted_at is null
          and msg.sender_id is distinct from public.current_user_id()
          and msg.created_at > cm.last_read_at
        """,
        org_id,
    )


async def get_channel(conn: asyncpg.Connection, channel_id: UUID) -> asyncpg.Record | None:
    """A single channel, shaped like `list_my_channels` - used right after
    `create_channel()` to build the response (that function returns only the
    new id), and to resolve a channel id reached directly by URL: RLS
    (`channels_select`) returns `None` here for a channel the caller isn't a
    member of, which the route turns into a 404 rather than leaking whether
    the id exists at all."""
    return await conn.fetchrow(
        f"""
        select {_CHANNEL_COLUMNS}
        from public.channels c
        join public.channel_members m on m.channel_id = c.id
        where c.id = $1
          and c.deleted_at is null
        group by c.id, c.kind, c.name, c.created_at, c.created_by
        """,
        channel_id,
    )


async def add_member(
    conn: asyncpg.Connection, *, org_id: UUID, channel_id: UUID, user_id: UUID
) -> bool:
    """A plain insert, governed entirely by `channel_members_insert`'s RLS
    policy - safe as an ordinary insert (not a `SECURITY DEFINER` function)
    precisely because the app never asks for this insert's row back via
    `RETURNING`, so the `channels_select`-style race doesn't apply here.
    `org_id` is the caller's own org, passed through rather than looked up -
    the policy's `org_id = channel_org_id(channel_id)` check is what actually
    rejects a mismatch, not this call site."""
    try:
        async with conn.transaction():
            await conn.execute(
                """
                insert into public.channel_members (channel_id, user_id, org_id)
                values ($1, $2, $3)
                """,
                channel_id,
                user_id,
                org_id,
            )
        return True
    except asyncpg.exceptions.InsufficientPrivilegeError:
        return False
    except asyncpg.exceptions.UniqueViolationError:
        # Already a member - adding them again is a harmless no-op, not an error.
        return True


async def remove_member(conn: asyncpg.Connection, *, channel_id: UUID, user_id: UUID) -> bool:
    """`channel_members_delete` covers three cases in one policy: leaving your
    own channel, the channel's creator removing someone, or an org owner/admin
    moderating any channel in their org. A non-matching caller simply deletes
    zero rows (RLS filters via `USING`, no `WITH CHECK` to violate on a
    DELETE) - the boolean here is "was anything actually removed", not "did an
    error occur"."""
    result = await conn.execute(
        "delete from public.channel_members where channel_id = $1 and user_id = $2",
        channel_id,
        user_id,
    )
    return result != "DELETE 0"


async def rename_channel(
    conn: asyncpg.Connection, *, channel_id: UUID, name: str
) -> asyncpg.Record | None:
    """`None` means either the channel doesn't exist, or `channels_update`
    rejected it (the caller is neither the creator nor an org owner/admin) -
    RLS filters the row out of the `UPDATE`'s own visibility rather than
    raising, the same as `test_cannot_update_another_tenants_organisation`
    documents for `organisations`."""
    return await conn.fetchrow(
        """
        update public.channels set name = $2
        where id = $1
        returning id, kind, name, created_at, created_by
        """,
        channel_id,
        name,
    )


async def mark_read(conn: asyncpg.Connection, *, channel_id: UUID, user_id: UUID) -> None:
    """Bumps the caller's own `last_read_at` - `channel_members_update`'s
    `user_id = current_user_id()` check is what keeps this from ever touching
    someone else's row, not the `$2` parameter here."""
    await conn.execute(
        "update public.channel_members set last_read_at = now() "
        "where channel_id = $1 and user_id = $2",
        channel_id,
        user_id,
    )


async def set_pinned(
    conn: asyncpg.Connection,
    *,
    channel_id: UUID,
    user_id: UUID,
    pinned: bool,
) -> bool:
    """Pin or unpin one conversation for one member.

    The at-most-three rule is a trigger on the table
    (`enforce_channel_pin_limit`, migration `e5c9d02a7f31`), not a check here:
    counting in Python would race two concurrent pins past the limit, and the
    limit has to hold for any caller, not just this code path.
    """
    result = await conn.execute(
        """
        update public.channel_members
        set pinned_at = case when $3 then now() else null end
        where channel_id = $1 and user_id = $2
        """,
        channel_id,
        user_id,
        pinned,
    )
    return result.endswith("1")


async def set_sort_order(
    conn: asyncpg.Connection,
    *,
    channel_id: UUID,
    user_id: UUID,
    sort_order: float,
) -> bool:
    """Place one conversation in the caller's own list.

    The caller sends the midpoint between the two rows it was dropped between,
    which is why the column is a float: inserting between neighbours costs one
    UPDATE rather than renumbering everything below it.
    """
    result = await conn.execute(
        """
        update public.channel_members
        set sort_order = $3
        where channel_id = $1 and user_id = $2
        """,
        channel_id,
        user_id,
        sort_order,
    )
    return result.endswith("1")


async def soft_delete_channel(conn: asyncpg.Connection, channel_id: UUID) -> bool:
    """Remove a channel from every member's list, keeping its messages.

    A soft delete because the messages are a record of what people said to
    each other; dropping the row would take that with it. RLS decides whether
    this caller may write the channel at all, so there is no ownership check
    here - the same division every other write in this file follows.
    """
    result = await conn.execute(
        """
        update public.channels
        set deleted_at = now()
        where id = $1 and deleted_at is null
        """,
        channel_id,
    )
    return result.endswith("1")
