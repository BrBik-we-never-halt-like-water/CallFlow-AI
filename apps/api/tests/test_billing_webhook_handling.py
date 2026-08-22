"""`services.billing.handle_event`, against the real database.

Nothing in the existing suite drove this end to end: `test_subscription_state.py`
tests the pure state machine, `test_payment_gating.py` tests `withholds_grant`
in isolation, and `test_public_billing.py` never reaches the webhook route at
all. That gap is exactly how two real bugs shipped unnoticed -

1. `subscription.plan_changed`/`.updated` were unmapped, so a plan change or a
   cancel-at-period-end never applied from the webhook (fixed alongside this
   file: `dodo.py`/`stub.py`'s `_KIND_BY_TYPE` and the `SUBSCRIPTION_UPDATED`
   branch in `handle_event`).
2. A credit-pack top-up's `payment.succeeded` had no `org_subscriptions` row to
   match and was dropped before it ever reached `record_payment` or a credit
   grant (fixed alongside this file: the `event.plan_id == CREDIT_PACK`
   fallback in `handle_event`, and `credit.grant_for_topup`).

Driven through the stub gateway's `remote` list, which is populated per test -
`_payment_settled` needs a specific answer, not the stub's empty default.

Skipped when DATABASE_URL is unset, so the suite still runs offline.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
import pytest_asyncio

from app.core.config import config
from app.database.repositories import credits as credits_repo
from app.integrations.payments.dodo import CREDIT_PACK
from app.integrations.payments.protocol import (
    RemoteSubscription,
    WebhookEvent,
    WebhookKind,
)
from app.services import billing as billing_module

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not config.database_url, reason="DATABASE_URL is not configured"),
]


class Tenant:
    def __init__(self, auth_user_id: uuid.UUID, user_id: uuid.UUID, org_id: uuid.UUID) -> None:
        self.auth_user_id = auth_user_id
        self.user_id = user_id
        self.org_id = org_id


async def _create_tenant(conn: asyncpg.Connection, label: str) -> Tenant:
    auth_user_id = uuid.uuid4()
    await conn.execute(
        """
        insert into auth.users (id, instance_id, aud, role, email, encrypted_password,
                                email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
                                created_at, updated_at)
        values ($1, '00000000-0000-0000-0000-000000000000', 'authenticated',
                'authenticated', $2, extensions.crypt('x', extensions.gen_salt('bf')), now(),
                '{"provider":"email"}', $3::jsonb, now(), now())
        """,
        auth_user_id,
        f"webhook-{label}-{auth_user_id.hex[:8]}@brbik.com",
        json.dumps({"full_name": f"Webhook {label}"}),
    )
    row = await conn.fetchrow(
        """
        select u.id as user_id, m.org_id
        from public.users u
        join public.memberships m on m.user_id = u.id
        where u.auth_user_id = $1
        """,
        auth_user_id,
    )
    assert row is not None, "signup trigger did not create a user and organisation"
    return Tenant(auth_user_id, row["user_id"], row["org_id"])


@asynccontextmanager
async def _as_anon(conn: asyncpg.Connection) -> AsyncIterator[asyncpg.Connection]:
    """`database.anonymous()`'s shape - what the real webhook route runs on."""
    async with conn.transaction():
        await conn.execute("select set_config('role', 'anon', true)")
        yield conn


async def _as_postgres(conn: asyncpg.Connection) -> None:
    await conn.execute("select set_config('role', 'postgres', true)")
    await conn.execute("select set_config('request.jwt.claims', '', true)")


@pytest_asyncio.fixture
async def db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(config.database_url, timeout=30)
    try:
        yield conn
    finally:
        await _as_postgres(conn)
        await conn.close()


@pytest_asyncio.fixture
async def tenant(db: asyncpg.Connection) -> AsyncIterator[Tenant]:
    created = await _create_tenant(db, "one")
    try:
        yield created
    finally:
        await _as_postgres(db)
        await db.execute("delete from auth.users where id = $1", created.auth_user_id)
        await db.execute(
            """
            delete from public.organisations o
            where not exists (select 1 from public.memberships m where m.org_id = o.id)
            """
        )


