"""Orchestrator behaviour: every run dials for real, guarded by the safety gate.

Origination goes through `LiveKitGateway`, which these tests supply as a stub -
the gateway's own translation of arguments and errors is covered in
`test_livekit_client.py`, so what is under test here is the orchestration: the
safety gate, the suppression check, the concurrency semaphore, idempotency keys,
and what a failure becomes.

**The ceiling and credit tests were removed, not lost.** The per-run ceiling,
the allowlist, the rate limiter, the daily budget and per-teammate credits were
deleted from `domain/safety.py` at the product owner's direction, pending a
replacement security layer - its module docstring is the record. Six tests here
outlived them and failed on arguments the dialler no longer accepts; a test for
a deleted feature asserts nothing, and leaving them red hides the next real
failure. They come back with the guards, against whatever shape those take
(`ISSUES.md` #178).

A runner with no `trunk_id` cannot dial at all and refuses every contact with
that reason, which is also the default in most tests below - they are asserting
guards that run *before* origination and should not need a fake carrier to do it.
"""

import asyncio
from typing import Any, Self

import pytest

from app.domain.entities import CallOutcome, Contact, DialFailure, Disposition, RunAgent
from app.domain.number_allocation import DialLine
from app.integrations.livekit.client import EngineError

# The agent these tests dial with, standing in for the deleted `TEST_AGENT`
# built-in campaign (now deleted).
TEST_AGENT = RunAgent(
    id="22222222-2222-4222-8222-222222222222",
    name="Orchestrator test agent",
    system_prompt="Ask {name} about their trip.",
)
from app.services.run_dialer import RunDialer

# A contact that clears the gate but cannot be dialled comes back FAILED; one
# the gate stops comes back BLOCKED. Both are SKIPPED - in neither case did a
# phone ring - so only `status` tells them apart.
UNDIALLABLE_STATUS = "FAILED"
BLOCKED_STATUS = "BLOCKED"
TRUNK = "ST_test_trunk"
# One verified line to dial from. A run takes a pool now, so the single-trunk
# case is just a pool of one - which is also the common case in production.
TEST_LINES = (DialLine(number_id="n1", phone_e164="+15555550100", outbound_trunk_id=TRUNK),)

# A dial needs a connected number *and* a configured agent - the trunk says
# which line to call from, this says what to run the conversation on. Both are
# resolved from the same voice agent, so a runner that has one and not the
# other is a caller bug, not a state the product reaches.
VOICE_AGENT = {
    "stt_provider": "sarvam",
    "tts_provider": "sarvam",
    "llm_provider": "openrouter",
    "llm_model": "openai/gpt-4o-mini",
}


