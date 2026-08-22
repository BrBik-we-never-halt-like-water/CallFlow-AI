"""SQLAlchemy tables. Structure only.

Alembic autogenerates from this metadata, and it cannot see RLS, policies,
triggers, functions, or grants - those are hand-written in the revision that needs
them. A table added here without its policy there ships with no tenant scoping.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    # Declared once so a plain `Mapped[datetime]` can never become a naive column.
    type_annotation_map: ClassVar[dict] = {
        datetime: DateTime(timezone=True),
        dict: JSONB,
    }


class OrgRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class SuppressionSource(str, enum.Enum):
    OPT_OUT = "opt_out"
    MANUAL = "manual"
    IMPORTED = "imported"
    API = "api"


def _pg_enum(python_enum: type[enum.Enum], name: str) -> Enum:
    # create_type=False: the types are created once in the initial revision, so
    # later revisions touching these columns do not re-emit CREATE TYPE.
    return Enum(
        python_enum,
        name=name,
        values_callable=lambda e: [member.value for member in e],
        create_type=False,
    )


org_role_enum = _pg_enum(OrgRole, "org_role")
suppression_source_enum = _pg_enum(SuppressionSource, "suppression_source")


class TimestampedMixin:
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class User(TimestampedMixin, Base):
    """A person.

    `auth_user_id` is the only reference to the auth provider in the schema.
    Everything else joins on `User.id`, so changing provider repopulates one
    column instead of rewriting every foreign key.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    auth_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Membership.user_id",
    )


class Organisation(TimestampedMixin, Base):
    """The tenant. All business data belongs to one of these."""

    __tablename__ = "organisations"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(name)) between 1 and 120", name="organisations_name_length"
        ),
        Index("organisations_active_idx", "id", postgresql_where=text("deleted_at IS NULL")),
        # Partial, so a soft-deleted organisation releases its slug for reuse.
        Index(
            "organisations_slug_active_key",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text)
    plan_id: Mapped[str] = mapped_column(String(32), nullable=False, server_default="free")

    # Paise. A derived cache of credit_ledger once F36 lands; the ledger is the truth.
    credit_balance_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )

    country: Mapped[str | None] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="Asia/Kolkata")
    deleted_at: Mapped[datetime | None] = mapped_column()
    # Null until a person confirms the org's name - distinguishes a real setup from
    # the auto-generated placeholder the signup trigger names a fresh org with.
    onboarded_at: Mapped[datetime | None] = mapped_column()

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="organisation", cascade="all, delete-orphan"
    )
    suppressions: Mapped[list[Suppression]] = relationship(
        back_populates="organisation", cascade="all, delete-orphan"
    )


