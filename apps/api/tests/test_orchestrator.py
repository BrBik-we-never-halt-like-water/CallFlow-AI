"""Orchestrator behaviour: every run dials for real, guarded by the safety gate.

Origination goes through `LiveKitGateway`, which these tests supply as a stub -
the gateway's own translation of arguments and errors is covered in
`test_livekit_client.py`, so what is under test here is the orchestration: the
safety gate, the check-and-reserve ceiling, the suppression check, the
concurrency semaphore, idempotency keys, and what a failure becomes.

A runner with no `trunk_id` cannot dial at all and refuses every contact with
that reason, which is also the default in most tests below - they are asserting
guards that run *before* origination and should not need a fake carrier to do it.
"""

import asyncio
from typing import Any, Self

import pytest

from app.domain.campaigns import TRAVEL_DISCOVERY
from app.domain.entities import CallOutcome, Contact, DialFailure, Disposition
from app.domain.goal_rendering import render_goal
from app.domain.outcome_extraction import (
    _extract_attempts,
    _extract_result,
    _extract_transcript,
    _resolve_outcome,
)
from app.integrations.livekit.client import EngineError
from app.services.campaign_runner import CampaignRunner

# A contact that clears the gate but cannot be dialled comes back FAILED; one
# the gate stops comes back BLOCKED. Both are SKIPPED - in neither case did a
# phone ring - so only `status` tells them apart.
UNDIALLABLE_STATUS = "FAILED"
BLOCKED_STATUS = "BLOCKED"
TRUNK = "ST_test_trunk"


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


def _dialling_runner(gateway: StubGateway | None = None, **kwargs: Any) -> tuple[CampaignRunner, StubGateway]:
    stub = gateway or StubGateway()
    runner = CampaignRunner(trunk_id=TRUNK, gateway_factory=lambda: stub, **kwargs)
    return runner, stub


def _twirp(code: str, *, sip_status: int | None = None) -> EngineError:
    metadata = {} if sip_status is None else {"sip_status_code": str(sip_status)}
    return EngineError(code, "stub failure", status=500, metadata=metadata)


def test_render_goal_substitutes_contact_fields() -> None:
    contact = Contact(name="Aditi", phone="+15555550100", context={"enquiry_note": "Bali"})
    goal = render_goal(TRAVEL_DISCOVERY, contact)
    assert "Aditi" in goal
    assert "Bali" in goal


def test_render_goal_tolerates_missing_context_key() -> None:
    # A contact with no enquiry_note must not crash the whole campaign.
    contact = Contact(name="Rahul", phone="+15555550101")
    goal = render_goal(TRAVEL_DISCOVERY, contact)
    assert "Rahul" in goal
    assert "{enquiry_note}" not in goal


def test_invalid_phone_rejected_at_model_level() -> None:
    with pytest.raises(ValueError):
        Contact(name="Bad", phone="5555550100")


async def test_a_campaign_with_no_connected_number_is_refused_with_that_reason() -> None:
    """Never a silent no-op, and never a generic complaint: the reason names the
    thing the operator has to go and do (CLAUDE.md non-negotiable #9, §5)."""
    runner = CampaignRunner()
    contact = Contact(name="Aditi", phone="+15555550100", context={"enquiry_note": "Bali"})

    result = await runner.run_one(TRAVEL_DISCOVERY, contact)

    assert result.status == UNDIALLABLE_STATUS
    assert result.error == "provider_unavailable"
    assert result.disposition is Disposition.SKIPPED
    assert "no connected number" in (result.disposition_reason or "")
    # Masking is a guarantee that does not depend on who places the call.
    assert "5555550" not in result.phone_masked


async def test_an_answered_call_is_reported_in_flight_not_finished() -> None:
    """LiveKit is not request/response: origination returns when the call is
    answered, and the worker reports the transcript later. A terminal status
    here would be claiming an outcome nobody has yet."""
    runner, _ = _dialling_runner()
    contact = Contact(name="Aditi", phone="+15555550100")

    result = await runner.run_one(TRAVEL_DISCOVERY, contact)

    assert result.status == "IN_PROGRESS"
    assert result.disposition is Disposition.IN_FLIGHT
    assert result.run_id == "SCL_1"


