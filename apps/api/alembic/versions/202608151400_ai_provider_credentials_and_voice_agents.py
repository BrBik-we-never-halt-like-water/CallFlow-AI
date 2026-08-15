"""ai_provider_credentials_and_voice_agents

Two new tables for the voice-agent builder (the Agentic tab): org-scoped
credentials for the AI vendors a voice agent can be wired to (Sarvam, Deepgram,
ElevenLabs, OpenAI, OpenRouter), and the agent configurations themselves.

`ai_provider_credentials` is deliberately its own table, not a widened
`provider_credentials`. `provider_credentials` is telephony-only (Twilio/Plivo
Account SID + Auth Token pairs) and owned by separate, actively in-flight work -
mixing the two would force that table's column shape and check constraint to
serve two unrelated vendor classes and risk a collision with that team's own
migrations. Same sensitivity tier and encrypted-at-rest posture as
`provider_credentials` (`api_key_encrypted`, Fernet ciphertext via
`app/core/crypto.py`, not part of this change) and the same RLS gating -
owner/admin only, because a vendor API key is a real, costed secret.

`voice_agents` intentionally gets broader read access than either credentials
table: `select` is `is_org_member`, not role-gated, because an agent
configuration is org infrastructure that any teammate needs to see to run or
share a campaign against it - not a per-creator artifact the way a campaign is.
`insert`/`update` extend to operator (building and editing an agent is a
day-to-day action, the same tier as campaigns); `delete` stays owner/admin only,
so an operator can create and edit an agent but not remove one.

Revision ID: a1c48e7f2b93
Revises: b938fa82e54d
Created: 2026-08-15 14:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c48e7f2b93"
down_revision: str | None = "b938fa82e54d"
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

alter table public.voice_agents enable row level security;
alter table public.voice_agents force  row level security;

create policy voice_agents_select on public.voice_agents for select
  using (public.is_org_member(org_id));

create policy voice_agents_insert on public.voice_agents for insert
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

create policy voice_agents_update on public.voice_agents for update
  using (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

create policy voice_agents_delete on public.voice_agents for delete
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));
"""

GRANTS = """
grant select, insert, update, delete on public.ai_provider_credentials to authenticated;
grant select, insert, update, delete on public.voice_agents to authenticated;
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

    op.create_table(
        "voice_agents",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), server_default="custom", nullable=False),
        sa.Column("stt_provider", sa.Text(), nullable=True),
        sa.Column("tts_provider", sa.Text(), nullable=True),
        sa.Column("llm_provider", sa.Text(), server_default="openrouter", nullable=True),
        sa.Column("llm_model", sa.Text(), nullable=True),
        sa.Column("voice_id", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("prebuilt_persona", sa.Text(), nullable=True),
        sa.Column("telephony_provider", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["public.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind in ('custom', 'prebuilt')", name="voice_agents_kind_check"),
        sa.CheckConstraint(
            "telephony_provider in ('twilio', 'plivo')",
            name="voice_agents_telephony_provider_check",
        ),
        schema="public",
    )
    op.create_index("voice_agents_org_idx", "voice_agents", ["org_id"], schema="public")

    op.execute(POLICIES)
    op.execute(GRANTS)


def downgrade() -> None:
    op.drop_index("voice_agents_org_idx", table_name="voice_agents", schema="public")
    op.drop_table("voice_agents", schema="public")

    op.drop_index(
        "ai_provider_credentials_org_idx", table_name="ai_provider_credentials", schema="public"
    )
    op.drop_table("ai_provider_credentials", schema="public")