class Membership(Base):
    """Which user belongs to which organisation, and with what authority."""

    __tablename__ = "memberships"
    __table_args__ = (
        Index("memberships_user_idx", "user_id"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[OrgRole] = mapped_column(
        org_role_enum, nullable=False, server_default=OrgRole.OPERATOR.value
    )

    # SET NULL so the audit trail survives the inviter leaving.
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    joined_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    organisation: Mapped[Organisation] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships", foreign_keys=[user_id])


class Suppression(Base):
    """Do-not-call list. Organisation-wide and permanent.

    `phone_hash` is the enforcement key: SHA-256 over the E.164 number plus a
    per-deployment pepper, computed in the application so the pepper never enters
    the database. `phone_e164` exists only for display and export, and a
    data-subject erasure nulls it while keeping the hash - forgetting that someone
    opted out is worse than remembering it.
    """

    __tablename__ = "suppressions"
    __table_args__ = (
        UniqueConstraint("org_id", "phone_hash", name="suppressions_org_phone_key"),
        CheckConstraint("length(phone_hash) = 64", name="suppressions_hash_length"),
        Index("suppressions_org_recent_idx", "org_id", text("suppressed_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    phone_e164: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[SuppressionSource] = mapped_column(
        suppression_source_enum,
        nullable=False,
        server_default=SuppressionSource.MANUAL.value,
    )
    reason: Mapped[str | None] = mapped_column(Text)
    suppressed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    suppressed_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    organisation: Mapped[Organisation] = relationship(back_populates="suppressions")


class ApiKey(Base):
    """An org-scoped credential for programmatic access to CallFlow's own API.

    Only `key_hash` (SHA-256 of the full key) is ever stored - the plaintext key
    is shown to the caller exactly once, at creation, and never again.
    """

    __tablename__ = "api_keys"
    __table_args__ = (
        UniqueConstraint("key_hash"),
        CheckConstraint("length(key_hash) = 64", name="api_keys_hash_length"),
        Index("api_keys_org_idx", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class ProviderCredential(TimestampedMixin, Base):
    """An org's own third-party credentials - carrier, STT, TTS, LLM, or storage.

    `fields_encrypted` is one Fernet ciphertext holding a JSON object keyed by
    the field names that provider declares in `app/domain/providers.py`. One
    ciphertext rather than one per field: encrypting values separately would
    leave the field *names* in plaintext and leak the shape of every credential.

    `identifier_encrypted`/`secret_encrypted` are the superseded two-column
    form, kept nullable so rows written before `c8e1f4a29b76` still read. The
    repository falls back to them and the next write upgrades the row; both
    columns go once nothing has a null `fields_encrypted`.

    One row per organisation per provider - and a provider can serve several
    roles (one Deepgram key does speech-to-text *and* text-to-speech), so the
    row is keyed on the vendor, never on what it is being used for.

    `provider` carries no database-level allow-list beyond "not blank": the set
    of accepted names is validated in the Pydantic layer instead, so adding a
    vendor is an app change rather than a migration (`PLATFORM_PIVOT_PLAN.md`
    ADR-4). Keep the two in step - the database will accept anything non-empty.
    """

    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("org_id", "provider", name="provider_credentials_org_provider_key"),
        CheckConstraint("provider <> ''", name="provider_credentials_provider_not_blank"),
        CheckConstraint(
            "fields_encrypted is not null or secret_encrypted is not null",
            name="provider_credentials_has_credentials",
        ),
        Index("provider_credentials_org_idx", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    fields_encrypted: Mapped[str | None] = mapped_column(Text)
    identifier_encrypted: Mapped[str | None] = mapped_column(Text)
    secret_encrypted: Mapped[str | None] = mapped_column(Text)
    phone_number: Mapped[str | None] = mapped_column(String(20))


class AiProviderCredential(TimestampedMixin, Base):
    """An org's own API key for an AI vendor used by its voice agents.

    `api_key_encrypted` is Fernet ciphertext, never plaintext - see
    `app/core/crypto.py`. One row per organisation per provider. Deliberately
    a separate table from `ProviderCredential`: that one holds Twilio/Plivo
    telephony credentials (identifier + secret); this one holds single-API-key
    STT/TTS/LLM vendors.
    """

    __tablename__ = "ai_provider_credentials"
    __table_args__ = (
        UniqueConstraint("org_id", "provider", name="ai_provider_credentials_org_provider_key"),
        CheckConstraint(
            "provider in ('sarvam', 'deepgram', 'elevenlabs', 'openai', 'openrouter')",
            name="ai_provider_credentials_provider_check",
        ),
        Index("ai_provider_credentials_org_idx", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)


class VoiceAgent(Base):
    """What a live conversation runs with: which STT, TTS and LLM to use, whose
    credentials to authenticate each with, and which number to dial from.

    Read access is org-wide, not per-creator - an agent is infrastructure a
    whole team dials against, not one person's private work product.

    One number per agent for V1 - an org with several agents connects a number
    per agent rather than sharing a pool. Every provider/credential column is
    nullable because an agent is built up incrementally in the Agentic tab, and
    a half-configured agent must be storable; the check that it is *complete
    enough to dial* belongs at run-start, not in the schema.
    """

    __tablename__ = "voice_agents"
    __table_args__ = (
        CheckConstraint("kind in ('custom', 'prebuilt')", name="voice_agents_kind_check"),
        # No `telephony_provider in (...)` check: the provisioning branch adds
        # carriers (Telnyx, Vonage) behind `app/domain/providers.py`, and a
        # constraint listing them here would have to be migrated every time
        # one is added. The allowed set lives with the adapters instead.
        Index("voice_agents_org_idx", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)

    stt_provider: Mapped[str | None] = mapped_column(Text)
    stt_credential_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("provider_credentials.id", ondelete="RESTRICT")
    )
    tts_provider: Mapped[str | None] = mapped_column(Text)
    tts_credential_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("provider_credentials.id", ondelete="RESTRICT")
    )
    llm_provider: Mapped[str | None] = mapped_column(Text)
    llm_credential_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("provider_credentials.id", ondelete="RESTRICT")
    )
    # Required when llm_provider = 'openrouter': one credential proxies many
    # models, so the credential alone does not say which one to run.
    llm_model: Mapped[str | None] = mapped_column(Text)

    telephony_provider: Mapped[str | None] = mapped_column(Text)
    telephony_credential_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("provider_credentials.id", ondelete="RESTRICT")
    )

    prebuilt_persona: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    voice_id: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class TelephonyProvisioning(TimestampedMixin, Base):
    """One attempt to connect a number to a voice agent.

    A row per attempt, not per agent: a failed attempt keeps its `last_error`
    when a fresh attempt is started, so the trail of what was tried survives.
    Rows are re-statused, never deleted - there is no delete policy and no
    delete grant on this table.

    `idempotency_key` is unique per agent so a double-submitted attempt cannot
    create two rows, and so a retry of the *same* attempt can look up what it
    already created (a LiveKit trunk, say) rather than re-running the step and
    orphaning a second one.
    """

    __tablename__ = "telephony_provisioning"
    __table_args__ = (
        UniqueConstraint(
            "voice_agent_id", "idempotency_key", name="telephony_provisioning_agent_key_uniq"
        ),
        CheckConstraint(
            "status in ('pending', 'provisioning', 'verified', 'failed')",
            name="telephony_provisioning_status_check",
        ),
        Index("telephony_provisioning_org_idx", "org_id"),
        Index("telephony_provisioning_agent_idx", "voice_agent_id", text("seq desc")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Monotonic, unlike `created_at` (transaction time, so it ties) and `id`
    # (a random uuid). The only column that can answer "which attempt is newest".
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False)
    voice_agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("voice_agents.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)

    livekit_inbound_trunk_id: Mapped[str | None] = mapped_column(Text)
    livekit_outbound_trunk_id: Mapped[str | None] = mapped_column(Text)
    livekit_dispatch_rule_id: Mapped[str | None] = mapped_column(Text)
    # Plivo's <trunk_id>.zt.plivo.com. Null for Twilio, which has no analog.
    carrier_termination_domain: Mapped[str | None] = mapped_column(Text)
    # Shown to the operator verbatim when status = 'failed', so it must read as
    # an instruction rather than a stack trace (CLAUDE.md §5).
    last_error: Mapped[str | None] = mapped_column(Text)


__all__ = [
    "AiProviderCredential",
    "ApiKey",
    "Base",
    "Membership",
    "OrgRole",
    "Organisation",
    "ProviderCredential",
    "Suppression",
    "SuppressionSource",
    "TelephonyProvisioning",
    "User",
    "VoiceAgent",
    "org_role_enum",
    "suppression_source_enum",
]
