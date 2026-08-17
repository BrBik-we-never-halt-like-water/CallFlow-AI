"""ai_provider_credentials, and the columns the Agentic tab adds to voice_agents

Org-scoped credentials for the AI vendors a voice agent can be wired to
(Sarvam, Deepgram, ElevenLabs, OpenAI, OpenRouter).

`ai_provider_credentials` is deliberately its own table, not a widened
`provider_credentials`. `provider_credentials` is telephony-first (carrier
account credentials) and owned by separate work - mixing the two would force
that table's column shape and check constraint to serve two unrelated vendor
classes. Same sensitivity tier and encrypted-at-rest posture
(`api_key_encrypted`, Fernet ciphertext via `app/core/crypto.py`) and the same
RLS gating - owner/admin only, because a vendor API key is a real, costed
secret.

**This revision originally created `voice_agents` too.** It no longer does.
`a7c4e2f9b813` (the platform pivot's schema half) creates that table with a
superset of the same columns plus the `*_credential_id` foreign keys, and both
revisions creating it left two Alembic heads that could not both be applied.
This one now runs *after* that chain and only adds what it is still missing:
`updated_at`, which the repository's `update_agent()` writes on every edit.
The `voice_agents` RLS policies and grants live in `a7c4e2f9b813` and are not
repeated here.

Revision ID: a1c48e7f2b93
Revises: c8e1f4a29b76
Created: 2026-08-15 14:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c48e7f2b93"
down_revision: str | None = "c8e1f4a29b76"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


POLICIES = """
alter table public.ai_provider_credentials enable row level security;
alter table public.ai_provider_credentials force  row level security;

create policy ai_provider_credentials_select on public.ai_provider_credentials for select
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy ai_provider_credentials_insert on public.ai_provider_credentials for insert
  with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy ai_provider_credentials_update on public.ai_provider_credentials for update
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy ai_provider_credentials_delete on public.ai_provider_credentials for delete
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));
"""

GRANTS = """
grant select, insert, update, delete on public.ai_provider_credentials to authenticated;
"""


def upgrade() -> None:
    op.create_table(
        "ai_provider_credentials",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["public.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "provider", name="ai_provider_credentials_org_provider_key"),
        sa.CheckConstraint(
            "provider in ('sarvam', 'deepgram', 'elevenlabs', 'openai', 'openrouter')",
            name="ai_provider_credentials_provider_check",
        ),
        schema="public",
    )
    op.create_index(
        "ai_provider_credentials_org_idx", "ai_provider_credentials", ["org_id"], schema="public"
    )

    op.add_column(
        "voice_agents",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema="public",
    )

    op.execute(POLICIES)
    op.execute(GRANTS)


def downgrade() -> None:
    op.drop_column("voice_agents", "updated_at", schema="public")

    op.drop_index(
        "ai_provider_credentials_org_idx", table_name="ai_provider_credentials", schema="public"
    )
    op.drop_table("ai_provider_credentials", schema="public")
