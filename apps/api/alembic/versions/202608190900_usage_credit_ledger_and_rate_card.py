"""Usage credit: the ledger, the rate card, and the per-leg tier map.

`docs/PRICING_DECISIONS.md` is the proposal these numbers come from, and every one
of them is a placeholder pending an owner. They live in tables precisely so that
setting them is a data change rather than a deploy.

**Why a ledger and not a balance column.** `organisations.credit_balance_paise`
has existed since the initial schema carrying the comment *"A derived cache of
credit_ledger once F36 lands; the ledger is the truth"*. This is that ledger, and
that column becomes the cache it always said it was.

**Signed deltas in one append-only table**, rather than a ledger plus a mutable
holds table. Nothing is ever updated, so the balance is auditable by replay and a
hold cannot be silently rewritten. `unique (org_id, dedupe_key)` is the whole
idempotency guarantee - the same shape `payments.gateway_payment_id` uses, for the
same reason: a delivery arriving twice must not become two rows.

**Money is integer paise, BIGINT** (CLAUDE.md §4 #3). No float touches this path.

Revision ID: b5e2c7a94f31
Revises: d7c3b8e21a94 (the merge of the billing and agent-visibility branches)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b5e2c7a94f31"
down_revision = "d7c3b8e21a94"
branch_labels = None
depends_on = None


ENTRY_KINDS = ("grant", "hold", "release", "spend", "expiry", "adjustment")
LEGS = ("stt", "llm", "tts")
TIERS = ("economy", "standard", "premium")

# Paise per minute. The platform fee is stored as its own row rather than a
# separate table, so the whole card is one query and one place to change.
PLATFORM_FEE_PAISE = 150
ADD_ONS: tuple[tuple[str, str, int], ...] = (
    ("stt", "economy", 35),
    ("stt", "standard", 100),
    ("stt", "premium", 205),
    ("llm", "economy", 7),
    ("llm", "standard", 35),
    ("llm", "premium", 460),
    ("tts", "economy", 210),
    ("tts", "standard", 365),
    ("tts", "premium", 1075),
)

# Derived from `integrations/ai_providers/catalog.py`'s own per-minute costs at
# authoring time, binned at the gaps in the real data (STT 0.25/0.70, TTS
# 1.50/2.60, LLM 0.05/0.25 rupees per minute). Inlined as a snapshot rather than
# imported: a migration must produce the same rows forever, and the catalogue is
# free to change.
#
# `sarvam` appears twice with different tiers - standard for STT, economy for TTS -
# which is why the key is (leg, provider_id) and not provider_id alone.
PROVIDER_TIERS: tuple[tuple[str, str, str], ...] = (
    ("stt", "deepgram", "standard"),
    ("stt", "deepgram-nova-2", "standard"),
    ("stt", "assemblyai", "economy"),
    ("stt", "openai-whisper", "standard"),
    ("stt", "groq-whisper", "economy"),
    ("stt", "speechmatics", "standard"),
    ("stt", "gladia", "economy"),
    ("stt", "azure-stt", "premium"),
    ("stt", "google-stt", "premium"),
    ("stt", "sarvam", "standard"),
    ("tts", "elevenlabs", "premium"),
    ("tts", "elevenlabs-turbo", "premium"),
    ("tts", "cartesia", "standard"),
    ("tts", "deepgram-aura", "standard"),
    ("tts", "rime", "economy"),
    ("tts", "playht", "standard"),
    ("tts", "openai-tts", "economy"),
    ("tts", "azure-tts", "economy"),
    ("tts", "google-tts", "standard"),
    ("tts", "lmnt", "standard"),
    ("tts", "sarvam", "economy"),
    ("llm", "openai/gpt-4o", "premium"),
    ("llm", "openai/gpt-4o-mini", "economy"),
    ("llm", "openai/gpt-4.1", "premium"),
    ("llm", "openai/gpt-4.1-mini", "standard"),
    ("llm", "openai/gpt-4.1-nano", "economy"),
    ("llm", "openai/gpt-5", "premium"),
    ("llm", "openai/gpt-5-mini", "standard"),
    ("llm", "openai/o4-mini", "standard"),
    ("llm", "anthropic/claude-3.5-sonnet", "premium"),
    ("llm", "anthropic/claude-3.5-haiku", "standard"),
    ("llm", "anthropic/claude-3.7-sonnet", "premium"),
    ("llm", "anthropic/claude-sonnet-4", "premium"),
    ("llm", "anthropic/claude-sonnet-4.5", "premium"),
    ("llm", "anthropic/claude-haiku-4.5", "standard"),
    ("llm", "anthropic/claude-opus-4.1", "premium"),
    ("llm", "google/gemini-2.0-flash-001", "economy"),
    ("llm", "google/gemini-2.5-flash", "standard"),
    ("llm", "google/gemini-2.5-flash-lite", "economy"),
    ("llm", "google/gemini-2.5-pro", "premium"),
    ("llm", "meta-llama/llama-3.3-70b-instruct", "economy"),
    ("llm", "meta-llama/llama-3.1-8b-instruct", "economy"),
    ("llm", "meta-llama/llama-3.1-70b-instruct", "economy"),
    ("llm", "meta-llama/llama-4-maverick", "economy"),
    ("llm", "meta-llama/llama-4-scout", "economy"),
    ("llm", "deepseek/deepseek-chat", "economy"),
    ("llm", "deepseek/deepseek-chat-v3.1", "economy"),
    ("llm", "deepseek/deepseek-r1", "standard"),
    ("llm", "deepseek/deepseek-r1-distill-llama-70b", "economy"),
    ("llm", "mistralai/mistral-large", "premium"),
    ("llm", "mistralai/mistral-small", "economy"),
    ("llm", "mistralai/mistral-nemo", "economy"),
    ("llm", "mistralai/magistral-medium-2506", "premium"),
    ("llm", "x-ai/grok-3", "premium"),
    ("llm", "x-ai/grok-3-mini", "economy"),
    ("llm", "x-ai/grok-4-fast", "economy"),
    ("llm", "qwen/qwen-2.5-72b-instruct", "economy"),
    ("llm", "qwen/qwen3-235b-a22b", "economy"),
    ("llm", "qwen/qwen3-30b-a3b", "economy"),
    ("llm", "amazon/nova-pro-v1", "standard"),
    ("llm", "amazon/nova-lite-v1", "economy"),
    ("llm", "cohere/command-a", "premium"),
    ("llm", "moonshotai/kimi-k2", "standard"),
    ("llm", "z-ai/glm-4.6", "standard"),
)

# Matches `domain/plans.py`'s ladder. A test asserts the two agree, the same way
# `plan_entitlements` is already tested against it.
PLAN_CREDIT: tuple[tuple[str, int, str, bool, int], ...] = (
    # plan_id, monthly_credit_paise, max_managed_tier, may_bring_own_keys, max_ai_integrations
    # Free keeps its own keys and stays dialable - see the ladder comment in
    # `domain/plans.py`. Managed-only needs platform-owned vendor keys, which
    # do not exist yet.
    ("free", 10_000, "economy", True, 2),
    ("starter", 85_000, "premium", True, 3),
    ("growth", 425_000, "premium", True, -1),
    ("enterprise", 425_000, "premium", True, -1),
)


BALANCE_FN = """
create or replace function public.credit_balance(target_org_id uuid)
returns bigint
language sql stable security definer
set search_path = public, pg_temp as $$
  select coalesce(sum(amount_minor), 0)::bigint
    from public.credit_ledger
   where org_id = target_org_id;