async def test_the_dial_carries_the_rendered_goal_to_the_worker() -> None:
    """The worker has no database access - the goal reaches it as metadata or
    it has nothing to talk about."""
    runner, stub = _dialling_runner(run_id="run_abc")
    contact = Contact(name="Aditi", phone="+15555550100", context={"enquiry_note": "Bali"})

    await runner.run_one(TRAVEL_DISCOVERY, contact)

    metadata = stub.calls[0]["metadata"]
    assert "Aditi" in metadata["goal"]
    assert "Bali" in metadata["goal"]
    assert metadata["campaign_id"] == TRAVEL_DISCOVERY.id
    assert metadata["run_id"] == "run_abc"


async def test_no_phone_number_ever_reaches_room_name_identity_or_metadata() -> None:
    """All three cross into LiveKit's logs, dashboards and webhooks, outside
    CallFlow's redaction filter (CLAUDE.md non-negotiable #5)."""
    runner, stub = _dialling_runner(run_id="run_abc")
    contact = Contact(name="Aditi", phone="+15555550100", context={"note": "call back"})

    await runner.run_one(TRAVEL_DISCOVERY, contact)

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
    runner, stub = _dialling_runner(run_id="run_abc", max_calls_per_run=5)
    contact = Contact(name="Aditi", phone="+15555550100")

    await runner.run_one(TRAVEL_DISCOVERY, contact)
    await runner.run_one(TRAVEL_DISCOVERY, contact)

    assert stub.calls[0]["room_name"] == stub.calls[1]["room_name"]


async def test_two_contacts_get_different_rooms() -> None:
    runner, stub = _dialling_runner(run_id="run_abc", max_calls_per_run=5)

    await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    await runner.run_one(TRAVEL_DISCOVERY, Contact(name="B", phone="+15555550101"))

    assert stub.calls[0]["room_name"] != stub.calls[1]["room_name"]


async def test_a_call_carries_a_hard_duration_ceiling() -> None:
    """Enforced by the carrier, so a wedged worker cannot bill for a call that
    never ends."""
    runner, stub = _dialling_runner()
    await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

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

    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert result.status == "FAILED"
    assert result.error == expected_error.value
    assert result.disposition is (Disposition.RETRY if retryable else Disposition.UNREACHABLE)


async def test_a_vendor_error_message_never_reaches_a_user_facing_field() -> None:
    """A vendor string can carry the dialled number or internal hostnames."""
    exc = EngineError(
        "internal", "call to +15555550100 via sip.internal.example failed", status=500
    )
    runner, _ = _dialling_runner(StubGateway(fail_with=exc))

    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert "5555550100" not in (result.disposition_reason or "")
    assert "sip.internal.example" not in (result.disposition_reason or "")


async def test_a_non_vendor_exception_still_fails_closed() -> None:
    runner, _ = _dialling_runner(StubGateway(fail_with=ConnectionError("dns lookup failed")))

    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert result.error == DialFailure.INTERNAL.value
    assert result.disposition is Disposition.UNREACHABLE
    assert "dns lookup failed" not in (result.disposition_reason or "")


async def test_a_blocked_contact_is_never_dialled() -> None:
    """The gate runs before origination, so a suppressed number must not reach
    the carrier at all - not merely be discarded afterwards."""
    from app.domain.safety import phone_hash

    contact = Contact(name="A", phone="+15555550100")
    runner, stub = _dialling_runner(suppressed_hashes=frozenset({phone_hash(contact.phone)}))

    result = await runner.run_one(TRAVEL_DISCOVERY, contact)

    assert result.status == BLOCKED_STATUS
    assert stub.calls == []


async def test_one_session_is_shared_across_a_whole_batch() -> None:
    """A gateway per contact would mean an aiohttp session per call, each held
    open for the length of a ring."""
    runner, stub = _dialling_runner(max_calls_per_run=5)
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(4)]

    await runner.run(TRAVEL_DISCOVERY, contacts)

    assert len(stub.calls) == 4
    assert stub.closed is True


async def test_ceiling_blocks_further_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    import dataclasses

    from app.domain import safety

    # Config is frozen, so swap in a replaced copy rather than mutating it.
    monkeypatch.setattr(safety, "config", dataclasses.replace(safety.config, max_calls_per_run=0))
    runner = CampaignRunner()
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    assert result.status == BLOCKED_STATUS
    assert result.disposition is Disposition.SKIPPED


