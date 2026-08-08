/**
 * Lamp semantics — the mapping from what happened on a call to which lamp
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

import type { Disposition, Outcome } from "./api";

export type LampState = "off" | "ice" | "brass" | "jade" | "flare";

export interface LampSpec {
  state: LampState;
  /** A slow pulse. Reserved for "queued for retry" — bad timing, not bad mood. */
  pulse?: boolean;
  /** Human label. Always present, because colour is never the only carrier. */
  label: string;
  /** Optional target so a lamp can open the call it represents. */
  href?: string;
}

export const LAMP_LABELS: Record<LampState, string> = {
  // Not currently assigned by any disposition — reserved for a future
  // "scheduled, not yet dialling" state rather than retired outright.
  off: "Queued",
  ice: "Scheduled",
  brass: "In conversation",
  jade: "Closed",
  flare: "Needs a person",
};

/** Which lamp a settled outcome gets. */
export function lampForOutcome(outcome: Outcome): LampSpec {
  return lampForDisposition(outcome.disposition);
}

export function lampForDisposition(disposition: Disposition): LampSpec {
  switch (disposition) {
    case "in_flight":
      return { state: "brass", label: "In conversation" };
    case "auto_closed":
      return { state: "jade", label: "Auto-closed — clean outcome" };
    case "escalated":
      return { state: "flare", label: "Needs a person" };
    case "retry":
      return { state: "brass", pulse: true, label: "Queued for retry" };
    case "unreachable":
      return { state: "flare", label: "Couldn't be reached" };
    case "skipped":
      return { state: "off", label: "Skipped by a safety guard" };
    default:
      return { state: "off", label: "Queued" };
  }
}

/**
 * Build the strip for a run: one lamp per contact, settled results first, then
 * dim lamps for everything still queued. The strip is the progress indicator —
 * there is no progress bar anywhere in this product.
 */
export function stripForRun(outcomes: Outcome[], total: number): LampSpec[] {
  const settled = outcomes.map(lampForOutcome);
  const queued = Math.max(0, total - settled.length);
  return [
    ...settled,
    ...Array.from({ length: queued }, () => ({ state: "off" as const, label: "Queued" })),
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
    if (lamp.state === "off") counts.queued += 1;
    else if (lamp.state === "jade") counts.closed += 1;
    else if (lamp.state === "flare") counts.needsPerson += 1;
    else if (lamp.state === "brass" && lamp.pulse) counts.retry += 1;
  }

  counts.settled = counts.total - counts.queued;
  return counts;
}

/**
 * One summarising sentence for the whole strip.
 *
 * A screen reader gets this, not twenty individual lamp labels — the strip is a
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

  const noun = c.total === 1 ? "call" : "calls";
  if (parts.length === 0) return `${c.total} ${noun}`;
  return `${c.total} ${noun}: ${parts.join(", ")}`;
}
