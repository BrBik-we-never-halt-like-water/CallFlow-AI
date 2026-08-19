"""plan_entitlements + org_subscriptions + payments + payment_webhook_events

The enforcement half of `docs/BILLING.md`. Four tables, one check constraint, and
the SQL-side guards that make a plan limit real rather than advisory.

**Why the numbers live in a table.** `apps/api/app/domain/plans.py` holds the same
ladder, but a `before insert` trigger cannot import Python, and `insert` on
`voice_agents` and `ai_provider_credentials` is granted straight to
`authenticated` - so a limit enforced only in the API is decoration against
anyone holding a database connection (CLAUDE.md §4b). `plan_entitlements` is the
one home both can read; `tests/test_entitlement_enforcement.py` asserts they
have not drifted.

**Why `plan_id` gets a check constraint now.** It has been a bare `varchar(32)`
since the initial schema, so nothing stopped a typo or a half-finished rename
from landing. `scale` was a real plan id until this revision and is migrated to
`enterprise` here; anything else unrecognised is moved to `free` rather than
left to fail the constraint, because a deploy that aborts on one stray row helps
nobody and `free` is the fail-closed answer (CLAUDE.md §4 #2).

**`payments` and `payment_webhook_events` are append-only**, which needs the
grant revoked as well as the policy withheld - Supabase's default `public` ACL
hands every new table full DML to `authenticated`, so a table with no insert
policy still has an insert *grant* nobody wrote
(`202608161700_revoke_delete_on_append_only_tables.py`). `payment_webhook_events`
goes further and has no policies at all: a raw gateway payload can carry data
before we know which organisation it belongs to, so it is platform-internal and
only reachable by `postgres`.

Money is `bigint` minor units (`amount_minor`) - paise for INR, cents for USD.
CLAUDE.md §4 #3 says paise/BIGINT; this generalises the unit to whatever the
gateway settled in without weakening the no-floats rule.

The per-organisation override table, the platform-admin identity and the
cross-tenant read predicate are deliberately **not** here - they are the risky
half and land in their own revision so they can be reviewed alone
(`docs/PLATFORM_ADMIN.md`).

Revision ID: a2d5c8f31e74
Revises: e5b9c4d26f31
Created: 2026-08-17 20:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a2d5c8f31e74"
down_revision: str | None = "e5b9c4d26f31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PLAN_IDS = "'free', 'starter', 'growth', 'enterprise'"

# Mirrors `_LADDER` in `apps/api/app/domain/plans.py`. `null` is unlimited, never
# a sentinel; `0` would be a real, enforced value.
#
# Enterprise carries Growth's numbers rather than unlimited ones on purpose: its
# real limits arrive as a per-organisation override, and seeding it blank would
# leave a window between "deal signed" and "override written" in which the
# organisation had no ceiling at all.
SEED = """
insert into public.plan_entitlements
  (plan_id, max_voice_agents, max_seats, max_organisations,
   max_ai_integrations, daily_call_budget, llm_spend_limit_usd)
values
  ('free',        1,  1, 1,    2,   20,   5.00),
  ('starter',     3,  3, 1,    3,  200,  25.00),
  ('growth',     10, 10, 3, null, 1000, 100.00),
  ('enterprise', 10, 10, 3, null, 1000, 100.00)
on conflict (plan_id) do nothing;
"""

# `scale` was a real plan id; every other unrecognised value lands on `free`.
NORMALISE_PLAN_IDS = f"""
update public.organisations set plan_id = 'enterprise' where plan_id = 'scale';
update public.organisations set plan_id = 'free'
 where plan_id is null or plan_id not in ({PLAN_IDS});

alter table public.organisations
  drop constraint if exists organisations_plan_id_check;
alter table public.organisations
  add constraint organisations_plan_id_check check (plan_id in ({PLAN_IDS}));
"""

RESTORE_PLAN_IDS = """
alter table public.organisations
  drop constraint if exists organisations_plan_id_check;
"""

# One resolver, so a trigger and the API cannot disagree about what a plan allows.
#
# SECURITY DEFINER because the callers are triggers running as whoever is
# inserting: an operator who cannot see a teammate's agents under RLS must still
# be counted against the organisation's *real* total, or the limit is trivially
# bypassed by having someone else create the rows.
#
# An unknown `limit_name` raises rather than returning null. Null means
# "unlimited" here, so a typo'd column name would otherwise fail open - the one
# failure mode this function must not have.
EFFECTIVE_LIMIT = """
create or replace function public.effective_limit(target_org_id uuid, limit_name text)
returns integer
language plpgsql stable security definer
set search_path = public, pg_temp as $$
declare
  resolved_plan text;
  result        integer;