def test_idempotency_key_is_stable_across_retries_of_the_same_run_and_contact() -> None:
    # The entire point of Idempotency-Key: a retry of the same logical attempt
    # (same run, same contact) must reuse the same key, so the provider can
    # recognise a duplicate instead of placing a second real call (#54).
    # Asserted against the key builder directly rather than through a fake
    # provider - the key is ours, and must survive swapping who dials.
    runner = CampaignRunner(run_id="run_abc123")
    contact = Contact(name="A", phone="+15555550100")

    assert runner._idempotency_key(TRAVEL_DISCOVERY, contact) == runner._idempotency_key(
        TRAVEL_DISCOVERY, contact
    )


def test_idempotency_key_differs_across_different_runs_for_the_same_contact() -> None:
    # An old run's key must never be replayable against a new one.
    contact = Contact(name="A", phone="+15555550100")

    one = CampaignRunner(run_id="run_one")._idempotency_key(TRAVEL_DISCOVERY, contact)
    two = CampaignRunner(run_id="run_two")._idempotency_key(TRAVEL_DISCOVERY, contact)

    assert one != two


def test_idempotency_key_never_contains_the_raw_phone_number() -> None:
    runner = CampaignRunner(run_id="run_abc123")
    key = runner._idempotency_key(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert "5555550100" not in key


def test_idempotency_key_falls_back_to_a_fresh_one_without_a_run_id() -> None:
    # No real run means no stable job identity to key off of - not idempotent,
    # but no worse than the behaviour this replaces.
    runner = CampaignRunner()
    contact = Contact(name="A", phone="+15555550100")

    assert runner._idempotency_key(TRAVEL_DISCOVERY, contact) != runner._idempotency_key(
        TRAVEL_DISCOVERY, contact
    )


async def test_suppressed_number_is_blocked() -> None:
    from app.domain.safety import phone_hash

    contact = Contact(name="A", phone="+15555550100")
    runner = CampaignRunner(suppressed_hashes=frozenset({phone_hash(contact.phone)}))
    result = await runner.run_one(TRAVEL_DISCOVERY, contact)
    assert result.status == BLOCKED_STATUS
    assert result.disposition is Disposition.SKIPPED
    assert "suppression" in (result.disposition_reason or "")


async def test_run_processes_every_contact() -> None:
    runner = CampaignRunner()
    contacts = [
        Contact(name="A", phone="+15555550100"),
        Contact(name="B", phone="+15555550101"),
    ]
    assert len(await runner.run(TRAVEL_DISCOVERY, contacts)) == 2


async def test_progress_hook_fires_once_per_contact() -> None:
    """`run()` must report every contact's resolved outcome through the hook,
    which is how the dashboard row gets written at all. The extra in-flight
    event a live call also emits comes back with origination (P1-T6)."""
    seen: list[tuple[str, str]] = []
    runner = CampaignRunner()

    async def on_progress(outcome: Any) -> None:
        seen.append((outcome.contact_name, outcome.status))

    await runner.run(
        TRAVEL_DISCOVERY,
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

    def __init__(self, runner: CampaignRunner) -> None:
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
    runner = CampaignRunner(max_concurrent_calls=3)
    probe = _ConcurrencyProbe(runner)
    runner.run_one = probe  # type: ignore[method-assign]
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(5)]

    await runner.run(TRAVEL_DISCOVERY, contacts)

    assert probe.peak_in_flight > 1


async def test_run_never_exceeds_the_configured_concurrency_limit() -> None:
    runner = CampaignRunner(max_concurrent_calls=2)
    probe = _ConcurrencyProbe(runner)
    runner.run_one = probe  # type: ignore[method-assign]
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(6)]

    await runner.run(TRAVEL_DISCOVERY, contacts)

    assert probe.peak_in_flight <= 2


