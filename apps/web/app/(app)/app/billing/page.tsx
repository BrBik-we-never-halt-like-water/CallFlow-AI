'use client';

import { useCallback, useState } from 'react';
import { EntitlementMeter } from '@/components/app/entitlement-meter';
import { PlanCard } from '@/components/app/plan-card';
import { SessionGate } from '@/components/app/session-gate';
import {
  NotWiredNotice,
  SettingsSection,
} from '@/components/app/settings-section';
import { Button } from '@/components/ui/button';
import { Meter } from '@/components/ui/meter';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import {
  api,
  type BillingOverview,
  type Credit,
  type LedgerEntry,
  type MyCredits,
  type PaymentRecord,
  type PlanOption,
} from '@/lib/api';
import { formatMinorUnits, formatNumber } from '@/lib/format';
import { bumpEntitlementsVersion } from '@/lib/hooks/use-entitlements-version';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession, type SessionProfile } from '@/lib/hooks/use-session';

export default function BillingPage() {
  const session = useSession();
  return (
    <SessionGate session={session}>
      {(profile) => <BillingContent profile={profile} />}
    </SessionGate>
  );
}

/**
 * Two genuinely different pages behind one sidebar entry.
 *
 * An owner or admin sees the organisation's plan and can change it; an operator
 * or viewer sees only their own slice of the daily budget, because
 * `billing:read` is what the org's plan and payment history sit behind. The
 * heading changes with the branch rather than promising "Billing" and then
 * showing one meter - the page says what it actually is.
 */
function BillingContent({ profile }: { profile: SessionProfile }) {
  const canRead = profile.permissions.includes('billing:read');
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="text-small font-bold text-text-mute">
          {canRead ? 'Billing' : 'Credits'}
        </p>
        <h1 className="font-display text-h2 text-text">
          {canRead ? 'What this plan buys you' : 'Your share of today'}
        </h1>
        <p className="measure text-small text-text-dim">
          {canRead
            ? 'The plan, the limits every run is checked against, and what has been paid.'
            : "Your own share of the organisation's usage credit."}
        </p>
      </div>

      {canRead ? <OrgBilling profile={profile} /> : <MyCreditsPanel />}
    </div>
  );
}

/* --------------------------------------------------------------------------
   Operators and viewers: their own share of the organisation's usage credit.
   -------------------------------------------------------------------------- */

function MyCreditsPanel() {
  const [myCredits, setMyCredits] = useState<MyCredits | null>(null);

  useOrgScopedEffect(() => {
    api
      .myCredits()
      .then(setMyCredits)
      .catch(() => setMyCredits(null));
  }, []);

  return (
    // Capped, unlike the owner view below: one meter stretched across a wide
    // screen reads as a page that failed to load the rest of itself.
    <div className="flex max-w-3xl flex-col gap-4">
      <SettingsSection
        title="My credits"
        description="Your own share of this organisation's usage credit - money, spent by the second."
      >
        {myCredits === null ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-2 w-full" />
          </div>
        ) : myCredits.credit_cap_paise === null ? (
          <NotWiredNotice>
            An owner or admin hasn&apos;t set your usage-credit share yet -
            until they do, you draw from the organisation&apos;s shared balance
            like everyone else.
          </NotWiredNotice>
        ) : (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-small text-text-dim">Spent this month</span>
              <span className="font-mono text-small tabular-nums text-text">
                {formatMinorUnits(myCredits.credit_spent_paise, 'INR')}
                <span className="text-text-mute">
                  {' / '}
                  {formatMinorUnits(myCredits.credit_cap_paise, 'INR')}
                </span>
              </span>
            </div>
            <Meter
              value={myCredits.credit_spent_paise}
              max={myCredits.credit_cap_paise}
              label="Usage credit spent this month"
            />
            {myCredits.credit_spent_paise >= myCredits.credit_cap_paise ? (
              <p className="text-small text-text-mute">
                Ask an owner or admin to raise your share in Organisation → Team.
              </p>
            ) : null}
          </div>
        )}
      </SettingsSection>
    </div>
  );
}

/* --------------------------------------------------------------------------
   Admins and owners: the plan, what it allows, and how to change it.
   -------------------------------------------------------------------------- */