begin
  if limit_name not in ('max_voice_agents', 'max_seats', 'max_organisations',
                        'max_ai_integrations', 'daily_call_budget') then
    raise exception 'Not a limit this schema enforces: %', limit_name
      using errcode = '22023';
  end if;

  select o.plan_id into resolved_plan
    from public.organisations o
   where o.id = target_org_id and o.deleted_at is null;

  -- No such organisation: allow nothing. Reached only by a forged org_id, which
  -- RLS would refuse anyway, so failing closed here costs nothing real.
  if resolved_plan is null then
    return 0;
  end if;

  if not exists (select 1 from public.plan_entitlements p where p.plan_id = resolved_plan) then
    resolved_plan := 'free';
  end if;

  select case limit_name
           when 'max_voice_agents'    then p.max_voice_agents
           when 'max_seats'           then p.max_seats
           when 'max_organisations'   then p.max_organisations
           when 'max_ai_integrations' then p.max_ai_integrations
           when 'daily_call_budget'   then p.daily_call_budget
         end
    into result
    from public.plan_entitlements p
   where p.plan_id = resolved_plan;

  return result;  -- null = unlimited
end;
$$;
"""

# Counted inside a definer function for the same reason as above: the true
# org-wide count, not the RLS-filtered one the inserting user can see.
ENFORCE_AGENT_LIMIT = """
create or replace function public.enforce_voice_agent_limit()
returns trigger
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  allowed integer := public.effective_limit(new.org_id, 'max_voice_agents');
  used    integer;
begin
  if allowed is null then
    return new;
  end if;

  select count(*) into used from public.voice_agents where org_id = new.org_id;

  if used >= allowed then
    raise exception
      'This plan includes % voice agent(s) and % already exist. Upgrade in Settings -> Billing to add another.',
      allowed, used
      using errcode = '23514';
  end if;

  return new;
end;
$$;

create trigger voice_agents_enforce_plan_limit before insert on public.voice_agents
  for each row execute function public.enforce_voice_agent_limit();
"""

# Insert only, never update: a credential already stored must stay rotatable
# after a downgrade, or a failed renewal strands a secret nobody can replace.
ENFORCE_AI_KEY_LIMIT = """
create or replace function public.enforce_ai_integration_limit()
returns trigger
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  allowed integer := public.effective_limit(new.org_id, 'max_ai_integrations');
  used    integer;
begin
  if allowed is null then
    return new;
  end if;

  select count(*) into used
    from public.ai_provider_credentials where org_id = new.org_id;

  if used >= allowed then
    raise exception
      'This plan includes % model provider key(s) and % already exist. Upgrade in Settings -> Billing to connect another.',
      allowed, used
      using errcode = '23514';
  end if;

  return new;
end;
$$;

create trigger ai_provider_credentials_enforce_plan_limit
  before insert on public.ai_provider_credentials
  for each row execute function public.enforce_ai_integration_limit();
"""

# `create_organisation` is SECURITY DEFINER and Postgres grants function EXECUTE
# to PUBLIC unless revoked, so it is reachable directly over SQL - the workspace
# limit has to live inside it, not only in the route.
#
# The limit is taken as the **most generous** plan among the organisations this
# user already owns, because SQL cannot see which organisation the request was
# acting from. That makes this guard deliberately no stricter than the loosest
# reading the API would take; `domain/entitlements.check_org_create_allowed`
# applies the precise active-org rule above it. Being looser here is correct -
# two guards that disagree in the *other* direction would refuse creates the
# product had already permitted.
#
# The signup trigger `handle_new_auth_user` has its own insert and is untouched:
# a new user's first organisation must be created regardless of plan, or a limit
# becomes a signup outage.
CREATE_ORGANISATION_WITH_LIMIT = """
create or replace function public.create_organisation(org_name text)
returns table(id uuid, name text, slug citext, logo_url text)
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  new_org_id uuid;
  new_slug   text;
  owner_id   uuid := public.current_user_id();
  owned      integer;
  allowed    integer;
begin
  if owner_id is null then
    raise exception 'Not signed in.' using errcode = '28000';
  end if;

  select count(*) into owned
    from public.memberships m
    join public.organisations o on o.id = m.org_id
   where m.user_id = owner_id and m.role = 'owner' and o.deleted_at is null;

  select max(public.effective_limit(m.org_id, 'max_organisations')) into allowed
    from public.memberships m
    join public.organisations o on o.id = m.org_id
   where m.user_id = owner_id and m.role = 'owner' and o.deleted_at is null;

  -- `max()` ignores nulls, so an unlimited plan among them looks like no rows at
  -- all. Distinguish the two explicitly rather than reading null as zero.
  if allowed is not null and owned >= allowed
     and not exists (
       select 1
         from public.memberships m
         join public.organisations o on o.id = m.org_id
        where m.user_id = owner_id and m.role = 'owner' and o.deleted_at is null
          and public.effective_limit(m.org_id, 'max_organisations') is null
     )
  then
    raise exception
      'This plan includes % organisation(s) and you already own %. Upgrade in Settings -> Billing to add another.',
      allowed, owned
      using errcode = '23514';
  end if;

  new_slug := public.unique_org_slug(org_name);

  insert into public.organisations (name, slug, country, timezone, onboarded_at)
  values (org_name, new_slug, 'IN', 'Asia/Kolkata', now())
  returning organisations.id into new_org_id;

  insert into public.memberships (org_id, user_id, role)
  values (new_org_id, owner_id, 'owner');

  return query
    select o.id, o.name, o.slug, o.logo_url
    from public.organisations o
    where o.id = new_org_id;
