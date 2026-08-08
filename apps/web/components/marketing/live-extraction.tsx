"use client";

import { memo, useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/cn";
import { WaveCanvas } from "@/components/brand/wave-canvas";
import { Lamp } from "@/components/brand/lamp";
import { Eyebrow } from "@/components/ui/panel";
import { useTypewriter } from "@/lib/hooks/use-typewriter";
import type { LampState } from "@/lib/lamp";

/**
 * The same call, two ways to end up — shown as two live sections side by side.
 *
 * Both sections start with the same call happening. When it ends, each expands
 * to reveal what you are actually left with:
 *   • Without CallFlow — the operator's reality: a log that says `completed`,
 *     and a pile of unanswered questions.
 *   • With CallFlow AI — the same call as solid, typed analytics.
 *
 * One clock drives both sections so the reveal lands at the same instant and the
 * contrast is exact. It cycles the range of calls (positive, negative, retry,
 * neutral) and is fully static and complete under prefers-reduced-motion.
 */

const EASE = [0.22, 1, 0.36, 1] as const;

const TONE_TEXT: Record<LampState, string> = {
  off: "text-lamp-off-text",
  ice: "text-lamp-ice-text",
  brass: "text-lamp-brass-text",
  jade: "text-lamp-jade-text",
  flare: "text-lamp-flare-text",
};

const softRaised =
  "linear-gradient(180deg, color-mix(in oklab, #ffffff 72%, var(--surface-raised)) 0%, var(--surface-raised) 100%)";

function tint(tone?: LampState): string {
  return tone
    ? `color-mix(in oklab, var(--lamp-${tone}) 13%, var(--surface-raised))`
    : "var(--surface-raised)";
}

type Field = { k: string; v: string; tone?: LampState; from?: string };
type Scenario = {
  name: string;
  sec: number;
  line: string;
  seed: number;
  /** The questions a person is left guessing at, with only a log to go on. */
  questions: string[];
  fields: Field[];
  disposition: { state: LampState; label: string; pulse?: boolean };
};

const SCENARIOS: Scenario[] = [
  {
    name: "Aditi Sharma",
    sec: 161,
    line: "Yes, I'm still interested — could you call me back tomorrow around 3?",
    seed: 0.6,
    questions: ["Did it go well?", "Are they buying?", "Call back — when?", "Who follows up?"],
    fields: [
      { k: "outcome", v: "interested", tone: "jade", from: "still interested" },
      { k: "sentiment", v: "positive", tone: "jade" },
      { k: "intent", v: "callback requested", from: "call me back" },
      { k: "callback", v: "Tomorrow, 3:00 PM", from: "tomorrow around 3" },
      { k: "next step", v: "auto-scheduled", tone: "jade" },
    ],
    disposition: { state: "jade", label: "Auto-closed" },
  },
  {
    name: "Rahul Verma",
    sec: 128,
    line: "This is the third time I've called about the same charge — it's still wrong.",
    seed: 2.4,
    questions: ["Angry or fine?", "What's the issue?", "Is it urgent?", "Who owns this?"],
    fields: [
      { k: "outcome", v: "unresolved", tone: "flare", from: "it's still wrong" },
      { k: "sentiment", v: "frustrated", tone: "flare", from: "third time I've called" },
      { k: "intent", v: "billing dispute", from: "the same charge" },
      { k: "account", v: "#48210" },
      { k: "next step", v: "route to agent", tone: "flare" },
    ],
    disposition: { state: "flare", label: "Needs a person" },
  },
  {
    name: "Meera Nair",
    sec: 24,
    line: "I'm driving right now — can you try me again this evening?",
    seed: 1.5,
    questions: ["Did we connect?", "Try again — when?", "Still a lead?", "Auto or manual?"],
    fields: [
      { k: "outcome", v: "reschedule", tone: "brass", from: "try me again" },
      { k: "sentiment", v: "neutral", tone: "ice" },
      { k: "intent", v: "bad timing", from: "driving right now" },
      { k: "retry at", v: "Today, 6:00 PM", from: "this evening" },
      { k: "next step", v: "queued for retry", tone: "brass" },
    ],
    disposition: { state: "brass", label: "Queued for retry", pulse: true },
  },
  {
    name: "Sanjay Rao",
    sec: 84,
    line: "Thanks for the details — I'll think it over. Nothing right now.",
    seed: 3.1,
    questions: ["Interested at all?", "Worth chasing?", "Send anything?", "Close or keep?"],
    fields: [
      { k: "outcome", v: "not interested", tone: "ice", from: "nothing right now" },
      { k: "sentiment", v: "neutral", tone: "ice" },
      { k: "intent", v: "information only", from: "thanks for the details" },
      { k: "follow-up", v: "none", from: "I'll think it over" },
      { k: "next step", v: "closed", tone: "ice" },
    ],
    disposition: { state: "ice", label: "Closed — no action" },
  },
];

const SIGNALS = ["transcribing", "detecting intent", "reading sentiment", "extracting entities"];
const SIGNAL_AT = [0.12, 0.38, 0.62, 0.85];

const PHASES = ["connecting", "live", "ended", "analyzing", "result"] as const;
type Phase = (typeof PHASES)[number];
const DURATION: Record<Phase, number> = {
  connecting: 700,
  live: 4200,
  ended: 700,
  analyzing: 1300,
  result: 3400,
};

/** Deterministic scatter so the "confusion" notes look hand-pinned, not gridded. */
const SCATTER = [-2.5, 2, -1.5, 3, -2, 1.5];

function fmt(s: number): string {
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}

/** The one clock that drives both sections. Extracted so the component body reads
    as layout, not timing. */
function useCallCycle(reduced: boolean) {
  const [idx, setIdx] = useState(0);
  const [phaseIdx, setPhaseIdx] = useState(0);
  const [progress, setProgress] = useState(0);
  const phase = PHASES[phaseIdx];

  useEffect(() => {
    if (reduced) return;
    const id = setTimeout(() => {
      if (phaseIdx < PHASES.length - 1) {
        const next = phaseIdx + 1;
        if (PHASES[next] === "live") setProgress(0);
        setPhaseIdx(next);
      } else {
        setIdx((c) => (c + 1) % SCENARIOS.length);
        setProgress(0);
        setPhaseIdx(0);
      }
    }, DURATION[phase]);
    return () => clearTimeout(id);
  }, [phaseIdx, phase, idx, reduced]);

  useEffect(() => {
    if (reduced || phase !== "live") return;
    const start = performance.now();
    const id = setInterval(() => {
      setProgress(Math.min(1, (performance.now() - start) / DURATION.live));
    }, 80);
    return () => clearInterval(id);
  }, [phase, idx, reduced]);

  return { idx, phase, progress };
}

export function LiveExtraction() {
  const reduced = !!useReducedMotion();
  const { idx, phase, progress } = useCallCycle(reduced);
  const scenario = SCENARIOS[idx];

  const onCall = !reduced && (phase === "connecting" || phase === "live");
  const speaking = !reduced && phase === "live";
  const reading = !reduced && (phase === "live" || phase === "analyzing");
  const done = reduced || phase === "result";
  const shownSec = reduced
    ? scenario.sec
    : phase === "connecting"
      ? 0
      : phase === "live"
        ? Math.round(progress * scenario.sec)
        : scenario.sec;
  const signalCount = reduced
    ? SIGNALS.length
    : phase === "live"
      ? SIGNAL_AT.filter((t) => progress >= t).length
      : phase === "connecting"
        ? 0
        : SIGNALS.length;

  const call = { scenario, idx, onCall, speaking, connecting: !reduced && phase === "connecting", shownSec, reduced };

  return (
    <div className="flex flex-col items-stretch lg:flex-row">
      <Section
        eyebrow="Without CallFlow"
        call={call}
        done={done}
        reduced={reduced}
        output={<ConfusionOutput scenario={scenario} idx={idx} reduced={reduced} />}
      />

      <Divider />

      <Section
        eyebrow="With CallFlow AI"
        call={call}
        done={done}
        reduced={reduced}
        scanning={reading}
        pending={<AiReading idx={idx} reading={reading} signalCount={signalCount} />}
        output={<InsightOutput scenario={scenario} idx={idx} reduced={reduced} />}
      />
    </div>
  );
}

/* ---- A section: a live call that expands into its output ---------------- */

type CallProps = {
  scenario: Scenario;
  idx: number;
  onCall: boolean;
  speaking: boolean;
  connecting: boolean;
  shownSec: number;
  reduced: boolean;
};

function Section({
  eyebrow,
  call,
  done,
  reduced,
  output,
  pending,
  scanning = false,
}: {
  eyebrow: string;
  call: CallProps;
  done: boolean;
  reduced: boolean;
  output: React.ReactNode;
  /** Shown in the reveal area while the call is still running. */
  pending?: React.ReactNode;
  /** Sweep the waveform with the reading scan (the CallFlow side only). */
  scanning?: boolean;
}) {
  return (
    <div className="flex flex-1 flex-col lg:min-w-0">
      <Eyebrow>{eyebrow}</Eyebrow>

      <div className="mt-3">
        <CallCard {...call} scanning={scanning} />
      </div>

      {/* The reveal. Height is FIXED (not min-height) to the tallest result any
          scenario produces, so neither the call ending nor cycling scenarios can
          change the section's height and shove the page below. */}
      <div className="relative mt-7 h-[17rem]">
        <AnimatePresence mode="wait">
          {done ? (
            <motion.div
              key="result"
              initial={reduced ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, transition: { duration: 0.2 } }}
            >
              {output}
            </motion.div>
          ) : (
            <motion.div
              key="pending"
              className="absolute inset-0"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, transition: { duration: 0.2 } }}
            >
              {pending ?? <ManualPending />}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function CallCard({
  scenario,
  idx,
  onCall,
  speaking,
  connecting,
  shownSec,
  reduced,
  scanning = false,
}: CallProps & { scanning?: boolean }) {
  return (
    <div className="rounded-[1.75rem] p-5 shadow-sm" style={{ background: softRaised }}>
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2.5">
          <LiveDot active={onCall && !reduced} />
          <span className="text-small font-semibold text-text">{scenario.name}</span>
        </span>
        <span className="flex items-center gap-2 font-mono text-data tabular-nums text-text-mute">
          <span className={cn("text-label", onCall ? "text-lamp-flare-text" : "text-text-mute")}>
            {connecting ? "CONNECTING" : onCall ? "LIVE" : "ENDED"}
          </span>
          {fmt(shownSec)}
        </span>
      </div>

      {/* The waveform, with a jade scan sweeping it while CallFlow reads the
          call — the visible "the AI is listening to this" moment. */}
      <div
        className={cn(
          "relative mt-4 overflow-hidden rounded-md transition-opacity duration-500 ease-out",
          speaking || scanning ? "opacity-100" : "opacity-35",
        )}
      >
        <WaveCanvas seed={scenario.seed} pitch={5} className="h-9 text-text" />
        {scanning && !reduced ? (
          <motion.span
            aria-hidden
            className="pointer-events-none absolute inset-y-0 w-12"
            style={{
              background:
                "linear-gradient(90deg, transparent, color-mix(in oklab, var(--lamp-jade) 55%, transparent) 72%, color-mix(in oklab, var(--lamp-jade) 85%, transparent) 96%, transparent)",
              boxShadow: "0 0 14px 0 color-mix(in oklab, var(--lamp-jade) 45%, transparent)",
            }}
            initial={{ left: "-14%" }}
            animate={{ left: "100%" }}
            transition={{ duration: 1.25, repeat: Infinity, ease: "easeInOut" }}
          />
        ) : null}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={idx}
          initial={reduced ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.2 } }}
        >
          <Transcript text={scenario.line} instant={reduced} />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

/* ---- Reveal: Without CallFlow → questions & confusion ------------------- */

function ConfusionOutput({ scenario, idx, reduced }: { scenario: Scenario; idx: number; reduced: boolean }) {
  return (
    <div key={idx}>
      <p className="text-small text-text-mute">All you really know:</p>

      <div className="mt-3 flex flex-wrap items-center gap-2.5">
        {/* The one hard fact — and it's useless. */}
        <span
          className="inline-flex items-center gap-2 rounded-2xl px-3.5 py-2 shadow-sm"
          style={{ background: "var(--surface-raised)" }}
        >
          <span className="size-1.5 rounded-full" style={{ background: "var(--lamp-off)" }} />
          <span className="font-mono text-data text-text-mute">completed · {fmt(scenario.sec)}</span>
        </span>

        {/* Everything else is a question. */}
        {scenario.questions.map((q, i) => (
          <motion.span
            key={q}
            className="inline-flex items-center gap-1.5 rounded-2xl px-3.5 py-2 text-small text-text-dim shadow-sm"
            style={{ background: "var(--surface-raised)" }}
            initial={reduced ? false : { opacity: 0, y: 14, scale: 0.9, rotate: SCATTER[i % SCATTER.length] }}
            animate={{ opacity: 1, y: 0, scale: 1, rotate: reduced ? 0 : SCATTER[i % SCATTER.length] }}
            transition={{ delay: reduced ? 0 : 0.1 + i * 0.09, duration: 0.4, ease: EASE }}
          >
            <span aria-hidden className="font-mono text-data text-text-mute">
              ?
            </span>
            {q}
          </motion.span>
        ))}
      </div>

      <p className="mt-4 text-small text-text-mute">Someone has to listen back and score it by hand.</p>
    </div>
  );
}

/** Shown in the Without column while the call runs — mirrors the reading list on
    the right, but every line is unaided, so the columns stay balanced and the
    contrast is explicit: none of this happens for you. */
function ManualPending() {
  return (
    <div className="flex h-full flex-col justify-center">
      <div className="flex items-center gap-2.5">
        <span aria-hidden className="flex h-4 items-end gap-0.5">
          {[0, 1, 2].map((i) => (
            <span key={i} className="block w-0.5 rounded-full" style={{ height: 5, background: "var(--text-mute)" }} />
          ))}
        </span>
        <span className="text-small font-semibold text-text-mute">Just you</span>
        <span className="font-mono text-label text-text-mute">listening…</span>
      </div>
      <div className="mt-3 flex flex-col gap-1.5">
        {SIGNALS.map((sig) => (
          <span key={sig} className="flex items-center gap-2 text-small text-text-mute">
            <span aria-hidden className="size-1.5 rounded-full" style={{ background: "var(--lamp-off)" }} />
            <span className="line-through decoration-text-mute/40">{sig}</span>
            <span className="ml-auto font-mono text-label">by hand</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/* ---- Reveal: With CallFlow → solid analytics --------------------------- */

function InsightOutput({ scenario, idx, reduced }: { scenario: Scenario; idx: number; reduced: boolean }) {
  return (
    <div key={idx}>
      <p className="text-small text-text-mute">Typed the moment it ends:</p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {scenario.fields.map((f, i) => (
          <Bubble key={f.k} label={f.k} value={f.v} tone={f.tone} from={f.from} index={i} reduced={reduced} />
        ))}
        <DispositionBubble
          state={scenario.disposition.state}
          label={scenario.disposition.label}
          pulse={scenario.disposition.pulse}
          index={scenario.fields.length}
          reduced={reduced}
        />
      </div>

      <p className="mt-4 text-small text-text-mute">The ones that need a person surface themselves.</p>
    </div>
  );
}

/** Shown in the With column while the call runs — the AI reading it live. */
function AiReading({ idx, reading, signalCount }: { idx: number; reading: boolean; signalCount: number }) {
  return (
    <div className="flex h-full flex-col justify-center">
      <div className="flex items-center gap-2.5">
        <Equalizer active={reading} />
        <span className="text-small font-semibold text-text">CallFlow&nbsp;AI</span>
        <span className="font-mono text-label text-text-mute">reading…</span>
      </div>
      <div className="mt-3 flex flex-col gap-1.5">
        {SIGNALS.map((sig, i) => {
          const on = i < signalCount;
          return (
            <motion.span
              key={`${idx}-${sig}`}
              className="flex items-center gap-2 text-small"
              animate={{ opacity: on ? 1 : 0.28, x: on ? 0 : -4 }}
              transition={{ duration: 0.3, ease: EASE }}
            >
              <span
                aria-hidden
                className="size-1.5 rounded-full"
                style={{ background: on ? "var(--lamp-jade)" : "var(--lamp-off)" }}
              />
              <span className={on ? "text-text-dim" : "text-text-mute"}>{sig}</span>
            </motion.span>
          );
        })}
      </div>
    </div>
  );
}

function Bubble({
  label,
  value,
  tone,
  from,
  index,
  reduced,
}: {
  label: string;
  value: string;
  tone?: LampState;
  from?: string;
  index: number;
  reduced: boolean;
}) {
  return (
    <motion.div
      className="flex flex-col gap-0.5 rounded-2xl px-3.5 py-2 shadow-sm"
      style={{ background: tint(tone) }}
      initial={reduced ? false : { opacity: 0, y: 26, scale: 0.85, filter: "blur(6px)" }}
      animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
      transition={{ delay: reduced ? 0 : 0.12 + index * 0.11, duration: 0.5, ease: EASE }}
    >
      <span className="text-label text-text-mute">{label}</span>
      <span className={cn("text-small font-semibold", tone ? TONE_TEXT[tone] : "text-text")}>{value}</span>
      {from ? (
        <span className="mt-0.5 text-label text-text-mute/80">
          from “{from}”
        </span>
      ) : null}
    </motion.div>
  );
}

function DispositionBubble({
  state,
  label,
  pulse,
  index,
  reduced,
}: {
  state: LampState;
  label: string;
  pulse?: boolean;
  index: number;
  reduced: boolean;
}) {
  return (
    <motion.div
      className="flex items-center gap-2 rounded-full px-4 py-2 shadow-sm"
      style={{ background: `color-mix(in oklab, var(--lamp-${state}) 16%, var(--surface-raised))` }}
      initial={reduced ? false : { opacity: 0, y: 18, scale: 0.85 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: reduced ? 0 : 0.15 + index * 0.1, duration: 0.42, ease: EASE }}
    >
      <Lamp state={state} size="md" pulse={pulse} />
      <span className={cn("text-small font-semibold", TONE_TEXT[state])}>{label}</span>
    </motion.div>
  );
}

/* ---- Shared bits -------------------------------------------------------- */

// Memoised so the once-per-tick timer re-render of the parent can't restart the
// ring animation mid-cycle (which read as a stutter).
const LiveDot = memo(function LiveDot({ active }: { active: boolean }) {
  return (
    <span className="relative flex size-2.5 items-center justify-center">
      <span className="size-2.5 rounded-full" style={{ background: "var(--lamp-flare)" }} />
      {active ? (
        <motion.span
          aria-hidden
          className="absolute inset-0 rounded-full"
          style={{ background: "var(--lamp-flare)" }}
          animate={{ scale: [1, 2.4], opacity: [0.5, 0] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: "easeOut" }}
        />
      ) : null}
    </span>
  );
});

function Transcript({ text, instant }: { text: string; instant: boolean }) {
  const { output, done } = useTypewriter(text, { durationMs: 3200, instant });
  return (
    <p className={cn("mt-3 min-h-[3.25rem] text-body font-medium text-text", !done && "caret")}>
      {output ? `“${output}${done ? "”" : ""}` : " "}
    </p>
  );
}

const Equalizer = memo(function Equalizer({ active }: { active: boolean }) {
  return (
    <span aria-hidden className="flex h-4 items-center gap-0.5">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="block w-0.5 rounded-full"
          style={{ background: "var(--text)" }}
          animate={active ? { height: [4, 14, 4] } : { height: 6 }}
          transition={active ? { duration: 0.7, repeat: Infinity, delay: i * 0.13, ease: "easeInOut" } : { duration: 0.3 }}
        />
      ))}
    </span>
  );
});

/**
 * The separator between the two sections — a clear line that runs the full
 * height, softening only at the very ends, with the "vs" set on it. Vertical on
 * desktop, horizontal when the sections stack.
 */
const LINE = "color-mix(in oklab, var(--text) 32%, transparent)";
function Divider() {
  return (
    <div className="relative flex shrink-0 items-center justify-center py-7 lg:mx-10 lg:w-px lg:py-0">
      <span
        aria-hidden
        className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 lg:hidden"
        style={{ background: `linear-gradient(90deg, transparent, ${LINE} 8%, ${LINE} 92%, transparent)` }}
      />
      <span
        aria-hidden
        className="absolute inset-y-0 left-1/2 hidden w-px -translate-x-1/2 lg:block"
        style={{ background: `linear-gradient(180deg, transparent, ${LINE} 5%, ${LINE} 95%, transparent)` }}
      />
      <span
        className="relative z-10 rounded-full border border-rule px-2.5 py-1 font-mono text-label tracking-[0.2em] text-text-mute"
        style={{ background: "var(--surface)" }}
      >
        vs
      </span>
    </div>
  );
}
