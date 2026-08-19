"""Per-org entitlement overrides, and the enumerated platform write path.

`docs/PLATFORM_ADMIN.md` §5. Two things land here:

1. **`effective_limit` learns about overrides**, so the SQL-side guards and the
   Python ladder resolve a negotiated deal the same way. Until now an Enterprise
   customer got Growth's numbers as a floor with no way to raise them.

2. **The writes, enumerated one function at a time** - never a blanket grant. The
   route dependency is convenience; the check *inside* each function is the actual
   boundary, because Postgres grants function EXECUTE to PUBLIC unless revoked and
   any authenticated user can therefore call these directly over SQL.

Every write takes a mandatory `reason` and lands a `platform_audit_log` row
carrying the before and after state, in the same transaction as the change. An
audit row written separately is one that can be missing.

Revision ID: f3c9d5e72b18
Revises: e2b8c4d61a95
"""

from __future__ import annotations

from alembic import op

revision = "f3c9d5e72b18"
down_revision = "e2b8c4d61a95"
branch_labels = None
depends_on = None


# `unlimited` is a separate array rather than a magic value, because null already
# means "no override, use the plan" and `0` is a real enforced ceiling. Without it
# there is no way to express "this customer has no cap" - the exact thing an
# enterprise deal is usually buying.
EFFECTIVE_LIMIT = """
create or replace function public.effective_limit(target_org_id uuid, limit_name text)
returns integer
language plpgsql stable security definer
set search_path = public, pg_temp as $$
declare
  resolved_plan text;
  result        integer;
  override      public.org_entitlement_overrides%rowtype;
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

  -- The override is consulted before the plan, and is the whole point of the
  -- enterprise tier. Read directly rather than through a policy: this function is
  -- SECURITY DEFINER precisely so the true value is used, not the RLS-filtered one
  -- the inserting user can see.
  select * into override
    from public.org_entitlement_overrides where org_id = target_org_id;

  if found then
    if limit_name = any(override.unlimited) then
      return null;
    end if;
    result := case limit_name
                when 'max_voice_agents'    then override.max_voice_agents
                when 'max_seats'           then override.max_seats
                when 'max_organisations'   then override.max_organisations
                when 'max_ai_integrations' then override.max_ai_integrations
                when 'daily_call_budget'   then override.daily_call_budget
              end;
    if result is not null then
      return result;
    end if;
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

# Every platform write opens the same way. Stated in each function rather than
# factored into a trigger, because a reader auditing this file has to be able to
# see the check without following an indirection.
SET_ORG_PLAN = """
create or replace function public.platform_set_org_plan(
  target_org_id uuid, new_plan_id text, reason text
) returns void
language plpgsql volatile security definer
set search_path = public, pg_temp as $$
declare
  previous text;
begin
  if not public.platform_has_capability('entitlements:write') then
    raise exception 'Not permitted.' using errcode = '42501';
  end if;

  if not exists (select 1 from public.plan_entitlements where plan_id = new_plan_id) then
    raise exception 'Not a plan this deployment offers: %', new_plan_id
      using errcode = '22023';
  end if;

  select plan_id into previous
    from public.organisations where id = target_org_id and deleted_at is null;
  if previous is null then
    raise exception 'No such organisation.' using errcode = '22023';
  end if;

  update public.organisations set plan_id = new_plan_id where id = target_org_id;

  perform public.platform_append_audit(
    'org.plan_set', target_org_id,
    jsonb_build_object('plan_id', previous),
    jsonb_build_object('plan_id', new_plan_id),
    reason
  );
end;
$$;
"""

# A single function for write-or-clear rather than a pair: "clear the override" is
# the same decision as "change it", needs the same authorisation and the same audit
# row, and splitting them is how one of the two ends up without a reason argument.
SET_ORG_ENTITLEMENTS = """
create or replace function public.platform_set_org_entitlements(
  target_org_id uuid,
  max_voice_agents integer,
  max_seats integer,
  max_organisations integer,
  max_ai_integrations integer,
  daily_call_budget integer,
  llm_spend_limit_usd numeric,
  unlimited text[],
  note text,
  reason text
) returns void
language plpgsql volatile security definer
set search_path = public, pg_temp as $$
declare
  before_state jsonb;
  after_state  jsonb;
  everything_null boolean;
