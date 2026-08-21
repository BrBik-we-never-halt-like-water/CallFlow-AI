"""Plans, the current subscription, checkout, and the gateway webhook.

`docs/BILLING.md` §7. `billing:read` is admin+, `billing:write` is owner-only -
`Permission.BILLING_WRITE` has existed since the initial schema, documented in
`permissions.py` as "upgrading/downgrading the plan itself", attached to nothing
until now.

The webhook is the odd one out and deliberately so: no auth dependency, raw bytes
rather than a parsed model, and 404 for every signature failure. See
`dodo_webhook` for why each of those is not an oversight.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission, current_user
from app.auth.permissions import Permission
from app.core.config import config
from app.core.rate_limit import limiter
from app.database import database
from app.database.repositories import credits as credits_repo
from app.database.repositories import safety_settings as safety_repo
from app.database.repositories import subscriptions as subs_repo
from app.database.repositories import usage_rates as rates_repo
from app.domain.plans import Entitlements, PlanId, ladder
from app.domain.safety import resolve_safety_settings

# The pseudo-plan a credit pack is looked up under. Not a `PlanId`: a top-up is
# not a plan and must never appear in the ladder, or it would show up as a
# fourth card someone could "upgrade" to. Shared with `services/billing.py`'s
# webhook handling, which is how it recognises a top-up payment with no
# subscription row to key off - one constant, so the two cannot drift.
from app.integrations.payments.dodo import CREDIT_PACK
from app.integrations.payments.protocol import (
    BillingPeriod,
    GatewayUnavailable,
    NotImplementedForProvider,
    PaymentCapability,
)
from app.services import billing
from app.services import credit as credit_service

log = logging.getLogger("callflow.billing.routes")

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
webhook_router = APIRouter(prefix="/api/v1/webhooks", tags=["billing"])
# Split out rather than hung off `router` with no dependency, so "which billing
# routes are reachable without a session" is answered by reading one line here
# instead of auditing every decorator in the file.
public_router = APIRouter(prefix="/api/v1/public/billing", tags=["billing"])


class EntitlementsOut(BaseModel):
    """`null` is unlimited throughout. `0` is a real, enforced ceiling - never
    collapse the two with a falsiness check on the way to the interface."""

    max_voice_agents: int | None
    max_seats: int | None
    max_organisations: int | None
    max_ai_integrations: int | None
    daily_call_budget: int | None
    """A runaway bound, identical on every plan - not a plan feature. Usage credit
    is the economic limit and binds first by a wide margin, so this is shown under
    Settings -> Safety rather than on a plan card."""
    monthly_credit_paise: int | None
    llm_spend_limit_usd: float


class UsageOut(BaseModel):
    voice_agents: int
    seats: int
    organisations: int
    ai_integrations: int
    calls_today: int


class PlanPriceOut(BaseModel):
    amount_minor: int
    currency: str
    period: str


class PlanOptionOut(BaseModel):
    plan_id: str
    name: str
    entitlements: EntitlementsOut
    prices: list[PlanPriceOut]
    self_serve: bool
    current: bool
    baseline_rate_paise_per_minute: int
    """What a connected minute costs on your own model keys - the platform fee
    alone, since no tier add-on applies once nothing runs on CallFlow's keys.
    The same number for every plan (`usage_rates`' one platform-fee row), carried
    per option so a card can show it and the credit together without a second
    request. A real call may cost more if it runs on CallFlow's keys for a tiered
    leg - see `docs/PRICING_DECISIONS.md` §3."""


class SubscriptionOut(BaseModel):
    status: str
    plan_id: str
    current_period_end: str | None
    cancel_at_period_end: bool
    last_error: str | None


class PaymentOut(BaseModel):
    id: str
    amount_minor: int
    currency: str
    status: str
    description: str | None
    paid_at: str | None
    has_receipt: bool
    """True when this payment settled *and* the gateway can produce an invoice for
    it. The interface uses it to decide whether to offer a Receipt link at all,
    rather than showing one on every row and letting a third of them 404."""


class CreditOut(BaseModel):
    """Usage credit. **Money is the truth; minutes are an estimate.**

    `estimated_minutes_left` is derived from the organisation's *current* rate, and
    the next call may use a different pipeline. With a 23x cost spread across
    pipelines there is no single honest conversion, which is why the interface
    shows the money figure and labels the minutes as approximate.
    """

    balance_paise: int
    granted_this_period_paise: int
    rate_paise_per_minute: int
    estimated_minutes_left: int
    is_uncapped: bool
    """True for a plan with no credit ceiling. The meter renders "unlimited"
    rather than a bar, and the dial gate does not check a balance at all."""


class LedgerEntryOut(BaseModel):
    id: str
    entry_kind: str
    amount_minor: int
    """Signed. Positive added credit, negative consumed or expired it."""
    currency: str
    call_key: str | None
    rate_paise_per_minute: int | None
    reason: str | None
    created_at: str


class TopUpIn(BaseModel):
    # Same contract as `/checkout`: the caller's own retry token, so a
    # double-click buys one pack rather than two.
    idempotency_key: str = Field(min_length=8, max_length=120)


class BillingOverviewOut(BaseModel):
    plan_id: str
    plan_name: str
    subscription: SubscriptionOut | None
    entitlements: EntitlementsOut
    usage: UsageOut
    effective_daily_call_budget: int
    """What runs actually stop at today - `min()` of the plan allowance, the
    organisation's own Settings -> Safety value, and the deployment default. The
    meter shows this; `entitlements.daily_call_budget` is what the *plan* permits,
    which can be higher."""
    has_custom_limits: bool
    credit: CreditOut
    payments: list[PaymentOut]
    payments_configured: bool
    """False on a deployment with no gateway key. The interface uses this to keep
    saying "no payment processor is connected" instead of offering an upgrade
    button that would run against the stub (CLAUDE.md §4 #9)."""
    credit_pack_configured: bool
    """False when `DODO_PRODUCT_CREDIT_PACK` is unset. Distinct from
    `payments_configured`: a deployment can take real subscription payments and
    still have no top-up product, and the "Top up" button reads this rather than
    `payments_configured` alone - CLAUDE.md §4 #9 again, the same reasoning that
    gates the subscription buttons above, just for the other purchase."""


class CheckoutIn(BaseModel):
    plan_id: str
    period: BillingPeriod = BillingPeriod.MONTHLY
    # The caller's own retry token. Reusing it resumes the same checkout instead of
    # opening a second subscription, the same contract `connect-number` has.
    idempotency_key: str = Field(min_length=8, max_length=120)


class CheckoutOut(BaseModel):
    checkout_url: str


class ChangePlanIn(BaseModel):
    plan_id: str
    period: BillingPeriod = BillingPeriod.MONTHLY


# `enterprise` is invoiced outside the product and `free` has nothing to charge
# for, so neither has a checkout. Stated once here rather than inferred from
# whether a price happens to exist, which would silently turn a misconfigured
# product id into "this plan is contact-us".
_SELF_SERVE = frozenset({PlanId.STARTER.value, PlanId.GROWTH.value})


def _entitlements_out(entitlements: Entitlements) -> EntitlementsOut:
    return EntitlementsOut(
        max_voice_agents=entitlements.max_voice_agents,
        max_seats=entitlements.max_seats,
        max_organisations=entitlements.max_organisations,
        max_ai_integrations=entitlements.max_ai_integrations,
        daily_call_budget=entitlements.daily_call_budget,
        monthly_credit_paise=entitlements.monthly_credit_paise,
        llm_spend_limit_usd=float(entitlements.llm_spend_limit_usd),
    )


async def _daily_calls(
    conn: Any, org_id: UUID, plan_daily_budget: int | None
) -> tuple[int, int]:
    """`(used today, the ceiling it was counted against)`.

    Both, deliberately. The plan's *allowance* and the *effective* ceiling are two
    different true numbers: a deployment default or an organisation's own Settings
    -> Safety value can be lower than the plan permits, and `min()` wins. Returning
    only the plan number is how Billing ends up promising 20 calls while runs stop
    at 5 - display and enforcement disagreeing, which is the exact failure
    `resolve_safety_settings` exists to prevent.

    Reads the same in-process limiter every run passes through. That counter resets
    on restart and does not cross replicas - a documented limitation (`SYSTEM.md`
    §7), and the reason this is labelled "today" rather than shown as a billing
    figure.
    """
    row = await safety_repo.get_for_org(conn, org_id)
    effective = resolve_safety_settings(
        allowlist=row["allowlist"] if row else None,
        max_calls_per_run=row["max_calls_per_run"] if row else None,
        calls_per_window=row["calls_per_window"] if row else None,
        window_minutes=row["window_minutes"] if row else None,
        daily_budget=row["daily_budget"] if row else None,
        plan_daily_budget=plan_daily_budget,
    )
    snapshot = limiter.snapshot(
        str(org_id),
        rate_limit_calls=effective.calls_per_window,
        rate_limit_window_seconds=effective.window_minutes * 60,
        daily_call_budget=effective.daily_budget,
    )
    return int(snapshot.get("used_today", 0)), effective.daily_budget


async def _live_prices() -> dict[tuple[str, BillingPeriod], Any]:
    """What the gateway currently charges, or `{}` if it cannot be asked.

    A gateway outage must not blank a plans page. Every plan still renders with its
    entitlements; only the numbers are missing, and both callers are built to say
    so rather than print a zero.
    """
    gateway = billing.provider()
    if not gateway.supports(PaymentCapability.LIVE_PRICES):
        return {}
    try:
        return dict(await gateway.list_prices())
    except GatewayUnavailable as exc:
        log.warning("could not read live prices: %s", exc.detail)
        return {}


def _plan_options(
    prices: dict[tuple[str, BillingPeriod], Any],
    *,
    current_plan_id: str | None,
    baseline_rate_paise_per_minute: int,
) -> list[PlanOptionOut]:
    """The ladder as the interface renders it.

    `current_plan_id=None` means the caller has no organisation - the public
    endpoint - so no card is marked current rather than one being guessed.
    """
    return [
        PlanOptionOut(
            plan_id=plan.value,
            name=billing.plan_name(plan.value),
            entitlements=_entitlements_out(entitlements),
            prices=[
                PlanPriceOut(
                    amount_minor=price.amount_minor,
                    currency=price.currency,
                    period=price.period.value,
                )
                for (plan_id, _), price in sorted(
                    prices.items(), key=lambda item: item[0][1].value
                )
                if plan_id == plan.value
            ],
            self_serve=plan.value in _SELF_SERVE,
            current=plan.value == current_plan_id,
            baseline_rate_paise_per_minute=baseline_rate_paise_per_minute,
        )
        for plan, entitlements in ladder().items()
    ]


@public_router.get("/plans", response_model=list[PlanOptionOut])
async def list_public_plans() -> list[PlanOptionOut]:
    """The ladder for the marketing site, which has no session.

    Unauthenticated, and the only billing route that is. It exposes nothing an
    organisation owns: the ladder is the same for everybody, the prices are the
    ones the gateway shows on its own hosted checkout, and `current` is always
    false because there is nobody to be current for.

    The one read this needs - the platform-fee row of `usage_rates` - goes
    through `database.anonymous()`, which sets the session to Postgres' `anon`
    role rather than opening an authenticated, org-scoped connection. `anon`
    holds a plain `select` on `usage_rates` (seeded in the same migration as the
    table), so this stays off the per-organisation RLS surface entirely; it is
    a public rate card, not a query that could leak a tenant's row.
    """
    async with database.anonymous() as conn:
        card = await rates_repo.load_rate_card(conn)
    return _plan_options(
        await _live_prices(),
        current_plan_id=None,
        baseline_rate_paise_per_minute=card.platform_fee,
    )


@router.get("/plans", response_model=list[PlanOptionOut])
async def list_plans(user: Annotated[CurrentUser, Depends(current_user)]) -> list[PlanOptionOut]:
    """The ladder, with live prices and the organisation's current plan marked.

    Signed in rather than `billing:read`: an operator who hits an agent limit is
    shown what the next plan includes, they just cannot start a checkout.

    Prices come from the gateway because it is the Merchant of Record and holds the
    price of record. A plan with no configured product simply has no price, which
    the interface renders as "contact us" rather than as a missing number.
    """
    prices = await _live_prices()
    async with database.as_user(user.auth_user_id) as conn:
        effective = await billing.resolve_plan(conn, user.org_id, user.org_plan_id)
        card = await rates_repo.load_rate_card(conn)
    return _plan_options(
        prices,
        current_plan_id=effective.plan_id,
        baseline_rate_paise_per_minute=card.platform_fee,
    )


@router.get("/subscription", response_model=BillingOverviewOut)
async def get_overview(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.BILLING_READ))],
) -> BillingOverviewOut:
    async with database.as_user(user.auth_user_id) as conn:
        effective = await billing.resolve_plan(conn, user.org_id, user.org_plan_id)
        calls_today, effective_daily = await _daily_calls(
            conn, user.org_id, effective.entitlements.daily_call_budget
        )
        usage = await billing.usage_for(conn, user.org_id, calls_today=calls_today)
        payments = await subs_repo.list_payments(conn, user.org_id)
        # The organisation's *current* rate, which today is the platform fee for
        # everyone: no leg runs on a CallFlow key because CallFlow holds none, so
        # `PipelineLeg` defaults `on_platform_key` to false. When platform keys
        # exist this becomes a per-agent question and moves to the agent read.
        # Same lazy grant as the run gate, so the meter shows what a Free
        # organisation actually has rather than a zero it would only discover
        # when a run was refused.
        await credit_service.ensure_period_credit(
            conn,
            org_id=user.org_id,
            entitlements=effective.entitlements,
            has_subscription=billing.subscription_grants_credit(effective),
        )
        rate = await credit_service.rate_for(conn, ())
        credit_view = await credit_service.overview(
            conn, org_id=user.org_id, entitlements=effective.entitlements, rate=rate
        )

    row = effective.subscription
    subscription = (
        SubscriptionOut(
            status=row["status"],
            plan_id=row["plan_id"],
            current_period_end=(
                row["current_period_end"].isoformat() if row["current_period_end"] else None
            ),
            cancel_at_period_end=row["cancel_at_period_end"],
            last_error=row["last_error"],
        )
        if row is not None
        else None
    )

    receipts_available = billing.provider().supports(PaymentCapability.INVOICE_LIST)

    return BillingOverviewOut(
        credit=CreditOut(
            balance_paise=credit_view.balance_paise,
            granted_this_period_paise=credit_view.granted_this_period_paise,
            rate_paise_per_minute=credit_view.rate_paise_per_minute,
            estimated_minutes_left=credit_view.estimated_minutes_left,
            is_uncapped=credit_view.is_uncapped,
        ),
        plan_id=effective.plan_id,
        plan_name=billing.plan_name(effective.plan_id),
        subscription=subscription,
        entitlements=_entitlements_out(effective.entitlements),
        usage=UsageOut(
            voice_agents=usage.voice_agents,
            seats=usage.seats,
            organisations=usage.organisations,
            ai_integrations=usage.ai_integrations,
            calls_today=usage.calls_today,
        ),
        effective_daily_call_budget=effective_daily,
        has_custom_limits=effective.has_custom_limits,
        payments=[
            PaymentOut(
                has_receipt=(p["status"] == "succeeded" and receipts_available),
                id=str(p["id"]),
                amount_minor=p["amount_minor"],
                currency=p["currency"],
                status=p["status"],
                description=p["description"],
                paid_at=p["paid_at"].isoformat() if p["paid_at"] else None,
            )
            for p in payments
        ],
        payments_configured=config.payments_configured,
        credit_pack_configured=bool(config.dodo_product_credit_pack),
    )


