'use client';

import { CheckIcon } from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { SectionHeading } from '@/components/ui/panel';
import { Reveal } from '@/components/ui/reveal';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/cn';
import { api, type PlanOption } from '@/lib/api';
import { formatMinorUnits } from '@/lib/format';
import { limitsSummary, PLANS, type Plan } from '@/lib/pricing';

/**
 * The plan ladder on the home page.
 *
 * A visitor who cannot find out roughly what something costs assumes it is
 * expensive, so the number belongs here. The reason this section was deleted in
 * the first place was that there was no number to show and it rendered `TODO`
 * chips (`DESIGN_NOTES.md`, 2026-08-10). There is one now - but it lives at the
 * payment gateway, which is the Merchant of Record and therefore the price of
 * record, so it has to be fetched rather than hard-coded.
 *
 * That shapes the whole component: **everything except the amount renders
 * statically and immediately**, from `lib/pricing.ts` - including the limits,
 * which are the numbers a buyer actually compares. Only the price waits on the
 * network. A visitor on a slow connection, a deployment with no gateway key, and
 * a gateway outage all still get a complete, readable comparison; they just see
 * "Pricing on request", which is true, rather than a zero, which is not
 * (CLAUDE.md §4 #9).
 *
 * Colour: the featured plan is raised with `.card-feature`'s halo, never a
 * coloured banner. The five lamp colours mean call state and only call state.
 */
export function PricingPreview() {
  // Enterprise is a conversation, not a card in a three-up grid. It gets the
  // line underneath instead.
  const shown = PLANS.filter((plan) => plan.id !== 'enterprise');
  const live = useLivePlans();

  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          title="Pick a plan, not a call budget."
          sub="Calls are never billed per minute. A plan buys how much you can stand up - agents and seats - plus calling credit, spent by the second at a rate that drops when you bring your own model providers."
        />
      </Reveal>

      <div className="mt-8 grid items-stretch gap-4 md:grid-cols-3">
        {shown.map((plan, i) => (
          <Reveal key={plan.id} delayMs={i * 60} className="h-full">
            <PlanColumn plan={plan} live={live} />
          </Reveal>
        ))}
      </div>

      <Reveal delayMs={200} className="mt-6 flex flex-col gap-2">
        {/* Every card above points at signup, so say what signup gives you before
            someone clicks "Choose Growth" and lands on a Free account wondering
            whether the choice was taken. There is no trial of a paid plan and no
            card at signup - both are worth stating rather than implying. */}
        <p className="measure text-small text-text-dim">
          Every account starts on Free, with no card. Move up whenever you want
          from Billing, and your plan runs to the end of any period you have
          already paid for if you cancel.
        </p>
        <p className="measure text-small text-text-dim">
          Running outbound as a core operation?{' '}
          <Link
            href="/demo"
            className="font-medium text-text underline decoration-rule-strong underline-offset-4 transition-colors hover:decoration-current"
          >
            Talk to us about Enterprise
          </Link>{' '}
          - limits set to whatever you actually need, with a signed DPA and SSO.
        </p>
      </Reveal>
    </section>
  );
}

/**
 * `loading` is deliberately distinct from `unavailable`: one is a skeleton, the
 * other is a sentence. Collapsing them into an empty value is how a slow network
 * ends up looking identical to a plan that has no price.
 *
 * Fetched once for the whole section rather than once per card - three cards each
 * asking for the same ladder is three requests for one answer.
 */
type LivePlans =
  | { status: 'loading' }
  | { status: 'ready'; plans: PlanOption[] }
  | { status: 'unavailable' };

