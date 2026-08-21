"""The only file that imports the Dodo Payments SDK.

Every vendor name is aliased on the way in, so nothing above this module speaks
Dodo's vocabulary - a repo-wide non-negotiable (CLAUDE.md §2/§3-D).

**Dodo is a Merchant of Record**, which shapes three things here:
  - It holds the price of record, so `list_prices()` reads products back rather
    than this repo storing a second copy for `lib/pricing.ts` to contradict.
  - It owns the mandate and the dunning ladder, so there is nothing to build for
    retries - a failed renewal arrives as `subscription.on_hold` and that is all.
  - It issues the invoice, so `fetch_invoice` hands back Dodo's own PDF rather
    than this repo generating a document it is not the seller on. A tax invoice
    from the merchant of record is the one a customer can actually file.

**Errors carry two layers.** The SDK raises `APIStatusError` subclasses that
already distinguish auth from validation from rate limiting, and a
`DodoPaymentsError` base for transport failures. `classify_error()` is the single
place those become CallFlow's own `PaymentFailure`, and it fails closed: anything
unrecognised becomes `INTERNAL`, which is *not* retryable, so a failure this code
has never seen stops rather than being retried on the assumption it is transient.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from dodopayments import (
    APIConnectionError as _VendorConnectionError,
)
from dodopayments import (
    APIStatusError as _VendorStatusError,
)
from dodopayments import (
    APITimeoutError as _VendorTimeoutError,
)
from dodopayments import AsyncDodoPayments as _VendorClient
from dodopayments import (
    AuthenticationError as _VendorAuthError,
)
from dodopayments import (
    BadRequestError as _VendorBadRequest,
)
from dodopayments import (
    DodoPaymentsError as _VendorError,
)
from dodopayments import (
    NotFoundError as _VendorNotFound,
)
from dodopayments import (
    PermissionDeniedError as _VendorForbidden,
)
from dodopayments import (
    RateLimitError as _VendorRateLimit,
)

try:  # `standardwebhooks` arrives with the dodopayments[webhooks] extra.
    from standardwebhooks.webhooks import (
        WebhookVerificationError as _WebhookVerificationError,
    )
except ImportError:  # pragma: no cover - a deployment missing the extra
    class _WebhookVerificationError(Exception):  # type: ignore[no-redef]
        """Placeholder so this module still imports without the extra installed.

        The API must boot even on a deployment that forgot it - the webhook route
        then refuses every delivery with a clear "verification is unavailable" log
        line, which beats a crash on startup that takes the whole API down.
        """

from app.core.config import config
from app.domain.subscriptions import PaymentFailure
from app.integrations.payments.protocol import (
    BillingPeriod,
    CheckoutSession,
    GatewayUnavailable,
    NotImplementedForProvider,
    PaymentCapability,
    PaymentsNotConfigured,
    Price,
    RemoteSubscription,
    WebhookEvent,
    WebhookKind,
)

log = logging.getLogger("callflow.payments.dodo")

#: The pseudo-plan a one-time credit pack is configured under. Deliberately not
#: a `PlanId`: a top-up changes no subscription, and letting it into the ladder
#: would make it look like a plan someone could be on.
CREDIT_PACK = "credit_pack"

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

# Dodo's own subscription statuses, mapped onto the same normalised kinds the
# webhook path uses. One mapping, so a reconcile and a delivery can never disagree
# about what "on_hold" means.
_KIND_BY_STATUS: Mapping[str, WebhookKind] = {
    "active": WebhookKind.SUBSCRIPTION_ACTIVE,
    "on_hold": WebhookKind.SUBSCRIPTION_ON_HOLD,
    "cancelled": WebhookKind.SUBSCRIPTION_CANCELLED,
    "expired": WebhookKind.SUBSCRIPTION_EXPIRED,
    "failed": WebhookKind.SUBSCRIPTION_FAILED,
}

# Dodo's own event names, mapped once. Nothing above this file branches on them.
_KIND_BY_TYPE: Mapping[str, WebhookKind] = {
    "subscription.active": WebhookKind.SUBSCRIPTION_ACTIVE,
    "subscription.renewed": WebhookKind.SUBSCRIPTION_RENEWED,
    "subscription.on_hold": WebhookKind.SUBSCRIPTION_ON_HOLD,
    "subscription.cancelled": WebhookKind.SUBSCRIPTION_CANCELLED,
    "subscription.expired": WebhookKind.SUBSCRIPTION_EXPIRED,
    "subscription.failed": WebhookKind.SUBSCRIPTION_FAILED,
    "subscription.updated": WebhookKind.SUBSCRIPTION_UPDATED,
    # A plan change (`change_plan`) and a cancel-at-period-end (`cancel`) both
    # move fields on an already-active subscription rather than its status, so
    # Dodo reports them as `.plan_changed`/`.updated` rather than `.active`.
    # Both map onto the same kind: `handle_event`'s "same status, different
    # details" branch is what actually applies either one.
    "subscription.plan_changed": WebhookKind.SUBSCRIPTION_UPDATED,
    "payment.succeeded": WebhookKind.PAYMENT_SUCCEEDED,
    "payment.failed": WebhookKind.PAYMENT_FAILED,
}

# Ordered most specific first: several of these are subclasses of one another, so
# an isinstance walk over an unordered mapping would classify by luck.
_FAILURE_BY_EXCEPTION: tuple[tuple[type[BaseException], PaymentFailure], ...] = (
    (_VendorAuthError, PaymentFailure.UNAUTHORIZED),
    (_VendorForbidden, PaymentFailure.UNAUTHORIZED),
    (_VendorNotFound, PaymentFailure.INVALID_REQUEST),
    (_VendorBadRequest, PaymentFailure.INVALID_REQUEST),
    (_VendorRateLimit, PaymentFailure.PROVIDER_UNAVAILABLE),
    (_VendorTimeoutError, PaymentFailure.TIMED_OUT),
    (_VendorConnectionError, PaymentFailure.PROVIDER_UNAVAILABLE),
    (_VendorStatusError, PaymentFailure.PROVIDER_UNAVAILABLE),
    (_VendorError, PaymentFailure.INTERNAL),
)


def classify_error(exc: BaseException) -> PaymentFailure:
    """Map a vendor failure onto CallFlow's own taxonomy.

    Fails closed: anything unrecognised becomes INTERNAL, which is not in
    `_RETRYABLE`, so an error this code has never seen stops the attempt rather
    than being retried on the assumption it is transient.
    """
    for vendor_type, failure in _FAILURE_BY_EXCEPTION:
        if isinstance(exc, vendor_type):
            return failure
    return PaymentFailure.INTERNAL


def _detail(exc: BaseException) -> str:
    """The vendor's own wording, which is usually the only thing that says why.

    Shown to an owner on the Billing page, so it must read as an instruction
    rather than a stack trace (CLAUDE.md §5).

    `str(exc)` on an SDK error includes the raw response body, so it renders as
    `Error code: 409 - {'code': 'PLAN_CHANGE_NOT_ALLOWED_FOR...', 'message':
    'Subscription scheduled for cancellation'}`. A customer was shown exactly that.
    The `message` inside the body is the sentence worth reading; the dict around it
    is noise, and the error code is a support detail belonging in the log.
    """
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        message = str(body.get("message", "")).strip()
        if message:
            # Gateways rarely end these with punctuation, and this lands mid-sentence
            # in a toast.
            return message if message.endswith((".", "!", "?")) else f"{message}."

    message = str(exc).strip()
    return message or f"The payment provider refused the request ({type(exc).__name__})."


class _VendorClientFactory(Protocol):
    """What `DodoGateway` needs from the SDK, so a test can supply its own.

    Narrower than the real client on purpose: a stub implements this, not the
    whole of `AsyncDodoPayments`.
    """

    def __call__(self, *, bearer_token: str, webhook_key: str, environment: str) -> Any: ...


def _default_factory(*, bearer_token: str, webhook_key: str, environment: str) -> Any:
    return _VendorClient(
        bearer_token=bearer_token, webhook_key=webhook_key, environment=environment
    )


class DodoGateway:
    """Conforms to `PaymentProvider` structurally, without inheriting from it."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        webhook_key: str | None = None,
        environment: str | None = None,
        client_factory: _VendorClientFactory | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else config.dodo_api_key
        self._webhook_key = webhook_key if webhook_key is not None else config.dodo_webhook_key
        self._environment = (
            environment if environment is not None else config.dodo_environment
        )

        if not self._api_key:
            # At construction, not at first use: a misconfigured deployment is
            # caught when it starts rather than when an owner clicks Upgrade.
            raise PaymentsNotConfigured(
                "Dodo Payments is not configured. Set DODO_API_KEY before taking payments."
            )

        self._factory = client_factory or _default_factory
        self._client = self._factory(
            bearer_token=self._api_key,
            webhook_key=self._webhook_key,
            environment=self._environment,
        )

    # --- products -----------------------------------------------------------

    def _product_ids(self) -> dict[tuple[str, BillingPeriod], str]:
        """Only configured plans appear. A plan without a product id has no
        checkout, which `list_prices()` reports by omission rather than raising.

        `credit_pack` is a one-time product rather than a plan, and it is listed
        here so `create_checkout` can find it by the same lookup. It is filtered
        out of `list_prices()` below, because a top-up is not a rung on the ladder
        and showing it as one would put a fourth card on the pricing page.
        """
        configured = {
            ("starter", BillingPeriod.MONTHLY): config.dodo_product_starter_monthly,
            ("starter", BillingPeriod.ANNUAL): config.dodo_product_starter_annual,
            ("growth", BillingPeriod.MONTHLY): config.dodo_product_growth_monthly,
            ("growth", BillingPeriod.ANNUAL): config.dodo_product_growth_annual,
            (CREDIT_PACK, BillingPeriod.MONTHLY): config.dodo_product_credit_pack,
        }
        return {key: value for key, value in configured.items() if value}


    def _plan_for_product(self, product_id: object) -> str | None:
        """Which plan a gateway product belongs to.

        **The product is authoritative, not the checkout metadata.** `change_plan`
        swaps the product and leaves `metadata` exactly as checkout wrote it, so a
        subscription that moved Growth -> Starter still carries `plan_id: growth`
        forever. Reading the plan from metadata therefore made every plan change
        invisible to reconciliation: the gateway had applied it, and we compared our
        stale copy against theirs and concluded nothing had happened.

        Metadata is still worth keeping for `org_id` and `subscription_row_id`,
        which never change. It is only `plan_id` that goes stale.
        """
        if not isinstance(product_id, str) or not product_id:
            return None
        for (plan_id, _period), configured in self._product_ids().items():
            if configured == product_id:
                return plan_id
        return None

    def supports(self, capability: PaymentCapability) -> bool:
        return capability in _SUPPORTED

    async def fetch_invoice(self, *, gateway_payment_id: str) -> bytes:
        """Dodo's own invoice PDF for one payment.

        `gateway_payment_id` must already have been resolved from *our* `payments`
        table under RLS. Passing an id straight from a request would let anyone
        fetch any customer's invoice by guessing one - the gateway has no idea
        which organisation is asking.
        """
        try:
            response = await self._client.invoices.payments.retrieve(gateway_payment_id)
            # `read()`, not `.content`: the SDK returns a streaming binary response,
            # so the body has not been consumed yet when this returns.
            return await response.read()
        except _VendorError as exc:
            raise GatewayUnavailable(classify_error(exc), _detail(exc)) from exc

    async def list_prices(self) -> Mapping[tuple[str, BillingPeriod], Price]:
        prices: dict[tuple[str, BillingPeriod], Price] = {}
        for (plan_id, period), product_id in self._product_ids().items():
            if plan_id == CREDIT_PACK:
                # A top-up is not a plan. Included in `_product_ids` so checkout
                # can find it, excluded here so it never renders as a fourth rung
                # on the ladder.
                continue
            try:
                product = await self._client.products.retrieve(product_id)
            except Exception as exc:  # noqa: BLE001 - normalised immediately below
                # One unreachable product must not blank the whole plans page.
                # The plan renders without a price, which is the same thing the
                # interface already does for enterprise.
                log.warning(
                    "could not read a product price",
                    extra={"plan_id": plan_id, "period": period.value},
                )
                _ = classify_error(exc)
                continue

            amount = getattr(product, "price", None)
            # The SDK returns a Price object on paid products and None on free
            # ones; `price_detail` is the newer shape. Read defensively rather
            # than trusting one field name, because guessing wrong here shows a
            # customer the wrong number.
            amount_minor = _first_int(
                getattr(amount, "price", None),
                getattr(product, "price_detail", None) and
                getattr(product.price_detail, "price", None),
            )
            currency = _first_str(
                getattr(amount, "currency", None),
                getattr(product, "currency", None),
            )
            if amount_minor is None or not currency:
                log.warning(
                    "product carries no readable price",
                    extra={"plan_id": plan_id, "period": period.value},
                )
                continue
            prices[(plan_id, period)] = Price(
                amount_minor=amount_minor, currency=currency, period=period
            )
        return prices

    # --- checkout -----------------------------------------------------------

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
        product_id = self._product_ids().get((plan_id, period))
        if not product_id:
            raise GatewayUnavailable(
                PaymentFailure.INVALID_REQUEST,
                f"{plan_id} has no {period.value} product configured, so it cannot be "
                "checked out. Set the matching DODO_PRODUCT_* variable.",
            )

        try:
            session = await self._client.checkout_sessions.create(
                product_cart=[{"product_id": product_id, "quantity": 1}],
                customer={"email": customer_email, "name": customer_name or customer_email},
                return_url=return_url,
                # Carried back on every webhook for this subscription. Load-bearing:
                # Dodo can deliver `subscription.active` before this call returns and
                # the subscription id is persisted, and without these the first paid
                # subscription in that race has nothing to match on.
                metadata={
                    "org_id": str(org_id),
                    "subscription_row_id": str(subscription_row_id),
                    "plan_id": plan_id,
                },
            )
        except Exception as exc:
            raise GatewayUnavailable(classify_error(exc), _detail(exc)) from exc

        url = _first_str(
            getattr(session, "checkout_url", None), getattr(session, "url", None)
        )
        if not url:
            raise GatewayUnavailable(
                PaymentFailure.INTERNAL,
                "The payment provider returned a checkout with no URL to send you to.",
            )
        return CheckoutSession(
            url=url,
            gateway_subscription_id=_first_str(
                getattr(session, "subscription_id", None)
            ),
            gateway_customer_id=_first_str(getattr(session, "customer_id", None)),
        )

    # --- lifecycle ----------------------------------------------------------

    async def change_plan(
        self, *, gateway_subscription_id: str, plan_id: str, period: BillingPeriod
    ) -> None:
        product_id = self._product_ids().get((plan_id, period))
        if not product_id:
            raise GatewayUnavailable(
                PaymentFailure.INVALID_REQUEST,
                f"{plan_id} has no {period.value} product configured.",
            )
        try:
            await self._client.subscriptions.change_plan(
                subscription_id=gateway_subscription_id,
                product_id=product_id,
                # Charge the difference now rather than at the next renewal, so an
                # upgrade takes effect immediately - which is what an owner who
                # just hit a limit expects.
                proration_billing_mode="prorated_immediately",
                quantity=1,
            )
        except Exception as exc:
            raise GatewayUnavailable(classify_error(exc), _detail(exc)) from exc

    async def cancel(self, *, gateway_subscription_id: str, at_period_end: bool) -> None:
        """Dodo has no `cancel`; it is an `update`.

        `cancel_at_next_billing_date=True` is the end-of-period form and the only
        one this product uses - entitlements are meant to survive to the end of a
        period already paid for. An immediate cancel would need
        `status='cancelled'`, which no caller here wants, so asking for it raises
        rather than silently doing the gentler thing.
        """
        if not at_period_end:
            raise NotImplementedForProvider(
                "Immediate cancellation is not offered - a paid period runs to its end."
            )
        try:
            await self._client.subscriptions.update(
                subscription_id=gateway_subscription_id,
                cancel_at_next_billing_date=True,
            )
        except Exception as exc:
            raise GatewayUnavailable(classify_error(exc), _detail(exc)) from exc

    # --- webhooks -----------------------------------------------------------


    async def _has_unsettled_payment(self, subscription_id: str) -> bool:
        """Whether the newest payment for this subscription has not succeeded.

        Only the newest matters: an older failure that was retried and settled is
        history, and blocking on it would strand a customer who has since paid.

        Fails *closed* - an unreadable payment list is treated as unsettled, so a
        gateway outage cannot be the reason an unpaid upgrade gets granted.
        """
        try:
            page = await self._client.payments.list(
                subscription_id=subscription_id, page_size=1
            )
        except _VendorError:
            # The SDK's own base, not a blind `except`: a bug in this adapter should
            # surface as a 500, not be silently reported as "payment unsettled".
            log.warning(
                "could not read payments for a subscription; treating as unsettled",
                extra={"subscription_id": subscription_id},
            )
            return True

        async for payment in page:
            status = str(getattr(payment, "status", "")).lower()
            # Dodo's terminal-success value. Anything else - processing, requires
            # action, failed, cancelled - is money that has not arrived.
            return status != "succeeded"
        # No payments at all. A subscription with no payment has not been paid for.
        return True

    async def find_subscriptions(self, *, org_id: UUID) -> list[RemoteSubscription]:
        """Every subscription Dodo holds for this organisation, newest first.

        Matched on the `org_id` planted in checkout metadata, because the gateway's
        own subscription id is precisely what is missing when a webhook never
        arrived. Dodo's list endpoint has no metadata filter, so this pages and
        filters here - fine at the volumes one organisation produces, and this runs
        on an explicit request, never on the hot path.
        """
        try:
            page = await self._client.subscriptions.list()
        except Exception as exc:
            raise GatewayUnavailable(classify_error(exc), _detail(exc)) from exc

        found: list[RemoteSubscription] = []
        async for subscription in page:
            meta = _as_dict(getattr(subscription, "metadata", None))
            if str(meta.get("org_id", "")) != str(org_id):
                continue
            status = str(getattr(subscription, "status", "")).lower()
            found.append(
                RemoteSubscription(
                    gateway_subscription_id=str(subscription.subscription_id),
                    status=_KIND_BY_STATUS.get(status, WebhookKind.UNKNOWN),
                    plan_id=self._plan_for_product(getattr(subscription, "product_id", None))
                    or _first_str(meta.get("plan_id")),
                    subscription_row_id=_uuid_or_none(meta.get("subscription_row_id")),
                    org_id=_uuid_or_none(meta.get("org_id")),
                    current_period_end=_parse_when(
                        getattr(subscription, "next_billing_date", None)
                    ),
                    cancel_at_period_end=bool(
                        getattr(subscription, "cancel_at_next_billing_date", False)
                    ),
                    has_unsettled_payment=await self._has_unsettled_payment(
                        str(subscription.subscription_id)
                    ),
                )
            )
        return found

    async def find_subscriptions_by_id(
        self, *, gateway_subscription_id: str
    ) -> RemoteSubscription | None:
        try:
            subscription = await self._client.subscriptions.retrieve(gateway_subscription_id)
        except _VendorNotFound:
            return None
        except _VendorError as exc:
            raise GatewayUnavailable(classify_error(exc), _detail(exc)) from exc

        meta = _as_dict(getattr(subscription, "metadata", None))
        status = str(getattr(subscription, "status", "")).lower()
        return RemoteSubscription(
            gateway_subscription_id=gateway_subscription_id,
            status=_KIND_BY_STATUS.get(status, WebhookKind.UNKNOWN),
            plan_id=self._plan_for_product(getattr(subscription, "product_id", None))
            or _first_str(meta.get("plan_id")),
            subscription_row_id=_uuid_or_none(meta.get("subscription_row_id")),
            org_id=_uuid_or_none(meta.get("org_id")),
            current_period_end=_parse_when(getattr(subscription, "next_billing_date", None)),
            cancel_at_period_end=bool(
                getattr(subscription, "cancel_at_next_billing_date", False)
            ),
            has_unsettled_payment=await self._has_unsettled_payment(gateway_subscription_id),
        )

    def verify_webhook(self, *, raw_body: bytes, headers: Mapping[str, str]) -> WebhookEvent:
        if not self._webhook_key:
            # Fails closed on an unset secret, so a misconfigured deployment
            # refuses deliveries rather than accepting anonymous ones.
            raise GatewayUnavailable(
                PaymentFailure.UNAUTHORIZED, "No webhook signing key is configured."
            )

        # `unwrap` is synchronous even on the async client - it is pure crypto -
        # and it verifies the signature over the exact bytes plus the timestamp,
        # per the Standard Webhooks spec.
        #
        # `payload` is typed `str` by the SDK and handed to `standardwebhooks`, so the
        # raw bytes are decoded here rather than relying on it to cope.
        try:
            unwrapped = self._client.webhooks.unwrap(
                raw_body.decode("utf-8"), headers=dict(headers), key=self._webhook_key
            )
        except _VendorError as exc:
            # **A broken install is not a bad signature.** `unwrap` raises the SDK's
            # own error when `standardwebhooks` is missing, and an earlier version of
            # this method funnelled that into the same "unverified" path as a genuine
            # mismatch. The result was an API that rejected every real delivery as
            # unauthenticated, with a log line pointing at secrets - hours of looking
            # in the wrong place. This still refuses the request, because unverifiable
            # data must never be accepted, but it says which problem it is.
            log.error(
                "cannot verify webhooks - the gateway SDK is not installed correctly: %s",
                exc,
            )
            raise GatewayUnavailable(
                PaymentFailure.INTERNAL,
                "Webhook verification is unavailable on this deployment.",
            ) from exc
        except UnicodeDecodeError as exc:
            raise GatewayUnavailable(
                PaymentFailure.INVALID_REQUEST, "Webhook body was not valid UTF-8."
            ) from exc
        except _WebhookVerificationError as exc:
            # A real verification failure: bad signature, stale timestamp, missing
            # headers. Deliberately indistinguishable to the caller.
            raise GatewayUnavailable(PaymentFailure.UNAUTHORIZED, _detail(exc)) from exc

        lowered = {k.lower(): v for k, v in headers.items()}
        return _normalise(lowered.get("webhook-id", ""), unwrapped, self._plan_for_product)


