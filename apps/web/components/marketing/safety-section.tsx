"use client";

import { SafetyBar, type Guard } from "@/components/app/safety-bar";
import { SectionHeading } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";

/**
 * Safety, shown rather than described.
 *
 * The live `SafetyBar` here is the same component the run composer uses, with the
 * same guards. That is deliberate: this section does double duty as a trust signal
 * and as a differentiator, and a screenshot of a safety feature is much less
 * convincing than the actual control.
 *
 * One guard is shown switched off, because the design's whole claim about guards
 * is that an unguarded configuration looks uncomfortable — and a visitor should
 * be able to see that for themselves.
 */

const DEMO_GUARDS: Guard[] = [
  {
    id: "allowlist",
    label: "Allowlist",
    value: "1",
    explanation:
      "While the allowlist has any number on it, those are the only numbers a run may dial. Everything else is skipped before it rings.",
    settingsHref: "/docs/safety-configuration",
  },
  {
    id: "ceiling",
    label: "Ceiling",
    value: "25/RUN",
    explanation:
      "A hard cap on how many real calls one run may place. The run stops at the ceiling rather than working through the rest of your list.",
    settingsHref: "/docs/safety-configuration",
  },
  {
    id: "rate",
    label: "Rate",
    value: "2/HR",
    explanation:
      "Paces how fast calls go out, so a run reaches people at a human rhythm instead of arriving as a burst.",
    settingsHref: "/docs/safety-configuration",
  },
  {
    id: "window",
    label: "Window",
    value: "09:00–20:00 IST",
    explanation:
      "Calls are only placed inside this window. A contact reached outside it is queued for the next opening rather than dialled.",
    settingsHref: "/docs/safety-configuration",
  },
];

const GUARDS_EXPLAINED = [
  {
    name: "Allowlist",
    behaviour: "Fails closed",
    detail:
      "While the allowlist has anything on it, those are the only numbers that can be reached. A contact that is not on it is skipped before the call is placed, and the row says so.",
  },
  {
    name: "Per-run ceiling",
    behaviour: "Hard stop",
    detail:
      "A run cannot place more real calls than the ceiling, no matter how long the list is. It stops and tells you it stopped, rather than quietly working through five hundred rows.",
  },
  {
    name: "Rate limit",
    behaviour: "Paced",
    detail:
      "Calls go out at a set rate per hour. The point is not throughput; it is that a run should reach people at a human rhythm.",
  },
  {
    name: "Calling window",
    behaviour: "Queued outside hours",
    detail:
      "Outside the window nothing is dialled. Contacts wait for the next opening, which is also why a bad time is queued for retry instead of counted as a bad outcome.",
  },
  {
    name: "Suppression list",
    behaviour: "Permanent, global",
    detail:
      "Anyone who asks not to be called again is added automatically and is never dialled by any campaign, ever. It is not per-campaign and it cannot be overridden from a run.",
  },
];

export function SafetySection() {
  return (
    <section id="safety" className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          eyebrow="Safety"
          title="The guards fail closed."
          sub="CallFlow places real phone calls, so every guard is on until you deliberately turn it off — and each one is visible on the screen where you start a run."
        />
      </Reveal>

      <Reveal delayMs={80} className="mt-8">
        <SafetyBar guards={DEMO_GUARDS} />
      </Reveal>

      <Reveal delayMs={120} className="mt-8">
        <dl className="grid gap-x-8 gap-y-6 border-t border-rule pt-8 sm:grid-cols-2 lg:grid-cols-3">
          {GUARDS_EXPLAINED.map((guard) => (
            <div key={guard.name} className="flex flex-col gap-1.5">
              <dt className="flex flex-wrap items-baseline gap-2">
                <span className="text-h4 font-medium text-text">{guard.name}</span>
                <span className="eyebrow text-text-mute">{guard.behaviour}</span>
              </dt>
              <dd className="text-small text-text-dim">{guard.detail}</dd>
            </div>
          ))}
        </dl>
      </Reveal>
    </section>
  );
}
