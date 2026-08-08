"use client";

import { useEffect, useState } from "react";
import { useReducedMotion } from "framer-motion";
import { Eyebrow, SectionHeading } from "@/components/ui/panel";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { formatNumber } from "@/lib/format";
import { COMPARISON_DEFAULTS } from "@/lib/pricing";

/**
 * A tele-caller versus CallFlow — shown as throughput, not a price table.
 *
 * What closes this comparison isn't cost per call (CallFlow's price isn't public
 * yet anyway); it's that a person is *linear* — one call at a time, eight hours —
 * while a campaign is *parallel* and around the clock. So both lanes clear the
 * same day's calls at once: the person's tally crawls, the campaign's races. The
 * buyer's own calls-per-day figure drives both, so it reads as their maths.
 */

/** One compressed "working day" plays in this many seconds, then loops. */
const DAY_SECONDS = 16;
/** Illustrative parallelism — many conversations at once, around the clock. */
const PARALLEL = 20;
const TICK_MS = 90;
const STRIP = 30;

export function CostComparison() {
  const [callsPerDay, setCallsPerDay] = useState<number>(COMPARISON_DEFAULTS.callsPerDay);
  const callsPerMonth = callsPerDay * COMPARISON_DEFAULTS.workingDaysPerMonth;

  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <SectionHeading
        eyebrow="What it replaces"
        title="One person dials in sequence. A campaign dials in parallel."
        sub="Your number, not our claim — watch the same day's calls clear each way."
      />

      <div className="mt-6 max-w-xs">
        <Field label="Connected calls per day" help="Per person, on a good day.">
          <Input
            type="number"
            min={1}
            value={callsPerDay}
            onChange={(e) => setCallsPerDay(Math.max(1, Number(e.target.value)))}
            className="font-mono tabular-nums"
          />
        </Field>
      </div>

      <div className="mt-8">
        <ThroughputViz
          callsPerDay={callsPerDay}
          callsPerMonth={callsPerMonth}
          coveredHours={COMPARISON_DEFAULTS.coveredHoursPerDay}
        />
      </div>

      <p className="mt-5 measure text-small text-text-mute">
        A person is one line. A campaign runs as many conversations in parallel as your
        rate limit allows — which is why this stops being about cost per call quite fast.
      </p>
    </section>
  );
}

function ThroughputViz({
  callsPerDay,
  callsPerMonth,
  coveredHours,
}: {
  callsPerDay: number;
  callsPerMonth: number;
  coveredHours: number;
}) {
  const reduced = useReducedMotion();
  const [ms, setMs] = useState(0);

  useEffect(() => {
    if (reduced) return;
    const start = performance.now();
    const id = setInterval(() => {
      setMs((performance.now() - start) % (DAY_SECONDS * 1000));
    }, TICK_MS);
    return () => clearInterval(id);
  }, [reduced]);

  // 0 → 1 across the compressed day.
  const progress = reduced ? 1 : ms / (DAY_SECONDS * 1000);
  const human = Math.round(progress * callsPerDay);
  const campaign = Math.round(progress * callsPerDay * PARALLEL);

  // The human strip fills once across the day; the campaign strip fills and
  // resets PARALLEL times, so it visibly churns while the person's crawls.
  const humanFilled = reduced ? Math.round(STRIP * 0.28) : Math.round(progress * STRIP);
  const campaignFilled = reduced ? STRIP : Math.round(((progress * PARALLEL) % 1) * STRIP);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Lane
        label="One tele-caller"
        tagline="One call at a time"
        count={human}
        filled={humanFilled}
        tone="mute"
        active="1 line · in sequence"
        foot={`≈ ${formatNumber(callsPerMonth)} calls a month, then home for the night · ${coveredHours}h weekdays · notes by hand`}
      />
      <Lane
        label="One CallFlow campaign"
        tagline="Many calls at once"
        count={campaign}
        filled={campaignFilled}
        tone="jade"
        active={`${PARALLEL} conversations in parallel · around the clock`}
        foot="Every call typed automatically — outcome, sentiment, next step"
      />
    </div>
  );
}

function Lane({
  label,
  tagline,
  count,
  filled,
  tone,
  active,
  foot,
}: {
  label: string;
  tagline: string;
  count: number;
  filled: number;
  tone: "mute" | "jade";
  active: string;
  foot: string;
}) {
  const fill = tone === "jade" ? "var(--lamp-jade)" : "var(--text-mute)";
  return (
    <div className="surface-flow flex flex-col gap-4 p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <Eyebrow>{label}</Eyebrow>
        <span className="text-small text-text-mute">{tagline}</span>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="font-display text-display-l tabular-nums text-text">
          {formatNumber(count)}
        </span>
        <span className="text-small text-text-mute">calls today</span>
      </div>

      <div className="flex h-2 items-stretch gap-1" aria-hidden>
        {Array.from({ length: STRIP }).map((_, i) => (
          <span
            key={i}
            className="flex-1 rounded-full transition-colors duration-150"
            style={{ background: i < filled ? fill : "var(--rule)" }}
          />
        ))}
      </div>

      <p className="text-small text-text-dim">{active}</p>
      <p className="mt-auto pt-1 text-small text-text-mute">{foot}</p>
    </div>
  );
}
