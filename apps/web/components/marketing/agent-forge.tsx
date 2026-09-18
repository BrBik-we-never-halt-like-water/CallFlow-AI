"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/cn";
import { Eyebrow, SectionHeading } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";

/**
 * The agent, assembling itself.
 *
 * The product's core object since ADR-8 is the voice agent - a plain-English
 * brief, three provider legs, and the fields it must come back with - and the
 * marketing site never told that story. This section plays it on a loop while
 * it is on screen: the brief types itself out, the legs light in sequence,
 * the fields snap in, and what is left standing is the thing a run dials
 * with. Then it starts over, the way the hero's board keeps running - the
 * page demonstrates, the reader just watches. Clicking a stage jumps the
 * demo there.
 *
 * Everything shown is the real configuration surface: `{name}` and
 * `{context[...]}` are the real placeholders `prompt_assembly.py` substitutes
 * per contact, the three legs are the real STT/LLM/TTS pipeline (coloured
 * with `--leg-*`, the tokens reserved for exactly this meaning), and
 * `required` is load-bearing - a completed call missing a required field
 * escalates to a person rather than guessing.
 */

const PHASES = [
  {
    title: "Write the brief",
    detail:
      "Plain English. {name} and any column from your spreadsheet are filled in per contact, so one brief serves the whole list.",
  },
  {
    title: "Pick the ears, the mind, the voice",
    detail:
      "A transcriber, a model, a voice — on your own keys, or platform keys while you're starting out.",
  },
  {
    title: "Name the fields it must bring back",
    detail:
      "Typed answers, recorded mid-call. Required means required: a call that ends without one goes to a person.",
  },
  {
    title: "That's the agent",
    detail:
      "Reusable across every list, every run, and every number you connect. Brief it once; point it anywhere.",
  },
] as const;

/** Seconds each phase holds. The first is longest - it has typing to do. */
const PHASE_SECONDS = [7, 4.5, 4.5, 6];
const PHASE_STARTS = PHASE_SECONDS.reduce<number[]>(
  (starts, _, i) => [...starts, i === 0 ? 0 : starts[i - 1] + PHASE_SECONDS[i - 1]],
  [],
);
const CYCLE = PHASE_SECONDS.reduce((a, b) => a + b, 0);
const TICK_MS = 80;

/** The brief, as segments - placeholders render as chips, prose as prose. */
const BRIEF: ReadonlyArray<string | { ph: string }> = [
  "You are Asha, a renewals specialist. You're calling ",
  { ph: "{name}" },
  " about the plan noted in ",
  { ph: "{context[plan]}" },
  ". Be brief and warm. If they've decided, capture the decision; if they hesitate, offer a callback and capture when.",
];

const BRIEF_LENGTH = BRIEF.reduce(
  (n, seg) => n + (typeof seg === "string" ? seg.length : seg.ph.length),
  0,
);

const LEGS = [
  { key: "stt", label: "Transcriber", pick: "Deepgram", token: "--leg-stt" },
  { key: "llm", label: "Model", pick: "40+ via OpenRouter", token: "--leg-llm" },
  { key: "tts", label: "Voice", pick: "Sarvam · Anushka", token: "--leg-tts" },
] as const;

const FIELDS = [
  { key: "decision", type: "string", required: true },
  { key: "callback_time", type: "string", required: false },
  { key: "objection", type: "string", required: false },
  { key: "plan_fit", type: "boolean", required: false },
] as const;

type ForgeState = {
  phase: number;
  chars: number;
  litLegs: number;
  shownFields: number;
};

const ASSEMBLED: ForgeState = {
  phase: PHASES.length - 1,
  chars: BRIEF_LENGTH,
  litLegs: LEGS.length,
  shownFields: FIELDS.length,
};

/** Where the demo stands `t` seconds into a cycle. */
function stateAt(t: number): ForgeState {
  const local = t % CYCLE;
  let phase = 0;
  for (let i = PHASES.length - 1; i >= 0; i--) {
    if (local >= PHASE_STARTS[i]) {
      phase = i;
      break;
    }
  }
  const sub = (local - PHASE_STARTS[phase]) / PHASE_SECONDS[phase];

  return {
    phase,
    chars: phase > 0 ? BRIEF_LENGTH : Math.round(sub * BRIEF_LENGTH),
    litLegs: phase > 1 ? 3 : phase === 1 ? Math.min(3, 1 + Math.floor(sub * 3)) : 0,
    shownFields:
      phase > 2 ? FIELDS.length : phase === 2 ? Math.ceil(sub * FIELDS.length) : 0,
  };
}

const sameState = (a: ForgeState, b: ForgeState) =>
  a.phase === b.phase &&
  a.chars === b.chars &&
  a.litLegs === b.litLegs &&
  a.shownFields === b.shownFields;

