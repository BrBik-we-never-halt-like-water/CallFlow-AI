'use client';

import { useState } from 'react';
import { Eyebrow, SectionHeading } from '@/components/ui/panel';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { formatCurrency, formatNumber, type Currency } from '@/lib/format';
import { COMPARISON_DEFAULTS } from '@/lib/pricing';
import { TodoChip } from './price-value';

/**
 * A tele-caller versus CallFlow.
 *
 * This is the comparison that actually closes deals in this market - the buyer is
 * weighing this against hiring someone, not against an API - so it gets a full
 * section rather than a footnote.
 *
 * The salary and call-rate figures are editable inputs with defaults, not claims.
 * A buyer who can put their own numbers in believes the result; one who is handed
 * a flattering static table does not.
 */
export function CostComparison({ currency }: { currency: Currency }) {
  const [monthlyCost, setMonthlyCost] = useState<number>(
    currency === 'INR'
      ? COMPARISON_DEFAULTS.callerMonthlyInr
      : COMPARISON_DEFAULTS.callerMonthlyUsd,
  );
  const [callsPerDay, setCallsPerDay] = useState<number>(
    COMPARISON_DEFAULTS.callsPerDay,
  );

  const callsPerMonth = callsPerDay * COMPARISON_DEFAULTS.workingDaysPerMonth;
  const costPerCall = callsPerMonth > 0 ? monthlyCost / callsPerMonth : 0;
  const notesHoursPerMonth =
    (callsPerMonth * COMPARISON_DEFAULTS.notesMinutesPerCall) / 60;

  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <SectionHeading
        eyebrow="What it replaces"
        title="Compared with hiring someone to dial."
        sub="Put your own numbers in. These are your assumptions, not our claims."
      />

      <div className="mt-6 grid gap-3 sm:max-w-md sm:grid-cols-2">
        <Field
          label="Monthly cost of one caller"
          help="Fully loaded - salary, desk, phone."
        >
          <Input
            type="number"
            min={0}
            value={monthlyCost}
            onChange={(e) =>
              setMonthlyCost(Math.max(0, Number(e.target.value)))
            }
            className="font-mono tabular-nums"
          />
        </Field>
        <Field
          label="Connected calls per day"
          help="Per person, on a good day."
        >
          <Input
            type="number"
            min={1}
            value={callsPerDay}
            onChange={(e) =>
              setCallsPerDay(Math.max(1, Number(e.target.value)))
            }
            className="font-mono tabular-nums"
          />
        </Field>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <div className="surface-flow flex flex-col divide-y divide-rule shadow-sm">
          <header className="p-5">
            <Eyebrow>A tele-caller</Eyebrow>
            <p className="mt-2 font-display text-h3 text-text">
              One person, one phone
            </p>
          </header>
          <Row
            label="Monthly cost"
            value={formatCurrency(monthlyCost, currency)}
          />
          <Row
            label="Calls per month"
            value={`${formatNumber(callsPerMonth)} connected`}
          />
          <Row
            label="Cost per connected call"
            value={formatCurrency(
              Math.round(costPerCall * 100) / 100,
              currency,
            )}
          />
          <Row
            label="Hours covered"
            value={`${COMPARISON_DEFAULTS.coveredHoursPerDay}h on weekdays`}
          />
          <Row
            label="Notes"
            value={`${notesHoursPerMonth.toFixed(0)}h/month typed by hand`}
          />
          <Row label="Sentiment recorded" value="Only when someone remembers" />
        </div>

        <div className="surface-flow flex flex-col divide-y divide-rule shadow-md">
          <header className="p-5">
            <Eyebrow>CallFlow Growth</Eyebrow>
            <p className="mt-2 font-display text-h3 text-text">
              A campaign, not a headcount
            </p>
          </header>
          {/* Plan price and included volume are unset until pricing is signed off,
              and the TODO chip says so rather than inventing a favourable number. */}
          <Row label="Monthly cost" value={<TodoChip />} />
          <Row label="Calls per month" value={<TodoChip />} />
          <Row label="Cost per connected call" value={<TodoChip />} />
          <Row label="Hours covered" value="24×7, including weekends" />
          <Row label="Notes" value="Typed automatically, on every call" />
          <Row
            label="Sentiment recorded"
            value="Every call, as a typed field"
          />
        </div>
      </div>

      <p className="mt-4 text-small text-text-mute">
        One caller is one caller. A campaign runs as many conversations in
        parallel as your rate limit allows, which is why the comparison stops
        being about cost per call fairly quickly.
      </p>
    </section>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 px-5 py-3">
      <span className="text-small text-text-dim">{label}</span>
      <span className="text-right font-mono text-data tabular-nums text-text">
        {value}
      </span>
    </div>
  );
}
