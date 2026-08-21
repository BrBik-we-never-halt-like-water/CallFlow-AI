"""The published rate card, and which tier each vendor sits in.

Two seeded, read-only tables. They exist rather than living in Python because
retiering a provider or moving a price is a commercial decision that should be a
data change, not a deploy - the same reasoning `plan_entitlements` already
carries.

Read on every dial, so both are small and indexed by their primary keys. If that
ever stops being cheap enough, the fix is a cache with an explicit TTL, not
moving the numbers back into code.
"""

from __future__ import annotations

import asyncpg

from app.domain.rates import Leg, PipelineTier, RateCard

#: The row that holds the fee charged on every call regardless of keys. Stored in
#: the same table as the add-ons so the whole card is one query, using a leg
#: value no real leg can collide with.
PLATFORM_ROW = ("platform", "flat")


async def load_rate_card(conn: asyncpg.Connection) -> RateCard:
    """The whole card in one query.

    A missing platform-fee row yields a fee of zero, which the caller must treat
    as a misconfiguration rather than a free product. It is not defaulted to a
    guess here: inventing a price is worse than surfacing that none is set.
    """
    rows = await conn.fetch("select leg, tier, paise_per_minute from public.usage_rates")

    platform_fee = 0
    add_ons: dict[tuple[Leg, PipelineTier], int] = {}
    for row in rows:
        if (row["leg"], row["tier"]) == PLATFORM_ROW:
            platform_fee = int(row["paise_per_minute"])
            continue
        try:
            key = (Leg(row["leg"]), PipelineTier(row["tier"]))
        except ValueError:
            # A row for a leg or tier this build does not know about. Skipped
            # rather than raised: a newer deployment seeding a fourth leg must
            # not take the dial path down on an older one.
            continue
        add_ons[key] = int(row["paise_per_minute"])

    return RateCard(platform_fee=platform_fee, add_ons=add_ons)


async def tiers_for(
    conn: asyncpg.Connection, wanted: tuple[tuple[Leg, str], ...]
) -> dict[tuple[Leg, str], PipelineTier]:
    """Look up several (leg, provider) pairs at once.

    Absent pairs are simply missing from the result, and the caller resolves them
    to `UNKNOWN_PROVIDER_TIER` - which is premium. That is the fail-closed
    direction and it belongs to the domain, not here: this function's job is to
    report what the table says, including that it says nothing.
    """
    if not wanted:
        return {}

    # Two parallel arrays unnested into pairs, rather than an array of records:
    # asyncpg refuses to encode anonymous composite types, so `= any($1::record[])`
    # fails at bind time regardless of how valid the SQL looks.
    rows = await conn.fetch(
        """
        select p.leg, p.provider_id, p.tier
          from public.provider_tiers p
          join unnest($1::text[], $2::text[]) as w(leg, provider_id)
            on w.leg = p.leg and w.provider_id = p.provider_id
        """,
        [leg.value for leg, _ in wanted],
        [provider for _, provider in wanted],
    )
    return {
        (Leg(row["leg"]), row["provider_id"]): PipelineTier(row["tier"]) for row in rows
    }
