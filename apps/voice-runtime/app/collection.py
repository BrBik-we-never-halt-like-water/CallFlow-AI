"""What the agent has to find out, and what it came back with.

The pure half of field collection: reading the field list off job metadata,
coercing a spoken answer into the declared type, and recovering anything the
agent forgot to record by reading it back out of the transcript.

Kept apart from `worker.py` for the same reason `pipeline.py` is - the LiveKit
tool wiring needs a live session to exercise, and none of the decisions here do.
`worker.py` holds the `record_field` / `end_call` tools and nothing else.

Two paths reach the same dict, on purpose (ADR-5):

1. **During the call.** The agent calls `record_field` as each answer arrives.
   This is the good path: the value is whatever the contact actually said, at
   the moment they said it.
2. **After the call.** `recover_missing()` scans the transcript for anything
   still absent. A model that held a perfect conversation and forgot to call the
   tool would otherwise produce an empty result and escalate a call that did not
   need a person.

The second path never overwrites the first. A recorded value is what the agent
heard; a recovered one is this module's guess, and a guess must not displace an
answer.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("voice-runtime.collection")

#: What `apps/api`'s `domain/entities.py:CollectField` declares. Anything else
#: is treated as free text rather than refused - a field type added on the API
#: side must not stop calls from being made by this worker.
_TYPES = frozenset({"string", "number", "integer", "boolean"})

_TRUE_WORDS = frozenset({"yes", "true", "y", "yeah", "yep", "correct", "sure", "ok", "okay", "1"})
_FALSE_WORDS = frozenset({"no", "false", "n", "nope", "nah", "never", "0"})

#: Guards `recover_missing` against a transcript that is mostly one long line -
#: a runaway regex over a 100kB transcript would hold the job open past the
#: point the room has already closed.
_MAX_SCAN_CHARS = 40_000


@dataclass(frozen=True)
class CollectField:
    """One thing the agent has to establish, as job metadata carries it."""

    key: str
    type: str = "string"
    description: str = ""
    required: bool = False

    @property
    def declared_type(self) -> str:
        return self.type if self.type in _TYPES else "string"


def fields_from_metadata(metadata: dict[str, Any]) -> list[CollectField]:
    """The field list off job metadata, dropping anything unusable.

    Never raises. An agent whose `collect_schema` arrived malformed should still
    hold its call - it just comes back as a transcript rather than as data,
    which is exactly what an agent with no fields does.
    """
    raw = metadata.get("collect_schema")
    if not isinstance(raw, list):
        return []

    out: list[CollectField] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("key") or "").strip()
        # A duplicate key would give the agent two tools with one name, and the
        # second silently wins. The API rejects duplicates on save; this is the
        # backstop for a row that predates that check.
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(
            CollectField(
                key=key,
                type=str(entry.get("type") or "string").lower(),
                description=str(entry.get("description") or ""),
                required=bool(entry.get("required")),
            )
        )
    return out


def coerce(value: Any, declared_type: str) -> Any:
    """A spoken answer as its declared type, or as text when it will not convert.

    Returning the raw string rather than refusing is deliberate: "about three
    thousand" is a real answer to a number field, and dropping it loses
    information a person reading the record would want. The API validates
    against the agent's schema on the way in, and a person is a better judge of
    "about three thousand" than a cast is.
    """
    if isinstance(value, bool):
        return value if declared_type == "boolean" else str(value).lower()

    text = str(value).strip()
    if not text:
        return None

    if declared_type == "boolean":
        lowered = text.lower()
        if lowered in _TRUE_WORDS:
            return True
        if lowered in _FALSE_WORDS:
            return False
        return text

    if declared_type in {"number", "integer"}:
        # Spoken numbers arrive with currency symbols, commas, and units.
        digits = re.sub(r"[^0-9.\-]", "", text)
        if digits and digits not in {"-", ".", "-."}:
            try:
                return int(digits) if declared_type == "integer" else float(digits)
            except ValueError:
                pass
        return text

    return text


@dataclass
class Collector:
    """The values gathered during one call.

    Mutable and single-call by design - one instance per `run_call`, handed to
    the `record_field` tool as a closure. It holds no session and does no I/O,
    so the tool stays a two-line adapter.
    """

    fields: list[CollectField] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)
    #: Set by `end_call`, read by the worker to close the room. A separate flag
    #: rather than a callback so the decision to hang up and the mechanics of
    #: hanging up stay on opposite sides of the tool boundary.
    hangup_reason: str | None = None

    def __post_init__(self) -> None:
        self._by_key = {f.key: f for f in self.fields}

    @property
    def keys(self) -> list[str]:
        return [f.key for f in self.fields]

    def record(self, key: str, value: Any) -> str:
        """Store one answer. Returns what the agent is told back.

        An unknown key is refused rather than stored: the agent asking for a
        field nobody declared means it invented one, and letting that through
        would put a hallucinated field on a customer's record.
        """
        declared = self._by_key.get(key)
        if declared is None:
            log.warning("agent tried to record an undeclared field: %s", key)
            return f"There is no field called {key}. Record only the fields you were given."

        coerced = coerce(value, declared.declared_type)
        if coerced is None:
            return f"That was empty, so {key} was not recorded. Ask again."

        self.values[key] = coerced
        return f"Recorded {key}."

    def missing(self) -> list[str]:
        """Required fields with no answer yet, in the order they were declared."""
        return [f.key for f in self.fields if f.required and f.key not in self.values]

    def request_hangup(self, reason: str) -> None:
        # First reason wins: the thing that made the agent hang up is the first
        # thing it decided, and a second call while the room is closing would
        # otherwise rewrite it.
        if self.hangup_reason is None:
            self.hangup_reason = reason.strip() or "the contact asked to end the call"


def recover_missing(
    fields: list[CollectField], collected: dict[str, Any], transcript: str
) -> dict[str, Any]:
    """Fields still absent, read back out of the transcript where possible.

    A deliberately narrow pass: it looks for the field's own key or description
    words followed by a value on the same line, which is the shape a transcript
    takes when the agent asked directly. It does not attempt inference - a
    second LLM call to interpret the conversation is a real design option, but a
    guess that *looks* like an answer is worse than a field marked unanswered,
    because a person is then never asked.

    Returns only newly found values. The caller merges them under the recorded
    ones, never over.
    """
    if not transcript or not fields:
        return {}

    scan = transcript[:_MAX_SCAN_CHARS]
    if len(transcript) > _MAX_SCAN_CHARS:
        log.info("transcript truncated to %d chars for field recovery", _MAX_SCAN_CHARS)

    found: dict[str, Any] = {}
    for declared in fields:
        if declared.key in collected:
            continue
        value = _scan_for(declared, scan)
        if value is not None:
            found[declared.key] = value
    return found


def _scan_for(declared: CollectField, transcript: str) -> Any:
    """The value stated for one field, or None if the transcript does not say."""
    label = declared.key.replace("_", " ").strip()
    if not label:
        return None

    # `budget: 40000` and `budget is 40000` are the two forms a transcript
    # actually contains. Anchored to a contact turn so the agent's own question
    # ("what is your budget?") is not read back as the answer.
    pattern = re.compile(
        rf"^Contact:.*\b{re.escape(label)}\b\s*(?:is|was|:|=)\s*(?P<value>[^.,;\n]{{1,80}})",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(transcript)
    if match is None:
        return None

    value = coerce(match.group("value"), declared.declared_type)
    if value is None:
        return None
    log.info("recovered %s from the transcript", declared.key)
    return value


__all__ = [
    "CollectField",
    "Collector",
    "coerce",
    "fields_from_metadata",
    "recover_missing",
]
