"""What one connected minute costs, and therefore what a call spends.

Pure, like `safety.py` and `entitlements.py`: every input arrives as a plain value
from a caller that already did the lookups, so the arithmetic is testable with no
database and no mocks.

**The shape of the charge.** A platform fee applies to every call. On top of it,
each leg of the pipeline - what the agent hears with, thinks with, speaks with -
adds a per-minute rate *only when CallFlow's own key paid for it*. A customer
using their own vendor keys pays the platform fee alone, because CallFlow's cost
for that call really is only the media.

    rate = platform fee + sum(tier add-on for each leg on CallFlow's key)

**Why tiers rather than measured vendor cost.** A call's vendor cost varies 23x
across pipelines (`docs/PRICING_DECISIONS.md` §1), so a single managed rate cannot
exist - priced for the cheap end it loses money on the expensive end, and priced
for the expensive end nobody uses CallFlow's keys. Three tiers per leg bound that
spread into nine published numbers a customer can see *before* they pick a model,
which is worth more to them than an exact bill they cannot predict.

**Why this module takes tiers, not provider names.** `domain/` imports nothing
outward (CLAUDE.md §2), and the provider catalogue lives in `integrations/`. The
provider-to-tier mapping is therefore data - a seeded `provider_tiers` table, read
by the caller - and this module does arithmetic on the result. That also makes
retiering a provider a data change rather than a deploy, which is the same reason
`plan_entitlements` is a table.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

SECONDS_PER_MINUTE = 60


class PipelineTier(str, Enum):
    """Cost bands, not quality judgements.

    Named for what they cost CallFlow, because that is what they decide. A cheap
    model is not a worse model - at conversational token rates most of the good
    ones land in `ECONOMY`.
    """

    ECONOMY = "economy"
    STANDARD = "standard"
    PREMIUM = "premium"


class Leg(str, Enum):
    """The three parts of a voice pipeline that cost money per minute.

    Named for the vendor role rather than the product's own "Hears / Thinks /
    Speaks", because these values reach the database and a rate table, and the
    interface is free to relabel them.
    """

    STT = "stt"
    LLM = "llm"
    TTS = "tts"


#: What an unrecognised provider is billed as. Fail closed (CLAUDE.md §4 #2):
#: a provider nobody has tiered is charged at the top of the card, never the
#: bottom. Resolving it to `ECONOMY` would make "add a provider and forget to
#: tier it" a silent discount, and a discount nobody decided is a cost nobody
#: notices.
UNKNOWN_PROVIDER_TIER = PipelineTier.PREMIUM


@dataclass(frozen=True)
class LegUsage:
    """One leg of a call, and who paid for it.

    `on_platform_key` is the whole reason this type exists. It is resolved from
    what the *worker actually built the pipeline with*, not from the agent's
    stored configuration, because a config row can be edited between the call and
    the settle - and then a customer is charged for a key they were not using.
    """

    leg: Leg
    tier: PipelineTier
    on_platform_key: bool


@dataclass(frozen=True)
class RateCard:
    """The published card: one platform fee plus nine add-ons.

    Integer paise per minute throughout, never a float - this feeds a ledger
    (CLAUDE.md §4 #3).
    """

    platform_fee: int
    add_ons: Mapping[tuple[Leg, PipelineTier], int]

    def add_on_for(self, leg: Leg, tier: PipelineTier) -> int:
        """A missing entry bills at the highest tier for that leg rather than
        zero. A half-seeded card must not hand out free calls; if even that is
        missing the card is unusable and the caller should have failed already."""
        if (leg, tier) in self.add_ons:
            return self.add_ons[(leg, tier)]
        return self.add_ons.get((leg, UNKNOWN_PROVIDER_TIER), 0)


@dataclass(frozen=True)
class CallRate:
    """A resolved per-minute rate, with the breakdown that produced it.

    The breakdown is carried because a customer asking "why did this call cost
    that" deserves an answer, and because the ledger stores the rate it used so a
    statement still explains itself after the card changes.
    """

    paise_per_minute: int
    platform_fee: int
    per_leg: Mapping[Leg, int]

    @property
    def billed_legs(self) -> tuple[Leg, ...]:
        """Only the legs CallFlow's own keys paid for, in a stable order."""
        return tuple(leg for leg in Leg if self.per_leg.get(leg, 0) > 0)


def resolve_rate(card: RateCard, legs: tuple[LegUsage, ...]) -> CallRate:
    """The per-minute rate for a call whose pipeline is `legs`.

    A leg on the customer's own key contributes nothing. A leg absent from `legs`
    also contributes nothing - a pipeline with no TTS is a real configuration, and
    charging for a leg that did not run would be charging for nothing.
    """
    per_leg: dict[Leg, int] = {}
    for usage in legs:
        if not usage.on_platform_key:
            continue
        # `+=` rather than `=`: two credentials for one leg is not a shape the
        # product builds, but silently dropping one would understate the charge.
        per_leg[usage.leg] = per_leg.get(usage.leg, 0) + card.add_on_for(
            usage.leg, usage.tier
        )

    return CallRate(
        paise_per_minute=card.platform_fee + sum(per_leg.values()),
        platform_fee=card.platform_fee,
        per_leg=per_leg,
    )


def spend_for(rate: CallRate, duration_seconds: float | None) -> int:
    """What a call of this length costs, in paise.

    Prorated by the second rather than rounded up to a whole minute. A voicemail
    that rings for eight seconds should cost eight seconds; billing it as a minute
    is the kind of arithmetic a customer notices and resents, and outbound work is
    full of short calls.

    Takes a float because `call_outcomes.duration_seconds` is a `Float` column,
    and returns integer paise regardless - the float stops at this boundary and
    never reaches the ledger. Rounding is half-up to the paise, so the error on
    any one call is under half a paise and does not accumulate in either party's
    favour. `None` and negatives both cost nothing: a call with no reported
    duration never connected, and a negative one is a clock going backwards, which
    must not become a credit.
    """
    if duration_seconds is None or duration_seconds <= 0:
        return 0
    total = rate.paise_per_minute * duration_seconds
    return int((total + SECONDS_PER_MINUTE // 2) // SECONDS_PER_MINUTE)


def reserve_for(rate: CallRate, typical_seconds: int) -> int:
    """What to hold before dialling, in paise.

    A *typical* call, deliberately not the worst case. The carrier ceiling is 900
    seconds, and holding that at a premium rate would let a month's credit support
    only a handful of concurrent calls - so the pool would be exhausted by calls
    that never happened.

    The consequence is accepted rather than mitigated: a call that runs long
    settles for more than was held and can push the balance slightly negative. A
    conversation already happening with a person is never cut off over money.
    """
    return spend_for(rate, max(typical_seconds, 0))


def estimated_minutes(balance_paise: int, rate: CallRate) -> int:
    """How many minutes a balance buys at this rate.

    An estimate, and the interface must say so. The next call may use a different
    pipeline and therefore a different rate, so this is "minutes if you keep doing
    what you are doing" - which is the only honest way to express a money balance
    in minutes when the same minute costs different amounts.
    """
    if rate.paise_per_minute <= 0 or balance_paise <= 0:
        return 0
    return balance_paise // rate.paise_per_minute


__all__ = [
    "UNKNOWN_PROVIDER_TIER",
    "CallRate",
    "Leg",
    "LegUsage",
    "PipelineTier",
    "RateCard",
    "estimated_minutes",
    "reserve_for",
    "resolve_rate",
    "spend_for",
]