$$;
"""

# One writer for every entry kind, because they share the only thing that matters:
# the insert must be idempotent on `dedupe_key`, and the cached balance on
# `organisations` must move in the same transaction as the row that changed it.
# Returning false for "already recorded" rather than raising: a retried settle is
# normal traffic, not an error.
APPEND_FN = """
create or replace function public.credit_append(
  target_org_id uuid,
  actor_user_id uuid,
  kind text,
  amount bigint,
  dedupe text,
  call_ref text default null,
  rate_per_minute integer default null,
  why text default null
) returns boolean
language plpgsql volatile security definer
set search_path = public, pg_temp as $$
declare
  inserted uuid;
begin
  if kind not in ('grant', 'hold', 'release', 'spend', 'expiry', 'adjustment') then
    raise exception 'Not a credit entry kind: %', kind using errcode = '22023';
  end if;
  if coalesce(trim(dedupe), '') = '' then
    raise exception 'A credit entry needs a dedupe key.' using errcode = '22023';
  end if;

  -- The sign is decided here rather than trusted from the caller, so a caller
  -- that passes a positive spend cannot credit an account by accident.
  if kind in ('hold', 'spend', 'expiry') then
    amount := -abs(amount);
  else
    amount := abs(amount);
  end if;

  insert into public.credit_ledger
    (org_id, user_id, entry_kind, amount_minor, currency, dedupe_key,
     call_key, rate_paise_per_minute, reason)
  values
    (target_org_id, actor_user_id, kind, amount, 'INR', trim(dedupe),
     call_ref, rate_per_minute, why)
  on conflict (org_id, dedupe_key) do nothing
  returning id into inserted;

  if inserted is null then
    return false;
  end if;

  -- The derived cache, moved in the same statement sequence as the ledger row.
  -- A separate job would leave a window where Billing and the dial gate disagree
  -- about how much money an organisation has.
  update public.organisations
     set credit_balance_paise = credit_balance_paise + amount
   where id = target_org_id;

  return true;
