"""provider_credentials

Org-owned Twilio/Plivo credentials, so an organisation can dial from its own
number instead of relying solely on CALL-E. Twilio and Plivo both authenticate
with an identifier + secret pair (Account SID + Auth Token; Auth ID + Auth
Token) rather than OAuth, so this is a simple encrypted-credential store, not an
OAuth connection flow.

`identifier` and `secret` are stored Fernet-encrypted (`app/core/crypto.py`),
using `PROVIDER_CREDENTIALS_KEY` - a key that lives only in this process's
environment, the same sensitivity class as `SUPABASE_SECRET_KEY`. Unlike an API
key, this can't just be a hash: the value has to be read back in plaintext to
authenticate with the vendor when a call is actually placed over the org's own
number (voice-agent platform work, not part of this change) - encryption, not
hashing, is the right primitive for a value that must be recoverable.

One credential set per org per provider (`unique(org_id, provider)`); saving
again overwrites the previous one rather than accumulating rows.

Revision ID: f6a3c9d1b527
Revises: e5f2b8d0a416
Created: 2026-08-07 16:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6a3c9d1b527"
down_revision: str | None = "e5f2b8d0a416"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


POLICIES = """
alter table public.provider_credentials enable row level security;
alter table public.provider_credentials force  row level security;

create policy provider_credentials_select on public.provider_credentials for select
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy provider_credentials_insert on public.provider_credentials for insert
  with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy provider_credentials_update on public.provider_credentials for update
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy provider_credentials_delete on public.provider_credentials for delete
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));
"""

GRANTS = (
    "grant select, insert, update, delete on public.provider_credentials to authenticated;"
)


def upgrade() -> None:
    op.create_table(
        "provider_credentials",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("identifier_encrypted", sa.Text(), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["public.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "provider", name="provider_credentials_org_provider_key"),
        sa.CheckConstraint("provider in ('twilio', 'plivo')", name="provider_credentials_provider_check"),
        schema="public",
    )
    op.create_index("provider_credentials_org_idx", "provider_credentials", ["org_id"], schema="public")

    op.execute(POLICIES)
    op.execute(GRANTS)


def downgrade() -> None:
    op.drop_index("provider_credentials_org_idx", table_name="provider_credentials", schema="public")
    op.drop_table("provider_credentials", schema="public")
