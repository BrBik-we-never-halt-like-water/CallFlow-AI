"""Campaign orchestration: contacts in, typed outcomes out.

Flow per contact:
    safety gate -> render goal -> engine create
                -> poll to terminal -> extract typed result -> triage

Only the orchestration itself lives here - I/O, concurrency, the safety
gate, polling. The pure extraction/triage logic each contact's terminal
payload goes through is `app/domain/outcome_extraction.py` (shared with the
webhook receiver, `api/v1/routes/webhooks.py`); goal-template rendering is
`app/domain/goal_rendering.py`. Split out of one file per CLAUDE.md's
Single-Responsibility guidance - none of that logic does any I/O, so it
belongs in `domain/`, not here.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from app.core.config import config
from app.core.logging import CallContext
from app.domain.entities import CallOutcome, Campaign, Contact, DialFailure, Disposition
from app.domain.goal_rendering import render_goal
from app.domain.outcome_extraction import _resolve_outcome
from app.domain.safety import check_dial_allowed, mask, phone_hash
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


class CampaignRunner:
    def __init__(
        self,
        gateway: EngineGateway | None = None,
        *,
        result_schema: JsonObject | None = None,
        webhook_url: str | None = None,
        suppressed_hashes: frozenset[str] = frozenset(),
        max_calls_per_run: int | None = None,
        allowlist: frozenset[str] | None = None,
        run_id: str | None = None,
        max_concurrent_calls: int | None = None,
        credit_ceiling: int | None = None,
        credits_used_before_run: int = 0,
    ) -> None:
        self.result_schema = result_schema
        self.webhook_url = webhook_url
        self._gateway = gateway
        self._calls_made = 0
        # Guards the check-and-reserve in `run_one()` (see its own comment) -
        # dialling itself still runs concurrently; only that brief moment is
        # serialised.
        self._calls_made_lock = asyncio.Lock()
        # Resolved once per run (a single query) rather than once per contact.
        self._suppressed_hashes = suppressed_hashes
        # An organisation's own Settings -> Safety override, or None to fall back
        # to the deployment's env-var defaults inside check_dial_allowed itself.
        self._max_calls_per_run = max_calls_per_run
        self._allowlist = allowlist
        # `None` when the caller (the run's own starter) has no per-teammate
        # allocation set at all - the per-teammate gate then never applies,
        # only the org-wide daily budget does. `credits_used_before_run` is a
        # live count of *today's already-connected* calls, resolved once at
        # run start the same way suppression/allowlist already are.
        # `_credits_reserved` is this run's own in-flight bookkeeping: a
        # contact reserves one credit before dialling (so two contacts
        # dialled concurrently can't both slip under the same last slot) and
        # gives it back if that particular call never connects - see
        # `run_one()`'s own comment for why a credit is only ever actually
        # spent by a connected call, never a mere attempt.
        self._credit_ceiling = credit_ceiling
        self._credits_used_before_run = credits_used_before_run
        self._credits_reserved = 0
        # The persisted run this instance belongs to, if any - gives each
        # contact's idempotency key a stable scope (see `run_one()`). `None`
        # for a caller with no real run (ad hoc use, tests).
        self._run_id = run_id
        self._max_concurrent_calls = (
            max_concurrent_calls if max_concurrent_calls is not None else config.max_concurrent_calls
        )

    @property
    def gateway(self) -> EngineGateway:
        if self._gateway is None:
            self._gateway = EngineGateway()
        return self._gateway

    async def run(
        self,
        campaign: Campaign,
        contacts: Iterable[Contact],
        *,
        on_progress: ProgressHook | None = None,
    ) -> list[CallOutcome]:
        """Dial every contact, up to `_max_concurrent_calls` at once.

        Was a strict one-at-a-time loop - for a run of N contacts at a
        minute or two per call, that's N minutes of wall-clock time when it
        could be a couple. `asyncio.gather` preserves the input order in its
        results regardless of which contact's call actually finishes first,
        so callers see the same per-contact ordering a sequential loop gave
        them. `return_exceptions=True` matters here specifically because of
        the concurrency: a bug in this module itself (not an engine/network
        failure - `run_one()` already turns those into a FAILED outcome
        without raising) must not cancel every *other* contact's real,
        already-in-flight phone call the way an unhandled `gather()`
        exception otherwise would - there is no sequential analog to that
        failure mode, since a one-at-a-time loop never has more than one
        contact in flight to abandon.
        """
        contact_list = list(contacts)
        semaphore = asyncio.Semaphore(self._max_concurrent_calls)

        async def _dial(contact: Contact) -> CallOutcome:
            # `on_progress` doubles as the live-status sink so an in-flight
            # call is visible while it happens, not only once it ends. Held
            # only around the dial/poll itself, not the final progress
            # write below - that's our own DB, not CALL-E, and doesn't need
            # to compete for the same concurrency budget.
            async with semaphore:
                outcome = await self.run_one(campaign, contact, on_status=on_progress)
            if on_progress:
                await on_progress(outcome)
            return outcome

        results = await asyncio.gather(
            *(_dial(contact) for contact in contact_list), return_exceptions=True
        )

        outcomes: list[CallOutcome] = []
        for contact, result in zip(contact_list, results, strict=True):
            if isinstance(result, BaseException):
                log.exception("contact processing crashed for %s", mask(contact.phone))
                outcomes.append(
                    CallOutcome(
                        contact_name=contact.name,
                        phone_masked=mask(contact.phone),
                        campaign_id=campaign.id,
                        status="FAILED",
                        error=DialFailure.INTERNAL.value,
                        disposition=Disposition.UNREACHABLE,
                        disposition_reason="Call could not be completed due to an internal error.",
                    )
                )
            else:
                outcomes.append(result)
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
                return call

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

    def _idempotency_key(self, campaign: Campaign, contact: Contact) -> str:
        """A retry of the *same* logical attempt must reuse the same key -
        that's the entire point of `Idempotency-Key`: if the create-call
        request reaches CALL-E and a call gets placed, but the response is
        lost before CallFlow sees it (timeout, dropped connection), a retry
        with the same key lets CALL-E recognise the duplicate and hand back
        the existing call instead of dialing the same person twice
        (`ISSUES.md` #54). Scoped to `self._run_id` (unique per persisted
        run) + a hash of the phone (never the raw number, in case this value
        ever surfaces in a trace/log outside CallFlow's own control) - stable
        across any retry of this exact (run, contact) pair, and distinct
        across two different runs dialling the same contact, so an old run's
        key can never be replayed against a new one.

        Without a real run (`self._run_id` is `None` - ad hoc use, tests),
        there's no stable job identity to key off, so this falls back to a
        fresh key every call, same as before this fix - not idempotent, but
        no worse than the prior default either.
        """
        if self._run_id is None:
            return f"{campaign.id}-{contact.phone}-{uuid.uuid4().hex[:8]}"
        return f"{self._run_id}:{phone_hash(contact.phone)}"

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
        # Checking `self._calls_made` and reserving a slot by incrementing it
        # must happen as one atomic step under concurrency - otherwise two
        # contacts dialled at the same time could both read the same
        # under-the-ceiling count before either increments, letting more
        # calls through than `max_calls_per_run` allows. The reservation
        # happens *before* the dial is attempted, not after it succeeds
        # (unlike the previous, sequential-only version) - a failed or
        # lost-response attempt still spent a real slot at CALL-E and must
        # still count, per CLAUDE.md's fail-closed rule (`ISSUES.md` #54).
        async with self._calls_made_lock:
            credits_remaining = (
                None
                if self._credit_ceiling is None
                else self._credit_ceiling - self._credits_used_before_run - self._credits_reserved
            )
            gate = check_dial_allowed(
                contact.phone,
                self._calls_made,
                is_suppressed=phone_hash(contact.phone) in self._suppressed_hashes,
                max_calls_per_run=self._max_calls_per_run,
                allowlist=self._allowlist,
                credits_remaining=credits_remaining,
            )
            reserved_credit = gate.allowed and self._credit_ceiling is not None
            if gate.allowed:
                self._calls_made += 1
                if reserved_credit:
                    self._credits_reserved += 1

        if not gate.allowed:
            return base.model_copy(
                update={
                    "status": "BLOCKED",
                    "disposition": Disposition.SKIPPED,
                    "disposition_reason": gate.reason,
                }
            )

        # Plain, vendor-neutral shape - the engine's `metadata` field is a fully
        # free-form bag with no required namespacing (confirmed against the
        # generated SDK model), so nothing above `engine.py` needs a
        # vendor-flavoured key to satisfy it. `run_id` is included so the
        # webhook receiver (`api/v1/routes/webhooks.py`) can tell which run a
        # terminal event belongs to once CALL-E echoes this back - omitted
        # when there's no real run to attribute it to (ad hoc use, tests).
        metadata: JsonObject = {
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "contact_name": contact.name,
            **contact.context,
        }
        if self._run_id is not None:
            metadata["run_id"] = self._run_id

        try:
            created = await asyncio.to_thread(
                self.gateway.start_call,
                task=goal,
                phone=contact.phone,
                result_schema=self.result_schema,
                metadata=metadata,
                webhook_url=self.webhook_url,
                idempotency_key=self._idempotency_key(campaign, contact),
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

            with CallContext(call_id=call_id):
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
            outcome = base.model_copy(
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
            outcome = base.model_copy(
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
            outcome = base.model_copy(
                update={
                    "status": "FAILED",
                    "error": DialFailure.INTERNAL.value,
                    "disposition": Disposition.UNREACHABLE,
                    "disposition_reason": "Call could not be completed due to an internal error.",
                }
            )
        else:
            outcome = _resolve_outcome(base, final, escalate_on_negative=campaign.escalate_on_negative)

        # A credit is only ever actually spent by a connected call (CLAUDE.md
        # money/credit non-negotiable, applied here even though credits
        # aren't currency: fail closed, but never charge for something that
        # didn't happen). Every non-connected path above reserved a slot
        # before knowing that - hand it back now so a later contact in this
        # same run can use it.
        if reserved_credit and not outcome.answered:
            async with self._calls_made_lock:
                self._credits_reserved -= 1

        return outcome
