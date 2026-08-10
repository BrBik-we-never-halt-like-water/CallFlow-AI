'use client';

import { CheckIcon, MinusIcon } from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { Tag } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tooltip } from '@/components/ui/tooltip';
import type { Currency } from '@/lib/format';
import {
  ANNUAL_MONTHS_FREE,
  ENTERPRISE,
  FEATURE_MATRIX,
  monthlyEquivalent,
  PLANS,
  type BillingPeriod,
  type MatrixValue,
  type PlanId,
} from '@/lib/pricing';
import { PriceValue, RateValue, TodoChip, VolumeValue } from './price-value';

/* -------------------------------------------------------------------------- */
/* Toggles                                                                     */
/* -------------------------------------------------------------------------- */

/**
 * Segmented control for the billing period and currency.
 *
 * Built as a radiogroup rather than two buttons, so a keyboard user gets arrow-key
 * movement between the options instead of tabbing through each one.
 */
export function SegmentedToggle<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string; hint?: string }[];
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex items-center gap-0.5 rounded-sm border border-rule bg-surface-sunken p-0.5"
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={cn(
              'inline-flex cursor-pointer items-center gap-1.5 rounded-xs px-3 py-1.5 text-small font-medium',
              'transition-colors duration-(--dur-micro)',
              active
                ? 'bg-surface-inverse text-text-inverse'
                : 'text-text-dim hover:text-text',
            )}
          >
            {option.label}
            {option.hint ? (
              <span
                className={cn(
                  'font-mono text-label',
                  active ? 'opacity-80' : 'text-text-mute',
                )}
              >
                {option.hint}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Plan cards                                                                  */
/* -------------------------------------------------------------------------- */

export function PlanCards({
  currency,
  period,
}: {
  currency: Currency;
  period: BillingPeriod;
}) {
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-4">
        {PLANS.map((plan) => {
          const price = monthlyEquivalent(plan, currency, period);
          return (
            <div
              key={plan.id}
              className={cn(
                'surface-flow flex flex-col gap-4 p-5',
                plan.mostChosen ? 'shadow-md' : 'shadow-sm',
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-h4 font-medium text-text">{plan.name}</h3>
                {plan.mostChosen ? <Tag>Most chosen</Tag> : null}
              </div>

              <div className="flex flex-col gap-1">
                <PriceValue
                  amount={price}
                  currency={currency}
                  suffix={price === 0 ? undefined : '/ month'}
                />
                {period === 'annual' && price !== 0 ? (
                  <span className="text-small text-text-mute">
                    billed annually, {ANNUAL_MONTHS_FREE} months free
                  </span>
                ) : null}
              </div>

              <p className="text-small text-text-dim">{plan.tagline}</p>

              <div className="flex flex-col gap-1 border-y border-rule py-3">
                <VolumeValue calls={plan.includedCalls} />
                <RateValue
                  amount={
                    currency === 'INR' ? plan.overageInr : plan.overageUsd
                  }
                  currency={currency}
                  suffix="per call after that"
                />
              </div>

              <ul className="flex flex-col gap-1.5">
                {plan.features.map((feature) => (
                  <li
                    key={feature}
                    className="flex items-start gap-2 text-small text-text-dim"
                  >
                    <CheckIcon
                      aria-hidden
                      weight="bold"
                      className="mt-1 size-3 shrink-0 text-text-mute"
                    />
                    {feature}
                  </li>
                ))}
              </ul>

              <Button
                asChild
                variant={plan.mostChosen ? 'primary' : 'secondary'}
                className="mt-auto"
              >
                <Link href={plan.ctaHref}>{plan.cta}</Link>
              </Button>
            </div>
          );
        })}
      </div>

      {/* Enterprise as a full-width band: it is a conversation, not a column. */}
      <div className="surface-flow mt-4 flex flex-col gap-5 p-5 shadow-sm lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-2">
          <h3 className="text-h4 font-medium text-text">{ENTERPRISE.name}</h3>
          <p className="text-small text-text-dim">{ENTERPRISE.tagline}</p>
        </div>

        <ul className="grid gap-1.5 sm:grid-cols-2 lg:max-w-xl lg:flex-1">
          {ENTERPRISE.features.map((feature) => (
            <li
              key={feature}
              className="flex items-start gap-2 text-small text-text-dim"
            >
              <CheckIcon
                aria-hidden
                weight="bold"
                className="mt-1 size-3 shrink-0 text-text-mute"
              />
              {feature}
            </li>
          ))}
        </ul>

        <Button asChild variant="secondary" className="shrink-0">
          <Link href={ENTERPRISE.ctaHref}>{ENTERPRISE.cta}</Link>
        </Button>
      </div>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Feature matrix                                                              */
/* -------------------------------------------------------------------------- */

const PLAN_IDS: PlanId[] = ['free', 'starter', 'growth', 'scale'];

/**
 * Full comparison, grouped by category with sticky plan headers.
 *
 * A real table with `scope` on every header, because this is exactly the content a
 * screen-reader user needs to navigate cell by cell - and a grid of divs would make
 * that impossible.
 */
export function FeatureMatrix() {
  return (
    <div className="overflow-x-auto rounded-md border border-rule">
      <table className="w-full min-w-3xl border-collapse text-left">
        <caption className="sr-only">
          Feature comparison across the Free, Starter, Growth, and Scale plans
        </caption>

        <thead className="sticky top-0 z-10 bg-surface-sunken">
          <tr className="border-b border-rule">
            <th scope="col" className="eyebrow w-2/5 px-4 py-3 text-text-mute">
              Feature
            </th>
            {PLANS.map((plan) => (
              <th key={plan.id} scope="col" className="px-4 py-3">
                <span className="flex flex-col gap-0.5">
                  <span className="text-small font-medium text-text">
                    {plan.name}
                  </span>
                  {plan.mostChosen ? (
                    <span className="eyebrow text-text-mute">Most chosen</span>
                  ) : null}
                </span>
              </th>
            ))}
          </tr>
        </thead>

        {FEATURE_MATRIX.map((category) => (
          <tbody key={category.name}>
            <tr>
              <th
                scope="colgroup"
                colSpan={PLAN_IDS.length + 1}
                className="eyebrow border-y border-rule bg-surface-sunken px-4 py-2 text-text"
              >
                {category.name}
              </th>
            </tr>

            {category.rows.map((row) => (
              <tr
                key={row.label}
                className="border-b border-rule last:border-0"
              >
                <th
                  scope="row"
                  className="px-4 py-2.5 text-small font-normal text-text"
                >
                  {row.hint ? (
                    <Tooltip content={row.hint}>
                      <span className="cursor-help underline decoration-rule-strong decoration-dotted underline-offset-4">
                        {row.label}
                      </span>
                    </Tooltip>
                  ) : (
                    row.label
                  )}
                </th>
                {PLAN_IDS.map((planId) => (
                  <td key={planId} className="px-4 py-2.5">
                    <MatrixCell
                      value={row.values[planId]}
                      label={row.label}
                      plan={planId}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}

function MatrixCell({
  value,
  label,
  plan,
}: {
  value: MatrixValue;
  label: string;
  plan: PlanId;
}) {
  // `null` means the number has not been set yet - same TODO treatment as prices,
  // so an unfinished commercial decision is never mistaken for a real limit.
  if (value === null) return <TodoChip />;

  if (value === true) {
    return (
      <>
        <CheckIcon aria-hidden weight="bold" className="size-4 text-text" />
        <span className="sr-only">{`${label} is included in ${plan}`}</span>
      </>
    );
  }

  if (value === false) {
    return (
      <>
        <MinusIcon aria-hidden className="size-4 text-text-mute" />
        <span className="sr-only">{`${label} is not included in ${plan}`}</span>
      </>
    );
  }

  return (
    <span className="font-mono text-data tabular-nums text-text">{value}</span>
  );
}
