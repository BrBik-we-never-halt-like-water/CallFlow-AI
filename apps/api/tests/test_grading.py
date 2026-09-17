"""Acceptance tests for `grade_lead()` - the worked examples and precedence
cases from `docs/GRADING.md` §4-§5. Every test fixes `now` explicitly so
`intake_month` comparisons stay correct regardless of when this suite runs.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.entities import CallResult, DeclineReason, LeadGrade, NextAction
from app.domain.grading import GradingConfig, grade_lead

NOW = datetime(2026, 9, 17, tzinfo=UTC)


def _months_from_now(months: int) -> str:
    month_index = NOW.month - 1 + months
    year = NOW.year + month_index // 12
    month = month_index % 12 + 1
    return datetime(year, month, 1, tzinfo=UTC).strftime("%B %Y")


def grade(result: CallResult, fields: dict, config: GradingConfig | None = None):
    return grade_lead(result, fields, config or GradingConfig(), now=NOW)


# ---------------------------------------------------------------------------
# §1 / rule 0 - reachability has no grade.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "result,expected_action",
    [
        (CallResult.NO_ANSWER, NextAction.CALL_NOW),
        (CallResult.BUSY, NextAction.CALL_NOW),
        (CallResult.VOICEMAIL, NextAction.NURTURE),
        (CallResult.INVALID_NUMBER, NextAction.FIX_DATA),
        (CallResult.FAILED, NextAction.FIX_DATA),
        (CallResult.SUPPRESSED, NextAction.SUPPRESS),
    ],
)
def test_unreachable_results_carry_no_grade(result, expected_action):
    outcome = grade(result, {})
    assert outcome.grade is None
    assert outcome.next_action == expected_action


def test_unreachable_is_never_silently_cold():
    # The precise thing §1 forbids: an unreachable number reading as a
    # rejection would poison the decline report.
    outcome = grade(CallResult.NO_ANSWER, {"decline_reason": None})
    assert outcome.grade is not LeadGrade.COLD
    assert outcome.grade is None


# ---------------------------------------------------------------------------
# §5 worked examples, two per grade.
# ---------------------------------------------------------------------------


def test_h1_hot_named_budget():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "yes",
            "intake_month": _months_from_now(6),
            "budget_stated": True,
            "budget_amount_paise": 120_000_000,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
    )
    assert outcome.grade is LeadGrade.HOT
    assert outcome.next_action is NextAction.CALL_NOW


def test_h2_hot_emi_accepted_no_budget_named():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "yes",
            "intake_month": _months_from_now(4),
            "budget_stated": False,
            "emi_needed": True,
            "emi_accepted": True,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
    )
    assert outcome.grade is LeadGrade.HOT


def test_w1_warm_no_intake_picked():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "yes",
            "intake_month": None,
            "budget_stated": True,
            "budget_amount_paise": 500_000,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
    )
    assert outcome.grade is LeadGrade.WARM
    assert outcome.next_action is NextAction.CALL_NOW


def test_w2_warm_maybe_with_callback():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "maybe",
            "callback_at": "2026-09-20T18:30+05:30",
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
    )
    assert outcome.grade is LeadGrade.WARM
    assert outcome.next_action is NextAction.CALL_AT


def test_maybe_without_callback_still_call_now():
    outcome = grade(
        CallResult.SPOKE,
        {"intent": "maybe", "is_decision_maker": True, "identity_confirmed": True},
    )
    assert outcome.grade is LeadGrade.WARM
    assert outcome.next_action is NextAction.CALL_NOW


def test_c1_cold_no_time():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "no",
            "intent_explicit_no": False,
            "is_decision_maker": True,
            "identity_confirmed": True,
            "decline_reason": DeclineReason.NO_TIME.value,
        },
    )
    assert outcome.grade is LeadGrade.COLD
    assert outcome.next_action is NextAction.NURTURE
    assert outcome.decline_reason is DeclineReason.NO_TIME


def test_c2_cold_wrong_programme():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "no",
            "intent_explicit_no": False,
            "decline_reason": DeclineReason.WRONG_PROGRAMME.value,
            "decline_note": "wanted a data science diploma, not an MBA",
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
    )
    assert outcome.grade is LeadGrade.COLD


def test_r1_refused_do_not_contact_suppresses():
    outcome = grade(
        CallResult.SPOKE,
        {"do_not_contact": True, "decline_reason": DeclineReason.DO_NOT_CONTACT.value},
    )
    assert outcome.grade is LeadGrade.REFUSED
    assert outcome.next_action is NextAction.SUPPRESS
    assert outcome.decline_reason is DeclineReason.DO_NOT_CONTACT


def test_r2_refused_already_enrolled_drops_not_suppresses():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "no",
            "intent_explicit_no": True,
            "already_enrolled": True,
            "competitor_named": "Amity",
            "decline_reason": DeclineReason.ALREADY_ENROLLED_ELSEWHERE.value,
        },
    )
    assert outcome.grade is LeadGrade.REFUSED
    assert outcome.next_action is NextAction.DROP


def test_p1_wrong_person_identity_not_confirmed():
    outcome = grade(
        CallResult.SPOKE,
        {"identity_confirmed": False, "is_decision_maker": False},
    )
    assert outcome.grade is LeadGrade.WRONG_PERSON
    assert outcome.next_action is NextAction.FIX_DATA


def test_p2_wrong_person_employer_decides():
    outcome = grade(
        CallResult.SPOKE,
        {
            "identity_confirmed": True,
            "is_decision_maker": False,
            "employer_sponsored": True,
            "intent": "yes",
        },
    )
    assert outcome.grade is LeadGrade.WRONG_PERSON


def test_u1_ungraded_extraction_errored():
    outcome = grade(CallResult.SPOKE, {"extraction_errored": True})
    assert outcome.grade is LeadGrade.UNGRADED
    assert outcome.grade is not LeadGrade.COLD


def test_u1b_precedence_do_not_contact_beats_extraction_error():
    # The precedence case docs/GRADING.md calls out by name: rule 1 must fire
    # before rule 4, or a person who opted out gets routed to a re-dial queue.
    outcome = grade(
        CallResult.SPOKE,
        {"do_not_contact": True, "extraction_errored": True},
    )
    assert outcome.grade is LeadGrade.REFUSED
    assert outcome.next_action is NextAction.SUPPRESS


def test_u2_ungraded_required_field_missing():
    outcome = grade(
        CallResult.SPOKE,
        {"intent": "unknown", "is_decision_maker": None, "identity_confirmed": True},
    )
    assert outcome.grade is LeadGrade.UNGRADED
    assert outcome.next_action is NextAction.FIX_DATA


# ---------------------------------------------------------------------------
# §4.2 precedence notes, tested by name.
# ---------------------------------------------------------------------------


def test_hostile_beats_a_stated_budget():
    # "A hostile contact who also stated a budget is REFUSED, not HOT."
    outcome = grade(
        CallResult.SPOKE,
        {
            "hostile": True,
            "intent": "yes",
            "intake_month": _months_from_now(1),
            "budget_stated": True,
            "budget_amount_paise": 999_999_999,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
    )
    assert outcome.grade is LeadGrade.REFUSED
    assert outcome.next_action is NextAction.SUPPRESS


def test_is_false_not_falsy_missing_field_is_ungraded_not_wrong_person():
    # A null (never asked) must not be treated as False (asked, said no).
    outcome = grade(
        CallResult.SPOKE,
        {"intent": "yes", "is_decision_maker": None, "identity_confirmed": True},
    )
    assert outcome.grade is LeadGrade.UNGRADED
    assert outcome.grade is not LeadGrade.WRONG_PERSON


def test_intent_unknown_is_ungraded_not_cold():
    outcome = grade(
        CallResult.SPOKE,
        {"intent": "unknown", "is_decision_maker": True, "identity_confirmed": True},
    )
    assert outcome.grade is LeadGrade.UNGRADED
    assert outcome.grade is not LeadGrade.COLD


def test_yes_with_both_intake_and_money_missing_is_warm_not_cold():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "yes",
            "intake_month": None,
            "budget_stated": False,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
    )
    assert outcome.grade is LeadGrade.WARM


def test_still_deciding_reaches_warm_through_intent_not_reason():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "maybe",
            "decline_reason": DeclineReason.STILL_DECIDING.value,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
    )
    assert outcome.grade is LeadGrade.WARM


def test_still_deciding_reason_with_intent_no_is_cold_not_warm():
    # The reason never overrides the grade - a mismatched extraction is a
    # data problem, not a reason to trust the enum over intent.
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "no",
            "intent_explicit_no": False,
            "decline_reason": DeclineReason.STILL_DECIDING.value,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
    )
    assert outcome.grade is LeadGrade.COLD


def test_intake_outside_the_horizon_is_warm_not_hot():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "yes",
            "intake_month": _months_from_now(18),
            "budget_stated": True,
            "budget_amount_paise": 100_000,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
        GradingConfig(intake_horizon_months=12),
    )
    assert outcome.grade is LeadGrade.WARM


def test_intake_month_that_does_not_parse_fails_closed_to_warm():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "yes",
            "intake_month": "sometime next year",
            "budget_stated": True,
            "budget_amount_paise": 100_000,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
    )
    assert outcome.grade is LeadGrade.WARM


def test_budget_floor_not_cleared_is_warm():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "yes",
            "intake_month": _months_from_now(1),
            "budget_stated": True,
            "budget_amount_paise": 10_000,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
        GradingConfig(budget_floor_paise=1_000_000),
    )
    assert outcome.grade is LeadGrade.WARM


def test_budget_floor_cleared_is_hot():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "yes",
            "intake_month": _months_from_now(1),
            "budget_stated": True,
            "budget_amount_paise": 2_000_000,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
        GradingConfig(budget_floor_paise=1_000_000),
    )
    assert outcome.grade is LeadGrade.HOT


def test_stated_budget_with_no_amount_clears_an_unset_floor():
    # "The amount is never compared when it is null" - a null floor, not a
    # null amount alongside a real floor.
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "yes",
            "intake_month": _months_from_now(1),
            "budget_stated": True,
            "budget_amount_paise": None,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
        GradingConfig(budget_floor_paise=None),
    )
    assert outcome.grade is LeadGrade.HOT


def test_stated_budget_with_no_amount_does_not_clear_a_real_floor():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "yes",
            "intake_month": _months_from_now(1),
            "budget_stated": True,
            "budget_amount_paise": None,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
        GradingConfig(budget_floor_paise=1_000_000),
    )
    assert outcome.grade is LeadGrade.WARM


def test_emi_qualifies_alone_disabled_falls_back_to_budget():
    outcome = grade(
        CallResult.SPOKE,
        {
            "intent": "yes",
            "intake_month": _months_from_now(1),
            "budget_stated": False,
            "emi_needed": True,
            "emi_accepted": True,
            "is_decision_maker": True,
            "identity_confirmed": True,
        },
        GradingConfig(emi_qualifies_alone=False),
    )
    assert outcome.grade is LeadGrade.WARM


# ---------------------------------------------------------------------------
# Configuration: the required-fields floor.
# ---------------------------------------------------------------------------


def test_intent_cannot_be_removed_from_required_fields():
    config = GradingConfig(required_fields=["is_decision_maker", "identity_confirmed"])
    assert "intent" in config.required_fields


def test_dropping_is_decision_maker_from_required_still_lets_rule_3_read_it():
    # Removing a field from required_fields means a null there no longer
    # blocks the grade (rule 4) - but rule 3 still reads an explicit False.
    config = GradingConfig(required_fields=["intent"])
    outcome = grade(
        CallResult.SPOKE,
        {"intent": "yes", "is_decision_maker": False, "identity_confirmed": None},
        config,
    )
    assert outcome.grade is LeadGrade.WRONG_PERSON