end;
$$;
"""

# The pre-limit body, restored verbatim from `202608072000`.
CREATE_ORGANISATION_WITHOUT_LIMIT = """
create or replace function public.create_organisation(org_name text)
returns table(id uuid, name text, slug citext, logo_url text)
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  new_org_id uuid;
  new_slug   text;
  owner_id   uuid := public.current_user_id();
begin
  if owner_id is null then
    raise exception 'Not signed in.' using errcode = '28000';
  end if;

  new_slug := public.unique_org_slug(org_name);

  insert into public.organisations (name, slug, country, timezone, onboarded_at)
  values (org_name, new_slug, 'IN', 'Asia/Kolkata', now())
  returning organisations.id into new_org_id;

  insert into public.memberships (org_id, user_id, role)
  values (new_org_id, owner_id, 'owner');

  return query
    select o.id, o.name, o.slug, o.logo_url
    from public.organisations o
    where o.id = new_org_id;
end;
$$;
"""

# Billing is an admin/owner concern, matching `Permission.BILLING_READ`. An
# operator sees their own credit allocation, never the organisation's gateway ids
# or payment history.
#
# `org_subscriptions` takes an insert policy for owners only (checkout is
# `BILLING_WRITE`, owner-only) and **no update policy at all**: every status
# change arrives from a webhook with no user session and goes through a definer
# function, so a session has no business writing one.
POLICIES = """
alter table public.plan_entitlements       enable row level security;
alter table public.plan_entitlements       force  row level security;
alter table public.org_subscriptions       enable row level security;
alter table public.org_subscriptions       force  row level security;
alter table public.payments                enable row level security;
alter table public.payments                force  row level security;
alter table public.payment_webhook_events  enable row level security;
alter table public.payment_webhook_events  force  row level security;

-- Public reference data: every signed-in user renders the plan ladder.
create policy plan_entitlements_select on public.plan_entitlements for select
  using (true);

create policy org_subscriptions_select on public.org_subscriptions for select
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy org_subscriptions_insert on public.org_subscriptions for insert
  with check (public.has_org_role(org_id, array['owner']::public.org_role[]));

create policy payments_select on public.payments for select
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));
"""

# No policies on payment_webhook_events, and no grant either: a raw payload can
# carry another organisation's data before we know whose it is.
#
# The revokes matter more than the withheld grants. Supabase's default `public`
# ACL gives `authenticated` and `anon` full DML on every newly created table, so
# "no insert policy" leaves an insert grant nobody wrote.
GRANTS = """
grant select on public.plan_entitlements to authenticated;
revoke insert, update, delete on public.plan_entitlements from authenticated, anon;

grant select, insert on public.org_subscriptions to authenticated;
revoke update, delete on public.org_subscriptions from authenticated, anon;

grant select on public.payments to authenticated;
revoke insert, update, delete on public.payments from authenticated, anon;

revoke all on public.payment_webhook_events from authenticated, anon;
"""

TRIGGERS = """
create trigger org_subscriptions_touch_updated_at before update
  on public.org_subscriptions
  for each row execute function public.touch_updated_at();
"""

# One live subscription per organisation. `pending`/`active`/`on_hold` are
# exactly `domain.subscriptions.is_live()`, and a test asserts the two agree -
# resubscribing after a terminal status inserts a new row, so without this index
# an organisation could end up with two.
LIVE_INDEX = """
create unique index org_subscriptions_one_live_per_org
  on public.org_subscriptions (org_id)
  where status in ('pending', 'active', 'on_hold');
