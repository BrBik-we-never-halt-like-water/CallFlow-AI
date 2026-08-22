"""What a minute costs, and what a call therefore spends.

Pure arithmetic, so these run in CI with no database. The cases that matter are
not "does addition work" but the three places this could quietly lose or invent
money: an untiered provider, a leg on the customer's own key, and rounding.
"""

from __future__ import annotations

import pytest

from app.domain.rates import (
    UNKNOWN_PROVIDER_TIER,
    CallRate,
    Leg,
    LegUsage,
    PipelineTier,
    RateCard,
    estimated_minutes,
    reserve_for,
    resolve_rate,
    spend_for,
)

PLATFORM_FEE = 150

# The proposal's placeholder card (`docs/PRICING_DECISIONS.md` §3), in paise.
CARD = RateCard(
    platform_fee=PLATFORM_FEE,
    add_ons={
        (Leg.STT, PipelineTier.ECONOMY): 35,
        (Leg.STT, PipelineTier.STANDARD): 100,
        (Leg.STT, PipelineTier.PREMIUM): 205,
        (Leg.LLM, PipelineTier.ECONOMY): 7,
        (Leg.LLM, PipelineTier.STANDARD): 35,
        (Leg.LLM, PipelineTier.PREMIUM): 460,
        (Leg.TTS, PipelineTier.ECONOMY): 210,
        (Leg.TTS, PipelineTier.STANDARD): 365,
        (Leg.TTS, PipelineTier.PREMIUM): 1075,
    },
)


def _legs(*specs: tuple[Leg, PipelineTier, bool]) -> tuple[LegUsage, ...]:
    return tuple(LegUsage(leg=leg, tier=tier, on_platform_key=ours) for leg, tier, ours in specs)


# --- own keys cost the platform fee and nothing else -----------------------------


def test_a_pipeline_entirely_on_the_customers_keys_is_the_platform_fee_exactly() -> None:
    """The whole argument for the model. If this ever picks up an add-on, a
    bring-your-own customer is being charged for a vendor we did not pay."""
    rate = resolve_rate(
        CARD,
        _legs(
            (Leg.STT, PipelineTier.PREMIUM, False),
            (Leg.LLM, PipelineTier.PREMIUM, False),
            (Leg.TTS, PipelineTier.PREMIUM, False),
        ),
    )
    assert rate.paise_per_minute == PLATFORM_FEE
    assert rate.per_leg == {}
    assert rate.billed_legs == ()


def test_the_tier_of_an_own_key_leg_is_irrelevant() -> None:
    """A customer's own premium key must cost exactly what their own economy key
    costs, because both cost CallFlow nothing."""
    premium = resolve_rate(CARD, _legs((Leg.TTS, PipelineTier.PREMIUM, False)))
    economy = resolve_rate(CARD, _legs((Leg.TTS, PipelineTier.ECONOMY, False)))
    assert premium.paise_per_minute == economy.paise_per_minute == PLATFORM_FEE


# --- mixing, which is the normal case --------------------------------------------


def test_only_the_legs_on_our_keys_are_billed() -> None:
    """Own STT and LLM, our premium TTS - the example from the pricing doc."""
    rate = resolve_rate(
        CARD,
        _legs(
            (Leg.STT, PipelineTier.STANDARD, False),
            (Leg.LLM, PipelineTier.STANDARD, False),
            (Leg.TTS, PipelineTier.PREMIUM, True),
        ),
    )
    assert rate.paise_per_minute == PLATFORM_FEE + 1075
    assert rate.billed_legs == (Leg.TTS,)


def test_a_fully_managed_standard_pipeline_matches_the_published_card() -> None:
    rate = resolve_rate(
        CARD,
        _legs(
            (Leg.STT, PipelineTier.STANDARD, True),
            (Leg.LLM, PipelineTier.STANDARD, True),
            (Leg.TTS, PipelineTier.STANDARD, True),
        ),
    )
    # Rs 1.50 + 1.00 + 0.35 + 3.65 = Rs 6.50, the doc's worked example.
    assert rate.paise_per_minute == 650


def test_a_leg_that_did_not_run_is_not_billed() -> None:
    """A pipeline with no TTS is a real configuration. Charging for a leg that
    never ran would be charging for nothing."""
    rate = resolve_rate(
        CARD,
        _legs(
            (Leg.STT, PipelineTier.ECONOMY, True),
            (Leg.LLM, PipelineTier.ECONOMY, True),
        ),
    )
    assert rate.paise_per_minute == PLATFORM_FEE + 35 + 7
    assert Leg.TTS not in rate.per_leg


# --- fail closed -----------------------------------------------------------------


def test_an_untiered_provider_bills_at_premium_not_free() -> None:
    """The fail-closed direction. A provider nobody tiered must be the most
    expensive guess, never the cheapest - otherwise forgetting to tier a new
    vendor is a silent discount, and a discount nobody decided is a cost nobody
    notices."""
    assert UNKNOWN_PROVIDER_TIER is PipelineTier.PREMIUM
    assert CARD.add_on_for(Leg.TTS, UNKNOWN_PROVIDER_TIER) == 1075


