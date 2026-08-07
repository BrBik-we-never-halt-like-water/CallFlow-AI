"""SQLAlchemy tables. Structure only.

Alembic autogenerates from this metadata, and it cannot see RLS, policies,
triggers, functions, or grants — those are hand-written in the revision that needs
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
    # Null until a person confirms the org's name — distinguishes a real setup from
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
    data-subject erasure nulls it while keeping the hash — forgetting that someone
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

    Only `key_hash` (SHA-256 of the full key) is ever stored — the plaintext key
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
    """An org's own Twilio or Plivo credentials, for dialling from its own number.

    `identifier_encrypted`/`secret_encrypted` are Fernet ciphertext, never
    plaintext — see `app/core/crypto.py`. One row per organisation per provider.
    """

    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("org_id", "provider", name="provider_credentials_org_provider_key"),
        CheckConstraint(
            "provider in ('twilio', 'plivo')", name="provider_credentials_provider_check"
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
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    identifier_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(20))


__all__ = [
    "ApiKey",
    "Base",
    "Membership",
    "OrgRole",
    "Organisation",
    "ProviderCredential",
    "Suppression",
    "SuppressionSource",
    "User",
    "org_role_enum",
    "suppression_source_enum",
]