async def test_a_plan_change_event_updates_the_stored_plan_and_cancel_flag(
    db: asyncpg.Connection, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression for finding #2: before the fix, `subscription.plan_changed`
    and `subscription.updated` mapped to nothing `_TARGET_STATUS` recognised and
    `handle_event` returned a no-op - the customer's plan and cancellation flag
    never moved even though the gateway had already applied the change."""
    subscription_id = uuid.uuid4()
    gateway_subscription_id = f"sub_test_{subscription_id.hex[:8]}"
    period_end = datetime.now(UTC) + timedelta(days=20)

    await db.execute(
        """
        insert into public.org_subscriptions
            (id, org_id, plan_id, status, gateway, gateway_subscription_id,
             current_period_end, created_by)
        values ($1, $2, 'starter', 'active', 'dodo', $3, $4, $5)
        """,
        subscription_id,
        tenant.org_id,
        gateway_subscription_id,
        period_end,
        tenant.user_id,
    )

    class _SettledStub:
        def __init__(self) -> None:
            self.remote = [
                RemoteSubscription(
                    gateway_subscription_id=gateway_subscription_id,
                    status=WebhookKind.SUBSCRIPTION_ACTIVE,
                    plan_id="growth",
                    subscription_row_id=subscription_id,
                    org_id=tenant.org_id,
                    current_period_end=period_end,
                    cancel_at_period_end=True,
                    has_unsettled_payment=False,
                )
            ]

        def supports(self, _capability: object) -> bool:
            return True

        async def find_subscriptions_by_id(
            self, *, gateway_subscription_id: str
        ) -> RemoteSubscription | None:
            return next(
                (s for s in self.remote if s.gateway_subscription_id == gateway_subscription_id),
                None,
            )

    monkeypatch.setattr(billing_module, "provider", _SettledStub)

    event = WebhookEvent(
        event_id="evt_plan_change_1",
        kind=WebhookKind.SUBSCRIPTION_UPDATED,
        raw_type="subscription.plan_changed",
        gateway_subscription_id=gateway_subscription_id,
        org_id=tenant.org_id,
        plan_id="growth",
        current_period_end=period_end,
        cancel_at_period_end=True,
    )

    async with _as_anon(db):
        outcome = await billing_module.handle_event(db, event)
    assert outcome.applied is True

    await _as_postgres(db)
    row = await db.fetchrow(
        "select plan_id from public.organisations where id = $1", tenant.org_id
    )
    assert row["plan_id"] == "growth"
    sub_row = await db.fetchrow(
        "select plan_id, cancel_at_period_end from public.org_subscriptions where id = $1",
        subscription_id,
    )
    assert sub_row["plan_id"] == "growth"
    assert sub_row["cancel_at_period_end"] is True


async def test_a_credit_pack_payment_grants_with_no_subscription_row(
    db: asyncpg.Connection, tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression for finding #3: a top-up is a one-time purchase with no
    `org_subscriptions` row, so before the fix `handle_event`'s lookup always
    missed and returned before `record_payment` - or a credit grant - ever ran."""
    monkeypatch.setattr(billing_module, "provider", lambda: None)  # unused by this path

    payment_id = f"pay_test_{uuid.uuid4().hex[:8]}"
    event = WebhookEvent(
        event_id="evt_topup_1",
        kind=WebhookKind.PAYMENT_SUCCEEDED,
        raw_type="payment.succeeded",
        gateway_payment_id=payment_id,
        org_id=tenant.org_id,
        plan_id=CREDIT_PACK,
        amount_minor=50_000,
        currency="INR",
    )

    async with _as_anon(db):
        outcome = await billing_module.handle_event(db, event)
        assert outcome.applied is True
        balance = await credits_repo.balance(db, tenant.org_id)
    assert balance == 50_000

    await _as_postgres(db)
    payment_row = await db.fetchrow(
        "select subscription_id, amount_minor, org_id from public.payments "
        "where gateway_payment_id = $1",
        payment_id,
    )
    assert payment_row is not None
    assert payment_row["subscription_id"] is None
    assert payment_row["amount_minor"] == 50_000
    assert payment_row["org_id"] == tenant.org_id

    # Replaying the same delivery must not grant, or record, a second time.
    async with _as_anon(db):
        replay = await billing_module.handle_event(db, event)
        assert replay.applied is False
        balance_after_replay = await credits_repo.balance(db, tenant.org_id)
    assert balance_after_replay == 50_000
