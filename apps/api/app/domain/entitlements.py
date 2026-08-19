"""The plan gate: whether an organisation may create one more of something.

Pure, like `safety.py` - every count arrives as a plain int from a caller that
already did the query, so nothing here touches a database and every rule is
testable without one. The API turns a refusal into 402 Payment Required rather
than 403, so the interface can tell "your plan doesn't include this" apart from
"your role doesn't allow this" and offer an upgrade instead of a dead end.
"""

from __future__ import annotations

from dataclasses import dataclass

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
