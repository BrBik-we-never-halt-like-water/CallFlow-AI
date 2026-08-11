"""Orchestrator behaviour: every run dials for real, guarded by the safety gate."""

import threading
import time
from typing import Any

import pytest

from app.domain.campaigns import TRAVEL_DISCOVERY
from app.domain.entities import CallOutcome, Contact, Disposition
from app.domain.goal_rendering import render_goal
from app.domain.outcome_extraction import (
    _extract_attempts,
    _extract_result,
    _extract_transcript,
    _resolve_outcome,
)
from app.services.campaign_runner import CampaignRunner


class ExplodingGateway:
    """Fails loudly if a guarded call reaches the gateway at all."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"a blocked contact must not call gateway.{name}")


class FakeGateway:
    """Completes a call immediately with a canned structured result."""

    def start_call(self, **_: Any) -> dict[str, Any]:
        return {"id": "call_test123", "status": "queued"}

    def get_call(self, call_id: str) -> dict[str, Any]:
        return {
            "id": call_id,
            "status": "completed",
            "structured_result": {
                "outcome": "interested",
                "sentiment": "positive",
                "frustration_signals": False,
                "summary": "Wants a Bali package.",
            },
        }


class RecordingGateway(FakeGateway):
    """A `FakeGateway` that also remembers every `idempotency_key` it was asked
    to dial with, in call order."""

    def __init__(self) -> None:
        self.idempotency_keys: list[str] = []

    def start_call(self, **kwargs: Any) -> dict[str, Any]:
        self.idempotency_keys.append(kwargs["idempotency_key"])
        return super().start_call(**kwargs)


class ConcurrencyTrackingGateway(FakeGateway):
    """Records the peak number of `start_call`s in flight at once, to prove
    `run()` actually overlaps contacts rather than dialling one at a time.

    The delay is a real `time.sleep()`, not `asyncio.sleep()` - it runs
    inside the worker thread `asyncio.to_thread` dispatches to, so the
    `_no_real_sleep` fixture (which only patches the event-loop sleep between
    polls) does not affect it, and concurrent calls genuinely overlap in
    wall-clock time.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._in_flight = 0
        self.peak_in_flight = 0

    def start_call(self, **_: Any) -> dict[str, Any]:
        with self._lock:
            self._in_flight += 1
            self.peak_in_flight = max(self.peak_in_flight, self._in_flight)
        time.sleep(0.05)
        with self._lock:
            self._in_flight -= 1
        return {"id": "call_test", "status": "completed"}


class NoAnswerGateway(FakeGateway):
    """Completes a call that never connected. `"failed"` - not a literal
    "no_answer" - is the realistic payload: CALL-E's documented task-level
    `CallStatus` enum (CALLE.md) is only `queued/in_progress/completed/
    failed/canceled`, no finer "why" at this level (that detail lives in
    `failure_code`/`failure_message`, unused by a clean poll like this)."""

    def get_call(self, call_id: str) -> dict[str, Any]:
        return {"id": call_id, "status": "failed"}


class FlakyThenConnectsGateway(FakeGateway):
    """The first call placed never connects; every call after that does -
    for proving a released credit reservation is actually usable again by a
    later contact in the same run."""

    def __init__(self) -> None:
        self._calls = 0

    def start_call(self, **kwargs: Any) -> dict[str, Any]:
        self._calls += 1
        return {"id": f"call_{self._calls}", "status": "queued"}

    def get_call(self, call_id: str) -> dict[str, Any]:
        if call_id == "call_1":
            return {"id": call_id, "status": "failed"}
        return super().get_call(call_id)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.services.campaign_runner.asyncio.sleep", _instant)


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


async def test_call_completes_and_masks_the_phone() -> None:
    runner = CampaignRunner(gateway=FakeGateway())  # type: ignore[arg-type]
    contact = Contact(name="Aditi", phone="+15555550100", context={"enquiry_note": "Bali"})

    result = await runner.run_one(TRAVEL_DISCOVERY, contact)

    assert result.disposition is Disposition.AUTO_CLOSED
    assert result.run_id == "call_test123"
    assert "5555550" not in result.phone_masked