async def test_ceiling_holds_under_concurrent_dialing(monkeypatch: pytest.MonkeyPatch) -> None:
    # The check-and-reserve race this guards against only shows up under
    # real concurrency - a sequential loop could never over-admit. Split on
    # `status`, not disposition: a gate block and a stubbed dial are both
    # SKIPPED, so only the status tells them apart.
    import dataclasses

    from app.domain import safety

    monkeypatch.setattr(safety, "config", dataclasses.replace(safety.config, max_calls_per_run=2))
    runner = CampaignRunner(max_concurrent_calls=5)
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(5)]

    outcomes = await runner.run(TRAVEL_DISCOVERY, contacts)

    blocked = [o for o in outcomes if o.status == BLOCKED_STATUS]
    admitted = [o for o in outcomes if o.status != BLOCKED_STATUS]
    assert len(admitted) == 2
    assert len(blocked) == 3


async def test_credits_already_used_before_this_run_count_toward_the_ceiling() -> None:
    # Purely a pre-dial gate check - never reaches origination, so this holds
    # regardless of what places the call.
    runner = CampaignRunner(credit_ceiling=1, credits_used_before_run=1)
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    assert result.status == "BLOCKED"
    assert result.disposition is Disposition.SKIPPED
    assert "credit" in (result.disposition_reason or "")


async def test_an_undiallable_call_releases_its_reserved_credit_for_the_next_contact() -> None:
    # A credit is only ever actually spent by a *connected* call. A campaign
    # with no connected number never reaches one, so a ceiling of 1 must not
    # block a second contact once the first's reservation is handed back.
    runner = CampaignRunner(credit_ceiling=1, credits_used_before_run=0)

    first = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    second = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="B", phone="+15555550101"))

    # Both are Disposition.SKIPPED - a gate block and an undiallable campaign
    # share that disposition, so only `status` tells "never got past the gate"
    # (BLOCKED_STATUS) apart from "got past it and failed honestly" (this).
    assert first.status == UNDIALLABLE_STATUS, "the call itself was never blocked"
    assert second.status == UNDIALLABLE_STATUS, "the released credit was not reusable"


async def test_a_carrier_failure_releases_its_reserved_credit() -> None:
    """The same rule, on the path that actually dials. A busy line spends no
    credit, so a ceiling of 1 must still admit the next contact."""
    runner, _ = _dialling_runner(
        StubGateway(fail_with=_twirp("internal", sip_status=486)),
        credit_ceiling=1,
        credits_used_before_run=0,
        max_calls_per_run=5,
    )

    first = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    second = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="B", phone="+15555550101"))

    assert first.error == DialFailure.BUSY.value
    assert second.error == DialFailure.BUSY.value, "the released credit was not reusable"


async def test_an_answered_call_keeps_its_credit() -> None:
    """The one path that does spend one. With a ceiling of 1, the second
    contact must be refused - otherwise the ceiling means nothing."""
    runner, _ = _dialling_runner(
        credit_ceiling=1, credits_used_before_run=0, max_calls_per_run=5
    )

    first = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    second = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="B", phone="+15555550101"))

    assert first.status == "IN_PROGRESS"
    assert second.status == BLOCKED_STATUS
    assert "credit" in (second.disposition_reason or "")


async def test_an_unanswered_call_is_not_credited_as_connected() -> None:
    result = await CampaignRunner().run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    assert result.answered is False


async def test_run_preserves_input_order_regardless_of_completion_order() -> None:
    runner = CampaignRunner(max_concurrent_calls=5)
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(5)]

    outcomes = await runner.run(TRAVEL_DISCOVERY, contacts)

    assert [o.contact_name for o in outcomes] == [c.name for c in contacts]


@pytest.mark.parametrize(
    "payload,expected_key",
    [
        ({"result": {"outcome": "interested"}}, "outcome"),
        ({"structured_result": {"outcome": "interested"}}, "outcome"),
        ({"recipients": [{"result": {"outcome": "interested"}}]}, "outcome"),
        ({"result": {"data": {"outcome": "interested"}}}, "outcome"),
    ],
)
def test_extract_result_handles_known_shapes(payload: dict, expected_key: str) -> None:
    assert expected_key in _extract_result(payload)


def test_extract_result_returns_empty_when_absent() -> None:
    assert _extract_result({"status": "completed"}) == {}


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


