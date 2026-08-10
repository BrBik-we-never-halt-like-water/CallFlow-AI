"""Structured logging, with a real global redaction filter.

CLAUDE.md's non-negotiable #5 says PII is "redacted by a global filter - and
the redaction is tested." Until this module, that filter didn't exist -
redaction was pure `mask()` (`app/domain/safety.py`) discipline at each log
call site, no backstop for a call site that forgot. `mask()` stays the
primary defence (it's the one place a *readable* partial number is produced
for an operator to act on); this filter is what catches whatever slips past
it, so it redacts fully rather than partially - a safety net doesn't need to
be pretty, it needs to not miss.

Also attaches optional correlation fields (`run_id`, `call_id`, `org_id`) to
every record emitted while a `CallContext` is active, so one call's whole
lifecycle - dial, poll, webhook, triage - greps as one unit instead of loose,
unrelated lines.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import time
from types import TracebackType

REDACTED = "[REDACTED]"

# A generic E.164-shaped run: 8-15 digits, optionally `+`-prefixed. Wide on
# purpose - a false positive redacts a harmless number-looking string; a
# false negative leaks a real one. This is the safety net, not the primary
# mask, so it errs toward over-redacting.
_PHONE_RE = re.compile(r"\+?\d{8,15}")

# Bearer tokens, CALL-E/Supabase-style prefixed secrets (`sk_...`), and
# `key=`/`token=`/`authorization=`-style inline assignments.
_TOKEN_RE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._\-]{8,}"
    r"|sk_[a-z0-9_\-]{8,}"
    r"|(?:api[_-]?key|token|authorization|secret|password)\s*[=:]\s*\S+)"
)

# Structured `extra=` field names redacted by name, in full, regardless of
# content - a transcript is free text, not pattern-matchable, so name-based
# redaction is the only reliable guarantee for it.
_SENSITIVE_FIELD_NAMES = frozenset(
    {
        "transcript",
        "phone",
        "raw_phone",
        "api_key",
        "token",
        "authorization",
        "password",
        "secret",
    }
)

# Correlation fields threaded through by `CallContext` - allow-listed rather
# than dumping every `LogRecord` attribute, so nothing internal to the
# logging module itself ends up in a JSON line by accident.
_CONTEXT_FIELDS = ("run_id", "call_id", "org_id")

# `default=None`, not `{}` - a mutable default would be the same dict object
# shared across every context that never called `.set()`, one shared bucket
# away from a bug if anything ever mutated it in place instead of replacing it.
_context: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "callflow_log_context", default=None
)


def _current_context() -> dict[str, str]:
    return _context.get() or {}


class CallContext:
    """Binds correlation fields to every log record emitted inside the block.

    Nests: a poll loop entered while a `run_id` is already bound adds
    `call_id` alongside it rather than replacing the whole context.

        with CallContext(run_id=run_id):
            with CallContext(call_id=call_id):
                log.info("dialing")  # carries both run_id and call_id
    """

    def __init__(self, **fields: str | None) -> None:
        self._fields = {k: v for k, v in fields.items() if v is not None}
        self._token: contextvars.Token[dict[str, str] | None] | None = None

    def __enter__(self) -> None:
        self._token = _context.set({**_current_context(), **self._fields})

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._token is not None:
            _context.reset(self._token)


def _redact_text(text: str) -> str:
    text = _PHONE_RE.sub(REDACTED, text)
    text = _TOKEN_RE.sub(REDACTED, text)
    return text


class RedactingFilter(logging.Filter):
    """Rewrites the rendered message and known-sensitive `extra=` fields.

    Runs on the handler, after formatting decisions but before emission, so
    it sees (and can rewrite) the final text regardless of how the record
    was built - an f-string, `%`-args, or `extra=`.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact_text(record.getMessage())
        record.args = ()
        for name in _SENSITIVE_FIELD_NAMES:
            if hasattr(record, name):
                setattr(record, name, REDACTED)
        return True


class ContextFilter(logging.Filter):
    """Attaches the active `CallContext` fields to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in _current_context().items():
            setattr(record, key, value)
        return True


class TextFormatter(logging.Formatter):
    """Human-readable - local dev, or any deployment that just tails stdout."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        context = {k: getattr(record, k, None) for k in _CONTEXT_FIELDS}
        pairs = " ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        return f"{base} [{pairs}]" if pairs else base


class JSONFormatter(logging.Formatter):
    """One JSON object per line - for a deployment shipping logs to an
    aggregator, where structured fields matter more than eyeball-readability."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in _CONTEXT_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(*, level: int = logging.INFO, json_format: bool = False) -> None:
    """The one place logging is set up - replaces a bare `logging.basicConfig`.

    Idempotent: clears any handlers a prior call (or a test importing
    `app.main` more than once in the same process) installed, so redaction
    and correlation are never accidentally doubled up or dropped.
    """
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setFormatter(
        JSONFormatter() if json_format else TextFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    handler.addFilter(ContextFilter())
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)


__all__ = [
    "REDACTED",
    "CallContext",
    "ContextFilter",
    "JSONFormatter",
    "RedactingFilter",
    "TextFormatter",
    "configure_logging",
]
