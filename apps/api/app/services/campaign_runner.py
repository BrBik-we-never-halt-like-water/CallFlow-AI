"""Campaign orchestration: contacts in, typed outcomes out.

Flow per contact:
    safety gate -> render goal -> engine create
                -> poll to terminal -> extract typed result -> triage
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime
from typing import Any

from app.core.config import config
from app.domain.entities import CallOutcome, Campaign, Contact, DialFailure, Disposition
from app.domain.safety import check_dial_allowed, mask, phone_hash
from app.domain.triage import triage
from app.integrations.voice.engine import (
    TERMINAL,
    EngineAPIError,
    EngineConnectionError,
    EngineGateway,
    EngineTimeoutError,
    classify_error,
)

# Failures worth trying again, not treating as "this number doesn't work": the
# engine, or its downstream carrier, said this is a transient condition rather
# than something wrong with the number or the request itself. This set governs
# dial-time decisions (start_call, and a non-retryable poll failure) - a fresh
# call attempt against a number/request that's genuinely invalid or blocked
# should not be retried, per CLAUDE.md's fail-closed rule for anything that
# spends a credit or places a call.
_RETRYABLE_FAILURES = frozenset(
    {DialFailure.RATE_LIMITED, DialFailure.PROVIDER_UNAVAILABLE, DialFailure.TIMED_OUT}
)

# A GET poll is a different question from "safe to dial again": it's an
# idempotent read of a call that's already in flight, not a safety/credit/
# permission decision, so CLAUDE.md's fail-closed rule doesn't apply to it the
# way it does to _RETRYABLE_FAILURES above. Abandoning a live, possibly-already
# -completed call because one status check hit `internal_error`, `not_found`
# (the classic read-after-write race right after creation), or `call_not_ready`
# is the lossy choice, not the conservative one - all three fall through
# `classify_error`'s unmapped-code default to DialFailure.INTERNAL today, and
# would otherwise sit outside _RETRYABLE_FAILURES. So every failure is worth
# retrying here except one this account cannot recover from by waiting:
# UNAUTHORIZED (covers both the engine's `unauthorized` and `forbidden` codes) -
# if the credentials are bad, no amount of polling fixes that, and burning the
# rest of the timeout on it delays the operator finding out.
_POLL_RETRYABLE_FAILURES = frozenset(DialFailure) - {DialFailure.UNAUTHORIZED}

log = logging.getLogger("app.services.campaign_runner")

JsonObject = dict[str, Any]
ProgressHook = Callable[[CallOutcome], Awaitable[None]]


def _live_label(status: str) -> str:
    """Human-readable text for an in-flight call status."""
    return {
        "queued": "Queued with the voice engine…",
        "scheduled": "Scheduled…",
        "dialing": "Dialing…",
        "ringing": "Ringing…",
        "in_progress": "In conversation…",
        "connected": "In conversation…",
    }.get(status, f"{status.replace('_', ' ').capitalize()}…")


def render_goal(campaign: Campaign, contact: Contact) -> str:
    """Fill the campaign template with contact data.

    Uses format_map with a defaulting dict so a missing context key degrades to
    an empty string instead of crashing a whole campaign run.
    """

    class _Safe(dict):
        def __missing__(self, key: str) -> str:
            return ""

    fields = _Safe(name=contact.name, phone=contact.phone, **contact.context)
    return campaign.goal_template.format_map(fields)


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


def _extract_duration(call: JsonObject) -> float | None:
    """Computes how long the call lasted from the final attempt's own
    timestamps.

    There is no `duration_seconds` field anywhere in CALL-E's real response -
    confirmed against the installed SDK's generated `CallTaskAttempt` model,
    which declares only `started_at`/`completed_at`, no duration of any kind.
    Reading `call.get("duration_seconds")` (the previous implementation)
    therefore always returned `None` for every real call - the same class of
    bug as the top-level-key-that-doesn't-exist transcript bug (ISSUES.md
    #52), just never cross-checked for this field at the time. Uses the same
    `_final_attempt()` selection as `_extract_transcript` so the reported
    duration always corresponds to the same attempt whose transcript is
    shown, not a different one.
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

    started = attempt.get("started_at")
    completed = attempt.get("completed_at")
    if not started or not completed:
        return None
    try:
        start_dt = datetime.fromisoformat(started)
        end_dt = datetime.fromisoformat(completed)
    except (TypeError, ValueError):
        return None
    return max(0.0, (end_dt - start_dt).total_seconds())


