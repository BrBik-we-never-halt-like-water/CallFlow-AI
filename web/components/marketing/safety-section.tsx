import type { Icon } from "@phosphor-icons/react";
import {
  CheckCircleIcon,
  ClockIcon,
  GaugeIcon,
  ListChecksIcon,
  ProhibitIcon,
  TimerIcon,
} from "@phosphor-icons/react/dist/ssr";
import { SectionHeading } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";

/**
 * Safety, shown rather than described.
 *
 * The active guards are shown as a panel of real settings — the exact values a
 * run enforces — above a glossary that explains each guard. One guard could be
 * switched off in the product, and the design's whole claim is that an unguarded
 * configuration looks uncomfortable; here every guard is on, which is the point.
 */

const ACTIVE_GUARDS: { icon: Icon; label: string; value: string; note: string }[] = [
  { icon: ListChecksIcon, label: "Allowlist", value: "1 number", note: "only these dial" },
  { icon: GaugeIcon, label: "Per-run ceiling", value: "25 / run", note: "then it stops" },
  { icon: TimerIcon, label: "Rate limit", value: "2 / hour", note: "paced, not bursty" },
  { icon: ClockIcon, label: "Calling window", value: "09:00–20:00", note: "IST" },
];

const GUARDS_EXPLAINED: { icon: Icon; name: string; behaviour: string; detail: string }[] = [
  {
    icon: CheckCircleIcon,
    name: "Validation first",
    behaviour: "Before any dial",
    detail: "Every run validates rows and walks the gates before dialling; a failing row is skipped and says why.",
  },
  {
    icon: ListChecksIcon,
    name: "Allowlist",
    behaviour: "Fails closed",
    detail: "With anything on it, those are the only numbers that can be reached. Everything else is skipped.",
  },
  {
    icon: GaugeIcon,
    name: "Per-run ceiling",
    behaviour: "Hard stop",
    detail: "A run can't place more calls than the ceiling. It stops and tells you, however long the list.",
  },
  {
    icon: TimerIcon,
    name: "Rate limit",
    behaviour: "Paced",
    detail: "Calls go out at a set rate per hour, so a run reaches people at a human rhythm.",
  },
  {
    icon: ClockIcon,
    name: "Calling window",
    behaviour: "Queued outside hours",
    detail: "Outside the window nothing dials; contacts wait for the next opening.",
  },
  {
    icon: ProhibitIcon,
    name: "Suppression list",
    behaviour: "Permanent, global",
    detail: "Anyone who opts out is added automatically and never dialled again, by any campaign.",
  },
];

export function SafetySection() {
  return (
    <section id="safety" className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          eyebrow="Safety"
          title="The guards fail closed."
          sub="Real calls go out, so every guard is on by default — and visible right where you start a run."
        />
      </Reveal>

      <Reveal delayMs={80} className="mt-8">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {ACTIVE_GUARDS.map((guard) => {
            const GuardIcon = guard.icon;
            return (
              <div
                key={guard.label}
                className="surface-flow flex items-start gap-3 p-4 shadow-sm"
              >
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-sunken text-text-dim">
                  <GuardIcon aria-hidden weight="light" className="size-5" />
                </span>
                <div className="min-w-0">
                  <span className="block text-label uppercase tracking-[0.12em] text-text-mute">
                    {guard.label}
                  </span>
                  <span className="mt-1 block font-mono text-data tabular-nums text-text">
                    {guard.value}
                  </span>
                  <span className="mt-0.5 block text-label text-text-mute">{guard.note}</span>
                </div>
              </div>
            );
          })}
        </div>
      </Reveal>

      <Reveal delayMs={120} className="mt-8">
        <dl className="grid gap-x-8 gap-y-7 border-t border-rule pt-8 sm:grid-cols-2 lg:grid-cols-3">
          {GUARDS_EXPLAINED.map((guard) => {
            const GuardIcon = guard.icon;
            return (
              <div key={guard.name} className="flex gap-3">
                <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-sunken text-text-dim">
                  <GuardIcon aria-hidden weight="light" className="size-5" />
                </span>
                <div className="flex flex-col gap-1.5">
                  <dt className="flex flex-wrap items-baseline gap-2">
                    <span className="text-h4 font-medium text-text">{guard.name}</span>
                    <span className="eyebrow text-text-mute">{guard.behaviour}</span>
                  </dt>
                  <dd className="text-small text-text-dim">{guard.detail}</dd>
                </div>
              </div>
            );
          })}
        </dl>
      </Reveal>
    </section>
  );
}
