"""Run orchestration: contacts in, typed outcomes out.

Flow per contact:
    safety gate -> allocate a line -> render the prompt -> originate -> report in flight

Only the orchestration itself lives here - I/O, concurrency, the safety gate.
Prompt assembly is `app/domain/prompt_assembly.py`, which line places the call is
`app/domain/number_allocation.py`, and post-call triage is
`app/domain/triage.py`. Split per CLAUDE.md's Single-Responsibility guidance -
none of that logic does any I/O, so it belongs in `domain/`, not here.

Formerly `campaign_runner.CampaignRunner`. A run is an *agent* dialling a list
from the organisation's own numbers now (ADR-8): the agent owns the instruction
and the fields to collect, where a campaign used to own a goal template and a
result schema.

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
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Sequence
from contextlib import asynccontextmanager
from typing import Any

from app.core.config import config
from app.domain.entities import CallOutcome, Contact, DialFailure, Disposition, RunAgent
from app.domain.number_allocation import DialLine, build_allocator
from app.domain.prompt_assembly import (
    PromptContact,
    render_call_prompt,
    visible_context,
)
from app.domain.safety import check_dial_allowed, mask, phone_hash
from app.integrations.livekit.client import EngineError, LiveKitGateway, classify_error

# Failures worth trying again, not treating as "this number doesn't work": the
# carrier said this is a transient condition rather than something wrong with
# the number or the request itself. A fresh call attempt against a
# number/request that's genuinely invalid or blocked should not be retried, per
# CLAUDE.md's fail-closed rule for anything that places a call.
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

log = logging.getLogger("app.services.run_dialer")

JsonObject = dict[str, Any]
ProgressHook = Callable[[CallOutcome], Awaitable[None]]
GatewayFactory = Callable[[], LiveKitGateway]
StopCheck = Callable[[], Awaitable[bool]]


class RunDialer:
    def __init__(
        self,
        *,
        result_schema: JsonObject | None = None,
        suppressed_hashes: frozenset[str] = frozenset(),
        run_id: str | None = None,
        max_concurrent_calls: int | None = None,
        voice_agent: JsonObject | None = None,
        gateway_factory: GatewayFactory | None = None,
        lines: Sequence[DialLine] | None = None,
        allocation_strategy: str = "round_robin",
        run_instruction: str | None = None,
        should_stop: StopCheck | None = None,
    ) -> None:
        self.result_schema = result_schema
        # The verified lines this run may dial from, resolved once by the caller
        # the same way the suppression set is, rather than looked
        # up per contact. Empty means nothing is connected and every contact is
        # refused with that reason rather than dialled.
        #
        # A pool rather than one trunk because an organisation holds several
        # numbers precisely so no single line carries a whole run - see
        # `domain/number_allocation.py`.
        self._lines = tuple(lines or ())
        self._allocator = (
            build_allocator(allocation_strategy, self._lines) if self._lines else None
        )
        # Appended to every prompt in this run, so a one-off instruction does not
        # mean editing an agent the whole organisation shares.
        self._run_instruction = run_instruction
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
        # The persisted run this instance belongs to, if any - gives each
        # contact's idempotency key a stable scope (see `run_one()`). `None`
        # for a caller with no real run (ad hoc use, tests).
        self._run_id = run_id
        self._max_concurrent_calls = (
            max_concurrent_calls if max_concurrent_calls is not None else config.max_concurrent_calls
        )
        # Asked once per contact, immediately before that contact is dialled.
        # An awaitable predicate rather than a flag, so this module keeps its
        # no-database property: the caller owns where the answer comes from
        # (`services/run_control.StopSignal` reads it from `runs`), and a test
        # passes a plain lambda. `None` means nothing can stop this run, which
        # is the right default for the ad-hoc and test callers that have no
        # persisted run to stop.
        self._should_stop = should_stop

    @asynccontextmanager
    async def _open_gateway(self) -> AsyncIterator[None]:
        """Hold one LiveKit session open for the block, if there is anything to dial.

        A no-op when no line is connected: constructing a gateway would raise
        on missing credentials, and refusing the whole run for that would hide
        the more useful per-contact "no number is connected" reason behind a
        configuration error.
        """
        if not self._lines:
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
        agent: RunAgent,
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
                # Checked *inside* the semaphore, which is the only place it
                # works. Every contact's task is created up front by the
                # `gather` below and then queues here, so a contact that has
                # been waiting twenty minutes for a slot asks about the stop
                # now rather than having decided before the button existed.
                if await self._stop_requested():
                    outcome = self._stopped_outcome(agent, contact)
                else:
                    outcome = await self.run_one(agent, contact)
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
                        voice_agent_id=agent.id,
                        status="FAILED",
                        error=DialFailure.INTERNAL.value,
                        disposition=Disposition.UNREACHABLE,
                        disposition_reason="Call could not be completed due to an internal error.",
                    )
                )
            else:
                outcomes.append(result)
        return outcomes

    async def _stop_requested(self) -> bool:
        """Whether this run has been asked to stop.

        Swallows a failing check rather than letting it abort the contact: the
        predicate reaches the network, and a run must not lose a contact because
        the question "should I stop?" could not be answered. `StopSignal` already
        makes the same call for the same reason; this is the backstop for any
        other predicate a caller passes in.
        """
        if self._should_stop is None:
            return False
        try:
            return await self._should_stop()
        except Exception:  # noqa: BLE001 - a failed stop check must not drop the contact
            log.warning("stop check failed for run %s - continuing to dial", self._run_id)
            return False

    def _stopped_outcome(self, agent: RunAgent, contact: Contact) -> CallOutcome:
        """The row for a contact the stop reached before the dialler did.

        Written as a real settled outcome rather than left absent, and the
        distinction matters twice over. It keeps `total` reachable, so
        `finish_if_all_settled` can close the run instead of leaving it open
        forever waiting for contacts that will never be dialled. And it says
        plainly that this person was not called - a run that quietly shrinks its
        own target would report success for 12 of 50 contacts (CLAUDE.md
        non-negotiable #9).

        BLOCKED/SKIPPED is the same shape a suppressed contact takes: deliberately
        not dialled, as opposed to dialled and failed. The error code is distinct
        from the crash sweep's `never_dialled` so the two are tellable apart -
        one is a person's decision, the other is a dead dispatcher.
        """
        return CallOutcome(
            contact_name=contact.name,
            phone_masked=mask(contact.phone),
            voice_agent_id=agent.id,
            status="BLOCKED",
            error="run_stopped",
            disposition=Disposition.SKIPPED,
            disposition_reason="The run was stopped before this contact was dialled.",
        )

    def _idempotency_key(self, agent: RunAgent, contact: Contact) -> str:
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
            return f"{agent.id}-{contact.phone}-{uuid.uuid4().hex[:8]}"
        return f"{self._run_id}:{phone_hash(contact.phone)}"

    async def run_one(self, agent: RunAgent, contact: Contact) -> CallOutcome:
        base = CallOutcome(
            contact_name=contact.name,
            phone_masked=mask(contact.phone),
            voice_agent_id=agent.id,
            # The suppression key for this number, recorded now because this is
            # the last point anything holds the real one. The completion
            # callback sees only the masked form, so without this a contact who
            # asks never to be called again could be escalated but never
            # actually suppressed (`f3c7b21a9d04`).
            phone_hash=phone_hash(contact.phone),
        )

        # --- Suppression gate: fails closed, runs before anything can dial. --
        # The lock still matters, but only for allocation now: round-robin
        # advances a shared cursor, so two contacts dialled concurrently would
        # otherwise race for the same line and the even distribution this exists
        # to guarantee would not hold. The per-run ceiling and credit
        # reservation this block used to hold were removed with the rest of the
        # cost guards (`domain/safety.py`'s module docstring).
        gate = check_dial_allowed(
            contact.phone,
            is_suppressed=phone_hash(contact.phone) in self._suppressed_hashes,
        )
        line: DialLine | None = None
        if gate.allowed:
            async with self._calls_made_lock:
                self._calls_made += 1
                if self._allocator is not None:
                    line = self._allocator.next_for(contact.phone)

        if not gate.allowed:
            return base.model_copy(
                update={
                    "status": "BLOCKED",
                    "disposition": Disposition.SKIPPED,
                    "disposition_reason": gate.reason,
                }
            )

        if not self._lines or self._allocator is None:
            log.info("dial refused for %s - no verified number", mask(contact.phone))
            return base.model_copy(
                update={
                    "status": "FAILED",
                    "error": DialFailure.PROVIDER_UNAVAILABLE.value,
                    "disposition": Disposition.SKIPPED,
                    "disposition_reason": (
                        "This run has no verified number to call from. "
                        "Connect one in Integrations, then pick it when you start the run."
                    ),
                }
            )

        # Refused here rather than discovered by the worker. Without a voice
        # agent the worker has no provider to resolve, so it would raise
        # `UnknownProvider` *after* the phone was already ringing - a person
        # saying "hello?" into silence. The gate belongs before the dial.
        if not self._voice_agent:
            log.info("dial refused for %s - no voice agent", mask(contact.phone))
            return base.model_copy(
                update={
                    "status": "FAILED",
                    "error": DialFailure.PROVIDER_UNAVAILABLE.value,
                    "disposition": Disposition.SKIPPED,
                    "disposition_reason": (
                        "This run's agent has no speech or language providers set. "
                        "Finish setting it up, then start the run again."
                    ),
                }
            )

        room = self._room_name(contact)
        # What the agent worker is told. Built here, where the agent and the
        # contact are both in hand, and travelling to the worker as room
        # metadata - so each person hears about their own case.
        prompt = render_call_prompt(
            system_prompt=agent.system_prompt,
            contact=PromptContact(name=contact.name, context=contact.context),
            collect_fields=agent.collect_fields,
            run_instruction=self._run_instruction,
        )

        try:
            created = await self._originate(
                contact=contact, agent=agent, room=room, prompt=prompt, line=line
            )
        except EngineError as exc:
            failure = classify_error(exc)
            # `mask()` on the phone and `failure.value` rather than the
            # exception text: a vendor message can carry the dialled number or
            # internal hostnames, and this string reaches a user-facing field.
            log.warning("call failed for %s: %s", mask(contact.phone), failure.value)
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
            return base.model_copy(
                update={
                    "status": "FAILED",
                    "error": DialFailure.INTERNAL.value,
                    "disposition": Disposition.UNREACHABLE,
                    "disposition_reason": "Call could not be completed due to an internal error.",
                }
            )

        # Answered, not finished. The
        # worker is in the room having the conversation and will POST the
        # transcript and terminal status back when it ends (P1-T4); this row
        # stays IN_FLIGHT until it does.
        return base.model_copy(
            update={
                "status": "IN_PROGRESS",
                "run_id": created["sip_call_id"] or created["participant_id"],
                "disposition": Disposition.IN_FLIGHT,
                "disposition_reason": "In conversation…",
                # Masked, because this row is read back to a person and a full
                # number is a separate permissioned reveal (CLAUDE.md #4). A run
                # spread across several lines is exactly when "which number
                # called them?" is a question worth being able to answer.
                "from_number_masked": mask(line.phone_e164) if line else None,
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
        self,
        *,
        contact: Contact,
        agent: RunAgent,
        room: str,
        prompt: str,
        line: DialLine | None,
    ) -> JsonObject:
        """Place the call, using the batch's gateway or a private one.

        `run_one()` is called directly as well as through `run()`, so it cannot
        assume the batch session exists.
        """
        assert line is not None  # guarded by the caller
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
            # Stripped as well as spread first. Spreading first protects the keys
            # this dict goes on to set, but `goal` was renamed to `prompt`, so a
            # hostile column called `goal` stopped colliding with anything and
            # simply rode along - inert today, and exactly the kind of thing that
            # becomes live again when a future reader adds a `goal` key back.
            # `visible_context` is the one list both this and the prompt strip
            # against, so the two cannot drift.
            **visible_context(contact.context),
            "prompt": prompt,
            "voice_agent_id": agent.id,
            "agent_name": agent.name,
            "contact_name": contact.name,
            "phone_masked": mask(contact.phone),
            "result_schema": self.result_schema,
            # The same field list the prompt renders, as data the worker can
            # build a `record_field` tool from. Sent rather than re-derived so
            # what the agent is asked for and what it can record cannot drift.
            # The reserved key is `collect_schema`, so a spreadsheet column by
            # that name is already stripped upstream.
            "collect_schema": [f.model_dump() for f in agent.collect_fields],
            "language": contact.language or agent.language,
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
            "trunk_id": line.outbound_trunk_id,
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

