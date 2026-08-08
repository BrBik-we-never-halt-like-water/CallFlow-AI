"""Orchestrator behaviour: every run dials for real, guarded by the safety gate."""

from typing import Any

import pytest

from app.domain.campaigns import TRAVEL_DISCOVERY
from app.domain.entities import Contact, Disposition
from app.services.campaign_runner import (
    CampaignRunner,
    _extract_result,
    _extract_transcript,
    render_goal,
)


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
    # The raw exception string must never reach a user-facing field — only the
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
    """Each contact fires at least once — a "dialing" event, then the resolved
    outcome — and always in contact order, never interleaved."""
    seen: list[str] = []
    runner = CampaignRunner(gateway=FakeGateway())  # type: ignore[arg-type]

    async def on_progress(outcome: Any) -> None:
        seen.append(outcome.contact_name)

    await runner.run(
        TRAVEL_DISCOVERY,
        [Contact(name="A", phone="+15555550100"), Contact(name="B", phone="+15555550101")],
        on_progress=on_progress,
    )
    assert seen == ["A", "A", "B", "B"]


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
    """A `CallTaskAttempt`-shaped fixture — every field the generated SDK
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
    # The real, confirmed shape: recipients[N].attempts[M].transcript_turns[] —
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
    transcript_turns at all — a real, permitted shape per the model's own
    docstring ("empty when no transcript is available") — while an earlier
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
    array position alone isn't a safe proxy for "most recent" — `started_at`
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
    DialFailure.INTERNAL — which the dial-time `_RETRYABLE_FAILURES` set
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
    """A connection that never recovers must not retry forever — it's bounded
    by the existing overall poll deadline, and ends up in the same RETRY
    bucket as any other poll timeout, not a hard failure. A small positive
    timeout (rather than 0) is used so the loop actually runs several
    iterations — and therefore several retries — before the deadline hits,
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