export function AgentForge() {
  const reduced = !!useReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);
  // Plays only while someone can see it - a demo advancing off-screen is
  // wasted, and a reader scrolling back should find it mid-performance, not
  // finished.
  const inView = useInView(rootRef, { amount: 0.3 });

  const elapsed = useRef(0);
  const [state, setState] = useState<ForgeState>(() => stateAt(0));
  // Bumped on a manual jump so the effect rebases its clock there.
  const [epoch, setEpoch] = useState(0);

  useEffect(() => {
    if (reduced || !inView) return;
    // Wall-clock, not tick-counting: browsers throttle timers well past
    // TICK_MS in busy or backgrounded tabs, and a demo that advances one tick
    // per fire would play in slow motion exactly when the machine is
    // struggling. Deriving from elapsed real time keeps the pace right at any
    // timer resolution - the board's pure-function-of-a-counter reasoning.
    const startedAt = performance.now() - elapsed.current * 1000;
    const id = setInterval(() => {
      elapsed.current = (performance.now() - startedAt) / 1000;
      const next = stateAt(elapsed.current);
      setState((current) => (sameState(current, next) ? current : next));
    }, TICK_MS);
    return () => clearInterval(id);
  }, [reduced, inView, epoch]);

  /** Clicking a stage jumps the demo there and lets it keep playing. */
  const jumpTo = (i: number) => {
    elapsed.current = PHASE_STARTS[i];
    setState(stateAt(elapsed.current));
    setEpoch((e) => e + 1);
  };

  // Reduced motion gets the finished agent, still: the one thing this section
  // cannot make motionless is its own assembly.
  const shown = reduced ? ASSEMBLED : state;

  return (
    <div ref={rootRef}>
      <section className="mx-auto w-full max-w-(--container-marketing) px-4 sm:px-6">
        <Reveal>
          <SectionHeading
            eyebrow="The agent"
            title="Build the agent once."
            sub="A brief, three providers, and the fields you want back — that's an agent."
          />
        </Reveal>

        <div className="mt-(--deck-gap) grid items-start gap-10 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)] lg:gap-16">
          <PhaseTracker phase={shown.phase} onSelect={jumpTo} />

          <Reveal delayMs={80}>
            <ForgeCard {...shown} />
          </Reveal>
        </div>
      </section>
    </div>
  );
}

