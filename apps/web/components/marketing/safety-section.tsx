import type { Icon } from "@phosphor-icons/react";
import {
  CheckCircleIcon,
  CoinsIcon,
  EyeSlashIcon,
  LockKeyIcon,
  ProhibitIcon,
  StackIcon,
} from "@phosphor-icons/react/dist/ssr";
import { SectionHeading } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";

/**
 * Safety, shown rather than described - and only the guards the code enforces.
 *
 * This section used to render an allowlist, a per-run ceiling and a rate limit
 * as live values. Those guards were deliberately removed from the product
 * (ISSUES.md #178; `domain/safety.py`'s own docstring), which made the panel a
 * success state for something that does not happen - the exact bug class
 * CLAUDE.md #9 exists to prevent. What is listed now is what runs: the
 * suppression gate before every dial, row validation, the fail-closed run
 * gate, both credit checks, masking, and RLS. Every quoted message below is
 * the product's real string, verbatim from the code that raises it.
 */

const GUARDS: { icon: Icon; name: string; behaviour: string; detail: string }[] = [
  {
    icon: ProhibitIcon,
    name: "Suppression list",
    behaviour: "Before every dial",
    detail:
      "The per-dial gate. Anyone on your list is never dialled — by any agent, in any run. Add someone once and it holds everywhere.",
  },
  {
    icon: CheckCircleIcon,
    name: "Row validation",
    behaviour: "Before a row queues",
    detail:
      "Every number is E.164-validated when the list is loaded. An invalid row is flagged and skipped with its reason, never guessed at.",
  },
  {
    icon: StackIcon,
    name: "The run gate",
    behaviour: "Fails closed",
    detail:
      "A run that can't dial safely doesn't start: a missing provider leg, a missing key, no connected number — each refusal names the exact fix.",
  },
  {
    icon: CoinsIcon,
    name: "Credit checks",
    behaviour: "Org and teammate",
    detail:
      "Integer paise, metered per second, on an append-only ledger. The org's balance and the starting teammate's own allocation both have to clear.",
  },
  {
    icon: EyeSlashIcon,
    name: "Masked numbers",
    behaviour: "Everywhere",
    detail:
      "Numbers render masked through one shared formatter. Revealing one is a separate, permissioned, audited action — and contacts are never stored at all.",
  },
  {
    icon: LockKeyIcon,
    name: "Org isolation",
    behaviour: "Enforced by the database",
    detail:
      "Row-level security on every tenant table, enforced by Postgres itself and held by cross-tenant tests that hit the database directly.",
  },
];

/**
 * What a tripped guard actually says. A guard nobody can see the output of is
 * a promise, not a feature. Every message here is verbatim from the code:
 * `domain/spreadsheet.py`, `domain/safety.py`, `services/run_dispatch.py`.
 */
const WHEN_A_GUARD_TRIPS: { trigger: string; message: string }[] = [
  {
    trigger: "A row fails validation",
    message: "Not a valid E.164 number - try +919876543210.",
  },
  {
    // The number inside the real message is masked by `domain/safety.mask()`;
    // this one is a reserved fictional number (+1 555 0142) through that exact
    // masking, so the example can never reach a real person.
    trigger: "A number is suppressed",
    message: "+1*****42 opted out and is on the suppression list",
  },
  {
    trigger: "An agent is missing a leg",
    message: "This agent has no tts provider set. Finish setting it up in Agents, then start the run again.",
  },
  {
    trigger: "A key is missing",
    message: "No API key for Sarvam. Connect it in Integrations, then start the run again.",
  },
];

export function SafetySection() {
  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          eyebrow="Guards"
          title="The guards fail closed."
          sub="Real calls go out, so this list holds itself to one rule: if it isn't enforced in code, it isn't on this page."
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
                    <span className="eyebrow text-text-mute">{guard.behaviour}</span>
                  </dt>
                  <dd className="text-small text-text-dim">{guard.detail}</dd>
                </div>
              </div>
            );
          })}
        </dl>
      </Reveal>

      <Reveal delayMs={140} className="mt-(--deck-gap)">
        <div className="card-raised p-6 sm:p-7">
          <h3 className="text-h4 font-medium text-text">When a guard trips, it says so.</h3>
          <p className="mt-1.5 text-small text-text-dim">
            Verbatim from the code that raises them — the run keeps going where it
            safely can, and the row says why it didn&apos;t.
          </p>

          <ul className="mt-5 flex flex-col gap-2.5">
            {WHEN_A_GUARD_TRIPS.map(({ trigger, message }) => (
              <li
                key={trigger}
                className="flex flex-col gap-1 rounded-md bg-surface-sunken/70 px-4 py-3 sm:flex-row sm:items-baseline sm:gap-4"
              >
                <span className="shrink-0 font-mono text-label tracking-wider text-text-mute uppercase sm:w-56">
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