class FailingGateway:
    """Raises the given engine error the moment a call is placed."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def start_call(self, **_: Any) -> dict[str, Any]:
        raise self._exc


async def test_rate_limited_error_is_classified_as_retryable() -> None:
    from app.integrations.voice.engine import EngineAPIError

    exc = EngineAPIError(code="rate_limit_exceeded", message="slow down", status_code=429)
    runner = CampaignRunner(gateway=FailingGateway(exc))  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert result.disposition is Disposition.RETRY
    assert result.error == "rate_limited"


async def test_invalid_number_error_is_not_retryable() -> None:
    from app.integrations.voice.engine import EngineAPIError

    exc = EngineAPIError(code="invalid_phone", message="bad number", status_code=422)
    runner = CampaignRunner(gateway=FailingGateway(exc))  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert result.disposition is Disposition.UNREACHABLE
    assert result.error == "invalid_number"


async def test_unmapped_engine_error_fails_closed_to_internal() -> None:
    """A future engine error code this codebase doesn't know about yet must
    never be treated as a known-safe, retryable failure."""
    from app.integrations.voice.engine import EngineAPIError

    exc = EngineAPIError(code="a_brand_new_code_from_the_future", message="?", status_code=500)
    runner = CampaignRunner(gateway=FailingGateway(exc))  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert result.disposition is Disposition.UNREACHABLE
    assert result.error == "internal"


async def test_non_engine_exception_still_fails_closed() -> None:
    runner = CampaignRunner(gateway=FailingGateway(ConnectionError("dns lookup failed")))  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert result.disposition is Disposition.UNREACHABLE
    assert result.error == "internal"
    # The raw exception string must never reach a user-facing field - only the
    # server log (log.exception, not asserted here) gets the real detail.
    assert "dns lookup failed" not in (result.disposition_reason or "")


async def test_poll_timeout_is_classified_as_retryable_not_a_raw_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dataclasses

    from app.services import campaign_runner as runner_module

    class TimingOutGateway:
        def start_call(self, **_: Any) -> dict[str, Any]:
            return {"id": "call_test123", "status": "queued"}

        def get_call(self, call_id: str) -> dict[str, Any]:
            return {"id": call_id, "status": "queued"}

    monkeypatch.setattr(
        runner_module,
        "config",
        dataclasses.replace(runner_module.config, poll_timeout_seconds=0),
    )
    runner = CampaignRunner(gateway=TimingOutGateway())  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert result.disposition is Disposition.RETRY
    assert result.error == "timed_out"
    assert "did not finish" not in (result.disposition_reason or "")


async def test_ceiling_blocks_further_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    import dataclasses

    from app.domain import safety

    # Config is frozen, so swap in a replaced copy rather than mutating it.
    monkeypatch.setattr(
        safety, "config", dataclasses.replace(safety.config, max_calls_per_run=0)
    )
    runner = CampaignRunner(gateway=ExplodingGateway())  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    assert result.status == "BLOCKED"
    assert result.disposition is Disposition.SKIPPED


async def test_idempotency_key_is_stable_across_retries_of_the_same_run_and_contact() -> None:
    # The entire point of Idempotency-Key: a retry of the same logical attempt
    # (same run, same contact) must reuse the same key, so CALL-E can
    # recognise a duplicate instead of placing a second real call (#54).
    gateway = RecordingGateway()
    runner = CampaignRunner(gateway=gateway, run_id="run_abc123")  # type: ignore[arg-type]
    contact = Contact(name="A", phone="+15555550100")

    await runner.run_one(TRAVEL_DISCOVERY, contact)
    await runner.run_one(TRAVEL_DISCOVERY, contact)

    assert len(gateway.idempotency_keys) == 2
    assert gateway.idempotency_keys[0] == gateway.idempotency_keys[1]


async def test_idempotency_key_differs_across_different_runs_for_the_same_contact() -> None:
    # An old run's key must never be replayable against a new one.
    contact = Contact(name="A", phone="+15555550100")

    gateway_1 = RecordingGateway()
    await CampaignRunner(gateway=gateway_1, run_id="run_one").run_one(  # type: ignore[arg-type]
        TRAVEL_DISCOVERY, contact
    )
    gateway_2 = RecordingGateway()
    await CampaignRunner(gateway=gateway_2, run_id="run_two").run_one(  # type: ignore[arg-type]
        TRAVEL_DISCOVERY, contact
    )

    assert gateway_1.idempotency_keys[0] != gateway_2.idempotency_keys[0]


async def test_idempotency_key_never_contains_the_raw_phone_number() -> None:
    gateway = RecordingGateway()
    runner = CampaignRunner(gateway=gateway, run_id="run_abc123")  # type: ignore[arg-type]
    await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert "5555550100" not in gateway.idempotency_keys[0]


async def test_idempotency_key_falls_back_to_a_fresh_one_without_a_run_id() -> None:
    # No real run means no stable job identity to key off of - not idempotent,
    # but no worse than the behaviour this replaces.
    gateway = RecordingGateway()
    runner = CampaignRunner(gateway=gateway)  # type: ignore[arg-type]
    contact = Contact(name="A", phone="+15555550100")

    await runner.run_one(TRAVEL_DISCOVERY, contact)
    await runner.run_one(TRAVEL_DISCOVERY, contact)

    assert gateway.idempotency_keys[0] != gateway.idempotency_keys[1]


async def test_suppressed_number_is_blocked() -> None:
    from app.domain.safety import phone_hash

    contact = Contact(name="A", phone="+15555550100")
    runner = CampaignRunner(
        gateway=ExplodingGateway(),  # type: ignore[arg-type]
        suppressed_hashes=frozenset({phone_hash(contact.phone)}),
    )
    result = await runner.run_one(TRAVEL_DISCOVERY, contact)
    assert result.status == "BLOCKED"
    assert result.disposition is Disposition.SKIPPED
    assert "suppression" in (result.disposition_reason or "")


async def test_run_processes_every_contact() -> None:
    runner = CampaignRunner(gateway=FakeGateway())  # type: ignore[arg-type]
    contacts = [
        Contact(name="A", phone="+15555550100"),
        Contact(name="B", phone="+15555550101"),
    ]
    assert len(await runner.run(TRAVEL_DISCOVERY, contacts)) == 2


async def test_progress_hook_fires_per_contact() -> None:
    """Each contact fires at least once - a "dialing" event, then the
    resolved outcome - in that relative order *for that contact*. Contacts
    now dial concurrently, so the two contacts' events can interleave with
    each other; only each contact's own event order is guaranteed."""
    seen: list[tuple[str, Disposition]] = []
    runner = CampaignRunner(gateway=FakeGateway())  # type: ignore[arg-type]

    async def on_progress(outcome: Any) -> None:
        seen.append((outcome.contact_name, outcome.disposition))

    await runner.run(
        TRAVEL_DISCOVERY,
        [Contact(name="A", phone="+15555550100"), Contact(name="B", phone="+15555550101")],
        on_progress=on_progress,
    )
    for name in ("A", "B"):
        events = [disposition for contact_name, disposition in seen if contact_name == name]
        assert events == [Disposition.IN_FLIGHT, Disposition.AUTO_CLOSED]