@router.get("/credit-ledger", response_model=list[LedgerEntryOut])
async def credit_ledger(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.BILLING_READ))],
    limit: int = 100,
) -> list[LedgerEntryOut]:
    """The statement: every grant, hold, release, spend and expiry.

    Holds and their releases are both shown rather than netted away. A customer
    asking "why did my balance dip and come back" deserves to see that a call was
    reserved for and did not connect - netting it would make the ledger tidier and
    less true.
    """
    async with database.as_user(user.auth_user_id) as conn:
        rows = await credits_repo.list_ledger(conn, user.org_id, limit=min(limit, 500))
    return [
        LedgerEntryOut(
            id=str(row["id"]),
            entry_kind=row["entry_kind"],
            amount_minor=row["amount_minor"],
            currency=row["currency"],
            call_key=row["call_key"],
            rate_paise_per_minute=row["rate_paise_per_minute"],
            reason=row["reason"],
            created_at=row["created_at"].isoformat(),
        )
        for row in rows
    ]


@router.post("/top-up", response_model=CheckoutOut)
async def start_top_up(
    body: TopUpIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.BILLING_WRITE))],
) -> CheckoutOut:
    """Buy more usage credit mid-period.

    A one-time purchase, not a subscription change - so it goes through the
    gateway's ordinary checkout against a credit-pack product, and the credit is
    granted by the resulting `payment.succeeded` webhook rather than here. Granting
    on this response would hand out credit for a payment that had not settled,
    which is the rule `withholds_grant` exists to hold.

    404 rather than 400 when no pack is configured: a deployment without one has
    no top-up feature, and saying so is honest where a 400 would imply the request
    was malformed.
    """
    if not config.dodo_product_credit_pack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No credit pack is configured on this deployment.",
        )

    gateway = billing.provider()
    if not gateway.supports(PaymentCapability.HOSTED_CHECKOUT):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This deployment cannot take payments yet.",
        )

    try:
        session = await gateway.create_checkout(
            plan_id=CREDIT_PACK,
            period=BillingPeriod.MONTHLY,
            org_id=user.org_id,
            subscription_row_id=uuid4(),
            customer_email=user.email,
            customer_name=user.name,
            return_url=f"{config.site_url}/app/billing",
        )
    except GatewayUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail
        ) from exc

    return CheckoutOut(checkout_url=session.url)


