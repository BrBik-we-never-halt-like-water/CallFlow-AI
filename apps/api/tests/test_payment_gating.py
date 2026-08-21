"""No entitlement is granted on money that has not arrived.

The rule these pin down cost a real debugging session: the gateway flips a
subscription's product the moment a plan change is *initiated*, so entitlements
that follow the product land before the charge clears. Combined with "a paid plan
survives to `current_period_end`", a failed top-up would leave an organisation on
the higher plan for the rest of the period - a plan given away.

Driven entirely through the stub gateway, so this runs in CI with no account and
no network. That is what the stub is for.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.integrations.payments.protocol import (
    PaymentCapability,
    RemoteSubscription,
    WebhookKind,
)
from app.integrations.payments.stub import StubPaymentProvider
from app.services.billing import withholds_grant

LATER = datetime.now(UTC) + timedelta(days=30)


def _remote(
    *,
    org_id,
    status: WebhookKind = WebhookKind.SUBSCRIPTION_ACTIVE,
    plan_id: str = "growth",
    unsettled: bool = False,
    winding_down: bool = False,
) -> RemoteSubscription:
    return RemoteSubscription(
        gateway_subscription_id=f"sub_{plan_id}_{'unpaid' if unsettled else 'paid'}",
        status=status,
        plan_id=plan_id,
        subscription_row_id=None,
        org_id=org_id,
        current_period_end=LATER,
        cancel_at_period_end=winding_down,
        has_unsettled_payment=unsettled,
    )


async def test_the_stub_reports_what_a_test_puts_in_it() -> None:
    org = uuid4()
    gateway = StubPaymentProvider(remote=[_remote(org_id=org, unsettled=True)])

    found = await gateway.find_subscriptions(org_id=org)

    assert len(found) == 1
    assert found[0].has_unsettled_payment is True


async def test_another_organisations_subscription_is_not_visible() -> None:
    """`find_subscriptions` is the input to a grant, so a mismatch here would grant
    one organisation a plan another paid for."""
    mine, theirs = uuid4(), uuid4()
    gateway = StubPaymentProvider(remote=[_remote(org_id=theirs)])

    assert await gateway.find_subscriptions(org_id=mine) == []


async def test_lookup_by_id_finds_only_that_subscription() -> None:
    org = uuid4()
    wanted = _remote(org_id=org, plan_id="growth")
    other = _remote(org_id=org, plan_id="starter")
    gateway = StubPaymentProvider(remote=[wanted, other])

    found = await gateway.find_subscriptions_by_id(
        gateway_subscription_id=wanted.gateway_subscription_id
    )

    assert found is not None
    assert found.plan_id == "growth"
    assert (
        await gateway.find_subscriptions_by_id(gateway_subscription_id="sub_nope") is None
    )


def test_reconcile_is_a_declared_capability() -> None:
    """`_payment_settled` fails closed when a gateway cannot be queried, so a
    provider that does not declare RECONCILE can never grant on trust."""
    assert StubPaymentProvider().supports(PaymentCapability.RECONCILE)


# --- the rule itself, as `reconcile` applies it ---------------------------------


@pytest.mark.parametrize(
    "status",
    [WebhookKind.SUBSCRIPTION_ACTIVE, WebhookKind.SUBSCRIPTION_ON_HOLD],
)
def test_a_granting_status_with_an_unsettled_payment_is_withheld(status) -> None:
    """Both statuses that hand an organisation a paid plan must wait for the money.

    `on_hold` is included deliberately: it grants the plan until the period ends
    under this product's own rule, so an unpaid `on_hold` would be just as much of a
    giveaway as an unpaid `active`.
    """
    remote = _remote(org_id=uuid4(), status=status, unsettled=True)

    assert withholds_grant(
        remote.status, has_unsettled_payment=remote.has_unsettled_payment
    ), f"{status.value} with an unsettled payment must not be granted"


@pytest.mark.parametrize(
    "status",
    [
        WebhookKind.SUBSCRIPTION_CANCELLED,
        WebhookKind.SUBSCRIPTION_EXPIRED,
        WebhookKind.SUBSCRIPTION_FAILED,
    ],
)
def test_a_reducing_status_is_applied_even_with_an_unsettled_payment(status) -> None:
    """The gate points one way only.

    Cancelled, expired and failed all *reduce* what an organisation has. Withholding
    those because a payment is in flight would be the same mistake facing the other
    direction - leaving somebody on a plan the gateway has already ended.
    """
    remote = _remote(org_id=uuid4(), status=status, unsettled=True)

    assert not withholds_grant(
        remote.status, has_unsettled_payment=remote.has_unsettled_payment
    )


def test_a_settled_payment_grants_normally() -> None:
    remote = _remote(org_id=uuid4(), unsettled=False)

    assert not withholds_grant(
        remote.status, has_unsettled_payment=remote.has_unsettled_payment
    )


# --- an unsubscribed plan still gets its credit ----------------------------------


class _FakeConn:
    """Records the grants a caller attempts, so `ensure_period_credit`'s decision
    can be asserted without a database."""

    def __init__(self, already: set[str] | None = None) -> None:
        self.granted: list[tuple[int, str]] = []
        self._already = already or set()

    async def fetchval(self, sql: str, *args: object) -> object:
        # `credits_repo.grant` calls `credit_append(...)`; the dedupe key is $3.
        key = str(args[2])
        if key in self._already:
            return False
        self._already.add(key)
        self.granted.append((int(args[1]), key))  # type: ignore[arg-type]
        return True


@pytest.mark.asyncio
async def test_an_unsubscribed_plan_is_granted_its_credit() -> None:
    """The hole this closes: `grant_for_period` runs off subscription webhooks, so
    a Free organisation - which has no subscription - would never receive the
    credit its plan advertises. Its balance would sit at zero and every run would
    be refused, while the pricing page promised otherwise."""
    from app.domain.plans import entitlements_for
    from app.services import credit as credit_service

    conn = _FakeConn()
    granted = await credit_service.ensure_period_credit(
        conn,  # type: ignore[arg-type]
        org_id=uuid4(),
        entitlements=entitlements_for("free"),
        has_subscription=False,
    )
    assert granted is True
    assert conn.granted[0][0] == 10_000


@pytest.mark.asyncio
async def test_a_subscribed_plan_is_not_granted_twice() -> None:
    """Its renewal webhook already grants, keyed on the gateway period. Granting
    here as well would hand it two allowances a month."""
    from app.domain.plans import entitlements_for
    from app.services import credit as credit_service

    conn = _FakeConn()
    granted = await credit_service.ensure_period_credit(
        conn,  # type: ignore[arg-type]
        org_id=uuid4(),
        entitlements=entitlements_for("starter"),
        has_subscription=True,
    )
    assert granted is False
    assert conn.granted == []


@pytest.mark.asyncio
async def test_the_lazy_grant_is_idempotent_within_a_month() -> None:
    """It is called on every Billing read and every run start, so a second call in
    the same month must add nothing."""
    from app.domain.plans import entitlements_for
    from app.services import credit as credit_service

    conn = _FakeConn()
    org, ents = uuid4(), entitlements_for("free")
    first = await credit_service.ensure_period_credit(
        conn, org_id=org, entitlements=ents, has_subscription=False  # type: ignore[arg-type]
    )
    second = await credit_service.ensure_period_credit(
        conn, org_id=org, entitlements=ents, has_subscription=False  # type: ignore[arg-type]
    )
    assert (first, second) == (True, False)
    assert len(conn.granted) == 1


@pytest.mark.asyncio
async def test_a_new_month_grants_again() -> None:
    """The key carries the calendar month, so the allowance rolls over on its own
    without a scheduler - there is none in this deployment."""
    from datetime import UTC, datetime

    from app.domain.plans import entitlements_for
    from app.services import credit as credit_service

    conn = _FakeConn()
    org, ents = uuid4(), entitlements_for("free")
    for month in (8, 9):
        await credit_service.ensure_period_credit(
            conn,  # type: ignore[arg-type]
            org_id=org,
            entitlements=ents,
            has_subscription=False,
            now=datetime(2026, month, 15, tzinfo=UTC),
        )
    assert len(conn.granted) == 2
