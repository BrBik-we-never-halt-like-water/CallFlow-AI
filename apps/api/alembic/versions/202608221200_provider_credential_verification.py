"""provider_credentials: when the vendor last confirmed this credential works

The interface said "Connected" for any row that existed, which made it a claim
about the *save* rather than about the credential. Pasting a typo produced a
connected-looking integration whose first symptom was a failed call - CLAUDE.md
non-negotiable #9.

`verified_at` is what makes the distinction storable. It is set only when
`app/integrations/credential_probe.py` has authenticated against the vendor and
been accepted, so:

  not null  -> the vendor accepted these exact credentials at that moment
  null      -> stored, unconfirmed. Either the vendor could not be reached, or
               CallFlow has no cheap authenticated read for it (Sarvam), or the
               row predates this column.

Nullable with no backfill and no default, deliberately. A default of `now()`
would assert that every credential already in the table had been checked, which
is precisely the false claim this column exists to stop, and a backfill cannot
check them without the encryption key (see `c8e1f4a29b76` for why a migration
must not need one). Existing rows read as unconfirmed until someone presses
Re-check, which is exactly what is true of them.

No RLS or grant work: `provider_credentials` already forces row level security
and `f6a3c9d1b527` grants at table level, not per column, so the new column
inherits both.

Revision ID: d1a83c5f27e6
Revises: c9f47a1e6b28
Created: 2026-08-22 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1a83c5f27e6"
down_revision: str | None = "c9f47a1e6b28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provider_credentials",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("provider_credentials", "verified_at", schema="public")
