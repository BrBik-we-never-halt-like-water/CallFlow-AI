'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/cn';
import type { LampState } from '@/lib/lamp';

export type LampSize = 'sm' | 'md' | 'lg';

const SIZE_PX: Record<LampSize, number> = { sm: 6, md: 10, lg: 14 };

/**
 * Colour is driven through a CSS variable rather than a Tailwind class so the same
 * value feeds both the fill and the halo (`--lamp-halo-color`), keeping a lamp's light
 * the same colour as the lamp.
 */
const COLOR_VAR: Record<LampState, string> = {
  off: 'var(--lamp-off)',
  ice: 'var(--lamp-ice)',
  brass: 'var(--lamp-brass)',
  jade: 'var(--lamp-jade)',
  flare: 'var(--lamp-flare)',
};

export interface LampProps {
  state: LampState;
  size?: LampSize;
  /** Slow pulse for a state that's still moving - in progress, or queued for retry. */
  pulse?: boolean;
  /**
   * Accessible name. Omit only when an ancestor already names this lamp - a
   * LampStrip labels itself as a whole, so its lamps are decorative.
   */
  label?: string;
  /**
   * Settle once on first paint instead of waiting for a state change. The strip
   * uses this to run its left-to-right entrance.
   */
  settleOnMount?: boolean;
  /** Stagger offset for a sequenced entrance. */
  delayMs?: number;
  className?: string;
}

/**
 * A single status lamp.
 *
 * On a state change it performs one "relay settle" - a fast flicker, then hold, with a
 * soft halo fading in at the end. It never loops. An idle lamp does not animate at all,
 * and an `off` lamp never animates or glows, because an unlit lamp has nothing to
 * announce.
 */
export function Lamp({
  state,
  size = 'md',
  pulse = false,
  label,
  settleOnMount = false,
  delayMs = 0,
  className,
}: LampProps) {
  const px = SIZE_PX[size];
  const isLit = state !== 'off';

  // Remounting the inner span replays the CSS animation from the start, which is what
  // makes a state change read as a relay closing rather than a colour swap. The first
  // paint deliberately does not animate - the strip's stagger owns the entrance.
  const [settleKey, setSettleKey] = useState(0);
  const previous = useRef(state);
  const mounted = useRef(false);

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      previous.current = state;
      return;
    }
    if (previous.current !== state) {
      previous.current = state;
      // Inside an effect but not a synchronous state write on mount: this only runs on
      // an actual change, which is the external event the lamp is reacting to.
      setSettleKey((k) => k + 1);
    }
  }, [state]);

  return (
    <span
      className={cn('relative inline-flex shrink-0', className)}
      style={{ width: px, height: px }}
      {...(label
        ? { role: 'img', 'aria-label': label }
        : { 'aria-hidden': true as const })}
    >
      <span
        key={settleKey}
        className={cn(
          'block h-full w-full rounded-full',
          isLit && (settleKey > 0 || settleOnMount) && 'lamp-settle',
          isLit && settleKey === 0 && !settleOnMount && 'lamp-lit',
          // The pulse layers on only once the settle has finished, so the two
          // animations never fight over opacity.
          isLit && pulse && settleKey === 0 && !settleOnMount && 'lamp-pulse',
        )}
        style={{
          background: COLOR_VAR[state],
          // Only a lit lamp gets a halo; `off` resolves to transparent.
          ['--lamp-halo-color' as string]: isLit
            ? `color-mix(in oklab, ${COLOR_VAR[state]} 22%, transparent)`
            : 'transparent',
          ...(settleOnMount && delayMs > 0
            ? { animationDelay: `${delayMs}ms` }
            : null),
        }}
      />
    </span>
  );
}
