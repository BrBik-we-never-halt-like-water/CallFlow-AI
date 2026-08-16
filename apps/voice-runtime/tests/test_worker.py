"""The worker's decisions: metadata parsing, transcript shaping, the payload the
completion callback sends, and how long a call is held.

That last one used to be excluded here as "needs a live room", and it was the
one that was wrong: the first version closed the session immediately after
starting it, so every call reported an empty transcript and NO_ANSWER.
`wait_for_call_end` is written against a duck-typed context precisely so the
fake room below can exercise it.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.worker import (
    completion_payload,
    parse_job_metadata,
    transcript_from_history,
    wait_for_call_end,
)


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


# --- holding the call ---------------------------------------------------------


class FakeRoom:
    """Just enough of `rtc.Room`: an event registry and a participant list."""

    def __init__(self, *, participants: int = 1) -> None:
        self.remote_participants = {f"p{i}": object() for i in range(participants)}
        self._handlers: dict[str, list[Any]] = {}

    def on(self, event: str, handler: Any) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def emit(self, event: str) -> None:
        for handler in self._handlers.get(event, []):
            handler()

    def everyone_leaves(self) -> None:
        self.remote_participants = {}
        self.emit("participant_disconnected")


class FakeContext:
    def __init__(
        self, room: FakeRoom, *, joins_after: float = 0.0, never_joins: bool = False
    ) -> None:
        self.room = room
        self._joins_after = joins_after
        self._never_joins = never_joins

    async def wait_for_participant(self) -> Any:
        if self._never_joins:
            await asyncio.Event().wait()  # blocks until the caller's timeout
        await asyncio.sleep(self._joins_after)
        return object()


async def test_the_call_is_held_until_the_contact_hangs_up() -> None:
    """The regression this file exists for. Returning as soon as the session
    starts closed the room while the phone was still ringing, so every call
    reported an empty transcript."""
    room = FakeRoom()
    ctx = FakeContext(room)

    async def hang_up_shortly() -> None:
        await asyncio.sleep(0.05)
        room.everyone_leaves()

    task = asyncio.create_task(hang_up_shortly())
    answered = await wait_for_call_end(ctx, answer_timeout=1.0, max_seconds=5.0)
    await task

    assert answered is True


async def test_nobody_joining_is_an_unanswered_call_not_an_error() -> None:
    ctx = FakeContext(FakeRoom(), never_joins=True)

    answered = await wait_for_call_end(ctx, answer_timeout=0.05, max_seconds=5.0)

    assert answered is False


async def test_a_call_that_ends_before_the_handlers_are_armed_still_returns() -> None:
    """The race the ordering guards against: a very short call can end between
    the participant joining and the disconnect handler being registered. A
    handler armed after that check would never fire and the worker would wait
    out the whole ceiling."""
    room = FakeRoom(participants=0)
    ctx = FakeContext(room)

    answered = await asyncio.wait_for(
        wait_for_call_end(ctx, answer_timeout=1.0, max_seconds=30.0), timeout=1.0
    )

    assert answered is True


async def test_a_room_that_never_reports_is_cut_off_at_the_ceiling() -> None:
    """The third case: somebody joined, nothing ever says they left. Without
    the ceiling the worker holds the job open indefinitely."""
    ctx = FakeContext(FakeRoom())

    answered = await asyncio.wait_for(
        wait_for_call_end(ctx, answer_timeout=1.0, max_seconds=0.05), timeout=2.0
    )

    assert answered is True, "somebody was on the line - this is a long call, not a missed one"


async def test_a_room_level_disconnect_ends_the_wait_too() -> None:
    """A dropped connection ends the call as surely as a hang-up does."""
    room = FakeRoom()
    ctx = FakeContext(room)

    async def drop() -> None:
        await asyncio.sleep(0.05)
        room.emit("disconnected")

    task = asyncio.create_task(drop())
    answered = await asyncio.wait_for(
        wait_for_call_end(ctx, answer_timeout=1.0, max_seconds=5.0), timeout=2.0
    )
    await task

    assert answered is True
