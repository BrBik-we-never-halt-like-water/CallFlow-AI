"""provider_credentials: one encrypted blob per provider, not two fixed columns

`identifier_encrypted` + `secret_encrypted` fit a vendor with exactly two
secrets. Most have one (Deepgram, ElevenLabs, Anthropic); several have three or
four (Azure wants a key, a region and an endpoint; AWS wants two keys and a
region; S3 adds a bucket; Langfuse wants a keypair and a host). Widening by
adding a column per vendor is the same treadmill the `provider` check was moved
off in `a7c4e2f9b813`.

So the shape moves to `fields_encrypted`: one Fernet ciphertext holding a JSON
object, keyed by the `CredentialField.key` values each provider declares in
`app/domain/providers.py`. One column, one ciphertext, and a new vendor is an
application change again.

**Encrypted as a whole, not per field.** Encrypting each value separately would
put the field *names* in plaintext and leak the shape of every credential to
anyone reading the table; it also multiplies the Fernet overhead by the field
count. The whole object is one token.

**The old columns stay, nullable, and are not backfilled here.** A backfill
would have to decrypt, which means this migration would need
`PROVIDER_CREDENTIALS_KEY` - a migration that fails on a missing application
secret is a migration nobody can run to inspect a database. Instead the read
path in `repositories/provider_credentials.py` falls back to the two old columns
when `fields_encrypted` is null, and the next write upgrades that row in place.
Delete the fallback (and these columns) once no row has a null `fields_encrypted`
- `select count(*) ... where fields_encrypted is null` is the whole check.

Revision ID: c8e1f4a29b76
Revises: a7c4e2f9b813
Created: 2026-08-16 14:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8e1f4a29b76"
down_revision: str | None = "a7c4e2f9b813"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provider_credentials",
        sa.Column("fields_encrypted", sa.Text(), nullable=True),
        schema="public",
    )
    # Nullable from here on: a provider with one secret writes only
    # `fields_encrypted`, and NOT NULL would force it to store a meaningless
    # empty ciphertext in a column nothing reads.
    op.alter_column(
        "provider_credentials",
        "identifier_encrypted",
        existing_type=sa.Text(),
        nullable=True,
        schema="public",
    )
    op.alter_column(
        "provider_credentials",
        "secret_encrypted",
        existing_type=sa.Text(),
        nullable=True,
        schema="public",
    )
    # A row has to carry its credentials one way or the other. Without this a
    # bug that skips both writes stores a row that looks connected in the
    # interface and authenticates with nothing (CLAUDE.md non-negotiable #9).
    op.create_check_constraint(
        "provider_credentials_has_credentials",
        "provider_credentials",
        "fields_encrypted is not null or secret_encrypted is not null",
        schema="public",
    )


def downgrade() -> None:
    # Rows written after the upgrade carry their secrets only in
    # `fields_encrypted`, and restoring NOT NULL on the old columns would fail
    # against them. The constraint is dropped and the columns left nullable:
    # a downgrade undoes this revision, it does not resurrect a shape the data
    # no longer fits.
    op.drop_constraint(
        "provider_credentials_has_credentials",
        "provider_credentials",
        type_="check",
        schema="public",
    )
    op.drop_column("provider_credentials", "fields_encrypted", schema="public")
