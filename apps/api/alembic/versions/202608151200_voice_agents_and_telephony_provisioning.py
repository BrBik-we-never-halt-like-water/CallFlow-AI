"""voice_agents + telephony_provisioning

The schema half of the platform pivot (`PLATFORM_PIVOT_PLAN.md` ADR-4,
`RUNBOOK_HET_PART_1.md` P1-T5). Two tables land together because they are one
coherent change: a `voice_agent` is not usable until a number is connected to
it, and `telephony_provisioning` is the record of that connection attempt.

`voice_agents` is the configuration an agent runs with - which STT, TTS and LLM
to use, whose credentials to use for each, and which number to dial from. One
number per agent for V1: an org with several agents connects a number per
agent rather than sharing a pool, which is the simplest model that is actually
correct. Revisit only when a real org asks for shared-number routing.

`telephony_provisioning` is one row per *attempt*, not per agent, so a failed
attempt keeps its diagnostic trail when a fresh one is started. The status
machine is pending -> provisioning -> verified | failed. `idempotency_key` is
unique per agent so a double-submitted attempt cannot create two rows, and so
a retry can look up what the first attempt already created (a LiveKit trunk,
say) instead of blindly re-running the step and orphaning a second one. There
is deliberately no delete policy and no delete grant: an attempt is
re-statused, never removed, so the history of what was tried survives.

The `provider_credentials` check is widened in the same revision rather than a
later one, because it is the same schema change: `voice_agents` references
that table for STT/TTS/LLM credentials, and those providers (sarvam,
openrouter, deepgram, elevenlabs, ...) are not in the old
`in ('twilio','plivo')` list. Growing that list forever would mean one
migration per vendor, so the allowed set moves to the application layer
(a `Literal[...]` in the Pydantic model) and the database keeps only a
non-empty check. `provider` also widens from varchar(16) to text in the same
breath - a 16-character ceiling would put a future vendor right back into a
migration, which is the exact cost this change exists to remove.

Revision ID: a7c4e2f9b813
Revises: b938fa82e54d
Created: 2026-08-15 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7c4e2f9b813"
down_revision: str | None = "b938fa82e54d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Reading an agent is any member's business - the Agentic tab lists them.
# Writing one is not a viewer's: it selects which credentials a live call
# authenticates with. Deleting is owner/admin only, matching how every other
# credential-adjacent table in this schema already draws that line.
POLICIES = """
alter table public.voice_agents enable row level security;
alter table public.voice_agents force  row level security;
alter table public.telephony_provisioning enable row level security;
alter table public.telephony_provisioning force  row level security;

create policy voice_agents_select on public.voice_agents for select
  using (public.is_org_member(org_id));

create policy voice_agents_insert on public.voice_agents for insert
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

create policy voice_agents_update on public.voice_agents for update
  using (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

create policy voice_agents_delete on public.voice_agents for delete
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy telephony_provisioning_select on public.telephony_provisioning for select
  using (public.is_org_member(org_id));

create policy telephony_provisioning_insert on public.telephony_provisioning for insert
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

create policy telephony_provisioning_update on public.telephony_provisioning for update
  using (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));
"""

# No `delete` on telephony_provisioning, and no delete policy above: a
# provisioning attempt is re-statused, never removed. Withholding the grant as
# well as the policy means the intent survives someone later adding a policy
# without re-reading this comment.
GRANTS = """
grant select, insert, update, delete on public.voice_agents to authenticated;
grant select, insert, update on public.telephony_provisioning to authenticated;
"""

# `updated_at` that never updates is a lie the rest of this schema does not
# tell - every other table carrying the column has this trigger.
TRIGGERS = """
create trigger telephony_provisioning_touch_updated_at before update
  on public.telephony_provisioning
  for each row execute function public.touch_updated_at();
"""

WIDEN_PROVIDER_CHECK = """
alter table public.provider_credentials
  drop constraint if exists provider_credentials_provider_check;
alter table public.provider_credentials
  alter column provider type text;
alter table public.provider_credentials
  add constraint provider_credentials_provider_not_blank check (provider <> '');
"""

# The type narrows back, but the `in ('twilio','plivo')` check deliberately does
# not. By the time anyone downgrades, the Integrations page has stored sarvam /
# openrouter / deepgram / elevenlabs rows, and re-adding that check would fail
# against existing data - turning `npm run db:reset` into an error nobody can
# clear without hand-deleting credentials. A downgrade's job is to undo this
# revision, not to make the database refuse rows it already holds.
RESTORE_PROVIDER_CHECK = """
alter table public.provider_credentials
  drop constraint if exists provider_credentials_provider_not_blank;