function PhaseTracker({
  phase,
  onSelect,
}: {
  phase: number;
  onSelect: (i: number) => void;
}) {
  return (
    <ol className="flex flex-col gap-1.5">
      {PHASES.map((p, i) => {
        const active = i === phase;
        return (
          <li key={p.title}>
            <button
              type="button"
              onClick={() => onSelect(i)}
              aria-current={active ? "step" : undefined}
              className={cn(
                "group w-full cursor-pointer rounded-lg border-l-2 py-3 pl-4 pr-3 text-left transition-colors duration-(--dur-base)",
                active
                  ? "border-l-primary bg-surface-raised shadow-sm"
                  : "border-l-rule hover:border-l-rule-strong hover:bg-surface-hover",
              )}
            >
              <span className="flex items-baseline gap-3">
                <span
                  className={cn(
                    "font-mono text-data",
                    active ? "text-primary-ink" : "text-text-mute",
                  )}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span
                  className={cn(
                    "text-h4 font-medium",
                    active ? "text-text" : "text-text-dim",
                  )}
                >
                  {p.title}
                </span>
              </span>
              <span
                className={cn(
                  "mt-1 block pl-8 text-small",
                  active ? "text-text-dim" : "text-text-mute",
                )}
              >
                {p.detail}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * The agent card, accreting. Each block arrives on its phase and stays -
 * assembly, not a slideshow - and the summary sentence below the card is what
 * a screen reader gets instead of the churn.
 */
function ForgeCard({ phase, chars, litLegs, shownFields }: ForgeState) {
  return (
    <div>
      <div
        role="img"
        aria-label={
          "A voice agent being assembled: a plain-English brief with per-contact placeholders; " +
          "a transcriber, a model and a voice; four typed fields to collect — decision (required), " +
          "callback_time, objection, plan_fit — then the agent, ready to run."
        }
        className="card-raised relative overflow-hidden p-5 sm:p-7"
      >
        <div aria-hidden className="flex flex-col gap-6">
          {/* --- The brief ------------------------------------------------- */}
          <div className={cn("transition-opacity duration-(--dur-base)", phase > 0 && "opacity-80")}>
            <Eyebrow className="mb-2.5">System prompt</Eyebrow>
            <p className="min-h-[7.5em] max-w-[62ch] font-mono text-data leading-relaxed text-text sm:min-h-[6em]">
              <TypedBrief chars={chars} />
              {phase === 0 && chars < BRIEF_LENGTH ? (
                <span className="ml-0.5 inline-block h-[1.1em] w-[2px] translate-y-[3px] bg-primary" />
              ) : null}
            </p>
          </div>

          {/* --- The legs ---------------------------------------------------
              `--leg-*` is the one other place colour carries meaning, and the
              meaning is "which part of the pipeline" - never how a call went. */}
          <Accrete shown={phase >= 1}>
            <Eyebrow className="mb-3">Pipeline</Eyebrow>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-stretch sm:gap-0">
              {LEGS.map((leg, i) => {
                const lit = litLegs > i;
                return (
                  <div key={leg.key} className="flex items-center sm:flex-1">
                    <div
                      className={cn(
                        "flex min-w-0 flex-1 flex-col gap-0.5 rounded-lg border px-3.5 py-2.5 transition-all duration-(--dur-base)",
                        lit ? "border-transparent bg-surface-sunken" : "border-rule opacity-45",
                      )}
                      style={
                        lit
                          ? { boxShadow: `inset 3px 0 0 0 var(${leg.token})` }
                          : undefined
                      }
                    >
                      <span className="eyebrow" style={lit ? { color: `var(${leg.token})` } : undefined}>
                        {leg.label}
                      </span>
                      <span className={cn("truncate text-small", lit ? "text-text" : "text-text-mute")}>
                        {leg.pick}
                      </span>
                    </div>
                    {i < LEGS.length - 1 ? (
                      <span
                        className={cn(
                          "mx-1 hidden h-px w-4 shrink-0 sm:block",
                          litLegs > i + 1 ? "bg-rule-strong" : "bg-rule",
                        )}
                      />
                    ) : null}
                  </div>
                );
              })}
            </div>
          </Accrete>

          {/* --- The fields ------------------------------------------------ */}
          <Accrete shown={phase >= 2}>
            <Eyebrow className="mb-3">Fields to collect</Eyebrow>
            <ul className="flex flex-wrap gap-2">
              {FIELDS.map((field, i) => (
                <li
                  key={field.key}
                  className={cn(
                    "flex items-baseline gap-2 rounded-md bg-surface-sunken px-2.5 py-1.5 font-mono text-data transition-all duration-(--dur-base)",
                    shownFields > i ? "opacity-100" : "translate-y-1 opacity-0",
                  )}
                >
                  <span className="text-text">{field.key}</span>
                  <span className="text-text-mute">{field.type}</span>
                  {field.required ? (
                    <span className="rounded-sm bg-primary-wash px-1 py-px text-label tracking-wider text-primary-ink uppercase">
                      required
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
            <p className="mt-3 max-w-[58ch] text-small text-text-dim">
              A completed call missing a required field doesn&apos;t guess — it lands
              with a person, named as the reason.
            </p>
          </Accrete>

          {/* --- Ready ------------------------------------------------------ */}
          <Accrete shown={phase >= 3}>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-rule bg-surface-raised px-4 py-3">
              <span className="flex items-center gap-2.5">
                <span aria-hidden className="size-2 rounded-full bg-primary" />
                <span className="text-small font-medium text-text">Asha · Renewals</span>
              </span>
              <span className="font-mono text-data text-text-mute">
                3 legs · 4 fields · dials from your numbers
              </span>
              <span className="ml-auto font-mono text-data text-text">ready to run</span>
            </div>
          </Accrete>
        </div>
      </div>

      <p className="mt-4 text-small text-text-mute">
        The exact configuration surface — placeholders, legs, and required fields
        included. Nothing staged that the editor can&apos;t save.
      </p>
    </div>
  );
}

/** A block that arrives on its phase and stays until the cycle restarts. */
function Accrete({ shown, children }: { shown: boolean; children: React.ReactNode }) {
  return (
    <motion.div
      initial={false}
      animate={shown ? { opacity: 1, y: 0 } : { opacity: 0, y: 14 }}
      transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
      className={cn(!shown && "pointer-events-none")}
    >
      {children}
    </motion.div>
  );
}

/** Each segment with the character offset it starts at, computed once. */
const BRIEF_OFFSETS: ReadonlyArray<{ seg: (typeof BRIEF)[number]; start: number }> = (() => {
  let at = 0;
  return BRIEF.map((seg) => {
    const entry = { seg, start: at };
    at += typeof seg === "string" ? seg.length : seg.ph.length;
    return entry;
  });
})();

/** The brief, sliced to `chars`, with placeholders rendering as whole chips. */
function TypedBrief({ chars }: { chars: number }) {
  return (
    <>
      {BRIEF_OFFSETS.map(({ seg, start }, i) => {
        if (chars <= start) return null;
        if (typeof seg === "string") {
          return <span key={i}>{seg.slice(0, chars - start)}</span>;
        }
        // A placeholder appears as a unit once typing reaches it - it is a
        // token the product substitutes, not prose someone types out.
        return (
          <span
            key={i}
            className="mx-0.5 rounded-sm bg-primary-wash px-1 py-px text-primary-ink"
          >
            {seg.ph}
          </span>
        );
      })}
    </>
  );
}
