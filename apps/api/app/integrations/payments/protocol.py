"""The `PaymentProvider` protocol every payment adapter conforms to.

Structural: an adapter conforms by having the right methods, not by inheriting
from anything here.

Two implementations exist from the start, which is the point. `dodo.py` is the
real one; `stub.py` is deterministic and offline, and it is what lets the whole
billing vertical - routes, repositories, webhook handling - be tested without a
gateway account. CLAUDE.md's Substitutability section asks for exactly that:
"An abstraction with one implementation is not an abstraction. Write the second
adapter, even if it is only a stub for tests."

**Nothing above this package may name a vendor.** Callers read `WebhookEvent.kind`
and `PaymentFailure`, never `"subscription.on_hold"` or a Dodo error string, so
swapping the gateway is a new file here rather than a rewrite everywhere. The
error taxonomy itself lives in `domain/subscriptions.py`, next to the state
machine it feeds, the same way `DialFailure` sits in `domain/entities.py` rather
than in the LiveKit adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from app.domain.subscriptions import PaymentFailure

JsonObject = dict[str, Any]


class PaymentCapability(str, Enum):
    """What an adapter can actually do.

    Checked with `supports()` before an optional feature is used, rather than
    assuming every gateway implements everything - CLAUDE.md's Interface
    Segregation. A Merchant of Record hosts its own invoices, for instance, so
    `INVOICE_LIST` may be absent and the UI links out instead of rendering a table
    it cannot fill.
    """

    HOSTED_CHECKOUT = "hosted_checkout"
    PLAN_CHANGE = "plan_change"
    CANCEL_AT_PERIOD_END = "cancel_at_period_end"
    LIVE_PRICES = "live_prices"
    RECONCILE = "reconcile"
    INVOICE_LIST = "invoice_list"
    REFUND = "refund"


class NotImplementedForProvider(NotImplementedError):
    """Raised by a capability a caller didn't check `supports()` for first."""


class PaymentsNotConfigured(RuntimeError):
    """Raised at construction when credentials are missing.

    Deliberately at construction rather than on first use, so a misconfigured
    deployment is caught when it starts rather than when an owner clicks Upgrade -
    the same choice `LiveKitGateway` and `core.crypto` already make.
    """


class GatewayUnavailable(RuntimeError):
    """A gateway call could not be completed.

    Carries the normalised `failure` so retry policy keys off CallFlow's own
    taxonomy, and `detail` because the vendor's own wording is often the only
    thing that says *why*. `detail` is shown to an owner, so it has to read as an
    instruction rather than a stack trace (CLAUDE.md §5).
    """

    def __init__(self, failure: PaymentFailure, detail: str) -> None:
        self.failure = failure
        self.detail = detail
        super().__init__(detail)


