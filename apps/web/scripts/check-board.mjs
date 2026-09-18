/**
 * Guards the marketing hero's call board against the one way it fails silently:
 * looking busy instead of looking finished.
 *
 * Run with `node scripts/check-board.mjs`, or as part of `npm run lint`.
 *
 * The board's whole argument is that a list mostly closes itself and a few rows
 * need a person. Nine independent periodic rows drift in and out of step, so
 * that argument is a property of the *schedule*, not of any one frame - and the
 * way it breaks is that most rows read `in conversation` at once, which no
 * screenshot taken at the wrong second will show you. The first version of the
 * schedule failed exactly this way: correct on average, and every row live.
 *
 * Constants are read out of the component rather than restated here. Restating
 * them is how a guard ends up passing while the thing it guards is broken.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const SOURCE = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../components/marketing/call-board.tsx",
);

const HORIZON_SECONDS = 3600;

/** Ceilings, each one a failure someone would have to notice by watching. */
const LIMITS = {
  /** Above this and the board reads as "everything is mid-call". */
  maxLiveAtOnce: 5,
  /** Above this and it reads as "nothing is happening yet". */
  maxQueuedAtOnce: 4,
  /** The payoff has to be on screen most of the time someone is looking. */
  minTicksShowingEscalation: 0.5,
  /** And the claim that calls close themselves has to be visibly true. */
  minClosedShare: 0.35,
};

function fail(lines) {
  console.error("check-board: FAIL");
  for (const line of lines) console.error(`  - ${line}`);
  process.exit(1);
}

const src = readFileSync(SOURCE, "utf8");

function extract(name) {
  const block = src.match(new RegExp(`const ${name}[^=]*= \\[([\\s\\S]*?)\\n\\];`));
  if (!block) {
    fail([
      `could not find \`const ${name} = [...]\` in ${SOURCE}.`,
      "This guard reads the schedule out of the component so the two cannot drift.",
      "If the constant was renamed or reshaped, update this script to match.",
    ]);
  }
  return block[1];
}

const slots = [...extract("SLOTS").matchAll(/\{[^}]*\}/g)].map((m) => {
  const num = (key) => {
    const found = m[0].match(new RegExp(`${key}:\\s*(\\d+)`));
    if (!found) fail([`a SLOTS entry is missing \`${key}\`: ${m[0].trim()}`]);
    return Number(found[1]);
  };
  return { lead: num("lead"), talk: num("talk"), hold: num("hold"), offset: num("offset") };
});

const settledStates = [...extract("SETTLED").matchAll(/state:\s*"(\w+)"/g)].map((m) => m[1]);

if (slots.length < 5) fail([`only ${slots.length} slots parsed - expected the board's full set.`]);
if (settledStates.length === 0) fail(["no settled lamp states parsed out of SETTLED."]);

/** The component's own row derivation, in the only part that matters here. */
function phaseAt(slotIndex, tick) {
  const slot = slots[slotIndex];
  const cycle = slot.lead + slot.talk + slot.hold;
  const elapsed = tick + slot.offset;
  const local = elapsed % cycle;
  const round = Math.floor(elapsed / cycle);

  if (local < slot.lead) return "queued";
  if (local < slot.lead + slot.talk) return "live";
  return settledStates[(slotIndex * 3 + round * 5) % settledStates.length];
}

let peakLive = 0;
let peakQueued = 0;
let ticksShowingEscalation = 0;
const rowSeconds = {};

for (let tick = 0; tick < HORIZON_SECONDS; tick++) {
  let live = 0;
  let queued = 0;
  let escalated = 0;

  for (let i = 0; i < slots.length; i++) {
    const phase = phaseAt(i, tick);
    rowSeconds[phase] = (rowSeconds[phase] ?? 0) + 1;
    if (phase === "live") live++;
    else if (phase === "queued") queued++;
    else if (phase === "flare") escalated++;
  }

  peakLive = Math.max(peakLive, live);
  peakQueued = Math.max(peakQueued, queued);
  if (escalated > 0) ticksShowingEscalation++;
}

const totalRowSeconds = HORIZON_SECONDS * slots.length;
const share = (phase) => (rowSeconds[phase] ?? 0) / totalRowSeconds;
const escalationShare = ticksShowingEscalation / HORIZON_SECONDS;

const problems = [];
if (peakLive > LIMITS.maxLiveAtOnce) {
  problems.push(
    `${peakLive} of ${slots.length} rows are in conversation at once (limit ${LIMITS.maxLiveAtOnce}). ` +
      `Raise \`hold\` relative to \`talk\`, then re-solve the offsets.`,
  );
}
if (peakQueued > LIMITS.maxQueuedAtOnce) {
  problems.push(
    `${peakQueued} of ${slots.length} rows are queued at once (limit ${LIMITS.maxQueuedAtOnce}). ` +
      `Lower \`lead\`, then re-solve the offsets.`,
  );
}
if (escalationShare < LIMITS.minTicksShowingEscalation) {
  problems.push(
    `a row needing a person is on screen only ${(escalationShare * 100).toFixed(0)}% of the time ` +
      `(need ${LIMITS.minTicksShowingEscalation * 100}%). The board's payoff is usually invisible.`,
  );
}
if (share("jade") < LIMITS.minClosedShare) {
  problems.push(
    `only ${(share("jade") * 100).toFixed(0)}% of row-seconds are a clean close ` +
      `(need ${LIMITS.minClosedShare * 100}%). "Clean calls close themselves" is not visibly true.`,
  );
}

// Every phase a row can be in must be one the board's accessible summary knows
// how to name. It names five - in conversation, closed, queued for retry,
// needing a person, not yet dialled - and it once named four, so a screen reader
// was told about eight of the nine rows on screen. A new settled state added to
// SETTLED fails here until the sentence learns the word for it.
const NAMED_PHASES = new Set(['live', 'queued', 'jade', 'flare', 'brass', 'off']);
const unnamed = Object.keys(rowSeconds).filter((phase) => !NAMED_PHASES.has(phase));
if (unnamed.length) {
  problems.push(
    `rows can be in phase(s) ${unnamed.join(', ')}, which the board's aria-label ` +
      `cannot name. Add them to the summary in call-board.tsx and to NAMED_PHASES here.`,
  );
}

if (problems.length) fail(problems);

const spread = Object.entries(rowSeconds)
  .sort((a, b) => b[1] - a[1])
  .map(([phase, n]) => `${phase} ${((n / totalRowSeconds) * 100).toFixed(0)}%`)
  .join(", ");

console.log(
  `check-board: ok - ${slots.length} rows, peak ${peakLive} live / ${peakQueued} queued, ` +
    `escalation on screen ${(escalationShare * 100).toFixed(0)}% of the time (${spread}).`,
);
