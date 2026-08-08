'use client';

import { cn } from '@/lib/cn';
import {
  countLamps,
  describeStrip,
  type LampSpec,
  type LampState,
} from '@/lib/lamp';
import { Lamp, type LampSize } from './lamp';

/** Stagger, and the point past which a sequence reveals as a group instead. */
const STAGGER_MS = 60;
const STAGGER_CAP = 12;

const GAP: Record<LampSize, string> = {
  sm: 'gap-1.5',
  md: 'gap-2',
  lg: 'gap-2.5',
};

export interface LampStripProps {
  lamps: LampSpec[];
  size?: LampSize;
  /** Mono caption, e.g. `14 of 20 settled`. */
  caption?: string;
  /** The counts line: closed · retry · needs a person. */
  counts?: boolean;
  /** Run the left-to-right entrance. Off for strips that are already settled. */
  animateIn?: boolean;
  /** Allow the row to wrap - used for the 100-call overview strip. */
  wrap?: boolean;
  /** Makes each lamp a button. Used where a lamp opens the call it represents. */
  onSelect?: (index: number, lamp: LampSpec) => void;
  className?: string;
}

/**
 * A horizontal row of lamps, one per call.
 *
 * This is the element the product is remembered by, and it is the reason the
 * rest of the interface stays quiet. It replaces the progress bar everywhere:
 * a bar says how much is done, a strip says how it went.
 *
 * Accessibility: the strip carries one summarising label for the whole row
 * ("20 calls: 9 closed, 2 queued for retry, 3 need a person"). Its lamps are
 * hidden from assistive tech, because reading out twenty individual lamps would
 * make the row unusable.
 */
export function LampStrip({
  lamps,
  size = 'md',
  caption,
  counts = false,
  animateIn = false,
  wrap = false,
  onSelect,
  className,
}: LampStripProps) {
  const summary = describeStrip(lamps);
  const c = countLamps(lamps);
  const staggered = animateIn && lamps.length <= STAGGER_CAP;

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      {caption ? <p className="eyebrow text-text-mute">{caption}</p> : null}

      <div
        role="img"
        aria-label={summary}
        className={cn('flex items-center', GAP[size], wrap && 'flex-wrap')}
      >
        {lamps.map((lamp, i) => {
          const lampEl = (
            <Lamp
              state={lamp.state}
              size={size}
              pulse={lamp.pulse}
              settleOnMount={animateIn}
              delayMs={staggered ? i * STAGGER_MS : 0}
            />
          );

          if (!onSelect) return <span key={i}>{lampEl}</span>;

          return (
            <button
              key={i}
              type="button"
              onClick={() => onSelect(i, lamp)}
              // The lamp is 6–14px, well under the 40px touch minimum, so the
              // button carries padding and a negative margin: a comfortable hit
              // target without changing the strip's spacing.
              className="-m-2 inline-flex cursor-pointer items-center justify-center rounded-full p-2 transition-colors duration-(--dur-micro) hover:bg-surface-hover"
              aria-label={`Call ${i + 1}: ${lamp.label}`}
            >
              {lampEl}
            </button>
          );
        })}
      </div>

      {counts ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-data">
          <Count state="jade" n={c.closed} label="closed" />
          <Count state="brass" n={c.retry} label="retry" pulse />
          <Count state="flare" n={c.needsPerson} label="need a person" />
        </div>
      ) : null}
    </div>
  );
}

const COUNT_TEXT: Record<LampState, string> = {
  off: 'text-lamp-off-text',
  ice: 'text-lamp-ice-text',
  brass: 'text-lamp-brass-text',
  jade: 'text-lamp-jade-text',
  flare: 'text-lamp-flare-text',
};

function Count({
  state,
  n,
  label,
  pulse,
}: {
  state: LampState;
  n: number;
  label: string;
  pulse?: boolean;
}) {
  // A zero count stays visible but drops to muted text: the operator learns the
  // shape of the row, and "0 need a person" is genuinely good news worth seeing.
  const isZero = n === 0;
  return (
    <span className="inline-flex items-center gap-1.5">
      <Lamp state={isZero ? 'off' : state} size="sm" pulse={!isZero && pulse} />
      <span
        className={cn(
          'tabular-nums',
          isZero ? 'text-text-mute' : COUNT_TEXT[state],
        )}
      >
        {n} {label}
      </span>
    </span>
  );
}
