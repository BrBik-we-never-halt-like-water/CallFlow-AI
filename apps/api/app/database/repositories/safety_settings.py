"""Org-scoped overrides for the safety guards. Every column is nullable - null
means "use the deployment default" (`app/core/config.py`), so an org that has
never touched Safety behaves exactly as it did before this table existed."""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def get_for_org(conn: asyncpg.Connection, org_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        select org_id, allowlist, max_calls_per_run, calls_per_window, window_minutes,
               daily_budget, updated_at
        from public.org_safety_settings
        where org_id = $1
        """,
        org_id,
    )


async def upsert(
    conn: asyncpg.Connection,
    org_id: UUID,
    *,
    allowlist: list[str],
    max_calls_per_run: int | None,
    calls_per_window: int | None,
    window_minutes: int | None,
    daily_budget: int | None,
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        insert into public.org_safety_settings
            (org_id, allowlist, max_calls_per_run, calls_per_window, window_minutes, daily_budget)
        values ($1, $2, $3, $4, $5, $6)
        on conflict (org_id) do update set
            allowlist = excluded.allowlist,
            max_calls_per_run = excluded.max_calls_per_run,
            calls_per_window = excluded.calls_per_window,
            window_minutes = excluded.window_minutes,
            daily_budget = excluded.daily_budget,
            updated_at = now()
        returning org_id, allowlist, max_calls_per_run, calls_per_window, window_minutes,
                  daily_budget, updated_at
        """,
        org_id,
        allowlist,
        max_calls_per_run,
        calls_per_window,
        window_minutes,
        daily_budget,
    )
