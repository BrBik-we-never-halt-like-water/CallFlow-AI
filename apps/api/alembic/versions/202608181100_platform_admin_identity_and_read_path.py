"""Platform admin: the identity table, the capability check, and the read path.

`docs/PLATFORM_ADMIN.md` §2 and §4. This adds the first cross-tenant privilege
boundary in the application, which CLAUDE.md calls the most severe bug class this
product can ship, so the shape matters more than the convenience.

**It is not an RLS bypass.** RLS evaluates on every row of every platform query.
Visibility is widened by one predicate, `platform_can_read`, added to `select`
policies only - never to an insert, update or delete policy, so no policy anywhere
grants a platform admin write access.

**One deliberate departure from the design doc.** §4 describes adding an `or`
clause to each of the 17 existing `select` policies. This migration adds a
*separate* permissive `select` policy per table instead, because Postgres combines
permissive policies with OR and the result is identical - without ever rewriting an
existing qual. Those quals encode tenant isolation, several are non-trivial
(`users_select` joins memberships twice), and transcribing 17 of them by hand to
append one clause is a way to break isolation with a typo that still looks right.
Not touching them at all removes that risk, and makes "does any write policy
reference the helper?" answerable by grepping for the policy name.

**Both the flag and the row are required.** `platform_can_read` returns false
unless the session set `callflow.platform_session` *and* the caller holds a
`platform_admins` row with the capability. An ordinary `as_user()` session never
sets that flag, so a platform admin browsing the product normally is treated as the
ordinary org member they are - elevation is per-session and explicit, never
ambient.

Revision ID: e2b8c4d61a95
Revises: d1a7b3e58f42
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e2b8c4d61a95"
down_revision = "d1a7b3e58f42"
branch_labels = None
depends_on = None


# Every table whose `select` policy is widened, and the column holding the org.
# `users` is absent: it has no org_id, so it gets its own policy below.
READ_SCOPE: tuple[tuple[str, str], ...] = (
    ("organisations", "id"),
    ("memberships", "org_id"),
    ("campaigns", "org_id"),
    ("runs", "org_id"),
    ("call_outcomes", "org_id"),
    ("escalations", "org_id"),
    ("voice_agents", "org_id"),
    ("telephony_provisioning", "org_id"),
    ("org_safety_settings", "org_id"),
    ("suppressions", "org_id"),
    ("share_requests", "org_id"),
    ("invitations", "org_id"),
    ("member_credit_allocations", "org_id"),
    ("api_keys", "org_id"),
    ("provider_credentials", "org_id"),
    ("ai_provider_credentials", "org_id"),
)

# Deliberately absent from READ_SCOPE: `channels`, `channel_members`, `messages`.
# A customer's internal team chat is the most privacy-sensitive table in the schema
# and the least useful for debugging a call (`docs/PLATFORM_ADMIN.md` §4).

CAPABILITIES = (
    "orgs:read",
    "data:read",
    "pii:reveal",
    "entitlements:write",
    "data:write",
)


HAS_CAPABILITY = """
create or replace function public.platform_has_capability(needed text)
returns boolean
language sql stable security definer
set search_path = public, pg_temp as $$
  select exists (
    select 1
      from public.platform_admins a
      join public.users u on u.id = a.user_id
     where u.auth_user_id = auth.uid()
       and (a.expires_at is null or a.expires_at > now())
       and needed = any(a.capabilities)
  );
$$;
"""

# Evaluated on every row of every query by every user across 17 policies, so the
# unset-flag fast path is not only performance - it is the security model. An
# ordinary session never sets the flag, so the ordinary path is a no-op that never
# touches `platform_admins` at all.
CAN_READ = """
create or replace function public.platform_can_read(target_org_id uuid)
returns boolean
language plpgsql stable security definer
set search_path = public, pg_temp as $$
begin
  if coalesce(current_setting('callflow.platform_session', true), '') = '' then
    return false;
  end if;
  return public.platform_has_capability('data:read');
end;
$$;

create or replace function public.platform_session_active()
returns boolean
language plpgsql stable security definer
set search_path = public, pg_temp as $$
begin
  if coalesce(current_setting('callflow.platform_session', true), '') = '' then
    return false;
  end if;
  return public.platform_has_capability('data:read');
end;
$$;
"""

# Written before any elevated read, and by the write functions below. SECURITY
# DEFINER because `platform_audit_log` grants nothing to `authenticated` - the log
# must not be writable, readable or deletable by the person it is recording.
APPEND_AUDIT = """
create or replace function public.platform_append_audit(
  action text,
  target_org_id uuid,
  before_state jsonb,
  after_state jsonb,
  reason text
) returns uuid
language plpgsql volatile security definer
set search_path = public, pg_temp as $$
declare
  actor uuid;
  new_id uuid;
begin
  if coalesce(trim(reason), '') = '' then
    raise exception 'A platform action needs a reason.' using errcode = '22023';
  end if;

  select u.id into actor from public.users u where u.auth_user_id = auth.uid();
  if actor is null then
    raise exception 'Not signed in.' using errcode = '28000';
  end if;

  insert into public.platform_audit_log
    (actor_user_id, action, target_org_id, before_state, after_state, reason)
  values (actor, action, target_org_id, before_state, after_state, trim(reason))
  returning id into new_id;

  return new_id;
