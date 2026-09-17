"""Domain models for voice agents, contacts, and call outcomes."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.domain.safety import is_e164

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


class DialFailure(str, Enum):
    """A vendor-neutral reason a call attempt itself failed - never placed, or
    never came back - as opposed to `Disposition`, which is the triage decision
    once a call *did* happen. CLAUDE.md's Substitutability section calls for
    exactly this: retry policy keys off this name, never a vendor error string,
    so a second voice provider slots in without every caller re-learning a new
    vocabulary of failures.
    """

    INVALID_NUMBER = "invalid_number"
    RATE_LIMITED = "rate_limited"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    POLICY_VIOLATION = "policy_violation"
    UNAUTHORIZED = "unauthorized"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TIMED_OUT = "timed_out"
    # The line itself answered with a reason, rather than the request failing.
    # Added when SIP became the transport: a carrier reports "486 Busy Here" and
    # "480 Temporarily Unavailable" distinctly, and collapsing either into
    # PROVIDER_UNAVAILABLE would tell an operator our provider broke when in fact
    # the person was on another call. Extending this enum is the intended move -
    # what CLAUDE.md forbids is a *second* vocabulary alongside it.
    BUSY = "busy"
    NO_ANSWER = "no_answer"
    INTERNAL = "internal"


class Disposition(str, Enum):
    """What the orchestrator decided to do after the call resolved."""

    # Not a decision - the call is still happening. Lets the dashboard show a
    # row while it runs instead of nothing until it ends.
    IN_FLIGHT = "in_flight"
    AUTO_CLOSED = "auto_closed"
    ESCALATED = "escalated"
    RETRY = "retry"
    UNREACHABLE = "unreachable"
    SKIPPED = "skipped"


# The two dispositions that read as "needs a person" everywhere in the
# product - the same grouping `lib/lamp.ts`'s `flare` state already uses on
# the frontend. Kept here, not just on the frontend, because Phase 2 of the
# role-based UI roadmap persists a real `escalations` row for exactly this
# set - the two must never drift apart.
NEEDS_A_PERSON_DISPOSITIONS = frozenset({Disposition.ESCALATED, Disposition.UNREACHABLE})


class CallResult(str, Enum):
    """Axis 1 of the graded-lead model: did a conversation happen at all?

    `docs/GRADING.md` §1-2.1 is the source of truth for this enum and for
    `LeadGrade`/`NextAction`/`DeclineReason` below - read it before changing
    any of the four. `Disposition` above answers "does this call need a
    human?"; this answers "did we speak to them?", which is a different
    question `Disposition` cannot express (`GRADING.md` intro).
    """

    IN_FLIGHT = "in_flight"
    SPOKE = "spoke"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    VOICEMAIL = "voicemail"
    INVALID_NUMBER = "invalid_number"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class LeadGrade(str, Enum):
    """Axis 2: is this lead worth a human's time? Only meaningful when
    `CallResult.SPOKE` - see `GRADING.md` §1, §2.2."""

    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    REFUSED = "refused"
    WRONG_PERSON = "wrong_person"
    # Extraction failed, or came back unusable. Never a silent COLD - a
    # fabricated rejection poisons the decline report (`GRADING.md` §2.2).
    UNGRADED = "ungraded"


class NextAction(str, Enum):
    """Axis 3: what a human does with the row. Always set, graded or not
    (`GRADING.md` §2.3, §4.1a)."""

    CALL_NOW = "call_now"
    CALL_AT = "call_at"
    NURTURE = "nurture"
    DROP = "drop"
    SUPPRESS = "suppress"
    FIX_DATA = "fix_data"


class DeclineReason(str, Enum):
    """Why a lead said no. Aggregates for the decline report; `decline_note`
    carries what the enum cannot (`GRADING.md` §2.4)."""

    ALREADY_ENROLLED_ELSEWHERE = "already_enrolled_elsewhere"
    PRICE_OR_EMI = "price_or_emi"
    DEGREE_VALIDITY_DOUBT = "degree_validity_doubt"
    WRONG_PROGRAMME = "wrong_programme"
    NO_TIME = "no_time"
    EMPLOYER_WONT_SPONSOR = "employer_wont_sponsor"
    STILL_DECIDING = "still_deciding"
    LANGUAGE_BARRIER = "language_barrier"
    DO_NOT_CONTACT = "do_not_contact"
    OTHER = "other"


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


#: The types a collect field may declare. Moved here from the deleted
#: `domain/campaigns.py`, where it described a campaign's `extra_fields` - the
#: set is unchanged because the field shape is.
FIELD_TYPES = {"string", "boolean", "integer", "number"}


class CollectField(BaseModel):
    """One thing the agent has to establish while the call is happening.

    The stored shape of a `voice_agents.collect_fields` entry, and deliberately
    the same field shape campaigns used for `extra_fields`: both end as
    structured call results, and a second format would mean a second validator to
    keep in step.

    `required` is load-bearing rather than advisory - ADR-5 makes a missing
    required field escalate a completed call to a person, with the field's own
    `description` becoming what that person is told to ask.
    """

    key: str
    type: str = "string"
    description: str = ""
    required: bool = False


class RunAgent(BaseModel):
    """A voice agent, as the run pipeline needs it.

    The successor to `Campaign`. A campaign owned the goal template, the result
    schema and the escalation policy; a voice agent owns all three better -
    `system_prompt` is the instruction, `collect_fields` is the contract, and
    both are configured once and reused across runs (ADR-8).

    Deliberately narrower than the `voice_agents` row: this carries what deciding
    and rendering a call needs, and nothing about who created the agent or which
    vendors it runs on. The provider choices travel separately, as the opaque
    `voice_agent` metadata dict the worker reads (`services/run_dispatch.py`), so
    the domain never holds a decrypted credential.

    Named `RunAgent` rather than `AgentSpec` on purpose: the voice runtime already
    has an `AgentSpec` for the provider half, and two different types with one
    name across two processes that talk to each other is a trap.
    """

    id: str
    name: str
    #: What the agent is told, before this contact's own detail is added.
    #: Supports `{name}` and `{context_key}` placeholders - see
    #: `domain/prompt_assembly.py`.
    system_prompt: str | None = None
    #: What the agent has to come back with. An empty list is a
    #: conversation-only agent, which is legal.
    collect_fields: list[CollectField] = Field(default_factory=list)
    language: str | None = None
    #: Whether a negative-sentiment call is worth one retry or a person. Carried
    #: on the agent now that campaigns are gone; `triage()` still reads it as a
    #: parameter rather than reaching for the agent itself.
    escalate_on_negative: bool = True

    @property
    def required_field_keys(self) -> list[str]:
        """The fields whose absence sends a call to a person (ADR-5)."""
        return [f.key for f in self.collect_fields if f.required]


class AttemptSummary(BaseModel):
    """One dial attempt at a recipient - CALL-E can redial the same recipient
    within one call task, and tracks each attempt separately in
    `recipients[].attempts[]`. `CallOutcome` used to keep only whichever
    attempt `_final_attempt()` picked for its transcript and discard the
    rest; this preserves the full history alongside it."""

    status: str
    started_at: str | None = None
    completed_at: str | None = None
    had_transcript: bool = False


class CallOutcome(BaseModel):
    """Everything CallFlow AI knows after one call reaches a terminal state."""

    contact_name: str
    phone_masked: str
    #: Which agent held this conversation. Nullable, unlike the `campaign_id` it
    #: replaces: rows written before ADR-8 have no agent, and a call outcome is a
    #: permanent record - backfilling a placeholder would invent history.
    voice_agent_id: str | None = None

    status: str = "UNKNOWN"
    plan_id: str | None = None
    run_id: str | None = None
    #: Which of the organisation's lines placed this call, masked. Without it the
    #: records surface cannot say where a call came from, and a run spread across
    #: several numbers is the case where that matters.
    from_number_masked: str | None = None

    #: The suppression key for the number that was dialled - SHA-256 over the
    #: E.164 plus the per-deployment pepper, the same value `suppressions` is
    #: keyed on.
    #:
    #: Set by the dialler, which is the last thing that holds the real number.
    #: It exists so a contact who says "never call me again" can actually be
    #: suppressed: the completion callback that hears them receives only
    #: `phone_masked`, and a masked number cannot be hashed, so without this the
    #: opt-out could be escalated to a person but never enforced against the
    #: next run.
    #:
    #: **Never serialised to a client.** No response model reads it and
    #: `list_outcomes` does not select it - it travels from the dialler to
    #: `call_outcomes` and is read back only by `phone_hash_for_outcome`. It is
    #: not a number, but it is a stable per-number identifier, and the surfaces
    #: that show a call have no use for one.
    phone_hash: str | None = None

    transcript: str | None = None
    summary: str | None = None

    sentiment: Sentiment = Sentiment.UNKNOWN
    sentiment_reason: str | None = None
    #: The triage signals - `sentiment`, `wants_human_callback`, `do_not_call`,
    #: `frustration_signals`. CallFlow's own contract, read by `triage()`.
    extracted: dict[str, Any] = Field(default_factory=dict)

    #: The organisation's own business fields, from the agent's `collect_fields`.
    #: Deliberately separate from `extracted`: merging them would let a field an
    #: org happened to name `sentiment` rewrite triage's own input, the same
    #: collision `run_dialer`'s spread-first metadata dict already guards
    #: against.
    collected: dict[str, Any] = Field(default_factory=dict)
    #: Required fields the call ended without (ADR-5). Empty means complete.
    #: Orthogonal to `disposition` rather than a replacement for it - a call can
    #: be clean in every other respect and still be missing an answer nobody
    #: volunteered.
    missing_required_fields: list[str] = Field(default_factory=list)
    #: What a person still has to ask, in the agent's own words. Written for the
    #: human reading the "needs a person" queue, so a callback asks only for what
    #: is actually outstanding.
    handoff_questions: list[str] = Field(default_factory=list)

    # CALL-E's own holistic judgment of whether the call accomplished its
    # task - confirmed against the live OpenAPI spec as task-level fields,
    # never per-recipient. Independent of `extracted`: an agent's own
    # collect_fields can be satisfied while the model still judges the
    # conversation itself unresolved (see `triage()`'s use of
    # `task_completed`).
    task_completed: bool | None = None
    completion_confidence_score: float | None = None
    completion_confidence_label: str | None = None
    evidence: list[str] = Field(default_factory=list)
    attempts: list[AttemptSummary] = Field(default_factory=list)

    disposition: Disposition = Disposition.SKIPPED
    disposition_reason: str | None = None

    #: The graded-lead model (`docs/GRADING.md`). Additive beside `disposition`
    #: - nothing drops that column until every reader has moved across
    #: (`GRADING.md` §8). `grade` is null whenever `result` is not `SPOKE`;
    #: never inferred as `COLD` for an unreachable call.
    result: CallResult | None = None
    grade: LeadGrade | None = None
    #: Prose a rep can read in one line - never a rule id (`GRADING.md` §4.3).
    grade_reason: str | None = None
    next_action: NextAction | None = None
    callback_at: datetime | None = None
    decline_reason: DeclineReason | None = None
    decline_note: str | None = None
    #: Two lines for the handoff queue: what they said, what to open with.
    #: Populated by a later task (`GRADING.md` §6, task A10) - present on the
    #: model now so the column exists ahead of the writer.
    handoff_brief: str | None = None
    #: A rep's thumbs-up/down on a handed-over lead. Null until reviewed.
    #: The accept-rate metric - "is this working" made measurable rather than
    #: an opinion (`GRADING.md` §6).
    human_verdict: bool | None = None

    error: str | None = None
    duration_seconds: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def answered(self) -> bool:
        return self.status.upper() in ANSWERED_STATUSES
