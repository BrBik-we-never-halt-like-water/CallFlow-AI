/**
 * Lamp semantics - the mapping from what happened on a call to which lamp
 * lights.
 *
 * This mapping is the product's core promise made mechanical: in a normal call
 * log a delighted customer and a furious one both read `completed`. Here they
 * are different colours. Keeping the mapping in one module means every surface
 * agrees on what a colour means.
 *
 * Colour with meaning is reserved for meaning: these five colours communicate
 * call state and nothing else. They are never used for buttons, links,
 * headings, borders, hovers, or decoration.
 */

import type { Disposition, Outcome, RunStatus } from './api';

export type LampState = 'off' | 'ice' | 'brass' | 'jade' | 'flare';

export interface LampSpec {
  state: LampState;
  /**
   * A slow pulse for a state that is still moving: a run that hasn't
   * finished, or a call queued for retry. A settled or idle state never
   * pulses - the animation itself is the claim that something is happening.
   */
  pulse?: boolean;
  /** Human label. Always present, because colour is never the only carrier. */
  label: string;
  /** Optional target so a lamp can open the call it represents. */
  href?: string;
}

export const LAMP_LABELS: Record<LampState, string> = {
  off: 'Queued',
  // Not currently assigned by any disposition - reserved for a future
  // "scheduled, not yet dialling" state rather than retired outright. The
  // comment used to sit a line higher, against `off`, which *is* assigned
  // (`skipped`, and the fallback): the one label here that means nothing yet
  // read as the one label that was load-bearing.
  ice: 'Scheduled',
  brass: 'In conversation',
  jade: 'Closed',
  flare: 'Needs a person',
};

/** Which lamp a settled outcome gets. */
export function lampForOutcome(outcome: Outcome): LampSpec {
  return lampForDisposition(outcome.disposition);
}

export function lampForDisposition(disposition: Disposition): LampSpec {
  switch (disposition) {
    case 'in_flight':
      return { state: 'brass', label: 'In conversation' };
    case 'auto_closed':
      return { state: 'jade', label: 'Auto-closed - clean outcome' };
    case 'escalated':
      return { state: 'flare', label: 'Needs a person' };
    case 'retry':
      return { state: 'brass', pulse: true, label: 'Queued for retry' };
    case 'unreachable':
      return { state: 'flare', label: "Couldn't be reached" };
    case 'skipped':
      return { state: 'off', label: 'Skipped by a safety guard' };
    default:
      return { state: 'off', label: 'Queued' };
  }
}

/**
 * A run's own batch-level status - distinct from any one call's disposition.
 *
 * Re-exported from `api.ts` rather than declared here a second time. The union
 * is the same one the API sends and the database constrains, and two copies of
 * it is how a fourth value gets added in one place and silently not the other.
 */
export type { RunStatus };

const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  stopped: 'Stopped',
};

/**
 * Which lamp a run's own status gets. `lampForOutcome` is per call; this is
 * the run as a whole, so every list that shows a run's status reads the same
 * colour and the same words instead of each re-deriving them.
 *
 * `stopping` is passed separately rather than being a fifth status, because it
 * is not one: it is `running` plus somebody having pressed Stop, derived
 * server-side (`domain/run_state.is_stopping`). Rendering it needs both facts,
 * so both arrive.
 */
export function lampForRunStatus(
  status: RunStatus,
  stopping = false,
): LampSpec {
  if (stopping) {
    // Still brass and still pulsing, because calls really are still in
    // progress - the label is what changes. A run winding down is not idle and
    // must not look it.
    return { state: 'brass', pulse: true, label: 'Stopping' };
  }
  switch (status) {
    case 'running':
      return { state: 'brass', pulse: true, label: RUN_STATUS_LABELS.running };
    case 'failed':
      return { state: 'flare', label: RUN_STATUS_LABELS.failed };
    case 'completed':
      return { state: 'jade', label: RUN_STATUS_LABELS.completed };
    case 'stopped':
      // Deliberately not jade and deliberately not flare. A stopped run did not
      // finish its list, so the "clean outcome" colour would be a success state
      // for something that did not happen (CLAUDE.md #9) - and nothing went
      // wrong either, so the failure colour would be just as untrue. `off` is
      // the honest one: this run is over and did not complete.
      return { state: 'off', label: RUN_STATUS_LABELS.stopped };
  }
}

/**
 * Build the strip for a run: one lamp per contact, settled results first, then
 * dim lamps for everything still queued. The strip is the progress indicator -
 * there is no progress bar anywhere in this product.
 */
export function stripForRun(outcomes: Outcome[], total: number): LampSpec[] {
  const settled = outcomes.map(lampForOutcome);
  const queued = Math.max(0, total - settled.length);
  return [
    ...settled,
    ...Array.from({ length: queued }, () => ({
      state: 'off' as const,
      label: 'Queued',
    })),
  ];
}

export interface LampCounts {
  closed: number;
  retry: number;
  needsPerson: number;
  queued: number;
  settled: number;
  total: number;
}

export function countLamps(lamps: LampSpec[]): LampCounts {
  const counts: LampCounts = {
    closed: 0,
    retry: 0,
    needsPerson: 0,
    queued: 0,
    settled: 0,
    total: lamps.length,
  };

  for (const lamp of lamps) {
    if (lamp.state === 'off') counts.queued += 1;
    else if (lamp.state === 'jade') counts.closed += 1;
    else if (lamp.state === 'flare') counts.needsPerson += 1;
    else if (lamp.state === 'brass' && lamp.pulse) counts.retry += 1;
  }

  counts.settled = counts.total - counts.queued;
  return counts;
}

/**
 * One summarising sentence for the whole strip.
 *
 * A screen reader gets this, not twenty individual lamp labels - the strip is a
 * single piece of information, and reading it out lamp by lamp would make it
 * unusable.
 */
export function describeStrip(lamps: LampSpec[]): string {
  const c = countLamps(lamps);
  const parts: string[] = [];
  if (c.closed) parts.push(`${c.closed} closed`);
  if (c.retry) parts.push(`${c.retry} queued for retry`);
  if (c.needsPerson) parts.push(`${c.needsPerson} need a person`);
  if (c.queued) parts.push(`${c.queued} not yet dialled`);

  const noun = c.total === 1 ? 'call' : 'calls';
  if (parts.length === 0) return `${c.total} ${noun}`;
  return `${c.total} ${noun}: ${parts.join(', ')}`;
}
