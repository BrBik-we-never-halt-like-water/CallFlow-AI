"""An offline payment gateway, for tests and for a deployment with no keys.

This is the second implementation CLAUDE.md's Substitutability rule asks for, and
it is not decoration: it signs its own webhooks with the same scheme the real
adapter verifies, so the entire billing vertical - checkout, webhook replay,
state transitions, entitlement changes - is exercisable in CI, which has no
gateway account and no network.

Deterministic on purpose. Ids are derived from the arguments rather than random,
so a test can predict them and a replayed call produces the same id - which is
what makes the idempotency assertions meaningful rather than coincidental.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.domain.subscriptions import PaymentFailure
from app.integrations.payments.protocol import (
    BillingPeriod,
    CheckoutSession,
    GatewayUnavailable,
    PaymentCapability,
    Price,
    RemoteSubscription,
    WebhookEvent,
    WebhookKind,
)

# Local-only, and identical on every machine by design - the same reasoning
# `docker/.env`'s anon key carries. Nothing signed with this reaches a gateway.
STUB_WEBHOOK_SECRET = "stub-webhook-secret"

_PRICES: dict[tuple[str, BillingPeriod], Price] = {
    ("starter", BillingPeriod.MONTHLY): Price(99_900, "INR", BillingPeriod.MONTHLY),
    ("starter", BillingPeriod.ANNUAL): Price(999_000, "INR", BillingPeriod.ANNUAL),
    ("growth", BillingPeriod.MONTHLY): Price(499_900, "INR", BillingPeriod.MONTHLY),
    ("growth", BillingPeriod.ANNUAL): Price(4_999_000, "INR", BillingPeriod.ANNUAL),
    # A one-time credit pack, so the top-up path is exercisable offline. Absent
    # from `list_prices`'s contract as a *plan* - callers ask for it by name.
    ("credit_pack", BillingPeriod.MONTHLY): Price(50_000, "INR", BillingPeriod.MONTHLY),
}

_SUPPORTED = frozenset(
    {
        PaymentCapability.HOSTED_CHECKOUT,
        PaymentCapability.PLAN_CHANGE,
        PaymentCapability.CANCEL_AT_PERIOD_END,
        PaymentCapability.LIVE_PRICES,
        PaymentCapability.RECONCILE,
        PaymentCapability.INVOICE_LIST,
    }
)

_KIND_BY_TYPE: Mapping[str, WebhookKind] = {
    "subscription.active": WebhookKind.SUBSCRIPTION_ACTIVE,
    "subscription.renewed": WebhookKind.SUBSCRIPTION_RENEWED,
    "subscription.on_hold": WebhookKind.SUBSCRIPTION_ON_HOLD,
    "subscription.cancelled": WebhookKind.SUBSCRIPTION_CANCELLED,
    "subscription.expired": WebhookKind.SUBSCRIPTION_EXPIRED,
    "subscription.failed": WebhookKind.SUBSCRIPTION_FAILED,
    "subscription.updated": WebhookKind.SUBSCRIPTION_UPDATED,
    # Mirrors the real adapter (`dodo.py`): a plan change reports as its own
    # event type, and is handled identically to `.updated` by `handle_event`.
    "subscription.plan_changed": WebhookKind.SUBSCRIPTION_UPDATED,
    "payment.succeeded": WebhookKind.PAYMENT_SUCCEEDED,
    "payment.failed": WebhookKind.PAYMENT_FAILED,
}

# Matches the real adapter's window. Standard Webhooks signs
# `id.timestamp.body`, and rejecting anything older than five minutes is what
# stops a captured delivery being replayed later.
_MAX_AGE_SECONDS = 300


def _digest(secret: str, event_id: str, timestamp: str, raw_body: bytes) -> str:
    signed = b".".join([event_id.encode(), timestamp.encode(), raw_body])
    return hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()


def sign(event_id: str, raw_body: bytes, *, timestamp: int | None = None) -> dict[str, str]:
    """Produce the headers a genuine delivery would carry.

    Test-only, and the reason the stub is worth having: a test can now assert
    that a *tampered* body is rejected, which is impossible to check against a
    real gateway without asking it to send something malformed.
    """
    stamp = str(timestamp if timestamp is not None else int(time.time()))
    return {
        "webhook-id": event_id,
        "webhook-timestamp": stamp,
        "webhook-signature": _digest(STUB_WEBHOOK_SECRET, event_id, stamp, raw_body),
    }


class StubPaymentProvider:
    """Conforms to `PaymentProvider` structurally, without inheriting from it."""

    def __init__(
        self,
        *,
        fail_with: PaymentFailure | None = None,
        remote: list[RemoteSubscription] | None = None,
    ) -> None:
        # Lets a test drive the unhappy path without patching internals.
        self._fail_with = fail_with
        # What `find_subscriptions` will report. A test sets this to stand in for
        # "the gateway took a payment we never heard about".
        self.remote: list[RemoteSubscription] = remote or []

    def supports(self, capability: PaymentCapability) -> bool:
        return capability in _SUPPORTED

    def _guard(self) -> None:
        if self._fail_with is not None:
            raise GatewayUnavailable(self._fail_with, "The stub gateway was asked to fail.")

    async def list_prices(self) -> Mapping[tuple[str, BillingPeriod], Price]:
        self._guard()
        return dict(_PRICES)

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
    ) -> CheckoutSession:
        self._guard()
        if (plan_id, period) not in _PRICES:
            # The same refusal a real gateway gives for a product it has no price
            # for, so the enterprise-has-no-checkout path is exercised too.
            raise GatewayUnavailable(
                PaymentFailure.INVALID_REQUEST,
                f"{plan_id} has no {period.value} price and cannot be checked out.",
            )
        token = hashlib.sha256(
            f"{org_id}:{subscription_row_id}:{plan_id}:{period.value}".encode()
        ).hexdigest()[:16]
        return CheckoutSession(
            url=f"https://stub.checkout.invalid/{token}?return_to={return_url}",
            gateway_subscription_id=f"sub_stub_{token}",
            gateway_customer_id=f"cus_stub_{token}",
        )

    async def change_plan(
        self, *, gateway_subscription_id: str, plan_id: str, period: BillingPeriod
    ) -> None:
        self._guard()

    async def cancel(self, *, gateway_subscription_id: str, at_period_end: bool) -> None:
        self._guard()

    async def find_subscriptions(self, *, org_id: UUID) -> list[RemoteSubscription]:
        """Whatever a test put in `remote`. Empty by default, which is the honest
        answer for an offline gateway that has never taken a payment."""
        self._guard()
        return [s for s in self.remote if s.org_id == org_id]

    async def find_subscriptions_by_id(
        self, *, gateway_subscription_id: str
    ) -> RemoteSubscription | None:
        self._guard()
        return next(
            (s for s in self.remote if s.gateway_subscription_id == gateway_subscription_id),
            None,
        )

    async def fetch_invoice(self, *, gateway_payment_id: str) -> bytes:
        """A real, minimal PDF - not a text file with a .pdf name.

        The route sets `application/pdf` and a browser will try to render it, so a
        stub that returned prose would make the offline path look broken in exactly
        the way a real failure does.
        """
        self._guard()
        return (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 50]>>endobj\n"
            b"trailer<</Root 1 0 R>>\n%%EOF\n"
        )

    def verify_webhook(self, *, raw_body: bytes, headers: Mapping[str, str]) -> WebhookEvent:
        lowered = {k.lower(): v for k, v in headers.items()}
        event_id = lowered.get("webhook-id", "")
        timestamp = lowered.get("webhook-timestamp", "")
        signature = lowered.get("webhook-signature", "")

        if not (event_id and timestamp and signature):
            raise GatewayUnavailable(PaymentFailure.UNAUTHORIZED, "Missing signature headers.")

        try:
            age = abs(int(time.time()) - int(timestamp))
        except ValueError as exc:
            raise GatewayUnavailable(
                PaymentFailure.UNAUTHORIZED, "Unreadable webhook timestamp."
            ) from exc
        if age > _MAX_AGE_SECONDS:
            raise GatewayUnavailable(PaymentFailure.UNAUTHORIZED, "Webhook timestamp too old.")

        expected = _digest(STUB_WEBHOOK_SECRET, event_id, timestamp, raw_body)
        # Constant time, so a caller cannot learn the digest a byte at a time.
        if not hmac.compare_digest(expected, signature):
            raise GatewayUnavailable(PaymentFailure.UNAUTHORIZED, "Signature does not match.")

        return _normalise(event_id, json.loads(raw_body))


def _normalise(event_id: str, body: dict[str, object]) -> WebhookEvent:
    raw_type = str(body.get("type", ""))
    data = body.get("data")
    payload: dict[str, object] = data if isinstance(data, dict) else {}
    metadata = payload.get("metadata")
    meta: dict[str, object] = metadata if isinstance(metadata, dict) else {}

    def _uuid(value: object) -> UUID | None:
        try:
            return UUID(str(value))
        except (ValueError, TypeError):
            return None

    period_end = payload.get("current_period_end")
    parsed_end: datetime | None = None
    if isinstance(period_end, str):
        try:
            parsed_end = datetime.fromisoformat(period_end)
        except ValueError:
            parsed_end = None
    elif isinstance(period_end, int):
        parsed_end = datetime.fromtimestamp(period_end, tz=UTC)

    return WebhookEvent(
        event_id=event_id,
        kind=_KIND_BY_TYPE.get(raw_type, WebhookKind.UNKNOWN),
        raw_type=raw_type,
        gateway_subscription_id=(
            str(payload["subscription_id"]) if payload.get("subscription_id") else None
        ),
        gateway_payment_id=(str(payload["payment_id"]) if payload.get("payment_id") else None),
        org_id=_uuid(meta.get("org_id")),
        subscription_row_id=_uuid(meta.get("subscription_row_id")),
        plan_id=str(payload["plan_id"]) if payload.get("plan_id") else None,
        current_period_end=parsed_end,
        cancel_at_period_end=bool(payload.get("cancel_at_period_end", False)),
        amount_minor=(
            int(payload["amount_minor"]) if isinstance(payload.get("amount_minor"), int) else None
        ),
        currency=str(payload["currency"]) if payload.get("currency") else None,
        payload=dict(payload),
    )


def stub_event_body(
    event_type: str,
    *,
    subscription_id: str | None = None,
    payment_id: str | None = None,
    org_id: UUID | None = None,
    subscription_row_id: UUID | None = None,
    plan_id: str | None = None,
    period_days: int | None = 30,
    amount_minor: int | None = None,
    currency: str = "INR",
    cancel_at_period_end: bool = False,
) -> bytes:
    """Build a delivery body a test can sign. Returns bytes, because the signature
    covers exact bytes and re-serialising would change the digest."""
    data: dict[str, object] = {"cancel_at_period_end": cancel_at_period_end}
    if subscription_id:
        data["subscription_id"] = subscription_id
    if payment_id:
        data["payment_id"] = payment_id
    if plan_id:
        data["plan_id"] = plan_id
    if amount_minor is not None:
        data["amount_minor"] = amount_minor
        data["currency"] = currency
    if period_days is not None:
        data["current_period_end"] = (
            datetime.now(UTC) + timedelta(days=period_days)
        ).isoformat()
    metadata: dict[str, str] = {}
    if org_id is not None:
        metadata["org_id"] = str(org_id)
    if subscription_row_id is not None:
        metadata["subscription_row_id"] = str(subscription_row_id)
    if metadata:
        data["metadata"] = metadata
    return json.dumps({"type": event_type, "data": data}).encode()


__all__ = ["STUB_WEBHOOK_SECRET", "StubPaymentProvider", "sign", "stub_event_body"]
