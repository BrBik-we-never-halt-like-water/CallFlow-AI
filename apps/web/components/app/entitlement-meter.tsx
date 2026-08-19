/**
 * One plan limit, and how much of it is used.
 *
 * Domain-aware, so it lives here rather than in `components/ui/` - it knows what
 * `null` means on an entitlement, which is the one thing a generic meter must not.
 */

'use client';

import { Meter } from '@/components/ui/meter';
import { formatNumber } from '@/lib/format';

export interface EntitlementMeterProps {
  label: string;
  used: number;
  /** `null` is unlimited. Never a sentinel, and never confused with `0`. */
  limit: number | null;
  /** Shown under the bar when the limit is reached, e.g. how to raise it. */
  atLimitHint?: string;
}

export function EntitlementMeter({ label, used, limit, atLimitHint }: EntitlementMeterProps) {
  const unlimited = limit === null;
  // `>=`, not `>`: at the ceiling you already cannot create another, so the
  // interface should say so before someone clicks and gets a 402 back.
  const atLimit = !unlimited && used >= limit;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-small text-text-dim">{label}</span>
        <span className="font-mono text-small tabular-nums text-text">
          {formatNumber(used)}
          <span className="text-text-mute">
            {unlimited ? ' · unlimited' : ` / ${formatNumber(limit)}`}
          </span>
        </span>
      </div>

      {/* An unlimited allowance has no bar to draw. A full-width bar would read
          as "you are at your limit", and an empty one as "you have used nothing"
          - both wrong, so the number stands alone instead. */}
      {unlimited ? null : <Meter value={used} max={limit} label={label} />}

      {atLimit && atLimitHint ? (
        <p className="text-small text-text-mute">{atLimitHint}</p>
      ) : null}
    </div>
  );
}
