"""SQL for subscriptions, payments, and the webhook event log.

Split by connection kind, because these run under two different identities:

  - `get_live_for_org`, `start_pending`, `attach_gateway_ids`, `list_payments` run
    on `database.as_user()` as a signed-in owner or admin, with RLS in force.
  - `claim_event`, `lookup_for_webhook`, `apply_event`, `record_payment`,
    `mark_event_processed` run on `database.anonymous()` and go through
    SECURITY DEFINER functions, because a gateway webhook has no user session
    (`docs/BILLING.md` §8).

The second group never inlines SQL against the tables. `payments` and
`payment_webhook_events` have their write grants revoked, so an `insert` from here
would fail - which is the point: the definer function is the only write path, and
it is narrow enough to read in one sitting.
"""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

import asyncpg

_SUBSCRIPTION_COLUMNS = """
    id, org_id, plan_id, status, gateway, gateway_subscription_id,
    gateway_customer_id, current_period_end, cancel_at_period_end,
    last_error, created_by, created_at, updated_at
"""


# --- signed-in reads and writes -------------------------------------------------


async def get_live_for_org(conn: asyncpg.Connection, org_id: UUID) -> asyncpg.Record | None:
    """The organisation's current subscription, or None.

    None is a normal state, not an error: an organisation that has never
    subscribed has no row, and an enterprise account on an invoiced deal may never
    have one. Callers must render "no subscription" rather than a failure.

    `pending`/`active`/`on_hold` mirrors `domain.subscriptions.is_live()` and the
    partial unique index, so at most one row can match.
    """
    return await conn.fetchrow(
        f"""
        select {_SUBSCRIPTION_COLUMNS}
          from public.org_subscriptions
         where org_id = $1 and status in ('pending', 'active', 'on_hold')
        """,
        org_id,
    )


async def get_latest_for_org(conn: asyncpg.Connection, org_id: UUID) -> asyncpg.Record | None:
    """The newest subscription whatever its status.

    Distinct from `get_live_for_org` on purpose: after a cancellation there is no
    live row, but Billing still has to show that the plan runs until the period
    ends. Reading only the live row would show a cancelled customer as if they had
    never subscribed.
    """
    return await conn.fetchrow(
        f"""
        select {_SUBSCRIPTION_COLUMNS}
          from public.org_subscriptions
         where org_id = $1
         order by created_at desc
         limit 1
        """,
        org_id,
    )


async def start_pending(
    conn: asyncpg.Connection,
    *,
    subscription_id: UUID,
    org_id: UUID,
    plan_id: str,
    gateway: str,
    created_by: UUID,
) -> tuple[asyncpg.Record, bool]:
    """Claim a checkout attempt. Returns `(row, created)`.

    `created is False` means this organisation already has a live subscription, and
    the row returned is that one - the caller must decide whether to resume it or
    refuse, never insert a second. The partial unique index
    `org_subscriptions_one_live_per_org` is what actually serialises two concurrent
    checkouts; this function only reports which side of it you landed on.

    The id is supplied by the caller rather than generated here, because it has to
    travel to the gateway as checkout metadata *before* this row is committed - it
    is how the webhook finds the subscription when the gateway's own id has not
    reached us yet.

    Two statements rather than `on conflict ... do update`, for the reason
    `telephony_provisioning.start_attempt` gives: the update form would fire the
    `updated_at` trigger and make a read look like a write.
    """
    row = await conn.fetchrow(
        f"""
        insert into public.org_subscriptions
          (id, org_id, plan_id, status, gateway, created_by)
        values ($1, $2, $3, 'pending', $4, $5)
        on conflict do nothing
        returning {_SUBSCRIPTION_COLUMNS}
        """,
        subscription_id,
        org_id,
        plan_id,
        gateway,
        created_by,
    )
    if row is not None:
        return row, True

    existing = await get_live_for_org(conn, org_id)
    if existing is None:
        # The insert conflicted but nothing live is visible. Under RLS that means
        # the row belongs to another organisation - failing closed beats returning
        # None and letting the caller treat "not visible" as "not created" and
        # start a second checkout.
        raise PermissionError("This subscription belongs to another organisation.")
    return existing, False


async def attach_gateway_ids(
    conn: asyncpg.Connection,
    *,
    subscription_id: UUID,
    gateway_subscription_id: str | None,
    gateway_customer_id: str | None,
) -> None:
    """Record the ids the gateway returned from checkout.

    Through a definer function because `org_subscriptions` has no update policy and
    no update grant - a session must not be able to move a subscription's status.
    The function re-checks that the caller owns the organisation.
    """
    await conn.execute(
        "select public.attach_gateway_ids($1, $2, $3)",
        subscription_id,
        gateway_subscription_id,
        gateway_customer_id,
    )


async def repoint_pending(
    conn: asyncpg.Connection, *, subscription_id: UUID, plan_id: str
) -> bool:
    """Move an unbound pending row onto the plan actually being bought.

    False means the row was not repointable - already bound to a gateway
    subscription, or no longer pending. The caller must treat that as "this row is
    spoken for" and refuse rather than proceed, or it re-labels a subscription
    somebody is paying for.
    """
    return bool(
        await conn.fetchval(
            "select public.repoint_pending_subscription($1, $2)", subscription_id, plan_id
        )
    )


