'use client';

import Link from 'next/link';
import { cn } from '@/lib/cn';
import { Popover } from '@/components/ui/disclosure';
import type { RunSafetySnapshot, SafetySettings } from '@/lib/api';

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
        'flex flex-wrap items-center gap-2 rounded-md border border-rule bg-surface-sunken p-2',
        className,
      )}
    >
      <span className="px-1 text-small font-bold text-text-mute">Guards</span>
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
            'inline-flex cursor-pointer items-center gap-1.5 rounded-xs border px-2 py-1',
            'font-mono text-label uppercase tracking-[0.14em]',
            'transition-colors duration-(--dur-micro)',
            off
              ? 'border-[color-mix(in_oklab,var(--lamp-flare)_35%,transparent)] bg-[color-mix(in_oklab,var(--lamp-flare)_10%,transparent)] text-lamp-flare-text'
              : 'border-rule bg-surface-raised text-text-dim hover:text-text',
          )}
        >
          <span>{guard.label}</span>
          <span
            className={cn('tabular-nums', off ? 'font-medium' : 'text-text')}
          >
            {guard.value ?? 'OFF'}
          </span>
        </button>
      }
    >
      <div className="flex flex-col gap-2">
        <p className="text-small text-text">{guard.explanation}</p>
        {off ? (
          <p className="text-small text-lamp-flare-text">
            This guard is off. Nothing is stopping a run from reaching numbers
            you did not mean to call.
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
 * Builds the guard list from this organisation's own safety settings.
 *
 * Where the value isn't known yet (still loading, or the service didn't respond),
 * the guard is reported as off rather than guessed at - a safety indicator that
 * shows a reassuring default it cannot actually confirm is worse than one that
 * admits it does not know.
 */
export function guardsFromSafety(settings: SafetySettings | null): Guard[] {
  return [
    {
      id: 'allowlist',
      label: 'Allowlist',
      value: settings && settings.allowlist.length > 0 ? 'ON' : null,
      explanation:
        'While the allowlist has any number on it, those are the only numbers a run may dial. Everything else is skipped before it rings.',
      settingsHref: '/app/settings/safety',
    },
    {
      id: 'ceiling',
      label: 'Ceiling',
      value: settings ? `${settings.max_calls_per_run}/RUN` : null,
      explanation:
        'A hard cap on how many real calls one run may place. The run stops at the ceiling rather than working through the rest of your list.',
      settingsHref: '/app/settings/safety',
    },
    {
      id: 'rate',
      label: 'Rate',
      value: settings
        ? `${settings.calls_per_window}/${formatWindow(settings.window_minutes)}`
        : null,
      explanation:
        'Paces how fast calls go out, so a run reaches people at a human rhythm instead of arriving as a burst.',
      settingsHref: '/app/settings/safety',
    },
    {
      id: 'window',
      label: 'Window',
      // Not built yet - see ISSUES.md #20. This used to show a hardcoded
      // "09:00–20:00 IST" as if it were real and enforced; `null` is the
      // honest value for a guard with no backing implementation at all,
      // and renders exactly like any other guard the service can't confirm.
      value: null,
      explanation:
        "Restricting calls to certain hours isn't enforced yet - a run can dial at any time of day until this ships.",
      settingsHref: '/app/settings/safety',
    },
  ];
}

/**
 * Builds the guard list from a run's own permanent safety snapshot - what
 * actually governed that run, not this organisation's current settings
 * (which may have changed since). Same chip rendering as `guardsFromSafety`
 * so a past run's guards read identically to a live one; only the source of
 * truth differs.
 */
export function guardsFromSnapshot(snapshot: RunSafetySnapshot): Guard[] {
  return [
    {
      id: 'allowlist',
      label: 'Allowlist',
      value: snapshot.allowlist.length > 0 ? 'ON' : null,
      explanation:
        'While the allowlist had any number on it, those were the only numbers this run could dial.',
      settingsHref: '/app/settings/safety',
    },
    {
      id: 'ceiling',
      label: 'Ceiling',
      value: `${snapshot.max_calls_per_run}/RUN`,
      explanation:
        'The hard cap on how many real calls this run could place.',
      settingsHref: '/app/settings/safety',
    },
    {
      id: 'rate',
      label: 'Rate',
      value: `${snapshot.calls_per_window}/${formatWindow(snapshot.window_minutes)}`,
      explanation: 'How fast this run was allowed to place calls.',
      settingsHref: '/app/settings/safety',
    },
  ];
}

function formatWindow(minutes: number): string {
  if (minutes % 60 === 0) {
    const hours = minutes / 60;
    return hours === 1 ? 'HR' : `${hours}HR`;
  }
  return `${minutes}MIN`;
}