async def test_run_dials_contacts_concurrently_not_one_at_a_time() -> None:
    gateway = ConcurrencyTrackingGateway()
    runner = CampaignRunner(gateway=gateway, max_concurrent_calls=3)  # type: ignore[arg-type]
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(5)]

    await runner.run(TRAVEL_DISCOVERY, contacts)

    assert gateway.peak_in_flight > 1


async def test_run_never_exceeds_the_configured_concurrency_limit() -> None:
    gateway = ConcurrencyTrackingGateway()
    runner = CampaignRunner(gateway=gateway, max_concurrent_calls=2)  # type: ignore[arg-type]
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(6)]

    await runner.run(TRAVEL_DISCOVERY, contacts)

    assert gateway.peak_in_flight <= 2


async def test_ceiling_holds_under_concurrent_dialing(monkeypatch: pytest.MonkeyPatch) -> None:
    # The check-and-reserve race this guards against only shows up under
    # real concurrency - a sequential loop could never over-admit.
    import dataclasses

    from app.domain import safety

    monkeypatch.setattr(safety, "config", dataclasses.replace(safety.config, max_calls_per_run=2))
    runner = CampaignRunner(gateway=FakeGateway(), max_concurrent_calls=5)  # type: ignore[arg-type]
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(5)]

    outcomes = await runner.run(TRAVEL_DISCOVERY, contacts)

    blocked = [o for o in outcomes if o.disposition is Disposition.SKIPPED]
    admitted = [o for o in outcomes if o.disposition is not Disposition.SKIPPED]
    assert len(admitted) == 2
    assert len(blocked) == 3