def _first_int(*candidates: object) -> int | None:
    for candidate in candidates:
        if isinstance(candidate, bool):
            continue
        if isinstance(candidate, int):
            return candidate
    return None


def _first_str(*candidates: object) -> str | None:
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    return None


def _uuid_or_none(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def _as_dict(value: object) -> dict[str, Any]:
    """The SDK hands back pydantic models; tests hand back plain dicts.

    `mode="json"` is not cosmetic. A plain `model_dump()` keeps `datetime` objects,
    and the payload goes straight into a `jsonb` column - so a real delivery died
    with "Object of type datetime is not JSON serializable" and returned 500, which
    a gateway treats as "retry this for the next ten hours".

    The stub could not have caught it: its payloads come from `json.loads`, so they
    only ever contain primitives. Converting here, at the boundary where a vendor
    object becomes ours, is what keeps that difference from mattering again.
    """
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            result = dump(mode="json")
        except TypeError:
            # Not a pydantic v2 model - fall back rather than lose the payload.
            result = dump()
        if isinstance(result, dict):
            return result
    return {}


def _parse_when(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            # 3.11+ `fromisoformat` parses a trailing `Z` itself, so the usual
            # `.replace("Z", "+00:00")` dance is dead weight here.
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _normalise(
    event_id: str,
    unwrapped: object,
    plan_for_product: Callable[[object], str | None] | None = None,
) -> WebhookEvent:
    body = _as_dict(unwrapped)
    raw_type = str(body.get("type", ""))
    data = _as_dict(body.get("data"))
    meta = _as_dict(data.get("metadata"))

    def _uuid(value: object) -> UUID | None:
        try:
            return UUID(str(value))
        except (ValueError, TypeError):
            return None

    return WebhookEvent(
        event_id=event_id,
        kind=_KIND_BY_TYPE.get(raw_type, WebhookKind.UNKNOWN),
        raw_type=raw_type,
        gateway_subscription_id=_first_str(data.get("subscription_id")),
        gateway_payment_id=_first_str(data.get("payment_id")),
        org_id=_uuid(meta.get("org_id")),
        subscription_row_id=_uuid(meta.get("subscription_row_id")),
        # Product first, for the same reason as `find_subscriptions`: a plan
        # change leaves the checkout metadata behind.
        plan_id=(
            (plan_for_product(data.get("product_id")) if plan_for_product else None)
            or _first_str(meta.get("plan_id"), data.get("plan_id"))
        ),
        current_period_end=_parse_when(
            data.get("next_billing_date") or data.get("current_period_end")
        ),
        cancel_at_period_end=bool(data.get("cancel_at_next_billing_date", False)),
        amount_minor=_first_int(data.get("total_amount"), data.get("amount")),
        currency=_first_str(data.get("currency")),
        detail=_first_str(data.get("error_message")),
        payload=data,
    )


__all__ = ["DodoGateway", "classify_error"]