begin
  if not public.platform_has_capability('entitlements:write') then
    raise exception 'Not permitted.' using errcode = '42501';
  end if;

  if not exists (
    select 1 from public.organisations where id = target_org_id and deleted_at is null
  ) then
    raise exception 'No such organisation.' using errcode = '22023';
  end if;

  if unlimited is not null and not (unlimited <@ ARRAY[
       'max_voice_agents', 'max_seats', 'max_organisations',
       'max_ai_integrations', 'daily_call_budget']::text[]) then
    raise exception 'Not a limit this schema enforces.' using errcode = '22023';
  end if;

  select to_jsonb(o) into before_state
    from public.org_entitlement_overrides o where o.org_id = target_org_id;

  everything_null := max_voice_agents is null and max_seats is null
    and max_organisations is null and max_ai_integrations is null
    and daily_call_budget is null and llm_spend_limit_usd is null
    and coalesce(array_length(unlimited, 1), 0) = 0;

  if everything_null then
    -- An override of nothing is not an override. Leaving an all-null row would
    -- make Billing report "limits agreed for this organisation" for a customer
    -- who is plainly on their plan's own numbers.
    delete from public.org_entitlement_overrides where org_id = target_org_id;
    after_state := null;
  else
    insert into public.org_entitlement_overrides as t
      (org_id, max_voice_agents, max_seats, max_organisations,
       max_ai_integrations, daily_call_budget, llm_spend_limit_usd, unlimited, note)
    values
      (target_org_id, max_voice_agents, max_seats, max_organisations,
       max_ai_integrations, daily_call_budget, llm_spend_limit_usd,
       coalesce(unlimited, '{}'), note)
    on conflict (org_id) do update set
      max_voice_agents    = excluded.max_voice_agents,
      max_seats           = excluded.max_seats,
      max_organisations   = excluded.max_organisations,
      max_ai_integrations = excluded.max_ai_integrations,
      daily_call_budget   = excluded.daily_call_budget,
      llm_spend_limit_usd = excluded.llm_spend_limit_usd,
      unlimited           = excluded.unlimited,
      note                = excluded.note,
      updated_at          = now();

    select to_jsonb(o) into after_state
      from public.org_entitlement_overrides o where o.org_id = target_org_id;
  end if;

  perform public.platform_append_audit(
    'org.entitlements_set', target_org_id, before_state, after_state, reason
  );
end;
$$;
"""

# The cross-org read used by the platform org list. A function rather than a
# widened policy because it aggregates counts across every organisation, and
# `orgs:read` is deliberately a lower bar than `data:read` - listing customers and
# their plans is not the same as reading their calls.
LIST_ORGS = """
create or replace function public.platform_list_organisations(search text)
returns table (
  org_id uuid,
  name text,
  slug text,
  plan_id text,
  has_override boolean,
  member_count bigint,
  agent_count bigint,
  run_count bigint,
  created_at timestamptz
)
language plpgsql stable security definer
set search_path = public, pg_temp as $$
begin
  if not public.platform_has_capability('orgs:read') then
    raise exception 'Not permitted.' using errcode = '42501';
  end if;

  return query
    select o.id, o.name, o.slug, o.plan_id,
           exists (select 1 from public.org_entitlement_overrides x where x.org_id = o.id),
           (select count(*) from public.memberships m where m.org_id = o.id),
           (select count(*) from public.voice_agents v where v.org_id = o.id),
           (select count(*) from public.runs r where r.org_id = o.id),
           o.created_at
      from public.organisations o
     where o.deleted_at is null
       and (coalesce(trim(search), '') = ''
            or o.name ilike '%' || trim(search) || '%'
            or o.slug ilike '%' || trim(search) || '%')
     order by o.created_at desc
     limit 200;
end;
$$;
"""

READ_AUDIT = """
create or replace function public.platform_read_audit(limit_rows integer)
returns setof public.platform_audit_log
language plpgsql stable security definer
set search_path = public, pg_temp as $$
begin
  if not public.platform_has_capability('orgs:read') then
    raise exception 'Not permitted.' using errcode = '42501';
  end if;

  return query
    select * from public.platform_audit_log
     order by created_at desc
     limit least(coalesce(limit_rows, 100), 500);
end;
$$;
"""

# One override row per organisation, read for the editor. Separate from
# `platform_list_organisations` so the list stays one query rather than N.
GET_OVERRIDE = """
create or replace function public.platform_get_override(target_org_id uuid)
returns setof public.org_entitlement_overrides
language plpgsql stable security definer
set search_path = public, pg_temp as $$
begin
  if not public.platform_has_capability('orgs:read') then
    raise exception 'Not permitted.' using errcode = '42501';
  end if;
  return query
    select * from public.org_entitlement_overrides where org_id = target_org_id;
end;
$$;
"""


def upgrade() -> None:
    op.execute(EFFECTIVE_LIMIT)
    op.execute(SET_ORG_PLAN)
    op.execute(SET_ORG_ENTITLEMENTS)
    op.execute(LIST_ORGS)
    op.execute(READ_AUDIT)
    op.execute(GET_OVERRIDE)


def downgrade() -> None:
    op.execute("drop function if exists public.platform_get_override(uuid)")
    op.execute("drop function if exists public.platform_read_audit(integer)")
    op.execute("drop function if exists public.platform_list_organisations(text)")
    op.execute(
        "drop function if exists public.platform_set_org_entitlements("
        "uuid, integer, integer, integer, integer, integer, numeric, text[], text, text)"
    )
    op.execute("drop function if exists public.platform_set_org_plan(uuid, text, text)")
    # `effective_limit` is left as the override-aware version deliberately: the
    # earlier definition is restored by 202608172000's own downgrade, and
    # re-inlining a stale copy here is how the two drift.
