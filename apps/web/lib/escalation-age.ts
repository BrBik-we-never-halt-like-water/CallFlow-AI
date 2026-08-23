/**
 * How long somebody has been waiting for a callback, as a thing the interface
 * can act on rather than a timestamp to read.
 *
 * The worklist already sorts oldest-first, and the reason is stated on the page:
 * the oldest escalation is the most expensive one, because somebody was
 * frustrated, nobody has called them back, and every hour makes the callback
 * harder. But sort order alone only says "this one is older than that one" - it
 * cannot say *this has gone on too long*, which is the thing that should make
 * someone pick an item up now rather than after lunch.
 *
 * Pure, and here rather than in a component, so the thresholds are one edit and
 * the rule is testable without rendering anything (CLAUDE.md: business logic in
 * `lib/` as a pure function, never in a React component).
 *
 * **Deliberately carries no colour.** Every other severity signal in this
 * product is a lamp, and the five lamp colours mean call state and nothing else
 * (CLAUDE.md non-negotiable #10) - an escalation's *age* is a different axis
 * from what happened on the call, so borrowing brass or flare for it would make
 * two unrelated things share a vocabulary. The urgency is carried by an explicit
 * word instead, which also means it reaches a screen reader exactly as it
 * reaches a sighted reader.
 */

/** Waiting long enough to matter. Ordered, least to most urgent. */
export type EscalationUrgency = 'fresh' | 'ageing' | 'overdue';

const HOUR_MS = 60 * 60 * 1000;

/**
 * Four hours, then twenty-four.
 *
 * Not arbitrary, but not a promise either - there is no SLA field on an
 * organisation yet, so these are the product's default reading of "a callback
 * somebody is still expecting". Four hours is about a working half-day: past it,
 * an item has survived a normal stretch of attention without anyone taking it.
 * Twenty-four means the person on the other end has been waiting since
 * yesterday, which is the point at which the callback stops being a follow-up
 * and starts being an apology.
 *
 * When per-organisation SLAs exist, this is the one place that changes.
 */
export const AGEING_AFTER_HOURS = 4;
export const OVERDUE_AFTER_HOURS = 24;

/**
 * How urgent an open escalation has become.
 *
 * `now` is injectable so the rule can be tested against fixed instants rather
 * than against whatever the clock says while the suite runs.
 */
export function urgencyFor(
  createdAt: string,
  now: number = Date.now(),
): EscalationUrgency {
  const waited = now - new Date(createdAt).getTime();
  // A clock skew or an unparseable date must not present as urgent - inventing
  // urgency is worse than missing it, because a queue where everything is
  // flagged is a queue where nothing is.
  if (!Number.isFinite(waited) || waited < 0) return 'fresh';
  if (waited >= OVERDUE_AFTER_HOURS * HOUR_MS) return 'overdue';
  if (waited >= AGEING_AFTER_HOURS * HOUR_MS) return 'ageing';
  return 'fresh';
}

/** The word shown beside an item. `null` for fresh - a queue that labels every
 *  row as urgent has said nothing. */
export function urgencyLabel(urgency: EscalationUrgency): string | null {
  switch (urgency) {
    case 'overdue':
      return 'Overdue';
    case 'ageing':
      return 'Waiting a while';
    case 'fresh':
      return null;
  }
}

/** How many of a set have gone past each threshold, for the queue's summary. */
export function countUrgency(
  createdAts: string[],
  now: number = Date.now(),
): { overdue: number; ageing: number } {
  let overdue = 0;
  let ageing = 0;
  for (const createdAt of createdAts) {
    const urgency = urgencyFor(createdAt, now);
    if (urgency === 'overdue') overdue += 1;
    else if (urgency === 'ageing') ageing += 1;
  }
  return { overdue, ageing };
}
