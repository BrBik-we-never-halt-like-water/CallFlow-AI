"""Orchestrator behaviour: every run dials for real, guarded by the safety gate.

Origination itself is stubbed while the voice platform migrates off CALL-E, so
the dial/poll tests that used to live here are gone rather than skipped - the
code under test was deleted with `engine.py`, and P1-T7 rewrites them against
the LiveKit client. Everything that survives here is vendor-agnostic on
purpose: the safety gate, the check-and-reserve ceiling, the suppression
check, the concurrency semaphore, idempotency keys, and the pure extraction
helpers. None of those depend on who places the call, and all of them must
keep passing across the migration.
"""

import asyncio
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

# What `run_one()` returns for any contact that clears the safety gate while
# origination is stubbed out. Distinct from a gate block by `status`, not by
# disposition - both are SKIPPED, because in neither case did a phone ring.
STUBBED_DIAL_STATUS = "FAILED"
BLOCKED_STATUS = "BLOCKED"


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


async def test_a_contact_that_clears_the_gate_reports_an_honest_failure() -> None:
    """No provider exists, so a contact past the safety gate must come back as
    an explicit failure with a reason a human can act on - never a success and
    never a silent no-op (CLAUDE.md non-negotiable #9)."""
    runner = CampaignRunner()
    contact = Contact(name="Aditi", phone="+15555550100", context={"enquiry_note": "Bali"})

    result = await runner.run_one(TRAVEL_DISCOVERY, contact)

    assert result.status == STUBBED_DIAL_STATUS
    assert result.error == "provider_unavailable"
    assert result.disposition is Disposition.SKIPPED
    assert "not available yet" in (result.disposition_reason or "")
    # Masking is a guarantee that does not depend on who places the call.
    assert "5555550" not in result.phone_masked


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
    assert sorted(seen) == [("A", STUBBED_DIAL_STATUS), ("B", STUBBED_DIAL_STATUS)]


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


