"""The webhook's write path: five narrow SECURITY DEFINER functions.

`docs/BILLING.md` §8. A gateway webhook has no user session, so it cannot use
`database.as_user()`, and `privileged.acquire()` must never appear in a request
handler (CLAUDE.md §2). This follows the precedent
`202608091200_calle_webhook_run_lookup.py` set: `database.anonymous()` calling one
narrow definer function per step.

**Why not attribute the write to the person who started the checkout.** That was
the obvious alternative and it is wrong: if they are later removed from the
organisation or downgraded, `as_user()` fails closed and the webhook silently
drops a subscription the customer has paid for. A paid plan must not depend on one
teammate's continued employment.

**Every function re-checks what it needs itself.** Postgres grants function
EXECUTE to PUBLIC unless revoked, so these are reachable directly over SQL by any
authenticated user. The write functions are therefore either unreachable-by-design
(they need a `gateway_subscription_id` the caller would have to already know) or
guarded on org ownership - see `attach_gateway_ids`.

**`apply_subscription_event` is deliberately dumb about policy.** It takes the
already-decided status and the already-decided effective plan id rather than
working them out, because that rule lives in `domain/subscriptions.py`
(`effective_plan_id`, and the `on_hold`-keeps-the-plan decision behind it). Two
copies of that rule - one in Python, one in plpgsql - is how they drift.

Revision ID: b7e3f9a24c81
Revises: a2d5c8f31e74
Created: 2026-08-17 21:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b7e3f9a24c81"
down_revision: str | None = "a2d5c8f31e74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Claim-first, so a redelivery is a no-op rather than a second application.
# Returns true only for the caller that actually inserted the row - the whole
# replay defence rests on the unique index on (gateway, event_id), not on this
# function being called once.
CLAIM_EVENT = """
create or replace function public.claim_webhook_event(
  p_gateway text,
  p_event_id text,
  p_event_type text,
  p_payload jsonb
) returns boolean
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  inserted uuid;
begin
  insert into public.payment_webhook_events (gateway, event_id, event_type, payload)
  values (p_gateway, p_event_id, p_event_type, p_payload)
  on conflict (gateway, event_id) do nothing
  returning id into inserted;

  return inserted is not null;
end;
$$;
"""

MARK_PROCESSED = """
create or replace function public.mark_webhook_event_processed(
  p_gateway text,
  p_event_id text,
  p_org_id uuid,
  p_error text
) returns void
language plpgsql security definer
set search_path = public, pg_temp as $$
begin
  update public.payment_webhook_events
     set processed_at = now(),
         org_id = coalesce(p_org_id, org_id),
         error = p_error
   where gateway = p_gateway and event_id = p_event_id;
end;
$$;
"""

# Resolves by the gateway's own id, falling back to the row id carried in checkout
# metadata. The fallback is load-bearing, not defensive padding: the gateway can
# deliver `subscription.active` before `create_checkout` has returned and the
# subscription id has been persisted, and without it the very first paid
# subscription in that race matches nothing and is dropped.
LOOKUP = """
create or replace function public.lookup_org_for_subscription(
  p_gateway text,
  p_gateway_subscription_id text,
  p_subscription_row_id uuid
) returns table(
  subscription_id uuid,
  org_id uuid,
  status text,
  plan_id text,
  current_period_end timestamptz
)
language plpgsql stable security definer
set search_path = public, pg_temp as $$
begin
  return query
    select s.id, s.org_id, s.status, s.plan_id, s.current_period_end
      from public.org_subscriptions s
     where (p_gateway_subscription_id is not null
            and s.gateway = p_gateway
            and s.gateway_subscription_id = p_gateway_subscription_id)
        or (p_subscription_row_id is not null and s.id = p_subscription_row_id)
     order by
       -- Prefer the gateway id when both match: it is the gateway's own opinion
       -- of which subscription this is, and metadata is only a hint we planted.
       (s.gateway_subscription_id = p_gateway_subscription_id) desc nulls last,
       s.created_at desc
     limit 1;