@router.get("/payments/{payment_id}/receipt")
async def download_receipt(
    payment_id: UUID,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.BILLING_READ))],
) -> Response:
    """The gateway's own invoice PDF for one payment.

    The organisation check is the whole security of this endpoint and it happens
    **before** the gateway is contacted: the payment is looked up by our id under
    RLS, and only a row this session can actually see yields the gateway's id. The
    gateway has no idea which organisation is asking, so taking its id from the URL
    would turn a guessable string into any customer's invoice.

    Served through the API rather than by redirecting to a gateway link: a merchant
    of record's invoice URLs are typically short-lived or session-bound, so a
    redirect hands the customer a receipt that stops working.
    """
    gateway = billing.provider()
    if not gateway.supports(PaymentCapability.INVOICE_LIST):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This payment provider doesn't issue downloadable receipts.",
        )

    async with database.as_user(user.auth_user_id) as conn:
        payment = await subs_repo.get_payment(conn, payment_id=payment_id)

    # 404 for "not yours" and "no such payment" alike - a different answer for each
    # tells someone which payment ids exist.
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such payment."
        )
    if payment["status"] != "succeeded" or not payment["gateway_payment_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="An invoice is issued once a payment has settled.",
        )

    try:
        pdf = await gateway.fetch_invoice(
            gateway_payment_id=payment["gateway_payment_id"]
        )
    except GatewayUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail
        ) from exc

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            # `inline` rather than `attachment`: a receipt is usually glanced at,
            # and a browser that renders it still offers a save button.
            "Content-Disposition": f'inline; filename="receipt-{payment_id}.pdf"',
            # A settled invoice never changes, but it is a customer's financial
            # document - private, and never held by a shared cache.
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.post("/checkout", response_model=CheckoutOut)
async def start_checkout(
    body: CheckoutIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.BILLING_WRITE))],
) -> CheckoutOut:
    """Open a hosted checkout for a plan.

    Order matters and is not arbitrary: the subscription row is created *before*
    the gateway call, with an id this route generates, because that id travels to
    the gateway as checkout metadata. It is how the webhook finds the subscription
    when the gateway delivers `subscription.active` before this call has returned.
    """
    if not config.payments_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No payment processor is connected on this deployment, so a plan "
                "cannot be purchased here yet."
            ),
        )
    if body.plan_id not in _SELF_SERVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{billing.plan_name(body.plan_id)} is not available to buy here. "
                "Book a demo and we will set it up."
            ),
        )

    gateway = billing.provider()
    subscription_id = uuid4()

    async with database.as_user(user.auth_user_id) as conn:
        row, created = await subs_repo.start_pending(
            conn,
            subscription_id=subscription_id,
            org_id=user.org_id,
            plan_id=body.plan_id,
            gateway=billing.GATEWAY_NAME,
            created_by=user.id,
        )
        if not created:
            if row["status"] != "pending":
                # An active or on-hold subscription already exists. Sending them
                # through checkout again would create a second one at the gateway
                # and charge twice; a plan change is the operation they want.
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This organisation already has a subscription. Change the plan "
                        "instead of starting a new checkout."
                    ),
                )
            if row["gateway_subscription_id"]:
                # Pending *and* already bound to a gateway subscription: a checkout
                # was started and the gateway has minted an id for it. Reusing this
                # row is what produced two active subscriptions billed in parallel,
                # both tagged with one row id.
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "A checkout is already in progress for this organisation. "
                        "Finish or cancel it with the payment provider, then use "
                        "Sync with provider."
                    ),
                )
            # Unbound and pending: an abandoned attempt. Move it onto the plan being
            # bought now, so the row never disagrees with the checkout it belongs to.
            await subs_repo.repoint_pending(
                conn, subscription_id=row["id"], plan_id=body.plan_id
            )
        subscription_id = row["id"]

    try:
        session = await gateway.create_checkout(
            plan_id=body.plan_id,
            period=body.period,
            org_id=user.org_id,
            subscription_row_id=subscription_id,
            customer_email=user.email,
            customer_name=user.name,
            return_url=f"{config.site_url}/app/billing",
        )
    except GatewayUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc

    if session.gateway_subscription_id or session.gateway_customer_id:
        async with database.as_user(user.auth_user_id) as conn:
            await subs_repo.attach_gateway_ids(
                conn,
                subscription_id=subscription_id,
                gateway_subscription_id=session.gateway_subscription_id,
                gateway_customer_id=session.gateway_customer_id,
            )

    return CheckoutOut(checkout_url=session.url)


