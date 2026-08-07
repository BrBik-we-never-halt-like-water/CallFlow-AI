"""organisations_onboarded_at

Adds a server-verified onboarding signal to `organisations`, replacing what would
otherwise be a client-only (`localStorage`) dismiss flag for the mandatory first-run
org setup screen.

A freshly-created organisation — whether from the signup trigger or the "create
another organisation" endpoint — gets a real name at creation time in the latter
case, but only an auto-generated placeholder (the email's local part or domain) in
the former. `onboarded_at` distinguishes "a person confirmed this name" from
"still whatever the trigger guessed." Existing organisations are backfilled to
`created_at` so nobody already using the product gets retroactively gated.

Revision ID: d4e1a7c9f203
Revises: c7a4e9f21b58
Created: 2026-08-07 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e1a7c9f203"
down_revision: str | None = "c7a4e9f21b58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organisations",
        sa.Column("onboarded_at", sa.DateTime(timezone=True), nullable=True),
        schema="public",
    )
    # Grandfather every organisation that already exists — onboarding is a gate for
    # first-time setup, not a retroactive chore for accounts already in use.
    op.execute(
        "update public.organisations set onboarded_at = created_at where onboarded_at is null"
    )


def downgrade() -> None:
    op.drop_column("organisations", "onboarded_at", schema="public")
