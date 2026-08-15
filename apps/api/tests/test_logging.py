"""The global redaction filter and correlation-context plumbing.

CLAUDE.md's non-negotiable #5 claims PII is "redacted by a global filter -
and the redaction is tested." This file is that test.
"""

from __future__ import annotations

import logging

import pytest

from app.core.logging import (
    REDACTED,
    CallContext,
    ContextFilter,
    JSONFormatter,
    RedactingFilter,
    TextFormatter,
)


def _record(msg: str, *args: object, **extra: str) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1, msg=msg, args=args, exc_info=None
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


class TestRedactingFilter:
    def test_redacts_a_raw_phone_number_in_the_rendered_message(self) -> None:
        record = _record("dialing +15555550123 now")
        RedactingFilter().filter(record)
        assert "5555550123" not in record.getMessage()
        assert REDACTED in record.getMessage()

    def test_redacts_a_phone_number_passed_as_a_format_arg(self) -> None:
        record = _record("dialing %s now", "+15555550123")
        RedactingFilter().filter(record)
        assert "5555550123" not in record.getMessage()

    @pytest.mark.parametrize(
        "text",
        [
            "Authorization: Bearer sk_live_abcdef1234567890",
            "using api_key=abcdef1234567890xyz",
            "token: abcdef1234567890xyz",
        ],
    )
    def test_redacts_bearer_and_key_style_tokens(self, text: str) -> None:
        record = _record(text)
        RedactingFilter().filter(record)
        rendered = record.getMessage()
        assert "abcdef1234567890" not in rendered
        assert REDACTED in rendered

    def test_redacts_known_sensitive_extra_fields_by_name_regardless_of_content(self) -> None:
        record = _record("call finished", transcript="bot: hello\nuser: hi there")
        RedactingFilter().filter(record)
        assert record.transcript == REDACTED

    def test_leaves_ordinary_text_untouched(self) -> None:
        record = _record("campaign %s completed with %d outcomes", "travel-discovery", 3)
        RedactingFilter().filter(record)
        assert record.getMessage() == "campaign travel-discovery completed with 3 outcomes"

    def test_filter_always_returns_true_so_the_record_is_still_emitted(self) -> None:
        assert RedactingFilter().filter(_record("hello")) is True


class TestCallContext:
    def test_attaches_bound_fields_to_records_emitted_inside_the_block(self) -> None:
        with CallContext(run_id="run_abc"):
            record = _record("dialing")
            ContextFilter().filter(record)
        assert record.run_id == "run_abc"  # type: ignore[attr-defined]

    def test_fields_do_not_leak_outside_the_block(self) -> None:
        with CallContext(run_id="run_abc"):
            pass
        record = _record("dialing")
        ContextFilter().filter(record)
        assert not hasattr(record, "run_id")

    def test_nested_contexts_merge_rather_than_replace(self) -> None:
        with CallContext(run_id="run_abc"), CallContext(call_id="call_123"):
            record = _record("polling")
            ContextFilter().filter(record)
        assert record.run_id == "run_abc"  # type: ignore[attr-defined]
        assert record.call_id == "call_123"  # type: ignore[attr-defined]

    def test_exiting_the_inner_context_restores_the_outer_ones_fields(self) -> None:
        with CallContext(run_id="run_abc"):
            with CallContext(call_id="call_123"):
                pass
            record = _record("after inner exits")
            ContextFilter().filter(record)
        assert record.run_id == "run_abc"  # type: ignore[attr-defined]
        assert not hasattr(record, "call_id")

    def test_none_valued_fields_are_not_bound(self) -> None:
        with CallContext(run_id="run_abc", call_id=None):
            record = _record("dialing")
            ContextFilter().filter(record)
        assert record.run_id == "run_abc"  # type: ignore[attr-defined]
        assert not hasattr(record, "call_id")


class TestFormatters:
    def test_text_formatter_appends_context_fields_when_present(self) -> None:
        record = _record("dialing", run_id="run_abc")
        rendered = TextFormatter("%(message)s").format(record)
        assert "dialing" in rendered
        assert "run_id=run_abc" in rendered

    def test_text_formatter_omits_the_bracket_entirely_when_no_context_is_bound(self) -> None:
        record = _record("dialing")
        rendered = TextFormatter("%(message)s").format(record)
        assert rendered == "dialing"

    def test_json_formatter_produces_one_parseable_object_with_context_fields(self) -> None:
        import json

        record = _record("dialing", run_id="run_abc", call_id="call_123")
        payload = json.loads(JSONFormatter().format(record))
        assert payload["message"] == "dialing"
        assert payload["run_id"] == "run_abc"
        assert payload["call_id"] == "call_123"
        assert payload["level"] == "INFO"