"""


def upgrade() -> None:
    op.create_table(
        "plan_entitlements",
        sa.Column("plan_id", sa.Text(), nullable=False),
        sa.Column("max_voice_agents", sa.Integer(), nullable=True),
        sa.Column("max_seats", sa.Integer(), nullable=True),
        sa.Column("max_organisations", sa.Integer(), nullable=True),
        sa.Column("max_ai_integrations", sa.Integer(), nullable=True),
        sa.Column("daily_call_budget", sa.Integer(), nullable=True),
        sa.Column("llm_spend_limit_usd", sa.Numeric(10, 2), nullable=False),
        sa.PrimaryKeyConstraint("plan_id"),
        sa.CheckConstraint(f"plan_id in ({PLAN_IDS})", name="plan_entitlements_plan_id_check"),
        # `null` is unlimited and `0` is a real ceiling; negative is neither.
        sa.CheckConstraint(
            "(max_voice_agents    is null or max_voice_agents    >= 0) and "
            "(max_seats           is null or max_seats           >= 0) and "
            "(max_organisations   is null or max_organisations   >= 0) and "
            "(max_ai_integrations is null or max_ai_integrations >= 0) and "
            "(daily_call_budget   is null or daily_call_budget   >= 0) and "
            "llm_spend_limit_usd >= 0",
            name="plan_entitlements_non_negative_check",
        ),
        schema="public",
    )

    op.create_table(
        "org_subscriptions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("gateway", sa.Text(), server_default=sa.text("'dodo'"), nullable=False),
        # Null until the gateway has issued one - the row is created before the
        # checkout call so a crash mid-call cannot lose the attempt.
        sa.Column("gateway_subscription_id", sa.Text(), nullable=True),
        sa.Column("gateway_customer_id", sa.Text(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        # Shown to the owner verbatim when a renewal fails, so it must read as an
        # instruction rather than a stack trace (CLAUDE.md §5).
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["public.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gateway_subscription_id", name="org_subscriptions_gateway_id_uniq"),
        sa.CheckConstraint(f"plan_id in ({PLAN_IDS})", name="org_subscriptions_plan_id_check"),
        sa.CheckConstraint(
            "status in ('pending', 'active', 'on_hold', 'cancelled', 'expired', 'failed')",
            name="org_subscriptions_status_check",
        ),
        schema="public",
    )
    op.create_index("org_subscriptions_org_idx", "org_subscriptions", ["org_id"], schema="public")

    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("subscription_id", sa.UUID(), nullable=True),
        sa.Column("gateway", sa.Text(), server_default=sa.text("'dodo'"), nullable=False),
        # The idempotency key. A webhook delivered twice must not become two rows.
        sa.Column("gateway_payment_id", sa.Text(), nullable=False),
        # Minor units of `currency` - paise for INR, cents for USD. Integer, so
        # nothing in the payment path is ever a float (CLAUDE.md §4 #3).
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["public.org_subscriptions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gateway", "gateway_payment_id", name="payments_gateway_id_uniq"),
        sa.CheckConstraint(
            "status in ('succeeded', 'failed', 'refunded')", name="payments_status_check"
        ),
        schema="public",
    )
    op.create_index("payments_org_idx", "payments", ["org_id"], schema="public")

    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("gateway", sa.Text(), nullable=False),
        # The gateway's own delivery id (`webhook-id` under Standard Webhooks).
        # Unique per gateway, and that uniqueness *is* the replay defence.
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gateway", "event_id", name="payment_webhook_events_event_uniq"),
        schema="public",
    )

    op.execute(SEED)
    op.execute(NORMALISE_PLAN_IDS)
    op.execute(LIVE_INDEX)
    op.execute(EFFECTIVE_LIMIT)
    op.execute(ENFORCE_AGENT_LIMIT)
    op.execute(ENFORCE_AI_KEY_LIMIT)
    op.execute(CREATE_ORGANISATION_WITH_LIMIT)
    op.execute(POLICIES)
    op.execute(GRANTS)
    op.execute(TRIGGERS)


def downgrade() -> None:
    op.execute(CREATE_ORGANISATION_WITHOUT_LIMIT)
    op.execute(
        "drop trigger if exists ai_provider_credentials_enforce_plan_limit "
        "on public.ai_provider_credentials"
    )
    op.execute(
        "drop trigger if exists voice_agents_enforce_plan_limit on public.voice_agents"
    )
    op.execute("drop function if exists public.enforce_ai_integration_limit()")
    op.execute("drop function if exists public.enforce_voice_agent_limit()")
    op.execute("drop function if exists public.effective_limit(uuid, text)")
    op.execute(RESTORE_PLAN_IDS)
    op.execute(
        "drop trigger if exists org_subscriptions_touch_updated_at on public.org_subscriptions"
    )

    op.drop_table("payment_webhook_events", schema="public")
    op.drop_index("payments_org_idx", table_name="payments", schema="public")
    op.drop_table("payments", schema="public")
    op.execute("drop index if exists public.org_subscriptions_one_live_per_org")
    op.drop_index("org_subscriptions_org_idx", table_name="org_subscriptions", schema="public")
    op.drop_table("org_subscriptions", schema="public")
    op.drop_table("plan_entitlements", schema="public")
