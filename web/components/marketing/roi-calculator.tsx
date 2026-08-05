"use client";

import { useState } from "react";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Eyebrow, Panel } from "@/components/ui/panel";
import { SegmentedToggle } from "./pricing-table";
import { formatCurrency, formatNumber, type Currency } from "@/lib/format";
import { ROI_DEFAULTS } from "@/lib/pricing";
import type { Vertical } from "@/lib/verticals";

/**
 * ROI calculator for a solution page.
 *
 * Everything it reports is derived from inputs the buyer sets, and it says so. The
 * output deliberately leads with **hours**, not money: the operations owner reading
 * this page does not control the salary line, but they do control where their team's
 * afternoon goes, and that is the number they can act on today.
 */
export function RoiCalculator({ vertical }: { vertical: Vertical }) {
  const [currency, setCurrency] = useState<Currency>("INR");
  const [contacts, setContacts] = useState(vertical.roi.contactsPerMonth);
  const [minutesPerCall, setMinutesPerCall] = useState(vertical.roi.minutesPerCall);
  const [costPerCall, setCostPerCall] = useState<number>(
    currency === "INR" ? ROI_DEFAULTS.costPerHumanCallInr : ROI_DEFAULTS.costPerHumanCallUsd,
  );

  function switchCurrency(next: Currency) {
    setCurrency(next);
    setCostPerCall(
      next === "INR" ? ROI_DEFAULTS.costPerHumanCallInr : ROI_DEFAULTS.costPerHumanCallUsd,
    );
  }

  // Attempts, not conversations: reaching someone usually takes more than one try,
  // and a calculator that ignores that flatters the result.
  const attempts = Math.round(contacts * 1.6);
  const humanHours = (attempts * minutesPerCall) / 60;
  const humanCost = attempts * costPerCall;

  // The share of calls that settle without anyone reading them. Conservative on
  // purpose — the remainder still needs a person, and the page should assume so.
  const autoClosedShare = 0.72;
  const hoursSaved = humanHours * autoClosedShare;
  const costAvoided = humanCost * autoClosedShare;
  const needsPerson = Math.max(0, Math.round(contacts * (1 - autoClosedShare)));

  return (
    <Panel className="flex flex-col gap-6 p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <Eyebrow>Your numbers</Eyebrow>
          <h3 className="font-display text-h3 text-text">What this frees up.</h3>
        </div>
        <SegmentedToggle
          label="Currency"
          value={currency}
          onChange={switchCurrency}
          options={[
            { value: "INR", label: "INR" },
            { value: "USD", label: "USD" },
          ]}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Contacts per month">
          <Input
            type="number"
            min={1}
            value={contacts}
            onChange={(e) => setContacts(Math.max(1, Number(e.target.value)))}
            className="font-mono tabular-nums"
          />
        </Field>
        <Field label="Minutes per attempt" help="Dialling and notes included.">
          <Input
            type="number"
            min={1}
            value={minutesPerCall}
            onChange={(e) => setMinutesPerCall(Math.max(1, Number(e.target.value)))}
            className="font-mono tabular-nums"
          />
        </Field>
        <Field label="Cost per attempt">
          <Input
            type="number"
            min={0}
            step="0.01"
            value={costPerCall}
            onChange={(e) => setCostPerCall(Math.max(0, Number(e.target.value)))}
            className="font-mono tabular-nums"
          />
        </Field>
      </div>

      <dl className="grid gap-4 border-t border-rule pt-5 sm:grid-cols-3">
        <Output
          label="Hours handed back"
          value={`${formatNumber(Math.round(hoursSaved))}h`}
          detail="per month, across the team"
        />
        <Output
          label="Cost avoided"
          value={formatCurrency(Math.round(costAvoided), currency, { compact: true })}
          detail="before CallFlow's own cost"
        />
        <Output
          label="Still reaches a person"
          value={formatNumber(needsPerson)}
          detail="the conversations worth having"
        />
      </dl>

      <p className="text-small text-text-mute">
        Assumes {formatNumber(attempts)} attempts to reach {formatNumber(contacts)} contacts,
        and that {Math.round(autoClosedShare * 100)}% of calls settle without anyone reading
        them. Subtract your plan cost for the net figure — the last column is the point:
        the work that needs judgement still gets it.
      </p>
    </Panel>
  );
}

function Output({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="eyebrow text-text-mute">{label}</dt>
      <dd className="font-display text-[2rem] leading-none tabular-nums text-text">{value}</dd>
      <p className="text-small text-text-mute">{detail}</p>
    </div>
  );
}