class StubGateway:
    """Stands in for `LiveKitGateway`, recording what it was asked to dial."""

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.closed = False
        self._fail_with = fail_with

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        self.closed = True

    async def start_call(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self._fail_with is not None:
            raise self._fail_with
        return {
            "participant_id": "PA_1",
            "participant_identity": kwargs["participant_identity"],
            "room_name": kwargs["room_name"],
            "sip_call_id": "SCL_1",
        }


def _dialling_runner(gateway: StubGateway | None = None, **kwargs: Any) -> tuple[RunDialer, StubGateway]:
    stub = gateway or StubGateway()
    kwargs.setdefault("voice_agent", VOICE_AGENT)
    runner = RunDialer(lines=TEST_LINES, gateway_factory=lambda: stub, **kwargs)
    return runner, stub


def _twirp(code: str, *, sip_status: int | None = None) -> EngineError:
    metadata = {} if sip_status is None else {"sip_status_code": str(sip_status)}
    return EngineError(code, "stub failure", status=500, metadata=metadata)






def test_invalid_phone_rejected_at_model_level() -> None:
    with pytest.raises(ValueError):
        Contact(name="Bad", phone="5555550100")


async def test_a_run_with_no_connected_number_is_refused_with_that_reason() -> None:
    """Never a silent no-op, and never a generic complaint: the reason names the
    thing the operator has to go and do (CLAUDE.md non-negotiable #9, §5)."""
    runner = RunDialer()
    contact = Contact(name="Aditi", phone="+15555550100", context={"enquiry_note": "Bali"})

    result = await runner.run_one(TEST_AGENT, contact)

    assert result.status == UNDIALLABLE_STATUS
    assert result.error == "provider_unavailable"
    assert result.disposition is Disposition.SKIPPED
    assert "no verified number" in (result.disposition_reason or "")
    # Masking is a guarantee that does not depend on who places the call.
    assert "5555550" not in result.phone_masked


async def test_an_answered_call_is_reported_in_flight_not_finished() -> None:
    """LiveKit is not request/response: origination returns when the call is
    answered, and the worker reports the transcript later. A terminal status
    here would be claiming an outcome nobody has yet."""
    runner, _ = _dialling_runner()
    contact = Contact(name="Aditi", phone="+15555550100")

    result = await runner.run_one(TEST_AGENT, contact)

    assert result.status == "IN_PROGRESS"
    assert result.disposition is Disposition.IN_FLIGHT
    assert result.run_id == "SCL_1"


async def test_the_dial_carries_the_rendered_prompt_to_the_worker() -> None:
    """The worker has no database access - the goal reaches it as metadata or
    it has nothing to talk about."""
    runner, stub = _dialling_runner(run_id="run_abc")
    contact = Contact(name="Aditi", phone="+15555550100", context={"enquiry_note": "Bali"})

    await runner.run_one(TEST_AGENT, contact)

    metadata = stub.calls[0]["metadata"]
    assert "Aditi" in metadata["prompt"]
    assert "Bali" in metadata["prompt"]
    assert metadata["voice_agent_id"] == TEST_AGENT.id
    assert metadata["run_id"] == "run_abc"


async def test_no_phone_number_ever_reaches_room_name_identity_or_metadata() -> None:
    """All three cross into LiveKit's logs, dashboards and webhooks, outside
    CallFlow's redaction filter (CLAUDE.md non-negotiable #5)."""
    runner, stub = _dialling_runner(run_id="run_abc")
    contact = Contact(name="Aditi", phone="+15555550100", context={"note": "call back"})

    await runner.run_one(TEST_AGENT, contact)

    call = stub.calls[0]
    leaked = "5555550100"
    assert leaked not in call["room_name"]
    assert leaked not in call["participant_identity"]
    assert leaked not in str(call["metadata"])
    # The number itself still has to reach the carrier, of course.
    assert call["phone"] == "+15555550100"


async def test_the_room_name_is_stable_for_the_same_run_and_contact() -> None:
    """A retry must land in the same room rather than opening a second
    conversation beside the first."""
    runner, stub = _dialling_runner(run_id="run_abc")
    contact = Contact(name="Aditi", phone="+15555550100")

    await runner.run_one(TEST_AGENT, contact)
    await runner.run_one(TEST_AGENT, contact)

    assert stub.calls[0]["room_name"] == stub.calls[1]["room_name"]


async def test_two_contacts_get_different_rooms() -> None:
    runner, stub = _dialling_runner(run_id="run_abc")

    await runner.run_one(TEST_AGENT, Contact(name="A", phone="+15555550100"))
    await runner.run_one(TEST_AGENT, Contact(name="B", phone="+15555550101"))

    assert stub.calls[0]["room_name"] != stub.calls[1]["room_name"]


async def test_a_call_carries_a_hard_duration_ceiling() -> None:
    """Enforced by the carrier, so a wedged worker cannot bill for a call that
    never ends."""
    runner, stub = _dialling_runner()
    await runner.run_one(TEST_AGENT, Contact(name="A", phone="+15555550100"))

    assert stub.calls[0]["max_call_duration_seconds"] > 0


@pytest.mark.parametrize(
    "sip_status,expected_error,retryable",
    [
        (486, DialFailure.BUSY, True),
        (480, DialFailure.NO_ANSWER, True),
        (404, DialFailure.INVALID_NUMBER, False),
        (403, DialFailure.UNAUTHORIZED, False),
    ],
)
async def test_a_carrier_failure_is_classified_not_swallowed(
    sip_status: int, expected_error: DialFailure, retryable: bool
) -> None:
    """The point of the taxonomy: an operator can tell "call them back later"
    apart from "this number is wrong", instead of both reading as one failure."""
    runner, _ = _dialling_runner(StubGateway(fail_with=_twirp("internal", sip_status=sip_status)))

    result = await runner.run_one(TEST_AGENT, Contact(name="A", phone="+15555550100"))

    assert result.status == "FAILED"
    assert result.error == expected_error.value
    assert result.disposition is (Disposition.RETRY if retryable else Disposition.UNREACHABLE)


async def test_a_vendor_error_message_never_reaches_a_user_facing_field() -> None:
    """A vendor string can carry the dialled number or internal hostnames."""
    exc = EngineError(
        "internal", "call to +15555550100 via sip.internal.example failed", status=500
    )
    runner, _ = _dialling_runner(StubGateway(fail_with=exc))

    result = await runner.run_one(TEST_AGENT, Contact(name="A", phone="+15555550100"))

    assert "5555550100" not in (result.disposition_reason or "")
    assert "sip.internal.example" not in (result.disposition_reason or "")


async def test_a_non_vendor_exception_still_fails_closed() -> None:
    runner, _ = _dialling_runner(StubGateway(fail_with=ConnectionError("dns lookup failed")))

    result = await runner.run_one(TEST_AGENT, Contact(name="A", phone="+15555550100"))

    assert result.error == DialFailure.INTERNAL.value
    assert result.disposition is Disposition.UNREACHABLE
    assert "dns lookup failed" not in (result.disposition_reason or "")


async def test_a_blocked_contact_is_never_dialled() -> None:
    """The gate runs before origination, so a suppressed number must not reach
    the carrier at all - not merely be discarded afterwards."""
    from app.domain.safety import phone_hash

    contact = Contact(name="A", phone="+15555550100")
    runner, stub = _dialling_runner(suppressed_hashes=frozenset({phone_hash(contact.phone)}))

    result = await runner.run_one(TEST_AGENT, contact)

    assert result.status == BLOCKED_STATUS
    assert stub.calls == []


async def test_one_session_is_shared_across_a_whole_batch() -> None:
    """A gateway per contact would mean an aiohttp session per call, each held
    open for the length of a ring."""
    runner, stub = _dialling_runner()
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(4)]

    await runner.run(TEST_AGENT, contacts)

    assert len(stub.calls) == 4
    assert stub.closed is True


