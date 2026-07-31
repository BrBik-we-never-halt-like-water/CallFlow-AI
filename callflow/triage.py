"""Post-call triage: decide what happens to each resolved call.

This is the layer that answers the operational question CallFlow AI exists for —
"which of these calls actually needs a human?" — so that clean outcomes
auto-close and only genuine problems reach a person.
"""

from __future__ import annotations

from typing import Any

from .models import CallOutcome, Disposition, Sentiment

# Statuses that mean nobody picked up. Worth one retry.
RETRYABLE_STATUSES = {"busy", "no_answer", "voicemail"}


def _as_sentiment(raw: Any) -> Sentiment:
    try:
        return Sentiment(str(raw).lower())
    except ValueError:
        return Sentiment.UNKNOWN


def triage(outcome: CallOutcome, *, escalate_on_negative: bool = True) -> CallOutcome:
    """Assign a disposition. Pure function — returns an updated copy."""
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
        updates["disposition_reason"] = "Contact requested do-not-call — suppress and log immediately."

    elif wants_human:
        updates["disposition"] = Disposition.ESCALATED
        updates["disposition_reason"] = "Contact explicitly asked for a human."

    elif frustrated:
        updates["disposition"] = Disposition.ESCALATED
        updates["disposition_reason"] = (
            "Contact showed frustration during the call — review before dialing again."
        )

    # Negative tone without frustration is usually "bad time, not bad mood".
    # That deserves another attempt, not a human escalation.
    elif escalate_on_negative and sentiment is Sentiment.NEGATIVE:
        updates["disposition"] = Disposition.RETRY
        updates["disposition_reason"] = (
            "Call went poorly but no frustration was detected — worth one polite retry."
        )

    elif status in RETRYABLE_STATUSES:
        updates["disposition"] = Disposition.RETRY
        updates["disposition_reason"] = f"Unreachable ({status}) — eligible for one retry."

    elif status in {"failed", "canceled"}:
        updates["disposition"] = Disposition.UNREACHABLE
        updates["disposition_reason"] = f"Call did not connect ({status})."

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
