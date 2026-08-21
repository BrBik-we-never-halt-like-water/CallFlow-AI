"""Billing orchestration: which gateway to use, and what a webhook means.

In `services/` rather than `domain/` because it does real I/O - it talks to a
payment gateway and a database. The *rules* it applies stay pure and live in
`domain/subscriptions.py` and `domain/plans.py`; this module only sequences them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from app.core.config import config
from app.database.repositories import ai_provider_credentials as ai_keys_repo
from app.database.repositories import organisations as org_repo
from app.database.repositories import platform as platform_repo
from app.database.repositories import subscriptions as subs_repo
from app.database.repositories import voice_agents as voice_agents_repo
from app.domain.entitlements import EntitlementUsage, EntitlementVerdict
from app.domain.plans import OVERRIDABLE, Entitlements, PlanId, entitlements_for
from app.domain.subscriptions import (
    InvalidTransition,
    SubscriptionStatus,
    check_transition,
    effective_plan_id,
    grants_via_subscription,
)
from app.integrations.payments.dodo import CREDIT_PACK, DodoGateway
from app.integrations.payments.protocol import (
    GatewayUnavailable,
    NotImplementedForProvider,
    PaymentCapability,
    PaymentProvider,
    PaymentsNotConfigured,
    RemoteSubscription,
    WebhookEvent,
    WebhookKind,
)
from app.integrations.payments.stub import StubPaymentProvider

log = logging.getLogger("callflow.billing")

GATEWAY_NAME = "dodo"


def provider() -> PaymentProvider:
    """The gateway this deployment actually has.

    Falls back to the stub when no key is configured, so a developer can exercise
    the whole flow offline. `config.payments_configured` is what the API reports to
    the interface, so Billing can say "no payment processor is connected on this
    deployment" rather than presenting a stub checkout as if it took money
    (CLAUDE.md §4 #9).
    """
    if not config.payments_configured:
        return StubPaymentProvider()
    try:
        return DodoGateway()
    except PaymentsNotConfigured:
        # Reachable only if `payments_configured` and the gateway disagree about
        # what "configured" means. Fall back rather than 500 a billing page.
        log.warning("payments looked configured but the gateway refused to construct")
        return StubPaymentProvider()


# --- what an organisation is entitled to, and what it has used ------------------


@dataclass(frozen=True)
class EffectivePlan:
    plan_id: str
    entitlements: Entitlements
    subscription: asyncpg.Record | None
    has_custom_limits: bool


def subscription_grants_credit(effective: EffectivePlan) -> bool:
    """Whether `effective.subscription` is why usage credit should arrive via
    `credit.grant_for_period` rather than the lazy, unsubscribed-org path
    (`credit.ensure_period_credit`).

    Deliberately checks the row's *status*, not merely whether a row exists.
    `effective.subscription` is `resolve_plan`'s "latest ever" record
    (`subs_repo.get_latest_for_org`), which stays populated forever once an
    organisation has subscribed once - including through `cancelled`,
    `expired`, `failed`, or an abandoned `pending` checkout. Treating any of
    those as "has a subscription" was the bug: an organisation whose
    subscription lapsed would be told, forever after, that a subscription
    covers its grants, while nothing ever grants against a lapsed one again.
    """
    if effective.subscription is None:
        return False
    return grants_via_subscription(SubscriptionStatus(effective.subscription["status"]))


async def resolve_plan(conn: asyncpg.Connection, org_id: UUID, stored_plan_id: str) -> EffectivePlan:
    """The plan an organisation actually has right now.

    `stored_plan_id` is `organisations.plan_id`, which the webhook keeps in step.
    It is re-derived here anyway because a period can lapse with no webhook to
    announce it - a subscription cancelled two months ago has a stale `plan_id`
    until something notices, and `effective_plan_id` noticing on read is cheaper
    and more reliable than a scheduled job.

    A missing subscription is normal: an organisation that never subscribed, and an
    enterprise account on an invoiced deal, both have none.
    """
    subscription = await subs_repo.get_latest_for_org(conn, org_id)

    resolved = stored_plan_id
    if subscription is not None:
        resolved = effective_plan_id(
            status=SubscriptionStatus(subscription["status"]),
            plan_id=subscription["plan_id"],
            current_period_end=subscription["current_period_end"],
            now=datetime.now(UTC),
        )

    # A negotiated per-organisation override wins over the plan's own numbers -
    # this is what the enterprise tier actually is. Read on every resolution rather
    # than cached: it is one indexed primary-key lookup, and a stale entitlement is
    # either a customer refused something they are paying for or given something
    # they are not.
    override = await _override_mapping(conn, org_id)
    return EffectivePlan(
        plan_id=resolved,
        entitlements=entitlements_for(resolved, override),
        subscription=subscription,
        has_custom_limits=bool(override),
    )


async def _override_mapping(
    conn: asyncpg.Connection, org_id: UUID
) -> dict[str, int | None] | None:
    """`org_entitlement_overrides` as the mapping `entitlements_for` expects.

    The translation is the interesting part, and it is why the table needs both
    nullable columns *and* an `unlimited` array. `entitlements_for` treats a key's
    **presence** as the override and its `None` as unlimited - so a null column has
    to mean "omit this key" (inherit the plan), and "unlimited" needs somewhere else
    to live. Collapsing the two would make an unset limit and an uncapped one
    indistinguishable, and an enterprise customer would silently inherit Growth's
    ceiling instead of the none they were sold.
    """
    row = await platform_repo.get_override_for_org(conn, org_id)
    if row is None:
        return None

    unlimited = set(row["unlimited"])
    mapping: dict[str, int | None] = {}
    for limit in OVERRIDABLE:
        if limit in unlimited:
            mapping[limit] = None
        elif row[limit] is not None:
            mapping[limit] = (
                float(row[limit]) if limit == "llm_spend_limit_usd" else row[limit]
            )
    return mapping or None


async def usage_for(conn: asyncpg.Connection, org_id: UUID, *, calls_today: int) -> EntitlementUsage:
    members, pending = await org_repo.seat_usage(conn, org_id)
    return EntitlementUsage(
        voice_agents=await voice_agents_repo.count_for_org(conn, org_id),
        seats=members + pending,
        organisations=await org_repo.count_owned_orgs_for_current_user(conn),
        ai_integrations=await ai_keys_repo.count_for_org(conn, org_id),
        calls_today=calls_today,
    )


# --- what a webhook does --------------------------------------------------------


@dataclass(frozen=True)
class WebhookOutcome:
    """Why a delivery ended the way it did.

    `applied` is False for every no-op - already seen, unknown subscription,
    illegal transition. The route answers 200 to all of them: delivery is
    at-least-once with retries, and none of those conditions is fixable by
    retrying (`docs/BILLING.md` §6).
    """

    applied: bool
    reason: str
    org_id: UUID | None = None


# Which status each event moves a subscription to. `SUBSCRIPTION_RENEWED` is
# absent on purpose - it extends the period without changing status, and putting
# it here would send it through `check_transition`, which rejects the
# self-transition it would look like.
_TARGET_STATUS: dict[WebhookKind, SubscriptionStatus] = {
    WebhookKind.SUBSCRIPTION_ACTIVE: SubscriptionStatus.ACTIVE,
    WebhookKind.SUBSCRIPTION_ON_HOLD: SubscriptionStatus.ON_HOLD,
    WebhookKind.SUBSCRIPTION_CANCELLED: SubscriptionStatus.CANCELLED,
    WebhookKind.SUBSCRIPTION_EXPIRED: SubscriptionStatus.EXPIRED,
    WebhookKind.SUBSCRIPTION_FAILED: SubscriptionStatus.FAILED,
}


async def _payment_settled(gateway_subscription_id: str | None) -> bool:
    """Has the money behind this subscription actually arrived?

    Asked of the gateway rather than inferred from the event, because a webhook
    announcing a plan change carries no payment status - and the gateway flips a
    subscription's product the moment a change is *initiated*. Trusting the event
    alone is how an upgrade gets granted while its charge is still processing.

    Fails closed: an unreadable or unsupported gateway is treated as unsettled, so
    an outage cannot become the reason an unpaid plan is granted.
    """
    if not gateway_subscription_id:
        return False
    remote = provider()
    if not remote.supports(PaymentCapability.RECONCILE):
        return False
    try:
        found = await remote.find_subscriptions_by_id(
            gateway_subscription_id=gateway_subscription_id
        )
    except (GatewayUnavailable, NotImplementedForProvider):
        return False
    return found is not None and not found.has_unsettled_payment


async def _grant_period_credit(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    plan_id: str,
    subscription_id: str,
    period_end: datetime | None,
    expire_remainder: bool,
) -> None:
    """Give this organisation its plan's usage credit for one period.

    Failures are logged and swallowed on purpose. This runs inside webhook
    handling, and a webhook that raises is a webhook the gateway retries for ten
    hours - so a credit grant that cannot complete must not take down the
    *subscription* update it rides along with. The subscription is the thing the
    customer paid for; the credit is recoverable by the next renewal or by hand,
    and `POST /billing/sync` exists for exactly this class of drift.

    Imported here rather than at module scope: `services.credit` imports the
    entitlement ladder, and a top-level import would make two service modules
    depend on each other's import order for no benefit.
    """
    from app.services import credit as credit_service

    try:
        effective = await resolve_plan(conn, org_id, plan_id)
        await credit_service.grant_for_period(
            conn,
            org_id=org_id,
            entitlements=effective.entitlements,
            period_key=credit_service.period_key_for(subscription_id, period_end),
            expire_remainder=expire_remainder,
        )
    except Exception:
        log.exception("could not grant usage credit to org %s", org_id)


async def _handle_topup_payment(conn: asyncpg.Connection, event: WebhookEvent) -> WebhookOutcome:
    """A one-time credit-pack purchase, resolved without a subscription row.

    `record_payment` already accepts `subscription_id=None` - it never needed a
    subscription to record a payment, `handle_event`'s early return on a
    missing `row` was the only thing standing in the way.
    """
    org_id = event.org_id
    if org_id is None:
        return WebhookOutcome(False, "Top-up payment carries no org_id.", None)

    recorded = False
    if event.gateway_payment_id and event.amount_minor is not None and event.currency:
        recorded = await subs_repo.record_payment(
            conn,
            org_id=org_id,
            subscription_id=None,
            gateway=GATEWAY_NAME,
            gateway_payment_id=event.gateway_payment_id,
            amount_minor=event.amount_minor,
            currency=event.currency,
            status="succeeded" if event.kind is WebhookKind.PAYMENT_SUCCEEDED else "failed",
            description=event.raw_type,
            paid_at=None,
        )

    if (
        event.kind is WebhookKind.PAYMENT_SUCCEEDED
        and event.gateway_payment_id
        and event.amount_minor
    ):
        from app.services import credit as credit_service

        try:
            await credit_service.grant_for_topup(
                conn,
                org_id=org_id,
                amount_paise=event.amount_minor,
                gateway_payment_id=event.gateway_payment_id,
            )
        except Exception:
            log.exception("could not grant top-up credit to org %s", org_id)

    return WebhookOutcome(
        recorded, "Top-up recorded." if recorded else "Already recorded.", org_id
    )


async def handle_event(conn: asyncpg.Connection, event: WebhookEvent) -> WebhookOutcome:
    """Apply one verified webhook. Runs on `database.anonymous()`.

    The caller has already verified the signature; this decides what it means and
    writes through the definer functions. Every branch that cannot proceed returns
    rather than raising, because the honest answer to the gateway is 200.
    """
    row = await subs_repo.lookup_for_webhook(
        conn,
        gateway=GATEWAY_NAME,
        gateway_subscription_id=event.gateway_subscription_id,
        subscription_row_id=event.subscription_row_id,
    )
    if row is None:
        # A credit-pack top-up is not a subscription and never gets an
        # `org_subscriptions` row, so it always misses the lookup above - this
        # is the one place that resolves it anyway, straight from checkout
        # metadata rather than a subscription.
        if (
            event.kind in {WebhookKind.PAYMENT_SUCCEEDED, WebhookKind.PAYMENT_FAILED}
            and event.plan_id == CREDIT_PACK
            and event.org_id is not None
        ):
            return await _handle_topup_payment(conn, event)
        return WebhookOutcome(False, f"No subscription matches {event.raw_type}.", event.org_id)

    org_id: UUID = row["org_id"]
    subscription_id: UUID = row["subscription_id"]
    current = SubscriptionStatus(row["status"])

    # The ledger is written before any status change and independently of it: a
    # payment can arrive for a subscription whose status is not moving, and a
    # receipt must survive even if the transition below turns out to be illegal.
    if event.gateway_payment_id and event.amount_minor is not None and event.currency:
        await subs_repo.record_payment(
            conn,
            org_id=org_id,
            subscription_id=subscription_id,
            gateway=GATEWAY_NAME,
            gateway_payment_id=event.gateway_payment_id,
            amount_minor=event.amount_minor,
            currency=event.currency,
            status="succeeded" if event.kind is WebhookKind.PAYMENT_SUCCEEDED else "failed",
            description=event.raw_type,
            # The gateway does not send a settlement time on every event shape, so
            # the definer function defaults it to now() rather than storing null and
            # leaving the payments list unsortable.
            paid_at=None,
        )

    if event.kind is WebhookKind.SUBSCRIPTION_RENEWED:
        extended = await subs_repo.extend_period(
            conn,
            subscription_id=subscription_id,
            current_period_end=event.current_period_end,
            effective_plan_id=row["plan_id"],
        )
        if extended:
            # A new period means new usage credit, and the old period's remainder
            # is written off first because plan credit does not roll over. Keyed
            # on the period rather than the delivery, so a redelivered renewal
            # grants once. Only on `extended`: if the guarded update did not
            # match, another delivery already handled this period.
            await _grant_period_credit(
                conn,
                org_id=org_id,
                plan_id=row["plan_id"],
                subscription_id=event.gateway_subscription_id
                or row["gateway_subscription_id"]
                or str(subscription_id),
                period_end=event.current_period_end,
                expire_remainder=True,
            )
        return WebhookOutcome(extended, "Period extended." if extended else "Not active.", org_id)

    if event.kind in {WebhookKind.PAYMENT_SUCCEEDED, WebhookKind.PAYMENT_FAILED}:
        return WebhookOutcome(True, "Payment recorded.", org_id)

    if event.kind is WebhookKind.SUBSCRIPTION_UPDATED:
        # `subscription.updated`/`.plan_changed` never move status on their
        # own - a plan change or a cancel-at-period-end both edit a field on an
        # already-active (or already-on-hold) row. Setting `target = current`
        # routes straight into the "same status, different details" branch
        # below rather than through `_TARGET_STATUS`, which has no entry for
        # this kind on purpose: there is no fixed status to look up.
        target = current
    else:
        target = _TARGET_STATUS.get(event.kind)
        if target is None:
            # Anything this version does not act on. Recorded and
            # acknowledged, never rejected: a gateway adding an event type
            # must not start failing deliveries.
            return WebhookOutcome(False, f"No action for {event.raw_type}.", org_id)

    if target is current:
        # Same status, different details - a plan change the gateway has confirmed,
        # or a reconcile finding a subscription we already believed active. Not a
        # transition: `check_transition` rejects self-transitions on purpose, and
        # routing this through it would park every plan-change confirmation as
        # "illegal" while the customer was already being billed for the new plan.
        plan_for_subscription = event.plan_id or row["plan_id"]

        # A plan change is a grant, so it waits for the money. An update that only
        # moves the period or the cancellation flag is not, and goes straight
        # through - otherwise a renewal would stall behind its own charge.
        if plan_for_subscription != row["plan_id"] and not await _payment_settled(
            event.gateway_subscription_id or row["gateway_subscription_id"]
        ):
            return WebhookOutcome(
                False,
                "The payment for this plan has not completed yet.",
                org_id,
            )

        updated = await subs_repo.apply_event(
            conn,
            subscription_id=subscription_id,
            expected_status=current.value,
            new_status=current.value,
            effective_plan_id=effective_plan_id(
                status=current,
                plan_id=plan_for_subscription,
                current_period_end=event.current_period_end or row["current_period_end"],
                now=datetime.now(UTC),
            ),
            subscription_plan_id=plan_for_subscription,
            current_period_end=event.current_period_end,
            cancel_at_period_end=event.cancel_at_period_end,
            gateway_subscription_id=event.gateway_subscription_id,
            last_error=event.detail,
        )
        return WebhookOutcome(
            updated,
            f"Updated in place ({plan_for_subscription})." if updated else "Nothing to update.",
            org_id,
        )

    try:
        check_transition(current, target)
    except InvalidTransition as exc:
        # Parked, not raised. An out-of-order delivery is normal traffic.
        await subs_repo.apply_event(
            conn,
            subscription_id=subscription_id,
            expected_status=current.value,
            new_status=current.value,
            effective_plan_id=row["plan_id"],
            last_error=str(exc),
        )
        return WebhookOutcome(False, str(exc), org_id)

    plan_for_subscription = event.plan_id or row["plan_id"]

    # Same rule on the transition path: activating a subscription is the biggest
    # grant there is, so it does not happen on an unsettled charge. Moves that
    # *reduce* entitlements - cancelled, expired, failed - are applied regardless.
    if target in {SubscriptionStatus.ACTIVE, SubscriptionStatus.ON_HOLD} and not await (
        _payment_settled(event.gateway_subscription_id or row["gateway_subscription_id"])
    ):
        return WebhookOutcome(
            False, "The payment for this subscription has not completed yet.", org_id
        )

    resolved = effective_plan_id(
        status=target,
        plan_id=plan_for_subscription,
        current_period_end=event.current_period_end or row["current_period_end"],
        now=datetime.now(UTC),
    )

    applied = await subs_repo.apply_event(
        conn,
        subscription_id=subscription_id,
        expected_status=current.value,
        new_status=target.value,
        effective_plan_id=resolved,
        subscription_plan_id=plan_for_subscription,
        current_period_end=event.current_period_end,
        cancel_at_period_end=event.cancel_at_period_end,
        gateway_subscription_id=event.gateway_subscription_id,
        last_error=event.detail,
    )
    if not applied:
        return WebhookOutcome(False, "Another delivery applied this first.", org_id)

    if target is SubscriptionStatus.ACTIVE:
        # Two different moves land here, and only one is a first grant.
        # First activation (`pending -> active`): no remainder to expire -
        # whatever a Free organisation had left is theirs, and writing it off
        # on upgrade would take credit away from someone who just paid.
        # Recovery (`on_hold -> active`): the *opposite* rule applies, same as
        # a renewal - the on-hold period's balance does not roll over into the
        # new one just because the card that failed got fixed.
        #
        # Guarded by `applied`, so only the delivery that actually moved the
        # subscription grants - and by the period key inside, so two deliveries
        # that both somehow got here still grant once.
        recovering_from_hold = current is SubscriptionStatus.ON_HOLD
        if recovering_from_hold and event.current_period_end is None:
            # `period_key_for` would otherwise fall back to `row["current_period_end"]`
            # - the pre-transition value, which may already be the dedupe key an
            # earlier grant used. `_grant_period_credit` swallows that as a no-op
            # grant rather than raising, so this is the only place it becomes
            # visible: a distinct, searchable warning instead of a generic
            # "could not grant" a few lines later.
            log.warning(
                "on_hold recovery for org %s arrived with no current_period_end - "
                "the renewal grant may key on a stale period and skip itself",
                org_id,
            )
        await _grant_period_credit(
            conn,
            org_id=org_id,
            plan_id=resolved,
            subscription_id=event.gateway_subscription_id
            or row["gateway_subscription_id"]
            or str(subscription_id),
            period_end=event.current_period_end or row["current_period_end"],
            expire_remainder=recovering_from_hold,
        )

    log.info(
        "subscription moved",
        extra={"org_id": str(org_id), "status": target.value, "plan_id": resolved},
    )
    return WebhookOutcome(True, f"Moved to {target.value}.", org_id)


# --- the route-level gate -------------------------------------------------------

# Statuses that hand an organisation a paid plan. `ON_HOLD` is here deliberately:
# under this product's own rule it keeps the plan until the period ends, so an
# unpaid `on_hold` is as much of a giveaway as an unpaid `active`.
GRANTING_STATUSES = frozenset(
    {WebhookKind.SUBSCRIPTION_ACTIVE, WebhookKind.SUBSCRIPTION_ON_HOLD}
)


def withholds_grant(status: WebhookKind, *, has_unsettled_payment: bool) -> bool:
    """Should this state be refused because the money has not arrived?

    Pure, and extracted so a test can exercise the real rule rather than its own
    copy of it. The gate points one way only: cancelled, expired and failed all
    *reduce* what an organisation has, and withholding those because a payment is in
    flight would be the same mistake facing the other direction - leaving somebody
    on a plan the gateway has already ended.
    """
    return has_unsettled_payment and status in GRANTING_STATUSES



async def reconcile(conn: asyncpg.Connection, org_id: UUID) -> WebhookOutcome:
    """Ask the gateway what it holds for this organisation, and apply it.

    A webhook is a *notification* about money; the gateway is the money. Deliveries
    get missed - an endpoint not configured yet, a tunnel down, a deploy during the
    retry window - and when one is, a customer has paid and the product does not
    know. Reconciliation is how that stops being a support ticket.

    Runs the result through `handle_event`, deliberately: the same transition
    checks, the same guarded write, the same `effective_plan_id` rule. A second
    code path that applied a subscription its own way is how the two drift, and
    this one would drift in the direction of granting plans nobody paid for.
    """
    gateway = provider()
    if not gateway.supports(PaymentCapability.RECONCILE):
        return WebhookOutcome(False, "This payment provider cannot be queried.", org_id)

    try:
        remote = await gateway.find_subscriptions(org_id=org_id)
    except GatewayUnavailable as exc:
        return WebhookOutcome(False, exc.detail, org_id)

    if not remote:
        return WebhookOutcome(False, "The payment provider holds no subscription for you.", org_id)

    # Newest first from the adapter, and a live one beats a terminal one: an
    # organisation that failed a checkout and then succeeded must land on the
    # success, whichever order the gateway lists them in.
    # Live before terminal, and within that the adapter's order (newest first) is
    # preserved because `sorted` is stable. So `ranked[0]` is the newest live
    # subscription when there is one, and `ranked[1:]` are the duplicates.
    def rank(s: RemoteSubscription) -> tuple[bool, bool]:
        live = s.status in {
            WebhookKind.SUBSCRIPTION_ACTIVE,
            WebhookKind.SUBSCRIPTION_ON_HOLD,
        }
        # A cancelled-at-period-end subscription still reports `active` until the
        # date passes. Preferring it over one that is not winding down would put the
        # organisation on a plan that is about to disappear.
        return (live and not s.cancel_at_period_end, live)

    # Stable sort, so the adapter's newest-first order survives within each rank:
    # `ranked[0]` is the newest subscription that is live and not winding down.
    ranked = sorted(remote, key=rank, reverse=True)
    chosen = ranked[0]

    if chosen.status is WebhookKind.UNKNOWN:
        return WebhookOutcome(False, "The provider reports a state we do not handle.", org_id)

    # More than one live subscription means the customer is being billed twice.
    #
    # No local guard can prevent it: a hosted checkout session stays valid after the
    # page is abandoned, so two tabs - or one abandoned attempt finished later - both
    # settle at the gateway, and the gateway is right to take both. Cancelling the
    # extras is therefore not cleanup after a bug, it is the only place this can be
    # handled at all.
    #
    # The newest is kept, on the reasoning that it is the plan the customer most
    # recently chose. Cancelled at period end, never immediately: they paid for it,
    # so it runs out rather than being cut off, which is the same rule the rest of
    # this module follows.
    extras = [
        s
        for s in ranked[1:]
        if s.status in {WebhookKind.SUBSCRIPTION_ACTIVE, WebhookKind.SUBSCRIPTION_ON_HOLD}
        # Already winding down. A cancelled-at-period-end subscription keeps
        # reporting `active` until the date passes, so without this every sync
        # would re-cancel the same one for as long as the period runs.
        and not s.cancel_at_period_end
    ]
    for extra in extras:
        try:
            await gateway.cancel(
                gateway_subscription_id=extra.gateway_subscription_id, at_period_end=True
            )
            log.warning(
                "cancelled a duplicate subscription",
                extra={"org_id": str(org_id), "kept": chosen.gateway_subscription_id},
            )
        except (GatewayUnavailable, NotImplementedForProvider) as exc:
            # Reported, not raised: failing the whole reconcile would leave the
            # organisation on no plan at all while still paying for two.
            log.error("could not cancel a duplicate subscription: %s", exc)

    # **Nothing is granted on an unsettled payment.**
    #
    # The gateway flips a subscription's product the moment a plan change is
    # initiated, and the charge behind it may still be processing or may fail. Left
    # alone, entitlements follow the product - so an organisation lands on the
    # higher plan before the money arrives, and because a paid plan survives to
    # `current_period_end` even on `on_hold`, a *failed* top-up would leave them
    # there for the rest of the period. That is a plan given away.
    #
    # A status change in the *other* direction is still applied: cancelled, expired
    # and failed all reduce what an organisation has, and withholding those because
    # a payment is in flight would be the same mistake pointing the wrong way.
    if withholds_grant(chosen.status, has_unsettled_payment=chosen.has_unsettled_payment):
        return WebhookOutcome(
            False,
            "The payment for this plan has not completed yet. It applies once the "
            "provider confirms it.",
            org_id,
        )

    # Synthesised rather than received. The id is derived from the subscription and
    # *everything about it we would act on*, so a repeated reconcile with nothing
    # changed claims the same row and no-ops like a redelivered webhook, while any
    # real change produces a new id and applies.
    #
    # Status alone is not enough, and that cost a debugging session: a plan change
    # leaves the status at `active`, so keying on `subscription:status` made the
    # first reconcile of a subscription the *only* one that could ever apply. A
    # customer switching plans saw the gateway accept it and the product do nothing,
    # for as long as the status held.
    fingerprint = ":".join(
        [
            chosen.gateway_subscription_id,
            chosen.status.value,
            chosen.plan_id or "-",
            chosen.current_period_end.isoformat() if chosen.current_period_end else "-",
            "cancelling" if chosen.cancel_at_period_end else "live",
        ]
    )
    event = WebhookEvent(
        event_id=f"reconcile:{fingerprint}",
        kind=chosen.status,
        raw_type=f"reconcile.{chosen.status.value}",
        gateway_subscription_id=chosen.gateway_subscription_id,
        org_id=chosen.org_id or org_id,
        subscription_row_id=chosen.subscription_row_id,
        plan_id=chosen.plan_id,
        current_period_end=chosen.current_period_end,
        cancel_at_period_end=chosen.cancel_at_period_end,
    )

    claimed = await subs_repo.claim_event(
        conn,
        gateway=GATEWAY_NAME,
        event_id=event.event_id,
        event_type=event.raw_type,
        payload={"source": "reconcile", "subscription": chosen.gateway_subscription_id},
    )
    if not claimed:
        return WebhookOutcome(False, "Already reconciled - nothing changed.", org_id)

    outcome = await handle_event(conn, event)
    await subs_repo.mark_event_processed(
        conn,
        gateway=GATEWAY_NAME,
        event_id=event.event_id,
        org_id=outcome.org_id,
        error=None if outcome.applied else outcome.reason,
    )
    return outcome


def refuse(verdict: EntitlementVerdict) -> None:
    """Turn a refused entitlement into 402 Payment Required.

    402 rather than 403 so the interface can tell "your plan doesn't include this"
    from "your role doesn't allow this" and offer an upgrade instead of a dead end
    (`docs/BILLING.md` §2).

    The SQL guards below these routes raise `CheckViolationError`, which FastAPI
    would surface as a 500 - so this check is not redundant with them. It exists to
    turn the same refusal into a sentence a person can act on; the trigger exists
    so the limit still holds when nobody came through the route at all.
    """
    if not verdict.allowed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=verdict.reason
        )


def plan_name(plan_id: str) -> str:
    try:
        return PlanId(plan_id).value.capitalize()
    except ValueError:
        return plan_id
