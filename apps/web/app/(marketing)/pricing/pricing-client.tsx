"use client";

import { useState } from "react";
import { CostComparison } from "@/components/marketing/cost-comparison";
import {
  FeatureMatrix,
  PlanCards,
  SegmentedToggle,
} from "@/components/marketing/pricing-table";
import { Accordion } from "@/components/ui/disclosure";
import { Eyebrow, SectionHeading } from "@/components/ui/panel";
import { Rule } from "@/components/ui/rule";
import type { Currency } from "@/lib/format";
import { ANNUAL_MONTHS_FREE, PRICING_FAQ, type BillingPeriod } from "@/lib/pricing";

/**
 * Pricing.
 *
 * Every commercial number on this page comes from `lib/pricing.ts`, and any that
 * has not been decided yet renders as a visible TODO chip rather than a guess. The
 * layout is finished; the numbers are a one-file change.
 */
export function PricingClient() {
  const [period, setPeriod] = useState<BillingPeriod>("monthly");
  // Defaults to INR because the primary market is India. A visitor can switch, and
  // deriving this from IP would mean a layout shift after hydration for no gain.
  const [currency, setCurrency] = useState<Currency>("INR");

  return (
    <>
      <section className="mx-auto max-w-(--container-marketing) px-4 pt-12 sm:px-6">
        <div className="flex flex-col gap-4">
          <Eyebrow>Pricing</Eyebrow>
          <h1 className="measure-display font-display text-display-l text-text">
            Start free, pay when you dial.
          </h1>
          <p className="measure text-body-l text-text-dim">
            Every plan, including Free, only bills for calls that actually connect. A
            call blocked by one of your safety guards is never billable.
          </p>
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <SegmentedToggle
            label="Billing period"
            value={period}
            onChange={setPeriod}
            options={[
              { value: "monthly", label: "Monthly" },
              {
                value: "annual",
                label: "Annual",
                hint: `${ANNUAL_MONTHS_FREE} months free`,
              },
            ]}
          />
          <SegmentedToggle
            label="Currency"
            value={currency}
            onChange={setCurrency}
            options={[
              { value: "INR", label: "INR" },
              { value: "USD", label: "USD" },
            ]}
          />
        </div>

        <div className="mt-8">
          <PlanCards currency={currency} period={period} />
        </div>
      </section>

      <Divider />
      <CostComparison currency={currency} />

      <Divider />
      <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
        <SectionHeading
          eyebrow="Every feature"
          title="What each plan includes."
          sub="Hover a feature name for a one-line explanation of what it actually does."
        />
        <div className="mt-8">
          <FeatureMatrix />
        </div>
      </section>

      <Divider />
      <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
        <SectionHeading eyebrow="Questions" title="Pricing questions, answered plainly." />
        <div className="mt-8 max-w-3xl">
          <Accordion
            items={PRICING_FAQ.map((item) => ({ title: item.q, content: item.a }))}
          />
        </div>
      </section>
    </>
  );
}

function Divider() {
  return (
    <div className="mx-auto max-w-(--container-marketing) px-4 py-(--space-section) sm:px-6">
      <Rule />
    </div>
  );
}