end;
$$;
"""

# The guarded update. `where status = p_expected_status` is what makes a duplicate
# or out-of-order delivery a no-op instead of a second application - the same
# single-statement-conditional-update technique `runs.finish_if_all_settled`
# already relies on. Returns whether *this* call was the one that applied it.
APPLY_EVENT = """
create or replace function public.apply_subscription_event(
  p_subscription_row_id uuid,
  p_expected_status text,
  p_new_status text,
  p_effective_plan_id text,
  p_subscription_plan_id text,
  p_current_period_end timestamptz,
  p_cancel_at_period_end boolean,
  p_gateway_subscription_id text,
  p_gateway_customer_id text,
  p_last_error text
) returns boolean
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  target_org uuid;
begin
  update public.org_subscriptions s
     set status = p_new_status,
         plan_id = coalesce(p_subscription_plan_id, s.plan_id),
         current_period_end = coalesce(p_current_period_end, s.current_period_end),
         cancel_at_period_end = coalesce(p_cancel_at_period_end, s.cancel_at_period_end),
         gateway_subscription_id =
           coalesce(p_gateway_subscription_id, s.gateway_subscription_id),
         gateway_customer_id = coalesce(p_gateway_customer_id, s.gateway_customer_id),
         -- Cleared on success so a recovered subscription stops showing the
         -- failure that is no longer true.
         last_error = p_last_error,
         updated_at = now()
   where s.id = p_subscription_row_id
     and s.status = p_expected_status
  returning s.org_id into target_org;

  if target_org is null then
    return false;
  end if;

  -- The mirror. Written in the same statement-sequence as the status it derives
  -- from, inside the caller's transaction, so `organisations.plan_id` cannot
  -- drift from the subscription that determines it.
  update public.organisations
     set plan_id = p_effective_plan_id, updated_at = now()
   where id = target_org and plan_id <> p_effective_plan_id;

  return true;
end;
$$;
"""

# Separate from the status change: a payment can arrive for a subscription whose
# status is not moving (a renewal), and a status can move with no payment (a
# cancellation). Unique on (gateway, gateway_payment_id), so a redelivered
# `payment.succeeded` cannot become a second receipt.
RECORD_PAYMENT = """
create or replace function public.record_gateway_payment(
  p_org_id uuid,
  p_subscription_row_id uuid,
  p_gateway text,
  p_gateway_payment_id text,
  p_amount_minor bigint,
  p_currency char(3),
  p_status text,
  p_description text,
  p_paid_at timestamptz
) returns boolean
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  inserted uuid;
begin
  insert into public.payments
    (org_id, subscription_id, gateway, gateway_payment_id, amount_minor,
     currency, status, description, paid_at)
  values
    (p_org_id, p_subscription_row_id, p_gateway, p_gateway_payment_id, p_amount_minor,
     p_currency, p_status, p_description, coalesce(p_paid_at, now()))
  on conflict (gateway, gateway_payment_id) do nothing
  returning id into inserted;

  return inserted is not null;
end;
$$;
"""

# The one function here a *session* is meant to call, so it is the one that has to
# check who is calling. `org_subscriptions` has no update policy and no update
# grant on purpose - a session has no business moving a subscription's status - but
# the checkout flow still has to record the ids the gateway just returned.
ATTACH_IDS = """
create or replace function public.attach_gateway_ids(
  p_subscription_row_id uuid,
  p_gateway_subscription_id text,
  p_gateway_customer_id text
) returns void
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  target_org uuid;
begin
  select org_id into target_org
    from public.org_subscriptions where id = p_subscription_row_id;

  if target_org is null then
    raise exception 'No such subscription.' using errcode = '42704';
  end if;

  -- Owner only, matching `Permission.BILLING_WRITE`. Checked here rather than
  -- trusting the route, because EXECUTE on this function defaults to PUBLIC.
  if not public.has_org_role(target_org, array['owner']::public.org_role[]) then
    raise exception 'Not permitted.' using errcode = '42501';
  end if;

  update public.org_subscriptions
     set gateway_subscription_id =
           coalesce(p_gateway_subscription_id, gateway_subscription_id),
         gateway_customer_id = coalesce(p_gateway_customer_id, gateway_customer_id),
         updated_at = now()
   where id = p_subscription_row_id;
end;
$$;
"""

DROPS = """
drop function if exists public.claim_webhook_event(text, text, text, jsonb);
drop function if exists public.mark_webhook_event_processed(text, text, uuid, text);
drop function if exists public.lookup_org_for_subscription(text, text, uuid);
drop function if exists public.apply_subscription_event(
  uuid, text, text, text, text, timestamptz, boolean, text, text, text);
drop function if exists public.record_gateway_payment(
  uuid, uuid, text, text, bigint, char(3), text, text, timestamptz);
drop function if exists public.attach_gateway_ids(uuid, text, text);
"""


def upgrade() -> None:
    op.execute(CLAIM_EVENT)
    op.execute(MARK_PROCESSED)
    op.execute(LOOKUP)
    op.execute(APPLY_EVENT)
    op.execute(RECORD_PAYMENT)
    op.execute(ATTACH_IDS)


def downgrade() -> None:
    op.execute(DROPS)
