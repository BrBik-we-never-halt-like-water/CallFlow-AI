"""Triage decides who reaches a human. Order of precedence matters."""

from app.domain.entities import CallOutcome, Disposition, Sentiment
from app.domain.triage import needs_human, triage


def outcome(
    status: str = "completed", task_completed: bool | None = None, **extracted: object
) -> CallOutcome:
    return CallOutcome(
        contact_name="Test",
        phone_masked="+91*******210",
        campaign_id="c",
        status=status,
        task_completed=task_completed,
        extracted={"summary": "s", **extracted},
    )


def test_do_not_call_escalates() -> None:
    r = triage(outcome(do_not_call=True, sentiment="positive"))
    assert r.disposition is Disposition.ESCALATED
    assert "do-not-call" in r.disposition_reason


def test_do_not_call_beats_positive_sentiment() -> None:
    # A cheerful opt-out is still an opt-out.
    r = triage(outcome(do_not_call=True, sentiment="positive", frustration_signals=False))
    assert r.disposition is Disposition.ESCALATED


def test_human_request_escalates() -> None:
    r = triage(outcome(wants_human_callback=True, sentiment="neutral"))
    assert r.disposition is Disposition.ESCALATED


def test_frustration_escalates() -> None:
    r = triage(outcome(frustration_signals=True, sentiment="neutral"))
    assert r.disposition is Disposition.ESCALATED
    assert needs_human(r)


def test_negative_without_frustration_is_a_retry_not_an_escalation() -> None:
    # "It's a bad time" is not "I'm angry". Escalating it wastes a human.
    r = triage(outcome(sentiment="negative", frustration_signals=False))
    assert r.disposition is Disposition.RETRY
    assert not needs_human(r)


def test_frustration_beats_negative_sentiment() -> None:
    r = triage(outcome(sentiment="negative", frustration_signals=True))
    assert r.disposition is Disposition.ESCALATED
    assert "frustration" in r.disposition_reason.lower()


def test_negative_sentiment_can_be_ignored() -> None:
    r = triage(outcome(sentiment="negative"), escalate_on_negative=False)
    assert r.disposition is Disposition.AUTO_CLOSED


def test_task_not_completed_escalates() -> None:
    # CALL-E's own judgment that the conversation never reached a clear
    # resolution - worth a look even with otherwise clean extracted fields.
    r = triage(outcome(task_completed=False, sentiment="positive", frustration_signals=False))
    assert r.disposition is Disposition.ESCALATED
    assert "did not reach a clear resolution" in r.disposition_reason


def test_task_not_completed_beats_negative_sentiment_retry() -> None:
    r = triage(outcome(task_completed=False, sentiment="negative", frustration_signals=False))
    assert r.disposition is Disposition.ESCALATED


def test_do_not_call_beats_task_not_completed() -> None:
    # An explicit, specific human signal outranks CALL-E's summary-level judgment.
    r = triage(outcome(task_completed=False, do_not_call=True))
    assert r.disposition is Disposition.ESCALATED
    assert "do-not-call" in r.disposition_reason


def test_task_completed_true_does_not_force_escalation() -> None:
    r = triage(outcome(task_completed=True, sentiment="positive", frustration_signals=False))
    assert r.disposition is Disposition.AUTO_CLOSED


def test_task_completed_unknown_is_not_treated_as_false() -> None:
    # task_completed=None (CALL-E hasn't judged, or the field never arrived)
    # must not be conflated with an explicit False.
    r = triage(outcome(task_completed=None, sentiment="positive", frustration_signals=False))
    assert r.disposition is Disposition.AUTO_CLOSED


def test_clean_call_auto_closes() -> None:
    r = triage(outcome(sentiment="positive", frustration_signals=False))
    assert r.disposition is Disposition.AUTO_CLOSED
    assert not needs_human(r)


def test_no_answer_is_retryable() -> None:
    assert triage(outcome(status="no_answer")).disposition is Disposition.RETRY


def test_busy_is_retryable() -> None:
    assert triage(outcome(status="busy")).disposition is Disposition.RETRY


def test_failed_is_unreachable() -> None:
    assert triage(outcome(status="failed")).disposition is Disposition.UNREACHABLE


def test_sentiment_parsed_onto_outcome() -> None:
    assert triage(outcome(sentiment="positive")).sentiment is Sentiment.POSITIVE


def test_unparseable_sentiment_is_unknown() -> None:
    assert triage(outcome(sentiment="ecstatic")).sentiment is Sentiment.UNKNOWN


def test_triage_does_not_mutate_input() -> None:
    original = outcome(frustration_signals=True)
    triage(original)
    assert original.disposition is Disposition.SKIPPED
