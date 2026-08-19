/**
 * A horizontal fill bar for "how much of a fixed amount is used".
 *
 * Extracted because four places had hand-rolled the same markup with slightly
 * different heights and no accessible name (`agent-editor`, `agent-metrics`, the
 * dashboard, Billing), and Billing alone now needs five of them.
 *
 * **Colourless, deliberately.** A meter shows consumption, never call, run or
 * escalation state, so it must not reach for a lamp colour - that spectrum is
 * reserved for meaning (CLAUDE.md §4 #10, `DESIGN_NOTES.md` §2). An earlier draft
 * of this file used `--flare` for "over the limit" on the reasoning that being
 * past a hard ceiling is a state worth seeing; that is exactly the rationalisation
 * the rule exists to stop, and it would have been a fourth exception alongside
 * danger buttons, toasts and error borders. Whether a limit is reached is said in
 * the text beside the bar instead, which is unambiguous and needs no hue - the
 * same call `CodeBlock` and the charts already make.
 */

'use client';

import { cn } from '@/lib/cn';

export interface MeterProps {
  value: number;
  max: number;
  /** Names the meter for a screen reader. Required - a bare bar reads as nothing. */
  label: string;
  className?: string;
}

export function Meter({ value, max, label, className }: MeterProps) {
  // `max` of 0 would divide by zero. It is a real value - a plan that includes
  // none of something - and the honest rendering is a full bar: everything you
  // were given is used, because you were given nothing.
  const safeMax = Math.max(0, max);
  const ratio = safeMax === 0 ? 1 : Math.max(0, value) / safeMax;

  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={safeMax}
      className={cn('h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken', className)}
    >
      <div
        className="h-full rounded-full bg-surface-inverse transition-[width] duration-500 ease-out"
        style={{ width: `${Math.min(100, ratio * 100)}%` }}
      />
    </div>
  );
}
