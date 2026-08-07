"use client";

import Link from "next/link";
import { cn } from "@/lib/cn";
import { Popover } from "@/components/ui/disclosure";
import type { Health } from "@/lib/api";

export interface Guard {
  id: string;
  label: string;
  /** The guard's current setting. `null` means the guard is off. */
  value: string | null;
  /** One sentence on what this guard does. */
  explanation: string;
  settingsHref: string;
}

/**
 * The four active guards, always visible above anything that can start a run.
 *
 * A guard that is off renders in flare with the word `OFF`, because an unguarded
 * configuration should look uncomfortable. That is the entire design intent: the
 * bar is not a status readout, it is a nudge that the operator reads every single
 * time they are about to dial real people.
 */
export function SafetyBar({
  guards,
  className,
}: {
  guards: Guard[];
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 rounded-md border border-rule bg-surface-sunken p-2",
        className,
      )}
    >
      <span className="eyebrow px-1 text-text-mute">Guards</span>
      {guards.map((guard) => (
        <GuardChip key={guard.id} guard={guard} />
      ))}
    </div>
  );
}

function GuardChip({ guard }: { guard: Guard }) {
  const off = guard.value === null;

  return (
    <Popover
      trigger={
        <button
          type="button"
          className={cn(
            "inline-flex cursor-pointer items-center gap-1.5 rounded-xs border px-2 py-1",
            "font-mono text-label uppercase tracking-[0.14em]",
            "transition-colors duration-(--dur-micro)",
            off
              ? "border-[color-mix(in_oklab,var(--lamp-flare)_35%,transparent)] bg-[color-mix(in_oklab,var(--lamp-flare)_10%,transparent)] text-lamp-flare-text"
              : "border-rule bg-surface-raised text-text-dim hover:text-text",
          )}
        >
          <span>{guard.label}</span>
          <span className={cn("tabular-nums", off ? "font-medium" : "text-text")}>
            {guard.value ?? "OFF"}
          </span>
        </button>
      }
    >
      <div className="flex flex-col gap-2">
        <p className="text-small text-text">{guard.explanation}</p>
        {off ? (
          <p className="text-small text-lamp-flare-text">
            This guard is off. Nothing is stopping a run from reaching numbers you did
            not mean to call.
          </p>
        ) : null}
        <Link
          href={guard.settingsHref}
          className="w-fit text-small font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
        >
          Change this in Settings
        </Link>
      </div>
    </Popover>
  );
}

/**
 * Builds the guard list from what the service reports.
 *
 * Where the service does not expose a value, the guard is reported as off rather
 * than guessed at — a safety indicator that shows a reassuring default it cannot
 * actually confirm is worse than one that admits it does not know.
 */
export function guardsFromHealth(health: Health | null): Guard[] {
  const limits = health?.limits;

  return [
    {
      id: "allowlist",
      label: "Allowlist",
      value: health?.allowlist_active ? "ON" : null,
      explanation:
        "While the allowlist has any number on it, those are the only numbers a run may dial. Everything else is skipped before it rings.",
      settingsHref: "/app/settings/safety",
    },
    {
      id: "ceiling",
      label: "Ceiling",
      value: health?.max_calls_per_run ? `${health.max_calls_per_run}/RUN` : null,
      explanation:
        "A hard cap on how many real calls one run may place. The run stops at the ceiling rather than working through the rest of your list.",
      settingsHref: "/app/settings/safety",
    },
    {
      id: "rate",
      label: "Rate",
      value: limits
        ? `${limits.per_window}/${formatWindow(limits.window_minutes)}`
        : null,
      explanation:
        "Paces how fast calls go out, so a run reaches people at a human rhythm instead of arriving as a burst.",
      settingsHref: "/app/settings/safety",
    },
    {
      id: "window",
      label: "Window",
      // Not built yet — see ISSUES.md #20. This used to show a hardcoded
      // "09:00–20:00 IST" as if it were real and enforced; `null` is the
      // honest value for a guard with no backing implementation at all,
      // and renders exactly like any other guard the service can't confirm.
      value: null,
      explanation:
        "Restricting calls to certain hours isn't enforced yet — a run can dial at any time of day until this ships.",
      settingsHref: "/app/settings/safety",
    },
  ];
}

function formatWindow(minutes: number): string {
  if (minutes % 60 === 0) {
    const hours = minutes / 60;
    return hours === 1 ? "HR" : `${hours}HR`;
  }
  return `${minutes}MIN`;
}
