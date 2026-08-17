"""Whether a call came back with what the agent was asked to find out.

Pure, so no database. ADR-5's gap: `required` was set on a field and then read
exactly once, to build the schema the model was asked to satisfy - nothing ever
re-checked the answer against it, so a call could return none of the required
fields and still be recorded as `auto_closed`.
"""

from __future__ import annotations

import pytest

from app.domain.collection import handoff_questions, is_present, missing_required
from app.domain.entities import CollectField

FIELDS = [
    CollectField(key="destination", description="Which destination they have in mind", required=True),
    CollectField(key="travel_date", description="Roughly when they want to travel"),
    CollectField(key="party_size", type="integer", description="How many are travelling", required=True),
]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Dubai", True),
        ("  Dubai  ", True),
        (0, True),
        (False, True),
        ([], True),
        ({}, True),
        (None, False),
        ("", False),
        ("   ", False),
    ],
)
def test_what_counts_as_an_answer(value: object, expected: bool) -> None:
    """`False` and `0` are the cases a bare falsiness check gets wrong. A yes/no
    field answered "no" was collected, and calling it missing would send a person
    to ask something the contact already answered."""
    assert is_present(value) is expected


def test_a_complete_call_is_missing_nothing() -> None:
    collected = {"destination": "Dubai", "party_size": 4, "travel_date": "December"}
    assert missing_required(FIELDS, collected) == []


def test_only_required_fields_are_chased() -> None:
    """`travel_date` is optional, so a call that never established it is still
    complete - the operator chose that when they left the box unticked."""
    assert missing_required(FIELDS, {"destination": "Dubai", "party_size": 4}) == []


def test_a_missing_required_field_is_reported_in_the_agents_own_order() -> None:
    """The list is read back to a person as what to ask, and the agent's field
    order is the order it would have asked them in."""
    assert missing_required(FIELDS, {"travel_date": "December"}) == [
        "destination",
        "party_size",
    ]


def test_a_field_answered_no_is_not_missing() -> None:
    """The whole reason `is_present` exists rather than `if not value`."""
    fields = [CollectField(key="wants_insurance", type="boolean", required=True)]
    assert missing_required(fields, {"wants_insurance": False}) == []


def test_nothing_collected_at_all_reports_every_required_field() -> None:
    assert missing_required(FIELDS, None) == ["destination", "party_size"]
    assert missing_required(FIELDS, {}) == ["destination", "party_size"]


def test_an_agent_collecting_nothing_is_never_incomplete() -> None:
    """A conversation-only agent is legal, and must not escalate every call."""
    assert missing_required([], {}) == []


def test_handoff_questions_read_as_instructions_not_field_names() -> None:
    """A list of keys is a database row; "Ask which destination they have in mind"
    is something a person can act on."""
    questions = handoff_questions(FIELDS, missing=["destination", "party_size"])
    assert questions == [
        "Ask: Which destination they have in mind",
        "Ask: How many are travelling",
    ]


def test_a_field_with_no_description_still_names_the_gap() -> None:
    """Naming it badly beats not naming it."""
    fields = [CollectField(key="policy_number", required=True)]
    assert handoff_questions(fields, missing=["policy_number"]) == [
        "Ask for policy number."
    ]


def test_the_reason_the_call_escalated_comes_after_the_data_gaps() -> None:
    """An opt-out or a callback request is not a question about data - a person
    should handle it before asking for anything else."""
    questions = handoff_questions(
        FIELDS, missing=["destination"], wants_human=True, do_not_call=True
    )
    assert questions[0].startswith("Ask:")
    assert "call them back" in questions[1]
    assert "suppress" in questions[2]


def test_a_clean_complete_call_needs_no_questions() -> None:
    assert handoff_questions(FIELDS, missing=[]) == []