alter table public.provider_credentials
  alter column provider type varchar(16);
"""


def upgrade() -> None:
    op.create_table(
        "voice_agents",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("stt_provider", sa.Text(), nullable=True),
        sa.Column("stt_credential_id", sa.UUID(), nullable=True),
        sa.Column("tts_provider", sa.Text(), nullable=True),
        sa.Column("tts_credential_id", sa.UUID(), nullable=True),
        sa.Column("llm_provider", sa.Text(), nullable=True),
        sa.Column("llm_credential_id", sa.UUID(), nullable=True),
        # Required when llm_provider = 'openrouter': one credential proxies
        # many models, so the credential alone does not say which to run.
        sa.Column("llm_model", sa.Text(), nullable=True),
        # Which number this agent dials from. Null until a number is connected.
        sa.Column("telephony_provider", sa.Text(), nullable=True),
        sa.Column("telephony_credential_id", sa.UUID(), nullable=True),
        sa.Column("prebuilt_persona", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("voice_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["public.users.id"], ondelete="SET NULL"),
        # RESTRICT, not CASCADE: deleting a credential that a live agent dials
        # with must fail loudly rather than silently leaving an agent that
        # cannot authenticate. The caller detaches it first, deliberately.
        sa.ForeignKeyConstraint(
            ["stt_credential_id"], ["public.provider_credentials.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tts_credential_id"], ["public.provider_credentials.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["llm_credential_id"], ["public.provider_credentials.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["telephony_credential_id"], ["public.provider_credentials.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind in ('custom', 'prebuilt')", name="voice_agents_kind_check"),
        schema="public",
    )
    op.create_index("voice_agents_org_idx", "voice_agents", ["org_id"], schema="public")

    op.create_table(
        "telephony_provisioning",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        # "The newest attempt for this agent" is what the status poll asks, and
        # `created_at` cannot answer it: `now()` is the transaction timestamp, so
        # two attempts can share one, and `id` is a random uuid that carries no
        # order at all. An identity column is the only monotonic thing here.
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("voice_agent_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("livekit_inbound_trunk_id", sa.Text(), nullable=True),
        sa.Column("livekit_outbound_trunk_id", sa.Text(), nullable=True),
        sa.Column("livekit_dispatch_rule_id", sa.Text(), nullable=True),
        # Plivo's <trunk_id>.zt.plivo.com. Null for Twilio, which has no analog.
        sa.Column("carrier_termination_domain", sa.Text(), nullable=True),
        # Shown to the operator verbatim when status = 'failed', so it must
        # read as an instruction, not a stack trace (CLAUDE.md §5).
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["voice_agent_id"], ["public.voice_agents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "voice_agent_id",
            "idempotency_key",
            name="telephony_provisioning_agent_key_uniq",
        ),
        sa.CheckConstraint(
            "status in ('pending', 'provisioning', 'verified', 'failed')",
            name="telephony_provisioning_status_check",
        ),
        schema="public",
    )
    op.create_index(
        "telephony_provisioning_org_idx", "telephony_provisioning", ["org_id"], schema="public"
    )
    # The provisioning-status poll reads the newest attempt for one agent, so
    # the index carries the ordering column too and the lookup is a backwards
    # index scan rather than a sort.
    op.create_index(
        "telephony_provisioning_agent_idx",
        "telephony_provisioning",
        ["voice_agent_id", sa.text("seq desc")],
        schema="public",
    )

    op.execute(POLICIES)
    op.execute(GRANTS)
    op.execute(TRIGGERS)
    op.execute(WIDEN_PROVIDER_CHECK)


def downgrade() -> None:
    op.execute(RESTORE_PROVIDER_CHECK)
    op.execute(
        "drop trigger if exists telephony_provisioning_touch_updated_at "
        "on public.telephony_provisioning"
    )
    op.drop_index(
        "telephony_provisioning_agent_idx", table_name="telephony_provisioning", schema="public"
    )
    op.drop_index(
        "telephony_provisioning_org_idx", table_name="telephony_provisioning", schema="public"
    )
    op.drop_table("telephony_provisioning", schema="public")
    op.drop_index("voice_agents_org_idx", table_name="voice_agents", schema="public")
    op.drop_table("voice_agents", schema="public")