def test_extract_transcript_reads_nested_turns_from_recipients_attempts() -> None:
    # The real, confirmed shape: recipients[N].attempts[M].transcript_turns[] -
    # not a top-level `transcript` key, which is what the old (wrong) code checked.
    call = {
        "status": "completed",
        "recipients": [
            {
                "status": "completed",
                "attempts": [
                    _attempt(
                        "completed",
                        [
                            {"offset_seconds": 0, "speaker": "bot", "text": "Hi, is this Aditi?"},
                            {"offset_seconds": 3, "speaker": "user", "text": "Yes, speaking."},
                        ],
                    )
                ],
            }
        ],
    }
    assert _extract_transcript(call) == "bot: Hi, is this Aditi?\nuser: Yes, speaking."


def test_extract_transcript_uses_the_last_completed_attempt_not_the_first() -> None:
    # A recipient redialled once: the first attempt rang out, the second is the
    # one that actually happened. The transcript must come from the second.
    call = {
        "recipients": [
            {
                "attempts": [
                    _attempt(
                        "failed",
                        [{"offset_seconds": 0, "speaker": "bot", "text": "First try, no answer."}],
                    ),
                    _attempt(
                        "completed",
                        [
                            {"offset_seconds": 0, "speaker": "bot", "text": "Second try, hello!"},
                            {"offset_seconds": 4, "speaker": "user", "text": "Hi there."},
                        ],
                    ),
                ]
            }
        ]
    }
    assert _extract_transcript(call) == "bot: Second try, hello!\nuser: Hi there."


def test_extract_transcript_falls_back_to_last_attempt_when_none_completed() -> None:
    call = {
        "recipients": [
            {
                "attempts": [
                    _attempt("failed", [{"offset_seconds": 0, "speaker": "bot", "text": "Attempt one failed."}]),
                    _attempt("failed", [{"offset_seconds": 0, "speaker": "bot", "text": "Attempt two failed."}]),
                ]
            }
        ]
    }
    assert _extract_transcript(call) == "bot: Attempt two failed."


def test_extract_transcript_uses_the_first_recipient_in_a_batch() -> None:
    # Follows _extract_result's own recipients[0] convention for consistency.
    call = {
        "recipients": [
            {"attempts": [_attempt("completed", [{"offset_seconds": 0, "speaker": "bot", "text": "Recipient one."}])]},
            {"attempts": [_attempt("completed", [{"offset_seconds": 0, "speaker": "bot", "text": "Recipient two."}])]},
        ]
    }
    assert _extract_transcript(call) == "bot: Recipient one."


def test_final_attempt_prefers_an_earlier_attempt_with_turns_over_an_empty_completed_one() -> None:
    """Reviewer-found gap: the last (and only completed) attempt has no
    transcript_turns at all - a real, permitted shape per the model's own
    docstring ("empty when no transcript is available") - while an earlier
    failed attempt actually captured part of the conversation. Picking by
    status alone would return the empty one and silently lose that transcript,
    reproducing this fix's own symptom through a different path."""
    call = {
        "recipients": [
            {
                "attempts": [
                    _attempt(
                        "failed",
                        [{"offset_seconds": 0, "speaker": "bot", "text": "Started talking, then the line dropped."}],
                        started_at="2026-08-07T10:00:00Z",
                    ),
                    _attempt("completed", [], started_at="2026-08-07T10:05:00Z"),
                ]
            }
        ]
    }
    assert _extract_transcript(call) == "bot: Started talking, then the line dropped."


def test_final_attempt_prefers_an_earlier_attempt_with_turns_when_none_completed() -> None:
    """Reviewer-found gap: no attempt ever completed, and the most recent
    attempt is empty, but an earlier failed attempt has real turns."""
    call = {
        "recipients": [
            {
                "attempts": [
                    _attempt(
                        "failed",
                        [{"offset_seconds": 0, "speaker": "bot", "text": "First failed attempt, briefly connected."}],
                        started_at="2026-08-07T10:00:00Z",
                    ),
                    _attempt("failed", [], started_at="2026-08-07T10:05:00Z"),
                ]
            }
        ]
    }
    assert _extract_transcript(call) == "bot: First failed attempt, briefly connected."