@router.post("/change-plan", response_model=SubscriptionOut)
async def change_plan(
    body: ChangePlanIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.BILLING_WRITE))],
) -> SubscriptionOut:
    """Move an existing subscription to another plan.

    The plan is *not* written here. The gateway charges the difference and then
    reports the change back as a webhook, and that webhook is the only thing that
    moves `organisations.plan_id` - so a change that fails at the gateway cannot
    leave the product believing it succeeded.
    """
    if body.plan_id not in _SELF_SERVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{billing.plan_name(body.plan_id)} cannot be switched to here.",
        )

    gateway = billing.provider()
    async with database.as_user(user.auth_user_id) as conn:
        row = await subs_repo.get_live_for_org(conn, user.org_id)

    if row is None or not row["gateway_subscription_id"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There is no active subscription to change. Start a checkout instead.",
        )

    # Already on it: do nothing, and say so.
    #
    # Every `change_plan` call is a billing event - the gateway raises a proration
    # payment for it, even a zero-amount one. Without this guard, clicking Switch a
    # few times before the page catches up produced four proration payments in
    # twenty-one seconds against one subscription. The interface hides the current
    # plan's own button, but that only helps once the page has refreshed.
    if row["plan_id"] == body.plan_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This organisation is already on {billing.plan_name(body.plan_id)}.",
        )

    # A subscription the gateway is not currently billing normally must not be
    # re-planned: it refuses a change on one scheduled for cancellation, and a
    # change on an `on_hold` subscription stacks a new charge on top of one that
    # already failed.
    if row["status"] != "active" or row["cancel_at_period_end"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This subscription is not billing normally, so its plan cannot be "
                "changed. Sort the payment out with the provider first."
            ),
        )

    try:
        await gateway.change_plan(
            gateway_subscription_id=row["gateway_subscription_id"],
            plan_id=body.plan_id,
            period=body.period,
        )
    except GatewayUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc

    return SubscriptionOut(
        status=row["status"],
        plan_id=row["plan_id"],
        current_period_end=(
            row["current_period_end"].isoformat() if row["current_period_end"] else None
        ),
        cancel_at_period_end=row["cancel_at_period_end"],
        last_error=row["last_error"],
    )


