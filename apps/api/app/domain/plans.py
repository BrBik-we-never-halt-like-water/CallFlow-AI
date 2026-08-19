"""What each plan allows, and how a negotiated override resolves against it."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType


class PlanId(str, Enum):
    """Mirrors `organisations.plan_id`'s check constraint and `pricing.ts`'s own
    `PlanId` exactly. All three move together or the product disagrees with
    itself about what an organisation is paying for.
    """

    FREE = "free"
    STARTER = "starter"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class Entitlements:
    """One plan's ceilings.

    `None` means unlimited, never a sentinel like `-1`. `0` is a real, enforced
    value and stays deliberately distinct from `None` - the same distinction
    `credits_repo.get_enforced_ceiling()` already depends on, for the same
    reason: "nobody set a limit" and "the limit is zero" are different answers.

    `llm_spend_limit_usd` is a float rather than integer minor units, which
    looks like a breach of CLAUDE.md §4 #3. It is not: this is a ceiling handed
    to OpenRouter's API in the units it accepts (matching
    `config.openrouter_default_limit_usd`), not a value this system does
    accounting arithmetic on. Nothing in the credit or payment path touches it.
    """

    max_voice_agents: int | None
    max_seats: int | None
    max_organisations: int | None
    max_ai_integrations: int | None
    daily_call_budget: int | None
    llm_spend_limit_usd: float


# The seeded ladder. `plan_entitlements` in the database carries these same
# numbers because a SQL trigger and an RLS predicate both need to read them;
# `tests/test_plans.py` asserts the two agree, so this stays the readable copy
# and the table stays the enforceable one.
#
# Telephony is deliberately absent. A carrier is the organisation's own Twilio
# account, so an extra connection costs CallFlow nothing - only LiveKit minutes
# and OpenRouter tokens do, and those are `daily_call_budget` and
# `llm_spend_limit_usd`. See docs/BILLING.md §1.
_LADDER: Mapping[PlanId, Entitlements] = MappingProxyType(
    {
        PlanId.FREE: Entitlements(
            max_voice_agents=1,
            max_seats=1,
            max_organisations=1,
            max_ai_integrations=2,
            daily_call_budget=20,
            llm_spend_limit_usd=5.0,
        ),
        PlanId.STARTER: Entitlements(
            max_voice_agents=3,
            max_seats=3,
            max_organisations=1,
            max_ai_integrations=3,
            daily_call_budget=200,
            llm_spend_limit_usd=25.0,
        ),
        PlanId.GROWTH: Entitlements(
            max_voice_agents=10,
            max_seats=10,
            max_organisations=3,
            max_ai_integrations=None,
            daily_call_budget=1000,
            llm_spend_limit_usd=100.0,
        ),
        # Enterprise carries Growth's numbers rather than unlimited ones. Its
        # real limits arrive as a per-organisation override, and seeding this
        # row blank would leave a window between "deal signed" and "override
        # written" in which the organisation had no ceiling at all.
        PlanId.ENTERPRISE: Entitlements(
            max_voice_agents=10,
            max_seats=10,
            max_organisations=3,
            max_ai_integrations=None,
            daily_call_budget=1000,
            llm_spend_limit_usd=100.0,
        ),
    }
)

OVERRIDABLE: frozenset[str] = frozenset(f.name for f in dataclasses.fields(Entitlements))


class UnknownOverrideKey(ValueError):
    """Raised rather than silently ignoring a limit nobody will ever enforce."""

    def __init__(self, keys: frozenset[str]) -> None:
        named = ", ".join(sorted(keys))
        allowed = ", ".join(sorted(OVERRIDABLE))
        super().__init__(f"Not a limit this system enforces: {named}. Use one of: {allowed}.")


def ladder() -> Mapping[PlanId, Entitlements]:
    """Every plan's seeded entitlements, for the plans endpoint and the seed test."""
    return _LADDER


def entitlements_for(
    plan_id: str, override: Mapping[str, int | None] | None = None
) -> Entitlements:
    """Resolve one organisation's effective ceilings.

    An unrecognised `plan_id` resolves to Free, not to the plan it looks
    closest to and not to unlimited. `organisations.plan_id` is a 32-character
    text column, so a hand-edited or half-migrated value must land on the
    *smallest* entitlement - CLAUDE.md §4 #2, fail closed.

    `override` carries a negotiated per-organisation limit (the `enterprise`
    tier). A key's **presence** is what overrides, so `{"max_seats": None}`
    means unlimited while omitting the key means inherit. That distinction is
    the reason this is a mapping rather than a dataclass of optional fields:
    with optional fields, `None` would have to mean "inherit" and "unlimited"
    at the same time.
    """
    try:
        base = _LADDER[PlanId(plan_id)]
    except ValueError:
        base = _LADDER[PlanId.FREE]

    if not override:
        return base

    unknown = frozenset(override) - OVERRIDABLE
    if unknown:
        raise UnknownOverrideKey(unknown)

    return dataclasses.replace(base, **dict(override))


__all__ = [
    "OVERRIDABLE",
    "Entitlements",
    "PlanId",
    "UnknownOverrideKey",
    "entitlements_for",
    "ladder",
]
