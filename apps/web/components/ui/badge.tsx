import { cn } from '@/lib/cn';
import type { LampState } from '@/lib/lamp';

/**
 * Status badge - the label, set in its own status colour.
 *
 * No dot and no filled pill. The dot made colour the carrier and left the
 * word repeating it, and the pill turned every list into a row of coloured
 * blocks louder than the data it labelled. What is left is the smallest
 * thing that works, and it matches `StatusPill` on the dashboard so one
 * status reads identically wherever it is drawn (CLAUDE.md §4 #10).
 *
 * The text uses the `-text` alias, which resolves to the darkened `-ink`
 * variant on a light surface - the pure status colours do not clear 4.5:1
 * against paper.
 *
 * The label is never optional. Colour is not allowed to be the only carrier
 * of meaning - a colourblind operator has to be able to run this product.
 */

const TEXT: Record<LampState, string> = {
  off: 'text-lamp-off-text',
  ice: 'text-lamp-ice-text',
  brass: 'text-lamp-brass-text',
  jade: 'text-lamp-jade-text',
  flare: 'text-lamp-flare-text',
};

export function LampBadge({
  state,
  children,
  className,
}: {
  state: LampState;
  children: React.ReactNode;
  /** Accepted and ignored: there is no dot left to pulse. Kept so the
   *  existing call sites compile unchanged. */
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center whitespace-nowrap text-small leading-none font-medium',
        TEXT[state],
        className,
      )}
    >
      {children}
    </span>
  );
}

/**
 * Neutral tag. Used for structural labels - `TEMPLATE`, `SUPPRESSED`, field
 * names - where nothing about call state is being communicated and a lamp
 * colour would therefore be wrong.
 */
export function Tag({
  children,
  mono = true,
  className,
}: {
  children: React.ReactNode;
  mono?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-xs border border-rule bg-surface-sunken px-1.5 py-0.5 whitespace-nowrap text-text-dim',
        mono
          ? 'font-mono text-label uppercase tracking-[0.14em]'
          : 'text-small',
        className,
      )}
    >
      {children}
    </span>
  );
}
