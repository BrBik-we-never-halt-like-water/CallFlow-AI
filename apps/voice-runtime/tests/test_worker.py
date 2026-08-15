"""The worker's pure parts: metadata parsing, transcript shaping, and the
payload the completion callback sends.

The LiveKit lifecycle itself needs a live room and is deliberately not tested;
what is tested is everything the lifecycle hands off to, which is where the
decisions actually are.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.worker import completion_payload, parse_job_metadata, transcript_from_history


class FakeItem:
    def __init__(self, role: str, text: str) -> None:
        self.role = role
        self.text_content = text


class FakeHistory:
    def __init__(self, *items: FakeItem) -> None:
        self.items = list(items)


# --- metadata -----------------------------------------------------------------


def test_valid_metadata_is_parsed() -> None:
    assert parse_job_metadata('{"run_id": "abc"}') == {"run_id": "abc"}


@pytest.mark.parametrize("raw", [None, "", "not json", "[1,2,3]", '"a string"', "null"])
def test_unusable_metadata_yields_an_empty_mapping_rather_than_raising(raw: str | None) -> None:
    """A worker that dies parsing metadata leaves a live call with nobody on
    the line. The caller refuses the job with a reason instead."""
    assert parse_job_metadata(raw) == {}


# --- transcript ---------------------------------------------------------------


def test_the_transcript_reads_as_a_conversation() -> None:
    history = FakeHistory(
        FakeItem("assistant", "Hello, is this Aditi?"),
        FakeItem("user", "Yes, speaking."),
    )
    assert transcript_from_history(history) == (
        "Agent: Hello, is this Aditi?\nContact: Yes, speaking."
    )


def test_non_conversational_turns_are_left_out() -> None:
    """System prompts and tool calls are not what the contact said."""
    history = FakeHistory(
        FakeItem("system", "You are a helpful agent."),
        FakeItem("assistant", "Hello."),
        FakeItem("tool", "{}"),
    )
    assert transcript_from_history(history) == "Agent: Hello."


def test_an_empty_turn_is_skipped_rather_than_rendered_blank() -> None:
    history = FakeHistory(FakeItem("assistant", "Hello."), FakeItem("user", ""))
    assert transcript_from_history(history) == "Agent: Hello."


@pytest.mark.parametrize("history", [None, FakeHistory()])
def test_no_history_gives_an_empty_transcript(history: Any) -> None:
    assert transcript_from_history(history) == ""


# --- the completion payload ---------------------------------------------------


def _metadata() -> dict[str, Any]:
    return {"run_id": "run_abc", "contact_name": "Aditi", "phone_masked": "+15******100"}


def test_a_conversation_is_reported_completed() -> None:
    payload = completion_payload(
        _metadata(), transcript="Agent: Hi.\nContact: Hello.", duration_seconds=42
    )

    assert payload["status"] == "COMPLETED"
    assert payload["duration_seconds"] == 42
    assert payload["transcript"]


def test_a_connected_call_with_no_turns_is_not_reported_as_completed() -> None:
    """The carrier says the call connected; nobody spoke. Reporting COMPLETED
    would show an operator a conversation that never happened."""
    payload = completion_payload(_metadata(), transcript="", duration_seconds=3)

    assert payload["status"] == "NO_ANSWER"
    assert payload["transcript"] is None


def test_a_crash_is_reported_as_failed_with_the_reason() -> None:
    payload = completion_payload(
        _metadata(), transcript="Agent: Hi.", duration_seconds=5, error="TimeoutError"
    )

    assert payload["status"] == "FAILED"
    assert payload["error"] == "TimeoutError"
    # Partial transcripts still go back - what was said before the crash is
    # more useful than nothing.
    assert payload["transcript"] == "Agent: Hi."


def test_the_payload_addresses_the_row_the_dial_already_created() -> None:
    """`call_outcomes` is keyed on (run_id, contact_name, phone_masked).
    Inventing either here would insert a second row rather than resolving the
    in-flight one."""
    payload = completion_payload(_metadata(), transcript="Agent: Hi.", duration_seconds=1)

    assert payload["contact_name"] == "Aditi"
    assert payload["phone_masked"] == "+15******100"


def test_extraction_is_left_empty_rather_than_guessed() -> None:
    """Structured extraction against the campaign's result_schema is Part 2's.
    An invented field would make triage act on something nobody produced."""
    payload = completion_payload(_metadata(), transcript="Agent: Hi.", duration_seconds=1)

    assert payload["extracted"] == {}


def test_the_payload_never_carries_a_real_phone_number() -> None:
    payload = completion_payload(_metadata(), transcript="Agent: Hi.", duration_seconds=1)
    assert "5555550100" not in str(payload)
