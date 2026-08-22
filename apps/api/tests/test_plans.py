"""The entitlement catalogue and how an override resolves against it.

Pure - no database, so this runs in CI. The companion assertion that the seeded
`plan_entitlements` rows match `_LADDER` needs a database and lives in
`test_entitlement_enforcement.py`; a drift between the two disables either the
API check or the SQL guard silently.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.domain.plans import (
    OVERRIDABLE,
    Entitlements,
    PlanId,
    UnknownOverrideKey,
    entitlements_for,
    ladder,
)


def test_plan_ids_match_the_frontend_and_the_check_constraint() -> None:
    """`PlanId` here, `PlanId` in `apps/web/lib/pricing.ts`, and
    `organisations_plan_id_check` are one value space in three places."""
    assert {p.value for p in PlanId} == {"free", "starter", "growth", "enterprise"}


def test_every_plan_has_seeded_entitlements() -> None:
    assert set(ladder()) == set(PlanId)


def test_the_ladder_is_not_mutable_through_the_accessor() -> None:
    """A caller holding the catalogue must not be able to edit the plan every
    other request resolves against."""
    with pytest.raises(TypeError):
        ladder()[PlanId.FREE] = Entitlements(  # type: ignore[index]
            max_voice_agents=999,
            max_seats=999,
            max_organisations=999,
            max_ai_integrations=999,
            daily_call_budget=999,
            llm_spend_limit_usd=999.0,
        )


@pytest.mark.parametrize(
    "smaller,larger",
    [(PlanId.FREE, PlanId.STARTER), (PlanId.STARTER, PlanId.GROWTH)],
)
def test_the_ladder_never_goes_backwards(smaller: PlanId, larger: PlanId) -> None:
    """Paying more must never buy less. `None` is unlimited, so it wins any
    comparison rather than reading as zero."""
    lo, hi = ladder()[smaller], ladder()[larger]
    for field in dataclasses.fields(Entitlements):
        low, high = getattr(lo, field.name), getattr(hi, field.name)
        if high is None:
            continue
        assert low is not None, f"{field.name}: {smaller.value} unlimited but {larger.value} is not"
        assert low <= high, f"{field.name} shrinks from {smaller.value} to {larger.value}"


def test_free_can_place_calls() -> None:
    """Telephony is unlimited on every plan and Free has a real daily budget, so
    Free dials. `pricing.ts`'s "prove the pipeline" tagline depends on it."""
    free = entitlements_for("free")
    assert free.daily_call_budget is not None and free.daily_call_budget > 0


def test_free_can_connect_at_least_one_model_provider() -> None:
    """A call needs an org-supplied STT and TTS key and there is no CallFlow-owned
    fallback, so a Free allowance of zero would silently make Free undialable."""
    assert (entitlements_for("free").max_ai_integrations or 0) >= 1


def test_enterprise_is_seeded_as_a_floor_not_a_blank() -> None:
    """Between "deal signed" and "override written" an enterprise organisation
    must be generous, never unlimited."""
    enterprise = entitlements_for("enterprise")
    assert enterprise.max_voice_agents is not None
    assert enterprise.daily_call_budget is not None


@pytest.mark.parametrize("unknown", ["", "scale", "Growth", "GROWTH", "premium", "free "])
def test_an_unrecognised_plan_falls_back_to_free(unknown: str) -> None:
    """`organisations.plan_id` is free text, so a hand-edited or half-migrated
    value must land on the smallest entitlement - CLAUDE.md §4 #2, fail closed.
    `scale` is in this list on purpose: it was a real plan id before the rename."""
    assert entitlements_for(unknown) == entitlements_for("free")


def test_a_known_plan_resolves_to_its_own_row() -> None:
    assert entitlements_for("growth") == ladder()[PlanId.GROWTH]


# --- overrides: the enterprise tier ---


def test_an_override_replaces_only_the_keys_it_names() -> None:
    resolved = entitlements_for("enterprise", {"max_seats": 250})
    base = ladder()[PlanId.ENTERPRISE]

    assert resolved.max_seats == 250
    assert resolved.max_voice_agents == base.max_voice_agents
    assert resolved.daily_call_budget == base.daily_call_budget


def test_an_override_can_grant_unlimited() -> None:
    """The reason `override` is a mapping and not a dataclass of optional fields:
    presence is what overrides, so `None` here means unlimited. With optional
    fields, `None` would have to mean "inherit" and "unlimited" at once."""
    assert entitlements_for("enterprise", {"max_seats": None}).max_seats is None


def test_omitting_a_key_inherits_rather_than_unlimiting() -> None:
    assert entitlements_for("enterprise", {}).max_seats == ladder()[PlanId.ENTERPRISE].max_seats


def test_an_override_of_zero_is_enforced_not_ignored() -> None:
    """`0` and `None` must stay distinguishable end to end - the same distinction
    `credits_repo.get_enforced_ceiling()` depends on."""
    assert entitlements_for("enterprise", {"max_voice_agents": 0}).max_voice_agents == 0


def test_an_override_can_apply_to_any_plan_not_just_enterprise() -> None:
    """Nothing in the resolver ties overrides to one tier, so a support grant to
    a customer mid-incident works without moving them to enterprise first."""
    assert entitlements_for("free", {"daily_call_budget": 500}).daily_call_budget == 500


def test_an_unknown_override_key_raises_rather_than_being_dropped() -> None:
    """A typo that resolved silently would read as a limit that had been raised
    while the real ceiling stayed put."""
    with pytest.raises(UnknownOverrideKey) as caught:
        entitlements_for("enterprise", {"max_agents": 50})

    message = str(caught.value)
    assert "max_agents" in message
    # Names the valid alternatives rather than just refusing (CLAUDE.md §5).
    assert "max_voice_agents" in message


def test_overridable_is_exactly_the_entitlement_fields() -> None:
    """Adding a limit to `Entitlements` must make it overridable automatically,
    or an enterprise deal cannot negotiate the newest thing the product sells."""
    assert OVERRIDABLE == {f.name for f in dataclasses.fields(Entitlements)}


def test_telephony_is_not_an_entitlement() -> None:
    """Deliberately absent: a bring-your-own carrier costs CallFlow nothing, so
    capping it is friction with no saving behind it (docs/BILLING.md §1). If this
    fails, someone re-added it - check that reasoning still holds first."""
    assert not any("telephony" in name for name in OVERRIDABLE)
