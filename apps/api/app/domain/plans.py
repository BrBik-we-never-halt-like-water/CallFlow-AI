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
    `credits_repo.get_credit_cap()` already depends on, for the same reason:
    "nobody set a limit" and "the limit is zero" are different answers.

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

    monthly_credit_paise: int | None = 0
    """Usage credit granted each period, in integer paise (CLAUDE.md §4 #3).

    `0` means a plan that grants none, `None` means uncapped. Defaulted so an
    override mapping that omits it does not have to know about it."""

    max_managed_tier: str = "premium"
    """The most expensive tier this plan may run on **CallFlow's** keys. Free is
    `economy`, because a free organisation on a premium pipeline costs ~Rs 13/min
    against no revenue. Own-key legs are unaffected - this caps what CallFlow
    pays for, not what the customer may choose."""

    may_bring_own_keys: bool = True
    """Whether this plan may connect its own STT/LLM/TTS vendor keys.

    False for Free only, and that is a reversal of shipped behaviour - see the
    ladder comment below. Telephony is *not* covered by this: a carrier is always
    bring-your-own and is mandatory to dial at all.
    """


#: The daily call ceiling, identical on every plan.
#:
#: **Not a plan feature, and no longer sold as one.** Usage credit is the economic
#: limit, and it binds first by a wide margin: at 90-second calls Free's credit
#: allows 44 calls a month against a former cap of 600, and Growth's allows about
#: 63 a day. A per-plan call cap was therefore a number no customer could reach -
#: it looked like a limit and was not one, and it described neither of the two
#: real answers (44 calls at 90 seconds, 11 at six minutes).
#:
#: It survives as a **runaway bound**, because credit does not bound everything
#: that matters: it limits money spent, not how many people a loop can disturb in
#: an hour. An organisation may still set itself lower in Settings -> Safety, and
#: `resolve_safety_settings` takes the `min()`. Weakening this further is the kind
#: of guard change CLAUDE.md §4 #8 asks for real scrutiny on.
RUNAWAY_CALL_CEILING = 500

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
        # `may_bring_own_keys=True` on Free, despite the decision to make Free
        # managed-only. **That decision is blocked, not implemented.**
        #
        # It presumes CallFlow has vendor keys to lend, and it has none: every
        # STT/TTS/LLM key a call uses comes from `ai_provider_credentials`, the
        # organisation's own table. There is no platform-owned credential in
        # `config`, no fallback in the worker's `AgentSpec`, and no resolution path
        # that could supply one. So `max_ai_integrations=0` here would not make
        # Free managed - it would make Free **undialable**, which
        # `test_free_can_connect_at_least_one_model_provider` has asserted since
        # before any of this.
        #
        # `max_managed_tier="economy"` is kept and is currently dormant: it caps
        # what Free may run *on CallFlow's keys*, and nothing runs on CallFlow's
        # keys yet. It becomes live the day platform keys exist, which is also the
        # day `may_bring_own_keys=False` becomes implementable.
        PlanId.FREE: Entitlements(
            max_voice_agents=1,
            max_seats=1,
            max_organisations=1,
            max_ai_integrations=2,
            daily_call_budget=RUNAWAY_CALL_CEILING,
            llm_spend_limit_usd=5.0,
            monthly_credit_paise=10_000,
            max_managed_tier="economy",
            may_bring_own_keys=True,
        ),
        PlanId.STARTER: Entitlements(
            max_voice_agents=3,
            max_seats=3,
            max_organisations=1,
            max_ai_integrations=3,
            daily_call_budget=RUNAWAY_CALL_CEILING,
            llm_spend_limit_usd=25.0,
            monthly_credit_paise=85_000,
        ),
        PlanId.GROWTH: Entitlements(
            max_voice_agents=10,
            max_seats=10,
            max_organisations=3,
            max_ai_integrations=None,
            daily_call_budget=RUNAWAY_CALL_CEILING,
            llm_spend_limit_usd=100.0,
            monthly_credit_paise=425_000,
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
            daily_call_budget=RUNAWAY_CALL_CEILING,
            llm_spend_limit_usd=100.0,
            monthly_credit_paise=425_000,
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
