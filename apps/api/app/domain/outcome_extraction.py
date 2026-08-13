"""Turning a raw CALL-E call payload into a triaged `CallOutcome`. Pure - no
I/O, no vendor SDK - shared by both ways a call resolves: `CampaignRunner`'s
own poll loop (`app/services/campaign_runner.py`) and the webhook receiver
(`app/api/v1/routes/webhooks.py`). One extraction implementation, one triage
call, regardless of which path noticed the call finished first.
"""

from __future__ import annotations

from typing import Any

from app.domain.entities import AttemptSummary, CallOutcome
from app.domain.safety import mask
from app.domain.triage import triage

JsonObject = dict[str, Any]


def _extract_result(call: JsonObject) -> JsonObject:
    """Pull the engine's structured extraction out of the call payload.

    Confirmed against the SDK's generated `CallTaskStructuredResultType0` model
    (its own docstring: "Schema-valid structured result object extracted for
    the whole call task using `result_schema`") - CampaignRunner always passes
    a task-level `result_schema` to `start_call`, never `recipient_result_schema`,
    so the real API always populates the top-level `structured_result` key,
    which the first loop below checks. The other top-level keys, the one-level
    nesting check, and the `recipients[0]` fallback are defensive rather than
    confirmed-necessary: harmless if never hit, and `recipients[0].structured_result`
    is a real, documented field (`CallTaskRecipient.structured_result`) that
    would start mattering if `recipient_result_schema` is ever adopted instead.
    """
    for key in ("result", "structured_result", "results", "output", "data"):
        value = call.get(key)
        if isinstance(value, dict) and value:
            # Some shapes nest the payload one level deeper.
            for inner in ("result", "structured_result", "data"):
                nested = value.get(inner)
                if isinstance(nested, dict) and nested:
                    return nested
            return value

    # Batch shape: recipients[0].result
    recipients = call.get("recipients")
    if isinstance(recipients, list) and recipients:
        first = recipients[0]
        if isinstance(first, dict):
            for key in ("result", "structured_result", "data"):
                value = first.get(key)
                if isinstance(value, dict) and value:
                    return value
    return {}


def _has_transcript(attempt: JsonObject) -> bool:
    turns = attempt.get("transcript_turns")
    return isinstance(turns, list) and len(turns) > 0


def _extract_attempts(call: JsonObject) -> list[AttemptSummary]:
    """Every dial attempt CALL-E made for this recipient - not just the one
    `_final_attempt()` picks below for its transcript. A recipient can be
    redialled; this preserves that history instead of discarding it."""
    recipients = call.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        return []
    first = recipients[0]
    if not isinstance(first, dict):
        return []
    attempts = first.get("attempts")
    if not isinstance(attempts, list):
        return []
    return [
        AttemptSummary(
            status=str(attempt.get("status", "unknown")),
            started_at=attempt.get("started_at"),
            completed_at=attempt.get("completed_at"),
            had_transcript=_has_transcript(attempt),
        )
        for attempt in attempts
        if isinstance(attempt, dict)
    ]


def _final_attempt(attempts: list[Any]) -> JsonObject | None:
    """Pick the attempt whose transcript best represents what actually happened.

    A recipient can be redialled, so `attempts` may hold more than one dial.
    Picking by status alone isn't enough: the model documents `transcript_turns`
    as "empty when no transcript is available" on *any* status, so a `completed`
    final attempt can still have nothing to show while an earlier `failed` one
    holds a real partial conversation - that's the exact case that would have
    reproduced this fix's own symptom (a real conversation existing, but
    nothing surfaced) if status were the only signal. So the actual transcript
    content is what decides: prefer the most recent `completed` attempt that
    has turns; if none, the most recent attempt of *any* status that has turns;
    only if nothing has ever captured a turn does this fall back to the literal
    most recent attempt (which will end up rendering as "no transcript").

    "Most recent" is `started_at` order, not array position - the model
    doesn't document `attempts` as chronologically ordered, and `started_at` is
    already on every attempt (an ISO 8601 string, so it sorts correctly as
    text with no parsing needed). Attempts with no `started_at` yet sort first.
    """
    dict_attempts = [a for a in attempts if isinstance(a, dict)]
    if not dict_attempts:
        return None

    ordered = sorted(dict_attempts, key=lambda a: a.get("started_at") or "")

    completed_with_transcript = [
        a for a in ordered if _has_transcript(a) and str(a.get("status", "")).lower() == "completed"
    ]
    if completed_with_transcript:
        return completed_with_transcript[-1]

    any_with_transcript = [a for a in ordered if _has_transcript(a)]
    if any_with_transcript:
        return any_with_transcript[-1]

    return ordered[-1]