def test_idempotency_key_is_stable_across_retries_of_the_same_run_and_contact() -> None:
    # The entire point of Idempotency-Key: a retry of the same logical attempt
    # (same run, same contact) must reuse the same key, so the provider can
    # recognise a duplicate instead of placing a second real call (#54).
    # Asserted against the key builder directly rather than through a fake
    # provider - the key is ours, and must survive swapping who dials.
    runner = RunDialer(run_id="run_abc123")
    contact = Contact(name="A", phone="+15555550100")

    assert runner._idempotency_key(TEST_AGENT, contact) == runner._idempotency_key(
        TEST_AGENT, contact
    )


def test_idempotency_key_differs_across_different_runs_for_the_same_contact() -> None:
    # An old run's key must never be replayable against a new one.
    contact = Contact(name="A", phone="+15555550100")

    one = RunDialer(run_id="run_one")._idempotency_key(TEST_AGENT, contact)
    two = RunDialer(run_id="run_two")._idempotency_key(TEST_AGENT, contact)

    assert one != two


def test_idempotency_key_never_contains_the_raw_phone_number() -> None:
    runner = RunDialer(run_id="run_abc123")
    key = runner._idempotency_key(TEST_AGENT, Contact(name="A", phone="+15555550100"))

    assert "5555550100" not in key


def test_idempotency_key_falls_back_to_a_fresh_one_without_a_run_id() -> None:
    # No real run means no stable job identity to key off of - not idempotent,
    # but no worse than the behaviour this replaces.
    runner = RunDialer()
    contact = Contact(name="A", phone="+15555550100")

    assert runner._idempotency_key(TEST_AGENT, contact) != runner._idempotency_key(
        TEST_AGENT, contact
    )