end;
$$;
"""

# Opening an elevated session is itself an audited action. Called by
# `database.as_platform_reader` before it yields the connection, so a session that
# reads nothing still leaves a trace that it was opened.
OPEN_SESSION = """
create or replace function public.platform_open_read_session(reason text)
returns uuid
language plpgsql volatile security definer
set search_path = public, pg_temp as $$
begin
  if not public.platform_has_capability('data:read') then
    raise exception 'Not permitted.' using errcode = '42501';
  end if;
  return public.platform_append_audit('session.read', null, null, null, reason);
end;
$$;
"""

PLATFORM_READ_POLICIES = "\n".join(
    f"""
create policy {table}_platform_read on public.{table}
  for select to authenticated
  using (public.platform_can_read({column}));
"""
    for table, column in READ_SCOPE
)

# `users` has no org_id. A platform admin reading customer data needs the names and
# emails behind those rows, so the predicate is the capability alone.
USERS_POLICY = """
create policy users_platform_read on public.users
  for select to authenticated
  using (public.platform_session_active());
"""


def upgrade() -> None:
    op.create_table(
        "platform_admins",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "capabilities",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "granted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "granted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Null means no expiry. A grant issued for one investigation should carry
        # one; a standing grant for on-call staff need not.
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "capabilities <@ ARRAY["
            + ", ".join(f"'{c}'" for c in CAPABILITIES)
            + "]::text[]",
            name="platform_admins_known_capabilities",
        ),
    )

    op.create_table(
        "platform_audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column(
            "target_org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("before_state", postgresql.JSONB(), nullable=True),
        sa.Column("after_state", postgresql.JSONB(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "platform_audit_log_created_at_idx",
        "platform_audit_log",
        ["created_at"],
        postgresql_using="btree",
    )
    op.create_index(
        "platform_audit_log_target_org_idx", "platform_audit_log", ["target_org_id"]
    )

    op.create_table(
        "org_entitlement_overrides",
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        # Every column nullable: null means "no override, fall back to the plan".
        # `0` is a real, enforced ceiling and must stay distinct from it.
        sa.Column("max_voice_agents", sa.Integer(), nullable=True),
        sa.Column("max_seats", sa.Integer(), nullable=True),
        sa.Column("max_organisations", sa.Integer(), nullable=True),
        sa.Column("max_ai_integrations", sa.Integer(), nullable=True),
        sa.Column("daily_call_budget", sa.Integer(), nullable=True),
        sa.Column("llm_spend_limit_usd", sa.Numeric(10, 2), nullable=True),
        # True means "unlimited", which a null cannot express - a null is
        # "unspecified". Without these an enterprise deal could never be given an
        # unlimited allowance through the product.
        sa.Column(
            "unlimited",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    for table in ("platform_admins", "platform_audit_log", "org_entitlement_overrides"):
        op.execute(f"alter table public.{table} enable row level security")
        op.execute(f"alter table public.{table} force row level security")

    # `platform_admins` and `platform_audit_log` get no policies and no grants at
    # all - unreachable through the API, readable only by `postgres`. That is what
    # makes "no endpoint anywhere can create a platform_admins row" structural
    # rather than a convention, and it is why the bootstrap script has to go
    # through `privileged.acquire`.
    op.execute(
        "revoke all on public.platform_admins, public.platform_audit_log "
        "from authenticated, anon"
    )

    # Functions before policies: a policy that references a function Postgres has
    # not seen yet fails to create.
    op.execute(HAS_CAPABILITY)
    op.execute(CAN_READ)
    op.execute(APPEND_AUDIT)
    op.execute(OPEN_SESSION)

    # An organisation may read its own agreed limits - Billing shows them as
    # "Limits agreed for this organisation". It may never write them.
    op.execute("grant select on public.org_entitlement_overrides to authenticated")
    op.execute(
        """
        create policy org_entitlement_overrides_select on public.org_entitlement_overrides
          for select to authenticated
          using (public.is_org_member(org_id) or public.platform_can_read(org_id))
        """
    )

    op.execute(PLATFORM_READ_POLICIES)
    op.execute(USERS_POLICY)


def downgrade() -> None:
    op.execute("drop policy if exists users_platform_read on public.users")
    for table, _ in READ_SCOPE:
        op.execute(f"drop policy if exists {table}_platform_read on public.{table}")
    op.execute(
        "drop policy if exists org_entitlement_overrides_select "
        "on public.org_entitlement_overrides"
    )
    op.execute("drop function if exists public.platform_open_read_session(text)")
    op.execute(
        "drop function if exists public.platform_append_audit(text, uuid, jsonb, jsonb, text)"
    )
    op.execute("drop function if exists public.platform_can_read(uuid)")
    op.execute("drop function if exists public.platform_session_active()")
    op.execute("drop function if exists public.platform_has_capability(text)")
    op.drop_table("org_entitlement_overrides")
    op.drop_index("platform_audit_log_target_org_idx", table_name="platform_audit_log")
    op.drop_index("platform_audit_log_created_at_idx", table_name="platform_audit_log")
    op.drop_table("platform_audit_log")
    op.drop_table("platform_admins")