async def list_payments(
    conn: asyncpg.Connection, org_id: UUID, *, limit: int = 24
) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        select id, amount_minor, currency, status, description, paid_at
          from public.payments
         where org_id = $1
         order by coalesce(paid_at, created_at) desc
         limit $2
        """,
        org_id,
        limit,
    )


async def get_payment(
    conn: asyncpg.Connection, *, payment_id: UUID
) -> asyncpg.Record | None:
    """One payment row by *our* id, under RLS.

    The security of the receipt endpoint is entirely here. The caller passes an id
    from a URL; this returns None unless the row belongs to an organisation the
    session can see, and only then is the gateway's own payment id read off the row
    and sent onward. Taking `gateway_payment_id` from the request instead would let
    anyone fetch any customer's invoice, because the gateway has no idea who is
    asking.
    """
    return await conn.fetchrow(
        """
        select id, org_id, gateway, gateway_payment_id, status, currency, amount_minor
          from public.payments
         where id = $1
        """,
        payment_id,
    )


# --- the webhook path (anonymous connection, definer functions) -----------------


async def claim_event(
    conn: asyncpg.Connection,
    *,
    gateway: str,
    event_id: str,
    event_type: str,
    payload: dict[str, object],
) -> bool:
    """False means this delivery has been seen before: ack and stop.

    At-least-once delivery makes a repeat normal traffic, not an error, so the
    caller answers 200 rather than raising.
    """
    # Forced through JSON before it reaches the `jsonb` codec. The adapter already
    # converts vendor objects, but this is the last point before the database and a
    # failure here costs more than the round trip: an unserialisable value raises
    # inside asyncpg, the route 500s, and the gateway then retries the same delivery
    # for ten hours. `default=str` is the right trade - a slightly lossy record of an
    # event beats no record and a retry storm.
    safe_payload = json.loads(json.dumps(payload, default=str))
    return bool(
        await conn.fetchval(
            "select public.claim_webhook_event($1, $2, $3, $4::jsonb)",
            gateway,
            event_id,
            event_type,
            safe_payload,
        )
    )


async def mark_event_processed(
    conn: asyncpg.Connection,
    *,
    gateway: str,
    event_id: str,
    org_id: UUID | None = None,
    error: str | None = None,
) -> None:
    await conn.execute(
        "select public.mark_webhook_event_processed($1, $2, $3, $4)",
        gateway,
        event_id,
        org_id,
        error,
    )


async def lookup_for_webhook(
    conn: asyncpg.Connection,
    *,
    gateway: str,
    gateway_subscription_id: str | None,
    subscription_row_id: UUID | None,
) -> asyncpg.Record | None:
    """Resolve a subscription from a webhook, by gateway id or checkout metadata.

    Both are passed because either can be the only one available: the gateway id is
    absent on the very first delivery of a race, and the metadata row id is absent
    on renewals months later.
    """
    return await conn.fetchrow(
        "select * from public.lookup_org_for_subscription($1, $2, $3)",
        gateway,
        gateway_subscription_id,
        subscription_row_id,
    )


async def apply_event(
    conn: asyncpg.Connection,
    *,
    subscription_id: UUID,
    expected_status: str,
    new_status: str,
    effective_plan_id: str,
    subscription_plan_id: str | None = None,
    current_period_end: datetime | None = None,
    cancel_at_period_end: bool | None = None,
    gateway_subscription_id: str | None = None,
    gateway_customer_id: str | None = None,
    last_error: str | None = None,
) -> bool:
    """Apply a status change, guarded on the status we believe it is now.

    False means the guard did not match - another delivery got there first, or the
    subscription has since moved on. Both are no-ops, not failures.

    `effective_plan_id` is what `organisations.plan_id` becomes, decided by
    `domain.subscriptions.effective_plan_id` and passed in. The SQL deliberately
    does not re-derive it: two copies of the "on_hold keeps the plan until the
    period ends" rule is how they drift.
    """
    return bool(
        await conn.fetchval(
            """
            select public.apply_subscription_event(
              $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
            )
            """,
            subscription_id,
            expected_status,
            new_status,
            effective_plan_id,
            subscription_plan_id,
            current_period_end,
            cancel_at_period_end,
            gateway_subscription_id,
            gateway_customer_id,
            last_error,
        )
    )


async def extend_period(
    conn: asyncpg.Connection,
    *,
    subscription_id: UUID,
    current_period_end: datetime | None,
    effective_plan_id: str,
) -> bool:
    """A renewal: the period moves, the status does not.

    Expressed as `active -> active` through the same guarded update, which is legal
    here precisely because it is *not* a transition - the state machine rejects
    self-transitions, so renewal must never go through `check_transition`.
    """
    return await apply_event(
        conn,
        subscription_id=subscription_id,
        expected_status="active",
        new_status="active",
        effective_plan_id=effective_plan_id,
        current_period_end=current_period_end,
    )


async def record_payment(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    subscription_id: UUID | None,
    gateway: str,
    gateway_payment_id: str,
    amount_minor: int,
    currency: str,
    status: str,
    description: str | None = None,
    paid_at: datetime | None = None,
) -> bool:
    """False means this payment was already recorded - a redelivery, not a duplicate
    charge. The unique index on (gateway, gateway_payment_id) is the guarantee."""
    return bool(
        await conn.fetchval(
            "select public.record_gateway_payment($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            org_id,
            subscription_id,
            gateway,
            gateway_payment_id,
            amount_minor,
            currency,
            status,
            description,
            paid_at,
        )
    )
