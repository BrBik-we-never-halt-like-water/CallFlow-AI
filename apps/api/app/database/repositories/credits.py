"""SQL for a teammate's share of the organisation's usage credit.

This table used to also hold a per-teammate *call-count* allocation
(`daily_allocation`) - a subdivision of the org-wide daily budget, counting
only connected calls. That concept is retired (`ISSUES.md`): calls-per-day
stopped being a meaningful lever once usage credit became the thing plans are
actually sold on, and the org-wide daily budget alone remains as the runaway
safety rail. Only the money-denominated cap below remains per teammate.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg


async def get_credit_cap(conn: asyncpg.Connection, org_id: UUID, user_id: UUID) -> int | None:
    """One teammate's share of the organisation's usage credit, in paise.

    `None` when no row exists, or a row exists but the cap was never set - both
    mean "ungated, only the organisation-wide balance governs." A cap of `0`
    is a real, explicit "this person spends none of it" and is returned as
    `0`, not `None`.
    """
    row = await conn.fetchrow(
        "select monthly_credit_cap_paise from public.member_credit_allocations "
        "where org_id = $1 and user_id = $2",
        org_id,
        user_id,
    )
    return row["monthly_credit_cap_paise"] if row is not None else None


async def set_credit_cap(
    conn: asyncpg.Connection, *, org_id: UUID, user_id: UUID, cap_paise: int | None, updated_by: UUID
) -> None:
    """Set (or clear, with `cap_paise=None`) one teammate's usage-credit share.

    The only writer to `member_credit_allocations` now that the call-count
    allocation it used to also hold has been retired.
    """
    await conn.execute(
        """
        insert into public.member_credit_allocations
            (org_id, user_id, monthly_credit_cap_paise, updated_by, updated_at)
        values ($1, $2, $3, $4, now())
        on conflict (org_id, user_id) do update set
            monthly_credit_cap_paise = excluded.monthly_credit_cap_paise,
            updated_by = excluded.updated_by,
            updated_at = now()
        """,
        org_id,
        user_id,
        cap_paise,
        updated_by,
    )


# --- usage credit: the money ledger ---------------------------------------------
#
# The org-wide balance, as opposed to the per-teammate share above: a single
# pool in paise that every teammate's calls draw from, spent by the second.
#
# Every write goes through a SECURITY DEFINER function. `credit_ledger` has its
# insert grant revoked, so a statement from here would fail - which is the point:
# the function is the only write path, it decides the sign of each entry, and it
# moves `organisations.credit_balance_paise` in the same breath as the row.


async def balance(conn: asyncpg.Connection, org_id: UUID) -> int:
    """The organisation's usable credit, in paise.

    Summed from the ledger rather than read from `organisations`, because the
    column is a cache and this is the number a dial decision turns on. Negative
    is a real answer: a call that overran its hold settles for more than was
    reserved.
    """
    return int(await conn.fetchval("select public.credit_balance($1)", org_id) or 0)


async def grant(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    amount_paise: int,
    dedupe_key: str,
    reason: str | None = None,
) -> bool:
    """Add credit. False means this grant was already recorded.

    False is normal traffic, not an error: a gateway redelivers, and a renewal
    handled twice must not grant twice. `dedupe_key` is what makes that safe, so
    callers must derive it from something stable - the payment id, or the
    subscription period - never from a clock.
    """
    return bool(
        await conn.fetchval(
            "select public.credit_append($1, null, 'grant', $2, $3, null, null, $4)",
            org_id,
            amount_paise,
            dedupe_key,
            reason,
        )
    )


async def expire_remainder(
    conn: asyncpg.Connection, *, org_id: UUID, dedupe_key: str, reason: str | None = None
) -> bool:
    """Write off whatever is left, as one negative entry.

    Called at renewal, before the new grant. Plan credit does not roll over, and
    expressing that as an explicit ledger row rather than a query-time filter is
    what keeps the balance a plain `sum()` and lets a customer see where their
    unused credit went.

    Reads the balance first, so this is only correct inside the caller's
    transaction - which is where a renewal already runs.
    """
    remaining = await balance(conn, org_id)
    if remaining <= 0:
        return False
    return bool(
        await conn.fetchval(
            "select public.credit_append($1, null, 'expiry', $2, $3, null, null, $4)",
            org_id,
            remaining,
            dedupe_key,
            reason,
        )
    )


async def hold(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    user_id: UUID | None,
    call_key: str,
    amount_paise: int,
    rate_paise_per_minute: int,
) -> bool:
    """Reserve credit before dialling. False means this call already had a hold.

    `call_key` is `run_id:contact_name:phone_masked` - the same triple
    `call_outcomes` is keyed on, so the hold and the outcome address the same
    call and the settle can find its own hold. Using the masked number is
    deliberate: it is the form the product already displays, and a billing table
    has no business holding the real one (CLAUDE.md §4 #4).
    """
    return bool(
        await conn.fetchval(
            "select public.credit_append($1, $2, 'hold', $3, $4, $5, $6, null)",
            org_id,
            user_id,
            amount_paise,
            f"hold:{call_key}",
            call_key,
            rate_paise_per_minute,
        )
    )


async def release(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    user_id: UUID | None,
    call_key: str,
    amount_paise: int,
    reason: str | None = None,
) -> bool:
    """Give a hold back with nothing spent - a call that never connected."""
    return bool(
        await conn.fetchval(
            "select public.credit_append($1, $2, 'release', $3, $4, $5, null, $6)",
            org_id,
            user_id,
            amount_paise,
            f"release:{call_key}",
            call_key,
            reason,
        )
    )


async def settle(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    user_id: UUID | None,
    call_key: str,
    spend_paise: int,
    rate_paise_per_minute: int,
) -> bool:
    """Release the hold and charge the actual duration, together.

    One function call rather than a release followed by a spend, because a
    half-applied settle is a free call: the hold comes back and nothing is
    charged. The definer function does both, and both are keyed on `call_key`, so
    a retried worker callback is a no-op.

    False means the spend was already recorded. The caller should treat that as
    success - the money has already moved.
    """
    return bool(
        await conn.fetchval(
            "select public.credit_settle($1, $2, $3, $4, $5)",
            org_id,
            user_id,
            call_key,
            spend_paise,
            rate_paise_per_minute,
        )
    )


async def member_spend_this_period(
    conn: asyncpg.Connection, *, org_id: UUID, user_id: UUID, since: datetime
) -> int:
    """What one teammate has drawn since `since`, in paise.

    Counts holds as well as spends. An in-flight call is money committed, and
    ignoring it would let one person start a hundred calls at once inside their
    cap and only discover the overrun as they settled.
    """
    return int(
        await conn.fetchval(
            "select public.credit_member_spend($1, $2, $3)", org_id, user_id, since
        )
        or 0
    )


async def release_stale_holds(conn: asyncpg.Connection, *, older_than_seconds: int) -> int:
    """Give back holds whose call never reported. Returns how many.

    A worker that dies leaves a hold pinning credit forever. Modelled on
    `runs.expire_stale_in_flight`, and released rather than deleted so the ledger
    still shows what happened. The carrier's own `max_call_duration` bounds how
    old a legitimate hold can be, so the caller passes a multiple of it.
    """
    return int(
        await conn.fetchval(
            "select public.credit_release_stale_holds($1)", older_than_seconds
        )
        or 0
    )


async def list_ledger(
    conn: asyncpg.Connection, org_id: UUID, *, limit: int = 100
) -> list[asyncpg.Record]:
    """The statement, newest first. Plain select - the organisation may read its
    own ledger, and RLS scopes it."""
    return await conn.fetch(
        """
        select id, entry_kind, amount_minor, currency, call_key,
               rate_paise_per_minute, reason, created_at
          from public.credit_ledger
         where org_id = $1
         order by created_at desc
         limit $2
        """,
        org_id,
        limit,
    )


async def granted_this_period(conn: asyncpg.Connection, org_id: UUID) -> int:
    """Credit actually made available in the current period, in paise.

    Derived from the ledger rather than from the plan's entitlement, because the
    two disagree in every state that matters: before the period's grant has landed
    the plan says 10,000 and the ledger says nothing, and after a top-up the ledger
    says more than the plan ever would. A meter built on the entitlement therefore
    reads "you have used everything" for an organisation that has used nothing, and
    goes negative for one that has topped up.

    The period boundary is the most recent `expiry` entry - that is exactly what an
    expiry marks, a period ending and its remainder written off. With no expiry yet
    the organisation is in its first period and every grant counts.
    """
    return int(
        await conn.fetchval(
            """
            select coalesce(sum(amount_minor), 0)::bigint
              from public.credit_ledger
             where org_id = $1
               and entry_kind = 'grant'
               and created_at >= coalesce(
                     (select max(created_at) from public.credit_ledger
                       where org_id = $1 and entry_kind = 'expiry'),
                     '-infinity'::timestamptz
                   )
            """,
            org_id,
        )
        or 0
    )
