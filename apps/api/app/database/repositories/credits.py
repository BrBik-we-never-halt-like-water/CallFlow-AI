"""SQL for per-teammate credit allocation - a subdivision of the org's
existing `org_safety_settings.daily_budget`, not a parallel limit.

Unlike the org-wide `used_today` (`core/rate_limit.py`'s in-process sliding
window, which resets on restart and doesn't cross replicas - `SYSTEM.md`'s own
documented limitation), a per-teammate `used_today` here is a real query
against persisted `call_outcomes`/`runs`, correct across restarts and
replicas. Both are cited as "calls used today"; only the org-wide one carries
that caveat.

**1 credit = 1 connected call.** `used_today`/`used_today_by_member` count
only calls where the callee actually answered (`status = 'COMPLETED'`, the
same predicate as `CallOutcome.answered`) - a dial that never rang through
(no answer, busy, an invalid number, a provider error) does not spend a
credit, and this is enforced at dial time
(`domain/safety.py::check_dial_allowed`'s `credits_remaining` param, wired up
in `services/run_dialer.py`), not just displayed. This *was* originally
a display-only number with no dial-time gate (migration `43a7b26f6038`'s own
docstring); enforcement was added afterward - see `ISSUES.md`.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def get_allocation(conn: asyncpg.Connection, org_id: UUID, user_id: UUID) -> int:
    """For display: `0` means either "explicitly set to zero" or "never set" -
    those two cases read identically to a teammate looking at their own
    number, which is the existing, deliberate UI convention (Settings ->
    Billing's "hasn't been set yet" placeholder). Enforcement needs to tell
    them apart, which is why it goes through `get_enforced_ceiling` instead,
    not this function."""
    row = await conn.fetchrow(
        "select daily_allocation from public.member_credit_allocations where org_id = $1 and user_id = $2",
        org_id,
        user_id,
    )
    return row["daily_allocation"] if row is not None else 0


async def get_enforced_ceiling(conn: asyncpg.Connection, org_id: UUID, user_id: UUID) -> int | None:
    """`None` when no row exists at all - nobody has ever set this teammate's
    allocation, so the per-teammate gate does not apply to them and only the
    org-wide daily budget governs. A row with `daily_allocation = 0` is a
    real, explicit "block this person entirely" and returns `0`, not `None` -
    the two are indistinguishable through `get_allocation()` above but must
    not be here, or an admin who deliberately zeroes someone's allocation
    would find it silently does nothing.
    """
    row = await conn.fetchrow(
        "select daily_allocation from public.member_credit_allocations where org_id = $1 and user_id = $2",
        org_id,
        user_id,
    )
    return row["daily_allocation"] if row is not None else None


async def used_today(conn: asyncpg.Connection, org_id: UUID, user_id: UUID) -> int:
    # `date_trunc('day', now())` resolves in the session's own timezone
    # setting, not a hardcoded offset - confirmed `UTC` on this deployment
    # (`show timezone`), matching CLAUDE.md §5's TIMESTAMPTZ/UTC convention.
    # "Today" therefore means the UTC day, same as every other day-boundary
    # calculation in this codebase. `upper(c.status) = 'COMPLETED'` - not
    # `disposition <> 'in_flight'` - is what makes this "connected calls",
    # not "resolved call attempts"; see this module's own docstring.
    row = await conn.fetchrow(
        """
        select count(*) as n
        from public.call_outcomes c
        join public.runs r on r.id = c.run_id
        where r.org_id = $1
          and r.started_by = $2
          and upper(c.status) = 'COMPLETED'
          and c.created_at >= date_trunc('day', now())
        """,
        org_id,
        user_id,
    )
    return row["n"]


async def used_today_by_member(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    """The grouped form of `used_today()` - one query for the whole team
    instead of one round-trip per member, for `team_performance()`'s panel.
    Same UTC-day boundary and connected-only definition as `used_today()`."""
    return await conn.fetch(
        """
        select r.started_by, count(*) as used_today
        from public.call_outcomes c
        join public.runs r on r.id = c.run_id
        where r.org_id = $1
          and upper(c.status) = 'COMPLETED'
          and c.created_at >= date_trunc('day', now())
        group by r.started_by
        """,
        org_id,
    )


async def list_allocations(conn: asyncpg.Connection, org_id: UUID) -> list[asyncpg.Record]:
    return await conn.fetch(
        "select user_id, daily_allocation from public.member_credit_allocations where org_id = $1",
        org_id,
    )


async def set_allocation(
    conn: asyncpg.Connection, *, org_id: UUID, user_id: UUID, daily_allocation: int, updated_by: UUID
) -> None:
    await conn.execute(
        """
        insert into public.member_credit_allocations (org_id, user_id, daily_allocation, updated_by, updated_at)
        values ($1, $2, $3, $4, now())
        on conflict (org_id, user_id) do update set
            daily_allocation = excluded.daily_allocation,
            updated_by = excluded.updated_by,
            updated_at = now()
        """,
        org_id,
        user_id,
        daily_allocation,
        updated_by,
    )
