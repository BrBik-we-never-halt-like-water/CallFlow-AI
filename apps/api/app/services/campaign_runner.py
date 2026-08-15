"""Campaign orchestration: contacts in, typed outcomes out.

Flow per contact:
    safety gate -> render goal -> originate call
                -> extract typed result -> triage

Only the orchestration itself lives here - I/O, concurrency, the safety gate.
The pure extraction/triage logic each contact's terminal payload goes through
is `app/domain/outcome_extraction.py`; goal-template rendering is
`app/domain/goal_rendering.py`. Split out of one file per CLAUDE.md's
Single-Responsibility guidance - none of that logic does any I/O, so it
belongs in `domain/`, not here.

The origination step is currently a stub: CALL-E has been removed and the
LiveKit replacement lands in RUNBOOK_HET_PART_1.md P1-T6. Until then every
contact returns an explicit failure - see `run_one()`.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from app.core.config import config
from app.domain.entities import CallOutcome, Campaign, Contact, DialFailure, Disposition
from app.domain.safety import check_dial_allowed, mask, phone_hash

# Failures worth trying again, not treating as "this number doesn't work": the
# carrier said this is a transient condition rather than something wrong with
# the number or the request itself. A fresh call attempt against a
# number/request that's genuinely invalid or blocked should not be retried, per
# CLAUDE.md's fail-closed rule for anything that spends a credit or places a
# call. Nothing populates this yet - P1-T6 maps LiveKit/Twilio/Plivo errors
# onto `DialFailure` and restores the classification that fed it.
_RETRYABLE_FAILURES = frozenset(
    {DialFailure.RATE_LIMITED, DialFailure.PROVIDER_UNAVAILABLE, DialFailure.TIMED_OUT}
)

log = logging.getLogger("app.services.campaign_runner")

JsonObject = dict[str, Any]
ProgressHook = Callable[[CallOutcome], Awaitable[None]]


class CampaignRunner:
    def __init__(
        self,
        *,
        result_schema: JsonObject | None = None,
        suppressed_hashes: frozenset[str] = frozenset(),
        max_calls_per_run: int | None = None,
        allowlist: frozenset[str] | None = None,
        run_id: str | None = None,
        max_concurrent_calls: int | None = None,
        credit_ceiling: int | None = None,
        credits_used_before_run: int = 0,
    ) -> None:
        self.result_schema = result_schema
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

        # Real origination lands in P1-T6 (LiveKit CreateSIPParticipant). Until
        # then this fails loudly rather than reporting anything that did not
        # happen - CLAUDE.md non-negotiable #9. The safety gate above still runs
        # first and still reserves a slot, so the guards stay exercised and the
        # blocked/allowed split keeps behaving exactly as it will once dialling
        # is back.
        log.info("dial skipped for %s - no voice provider configured", mask(contact.phone))

        # A credit is only ever actually spent by a connected call (CLAUDE.md
        # money/credit non-negotiable, applied here even though credits aren't
        # currency). This stub never connects, so any slot reserved above must
        # be handed back immediately - otherwise every contact in a run with a
        # credit ceiling set would permanently burn a credit it never spent,
        # eventually blocking every later contact for a reason that never
        # actually happened.
        if reserved_credit:
            async with self._calls_made_lock:
                self._credits_reserved -= 1

        return base.model_copy(
            update={
                "status": "FAILED",
                "error": DialFailure.PROVIDER_UNAVAILABLE.value,
                "disposition": Disposition.SKIPPED,
                "disposition_reason": (
                    "Calling is not available yet - the voice platform migration is in progress."
                ),
            }
        )