def _extract_transcript(call: JsonObject) -> str | None:
    """Pull the transcript out of the call payload.

    CALL-E's response has no top-level transcript field at all - confirmed
    against the installed SDK's generated models (`CallTaskAttempt.transcript_turns`,
    `CallTranscriptTurn`) and the public OpenAPI spec (CALLE.md). The real
    location is nested two levels down: recipients[N].attempts[M].transcript_turns[],
    where each turn is `{offset_seconds, speaker: "bot"|"user"|"unknown", text}`.

    `_extract_result` above uses `recipients[0]` for its batch fallback, so the
    same convention is followed here: this codebase only ever dials one contact
    per call, so a real batch (recipients > 1) shouldn't occur in practice, but
    if the engine ever returns more than one, the first is the one this call
    was actually placed for.
    """
    recipients = call.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        return None
    first = recipients[0]
    if not isinstance(first, dict):
        return None

    attempts = first.get("attempts")
    if not isinstance(attempts, list):
        return None
    attempt = _final_attempt(attempts)
    if attempt is None:
        return None

    turns = attempt.get("transcript_turns")
    if not isinstance(turns, list) or not turns:
        return None

    parts: list[str] = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        # `.get(key, default)` only falls back when the key is absent - a turn
        # with `"text": null` (a real, permitted value on the model) still
        # returns None here, which would otherwise render the literal string
        # "None" to whoever reads the transcript. `or ""` catches that case
        # too, and a turn with nothing real to say is skipped outright rather
        # than rendered as an empty line.
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        speaker = turn.get("speaker") or "?"
        parts.append(f"{speaker}: {text}")
    return "\n".join(parts) if parts else None


def _resolve_outcome(
    base: CallOutcome, final: JsonObject, *, escalate_on_negative: bool
) -> CallOutcome:
    """Turns a terminal CALL-E payload into a triaged `CallOutcome`."""
    extracted = _extract_result(final)

    # Task-level judgment fields, confirmed against the live OpenAPI spec as
    # task-level only, never per-recipient - independent of `extracted`,
    # which is whatever the campaign's own `result_schema` asked for.
    confidence = final.get("completion_confidence")
    confidence_score = confidence.get("score") if isinstance(confidence, dict) else None
    confidence_label = confidence.get("label") if isinstance(confidence, dict) else None
    evidence = final.get("evidence")
    evidence_list = [str(item) for item in evidence] if isinstance(evidence, list) else []

    resolved = base.model_copy(
        update={
            "status": str(final.get("status", "unknown")).upper(),
            "run_id": str(final.get("id", "")),
            "transcript": _extract_transcript(final),
            "summary": extracted.get("summary") or final.get("summary"),
            "extracted": extracted,
            "duration_seconds": final.get("duration_seconds"),
            "task_completed": final.get("task_completed"),
            "completion_confidence_score": confidence_score,
            "completion_confidence_label": confidence_label,
            "evidence": evidence_list,
            "attempts": _extract_attempts(final),
        }
    )
    return triage(resolved, escalate_on_negative=escalate_on_negative)


def base_outcome_from_webhook_payload(call: JsonObject) -> CallOutcome | None:
    """Reconstructs the same `base` `CallOutcome` shape `CampaignRunner.run_one()`
    builds from its live `Contact`/`Campaign`, but from a raw webhook payload
    alone - the receiver has no `Contact`/`Campaign` object, only what CALL-E
    echoes back in `metadata` plus the call's own `recipients[]`.

    Returns `None` if the payload doesn't carry what a call placed by
    `CampaignRunner` always includes (`metadata.contact_name`/`campaign_id`,
    at least one recipient/attempt with a `phone`) - a call placed some other
    way, or a shape this defensive check doesn't expect. No leading
    underscore, unlike this module's other private helpers - the webhook
    route imports it directly, the same way tests already import
    `_extract_result`/`_extract_transcript`.
    """
    metadata = call.get("metadata")
    if not isinstance(metadata, dict):
        return None
    contact_name = metadata.get("contact_name")
    campaign_id = metadata.get("campaign_id")
    if not contact_name or not campaign_id:
        return None

    recipients = call.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        return None
    first = recipients[0]
    if not isinstance(first, dict):
        return None
    attempts = first.get("attempts")
    attempt = _final_attempt(attempts) if isinstance(attempts, list) else None
    phone = attempt.get("phone") if isinstance(attempt, dict) else None
    if not phone:
        return None

    return CallOutcome(
        contact_name=str(contact_name),
        phone_masked=mask(str(phone)),
        campaign_id=str(campaign_id),
    )


__all__ = [
    "_extract_attempts",
    "_extract_result",
    "_extract_transcript",
    "_final_attempt",
    "_has_transcript",
    "_resolve_outcome",
    "base_outcome_from_webhook_payload",
]