async def test_no_credit_ceiling_means_only_the_org_wide_budget_applies() -> None:
    # `credit_ceiling` defaults to `None` - nobody has set this teammate's
    # allocation, so nothing about credits should block them here.
    runner = CampaignRunner(gateway=FakeGateway())  # type: ignore[arg-type]
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(3)]
    outcomes = await runner.run(TRAVEL_DISCOVERY, contacts)
    assert all(o.answered for o in outcomes)


async def test_credit_ceiling_blocks_the_next_contact_once_a_call_connects() -> None:
    runner = CampaignRunner(  # type: ignore[arg-type]
        gateway=FakeGateway(), credit_ceiling=1, credits_used_before_run=0
    )

    first = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    second = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="B", phone="+15555550101"))

    assert first.answered
    assert second.status == "BLOCKED"
    assert second.disposition is Disposition.SKIPPED
    assert "credit" in (second.disposition_reason or "")


async def test_credits_already_used_before_this_run_count_toward_the_ceiling() -> None:
    runner = CampaignRunner(  # type: ignore[arg-type]
        gateway=ExplodingGateway(), credit_ceiling=1, credits_used_before_run=1
    )
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    assert result.status == "BLOCKED"
    assert result.disposition is Disposition.SKIPPED
    assert "credit" in (result.disposition_reason or "")


async def test_a_call_that_never_connects_does_not_spend_a_credit() -> None:
    # A credit is only ever actually spent by a connected call - a dial that
    # never rings through must give its reservation back so a later contact
    # in the same run can still use it.
    runner = CampaignRunner(  # type: ignore[arg-type]
        gateway=FlakyThenConnectsGateway(), credit_ceiling=1, credits_used_before_run=0
    )

    first = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    second = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="B", phone="+15555550101"))

    assert not first.answered
    assert first.disposition is not Disposition.SKIPPED, "the call itself was never blocked"
    assert second.disposition is not Disposition.SKIPPED, "the released credit was not reusable"
    assert second.answered


async def test_an_unanswered_call_is_not_credited_as_connected() -> None:
    runner = CampaignRunner(gateway=NoAnswerGateway())  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    assert result.answered is False


async def test_credit_ceiling_holds_under_concurrent_dialing() -> None:
    # Same shape as test_ceiling_holds_under_concurrent_dialing - the
    # check-and-reserve race only shows up under real concurrency, and
    # FakeGateway always connects, so every reservation here is a real spend.
    runner = CampaignRunner(  # type: ignore[arg-type]
        gateway=FakeGateway(), max_concurrent_calls=5, credit_ceiling=2, credits_used_before_run=0
    )
    contacts = [Contact(name=f"C{i}", phone=f"+155555501{i:02d}") for i in range(5)]

    outcomes = await runner.run(TRAVEL_DISCOVERY, contacts)

    connected = [o for o in outcomes if o.answered]
    blocked = [o for o in outcomes if o.disposition is Disposition.SKIPPED]
    assert len(connected) == 2
    assert len(blocked) == 3


async def test_run_preserves_input_order_regardless_of_completion_order() -> None:
    gateway = ConcurrencyTrackingGateway()
    runner = CampaignRunner(gateway=gateway, max_concurrent_calls=5)  # type: ignore[arg-type]
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


async def test_run_one_surfaces_the_real_transcript() -> None:
    """End-to-end: `run_one` must actually thread `_extract_transcript`'s output
    into the `CallOutcome`, using a payload shaped like CALL-E's real response
    rather than the flat shape the old, broken extractor expected."""

    class TranscriptGateway:
        def start_call(self, **_: Any) -> dict[str, Any]:
            return {"id": "call_test123", "status": "queued"}

        def get_call(self, call_id: str) -> dict[str, Any]:
            return {
                "id": call_id,
                "status": "completed",
                "structured_result": {"outcome": "interested"},
                "recipients": [
                    {
                        "status": "completed",
                        "attempts": [
                            _attempt(
                                "completed",
                                [
                                    {"offset_seconds": 0, "speaker": "bot", "text": "Hello!"},
                                    {"offset_seconds": 2, "speaker": "user", "text": "Hi."},
                                ],
                            )
                        ],
                    }
                ],
            }

    runner = CampaignRunner(gateway=TranscriptGateway())  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="Aditi", phone="+15555550100"))

    assert result.transcript == "bot: Hello!\nuser: Hi."
    assert result.disposition is Disposition.AUTO_CLOSED


