import { cn } from '@/lib/cn';

/**
 * A call, run, or escalation status: the word itself, set in its own colour.
 *
 * No dot and no pill. The lamp treatment put a coloured circle beside a
 * neutral word, so the colour carried the meaning and the word only repeated
 * it; the filled pill that replaced it turned every row of a table into a
 * row of coloured blocks, which is louder than the data it labels. What is
 * left is the smallest thing that works - the status *is* the coloured word,
 * legible to someone scanning the column and to a screen reader alike, with
 * no legend anywhere in the product.
 *
 * The `-ink` tier, not the raw hue: these sit directly on the card surface
 * now rather than on a soft backing of their own, so they need the value
 * that clears the contrast bar against it.
 */
export type StatusTone = 'success' | 'warning' | 'danger' | 'neutral';

const TONE_COLOR: Record<StatusTone, string> = {
  success: 'var(--dash-success-ink)',
  warning: 'var(--dash-warning-ink)',
  danger: 'var(--dash-danger-ink)',
  neutral: 'var(--dash-neutral-ink)',
};

/**
 * Every status string the dashboard can receive, mapped to a tone. Anything
 * unrecognised falls through to neutral rather than guessing a colour - a
 * status shown in the wrong colour is worse than one shown in grey.
 */
const STATUS_TONE: Record<string, StatusTone> = {
  completed: 'success',
  closed: 'success',
  delivered: 'success',
  active: 'success',
  running: 'warning',
  in_progress: 'warning',
  queued: 'neutral',
  pending: 'neutral',
  paused: 'warning',
  processing: 'warning',
  retried: 'warning',
  needs_person: 'danger',
  escalated: 'danger',
  failed: 'danger',
  error: 'danger',
};

/** `needs_person` -> `Needs a person`. */
function humanise(status: string): string {
  if (status === 'needs_person') return 'Needs a person';
  const spaced = status.replace(/_/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function StatusPill({
  status,
  label,
  className,
}: {
  status: string;
  /** Overrides the derived wording; the tone still comes from `status`. */
  label?: string;
  className?: string;
}) {
  const key = status.toLowerCase();
  const tone = STATUS_TONE[key] ?? 'neutral';

  return (
    <span
      className={cn(
        'inline-flex items-center whitespace-nowrap text-[0.6875rem] font-medium',
        className,
      )}
      style={{ color: TONE_COLOR[tone] }}
    >
      {label ?? humanise(key)}
    </span>
  );
}
