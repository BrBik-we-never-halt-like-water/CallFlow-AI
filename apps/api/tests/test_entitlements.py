"""The plan gate: at, under and over each ceiling.

Pure - no database, so this runs in CI. What these do *not* prove is that the
same limits hold against raw SQL: `insert` is granted straight to
`authenticated` on the tables involved, so the SQL-side guards are covered by
`test_entitlement_enforcement.py` instead.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

from app.domain.entitlements import (
    AgentStanding,
    check_agent_create_allowed,
    check_agent_usable,
    check_ai_integration_allowed,
    check_credit_available,
    check_managed_tier_allowed,
    check_member_credit_cap,
    check_org_create_allowed,
    check_own_keys_allowed,
    check_seat_available,
    effective_daily_call_budget,
    usable_agent_ids,
)
from app.domain.plans import Entitlements, entitlements_for

STARTER = entitlements_for("starter")


def _with(**changes: object) -> Entitlements:
    return dataclasses.replace(STARTER, **changes)  # type: ignore[arg-type]


# --- agents ---


def test_under_the_agent_limit_is_allowed() -> None:
    verdict = check_agent_create_allowed(
        entitlements=_with(max_voice_agents=3), plan_name="Starter", current_agent_count=2
    )
    assert verdict.allowed
    assert verdict.reason == ""


def test_at_the_agent_limit_is_refused() -> None:
    """The boundary that matters: 3 existing agents on a 3-agent plan means the
    *fourth* is refused, not the third."""
    verdict = check_agent_create_allowed(
        entitlements=_with(max_voice_agents=3), plan_name="Starter", current_agent_count=3
    )
    assert not verdict.allowed


def test_the_agent_refusal_names_the_plan_the_limit_and_the_way_out() -> None:
    """CLAUDE.md §5: an error says what happened and what to do next."""
    reason = check_agent_create_allowed(
        entitlements=_with(max_voice_agents=3), plan_name="Starter", current_agent_count=3
    ).reason

    assert "Starter" in reason
    assert "3" in reason
    assert "Billing" in reason


def test_an_unlimited_agent_allowance_never_refuses() -> None:
    verdict = check_agent_create_allowed(
        entitlements=_with(max_voice_agents=None), plan_name="Enterprise", current_agent_count=10_000
    )
    assert verdict.allowed


def test_a_zero_agent_allowance_refuses_from_the_start() -> None:
    """`0` is an enforced value, not "unset". An override may legitimately set it."""
    verdict = check_agent_create_allowed(
        entitlements=_with(max_voice_agents=0), plan_name="Free", current_agent_count=0
    )
    assert not verdict.allowed
    # Reads as a capability the plan lacks, not as "0 of 0 in use" - and not as
    # "add another" when you have none.
    assert "does not include" in verdict.reason
    assert "another" not in verdict.reason


# --- seats ---


def test_a_pending_invitation_holds_a_seat() -> None:
    """Two members and one outstanding invitation fill a three-seat plan. Counting
    members only would let an admin over-invite and disappoint people one accept
    at a time."""
    verdict = check_seat_available(
        entitlements=_with(max_seats=3),
        plan_name="Starter",
        member_count=2,
        pending_invite_count=1,
    )
    assert not verdict.allowed


def test_seats_free_up_when_an_invitation_is_revoked() -> None:
    verdict = check_seat_available(
        entitlements=_with(max_seats=3),
        plan_name="Starter",
        member_count=2,
        pending_invite_count=0,
    )
    assert verdict.allowed


def test_an_unlimited_seat_allowance_never_refuses() -> None:
    verdict = check_seat_available(
        entitlements=_with(max_seats=None),
        plan_name="Enterprise",
        member_count=900,
        pending_invite_count=100,
    )
    assert verdict.allowed


# --- organisations ---


def test_a_user_at_their_workspace_limit_is_refused() -> None:
    verdict = check_org_create_allowed(
        entitlements=_with(max_organisations=1), plan_name="Starter", owned_org_count=1
    )
    assert not verdict.allowed
    # "organisation", not "organisations": a ceiling of one gets its own wording,
    # because "all 1 is in use" is not a sentence.
    assert "1 organisation, and it is in use" in verdict.reason


def test_a_limit_of_one_reads_as_a_sentence() -> None:
    """Every Free limit is 1, so this is the refusal most people will ever see. A
    template that produced "includes 1 seats and all 1 are in use" technically
    fitted and was wrong."""
    one = check_seat_available(
        entitlements=_with(max_seats=1), plan_name="Free", member_count=1, pending_invite_count=0
    ).reason
    assert "1 seat, and it is in use" in one
    assert "1 seats" not in one and "all 1" not in one

    many = check_seat_available(
        entitlements=_with(max_seats=3), plan_name="Starter", member_count=3, pending_invite_count=0
    ).reason
    assert "3 seats and all 3 are in use" in many


def test_a_user_below_their_workspace_limit_is_allowed() -> None:
    verdict = check_org_create_allowed(
        entitlements=_with(max_organisations=3), plan_name="Growth", owned_org_count=2
    )
    assert verdict.allowed


# --- model providers ---


def test_at_the_ai_key_limit_is_refused() -> None:
    verdict = check_ai_integration_allowed(
        entitlements=_with(max_ai_integrations=2), plan_name="Free", current_count=2
    )
    assert not verdict.allowed
    assert "model providers" in verdict.reason


def test_an_unlimited_ai_key_allowance_never_refuses() -> None:
    verdict = check_ai_integration_allowed(
        entitlements=_with(max_ai_integrations=None), plan_name="Growth", current_count=50
    )
    assert verdict.allowed


# --- the daily-budget ceiling ---


def test_an_organisation_may_pace_itself_below_its_with() -> None:
    """Settings → Safety exists for exactly this: a customer choosing to go slower
    than they pay for."""
    assert effective_daily_call_budget(org_override=50, plan_max=200) == 50


def test_an_organisation_cannot_raise_itself_above_its_with() -> None:
    """The whole point of the ceiling. Without it, Settings → Safety is a way to
    grant yourself a bigger plan."""
    assert effective_daily_call_budget(org_override=5_000, plan_max=200) == 200


def test_no_override_takes_the_plan_number() -> None:
    assert effective_daily_call_budget(org_override=None, plan_max=200) == 200


def test_an_unlimited_plan_leaves_the_organisations_own_number_alone() -> None:
    assert effective_daily_call_budget(org_override=50, plan_max=None) == 50


def test_unlimited_on_both_sides_stays_unlimited() -> None:
    assert effective_daily_call_budget(org_override=None, plan_max=None) is None


def test_an_explicit_zero_override_survives_the_ceiling() -> None:
    """`0` must beat truthiness checks the whole way down - an organisation that
    deliberately paused its own calling stays paused. `min()` gets this right
    where `org_override or plan_max` would silently resume calling."""
    assert effective_daily_call_budget(org_override=0, plan_max=200) == 0


# --- usage credit, the managed-key tier, and bring-your-own ----------------------


class TestOwnKeys:
    """Free may not connect its own vendor keys; every paid plan may.

    The asymmetry is deliberate and reverses shipped behaviour - see the ladder
    comment in `domain/plans.py`. A test that only proved refusal would pass just
    as well if the gate had been applied to everyone, so the permit case is
    asserted too.
    """

    def test_free_may_not_bring_its_own_keys(self) -> None:
        verdict = check_own_keys_allowed(
            entitlements=_with(may_bring_own_keys=False), plan_name="Free"
        )
        assert not verdict.allowed
        assert "Free" in verdict.reason
        assert "Billing" in verdict.reason

    def test_a_paid_plan_may(self) -> None:
        assert check_own_keys_allowed(
            entitlements=_with(may_bring_own_keys=True), plan_name="Starter"
        ).allowed


class TestManagedTier:
    """What a plan may run on *CallFlow's* keys. Own-key legs never reach here -
    what a customer pays their own vendor is not ours to have an opinion on."""

    def test_free_may_run_economy_on_our_keys(self) -> None:
        assert check_managed_tier_allowed(
            entitlements=_with(max_managed_tier="economy"),
            plan_name="Free",
            tier="economy",
            leg_label="voice",
        ).allowed

    def test_free_may_not_run_premium_on_our_keys(self) -> None:
        verdict = check_managed_tier_allowed(
            entitlements=_with(max_managed_tier="economy"),
            plan_name="Free",
            tier="premium",
            leg_label="voice",
        )
        assert not verdict.allowed
        # Names the way out that does not cost money, because on a paid plan it
        # is genuinely available.
        assert "your own key" in verdict.reason

    def test_a_premium_plan_may_run_every_tier(self) -> None:
        for tier in ("economy", "standard", "premium"):
            assert check_managed_tier_allowed(
                entitlements=_with(max_managed_tier="premium"),
                plan_name="Growth",
                tier=tier,
                leg_label="voice",
            ).allowed

    def test_an_unrecognised_tier_refuses(self) -> None:
        """Fail closed. `domain/rates.py` bills an untiered provider at premium, so
        permitting it here would let Free run the most expensive pipeline for Rs 100."""
        assert not check_managed_tier_allowed(
            entitlements=_with(max_managed_tier="economy"),
            plan_name="Free",
            tier="platinum",
            leg_label="voice",
        ).allowed

    def test_an_unrecognised_plan_ceiling_refuses(self) -> None:
        """A hand-edited `max_managed_tier` must not become permissive."""
        assert not check_managed_tier_allowed(
            entitlements=_with(max_managed_tier="whatever"),
            plan_name="Free",
            tier="economy",
            leg_label="voice",
        ).allowed


class TestCreditAvailable:
    def test_credit_remaining_allows(self) -> None:
        assert check_credit_available(balance_paise=1, plan_name="Starter").allowed

    def test_spent_credit_refuses_and_names_the_top_up(self) -> None:
        verdict = check_credit_available(balance_paise=0, plan_name="Starter")
        assert not verdict.allowed
        assert "Top up" in verdict.reason

    def test_a_negative_balance_refuses(self) -> None:
        """Reachable, and normal: a call that overran its hold settles for more
        than was reserved rather than being cut off mid-sentence. The *next* call
        is the one that stops."""
        assert not check_credit_available(balance_paise=-500, plan_name="Starter").allowed

    def test_an_unreadable_balance_refuses(self) -> None:
        """The fail-closed case that matters most. A credit check that cannot
        complete must deny, or an outage becomes free calling (CLAUDE.md §4 #2)."""
        verdict = check_credit_available(balance_paise=None, plan_name="Starter")
        assert not verdict.allowed
        assert "couldn't be checked" in verdict.reason


class TestMemberCreditCap:
    """The same no-row-versus-zero-row distinction `get_enforced_ceiling()`
    established, now in money."""

    def test_no_cap_is_ungated(self) -> None:
        assert check_member_credit_cap(
            cap_paise=None, spent_paise=10_000_000, plan_name="Growth"
        ).allowed

    def test_a_cap_of_zero_blocks_entirely(self) -> None:
        verdict = check_member_credit_cap(cap_paise=0, spent_paise=0, plan_name="Growth")
        assert not verdict.allowed
        assert "no usage credit allocated" in verdict.reason

    def test_under_the_cap_allows(self) -> None:
        assert check_member_credit_cap(
            cap_paise=5_000, spent_paise=4_999, plan_name="Growth"
        ).allowed

    def test_at_the_cap_refuses(self) -> None:
        verdict = check_member_credit_cap(
            cap_paise=5_000, spent_paise=5_000, plan_name="Growth"
        )
        assert not verdict.allowed
        assert "your share" in verdict.reason


# --- which agents survive a downgrade -------------------------------------------


def _agent(name: str, day: int, kept: int | None = None) -> AgentStanding:
    return AgentStanding(
        agent_id=name,
        created_at=datetime(2026, 8, day, tzinfo=UTC),
        kept_at=datetime(2026, 9, kept, tzinfo=UTC) if kept else None,
    )


class TestUsableAgents:
    """Locking the excess is what stops the limit being a one-time toll: without
    it you subscribe for a month, create ten agents, downgrade, and keep all ten."""

    def test_unlimited_keeps_everything(self) -> None:
        agents = [_agent("a", 1), _agent("b", 2)]
        assert usable_agent_ids(agents, limit=None) == {"a", "b"}

    def test_under_the_limit_keeps_everything(self) -> None:
        agents = [_agent("a", 1), _agent("b", 2)]
        assert usable_agent_ids(agents, limit=5) == {"a", "b"}

    def test_the_default_is_oldest_first(self) -> None:
        """The agent built on day one is the likeliest to be the one doing the
        work. Newest-first would lock it in favour of one made minutes ago."""
        agents = [_agent("newest", 18), _agent("oldest", 12), _agent("middle", 14)]
        assert usable_agent_ids(agents, limit=1) == {"oldest"}

    def test_an_explicit_choice_beats_age(self) -> None:
        """The whole reason `kept_at` exists - only the customer knows which agent
        matters, and the age default is a guess."""
        agents = [_agent("oldest", 12), _agent("chosen", 18, kept=1)]
        assert usable_agent_ids(agents, limit=1) == {"chosen"}

    def test_the_most_recent_choice_wins_when_several_are_kept(self) -> None:
        """Marking a third agent on a one-agent plan must activate it, not be
        silently ignored because two were already marked."""
        agents = [_agent("first", 12, kept=1), _agent("second", 14, kept=5)]
        assert usable_agent_ids(agents, limit=1) == {"second"}

    def test_kept_agents_fill_the_allowance_before_unkept_ones(self) -> None:
        agents = [_agent("old", 1), _agent("kept", 20, kept=2), _agent("mid", 10)]
        assert usable_agent_ids(agents, limit=2) == {"kept", "old"}

    def test_a_limit_of_zero_locks_everything(self) -> None:
        """A real, enforced value - an organisation whose plan includes no agents
        has none it may use. Not an edge to round away to one."""
        assert usable_agent_ids([_agent("a", 1)], limit=0) == frozenset()

    def test_no_agents_is_not_an_error(self) -> None:
        assert usable_agent_ids([], limit=1) == frozenset()


class TestAgentUsableVerdict:
    def test_a_usable_agent_is_allowed(self) -> None:
        assert check_agent_usable(
            agent_id="a", usable=frozenset({"a"}), plan_name="Free", limit=1
        ).allowed

    def test_a_locked_agent_names_both_ways_out(self) -> None:
        """Upgrading is not the only remedy - they can make this agent the active
        one instead, and a refusal that hides the free option is a sales pitch."""
        verdict = check_agent_usable(
            agent_id="b", usable=frozenset({"a"}), plan_name="Free", limit=1
        )
        assert not verdict.allowed
        assert "Billing" in verdict.reason
        assert "make this one active" in verdict.reason

    def test_a_plan_with_no_agents_says_so_rather_than_counting(self) -> None:
        verdict = check_agent_usable(
            agent_id="a", usable=frozenset(), plan_name="Free", limit=0
        )
        assert not verdict.allowed
        assert "does not include voice agents" in verdict.reason