def test_final_attempt_orders_by_started_at_not_array_position() -> None:
    """The model doesn't document `attempts` as chronologically ordered, so
    array position alone isn't a safe proxy for "most recent" - `started_at`
    is. Here the truly later attempt (by timestamp) is placed first in the
    list; the earlier one, placed last, must still lose."""
    call = {
        "recipients": [
            {
                "attempts": [
                    _attempt(
                        "completed",
                        [{"offset_seconds": 0, "speaker": "bot", "text": "Actually the later attempt."}],
                        started_at="2026-08-07T12:00:00Z",
                    ),
                    _attempt(
                        "completed",
                        [{"offset_seconds": 0, "speaker": "bot", "text": "Actually the earlier attempt."}],
                        started_at="2026-08-07T09:00:00Z",
                    ),
                ]
            }
        ]
    }
    assert _extract_transcript(call) == "bot: Actually the later attempt."


def test_extract_transcript_skips_a_turn_with_null_text_instead_of_rendering_none() -> None:
    call = {
        "recipients": [
            {
                "attempts": [
                    _attempt(
                        "completed",
                        [
                            {"offset_seconds": 0, "speaker": "bot", "text": "Hello?"},
                            {"offset_seconds": 1, "speaker": "unknown", "text": None},
                            {"offset_seconds": 2, "speaker": "user", "text": "Hi."},
                        ],
                    )
                ]
            }
        ]
    }
    transcript = _extract_transcript(call)
    assert transcript == "bot: Hello?\nuser: Hi."
    assert "None" not in (transcript or "")


@pytest.mark.parametrize(
    "call",
    [
        {"status": "completed"},
        {"recipients": []},
        {"recipients": [{"attempts": []}]},
        {"recipients": [{"attempts": [_attempt("completed", [])]}]},
        {"transcript": "legacy flat shape that no longer exists on the real API"},
    ],
)
def test_extract_transcript_returns_none_when_nothing_usable(call: dict[str, Any]) -> None:
    assert _extract_transcript(call) is None


def test_extract_attempts_preserves_every_attempt_not_just_the_final_one() -> None:
    call = {
        "recipients": [
            {
                "attempts": [
                    {"status": "no_answer", "started_at": "2026-08-09T10:00:00Z"},
                    {"status": "completed", "started_at": "2026-08-09T10:05:00Z"},
                ]
            }
        ]
    }
    attempts = _extract_attempts(call)
    assert [a.status for a in attempts] == ["no_answer", "completed"]


def test_extract_attempts_records_whether_each_attempt_had_a_transcript() -> None:
    call = {
        "recipients": [
            {
                "attempts": [
                    {"status": "no_answer", "transcript_turns": []},
                    {"status": "completed", "transcript_turns": [{"speaker": "bot", "text": "hi"}]},
                ]
            }
        ]
    }
    attempts = _extract_attempts(call)
    assert [a.had_transcript for a in attempts] == [False, True]


@pytest.mark.parametrize("call", [{}, {"recipients": []}, {"recipients": [{"attempts": "not-a-list"}]}])
def test_extract_attempts_returns_empty_list_when_nothing_usable(call: dict[str, Any]) -> None:
    assert _extract_attempts(call) == []


def _base() -> CallOutcome:
    return CallOutcome(contact_name="A", phone_masked="+91***210", campaign_id="c")


def test_resolve_outcome_extracts_task_completed_and_confidence() -> None:
    call = {
        "status": "completed",
        "id": "call_1",
        "task_completed": False,
        "completion_confidence": {"score": 0.3, "label": "low"},
        "evidence": ["Contact hung up mid-sentence."],
    }
    resolved = _resolve_outcome(_base(), call, escalate_on_negative=True)
    assert resolved.task_completed is False
    assert resolved.completion_confidence_score == 0.3
    assert resolved.completion_confidence_label == "low"
    assert resolved.evidence == ["Contact hung up mid-sentence."]
    assert resolved.disposition is Disposition.ESCALATED


def test_resolve_outcome_defaults_confidence_and_evidence_when_absent() -> None:
    call = {"status": "completed", "id": "call_1"}
    resolved = _resolve_outcome(_base(), call, escalate_on_negative=True)
    assert resolved.task_completed is None
    assert resolved.completion_confidence_score is None
    assert resolved.completion_confidence_label is None
    assert resolved.evidence == []
    assert resolved.attempts == []


