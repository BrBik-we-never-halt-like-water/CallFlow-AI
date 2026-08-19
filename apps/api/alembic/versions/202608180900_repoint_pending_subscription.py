"""repoint_pending_subscription: stop a reused checkout row from double-billing.

A real bug, found live. `start_pending` returns the organisation's existing live
row when one exists, and checkout reused it without touching its `plan_id`. Buy
Starter, abandon the page, buy Growth, and both gateway checkouts carry the *same*
`subscription_row_id` while the row still says `starter`. Complete both and the
organisation has two active subscriptions at the gateway, is billed for both, and
our side tracks one - whichever the webhook happened to match first.

Two changes close it:

  - `repoint_pending_subscription` lets checkout move a *pending* row onto the plan
    actually being bought, so the row is never stale. Guarded to `status =
    'pending' and gateway_subscription_id is null`: once a row is bound to a
    gateway subscription it is spoken for, and repointing it would silently
    re-label a subscription somebody is already paying for.

  - The route refuses a fresh checkout when the pending row is already bound, which
    is the case the old `status != 'pending'` check missed entirely.

Neither prevents a customer completing two hosted-checkout sessions from two
tabs - the gateway will happily take both, and no local guard can stop that. That
is handled where it has to be, by cancelling the extras on reconcile.

`SECURITY DEFINER` for the same reason as `attach_gateway_ids`:
`org_subscriptions` has no update policy and no update grant, deliberately, so a
session cannot move a subscription's status. Owner-checked inside the function,
because Postgres grants EXECUTE to PUBLIC unless revoked.

Revision ID: c8f4a1e97b23
Revises: b7e3f9a24c81
Created: 2026-08-18 09:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c8f4a1e97b23"
down_revision: str | None = "b7e3f9a24c81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REPOINT = """
create or replace function public.repoint_pending_subscription(
  p_subscription_row_id uuid,
  p_plan_id text
) returns boolean
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

  if not public.has_org_role(target_org, array['owner']::public.org_role[]) then
    raise exception 'Not permitted.' using errcode = '42501';
  end if;

  -- Only an unbound, still-pending row. A row that already carries a gateway
  -- subscription id belongs to something the customer may be paying for.
  update public.org_subscriptions
     set plan_id = p_plan_id, updated_at = now()
   where id = p_subscription_row_id
     and status = 'pending'
     and gateway_subscription_id is null;

  return found;
end;
$$;
"""


def upgrade() -> None:
    op.execute(REPOINT)


def downgrade() -> None:
    op.execute("drop function if exists public.repoint_pending_subscription(uuid, text)")
