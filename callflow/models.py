"""Domain models for campaigns, contacts, and call outcomes."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .safety import is_e164

# Terminal call statuses reported by the voice engine.
TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        "BUSY",
        "CANCELED",
        "CANCELLED",
        "COMPLETED",
        "DECLINED",
        "EXPIRED",
        "FAILED",
        "NO_ANSWER",
        "VOICEMAIL",
    }
)

# Statuses where a human actually picked up and talked.
ANSWERED_STATUSES: frozenset[str] = frozenset({"COMPLETED"})


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class Disposition(str, Enum):
    """What the orchestrator decided to do after the call resolved."""

    # Not a decision — the call is still happening. Lets the dashboard show a
    # row while it runs instead of nothing until it ends.
    IN_FLIGHT = "in_flight"
    AUTO_CLOSED = "auto_closed"
    ESCALATED = "escalated"
    RETRY = "retry"
    UNREACHABLE = "unreachable"
    SKIPPED = "skipped"


class Contact(BaseModel):
    name: str
    phone: str
    region: str | None = None
    language: str | None = None
    # Arbitrary business context merged into the call goal and engine metadata.
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        if not is_e164(v):
            raise ValueError(f"phone must be E.164 (e.g. +15555550100), got {v!r}")
        return v


class Campaign(BaseModel):
    """A goal applied across many contacts, with a typed result contract."""

    id: str
    name: str
    # Instruction template for the engine's `goal` field. Supports {name}, {context[key]}.
    goal_template: str
    # JSON-schema-ish description of what to extract from the transcript.
    outcome_fields: dict[str, str] = Field(default_factory=dict)
    region: str | None = None
    language: str | None = None
    escalate_on_negative: bool = True


class CallOutcome(BaseModel):
    """Everything CallFlow AI knows after one call reaches a terminal state."""

    contact_name: str
    phone_masked: str
    campaign_id: str

    status: str = "UNKNOWN"
    plan_id: str | None = None
    run_id: str | None = None

    transcript: str | None = None
    summary: str | None = None

    sentiment: Sentiment = Sentiment.UNKNOWN
    sentiment_reason: str | None = None
    extracted: dict[str, Any] = Field(default_factory=dict)

    disposition: Disposition = Disposition.SKIPPED
    disposition_reason: str | None = None

    dry_run: bool = True
    error: str | None = None
    duration_seconds: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def answered(self) -> bool:
        return self.status.upper() in ANSWERED_STATUSES
