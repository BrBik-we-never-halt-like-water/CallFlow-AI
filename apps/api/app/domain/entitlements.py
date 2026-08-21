"""The plan gate: whether an organisation may create one more of something.

Pure, like `safety.py` - every count arrives as a plain int from a caller that
already did the query, so nothing here touches a database and every rule is
testable without one. The API turns a refusal into 402 Payment Required rather
than 403, so the interface can tell "your plan doesn't include this" apart from
"your role doesn't allow this" and offer an upgrade instead of a dead end.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.domain.plans import Entitlements

# What an organisation sees when it runs out of room. Named for what the reader
# controls, not for the column that stopped them (CLAUDE.md §5).
_UPGRADE = "Upgrade in Billing"


@dataclass(frozen=True)
class EntitlementUsage:
    """What an organisation has actually used, against `Entitlements`.

    Lives here beside the limits rather than in the route, so the interface and the
    gates count the same things by the same names. `seats` counts members *plus*
    pending invitations, for the reason `check_seat_available` explains.
    """

    voice_agents: int
    seats: int
    organisations: int
    ai_integrations: int
    calls_today: int


@dataclass(frozen=True)
class EntitlementVerdict:
    """Allowed, or refused with a sentence worth showing to a person.

    Shaped like `rate_limit.LimitVerdict` and `safety.GateResult` rather than
    reusing either: this module has no business importing the dial gate, and a
    four-line value type is cheaper to repeat than a dependency between two
    domain modules that otherwise never meet.
    """

    allowed: bool
    reason: str = ""


_ALLOWED = EntitlementVerdict(True)


def _check(
    *,
    limit: int | None,
    current: int,
    plan_name: str,
    noun: str,
    plural: str,
    verb: str,
) -> EntitlementVerdict:
    """One shape for every count-against-a-ceiling rule.

    `limit is None` means unlimited and is checked before the comparison, so an
    unlimited plan never depends on how the count is spelled. `limit == 0` falls
    through to the comparison and refuses, which is the point of keeping the two
    distinguishable.

    Both singular and plural nouns are passed in rather than derived. Free's limits
    are mostly `1`, so the naive version produced "Free includes 1 seats and all 1
    are in use" on the message the largest number of people will ever see - and
    English pluralisation is not a rule worth guessing at ("organisations",
    "model providers", "agents" all differ).
    """
    if limit is None:
        return _ALLOWED
    if current < limit:
        return _ALLOWED
    if limit == 0:
        # A separate sentence, not the "all N are in use" one: with a ceiling of
        # zero there is nothing in use, and "add another" is wrong when you have
        # none. This reads as a capability the plan lacks, which is what it is.
        return EntitlementVerdict(False, f"{plan_name} does not include {plural}. {_UPGRADE}.")
    if limit == 1:
        # "all 1 is in use" is not a sentence anyone writes. A ceiling of one is the
        # single most common refusal in the product - it is every Free limit - so it
        # gets its own wording rather than a template that technically fits.
        return EntitlementVerdict(
            False, f"{plan_name} includes 1 {noun}, and it is in use. {_UPGRADE} to {verb}."
        )
    return EntitlementVerdict(
        False,
        f"{plan_name} includes {limit} {plural} and all {limit} are in use. "
        f"{_UPGRADE} to {verb}.",
    )


def check_agent_create_allowed(
    *, entitlements: Entitlements, plan_name: str, current_agent_count: int
) -> EntitlementVerdict:
    return _check(
        limit=entitlements.max_voice_agents,
        current=current_agent_count,
        plan_name=plan_name,
        noun="agent",
        plural="agents",
        verb="add another",
    )


def check_seat_available(
    *,
    entitlements: Entitlements,
    plan_name: str,
    member_count: int,
    pending_invite_count: int,
) -> EntitlementVerdict:
    """A pending invitation holds a seat.

    Counting members only would let an admin send ten invitations against three
    seats and discover the problem at accept time, one disappointed teammate at
    a time. Accept re-checks anyway, because a downgrade can land between the
    invitation and the click.
    """
    return _check(
        limit=entitlements.max_seats,
        current=member_count + pending_invite_count,
        plan_name=plan_name,
        noun="seat",
        plural="seats",
        verb="invite more",
    )


def check_org_create_allowed(
    *, entitlements: Entitlements, plan_name: str, owned_org_count: int
) -> EntitlementVerdict:
    """The one entitlement counted per user rather than per organisation.

    A plan belongs to an organisation, but "how many workspaces may I create" is
    a property of a person, so `owned_org_count` is every non-deleted
    organisation this user owns - and the limit comes from whichever
    organisation they are acting from. The signup trigger never reaches this
    check: a new user's first organisation must be created regardless of plan,
    or a limit becomes a signup outage.
    """
    return _check(
        limit=entitlements.max_organisations,
        current=owned_org_count,
        plan_name=plan_name,
        noun="organisation",
        plural="organisations",
        verb="add another",
    )


def check_ai_integration_allowed(
    *, entitlements: Entitlements, plan_name: str, current_count: int
) -> EntitlementVerdict:
    """Packaging, explicitly not cost control.

    An organisation's own model key is billed to them and *reduces* CallFlow's
    OpenRouter spend, so limiting it saves nothing - it exists so "mix any
    vendors you like" is a legible step up. Checked on connect only, never on
    update and never at use, so a downgrade cannot break a live campaign or
    strand a credential nobody can rotate.
    """
    return _check(
        limit=entitlements.max_ai_integrations,
        current=current_count,
        plan_name=plan_name,
        noun="model provider",
        plural="model providers",
        verb="connect another",
    )


def effective_daily_call_budget(*, org_override: int | None, plan_max: int | None) -> int | None:
    """The plan is a ceiling on the organisation's own number, not a default.

    An organisation may pace itself *below* what it pays for - that is what
    Settings → Safety is - but never above it. `None` from either side means
    unlimited, so the ceiling only applies when the plan actually states one.
    Feeds `safety.resolve_safety_settings()`, which stays the single place a
    deployment default, an organisation override and now a plan ceiling meet.
    """
    if plan_max is None:
        return org_override
    if org_override is None:
        return plan_max
    return min(org_override, plan_max)


__all__ = [
    "EntitlementUsage",
    "EntitlementVerdict",
    "check_agent_create_allowed",
    "check_ai_integration_allowed",
    "check_org_create_allowed",
    "check_seat_available",
    "effective_daily_call_budget",
]


# --- usage credit and the managed-key tier ---------------------------------------
#
# Both of these gate a *call*, not a stored row, so they are checked at dial time
# as well as wherever the interface offers the action. An agent saved on Starter
# must not keep dialling premium on CallFlow's keys after a downgrade to Free.


def check_own_keys_allowed(
    *, entitlements: Entitlements, plan_name: str
) -> EntitlementVerdict:
    """Whether this plan may connect its own STT/LLM/TTS vendor key.

    Free may not; every paid plan may. The refusal names the capability rather
    than a count, because there is no number to be at the end of - `_check`'s
    "does not include" wording exists for exactly this shape but reads oddly for
    something the customer already owns.

    Deliberately not about telephony. A carrier is always the organisation's own
    account and is mandatory to dial at all, so a "you may not bring your own"
    rule that swept it up would stop Free working entirely.
    """
    if entitlements.may_bring_own_keys:
        return _ALLOWED
    return EntitlementVerdict(
        False,
        f"{plan_name} runs on CallFlow's model providers, so your own keys "
        f"can't be connected on it. {_UPGRADE} to use your own vendors.",
    )


def check_managed_tier_allowed(
    *, entitlements: Entitlements, plan_name: str, tier: str, leg_label: str
) -> EntitlementVerdict:
    """Whether this plan may run `leg_label` at `tier` on **CallFlow's** key.

    Callers must not reach here for a leg on the customer's own key: what the
    customer pays their own vendor is not something this product gets an opinion
    on, and refusing it would be refusing a model they are entitled to use.

    An unrecognised tier refuses. That is the fail-closed direction (CLAUDE.md
    §4 #2) - `domain/rates.py` already bills an untiered provider at the top of
    the card, and permitting here what is charged at premium there would let a
    Free organisation run the most expensive pipeline for Rs 100.
    """
    order = ("economy", "standard", "premium")
    allowed = entitlements.max_managed_tier
    if allowed not in order or tier not in order:
        return EntitlementVerdict(
            False,
            f"{leg_label} isn't priced on {plan_name} yet. {_UPGRADE} to use it.",
        )
    if order.index(tier) <= order.index(allowed):
        return _ALLOWED
    return EntitlementVerdict(
        False,
        f"{plan_name} covers {allowed} model providers on CallFlow's keys, and "
        f"this {leg_label} is {tier}. {_UPGRADE}, or connect your own key for it.",
    )


def check_credit_available(
    *, balance_paise: int | None, plan_name: str
) -> EntitlementVerdict:
    """Whether there is credit left to place a call.

    `None` means the balance could not be read, and that **refuses**. A credit
    check that cannot complete must deny, or an outage becomes free calling
    (CLAUDE.md §4 #2) - the same reason the rate limiter fails closed.

    A negative balance also refuses, but it is a normal state rather than an
    error: a call that overran its hold settles for more than was reserved,
    because a conversation already happening with a person is never cut off over
    money. The next call is the one that stops.
    """
    if balance_paise is None:
        return EntitlementVerdict(
            False,
            "Your usage credit couldn't be checked, so no call was placed. "
            "Try again in a moment.",
        )
    if balance_paise > 0:
        return _ALLOWED
    return EntitlementVerdict(
        False,
        f"{plan_name}'s usage credit is spent. Top up in Billing, or wait for "
        "the next period to start.",
    )


def check_member_credit_cap(
    *, cap_paise: int | None, spent_paise: int, plan_name: str
) -> EntitlementVerdict:
    """One teammate's share of the organisation's credit.

    `None` means nobody set a cap for this person, so only the organisation-wide
    balance governs them - "no row is ungated," the reason a cap of `0` must
    stay distinguishable from it. `0` blocks them entirely, which is a real
    thing an owner may want.
    """
    if cap_paise is None:
        return _ALLOWED
    if spent_paise < cap_paise:
        return _ALLOWED
    if cap_paise == 0:
        return EntitlementVerdict(
            False,
            "You have no usage credit allocated. Ask an owner or admin to set "
            "some in Organisation → Team.",
        )
    return EntitlementVerdict(
        False,
        "You have used your share of this period's usage credit. Ask an owner "
        "or admin to raise it in Organisation → Team.",
    )


# --- which agents an over-limit organisation may still use ----------------------


@dataclass(frozen=True)
class AgentStanding:
    """One agent, as the usability rule needs to see it."""

    agent_id: str
    created_at: datetime
    kept_at: datetime | None = None
    """When the customer explicitly chose to keep this one active, if they have.

    Nullable because most organisations never go over their limit and never make
    the choice. It is a *preference*, not a state: it survives an upgrade, so
    downgrading twice does not ask the same question twice.
    """


def usable_agent_ids(
    agents: Sequence[AgentStanding], *, limit: int | None
) -> frozenset[str]:
    """Which agents may still place calls.

    `None` is unlimited and every agent is usable. Otherwise the allowance is
    filled in this order, and the rest are locked:

      1. agents the customer explicitly kept, most recent choice first
      2. everything else, oldest first

    **Oldest-first rather than newest** for the default, because the agent someone
    built on day one is the likeliest to be the one running their work - and if the
    guess is wrong they can override it, which is what `kept_at` is for. Newest-first
    would lock the established agent in favour of one made five minutes ago.

    **Locked, never deleted.** An agent is a configuration row; making it unusable
    destroys nothing and it comes back the moment the plan does. That is different
    from a vendor credential, which holds a secret this product could not recreate -
    which is why `docs/BILLING.md` §3 leaves *those* alone on a downgrade and this
    rule does not extend to them.

    A limit of `0` locks everything, and that is deliberate rather than an edge to
    round away: an organisation whose plan includes no agents has none it may use.
    """
    if limit is None:
        return frozenset(agent.agent_id for agent in agents)
    if limit <= 0:
        return frozenset()

    ranked = sorted(
        agents,
        key=lambda a: (
            a.kept_at is None,
            # Negated via the tuple's second slot below rather than `reverse`,
            # because the other keys sort ascending and one `reverse` would flip
            # them all.
            -(a.kept_at.timestamp() if a.kept_at else 0.0),
            a.created_at,
        ),
    )
    return frozenset(agent.agent_id for agent in ranked[:limit])


def check_agent_usable(
    *, agent_id: str, usable: frozenset[str], plan_name: str, limit: int | None
) -> EntitlementVerdict:
    """Refuse a run whose agent is locked by the plan.

    Separate from `check_agent_create_allowed`, which gates *making* one. Without
    this second check the limit is a one-time toll rather than an entitlement:
    subscribe for a month, create ten agents, downgrade, keep using all ten.
    """
    if agent_id in usable:
        return _ALLOWED
    if limit == 0:
        return EntitlementVerdict(
            False, f"{plan_name} does not include voice agents. {_UPGRADE}."
        )
    return EntitlementVerdict(
        False,
        f"This agent is locked - {plan_name} covers "
        f"{limit} {'agent' if limit == 1 else 'agents'} and others are active. "
        f"{_UPGRADE}, or make this one active in Agents.",
    )
