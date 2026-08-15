import type { Icon } from "@phosphor-icons/react";
import {
  CheckCircleIcon,
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
 * Every guard is on: one could be switched off in the product, and the design's
 * whole claim is that an unguarded configuration looks uncomfortable.
 *
 * This was two bands - a strip of three settings cards above a glossary
 * explaining five guards - which made the reader compare "Allowlist / 1 number"
 * against "Allowlist / Fails closed" and work out that they were the same guard
 * twice. The settings are now the `value` on the three entries that have one,
 * so the concrete number sits with the sentence that explains it.
 */

const GUARDS: { icon: Icon; name: string; behaviour: string; value?: string; detail: string }[] = [
  {
    icon: CheckCircleIcon,
    name: "Validation first",
    behaviour: "Before any dial",
    detail: "Rows are checked and gates walked before anything dials. A failing row says why.",
  },
  {
    icon: ListChecksIcon,
    name: "Allowlist",
    behaviour: "Fails closed",
    value: "1 number",
    detail: "With anything on it, nothing else can be reached.",
  },
  {
    icon: GaugeIcon,
    name: "Per-run ceiling",
    behaviour: "Hard stop",
    value: "25 / run",
    detail: "A run stops at the ceiling and tells you, however long the list.",
  },
  {
    icon: TimerIcon,
    name: "Rate limit",
    behaviour: "Paced",
    value: "2 / hour",
    detail: "A set rate per hour, so calls land at a human rhythm.",
  },
  {
    icon: ProhibitIcon,
    name: "Suppression list",
    behaviour: "Permanent, global",
    detail: "An opt-out is added automatically and never dialled again, by any campaign.",
  },
];

/**
 * What a tripped guard actually says.
 *
 * A guard nobody can see the output of is a promise, not a feature — the claim
 * "it fails closed" is only checkable if you know what closing looks like. These
 * are the product's real messages, in the product's own voice (CLAUDE.md §5:
 * state what happened and what to do next, never "something went wrong"), which
 * is also the fastest way to show that a skip is specific rather than a shrug.
 */
const WHEN_A_GUARD_TRIPS: { trigger: string; message: string }[] = [
  {
    trigger: "A row fails validation",
    message: "Not a valid E.164 number — try +919876543210.",
  },
  {
    trigger: "The run reaches its ceiling",
    message: "This run hit the per-run ceiling of 3 calls and stopped.",
  },
  {
    trigger: "A number is on the suppression list",
    message: "Skipped — this person opted out. They are never dialled again, by any campaign.",
  },
];

export function SafetySection() {
  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          title="The guards fail closed."
          sub="Real calls go out, so every guard is on by default."
        />
      </Reveal>

      <Reveal delayMs={80} className="mt-(--deck-gap)">
        <dl className="grid gap-x-8 gap-y-(--deck-gap) border-t border-rule pt-(--deck-gap) sm:grid-cols-2 lg:grid-cols-3">
          {GUARDS.map((guard) => {
            const GuardIcon = guard.icon;
            return (
              <div key={guard.name} className="flex gap-3">
                <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-sunken text-text-dim">
                  <GuardIcon aria-hidden weight="light" className="size-5" />
                </span>
                <div className="flex flex-col gap-1.5">
                  <dt className="flex flex-wrap items-baseline gap-2">
                    <span className="text-h4 font-medium text-text">{guard.name}</span>
                    {/* A chip, not bare text: name, setting and behaviour are
                        three different kinds of thing on one line, and without
                        an edge the middle one reads as part of whichever
                        neighbour the eye reaches first. */}
                    {guard.value ? (
                      <span className="rounded bg-surface-sunken px-1.5 py-0.5 font-mono text-label tabular-nums text-text-dim">
                        {guard.value}
                      </span>
                    ) : null}
                    <span className="eyebrow text-text-mute">{guard.behaviour}</span>
                  </dt>
                  <dd className="text-small text-text-dim">{guard.detail}</dd>
                </div>
              </div>
            );
          })}
        </dl>
      </Reveal>

      <Reveal delayMs={120} className="mt-(--deck-gap)">
        <div className="card-raised p-6 sm:p-7">
          <h3 className="text-h4 font-medium text-text">When a guard trips, it says so.</h3>
          <p className="mt-1.5 text-small text-text-dim">
            The row is skipped, not the list.
          </p>

          <ul className="mt-5 flex flex-col gap-2.5">
            {WHEN_A_GUARD_TRIPS.map(({ trigger, message }) => (
              <li
                key={trigger}
                className="flex flex-col gap-1 rounded-md bg-surface-sunken/70 px-4 py-3 sm:flex-row sm:items-baseline sm:gap-4"
              >
                <span className="shrink-0 font-mono text-label tracking-wider text-text-mute uppercase sm:w-64">
                  {trigger}
                </span>
                <span className="text-small text-text">{message}</span>
              </li>
            ))}
          </ul>
        </div>
      </Reveal>
    </section>
  );
}