function OrgBilling({ profile }: { profile: SessionProfile }) {
  const toast = useToast();
  const canPurchase = profile.permissions.includes('billing:write');

  const [overview, setOverview] = useState<BillingOverview | null>(null);
  const [plans, setPlans] = useState<PlanOption[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [busyPlan, setBusyPlan] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useOrgScopedEffect(() => {
    let cancelled = false;
    setFailed(false);
    Promise.all([api.billingOverview(), api.billingPlans()])
      .then(([nextOverview, nextPlans]) => {
        if (cancelled) return;
        setOverview(nextOverview);
        setPlans(nextPlans);
      })
      .catch(() => {
        // An explicit failed state, not an indefinite skeleton. A loader that
        // never resolves tells someone the page is still working when it has
        // already given up - which is exactly what this page used to do when
        // the safety fetch failed.
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [nonce]);

  // A live subscription means the gateway wants a plan *change*, not a second
  // checkout - starting one would open a second subscription and bill twice,
  // which is what the API refuses with a 409. `cancelled` is deliberately not
  // "live": once cancelled you buy again rather than switch.
  const liveSubscription =
    overview?.subscription &&
    ['pending', 'active', 'on_hold'].includes(overview.subscription.status)
      ? overview.subscription
      : null;

  // Cancelled at period end: still live, but the gateway refuses a plan change on
  // it outright. Treated as "no subscription" for routing, so the button starts a
  // fresh checkout - which is the action that actually works.
  const windingDown = liveSubscription?.cancel_at_period_end === true;

  // Only an `active` subscription can have its plan changed. `pending` counts as
  // live - it holds the one-live-row-per-org slot - but it means a checkout was
  // started and never finished, so there is nothing at the gateway to re-plan. The
  // API says so with a 409; offering Switch anyway just walks someone into it.
  const changeable =
    liveSubscription?.status === 'active' && !windingDown;

  const choose = useCallback(
    async (plan: PlanOption) => {
      setBusyPlan(plan.plan_id);
      try {
        if (changeable) {
          await api.changePlan(plan.plan_id, 'monthly');
          // Then ask the gateway what it now holds, rather than waiting on a
          // webhook. The change is applied at the gateway the moment `changePlan`
          // returns, so this usually confirms straight away - and where it doesn't,
          // the wording below stays true instead of claiming a plan that has not
          // moved. Leaving it to the webhook alone meant a successful change looked
          // like nothing happening at all.
          const { applied } = await api.syncBilling().catch(() => ({ applied: false }));
          toast({
            tone: 'success',
            title: applied ? `Now on ${plan.name}` : `Switching to ${plan.name}`,
            body: applied
              ? 'The provider has confirmed the change.'
              : 'The provider is processing the change. Use Sync with provider once it settles.',
          });
          setNonce((n) => n + 1);
          bumpEntitlementsVersion();
          return;
        }
        const { checkout_url } = await api.startCheckout(
          plan.plan_id,
          'monthly',
          // Generated per click, not per render: a re-render must not open a
          // second subscription at the gateway.
          crypto.randomUUID(),
        );
        window.location.href = checkout_url;
      } catch (error) {
        toast({
          tone: 'error',
          title: changeable ? 'Could not change plan' : 'Could not start checkout',
          body: error instanceof Error ? error.message : undefined,
        });
      } finally {
        setBusyPlan(null);
      }
    },
    [changeable, toast],
  );

  const sync = useCallback(async () => {
    setBusyPlan('sync');
    try {
      const { applied, detail } = await api.syncBilling();
      toast({
        tone: applied ? 'success' : 'info',
        title: applied ? 'Updated from the provider' : 'Nothing to update',
        body: detail,
      });
      if (applied) {
        setNonce((n) => n + 1);
        bumpEntitlementsVersion();
      }
    } catch (error) {
      toast({
        tone: 'error',
        title: 'Could not reach the payment provider',
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setBusyPlan(null);
    }
  }, [toast]);

  const cancel = useCallback(async () => {
    setBusyPlan('cancel');
    try {
      await api.cancelSubscription();
      toast({
        tone: 'success',
        title: 'Subscription cancelled',
        body: 'Your plan runs to the end of the period you have paid for.',
      });
      setNonce((n) => n + 1);
      bumpEntitlementsVersion();
    } catch (error) {
      toast({
        tone: 'error',
        title: 'Could not cancel',
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setBusyPlan(null);
    }
  }, [toast]);

  if (failed) {
    return (
      <SettingsSection title="Plan" description="What this organisation is on.">
        <div className="flex flex-col items-start gap-3">
          <p className="text-body text-text-dim">
            Billing didn&apos;t load. Nothing has changed.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setNonce((n) => n + 1)}
          >
            Try again
          </Button>
        </div>
      </SettingsSection>
    );
  }

  if (!overview || !plans) {
    return (
      <div className="flex flex-col gap-4">
        <SettingsSection
          title="Plan"
          description="What this organisation is on."
        >
          <div className="flex flex-col gap-2">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-2 w-full" />
          </div>
        </SettingsSection>
      </div>
    );
  }

  const { entitlements: limits, usage, subscription } = overview;

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Plan"
        description="What this organisation is on, and what it allows."
      >
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="text-h3 font-medium text-text">
              {overview.plan_name}
            </span>
            {overview.has_custom_limits ? (
              <span className="text-small text-text-dim">
                Limits agreed for this organisation.
              </span>
            ) : null}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <EntitlementMeter
              label="Voice agents"
              used={usage.voice_agents}
              limit={limits.max_voice_agents}
              atLimitHint="Upgrade to add another agent."
            />
            <EntitlementMeter
              label="Seats"
              used={usage.seats}
              limit={limits.max_seats}
              atLimitHint="Pending invitations count as seats."
            />
            <EntitlementMeter
              label="Organisations"
              used={usage.organisations}
              limit={limits.max_organisations}
              atLimitHint="Counted across the workspaces you own."
            />
            <EntitlementMeter
              label="Model providers"
              used={usage.ai_integrations}
              limit={limits.max_ai_integrations}
              atLimitHint="Keys already connected keep working."
            />
          </div>

          <SubscriptionNote
            subscription={subscription}
            canPurchase={canPurchase}
            busy={busyPlan === 'cancel'}
            onCancel={cancel}
          />
        </div>
      </SettingsSection>

      <CreditSection
        credit={overview.credit}
        canTopUp={
          canPurchase && overview.payments_configured && overview.credit_pack_configured
        }
      />

      <SettingsSection
        title="Calls today"
        description={
          limits.daily_call_budget !== null &&
          overview.effective_daily_call_budget < limits.daily_call_budget
            ? `A safety ceiling, not a plan allowance - it exists to bound a runaway, and usage credit above is what actually limits how much you can call. This organisation is set to ${overview.effective_daily_call_budget}, below the ${limits.daily_call_budget} the deployment permits.`
            : 'A safety ceiling over a rolling 24 hours, identical on every plan - it exists to bound a runaway, not to meter you. Usage credit above is the real limit. Set a lower one in Settings → Safety.'
        }
      >
        <EntitlementMeter
          label="Calls used today"
          used={usage.calls_today}
          // The effective ceiling, not the plan allowance. Settings → Safety and
          // the deployment default can both be lower, and the lower one is what
          // runs actually stop at.
          limit={overview.effective_daily_call_budget}
          // "a rolling 24 hours", not "until tomorrow": the org-wide limiter prunes
          // its bucket to the last 86,400 seconds (`rate_limit.py`), so capacity
          // comes back gradually as old calls age out rather than all at once at
          // midnight. The copy here used to say "Resets daily", which is the one
          // thing it does not do.
          atLimitHint="Capacity returns as calls from the last 24 hours age out."
        />
      </SettingsSection>

      <SettingsSection
        title="Plans"
        description="Every plan, and what each one includes."
        footer={
          canPurchase && overview.payments_configured ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-small text-text-mute">
                Paid but still showing the old plan? The provider confirms by
                webhook, and that can be delayed or missed.
              </p>
              <Button
                variant="secondary"
                size="sm"
                loading={busyPlan === 'sync'}
                onClick={sync}
              >
                Sync with provider
              </Button>
            </div>
          ) : null
        }
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {plans.map((plan) => (
            <PlanCard
              key={plan.plan_id}
              plan={plan}
              paymentsConfigured={overview.payments_configured}
              canPurchase={canPurchase}
              hasSubscription={liveSubscription !== null}
              windingDown={windingDown}
              busy={busyPlan === plan.plan_id}
              onChoose={choose}
            />
          ))}
        </div>
      </SettingsSection>

      {overview.payments.length > 0 ? (
        <SettingsSection
          title="Payments"
          description="Every charge, with the tax invoice the payment provider issued for it."
        >
          <ul className="flex flex-col gap-2">
            {overview.payments.map((payment) => (
              <li
                key={payment.id}
                className="flex items-baseline justify-between gap-3 text-small"
              >
                <span className="text-text-dim">
                  {payment.paid_at
                    ? new Date(payment.paid_at).toLocaleDateString()
                    : '-'}
                </span>
                <span className="font-mono tabular-nums text-text">
                  {formatMinorUnits(payment.amount_minor, payment.currency)}
                </span>
                <span className="text-text-mute">{payment.status}</span>
                <ReceiptLink payment={payment} />
              </li>
            ))}
          </ul>
        </SettingsSection>
      ) : null}

      {!overview.payments_configured ? (
        <NotWiredNotice>
          There&apos;s no payment processor connected on this deployment, so
          plans can&apos;t be bought here yet. The plan, the limits and the usage
          above are all real and enforced - every number is one that runs
          actually stop at.
        </NotWiredNotice>
      ) : null}
    </div>
  );
}

function SubscriptionNote({
  subscription,
  canPurchase,
  busy,
  onCancel,
}: {
  subscription: BillingOverview['subscription'];
  canPurchase: boolean;
  busy: boolean;
  onCancel: () => void;
}) {
  // No row is a normal state, not an error: an organisation that never
  // subscribed, and an enterprise account on an invoiced deal, both have none.
  if (!subscription) return null;

  if (subscription.status === 'pending') {
    // An unfinished checkout. Saying so beats leaving the panel blank while the
    // plan cards offer an upgrade that looks like it should already have happened.
    return (
      <p className="text-small text-text-dim">
        A checkout for {subscription.plan_id} was started and hasn&apos;t completed.
        Pick a plan below to start again, or use Sync with provider if you have
        already paid.
      </p>
    );
  }

  const renews = subscription.current_period_end
    ? new Date(subscription.current_period_end).toLocaleDateString()
    : null;

  return (
    <div className="flex flex-col gap-2">
      {subscription.status === 'on_hold' ? (
        <p className="text-small text-text-dim">
          A renewal payment didn&apos;t go through. Your plan keeps working
          until {renews ?? 'the end of this period'} - update your payment
          method with the provider before then.
        </p>
      ) : subscription.cancel_at_period_end ? (
        <p className="text-small text-text-dim">
          Cancelled. This plan runs until {renews ?? 'the end of the period'},
          then the organisation moves to Free.
        </p>
      ) : renews ? (
        <p className="text-small text-text-mute">Renews on {renews}.</p>
      ) : null}

      {canPurchase &&
      !subscription.cancel_at_period_end &&
      subscription.status !== 'cancelled' ? (
        <div>
          <Button variant="ghost" size="sm" loading={busy} onClick={onCancel}>
            Cancel subscription
          </Button>
        </div>
      ) : null}
    </div>
  );
}


/**
 * The invoice for one payment, fetched rather than linked.
 *
 * A plain `<a href>` cannot carry the session's bearer token, so the endpoint
 * would 401 - which is why this is a button that fetches a blob and opens it.
 *
 * Only rendered when the API says a receipt exists: a settled payment on a gateway
 * that issues invoices. Showing "Receipt" on a failed charge and letting it 404
 * would be a link that lies (CLAUDE.md §4 #9), and the gap is real - a `failed`
 * row has no invoice to issue.
 */
function ReceiptLink({ payment }: { payment: PaymentRecord }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  if (!payment.has_receipt) {
    return <span className="text-text-mute">-</span>;
  }

  async function open() {
    setBusy(true);
    try {
      const blob = await api.paymentReceipt(payment.id);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener');
      // Revoked on a delay, not immediately: the new tab has to finish reading
      // the blob first, and revoking synchronously gives it an empty document.
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      toast({
        tone: 'error',
        title: 'Could not open the receipt',
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button variant="ghost" size="sm" loading={busy} onClick={open}>
      Receipt
    </Button>
  );
}


/**
 * Usage credit: money spent by the second, shown as money.
 *
 * **Minutes are a footnote, not the headline.** The same balance buys wildly
 * different amounts of talking depending on which models a call runs on, so a
 * minutes figure is only true for the rate the organisation is on right now -
 * which is why it is prefixed "about" and the rate is stated beside it.
 *
 * A negative balance is a real state, not an error: a call that overran its hold
 * settles for more than was reserved, because a conversation already happening
 * with a person is never cut off over money. It renders as spent-and-then-some
 * rather than as a bug.
 */
function CreditSection({
  credit,
  canTopUp,
}: {
  /** Whether to offer the "Top up" button at all - not whether it might work.
   *  A deployment can take real subscription payments with no credit-pack
   *  product configured (`credit_pack_configured`), in which case the button
   *  must not render: clicking it always 404s, and rendering it anyway turns
   *  an honest "not offered here" into a control that looks broken. */
  credit: Credit;
  canTopUp: boolean;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [ledger, setLedger] = useState<LedgerEntry[] | null>(null);
  const [showLedger, setShowLedger] = useState(false);

  const openLedger = useCallback(async () => {
    setShowLedger(true);
    if (ledger !== null) return;
    try {
      setLedger(await api.creditLedger(50));
    } catch {
      // An empty array, not a stuck spinner: the statement is supporting detail,
      // and the balance above it is already the answer to the real question.
      setLedger([]);
    }
  }, [ledger]);

  const topUp = useCallback(async () => {
    setBusy(true);
    try {
      const { checkout_url } = await api.startTopUp(crypto.randomUUID());
      window.location.href = checkout_url;
    } catch (error) {
      toast({
        tone: 'error',
        title: 'Could not start the top-up',
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setBusy(false);
    }
  }, [toast]);

  if (credit.is_uncapped) {
    return (
      <SettingsSection
        title="Usage credit"
        description="What calls draw against, spent by the second."
      >
        <p className="text-small text-text-dim">
          This plan has no usage ceiling, so calls are not metered against a
          balance.
        </p>
      </SettingsSection>
    );
  }

  // Clamped, and the meter is hidden entirely when nothing has been granted yet.
  // `granted` now comes from the ledger rather than the plan, so the two agree -
  // but a meter is a ratio, and a ratio with a zero denominator has no honest
  // rendering. Showing "0 / 0" as a full bar is what made an organisation that
  // had used nothing look like it had used everything.
  const granted = credit.granted_this_period_paise;
  const spent = Math.max(granted - credit.balance_paise, 0);

  return (
    <SettingsSection
      title="Usage credit"
      description="What calls draw against. Spent by the second, at a rate that depends on whose model providers ran the call."
      footer={
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Button variant="ghost" size="sm" onClick={openLedger}>
            {showLedger ? 'Statement' : 'See statement'}
          </Button>
          {canTopUp ? (
            <Button variant="secondary" size="sm" loading={busy} onClick={topUp}>
              Top up
            </Button>
          ) : null}
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-mono text-h3 tabular-nums text-text">
            {formatMinorUnits(Math.max(credit.balance_paise, 0), 'INR')}
          </span>
          {granted > 0 ? (
            <span className="text-small text-text-dim">
              left of {formatMinorUnits(granted, 'INR')}
            </span>
          ) : null}
        </div>

        {granted > 0 ? (
          <EntitlementMeter
            label="Credit used this period"
            used={spent}
            limit={granted}
            atLimitHint="Top up, or wait for the next period to start."
          />
        ) : (
          <p className="text-small text-text-dim">
            No credit has been added this period yet.
          </p>
        )}

        <p className="text-small text-text-mute">
          {credit.balance_paise <= 0
            ? granted > 0
              ? 'Spent. Runs will stop until this is topped up or the period rolls over.'
              : 'Runs will stop until credit is added.'
            : `About ${formatNumber(credit.estimated_minutes_left)} minutes at your current rate of ${formatMinorUnits(credit.rate_paise_per_minute, 'INR')} a minute - an estimate, because a call on different providers costs a different amount.`}
        </p>

        {showLedger ? (
          ledger === null ? (
            <Skeleton className="h-24 w-full" />
          ) : ledger.length === 0 ? (
            <p className="text-small text-text-dim">Nothing recorded yet.</p>
          ) : (
            <ul className="flex flex-col gap-1.5 border-t border-rule pt-3">
              {ledger.map((entry) => (
                <li
                  key={entry.id}
                  className="flex items-baseline justify-between gap-3 text-small"
                >
                  <span className="text-text-dim">
                    {new Date(entry.created_at).toLocaleDateString()}
                  </span>
                  <span className="flex-1 text-text-mute">
                    {LEDGER_LABEL[entry.entry_kind] ?? entry.entry_kind}
                  </span>
                  <span className="font-mono tabular-nums text-text">
                    {entry.amount_minor >= 0 ? '+' : '-'}
                    {formatMinorUnits(Math.abs(entry.amount_minor), entry.currency)}
                  </span>
                </li>
              ))}
            </ul>
          )
        ) : null}
      </div>
    </SettingsSection>
  );
}

/** Ledger kinds in the reader's words, not the schema's. `hold` and `release`
 *  are both shown rather than netted away - a customer whose balance dipped and
 *  came back deserves to see that a call was reserved for and never connected. */
const LEDGER_LABEL: Record<LedgerEntry['entry_kind'], string> = {
  grant: 'Credit added',
  hold: 'Reserved for a call',
  release: 'Reservation returned',
  spend: 'Call',
  expiry: 'Expired at period end',
  adjustment: 'Adjustment',
};
