"""Post-call triage: decide what happens to each resolved call.

This is the layer that answers the operational question CallFlow AI exists for -
"which of these calls actually needs a human?" - so that clean outcomes
auto-close and only genuine problems reach a person.
"""

from __future__ import annotations

from typing import Any

from app.domain.entities import CallOutcome, Disposition, Sentiment

# Statuses that mean nobody picked up. Worth one retry.
RETRYABLE_STATUSES = {"busy", "no_answer", "voicemail"}


def _join_human(names: list[str]) -> str:
    """"a", "a and b", "a, b and c" - the reason is read by a person."""
    readable = [name.replace("_", " ") for name in names]
    if len(readable) == 1:
        return readable[0]
    return ", ".join(readable[:-1]) + " and " + readable[-1]


def _as_sentiment(raw: Any) -> Sentiment:
    try:
        return Sentiment(str(raw).lower())
    except ValueError:
        return Sentiment.UNKNOWN


def triage(outcome: CallOutcome, *, escalate_on_negative: bool = True) -> CallOutcome:
    """Assign a disposition. Pure function - returns an updated copy."""
    extracted = outcome.extracted or {}
    status = (outcome.status or "").lower()

    sentiment = _as_sentiment(extracted.get("sentiment"))
    frustrated = bool(extracted.get("frustration_signals"))
    wants_human = bool(extracted.get("wants_human_callback"))
    do_not_call = bool(extracted.get("do_not_call"))

    updates: dict[str, Any] = {"sentiment": sentiment}

    # Order matters: hard opt-outs beat everything, then human requests,
    # then emotional escalation, then reachability.
    if do_not_call:
        updates["disposition"] = Disposition.ESCALATED
        updates["disposition_reason"] = "Contact requested do-not-call - suppress and log immediately."

    elif wants_human:
        updates["disposition"] = Disposition.ESCALATED
        updates["disposition_reason"] = "Contact explicitly asked for a human."

    elif frustrated:
        updates["disposition"] = Disposition.ESCALATED
        updates["disposition_reason"] = (
            "Contact showed frustration during the call - review before dialing again."
        )

    # CALL-E's own holistic judgment that the conversation never reached a
    # clear resolution - independent of whatever the campaign's own
    # result_schema managed to extract. Ranked above the plain-status
    # buckets below, since an explicit `False` here is a real, considered
    # signal, not a fallback the way "no extracted fields" is; ranked below
    # the explicit human-said-so signals above, since those are more
    # specific and more actionable than CALL-E's summary-level judgment.
    elif outcome.task_completed is False:
        updates["disposition"] = Disposition.ESCALATED
        updates["disposition_reason"] = (
            "CALL-E judged the conversation did not reach a clear resolution - review "
            "before counting this as closed."
        )

    # Negative tone without frustration is usually "bad time, not bad mood".
    # That deserves another attempt, not a human escalation.
    elif escalate_on_negative and sentiment is Sentiment.NEGATIVE:
        updates["disposition"] = Disposition.RETRY
        updates["disposition_reason"] = (
            "Call went poorly but no frustration was detected - worth one polite retry."
        )

    elif status in RETRYABLE_STATUSES:
        updates["disposition"] = Disposition.RETRY
        updates["disposition_reason"] = f"Unreachable ({status}) - eligible for one retry."

    elif status in {"failed", "canceled"}:
        updates["disposition"] = Disposition.UNREACHABLE
        updates["disposition_reason"] = f"Call did not connect ({status})."

    # Completeness is checked *only* for a call that actually connected, and this
    # placement is ADR-5's own correction after review. The rules above for
    # negative sentiment, busy/no-answer/voicemail and failed/canceled all cover
    # calls that never had a chance to provide the data at all - escalating those
    # for "missing fields" would replace a useful "worth retrying" signal with a
    # useless one, for calls where of course nothing was collected.
    elif status == "completed" and outcome.missing_required_fields:
        updates["disposition"] = Disposition.ESCALATED
        updates["disposition_reason"] = (
            "The call ended without "
            + _join_human(outcome.missing_required_fields)
            + " - a person needs to ask."
        )

    elif status == "completed":
        updates["disposition"] = Disposition.AUTO_CLOSED
        updates["disposition_reason"] = "Conversation completed with no escalation signals."

    else:
        updates["disposition"] = Disposition.SKIPPED
        updates["disposition_reason"] = f"Unhandled status: {status or 'unknown'}"

    updates["sentiment_reason"] = updates["disposition_reason"]
    return outcome.model_copy(update=updates)


def needs_human(outcome: CallOutcome) -> bool:
    return outcome.disposition is Disposition.ESCALATED