function useLivePlans(): LivePlans {
  const [state, setState] = useState<LivePlans>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;
    api
      .publicPlans()
      .then((plans) => {
        if (!cancelled) setState({ status: 'ready', plans });
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'unavailable' });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

function PlanColumn({ plan, live }: { plan: Plan; live: LivePlans }) {
  const featured = !!plan.mostChosen;

  return (
    <div
      className={cn(
        'relative flex h-full flex-col gap-4 overflow-hidden p-5',
        featured ? 'card-feature' : 'card-raised',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-h4 font-medium text-text">{plan.name}</h3>
        {featured ? (
          <span className="rounded-full bg-text px-2.5 py-1 text-label uppercase tracking-[0.12em] text-surface">
            Most chosen
          </span>
        ) : null}
      </div>

      <div className="flex flex-col gap-1">
        <PriceLine planId={plan.id} live={live} />
        <p className="text-small text-text-mute">{limitsSummary(plan.id)}</p>
        <RateLine planId={plan.id} live={live} />
      </div>

      <p className="text-small text-text-dim">{plan.tagline}</p>

      <div aria-hidden className="h-px bg-rule" />

      <ul className="flex flex-1 flex-col gap-2.5">
        {plan.features.slice(0, 4).map((feature) => (
          <li
            key={feature}
            className="flex items-start gap-2.5 text-small text-text-dim"
          >
            <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full bg-surface-sunken">
              <CheckIcon
                aria-hidden
                weight="bold"
                className="size-2.5 text-text-mute"
              />
            </span>
            {feature}
          </li>
        ))}
      </ul>

      <Button
        asChild
        variant={featured ? 'primary' : 'secondary'}
        className="mt-auto"
      >
        <Link href={plan.ctaHref}>{plan.cta}</Link>
      </Button>
    </div>
  );
}

/** One plan's rates - the only thing on this card that needs the network,
 *  because the gateway is the price of record. */
function PriceLine({ planId, live }: { planId: string; live: LivePlans }) {
  if (planId === 'free') {
    // Nothing to fetch: no gateway product exists for a plan with no charge, so
    // waiting on the network here would skeleton a number that is never coming.
    return <span className="font-display text-h3 text-text">Free forever</span>;
  }

  if (live.status === 'loading') {
    return (
      <div className="flex flex-col gap-1.5">
        <Skeleton className="h-8 w-28" />
        <Skeleton className="h-3 w-36" />
      </div>
    );
  }

  const prices =
    live.status === 'ready'
      ? live.plans.find((plan) => plan.plan_id === planId)?.prices
      : undefined;
  const monthly = prices?.find((price) => price.period === 'monthly');
  const annual = prices?.find((price) => price.period === 'annual');

  if (!monthly) {
    return <span className="text-body text-text-dim">Pricing on request</span>;
  }

  return (
    <div className="flex flex-col gap-0.5">
      <span className="flex items-baseline gap-1.5">
        <span className="font-display text-h3 tabular-nums text-text">
          {formatMinorUnits(monthly.amount_minor, monthly.currency)}
        </span>
        <span className="text-small text-text-dim">/month</span>
      </span>
      {annual ? (
        <span className="text-small text-text-dim">
          or {formatMinorUnits(annual.amount_minor, annual.currency)} a year
          {monthsFree(monthly.amount_minor, annual.amount_minor)}
        </span>
      ) : null}
    </div>
  );
}

/**
 * "≈66 min at ₹1.50/min with your own keys" - what the included credit actually
 * buys, at the one rate that is the same for every plan: the platform fee alone,
 * which is what a call costs once nothing runs on CallFlow's own keys. The
 * per-provider tier add-ons (`docs/PRICING_DECISIONS.md` §3) can raise it above
 * this, so "with your own keys" is load-bearing rather than decoration - it is
 * the floor, not a promise every call lands there.
 *
 * Loads with the same request `PriceLine` makes, so it renders nothing rather
 * than a skeleton while that is in flight - a second loading indicator for one
 * fetch is noise, and the price line already carries that signal.
 */
function RateLine({ planId, live }: { planId: string; live: LivePlans }) {
  if (live.status !== 'ready') return null;

  const plan = live.plans.find((option) => option.plan_id === planId);
  const rate = plan?.baseline_rate_paise_per_minute;
  if (!rate || rate <= 0) return null;

  const rateText = `${formatMinorUnits(rate, 'INR')}/min with your own keys`;
  const credit = plan?.entitlements.monthly_credit_paise;
  if (credit == null || credit <= 0) {
    return <p className="text-small text-text-mute">{rateText}</p>;
  }

  const minutes = Math.floor(credit / rate);
  return (
    <p className="text-small text-text-mute">
      ≈{minutes} min at {rateText}
    </p>
  );
}

/**
 * " - 2 months free", or nothing.
 *
 * Derived from the two amounts rather than written as copy, so it cannot outlive
 * a price change at the gateway. Stated only when the discount lands on a whole
 * number of months: "1.7 months free" is not a claim anyone makes, and rounding
 * it to 2 would overstate the saving on a page someone buys from.
 */
function monthsFree(monthlyMinor: number, annualMinor: number): string {
  if (monthlyMinor <= 0) return '';
  const free = 12 - annualMinor / monthlyMinor;
  const whole = Math.round(free);
  if (whole < 1 || Math.abs(free - whole) > 0.02) return '';
  return ` - ${whole} ${whole === 1 ? 'month' : 'months'} free`;
}