async def test_one_transient_poll_failure_does_not_fail_the_call() -> None:
    """A single flaky HTTP call mid-poll must not end the whole call as FAILED
    when the actual phone conversation goes on to complete successfully."""
    from app.integrations.voice.engine import EngineAPIError

    class FlakyThenOkGateway:
        def __init__(self) -> None:
            self._polls = 0

        def start_call(self, **_: Any) -> dict[str, Any]:
            return {"id": "call_test123", "status": "queued"}

        def get_call(self, call_id: str) -> dict[str, Any]:
            self._polls += 1
            if self._polls == 1:
                raise EngineAPIError(code="provider_unavailable", message="hiccup", status_code=503)
            return {
                "id": call_id,
                "status": "completed",
                "structured_result": {"outcome": "interested"},
            }

    runner = CampaignRunner(gateway=FlakyThenOkGateway())  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert result.disposition is Disposition.AUTO_CLOSED
    assert result.error is None
    assert result.extracted.get("outcome") == "interested"


@pytest.mark.parametrize("code", ["internal_error", "not_found", "call_not_ready"])
async def test_previously_unretryable_poll_codes_no_longer_fail_a_completing_call(code: str) -> None:
    """`internal_error`, `not_found` (the classic read-after-write race right
    after creation), and `call_not_ready` (literally "not ready yet, check
    again") all fall through classify_error's unmapped-code default to
    DialFailure.INTERNAL - which the dial-time `_RETRYABLE_FAILURES` set
    excludes on purpose. A GET poll is a different question: none of these
    three should abandon a call that goes on to complete successfully."""
    from app.integrations.voice.engine import EngineAPIError

    class FlakyThenOkGateway:
        def __init__(self) -> None:
            self.polls = 0

        def start_call(self, **_: Any) -> dict[str, Any]:
            return {"id": "call_test123", "status": "queued"}

        def get_call(self, call_id: str) -> dict[str, Any]:
            self.polls += 1
            if self.polls == 1:
                raise EngineAPIError(code=code, message="transient", status_code=500)
            return {
                "id": call_id,
                "status": "completed",
                "structured_result": {"outcome": "interested"},
            }

    runner = CampaignRunner(gateway=FlakyThenOkGateway())  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert result.disposition is Disposition.AUTO_CLOSED
    assert result.error is None


async def test_repeated_transient_poll_failures_eventually_time_out_as_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A connection that never recovers must not retry forever - it's bounded
    by the existing overall poll deadline, and ends up in the same RETRY
    bucket as any other poll timeout, not a hard failure. A small positive
    timeout (rather than 0) is used so the loop actually runs several
    iterations - and therefore several retries - before the deadline hits,
    proving the retry path is bounded rather than skipped altogether."""
    import dataclasses

    from app.integrations.voice.engine import EngineConnectionError
    from app.services import campaign_runner as runner_module

    monkeypatch.setattr(
        runner_module, "config", dataclasses.replace(runner_module.config, poll_timeout_seconds=0.2)
    )

    class AlwaysFlakyGateway:
        def __init__(self) -> None:
            self.polls = 0

        def start_call(self, **_: Any) -> dict[str, Any]:
            return {"id": "call_test123", "status": "queued"}

        def get_call(self, call_id: str) -> dict[str, Any]:
            self.polls += 1
            raise EngineConnectionError("connection refused")

    gateway = AlwaysFlakyGateway()
    runner = CampaignRunner(gateway=gateway)  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert gateway.polls > 1  # actually retried, not just a single failed attempt
    assert result.disposition is Disposition.RETRY
    assert result.error == "timed_out"


async def test_non_retryable_poll_failure_fails_the_call_immediately() -> None:
    """A poll failure the taxonomy classifies as permanent (not a transient
    network blip) must not be swallowed and retried for the full timeout."""
    from app.integrations.voice.engine import EngineAPIError

    class AlwaysUnauthorizedGateway:
        def start_call(self, **_: Any) -> dict[str, Any]:
            return {"id": "call_test123", "status": "queued"}

        def get_call(self, call_id: str) -> dict[str, Any]:
            raise EngineAPIError(code="unauthorized", message="key revoked", status_code=401)

    runner = CampaignRunner(gateway=AlwaysUnauthorizedGateway())  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))

    assert result.disposition is Disposition.UNREACHABLE
    assert result.error == "unauthorized"
