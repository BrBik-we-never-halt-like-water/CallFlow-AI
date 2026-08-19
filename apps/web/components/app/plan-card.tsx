/**
 * One plan, with its price and whatever action is honestly available on it.
 *
 * The action is the whole point of this component, and it has four distinct
 * states rather than one disabled flag - "you are on this", "we cannot take money
 * on this deployment", "this tier is a conversation", and "buy it". Collapsing
 * them into a greyed-out button would tell someone their plan is unavailable when
 * the truth is that this *deployment* has no payment processor (CLAUDE.md §4 #9).
 */

'use client';

import { Button } from '@/components/ui/button';
import { Panel } from '@/components/ui/panel';
import { cn } from '@/lib/cn';
import { formatMinorUnits, formatNumber } from '@/lib/format';
import type { PlanOption } from '@/lib/api';

/** `null` is unlimited, `0` is a real ceiling - never collapse them. */
function limitLabel(value: number | null): string {
  return value === null ? 'Unlimited' : formatNumber(value);
}

export interface PlanCardProps {
  plan: PlanOption;
  /** False when this deployment has no gateway key. */
  paymentsConfigured: boolean;
  /** Only an owner may buy; `billing:write` is owner-only. */
  canPurchase: boolean;
  /**
   * True when the organisation already has a live subscription. Changes both the
   * verb and the endpoint: with one in place the gateway wants a plan *change*,
   * and starting a second checkout would open a second subscription and bill
   * twice - which is exactly what the API refuses with a 409.
   */
  hasSubscription: boolean;
  /**
   * True when the live subscription is cancelled at period end. The gateway
   * refuses a plan change on one of these outright
   * ("PLAN_CHANGE_NOT_ALLOWED_FOR_CANCELLED"), so offering Switch produces a 409
   * the customer can do nothing about. Buying again is the action that works.
   */
  windingDown: boolean;
  busy: boolean;
  onChoose: (plan: PlanOption) => void;
}

export function PlanCard({
  plan,
  paymentsConfigured,
  canPurchase,
  hasSubscription,
  windingDown,
  busy,
  onChoose,
}: PlanCardProps) {
  const monthly = plan.prices.find((p) => p.period === 'monthly');
  const isFree = plan.plan_id === 'free';

  return (
    <Panel
      className={cn(
        'flex flex-col gap-3 p-4',
        // A 1px ink border marks the current plan - never a coloured banner, which
        // would put a meaningless hue next to the lamps (DESIGN_NOTES §2).
        plan.current && 'border-text',
      )}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-h3 font-medium text-text">{plan.name}</span>
        {plan.current ? (
          <span className="font-mono text-small text-text-mute">Current</span>
        ) : null}
      </div>

      <div className="flex items-baseline gap-1.5">
        {isFree ? (
          <span className="font-mono text-h3 tabular-nums text-text">Free</span>
        ) : monthly ? (
          <>
            <span className="font-mono text-h3 tabular-nums text-text">
              {formatMinorUnits(monthly.amount_minor, monthly.currency)}
            </span>
            <span className="text-small text-text-dim">/month</span>
          </>
        ) : (
          // No configured product. Says so rather than rendering a blank or a
          // zero, either of which reads as "this is free".
          <span className="text-body text-text-dim">Priced per agreement</span>
        )}
      </div>

      <dl className="flex flex-col gap-1 text-small">
        {(
          [
            ['Voice agents', plan.entitlements.max_voice_agents],
            ['Seats', plan.entitlements.max_seats],
            ['Organisations', plan.entitlements.max_organisations],
            ['Model providers', plan.entitlements.max_ai_integrations],
            ['Calls per day', plan.entitlements.daily_call_budget],
          ] as const
        ).map(([label, value]) => (
          <div key={label} className="flex justify-between gap-2">
            <dt className="text-text-dim">{label}</dt>
            <dd className="font-mono tabular-nums text-text">{limitLabel(value)}</dd>
          </div>
        ))}
      </dl>

      <PlanAction
        plan={plan}
        paymentsConfigured={paymentsConfigured}
        canPurchase={canPurchase}
        hasSubscription={hasSubscription}
        windingDown={windingDown}
        busy={busy}
        onChoose={onChoose}
      />
    </Panel>
  );
}

function PlanAction({
  plan,
  paymentsConfigured,
  canPurchase,
  hasSubscription,
  windingDown,
  busy,
  onChoose,
}: PlanCardProps) {
  if (plan.current) {
    return (
      <p className="text-small text-text-mute">This is the plan you are on.</p>
    );
  }

  if (!plan.self_serve) {
    // Enterprise and Free. Neither has a checkout, and saying so beats a
    // disabled button that looks like something is broken.
    return plan.plan_id === 'free' ? (
      <p className="text-small text-text-mute">
        Where every organisation starts.
      </p>
    ) : (
      <Button variant="secondary" size="sm" asChild>
        <a href="/demo">Book a 15-min demo</a>
      </Button>
    );
  }

  if (!paymentsConfigured) {
    return (
      <p className="text-small text-text-mute">
        No payment processor is connected on this deployment, so this plan
        can&apos;t be bought here yet.
      </p>
    );
  }

  if (!canPurchase) {
    return (
      <p className="text-small text-text-mute">
        Only an owner can change the plan.
      </p>
    );
  }

  // A cancelled subscription cannot be switched, only replaced - so the verb is
  // the buying one even though a subscription technically still exists.
  const verb = hasSubscription && !windingDown ? 'Switch to' : 'Upgrade to';
  return (
    <Button size="sm" loading={busy} onClick={() => onChoose(plan)}>
      {verb} {plan.name}
    </Button>
  );
}