@router.post("/cancel", response_model=SubscriptionOut)
async def cancel_subscription(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.BILLING_WRITE))],
) -> SubscriptionOut:
    """Cancel at the end of the period already paid for.

    Never immediately: entitlements are meant to survive to the end of a paid
    period, which is the same rule `on_hold` and downgrade follow. The gateway
    confirms by webhook; this route does not write the status itself.
    """
    gateway = billing.provider()
    if not gateway.supports(PaymentCapability.CANCEL_AT_PERIOD_END):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="This payment processor cannot cancel at the end of a period.",
        )

    async with database.as_user(user.auth_user_id) as conn:
        row = await subs_repo.get_live_for_org(conn, user.org_id)

    if row is None or not row["gateway_subscription_id"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="There is no subscription to cancel."
        )

    try:
        await gateway.cancel(
            gateway_subscription_id=row["gateway_subscription_id"], at_period_end=True
        )
    except NotImplementedForProvider as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)
        ) from exc
    except GatewayUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail) from exc

    return SubscriptionOut(
        status=row["status"],
        plan_id=row["plan_id"],
        current_period_end=(
            row["current_period_end"].isoformat() if row["current_period_end"] else None
        ),
        cancel_at_period_end=True,
        last_error=row["last_error"],
    )


class SyncOut(BaseModel):
    applied: bool
    detail: str


