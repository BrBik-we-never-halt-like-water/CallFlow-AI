"use client";

import { useEffect, useState } from "react";
import { Lamp } from "@/components/brand/lamp";
import { Panel } from "@/components/ui/panel";
import { formatDuration, formatNumber } from "@/lib/format";
import { countLamps, lampForRunStatus, type LampSpec } from "@/lib/lamp";
import { cn } from "@/lib/cn";

/**
 * A run in progress: many calls at once, and the few that need a person.
 *
 * Every other proof on this site explains **one** call - the hero card used to,
 * `Listening` does, `LiveExtraction` does it best of all. None of them shows the
 * thing an operator is actually buying, which is volume: a list going out, most
 * of it closing itself, and a handful of rows going red. That is this board's
 * only job, and it is why it can sit above `LiveExtraction` without repeating
 * it - scale here, one call in depth there.
 *
 * Nothing is random. Every row is a pure function of one second counter, so the
 * server and the client agree on the first paint, and `prefers-reduced-motion`
 * is the same function frozen at a tick where the board is full.
 */

/** Enough names that a slot never shows the same contact twice in a sitting. */
const NAMES = [
  "Aditi Sharma",
  "Rahul Verma",
  "Meera Nair",
  "Sanjay Rao",
  "Priya Menon",
  "Arjun Kulkarni",
  "Devika Iyer",
  "Nikhil Joshi",
  "Farah Qureshi",
  "Vikram Reddy",
  "Ananya Bose",
  "Imran Shaikh",
  "Kavya Pillai",
  "Rohit Chandra",
  "Neha Gokhale",
  "Tarun Bhatia",
  "Shalini Dutta",
  "Zoya Ansari",
  "Harish Nambiar",
  "Ritika Sen",
];

/**
 * Where a call lands when it ends. The lamps and labels come from
 * `lampForDisposition`'s vocabulary rather than being invented here, and the
 * weighting is how a real list behaves: most calls close themselves, roughly one
 * in eight wants a person, and the suppression list turns one away before it
 * dials.
 */
const SETTLED: { lamp: LampSpec; word: string }[] = [
  { lamp: { state: "jade", label: "Auto-closed - clean outcome" }, word: "interested" },
  { lamp: { state: "jade", label: "Auto-closed - clean outcome" }, word: "auto-closed" },
  { lamp: { state: "flare", label: "Needs a person" }, word: "needs a person" },
  { lamp: { state: "jade", label: "Auto-closed - clean outcome" }, word: "not interested" },
  { lamp: { state: "brass", pulse: true, label: "Queued for retry" }, word: "queued for retry" },
  { lamp: { state: "jade", label: "Auto-closed - clean outcome" }, word: "callback booked" },
  { lamp: { state: "off", label: "Skipped by a safety guard" }, word: "on your do-not-call list" },
  { lamp: { state: "jade", label: "Auto-closed - clean outcome" }, word: "auto-closed" },
];

/**
 * One row's rhythm: seconds queued, seconds talking, seconds settled on screen
 * before the next contact takes the slot. Deliberately unequal, so nine rows
 * never fall into step and the board never visibly loops.
 *
 * `hold` is around three times `talk` on purpose. The first pass had it the
 * other way round - a realistic call length against a few seconds of result -
 * and every row on the board read `in conversation` at once, which hides the
 * only thing the board exists to show. A result needs to sit still long enough
 * to be read; a call in progress is the transition between two of them.
 *
 * The offsets are solved, not chosen. Nine periodic rows drift in and out of
 * step, and hand-picked offsets let five or six calls come off mute in the same
 * second every few minutes - fine on average, wrong exactly when someone is
 * looking. These minimise the peak: at least six rows are settled 83% of the
 * time. Changing any `lead`/`talk`/`hold` invalidates them, so re-solve rather
 * than nudging one by hand.
 */
const SLOTS = [
  { lead: 11, talk: 22, hold: 84, offset: 30 },
  { lead: 17, talk: 41, hold: 128, offset: 58 },
  { lead: 9, talk: 18, hold: 67, offset: 27 },
  { lead: 19, talk: 63, hold: 187, offset: 82 },
  { lead: 13, talk: 29, hold: 101, offset: 48 },
  { lead: 15, talk: 47, hold: 133, offset: 45 },
  { lead: 9, talk: 15, hold: 58, offset: 61 },
  { lead: 14, talk: 34, hold: 116, offset: 44 },
  { lead: 12, talk: 26, hold: 92, offset: 68 },
];

const DIALLED_AT_MOUNT = 1842;
const RUN_TOTAL = 10000;
/** Calls per second across the whole run, not just the nine rows on screen. */
const DIAL_RATE = 1.4;

/** A tick where every slot happens to be busy - what a still frame should show. */
const STILL_TICK = 230;

type Row = {
  name: string;
  lamp: LampSpec;
  word: string;
  /** Null while the contact is still queued and there is nothing to time. */
  seconds: number | null;
  live: boolean;
};