async def test_suppressed_number_is_blocked() -> None:
    from app.domain.safety import phone_hash

    contact = Contact(name="A", phone="+15555550100")
    runner = RunDialer(suppressed_hashes=frozenset({phone_hash(contact.phone)}))
    result = await runner.run_one(TEST_AGENT, contact)
    assert result.status == BLOCKED_STATUS
    assert result.disposition is Disposition.SKIPPED
    assert "suppression" in (result.disposition_reason or "")


async def test_run_processes_every_contact() -> None:
    runner = RunDialer()
    contacts = [
        Contact(name="A", phone="+15555550100"),
        Contact(name="B", phone="+15555550101"),
    ]
    assert len(await runner.run(TEST_AGENT, contacts)) == 2


async def test_progress_hook_fires_once_per_contact() -> None:
    """`run()` must report every contact's resolved outcome through the hook,
    which is how the dashboard row gets written at all. The extra in-flight
    event a live call also emits comes back with origination (P1-T6)."""
    seen: list[tuple[str, str]] = []
    runner = RunDialer()

    async def on_progress(outcome: Any) -> None:
        seen.append((outcome.contact_name, outcome.status))

    await runner.run(
        TEST_AGENT,
        [Contact(name="A", phone="+15555550100"), Contact(name="B", phone="+15555550101")],
        on_progress=on_progress,
    )
    assert sorted(seen) == [("A", UNDIALLABLE_STATUS), ("B", UNDIALLABLE_STATUS)]


class _ConcurrencyProbe:
    """Stands in for `run_one` to observe how many contacts `run()` has in
    flight at once. Patched onto the instance rather than faking a provider:
    the semaphore lives in `run()` and is ours, so this stays true no matter
    who ends up placing the call.
    """

    def __init__(self, runner: RunDialer) -> None:
        self._real = runner.run_one
        self.in_flight = 0
        self.peak_in_flight = 0

    async def __call__(self, *args: Any, **kwargs: Any) -> CallOutcome:
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.02)
            return await self._real(*args, **kwargs)
        finally:
            self.in_flight -= 1


async def test_run_dials_contacts_concurrently_not_one_at_a_time() -> None:
    runner = RunDialer(max_concurrent_calls=3)
    probe = _ConcurrencyProbe(runner)
    runner.run_one = probe  # type: ignore[method-assign]
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(5)]

    await runner.run(TEST_AGENT, contacts)

    assert probe.peak_in_flight > 1


async def test_run_never_exceeds_the_configured_concurrency_limit() -> None:
    runner = RunDialer(max_concurrent_calls=2)
    probe = _ConcurrencyProbe(runner)
    runner.run_one = probe  # type: ignore[method-assign]
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(6)]

    await runner.run(TEST_AGENT, contacts)

    assert probe.peak_in_flight <= 2


async def test_an_unanswered_call_is_not_credited_as_connected() -> None:
    result = await RunDialer().run_one(TEST_AGENT, Contact(name="A", phone="+15555550100"))
    assert result.answered is False


async def test_run_preserves_input_order_regardless_of_completion_order() -> None:
    runner = RunDialer(max_concurrent_calls=5)
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(5)]

    outcomes = await runner.run(TEST_AGENT, contacts)

    assert [o.contact_name for o in outcomes] == [c.name for c in contacts]






def _attempt(
    status: str,
    turns: list[dict[str, Any]] | None = None,
    *,
    started_at: str | None = None,
) -> dict[str, Any]:
    """A `CallTaskAttempt`-shaped fixture - every field the generated SDK
    model has, not just the ones today's assertions read, so a fixture that
    claims to match the real shape actually does."""
    return {
        "id": "attempt_1",
        "phone": "+15555550100",
        "status": status,
        "started_at": started_at,
        "completed_at": None,
        "summary": None,
        "transcript_turns": turns or [],
        "provider_call_id": None,
        "failure_code": None,
        "failure_message": None,
    }


























def _base() -> CallOutcome:
    return CallOutcome(contact_name="A", phone_masked="+91***210")