def test_a_half_seeded_card_falls_back_to_its_own_premium_row() -> None:
    """A card missing the economy row must not bill economy calls at zero."""
    partial = RateCard(
        platform_fee=PLATFORM_FEE,
        add_ons={(Leg.TTS, PipelineTier.PREMIUM): 1075},
    )
    assert partial.add_on_for(Leg.TTS, PipelineTier.ECONOMY) == 1075


def test_a_completely_empty_card_bills_only_the_platform_fee() -> None:
    """Not a silent zero-rate call: the platform fee still applies, so an
    unseeded card under-charges rather than giving the product away."""
    empty = RateCard(platform_fee=PLATFORM_FEE, add_ons={})
    rate = resolve_rate(empty, _legs((Leg.TTS, PipelineTier.PREMIUM, True)))
    assert rate.paise_per_minute == PLATFORM_FEE


# --- what a call actually spends -------------------------------------------------


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (60, 650),  # exactly a minute at Rs 6.50
        (30, 325),  # half a minute, exact
        (240, 2600),  # the doc's 4-minute call: Rs 26
        (8, 87),  # a voicemail: 86.67 paise, rounded half-up
        (1, 11),  # 10.83 paise
    ],
)
def test_spend_is_prorated_by_the_second(seconds: int, expected: int) -> None:
    """Prorated, not rounded up to a whole minute. Outbound work is full of short
    calls, and billing an 8-second voicemail as a minute is arithmetic a customer
    notices."""
    rate = CallRate(paise_per_minute=650, platform_fee=PLATFORM_FEE, per_leg={})
    assert spend_for(rate, seconds) == expected


def test_spend_is_always_an_integer_number_of_paise() -> None:
    """`duration_seconds` is a Float column, so a float reaches this function -
    and must stop here. Nothing downstream of the ledger may see one
    (CLAUDE.md §4 #3)."""
    rate = CallRate(paise_per_minute=650, platform_fee=PLATFORM_FEE, per_leg={})
    result = spend_for(rate, 37.4)
    assert isinstance(result, int)
    assert result == 405


@pytest.mark.parametrize("duration", [None, 0, -1, -900.0])
def test_a_call_that_never_connected_costs_nothing(duration: float | None) -> None:
    """`None` is a call that never reported a duration. A negative is a clock
    going backwards, and must not become a *credit*."""
    rate = CallRate(paise_per_minute=650, platform_fee=PLATFORM_FEE, per_leg={})
    assert spend_for(rate, duration) == 0


# --- the hold --------------------------------------------------------------------


def test_the_reserve_is_a_typical_call_not_the_carrier_ceiling() -> None:
    """Holding the 900-second ceiling at a premium rate would let a month's credit
    support only a handful of concurrent calls - the pool would be exhausted by
    calls that had not happened."""
    rate = resolve_rate(
        CARD,
        _legs(
            (Leg.STT, PipelineTier.PREMIUM, True),
            (Leg.LLM, PipelineTier.PREMIUM, True),
            (Leg.TTS, PipelineTier.PREMIUM, True),
        ),
    )
    typical = reserve_for(rate, 180)
    ceiling = reserve_for(rate, 900)
    assert typical * 5 == ceiling

    # Growth's Rs 4,250 of credit, against an all-premium managed pipeline at
    # Rs 18.90/min. Holding a 3-minute typical call leaves room for 74 calls in
    # flight; holding the 15-minute carrier ceiling leaves 14 - and the other 60
    # are refused for credit that is not being spent.
    growth_credit = 425_000
    assert growth_credit // typical == 74
    assert growth_credit // ceiling == 14


def test_a_reserve_never_goes_negative() -> None:
    rate = CallRate(paise_per_minute=650, platform_fee=PLATFORM_FEE, per_leg={})
    assert reserve_for(rate, -60) == 0


# --- the minutes estimate --------------------------------------------------------


def test_the_same_balance_is_worth_very_different_minutes() -> None:
    """Why money is the headline unit and minutes are only an estimate: the same
    Rs 8.50 buys 5.6x more talking on own keys than on a managed premium
    pipeline."""
    balance = 85_000
    byo = resolve_rate(CARD, _legs((Leg.TTS, PipelineTier.PREMIUM, False)))
    managed = resolve_rate(
        CARD,
        _legs(
            (Leg.STT, PipelineTier.STANDARD, True),
            (Leg.LLM, PipelineTier.STANDARD, True),
            (Leg.TTS, PipelineTier.STANDARD, True),
        ),
    )
    assert estimated_minutes(balance, byo) == 566
    assert estimated_minutes(balance, managed) == 130


@pytest.mark.parametrize("balance", [0, -1, -85_000])
def test_a_spent_or_negative_balance_estimates_no_minutes(balance: int) -> None:
    """A negative balance is reachable - a call that overran its hold settles for
    more than was reserved. It must read as zero, never as a huge number from an
    unguarded division."""
    rate = CallRate(paise_per_minute=650, platform_fee=PLATFORM_FEE, per_leg={})
    assert estimated_minutes(balance, rate) == 0


def test_a_zero_rate_estimates_no_minutes_rather_than_dividing_by_zero() -> None:
    rate = CallRate(paise_per_minute=0, platform_fee=0, per_leg={})
    assert estimated_minutes(85_000, rate) == 0