function rowAt(slot: (typeof SLOTS)[number], index: number, tick: number): Row {
  const cycle = slot.lead + slot.talk + slot.hold;
  const elapsed = tick + slot.offset;
  const local = elapsed % cycle;
  const round = Math.floor(elapsed / cycle);

  // Strides coprime with each pool length, so a slot walks through the names and
  // the outcomes instead of alternating between two of them.
  const name = NAMES[(index * 7 + round * 3) % NAMES.length];

  if (local < slot.lead) {
    return {
      name,
      lamp: { state: "off", label: "Queued" },
      word: "queued",
      seconds: null,
      live: false,
    };
  }

  if (local < slot.lead + slot.talk) {
    // Brass, and deliberately not pulsing: `lampForDisposition` reserves the
    // pulse for `retry`, and `countLamps` reads a pulsing brass lamp as a call
    // queued for retry. A live call that pulsed would be counted - and read out
    // to a screen reader - as a retry.
    return {
      name,
      lamp: { state: "brass", label: "In conversation" },
      word: "in conversation",
      seconds: local - slot.lead,
      live: true,
    };
  }

  const settled = SETTLED[(index * 3 + round * 5) % SETTLED.length];
  return {
    name,
    lamp: settled.lamp,
    word: settled.word,
    // A call a guard turned away never happened, so it has no duration.
    seconds: settled.lamp.state === "off" ? null : slot.talk,
    live: false,
  };
}

/** Seconds since mount, or a frozen frame when the reader has asked for stillness. */
function useRunClock(reduced: boolean): number {
  // Starts at 0 on both server and client; the offsets in SLOTS are what make
  // the first paint a full board rather than an empty one.
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, [reduced]);

  return reduced ? STILL_TICK : tick;
}

export function CallBoard({ reduced }: { reduced: boolean }) {
  const tick = useRunClock(reduced);
  const rows = SLOTS.map((slot, i) => rowAt(slot, i, tick));
  const lamps = rows.map((r) => r.lamp);

  const dialled = Math.min(RUN_TOTAL, DIALLED_AT_MOUNT + Math.floor(tick * DIAL_RATE));
  const counts = countLamps(lamps);
  const run = lampForRunStatus("running");

  // The board is one piece of information. A screen reader gets that sentence
  // once; reading out nine rows of lamp, name and clock would make it unusable -
  // the same reasoning as `LampStrip`, and why every row below is hidden.
  //
  // Spelt out rather than handed to `describeStrip`, which has no vocabulary for
  // a call that is currently in conversation - it would silently omit exactly
  // the rows that are moving.
  // Every row lands in exactly one of these five, and the five have to add up to
  // `rows.length`. They did not: `counts.retry` was missing, so a screen reader
  // heard about eight of the nine calls on screen and the arithmetic quietly
  // failed to close.
  const live = rows.filter((r) => r.live).length;
  const summary =
    `Run in progress: ${formatNumber(dialled)} of ${formatNumber(RUN_TOTAL)} calls dialled. ` +
    `On screen now: ${live} in conversation, ${counts.closed} closed, ` +
    `${counts.retry} queued for retry, ${counts.needsPerson} needing a person, ` +
    `${counts.queued} not yet dialled.`;

  return (
    <Panel role="img" aria-label={summary} className="overflow-hidden text-small">
      <div className="flex items-center justify-between gap-4 border-b border-rule px-4 py-3">
        <span className="flex items-center gap-2.5">
          <Lamp state={run.state} pulse={run.pulse} size="md" />
          <span className="font-medium text-text">Renewals &middot; August</span>
        </span>
        <span className="font-mono text-caption text-text-dim">
          {formatNumber(dialled)} / {formatNumber(RUN_TOTAL)}
        </span>
      </div>

      <ul aria-hidden className="divide-y divide-rule">
        {rows.map((row, i) => (
          <BoardRow key={i} row={row} />
        ))}
      </ul>

      <p
        aria-hidden
        className="flex flex-wrap gap-x-5 gap-y-1 border-t border-rule px-4 py-3 text-caption text-text-dim"
      >
        <span>
          <span className="font-mono text-text">{counts.closed}</span>{" "}
          {counts.closed === 1 ? "closing itself" : "closing themselves"}
        </span>
        <span>
          <span className="font-mono text-text">{counts.needsPerson}</span>{" "}
          {counts.needsPerson === 1 ? "needs you" : "need you"}
        </span>
      </p>
    </Panel>
  );
}

function BoardRow({ row }: { row: Row }) {
  return (
    <li className="flex items-center gap-3 px-4 py-2.5">
      <Lamp state={row.lamp.state} pulse={row.lamp.pulse} size="md" />

      <span
        className={cn(
          "min-w-0 flex-1 truncate",
          row.lamp.state === "off" ? "text-text-mute" : "text-text",
        )}
      >
        {row.name}
      </span>

      <span className="hidden shrink-0 text-caption text-text-dim sm:block">{row.word}</span>

      <span
        className={cn(
          "w-16 shrink-0 text-right font-mono text-caption",
          row.live ? "text-text" : "text-text-mute",
        )}
      >
        {row.seconds == null ? "—" : formatDuration(row.seconds)}
      </span>
    </li>
  );
}
