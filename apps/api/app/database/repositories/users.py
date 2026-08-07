"""SQL for a user's own profile."""

from __future__ import annotations

import asyncpg


async def update_profile(
    conn: asyncpg.Connection, *, name: str | None, avatar_url: str | None
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        update public.users
           set name = coalesce($1, name),
               avatar_url = coalesce($2, avatar_url)
         where id = public.current_user_id()
        returning id, email, name, avatar_url
        """,
        name,
        avatar_url,
    )