class CampaignRunner:
    def __init__(
        self,
        gateway: EngineGateway | None = None,
        *,
        run_id: str | None = None,
        result_schema: JsonObject | None = None,
        webhook_url: str | None = None,
        suppressed_hashes: frozenset[str] = frozenset(),
        max_calls_per_run: int | None = None,
        allowlist: frozenset[str] | None = None,
    ) -> None:
        self.result_schema = result_schema
        self.webhook_url = webhook_url
        self._gateway = gateway
        self._calls_made = 0
        self._canceled = False
        # Stable for the lifetime of this runner even when the caller doesn't
        # pass one (every unit test constructs a CampaignRunner directly) -
        # what matters is that it never changes between the safety gate and
        # the dial for the *same* contact, unlike the freshly-random suffix it
        # replaces (`uuid.uuid4().hex[:8]` generated fresh on every call,
        # which defeated the whole point of an idempotency key - ISSUES.md
        # #54: a connection dropped after the vendor placed the call but
        # before the response arrived meant a retry looked like a brand new
        # request to CALL-E).
        self._run_id = run_id or uuid.uuid4().hex[:12]
        # Resolved once per run (a single query) rather than once per contact.
        self._suppressed_hashes = suppressed_hashes
        # An organisation's own Settings -> Safety override, or None to fall back
        # to the deployment's env-var defaults inside check_dial_allowed itself.
        self._max_calls_per_run = max_calls_per_run
        self._allowlist = allowlist

    @property
    def gateway(self) -> EngineGateway:
        if self._gateway is None:
            self._gateway = EngineGateway()
        return self._gateway

    @property
    def canceled(self) -> bool:
        """True once `run()` has stopped early because `should_cancel()`
        returned True. Distinct from simply "not all contacts were dialled" -
        a run that raised partway through is not `canceled`, it's failed."""
        return self._canceled

    async def run(
        self,
        campaign: Campaign,
        contacts: Iterable[Contact],
        *,
        on_progress: ProgressHook | None = None,
        should_cancel: Callable[[], Awaitable[bool]] | None = None,
    ) -> list[CallOutcome]:
        """Dial each contact in turn, stopping early if `should_cancel` ever
        returns True.

        Checked *between* contacts only, never mid-call - there is no way to
        interrupt a call already in conversation (the voice engine has no
        cancel operation), so the honest guarantee is "no further contacts
        are dialled," not "the run stops instantly." Contacts never reached
        get no outcome row at all rather than a fabricated "canceled" one -
        the run's own `status` already says a canceled run didn't finish, and
        `total` vs however many outcomes exist already shows how far it got.
        """
        outcomes: list[CallOutcome] = []
        for contact in contacts:
            if should_cancel is not None and await should_cancel():
                self._canceled = True
                break
            # `on_progress` doubles as the live-status sink so an in-flight
            # call is visible while it happens, not only once it ends.
            outcome = await self.run_one(campaign, contact, on_status=on_progress)
            outcomes.append(outcome)
            if on_progress:
                await on_progress(outcome)
        return outcomes

    async def _poll_until_done(
        self,
        call_id: str,
        *,
        on_status: ProgressHook | None,
        base: CallOutcome,
    ) -> JsonObject:
        """Poll a call to completion, reporting each status change.

        The SDK's own `wait_for_result` blocks silently. Polling here lets the
        dashboard show `queued → ringing → in_progress` while the call happens,
        instead of a frozen spinner until it ends. The SDK itself is a blocking
        client, so each poll runs in a worker thread rather than on the event
        loop - otherwise one in-flight call would stall every other request.

        At 2s between polls and up to `poll_timeout_seconds` (900s by default),
        a single call can make on the order of 450 HTTP requests just to watch
        it finish. A poll failing doesn't mean the phone call failed - CALL-E
        keeps running the conversation regardless of whether we can currently
        reach `GET /v1/calls/{id}` - so one flaky request must not end the
        whole loop the way any other unhandled exception here would. Each
        failure is classified with `_POLL_RETRYABLE_FAILURES` (deliberately
        wider than `_RETRYABLE_FAILURES` - see its own comment for why a GET
        poll gets a different, more forgiving answer than a dial decision):
        retryable ones are logged and the loop tries again next tick; anything
        still classified as non-retryable (an outright auth failure - polling
        can't recover from that) is re-raised immediately rather than spending
        the rest of the timeout on something that cannot succeed. No separate
        consecutive-failure counter is needed for the retryable path - the
        existing `deadline` is already a firm 900s ceiling, not an unbounded
        retry.
        """
        deadline = time.monotonic() + config.poll_timeout_seconds
        last_status = ""

        while time.monotonic() < deadline:
            try:
                call = await asyncio.to_thread(self.gateway.get_call, call_id)
            except (EngineAPIError, EngineTimeoutError, EngineConnectionError) as exc:
                failure = classify_error(exc)
                if failure not in _POLL_RETRYABLE_FAILURES:
                    raise
                log.warning(
                    "transient poll failure for call %s: %s - retrying", call_id, failure.value
                )
                await asyncio.sleep(2.0)
                continue

            status = str(call.get("status", "")).lower()

            if status in TERMINAL:
                return await self._await_settled_duration(call_id, call)

            if status and status != last_status and on_status is not None:
                last_status = status
                await on_status(
                    base.model_copy(
                        update={
                            "status": status.upper(),
                            "run_id": call_id,
                            "disposition": Disposition.IN_FLIGHT,
                            "disposition_reason": _live_label(status),
                        }
                    )
                )

            await asyncio.sleep(2.0)

        raise TimeoutError(f"Call {call_id} did not finish within the timeout.")

    async def _await_settled_duration(self, call_id: str, call: JsonObject) -> JsonObject:
        """Close the gap between the top-level `status` going terminal and the
        same response's nested attempt timestamps catching up.

        Confirmed against a real call (ISSUES.md #61's follow-up): a live
        re-fetch of a call that had already been sitting at `duration_seconds =
        None` in the database returned a fully-settled `completed`/`failed`
        attempt with both `started_at` and `completed_at` populated, and
        `_extract_duration` computed the correct value from it without any
        change to that function. The only place the two could have disagreed
        is the moment the *original* poll accepted its terminal response - so
        the engine's own top-level `status` field and its nested
        `recipients[0].attempts[].completed_at` are not written atomically,
        the same class of eventual-consistency gap as the flaky-poll bug
        already fixed for status itself (#53). A few short re-fetches close
        it; if it never settles, this returns the last response anyway rather
        than blocking the whole run - a stuck `duration_seconds` is a data gap,
        not a reason to fail the call.
        """
        for _ in range(3):
            if _extract_duration(call) is not None:
                return call
            await asyncio.sleep(1.5)
            call = await asyncio.to_thread(self.gateway.get_call, call_id)
        return call

    async def run_one(
        self,
        campaign: Campaign,
        contact: Contact,
        *,
        on_status: ProgressHook | None = None,
    ) -> CallOutcome:
        base = CallOutcome(
            contact_name=contact.name,
            phone_masked=mask(contact.phone),
            campaign_id=campaign.id,
        )

        goal = render_goal(campaign, contact)

        # --- Safety gate: fails closed, runs before anything can dial. ------
        gate = check_dial_allowed(
            contact.phone,
            self._calls_made,
            is_suppressed=phone_hash(contact.phone) in self._suppressed_hashes,
            max_calls_per_run=self._max_calls_per_run,
            allowlist=self._allowlist,
        )
        if not gate.allowed:
            return base.model_copy(
                update={
                    "status": "BLOCKED",
                    "disposition": Disposition.SKIPPED,
                    "disposition_reason": gate.reason,
                }
            )

        metadata = {
            "call-e/customerMetadata": {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "contact_name": contact.name,
                **contact.context,
            }
        }

        # Reserved before the request is sent, not after a successful return.
        # A request whose response never arrives (EngineConnectionError) may
        # still have reached the vendor and placed a real call - undercounting
        # the per-run ceiling is safe, only counting *confirmed* successes is
        # not, since it let a connection-drop retry dial past the ceiling
        # without ever being counted against it (ISSUES.md #54).
        self._calls_made += 1

        try:
            created = await asyncio.to_thread(
                self.gateway.start_call,
                task=goal,
                phone=contact.phone,
                result_schema=self.result_schema,
                metadata=metadata,
                webhook_url=self.webhook_url,
                # Stable per (run, contact) - not a fresh random suffix per
                # attempt - so CALL-E can actually recognise a retry as a
                # duplicate of a request that already reached it (see
                # `self._run_id`'s docstring in __init__).
                idempotency_key=f"{self._run_id}-{contact.phone}",
                region=contact.region or campaign.region,
                language=contact.language or campaign.language,
            )

            call_id = str(created.get("id", ""))

            # Surface the row as soon as the call is placed. Otherwise the
            # dashboard shows nothing for the whole call - which reads as a
            # hang when a conversation runs for minutes.
            if on_status is not None:
                await on_status(
                    base.model_copy(
                        update={
                            "status": str(created.get("status", "queued")).upper(),
                            "run_id": call_id,
                            "disposition": Disposition.IN_FLIGHT,
                            "disposition_reason": "Dialing…",
                        }
                    )
                )

            final = await self._poll_until_done(call_id, on_status=on_status, base=base)

        except (EngineAPIError, EngineTimeoutError, EngineConnectionError) as exc:
            # Classified against the engine's own documented error taxonomy
            # (CALLE.md §4), not left as a raw exception string - so an operator
            # can tell "this number is bad, stop trying" apart from "we're rate
            # limited, this will work on retry" instead of both reading as the
            # same generic failure. `EngineConnectionError` (raised by the SDK
            # when a request fails before any response arrives) is included
            # here too - without it, a dropped connection during `start_call`
            # would fall through to the generic `except Exception` below and
            # be misclassified as a non-retryable internal error instead of
            # the transient, worth-retrying failure it actually is.
            failure = classify_error(exc)
            log.exception("call failed for %s: %s", mask(contact.phone), failure.value)
            retryable = failure in _RETRYABLE_FAILURES
            return base.model_copy(
                update={
                    "status": "FAILED",
                    "error": failure.value,
                    "disposition": Disposition.RETRY if retryable else Disposition.UNREACHABLE,
                    "disposition_reason": (
                        f"Worth retrying - {failure.value.replace('_', ' ')}."
                        if retryable
                        else f"Call could not be completed: {failure.value.replace('_', ' ')}."
                    ),
                }
            )
        except TimeoutError:
            # Raised by _poll_until_done itself when the call never reached a
            # terminal status in time - not an engine error, so it can't go
            # through classify_error(), but it's the same "transient, worth
            # trying again" shape as PROVIDER_UNAVAILABLE/RATE_LIMITED.
            log.exception("poll timed out for %s", mask(contact.phone))
            return base.model_copy(
                update={
                    "status": "FAILED",
                    "error": DialFailure.TIMED_OUT.value,
                    "disposition": Disposition.RETRY,
                    "disposition_reason": "Worth retrying - timed out waiting for a result.",
                }
            )
        except Exception:  # network error, or anything else unclassified
            # The exception's own message is logged (log.exception captures it
            # in full) but never interpolated into a user-facing field - unlike
            # a vendor error's DialFailure.value, a raw exception string is
            # untrusted content that can carry hostnames, URLs, or other
            # internal detail through to whoever views this run or escalation.
            log.exception("call failed for %s", mask(contact.phone))
            return base.model_copy(
                update={
                    "status": "FAILED",
                    "error": DialFailure.INTERNAL.value,
                    "disposition": Disposition.UNREACHABLE,
                    "disposition_reason": "Call could not be completed due to an internal error.",
                }
            )

        extracted = _extract_result(final)
        resolved = base.model_copy(
            update={
                "status": str(final.get("status", "unknown")).upper(),
                "run_id": call_id,
                "transcript": _extract_transcript(final),
                "summary": extracted.get("summary") or final.get("summary"),
                "extracted": extracted,
                "duration_seconds": _extract_duration(final),
            }
        )
        return triage(resolved, escalate_on_negative=campaign.escalate_on_negative)