class BillingPeriod(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


@dataclass(frozen=True)
class Price:
    """A plan's price as the gateway holds it.

    Integer minor units - paise for INR, cents for USD - because money is never a
    float in this codebase (CLAUDE.md §4 #3). The gateway is the Merchant of
    Record and therefore the price of record; nothing in this repo stores a second
    copy for `lib/pricing.ts` to disagree with.
    """

    amount_minor: int
    currency: str
    period: BillingPeriod


@dataclass(frozen=True)
class CheckoutSession:
    url: str
    """The gateway's own subscription id, when it is known this early. Some
    gateways only mint one once the customer pays, which is why the webhook must
    also be able to resolve an organisation from checkout metadata."""
    gateway_subscription_id: str | None = None
    gateway_customer_id: str | None = None


class WebhookKind(str, Enum):
    """Normalised event kinds.

    A gateway's own event names never leave this package. `SUBSCRIPTION_RENEWED`
    is separate from `SUBSCRIPTION_ACTIVE` on purpose: renewal extends the paid
    period without changing status, so treating them as one event would force the
    state machine to permit a self-transition it deliberately rejects.
    """

    SUBSCRIPTION_ACTIVE = "subscription_active"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    SUBSCRIPTION_ON_HOLD = "subscription_on_hold"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    SUBSCRIPTION_FAILED = "subscription_failed"
    SUBSCRIPTION_UPDATED = "subscription_updated"
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_FAILED = "payment_failed"
    UNKNOWN = "unknown"
    """Everything a gateway sends that this version does not act on. Acknowledged
    and recorded rather than rejected: a gateway adding an event type must not
    start failing deliveries."""


@dataclass(frozen=True)
class WebhookEvent:
    """One verified inbound event, in CallFlow's own vocabulary."""

    event_id: str
    """The gateway's delivery id. Unique per delivery and the whole basis of
    replay protection - `payment_webhook_events` is keyed on it."""

    kind: WebhookKind
    raw_type: str
    """The vendor's own string. Recorded for diagnosis, never branched on."""

    gateway_subscription_id: str | None = None
    gateway_payment_id: str | None = None
    org_id: UUID | None = None
    """Resolved from checkout metadata when present. Load-bearing: a gateway can
    deliver `subscription.active` before the checkout call has returned and the
    subscription id has been persisted, and without this the first paid
    subscription in that race has nothing to match on."""

    subscription_row_id: UUID | None = None
    plan_id: str | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False
    amount_minor: int | None = None
    currency: str | None = None
    failure: PaymentFailure | None = None
    detail: str | None = None
    payload: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class RemoteSubscription:
    """A subscription as the gateway currently sees it.

    The gateway is the source of truth for money, and a webhook is only a
    notification about it - one that can be missed, delayed, or never configured.
    Being able to ask directly is what makes a missed delivery recoverable instead
    of a support ticket about a payment that vanished.
    """

    gateway_subscription_id: str
    status: WebhookKind
    """Expressed as the event it is equivalent to, so reconciliation and the
    webhook path converge on one mapping rather than two that can disagree."""

    plan_id: str | None
    subscription_row_id: UUID | None
    org_id: UUID | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    has_unsettled_payment: bool = False
    """True when the gateway's newest payment for this subscription has not
    succeeded yet.

    The gateway flips a subscription's product the moment a plan change is
    *initiated* - the charge behind it may still be processing, or may fail. Without
    this, entitlements follow the product and an organisation is upgraded before the
    money arrives; combined with a rule that keeps a paid plan until the period
    ends, a failed top-up would leave them on the higher plan for weeks.
    """


class PaymentProvider(Protocol):
    def supports(self, capability: PaymentCapability) -> bool: ...

    async def list_prices(self) -> Mapping[tuple[str, BillingPeriod], Price]:
        """Live prices, keyed by (plan_id, period).

        Plans with no configured product are simply absent - `enterprise` is
        invoiced outside the product and has no checkout, so the billing endpoint
        renders it without a price rather than inventing one.
        """
        ...

    async def create_checkout(
        self,
        *,
        plan_id: str,
        period: BillingPeriod,
        org_id: UUID,
        subscription_row_id: UUID,
        customer_email: str,
        customer_name: str | None,
        return_url: str,
    ) -> CheckoutSession: ...

    async def change_plan(
        self, *, gateway_subscription_id: str, plan_id: str, period: BillingPeriod
    ) -> None: ...

    async def cancel(self, *, gateway_subscription_id: str, at_period_end: bool) -> None:
        """Raises `NotImplementedForProvider` when `at_period_end` is asked of a
        gateway that only cancels immediately, rather than cancelling immediately
        and letting the caller believe otherwise."""
        ...

    async def find_subscriptions(self, *, org_id: UUID) -> list[RemoteSubscription]:
        """Every subscription the gateway holds for this organisation, newest first.

        Matched on the metadata planted at checkout, because the gateway's own id
        is exactly what we are missing when reconciliation is needed.

        Raises `NotImplementedForProvider` when `supports(RECONCILE)` is false.
        """
        ...

    async def find_subscriptions_by_id(
        self, *, gateway_subscription_id: str
    ) -> RemoteSubscription | None:
        """One subscription by the gateway's own id, or None if it has none.

        Separate from `find_subscriptions` because the webhook path already knows
        which subscription it is talking about and must not pay for a full listing
        to answer one question about it.
        """
        ...

    async def fetch_invoice(self, *, gateway_payment_id: str) -> bytes:
        """The invoice PDF for one settled payment.

        Bytes rather than a URL: a Merchant of Record's own invoice link is
        typically short-lived or session-bound, so handing one to a browser gives
        a customer a receipt that stops working. Fetching server-side also keeps
        the check that this payment belongs to *this* organisation on our side of
        the boundary, where it can be enforced.

        Raises `NotImplementedForProvider` when `supports(INVOICE_LIST)` is false.
        """
        ...

    def verify_webhook(self, *, raw_body: bytes, headers: Mapping[str, str]) -> WebhookEvent:
        """Verify a signature and normalise the payload, or raise.

        Takes raw bytes, never a parsed model: the signature covers the exact
        bytes received, so re-serialising a parsed body computes a different digest
        and rejects every genuine delivery.

        Raising must be indistinguishable to the caller for a bad signature, a
        stale timestamp and an unset secret - the route answers 404 to all three,
        so a prober learns nothing about which one it hit.
        """
        ...


__all__ = [
    "BillingPeriod",
    "CheckoutSession",
    "GatewayUnavailable",
    "JsonObject",
    "NotImplementedForProvider",
    "PaymentCapability",
    "PaymentProvider",
    "PaymentsNotConfigured",
    "Price",
    "RemoteSubscription",
    "WebhookEvent",
    "WebhookKind",
]
