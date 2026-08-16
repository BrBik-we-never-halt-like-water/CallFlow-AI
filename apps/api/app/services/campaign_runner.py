"""Campaign orchestration: contacts in, typed outcomes out.

Flow per contact:
    safety gate -> render goal -> originate call -> report in flight

Only the orchestration itself lives here - I/O, concurrency, the safety gate.
Goal-template rendering is `app/domain/goal_rendering.py`; the pure
extraction/triage logic is `app/domain/outcome_extraction.py`. Split out of one
file per CLAUDE.md's Single-Responsibility guidance - none of that logic does
any I/O, so it belongs in `domain/`, not here.

**A run no longer ends here.** CALL-E was a request/response engine that could
be polled to completion, so `run_one()` used to return a finished, triaged
outcome. LiveKit is not: origination puts a caller and an agent worker into a
room, and the conversation then happens somewhere this process is not. So
`run_one()` returns once the call is *answered*, reporting IN_FLIGHT, and the
worker POSTs the transcript and terminal status back when the call actually
ends (RUNBOOK_HET_PART_1.md P1-T4). Extraction and triage move to that callback.

That is a real behavioural change, not an implementation detail: anything
reading a run's outcomes must expect IN_FLIGHT rows that resolve later, rather
than every row being terminal the moment `run()` returns.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from typing import Any

from app.core.config import config
from app.domain.entities import CallOutcome, Campaign, Contact, DialFailure, Disposition
from app.domain.goal_rendering import render_goal
from app.domain.safety import check_dial_allowed, mask, phone_hash
from app.integrations.livekit.client import EngineError, LiveKitGateway, classify_error

# Failures worth trying again, not treating as "this number doesn't work": the
# carrier said this is a transient condition rather than something wrong with
# the number or the request itself. A fresh call attempt against a
# number/request that's genuinely invalid or blocked should not be retried, per
# CLAUDE.md's fail-closed rule for anything that spends a credit or places a
# call.
#
# BUSY and NO_ANSWER belong here for the obvious reason: the number is fine and
# the person simply wasn't available, which is the textbook case for calling
# back rather than giving up on them.
_RETRYABLE_FAILURES = frozenset(
    {
        DialFailure.RATE_LIMITED,
        DialFailure.PROVIDER_UNAVAILABLE,
        DialFailure.TIMED_OUT,
        DialFailure.BUSY,
        DialFailure.NO_ANSWER,
    }
)

log = logging.getLogger("app.services.campaign_runner")

JsonObject = dict[str, Any]
ProgressHook = Callable[[CallOutcome], Awaitable[None]]
GatewayFactory = Callable[[], LiveKitGateway]


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
        trunk_id: str | None = None,
        voice_agent: JsonObject | None = None,
        gateway_factory: GatewayFactory | None = None,
        credit_ceiling: int | None = None,
        credits_used_before_run: int = 0,
    ) -> None:
        self.result_schema = result_schema
        # The verified LiveKit outbound trunk this run dials through - resolved
        # by the caller from the campaign's voice agent, the same way the
        # allowlist and suppression set are resolved once and passed in rather
        # than looked up per contact. `None` means no number is connected, and
        # every contact is refused with that reason rather than dialled.
        self._trunk_id = trunk_id
        # Which STT, TTS and LLM the worker runs this call on, and the keys for
        # each - resolved by the caller from the same voice agent `trunk_id`
        # came from. This travels to the worker verbatim under the
        # `voice_agent` metadata key, which is the *only* thing
        # `AgentSpec.from_metadata()` reads on the other side; the two names
        # have to match or every dispatched job dies resolving providers.
        self._voice_agent = voice_agent
        self._gateway_factory = gateway_factory or LiveKitGateway
        # Held open for the length of a `run()` so one batch shares a single
        # aiohttp session instead of opening one per contact.
        self._gateway: LiveKitGateway | None = None
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

    @asynccontextmanager
    async def _open_gateway(self) -> AsyncIterator[None]:
        """Hold one LiveKit session open for the block, if there is anything to dial.

        A no-op when no trunk is connected: constructing a gateway would raise
        on missing credentials, and refusing the whole run for that would hide
        the more useful per-contact "no number is connected" reason behind a
        configuration error.
        """
        if self._trunk_id is None:
            yield
            return

        self._gateway = self._gateway_factory()
        try:
            async with self._gateway:
                yield
        finally:
            self._gateway = None

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
            # The semaphore is held only around origination, not the progress
            # write below - that's our own database, and doesn't need to
            # compete for the same concurrency budget as the carrier.
            async with semaphore:
                outcome = await self.run_one(campaign, contact)
            if on_progress:
                await on_progress(outcome)
            return outcome

        # One session for the whole batch. Opening a gateway per contact would
        # mean an aiohttp session per call, and `wait_until_answered` holds each
        # one open for the length of a ring.
        async with self._open_gateway():
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

    async def run_one(self, campaign: Campaign, contact: Contact) -> CallOutcome:
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

        # A credit is only ever actually spent by a *connected* call. Every
        # early return below hands the reserved slot back, because none of them
        # reached a person - without that, a run with a credit ceiling burns a
        # credit per refused contact and eventually blocks later contacts for a
        # reason that never happened. The one path that keeps its credit is the
        # answered call at the bottom.
        async def release_credit() -> None:
            if reserved_credit:
                async with self._calls_made_lock:
                    self._credits_reserved -= 1

        if self._trunk_id is None:
            log.info("dial refused for %s - no connected number", mask(contact.phone))
            await release_credit()
            return base.model_copy(
                update={
                    "status": "FAILED",
                    "error": DialFailure.PROVIDER_UNAVAILABLE.value,
                    "disposition": Disposition.SKIPPED,
                    "disposition_reason": (
                        "This campaign has no connected number to call from. "
                        "Connect one to its voice agent, then start the run again."
                    ),
                }
            )

        # Refused here rather than discovered by the worker. Without a voice
        # agent the worker has no provider to resolve, so it would raise
        # `UnknownProvider` *after* the phone was already ringing - a person
        # saying "hello?" into silence. The gate belongs before the dial.
        if not self._voice_agent:
            log.info("dial refused for %s - no voice agent", mask(contact.phone))
            await release_credit()
            return base.model_copy(
                update={
                    "status": "FAILED",
                    "error": DialFailure.PROVIDER_UNAVAILABLE.value,
                    "disposition": Disposition.SKIPPED,
                    "disposition_reason": (
                        "This campaign's voice agent has no speech or language providers set. "
                        "Finish setting it up, then start the run again."
                    ),
                }
            )

        room = self._room_name(contact)
        # The rendered goal is what the agent worker is told to accomplish. It
        # is built here, where the campaign and contact are both in hand, and
        # travels to the worker as room metadata.
        goal = render_goal(campaign, contact)

        try:
            created = await self._originate(contact=contact, campaign=campaign, room=room, goal=goal)
        except EngineError as exc:
            failure = classify_error(exc)
            # `mask()` on the phone and `failure.value` rather than the
            # exception text: a vendor message can carry the dialled number or
            # internal hostnames, and this string reaches a user-facing field.
            log.warning("call failed for %s: %s", mask(contact.phone), failure.value)
            await release_credit()
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
        except Exception:
            # The exception's own message is logged in full but never
            # interpolated into a user-facing field - unlike a DialFailure
            # value, a raw exception string is untrusted content.
            log.exception("call failed for %s", mask(contact.phone))
            await release_credit()
            return base.model_copy(
                update={
                    "status": "FAILED",
                    "error": DialFailure.INTERNAL.value,
                    "disposition": Disposition.UNREACHABLE,
                    "disposition_reason": "Call could not be completed due to an internal error.",
                }
            )

        # Answered, not finished - and the only path that keeps its credit. The
        # worker is in the room having the conversation and will POST the
        # transcript and terminal status back when it ends (P1-T4); this row
        # stays IN_FLIGHT until it does.
        return base.model_copy(
            update={
                "status": "IN_PROGRESS",
                "run_id": created["sip_call_id"] or created["participant_id"],
                "disposition": Disposition.IN_FLIGHT,
                "disposition_reason": "In conversation…",
            }
        )

    def _room_name(self, contact: Contact) -> str:
        """The room the caller and the agent worker both join.

        Built from the run id and a hash of the number, never the number
        itself: a room name reaches LiveKit's logs, dashboards, and webhooks,
        all outside CallFlow's redaction (CLAUDE.md non-negotiable #5). It is
        deterministic so a retry of the same (run, contact) lands in the same
        room rather than starting a second conversation beside the first.
        """
        scope = self._run_id or "adhoc"
        return f"call-{scope}-{phone_hash(contact.phone)[:12]}"

    async def _originate(
        self, *, contact: Contact, campaign: Campaign, room: str, goal: str
    ) -> JsonObject:
        """Place the call, using the batch's gateway or a private one.

        `run_one()` is called directly as well as through `run()`, so it cannot
        assume the batch session exists.
        """
        assert self._trunk_id is not None  # guarded by the caller
        identity = f"contact-{phone_hash(contact.phone)[:12]}"

        # What the worker needs to hold the conversation and to attribute the
        # result. Deliberately no phone number: participant metadata is visible
        # to everything in the room and reaches LiveKit's logs and webhooks,
        # outside CallFlow's own redaction (CLAUDE.md non-negotiable #5). The
        # worker POSTs its result back keyed on `run_id`, and the API maps that
        # to the contact from its own records.
        # `contact_name` + `phone_masked` are how the worker's callback addresses
        # the row this call already created: `call_outcomes` is keyed on
        # (run_id, contact_name, phone_masked), so without them the completion
        # would insert a second row beside the in-flight one instead of
        # resolving it. The masked form is safe to send - it is the same value
        # the product displays, and masking is the guarantee (CLAUDE.md #4).
        # `contact.context` is spread **first**, so CallFlow's own keys win. It
        # is uploaded CSV columns - a column happening to be named `goal` would
        # otherwise rewrite the agent's instructions, and one named
        # `phone_masked` would misaddress the completion callback's row. The
        # customer's data is context for the conversation, never control of it.
        max_call_seconds = int(config.poll_timeout_seconds)
        metadata: JsonObject = {
            **contact.context,
            "goal": goal,
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "contact_name": contact.name,
            "phone_masked": mask(contact.phone),
            "result_schema": self.result_schema,
            "language": contact.language or campaign.language,
            # The key `AgentSpec.from_metadata()` reads. Both sides of this
            # contract live in this repo and are tested against each other
            # (`test_dispatch_contract.py`) - they were written apart once, and
            # every dispatched job died before its pipeline existed.
            "voice_agent": self._voice_agent,
            # The worker's own backstop for a call that connects and never
            # ends. Sent alongside the carrier-enforced ceiling below so both
            # halves agree rather than each inventing a number.
            "max_call_duration_seconds": max_call_seconds,
        }
        if self._run_id is not None:
            metadata["run_id"] = self._run_id

        kwargs: JsonObject = {
            "trunk_id": self._trunk_id,
            "phone": contact.phone,
            "room_name": room,
            "participant_identity": identity,
            "metadata": metadata,
            "max_call_duration_seconds": max_call_seconds,
        }

        if self._gateway is not None:
            return await self._gateway.start_call(**kwargs)

        async with self._gateway_factory() as gateway:
            return await gateway.start_call(**kwargs)