end;
$$;
"""

# Settling is two entries that must land together: give back what was held, then
# take what was actually used. Separate `credit_append` calls could half-apply if
# the second failed, leaving a released hold and no charge - a free call.
SETTLE_FN = """
create or replace function public.credit_settle(
  target_org_id uuid,
  actor_user_id uuid,
  call_ref text,
  spend_amount bigint,
  rate_per_minute integer
) returns boolean
language plpgsql volatile security definer
set search_path = public, pg_temp as $$
declare
  did_spend boolean;
begin
  -- Order matters only for readability; both are idempotent. The release is
  -- keyed on the hold it reverses, so a hold that never existed releases nothing
  -- and the spend still lands.
  perform public.credit_append(
    target_org_id, actor_user_id, 'release',
    coalesce((select abs(amount_minor) from public.credit_ledger
               where org_id = target_org_id and entry_kind = 'hold'
                 and call_key = call_ref limit 1), 0),
    'release:' || call_ref, call_ref, rate_per_minute,
    'hold released on settle'
  );

  did_spend := public.credit_append(
    target_org_id, actor_user_id, 'spend', spend_amount,
    'spend:' || call_ref, call_ref, rate_per_minute, null
  );

  return did_spend;
end;
$$;
"""

# The abandoned-hold reaper, modelled on `runs.expire_stale_in_flight`: a worker
# that dies leaves a hold that would otherwise pin credit forever. Releases
# rather than deletes, so the ledger still shows what happened.
REAP_FN = """
create or replace function public.credit_release_stale_holds(older_than_seconds integer)
returns integer
language plpgsql volatile security definer
set search_path = public, pg_temp as $$
declare
  released integer := 0;
  row_rec  record;
begin
  for row_rec in
    select h.org_id, h.user_id, h.call_key, abs(h.amount_minor) as held
      from public.credit_ledger h
     where h.entry_kind = 'hold'
       and h.call_key is not null
       and h.created_at < now() - make_interval(secs => older_than_seconds)
       and not exists (
         select 1 from public.credit_ledger r
          where r.org_id = h.org_id and r.call_key = h.call_key
            and r.entry_kind in ('release', 'spend')
       )
  loop
    if public.credit_append(
         row_rec.org_id, row_rec.user_id, 'release', row_rec.held,
         'release:' || row_rec.call_key, row_rec.call_key, null,
         'hold expired without a settle'
       ) then
      released := released + 1;
    end if;
  end loop;
  return released;
