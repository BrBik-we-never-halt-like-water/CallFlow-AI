"""Grade a resolved call: is this lead worth a human's time, and what do they do next.

Source of truth: `docs/GRADING.md`. Code disagreeing with that document is a bug
in the code, until the Sunday sync says otherwise.

Pure function, no I/O, no vendor, no database - the same standard `safety.py`,
`triage.py` and `collection.py` already hold (CLAUDE.md §3-S), and the reason
this can be tested against a dict instead of a transcript.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.entities import CallResult, DeclineReason, LeadGrade, NextAction

#: A floor on `GradingConfig.required_fields`, not a default: `docs/GRADING.md`
#: §7 constraint 1 says this field cannot be removed, because doing so would
#: stop rule 4 from ever firing and every unreadable call would fall through
#: to rule 9 - survivable, but silently the wrong reason.
_REQUIRED_FLOOR = "intent"

_DEFAULT_REQUIRED_FIELDS = ["intent", "is_decision_maker", "identity_confirmed"]


class GradingConfig(BaseModel):
    """Per-organisation thresholds. Defaults match `docs/GRADING.md` §7."""

    budget_floor_paise: int | None = None
    required_fields: list[str] = Field(default_factory=lambda: list(_DEFAULT_REQUIRED_FIELDS))
    intake_horizon_months: int = 12
    emi_qualifies_alone: bool = True

    def model_post_init(self, _context: Any) -> None:
        if _REQUIRED_FLOOR not in self.required_fields:
            self.required_fields = [*self.required_fields, _REQUIRED_FLOOR]


class GradeOutcome(BaseModel):
    """`grade` is nullable; `next_action` is not - an unreachable row still
    has to tell a human what to do with it (`docs/GRADING.md` §4)."""

    grade: LeadGrade | None
    grade_reason: str
    next_action: NextAction
    decline_reason: DeclineReason | None = None


# docs/GRADING.md §4.1a - what an unreachable row gets instead of a grade.
_NEXT_ACTION_BY_RESULT: dict[CallResult, NextAction] = {
    CallResult.NO_ANSWER: NextAction.CALL_NOW,
    CallResult.BUSY: NextAction.CALL_NOW,
    CallResult.VOICEMAIL: NextAction.NURTURE,
    CallResult.INVALID_NUMBER: NextAction.FIX_DATA,
    CallResult.FAILED: NextAction.FIX_DATA,
    CallResult.SUPPRESSED: NextAction.SUPPRESS,
}

_NOT_REACHED_REASON: dict[CallResult, str] = {
    CallResult.NO_ANSWER: "Rang out - not yet spoken to.",
    CallResult.BUSY: "Line was busy - not yet spoken to.",
    CallResult.VOICEMAIL: "Reached voicemail, not a person.",
    CallResult.INVALID_NUMBER: "Not a dialable number.",
    CallResult.FAILED: "The call attempt did not complete.",
    CallResult.SUPPRESSED: "On the suppression list - never dialled.",
    CallResult.IN_FLIGHT: "Still in progress.",
}


def _join_human(names: list[str]) -> str:
    """"a", "a and b", "a, b and c" - the reason is read by a person."""
    readable = [name.replace("_", " ") for name in names]
    if len(readable) == 1:
        return readable[0]
    return ", ".join(readable[:-1]) + " and " + readable[-1]


def _intake_ok(intake_month: str | None, horizon_months: int, *, now: datetime) -> bool:
    """Whether `intake_month` falls inside the configured horizon.

    `intake_month` is collected as free-form "<Month> <Year>" prose (the
    worked examples in `docs/GRADING.md` §5 use e.g. "March 2027"). Parsed
    leniently - a format that doesn't parse fails this check rather than
    raising, since a caller naming an intake unusually should cost this lead
    HOT, not crash grading.
    """
    if not intake_month:
        return False
    parsed: datetime | None = None
    for fmt in ("%B %Y", "%b %Y"):
        try:
            parsed = datetime.strptime(intake_month.strip(), fmt).replace(tzinfo=UTC)
            break
        except ValueError:
            continue
    if parsed is None:
        return False

    months_out = (parsed.year - now.year) * 12 + (parsed.month - now.month)
    return 0 <= months_out <= horizon_months


def _money_ok(fields: dict[str, Any], config: GradingConfig) -> bool:
    """A stated budget clearing the floor, or accepted EMI when the org's
    config says EMI alone qualifies (`docs/GRADING.md` §4.1a)."""
    if config.emi_qualifies_alone and fields.get("emi_accepted"):
        return True
    if not fields.get("budget_stated"):
        return False
    floor = config.budget_floor_paise
    if floor is None:
        return True
    # The amount is never compared when it is null: a stated-but-unnamed
    # budget clears an unset floor, not a real one (`docs/GRADING.md` §4.1a).
    amount = fields.get("budget_amount_paise")
    return amount is not None and amount >= floor


def grade_lead(
    result: CallResult,
    fields: dict[str, Any],
    config: GradingConfig,
    *,
    now: datetime | None = None,
) -> GradeOutcome:
    """Assign a grade and next action per `docs/GRADING.md` §4.1.

    `now` only affects the `intake_ok` comparison; it defaults to the real
    clock for callers, and tests should pass it explicitly to stay
    deterministic regardless of when they run.
    """
    now = now or datetime.now(UTC)

    raw_decline_reason = fields.get("decline_reason")
    decline_reason = DeclineReason(raw_decline_reason) if raw_decline_reason else None

    # Rule 0: an unreachable call carries no grade, only a next_action.
    if result is not CallResult.SPOKE:
        return GradeOutcome(
            grade=None,
            grade_reason=_NOT_REACHED_REASON.get(result, "Not yet spoken to."),
            next_action=_NEXT_ACTION_BY_RESULT.get(result, NextAction.FIX_DATA),
            decline_reason=decline_reason,
        )

    do_not_contact = fields.get("do_not_contact")
    hostile = fields.get("hostile")
    intent = fields.get("intent")
    intent_explicit_no = fields.get("intent_explicit_no")
    identity_confirmed = fields.get("identity_confirmed")
    is_decision_maker = fields.get("is_decision_maker")
    extraction_errored = bool(fields.get("extraction_errored"))
    callback_at = fields.get("callback_at")

    # Rule 1: a hard opt-out or hostility outranks everything, including a
    # failed extraction (rule 4) - losing an opt-out to a parsing gap is the
    # one failure here with a legal consequence (`docs/GRADING.md` §4.2).
    if do_not_contact or hostile:
        if do_not_contact:
            return GradeOutcome(
                grade=LeadGrade.REFUSED,
                grade_reason="Asked not to be contacted again.",
                next_action=NextAction.SUPPRESS,
                decline_reason=decline_reason or DeclineReason.DO_NOT_CONTACT,
            )
        return GradeOutcome(
            grade=LeadGrade.REFUSED,
            grade_reason="Call turned hostile.",
            next_action=NextAction.SUPPRESS,
            decline_reason=decline_reason,
        )

    # Rule 2: an explicit spoken no.
    if intent == "no" and intent_explicit_no:
        return GradeOutcome(
            grade=LeadGrade.REFUSED,
            grade_reason="Said no outright.",
            next_action=NextAction.DROP,
            decline_reason=decline_reason,
        )

    # Rule 3: `is False`, never falsy and never a missing field - a null here
    # is rule 4's business, not rule 3's. "We asked and they said no" and "we
    # never got to ask" are different facts and get different grades
    # (`docs/GRADING.md` §4.2).
    if identity_confirmed is False or is_decision_maker is False:
        reason = (
            "Spoke to someone else at this number - not the person on the list."
            if identity_confirmed is False
            else "Interested, but not the decision maker."
        )
        return GradeOutcome(
            grade=LeadGrade.WRONG_PERSON,
            grade_reason=reason,
            next_action=NextAction.FIX_DATA,
            decline_reason=decline_reason,
        )

    # Rule 4: extraction failed, or a required field never got answered.
    # Never a silent COLD (`docs/GRADING.md` §2.2) - this is the single most
    # important test in the suite.
    missing_required = [f for f in config.required_fields if fields.get(f) is None]
    if extraction_errored or missing_required:
        reason = (
            "We could not read this call reliably - needs a person."
            if extraction_errored
            else f"Call ended before we could establish {_join_human(missing_required)}."
        )
        return GradeOutcome(
            grade=LeadGrade.UNGRADED,
            grade_reason=reason,
            next_action=NextAction.FIX_DATA,
            decline_reason=decline_reason,
        )

    # Rules 5-6: unconditional after rule 5 - a contact who said yes with
    # both the intake and the money unresolved is still handed to a human,
    # never dropped to COLD (`docs/GRADING.md` §4.2).
    if intent == "yes":
        intake_ok = _intake_ok(fields.get("intake_month"), config.intake_horizon_months, now=now)
        money_ok = _money_ok(fields, config)
        if intake_ok and money_ok:
            return GradeOutcome(
                grade=LeadGrade.HOT,
                grade_reason=(
                    f"Said yes, wants the {fields.get('intake_month')} intake, "
                    "and the money side is settled."
                ),
                next_action=NextAction.CALL_NOW,
                decline_reason=decline_reason,
            )
        missing = []
        if not intake_ok:
            missing.append("no intake picked yet" if not fields.get("intake_month") else "intake outside the window")
        if not money_ok:
            missing.append("budget not resolved")
        return GradeOutcome(
            grade=LeadGrade.WARM,
            grade_reason="Said yes, but " + " and ".join(missing) + ".",
            next_action=NextAction.CALL_NOW,
            decline_reason=decline_reason,
        )

    # Rule 7: genuinely undecided reaches WARM through intent, not through
    # decline_reason - STILL_DECIDING never overrides the grade
    # (`docs/GRADING.md` §4.2).
    if intent == "maybe":
        return GradeOutcome(
            grade=LeadGrade.WARM,
            grade_reason="Interested but undecided.",
            next_action=NextAction.CALL_AT if callback_at else NextAction.CALL_NOW,
            decline_reason=decline_reason,
        )

    # Rule 8: heard out, no present intent, no chaseable objection.
    if intent == "no":
        return GradeOutcome(
            grade=LeadGrade.COLD,
            grade_reason="Listened, but no present interest.",
            next_action=NextAction.NURTURE,
            decline_reason=decline_reason,
        )

    # Rule 9: the terminal arm. `intent` missing or `"unknown"` lands here,
    # not on a fabricated COLD (`docs/GRADING.md` §4.1, the note under rule 9).
    return GradeOutcome(
        grade=LeadGrade.UNGRADED,
        grade_reason="Could not establish interest reliably.",
        next_action=NextAction.FIX_DATA,
        decline_reason=decline_reason,
    )
