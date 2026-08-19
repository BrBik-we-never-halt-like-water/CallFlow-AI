"""The plan gate: at, under and over each ceiling.

Pure - no database, so this runs in CI. What these do *not* prove is that the
same limits hold against raw SQL: `insert` is granted straight to
`authenticated` on the tables involved, so the SQL-side guards are covered by
`test_entitlement_enforcement.py` instead.
"""

from __future__ import annotations

import dataclasses

from app.domain.entitlements import (
    check_agent_create_allowed,
    check_ai_integration_allowed,
    check_org_create_allowed,
    check_seat_available,
    effective_daily_call_budget,
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


def test_an_organisation_may_pace_itself_below_its_plan() -> None:
    """Settings → Safety exists for exactly this: a customer choosing to go slower
    than they pay for."""
    assert effective_daily_call_budget(org_override=50, plan_max=200) == 50


def test_an_organisation_cannot_raise_itself_above_its_plan() -> None:
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
