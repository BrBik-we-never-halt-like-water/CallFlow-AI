"""Field collection: what the agent records, and what is read back afterwards.

The interesting cases are the ones where being lenient and being safe disagree.
"About three thousand" is a real answer to a number field and must survive;
a field the agent invented must not. And recovery must never displace a value
the agent actually heard, because a guess that looks like an answer means the
person who should have been asked never is.
"""

from __future__ import annotations

from app.collection import (
    CollectField,
    Collector,
    coerce,
    fields_from_metadata,
    recover_missing,
)


def field(key: str, **kw: object) -> CollectField:
    return CollectField(key=key, **kw)  # type: ignore[arg-type]


# --- reading the schema off metadata ---------------------------------------


def test_fields_from_metadata_reads_the_declared_list() -> None:
    fields = fields_from_metadata(
        {
            "collect_schema": [
                {"key": "budget", "type": "integer", "required": True},
                {"key": "destination", "description": "Where they want to go"},
            ]
        }
    )
    assert [f.key for f in fields] == ["budget", "destination"]
    assert fields[0].required is True
    assert fields[1].required is False
    assert fields[1].description == "Where they want to go"


def test_malformed_schema_yields_no_fields_rather_than_raising() -> None:
    # A call must still be held. It comes back as a transcript, which is exactly
    # what an agent with no fields produces.
    for bad in ({}, {"collect_schema": None}, {"collect_schema": "budget"}):
        assert fields_from_metadata(bad) == []


def test_unusable_entries_are_dropped_individually() -> None:
    fields = fields_from_metadata(
        {"collect_schema": [{"key": ""}, "not a dict", {"key": "budget"}, {"key": "budget"}]}
    )
    assert [f.key for f in fields] == ["budget"]


def test_unknown_type_falls_back_to_text() -> None:
    # A field type added on the API side must not stop this worker dialling.
    assert fields_from_metadata({"collect_schema": [{"key": "x", "type": "date"}]})[
        0
    ].declared_type == "string"


# --- coercion --------------------------------------------------------------


def test_spoken_numbers_survive_currency_and_commas() -> None:
    assert coerce("₹40,000", "integer") == 40000
    assert coerce("about 2.5 lakh", "number") == 2.5


def test_a_number_that_will_not_convert_is_kept_as_text() -> None:
    # Losing this would lose information a person reading the record wants.
    assert coerce("about three thousand", "integer") == "about three thousand"


def test_boolean_words_both_ways() -> None:
    assert coerce("yeah", "boolean") is True
    assert coerce("nope", "boolean") is False
    assert coerce("only on Tuesdays", "boolean") == "only on Tuesdays"


def test_empty_answers_are_not_values() -> None:
    assert coerce("   ", "string") is None


# --- the collector ---------------------------------------------------------


def test_recording_an_answer_coerces_it() -> None:
    collector = Collector(fields=[field("budget", type="integer")])
    assert collector.record("budget", "40,000") == "Recorded budget."
    assert collector.values == {"budget": 40000}


def test_an_undeclared_field_is_refused_not_stored() -> None:
    # An invented field would land on a customer's record as if it were asked for.
    collector = Collector(fields=[field("budget")])
    reply = collector.record("credit_card", "4111 1111 1111 1111")
    assert "no field called credit_card" in reply
    assert collector.values == {}


def test_an_empty_value_asks_again_rather_than_storing_nothing() -> None:
    collector = Collector(fields=[field("budget")])
    assert "not recorded" in collector.record("budget", "  ")
    assert collector.values == {}


def test_missing_lists_only_required_fields_in_declared_order() -> None:
    collector = Collector(
        fields=[
            field("destination", required=True),
            field("notes"),
            field("budget", required=True),
        ]
    )
    collector.record("destination", "Dubai")
    assert collector.missing() == ["budget"]


def test_the_first_hangup_reason_wins() -> None:
    collector = Collector(fields=[])
    collector.request_hangup("they asked not to be called again")
    collector.request_hangup("goodbye")
    assert collector.hangup_reason == "they asked not to be called again"


def test_an_empty_hangup_reason_still_ends_the_call() -> None:
    collector = Collector(fields=[])
    collector.request_hangup("   ")
    assert collector.hangup_reason == "the contact asked to end the call"


# --- recovery from the transcript -----------------------------------------


def test_recovery_finds_a_field_the_agent_forgot_to_record() -> None:
    transcript = "Agent: What is your budget?\nContact: My budget is 40000 rupees."
    found = recover_missing([field("budget", type="integer")], {}, transcript)
    assert found == {"budget": 40000}


def test_recovery_never_returns_a_field_already_recorded() -> None:
    transcript = "Contact: budget is 999"
    found = recover_missing([field("budget", type="integer")], {"budget": 40000}, transcript)
    assert found == {}


def test_the_agents_own_question_is_not_read_back_as_the_answer() -> None:
    # Anchored to a contact turn on purpose: otherwise every field the agent
    # asked about comes back "answered".
    transcript = "Agent: So your budget is what exactly?"
    assert recover_missing([field("budget")], {}, transcript) == {}


def test_recovery_on_an_empty_transcript_finds_nothing() -> None:
    assert recover_missing([field("budget")], {}, "") == {}
    assert recover_missing([], {}, "Contact: budget is 5") == {}


def test_a_huge_transcript_is_truncated_rather_than_scanned_whole() -> None:
    # The answer sits past the scan window, so it is not found - which is the
    # safe direction: the field is reported missing and a person is asked.
    transcript = "Contact: hello. " * 6000 + "Contact: budget is 40000"
    assert recover_missing([field("budget", type="integer")], {}, transcript) == {}
