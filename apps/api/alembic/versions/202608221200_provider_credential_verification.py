"""provider_credentials: when the vendor last confirmed this credential works

`services/credential_check.py` already asks the vendor whether a credential
works, and `connect_provider` already reports the answer - but only in the
response to that one request. Nothing stores it, so the answer survives exactly
as long as the toast does.

After a reload the card falls back to `spec.wired`, which is "does anything in a
call read this vendor", not "does this key work". A rejected credential is stored
too, so a typo ends up rendering as **Connected** the moment the page is
refreshed - the same false success the verification path was built to remove
(CLAUDE.md non-negotiable #9), just one navigation later.

`verified_at` is what makes the answer outlive the request. It is written only
where `check_credentials()` returned `ok=True`, so:

  not null  -> the vendor accepted these exact credentials at that moment
  null      -> stored, unconfirmed. `ok=False` (the vendor refused), `ok=None`
               (no probe declared, unreachable, or a key too narrowly scoped to
               confirm), or a row written before this column existed.

Nullable with no backfill and no default, deliberately. A default of `now()`
would assert that every credential already in the table had been checked, which
is precisely the false claim this column exists to stop, and a backfill cannot
check them without the encryption key (see `c8e1f4a29b76` for why a migration
must not need one). Existing rows read as unconfirmed until someone presses
Re-check, which is exactly what is true of them.

Note it stores *when*, not *whether*. A boolean cannot distinguish "checked and
accepted a minute ago" from "checked and accepted in March", and a key revoked
at the vendor's end makes that difference the whole point.

No RLS or grant work: `provider_credentials` already forces row level security
and `f6a3c9d1b527` grants at table level, not per column, so the new column
inherits both.

Revision ID: d1a83c5f27e6
Revises: e5c9d02a7f31
Created: 2026-08-22 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1a83c5f27e6"
down_revision: str | None = "e5c9d02a7f31"
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