end;
$$;
"""

# What a teammate has drawn this period, for the per-member cap. Counts holds as
# well as spends: an in-flight call is money committed, and ignoring it would let
# one person start a hundred calls at once inside their cap.
MEMBER_SPEND_FN = """
create or replace function public.credit_member_spend(
  target_org_id uuid, target_user_id uuid, since timestamptz
) returns bigint
language sql stable security definer
set search_path = public, pg_temp as $$
  select coalesce(sum(abs(amount_minor)), 0)::bigint
    from public.credit_ledger
   where org_id = target_org_id
     and user_id = target_user_id
     and entry_kind in ('hold', 'spend')
     and created_at >= since;
$$;
"""


def upgrade() -> None:
    # --- the ledger -------------------------------------------------------------
    op.create_table(
        "credit_ledger",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Nullable and SET NULL: a grant belongs to the organisation, not a
        # person, and a departed teammate's spend must stay on the ledger.
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entry_kind", sa.Text(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="INR"),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("call_key", sa.Text(), nullable=True),
        # The rate this entry was priced at, so a statement still explains itself
        # after the card changes.
        sa.Column("rate_paise_per_minute", sa.Integer(), nullable=True),
        sa.Column("gateway_payment_id", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "entry_kind in (" + ", ".join(f"'{k}'" for k in ENTRY_KINDS) + ")",
            name="credit_ledger_known_kind",
        ),
        # The sign is part of the meaning, not a convention. A positive spend
        # would credit an account.
        sa.CheckConstraint(
            "(entry_kind in ('grant', 'release', 'adjustment') and amount_minor >= 0) or "
            "(entry_kind in ('hold', 'spend', 'expiry') and amount_minor <= 0)",
            name="credit_ledger_sign_matches_kind",
        ),
        sa.UniqueConstraint("org_id", "dedupe_key", name="credit_ledger_dedupe"),
    )
    op.create_index("credit_ledger_org_idx", "credit_ledger", ["org_id"])
    op.create_index(
        "credit_ledger_call_idx", "credit_ledger", ["org_id", "call_key"]
    )
    # The reaper's own predicate. Partial, because holds are a small fraction of
    # the table and the scan is otherwise the whole ledger every sweep.
    op.execute(
        "create index credit_ledger_open_holds_idx on public.credit_ledger "
        "(created_at) where entry_kind = 'hold'"
    )

    # --- the rate card ----------------------------------------------------------
    op.create_table(
        "usage_rates",
        sa.Column("leg", sa.Text(), primary_key=True),
        sa.Column("tier", sa.Text(), primary_key=True),
        sa.Column("paise_per_minute", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("paise_per_minute >= 0", name="usage_rates_non_negative"),
    )

    op.create_table(
        "provider_tiers",
        sa.Column("leg", sa.Text(), primary_key=True),
        sa.Column("provider_id", sa.Text(), primary_key=True),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "tier in (" + ", ".join(f"'{t}'" for t in TIERS) + ")",
            name="provider_tiers_known_tier",
        ),
        sa.CheckConstraint(
            "leg in (" + ", ".join(f"'{lg}'" for lg in LEGS) + ")",
            name="provider_tiers_known_leg",
        ),
    )

    # --- plan columns -----------------------------------------------------------
    op.add_column(
        "plan_entitlements",
        sa.Column("monthly_credit_paise", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "plan_entitlements",
        sa.Column(
            "max_managed_tier", sa.Text(), nullable=False, server_default="premium"
        ),
    )
    op.add_column(
        "plan_entitlements",
        sa.Column(
            "may_bring_own_keys",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "member_credit_allocations",
        sa.Column("monthly_credit_cap_paise", sa.BigInteger(), nullable=True),
    )

    # --- seed -------------------------------------------------------------------
    op.execute(
        "insert into public.usage_rates (leg, tier, paise_per_minute) values "
        + ", ".join(f"('{lg}', '{t}', {p})" for lg, t, p in ADD_ONS)
        + f", ('platform', 'flat', {PLATFORM_FEE_PAISE})"
    )
    op.execute(
        "insert into public.provider_tiers (leg, provider_id, tier) values "
        + ", ".join(f"('{lg}', '{pid}', '{t}')" for lg, pid, t in PROVIDER_TIERS)
    )
    for plan_id, credit, tier, byo, ai_keys in PLAN_CREDIT:
        op.execute(
            f"""
            update public.plan_entitlements
               set monthly_credit_paise = {credit},
                   max_managed_tier = '{tier}',
                   may_bring_own_keys = {str(byo).lower()},
                   max_ai_integrations = {"null" if ai_keys < 0 else ai_keys}
             where plan_id = '{plan_id}'
            """
        )

    # --- policies, grants, functions -------------------------------------------
    for table in ("credit_ledger", "usage_rates", "provider_tiers"):
        op.execute(f"alter table public.{table} enable row level security")
        op.execute(f"alter table public.{table} force row level security")

    # An organisation reads its own statement and nothing else. Writes go only
    # through the definer functions, so `insert` is revoked outright - the same
    # shape `payments` uses.
    op.execute("grant select on public.credit_ledger to authenticated")
    op.execute(
        "revoke insert, update, delete on public.credit_ledger from authenticated, anon"
    )
    op.execute(
        """
        create policy credit_ledger_select on public.credit_ledger
          for select to authenticated
          using (public.is_org_member(org_id) or public.platform_can_read(org_id))
        """
    )

    # The card is public knowledge - it is on the pricing page. Read by anyone
    # signed in, written by nobody through the API.
    for table in ("usage_rates", "provider_tiers"):
        op.execute(f"grant select on public.{table} to authenticated, anon")
        op.execute(
            f"revoke insert, update, delete on public.{table} from authenticated, anon"
        )
        op.execute(
            f"""
            create policy {table}_select on public.{table}
              for select to authenticated, anon using (true)
            """
        )

    op.execute(BALANCE_FN)
    op.execute(APPEND_FN)
    op.execute(SETTLE_FN)
    op.execute(REAP_FN)
    op.execute(MEMBER_SPEND_FN)

    # The defect this closes in passing: `member_credit_allocations` never had its
    # delete grant revoked, so Supabase's default public ACL still left a DELETE
    # nobody wrote (see 202608161700's own docstring).
    op.execute(
        "revoke delete on public.member_credit_allocations from authenticated, anon"
    )


def downgrade() -> None:
    op.execute("drop function if exists public.credit_member_spend(uuid, uuid, timestamptz)")
    op.execute("drop function if exists public.credit_release_stale_holds(integer)")
    op.execute("drop function if exists public.credit_settle(uuid, uuid, text, bigint, integer)")
    op.execute(
        "drop function if exists public.credit_append("
        "uuid, uuid, text, bigint, text, text, integer, text)"
    )
    op.execute("drop function if exists public.credit_balance(uuid)")
    op.execute("drop policy if exists provider_tiers_select on public.provider_tiers")
    op.execute("drop policy if exists usage_rates_select on public.usage_rates")
    op.execute("drop policy if exists credit_ledger_select on public.credit_ledger")
    op.drop_column("member_credit_allocations", "monthly_credit_cap_paise")
    op.drop_column("plan_entitlements", "may_bring_own_keys")
    op.drop_column("plan_entitlements", "max_managed_tier")
    op.drop_column("plan_entitlements", "monthly_credit_paise")
    op.drop_table("provider_tiers")
    op.drop_table("usage_rates")
    op.drop_index("credit_ledger_open_holds_idx", table_name="credit_ledger")
    op.drop_index("credit_ledger_call_idx", table_name="credit_ledger")
    op.drop_index("credit_ledger_org_idx", table_name="credit_ledger")
    op.drop_table("credit_ledger")
