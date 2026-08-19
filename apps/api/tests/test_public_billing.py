"""The one billing route reachable without a session, and what it must not leak.

`GET /api/v1/public/billing/plans` exists because the marketing site has no
session and a pricing section with no prices is the reason that section was
deleted once already. An unauthenticated route on a product whose most severe bug
class is cross-tenant access earns a test that says exactly what it is allowed to
return.

Driven through the stub gateway, so this runs in CI with no account and no
network.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes import billing as billing_routes
from app.integrations.payments.protocol import PaymentCapability
from app.integrations.payments.stub import StubPaymentProvider
from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(billing_routes.billing, "provider", StubPaymentProvider)
    return TestClient(app)


def _plans(client: TestClient) -> list[dict]:
    response = client.get("/api/v1/public/billing/plans")
    assert response.status_code == 200
    return response.json()


def test_the_ladder_is_readable_with_no_authorization_header(client: TestClient) -> None:
    """The whole point. A bearer token the marketing page cannot produce would make
    this render empty for every visitor who is not already a customer."""
    assert [plan["plan_id"] for plan in _plans(client)] == [
        "free",
        "starter",
        "growth",
        "enterprise",
    ]


def test_a_bearer_token_is_ignored_rather_than_rejected(client: TestClient) -> None:
    """A signed-in visitor browsing the marketing site still sends their token on a
    same-origin request. Answering 401 to a *public* route because a token happens
    to be present, or worse honouring it, are both wrong - it is the same public
    answer either way."""
    response = client.get(
        "/api/v1/public/billing/plans",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 200
    assert all(plan["current"] is False for plan in response.json())


def test_no_plan_is_marked_current(client: TestClient) -> None:
    """There is no organisation to be current for. A `true` here would mean the
    route had resolved a tenant from an unauthenticated request."""
    assert all(plan["current"] is False for plan in _plans(client))


def test_the_response_carries_only_the_ladder_and_its_prices(client: TestClient) -> None:
    """Pins the shape, so adding a field to `PlanOptionOut` for the signed-in
    endpoint cannot quietly widen the public one. Anything org-scoped - usage, a
    subscription, a payment - must fail this."""
    for plan in _plans(client):
        assert set(plan) == {
            "plan_id",
            "name",
            "entitlements",
            "prices",
            "self_serve",
            "current",
        }


def test_prices_are_the_gateways_own_minor_units(client: TestClient) -> None:
    starter = next(plan for plan in _plans(client) if plan["plan_id"] == "starter")
    monthly = next(price for price in starter["prices"] if price["period"] == "monthly")

    # Integer minor units, never a float and never a major-unit number the
    # interface would then render as 999 paise (CLAUDE.md §4 #3).
    assert isinstance(monthly["amount_minor"], int)
    assert monthly["amount_minor"] == 99_900
    assert monthly["currency"] == "INR"


def test_free_and_enterprise_have_no_price_and_no_checkout(client: TestClient) -> None:
    """Neither has a gateway product: Free has nothing to charge for and Enterprise
    is invoiced outside the product. The interface reads `self_serve` to say
    "contact us" rather than inferring it from an empty price list."""
    for plan_id in ("free", "enterprise"):
        plan = next(p for p in _plans(client) if p["plan_id"] == plan_id)
        assert plan["prices"] == []
        assert plan["self_serve"] is False


def test_a_gateway_that_cannot_be_asked_for_prices_still_returns_every_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gateway outage must not blank the pricing section. Every plan still
    renders with its entitlements; only the amounts are missing, which the page is
    built to say out loud rather than print a zero for (CLAUDE.md §4 #9)."""

    class NoPrices(StubPaymentProvider):
        def supports(self, capability: PaymentCapability) -> bool:
            if capability is PaymentCapability.LIVE_PRICES:
                return False
            return super().supports(capability)

    monkeypatch.setattr(billing_routes.billing, "provider", NoPrices)
    plans = _plans(TestClient(app))

    assert len(plans) == 4
    assert all(plan["prices"] == [] for plan in plans)
    assert all(plan["entitlements"]["max_voice_agents"] is not None for plan in plans)


def test_unlimited_is_null_and_never_a_sentinel(client: TestClient) -> None:
    """`null` is unlimited, `0` is a real enforced ceiling, and `-1` is neither.
    The interface branches on `=== null`, so a sentinel would render as a number."""
    growth = next(plan for plan in _plans(client) if plan["plan_id"] == "growth")

    assert growth["entitlements"]["max_ai_integrations"] is None
    for limit in growth["entitlements"].values():
        assert limit is None or limit >= 0


# --- receipts --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_invoice_returns_raw_bytes_not_a_response_object() -> None:
    """Pins the contract both adapters have to meet.

    Narrow on purpose, because this is the one thing the stub could not have caught
    on its own: the real SDK hands back a *streaming* binary response, so the first
    version of `dodo.fetch_invoice` returned `response.content` - an attribute that
    does not exist - and every receipt download would have 500'd. The stub returns
    bytes directly, so only the type assertion is portable between them.

    The Dodo path itself was verified against a live invoice (52,453 bytes,
    `%PDF-1.7`); nothing here reaches the network.
    """
    pdf = await StubPaymentProvider().fetch_invoice(gateway_payment_id="pay_stub_1")

    assert isinstance(pdf, bytes)
    # A browser is handed this with `Content-Type: application/pdf`, so a body that
    # is not a PDF renders as a broken document rather than an error.
    assert pdf.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_a_gateway_that_issues_no_invoices_says_so_through_supports() -> None:
    """The route checks `supports(INVOICE_LIST)` before offering a receipt, and
    `BillingOverviewOut.has_receipt` is built from the same answer - so a deployment
    on a gateway with no invoices never renders a link that would 404."""
    assert StubPaymentProvider().supports(PaymentCapability.INVOICE_LIST) is True

    class NoInvoices(StubPaymentProvider):
        def supports(self, capability: PaymentCapability) -> bool:
            if capability is PaymentCapability.INVOICE_LIST:
                return False
            return super().supports(capability)

    assert NoInvoices().supports(PaymentCapability.INVOICE_LIST) is False