@router.post("/sync", response_model=SyncOut)
async def sync_from_gateway(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.BILLING_WRITE))],
) -> SyncOut:
    """Pull the subscription state the gateway holds, and apply it.

    For when a webhook never arrived - an endpoint not yet configured, a tunnel
    down, a deploy inside the retry window. The customer has paid and the product
    does not know, and no amount of waiting fixes it.

    Owner-only, like every other write here. Idempotent: the synthesised event id
    is derived from the subscription and its state, so pressing it twice claims the
    same row and reports "already reconciled" instead of applying twice.

    This is a fallback, not the mechanism. The webhook stays the primary path
    because it is immediate; this exists because "primary" is not "guaranteed".
    """
    async with database.anonymous() as conn:
        outcome = await billing.reconcile(conn, user.org_id)
    return SyncOut(applied=outcome.applied, detail=outcome.reason)


@webhook_router.post("/dodo", status_code=status.HTTP_200_OK)
async def dodo_webhook(request: Request) -> dict[str, bool]:
    """The gateway's inbound callback. The only write path with no user session.

    **Raw bytes, not a parsed model.** The signature covers the exact bytes
    received, so re-serialising a Pydantic model computes a different digest and
    rejects every genuine delivery. This is the one route in the repo that takes
    `await request.body()`.

    **404 for every signature failure**, including an unset secret: a misconfigured
    deployment refuses deliveries rather than accepting anonymous writes, and a
    prober learns nothing about which of the three it hit. Same shape as
    `internal.py::_require_internal_key`.

    **200 for every post-verification refusal** - already seen, unknown
    subscription, illegal transition. Delivery is at-least-once with eight retries
    over ten hours, and a retry cannot fix any of those, so asking for one would
    just fill the log.
    """
    raw_body = await request.body()
    gateway = billing.provider()

    try:
        event = gateway.verify_webhook(raw_body=raw_body, headers=dict(request.headers))
    except (GatewayUnavailable, ValueError):
        # Narrow on purpose. `GatewayUnavailable` is every verification refusal;
        # `ValueError` covers a body that verified but is not JSON. A blind
        # `except Exception` here would turn a genuine bug - an AttributeError in
        # the adapter, say - into a 404 that reads as "bad signature", hiding the
        # one failure mode this route must not hide.
        #
        # The message is deliberately absent and the body deliberately unlogged:
        # an unverified payload is attacker-controlled input.
        log.warning("rejected an unverified payment webhook")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from None

    async with database.anonymous() as conn:
        first_delivery = await subs_repo.claim_event(
            conn,
            gateway=billing.GATEWAY_NAME,
            event_id=event.event_id,
            event_type=event.raw_type,
            payload=event.payload,
        )
        if not first_delivery:
            return {"ok": True}

        outcome = await billing.handle_event(conn, event)
        await subs_repo.mark_event_processed(
            conn,
            gateway=billing.GATEWAY_NAME,
            event_id=event.event_id,
            org_id=outcome.org_id,
            error=None if outcome.applied else outcome.reason,
        )

    if not outcome.applied:
        log.info("payment webhook was a no-op", extra={"reason": outcome.reason})
    return {"ok": True}


__all__ = ["router", "webhook_router"]
