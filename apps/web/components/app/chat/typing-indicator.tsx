'use client';

import { cn } from '@/lib/cn';

/**
 * "Ana is typing" - the sentence, with three dots that carry the liveness.
 *
 * Sits between the message list and the composer, in its own reserved row. The
 * row keeps its height whether or not anyone is typing, because the alternative
 * is the whole thread jumping a line every time a colleague starts and stops -
 * the reserved space costs 20px and removes a layout shift from the one surface
 * where text is being read and written at the same time.
 *
 * Announced with `aria-live="polite"`: it is worth knowing, and never worth
 * interrupting what a screen reader is already saying.
 */
export function TypingIndicator({
  /** Display names, already resolved. Ids are useless to a reader. */
  names,
  className,
}: {
  names: string[];
  className?: string;
}) {
  return (
    <div
      aria-live="polite"
      className={cn(
        'flex h-5 shrink-0 items-center gap-2 px-1 text-small',
        className,
      )}
      style={{ color: 'var(--dash-text-mute)' }}
    >
      {names.length > 0 ? (
        <>
          <span aria-hidden className="typing-dots">
            <i />
            <i />
            <i />
          </span>
          <span className="truncate">{sentence(names)}</span>
        </>
      ) : null}
    </div>
  );
}

/**
 * Names into a sentence that stays short.
 *
 * Beyond two it counts rather than lists: a busy channel would otherwise print
 * a paragraph into a 20px row, and "4 people are typing" is the whole of what a
 * reader does anything with.
 */
function sentence(names: string[]): string {
  const [first, second] = names;
  if (names.length === 1) return `${first} is typing`;
  if (names.length === 2) return `${first} and ${second} are typing`;
  return `${names.length} people are typing`;
}
