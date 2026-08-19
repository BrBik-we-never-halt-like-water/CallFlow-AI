"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/cn";
import { LiveLamp } from "./live-lamp";
import { Eyebrow, SectionHeading } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";
import { Tag } from "@/components/ui/badge";
import { WaveCanvas } from "@/components/brand/wave-canvas";

/**
 * How it works — one contact, four forms.
 *
 * This is a genuine sequence, so it is shown as a single transformation rather
 * than four parallel cards: we follow one contact (Aditi) and the demo card
 * morphs in place through the pipeline — her validated row, the agent that calls her,
 * her live call, her triaged result. A vertical tracker on the left marks where
 * in the pipeline we are. Everything is real product UI, not a screenshot.
 */

const STEPS = [
  {
    n: "01",
    title: "Load your contacts",
    body: "Paste them in or drop a CSV. Every row is validated before anything dials.",
  },
  {
    n: "02",
    title: "Choose an agent",
    body: "Pick the agent that makes the call — it carries the prompt and the fields to extract.",
  },
  {
    n: "03",
    title: "Run it",
    body: "Guards are checked, then it dials. Results arrive as each call ends.",
  },
  {
    n: "04",
    title: "Triage what matters",
    body: "Clean outcomes close themselves. Only the calls that need a person reach your team.",
  },
];

/** How long each stage holds before the demo morphs to the next. */
const STEP_MS = 3400;

export function Steps() {
  const reduced = !!useReducedMotion();
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => setStep((s) => (s + 1) % STEPS.length), STEP_MS);
    return () => clearInterval(id);
  }, [reduced]);

  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          title="Watch one contact become a triaged result."
          sub="One row, four forms — her validated row, the agent that calls her, her live call, and the typed result your team actually reads. Every frame is the real product UI."
        />
      </Reveal>

      <div className="mt-(--deck-gap) grid items-start gap-10 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)] lg:gap-16">
        <StepTracker step={step} onSelect={setStep} />
        <Reveal delayMs={80}>
          <MorphCard step={step} reduced={reduced} />
        </Reveal>
      </div>
    </section>
  );
}

/**
 * The vertical pipeline tracker. A line fills jade up to the current stage and
 * each stage's node lights as the signal reaches it. Every stage shows its own
 * description, dimmed until it is current. Stages are clickable to jump.
 */
function StepTracker({
  step,
  onSelect,
}: {
  step: number;
  onSelect: (i: number) => void;
}) {
  const fill = STEPS.length > 1 ? (step / (STEPS.length - 1)) * 100 : 0;

  return (
    <Reveal>
      {/* Every step shows its own description, dimmed until it is the current
          one. It used to be one description in a fixed slot at the bottom that
          swapped as the stage advanced — which kept the column short, but meant
          three quarters of the explanation was always hidden behind a timer.
          Four short lines do not need progressive disclosure, and inlining them
          fills the column against the card beside it. Heights are constant per
          row, so switching steps still never reflows the section. */}
      <ol className="relative flex flex-col gap-9 pl-8">
        <span aria-hidden className="absolute top-2 bottom-2 left-[9px] w-px bg-rule" />
        <motion.span
          aria-hidden
          className="absolute top-2 left-[9px] w-px bg-lamp-jade"
          animate={{ height: `${fill}%` }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        />

        {STEPS.map((s, i) => {
          const current = i === step;
          const reached = i <= step;
          return (
            <li key={s.n}>
              <button
                type="button"
                onClick={() => onSelect(i)}
                className="group relative flex w-full flex-col items-start gap-1.5 py-0.5 text-left"
              >
                {/* Pinned to the title's own line, not the row's centre. The row
                    carries a description now, so `top-1/2` would float the node
                    down into the gap between title and body and break the rail. */}
                <span
                  aria-hidden
                  className="absolute top-[3px] -left-8 flex size-[18px] items-center justify-center rounded-full bg-surface ring-1 ring-rule"
                >
                  <span
                    className="size-2 rounded-full transition-colors duration-300"
                    style={{
                      background: reached ? "var(--lamp-jade)" : "var(--rule-strong)",
                      boxShadow: current
                        ? "0 0 0 3px color-mix(in oklab, var(--lamp-jade) 22%, transparent)"
                        : "none",
                    }}
                  />
                </span>

                <span className="flex items-baseline gap-2">
                  <Eyebrow as="span" className={current ? "text-lamp-jade-text" : "text-text-mute"}>
                    {s.n}
                  </Eyebrow>
                  <span
                    className={cn(
                      "text-body font-medium transition-colors duration-300",
                      current ? "text-text" : "text-text-dim group-hover:text-text",
                    )}
                  >
                    {s.title}
                  </span>
                </span>

                <span
                  className={cn(
                    "max-w-[42ch] text-small transition-colors duration-300",
                    current ? "text-text-dim" : "text-text-mute",
                  )}
                >
                  {s.body}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </Reveal>
  );
}

/** The demo card: the same contact's data, morphing between the four forms. */
function MorphCard({ step, reduced }: { step: number; reduced: boolean }) {
  const forms = [<LoadForm key="l" />, <ChooseForm key="c" />, <RunForm key="r" />, <TriageForm key="t" />];

  return (
    // Fixed *for a given viewport* on purpose: the four forms are different
    // lengths and the card must not resize as they swap, or the whole section
    // jumps on every tick. The height itself scales with the viewport, because
    // the section it lives in is exactly one screen tall — at a flat 25rem this
    // was the single biggest reason this section overflowed a laptop.
    <div className="card-raised relative flex h-[clamp(16rem,38vh,25rem)] flex-col justify-center overflow-hidden p-6 sm:p-8">
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={reduced ? false : { opacity: 0, y: 14, filter: "blur(6px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          exit={reduced ? { opacity: 0 } : { opacity: 0, y: -14, filter: "blur(6px)" }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        >
          {forms[step]}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function FormShell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4">
      <Eyebrow>{label}</Eyebrow>
      {children}
    </div>
  );
}

function LoadForm() {
  const rows = [
    { name: "Aditi Sharma", phone: "+91*******210", ok: true, lead: true },
    { name: "Rahul Verma", phone: "+91*******884", ok: true },
    { name: "Priya Nair", phone: "98765", ok: false },
  ];
  return (
    <FormShell label="Contacts loaded">
      <div className="flex flex-col gap-1.5">
        {rows.map((r) => (
          <div
            key={r.name}
            className={cn(
              "flex items-center gap-3 rounded-md px-2.5 py-1.5",
              r.lead && "ring-1 ring-[color-mix(in_oklab,var(--lamp-jade)_38%,transparent)]",
            )}
          >
            <span className="min-w-0 flex-1 truncate text-body text-text">{r.name}</span>
            <span
              className={cn(
                "font-mono text-data tabular-nums",
                r.ok ? "text-text-mute" : "text-lamp-flare-text",
              )}
            >
              {r.phone}
            </span>
            <span className={cn("text-small", r.ok ? "text-lamp-jade-text" : "text-lamp-flare-text")}>
              {r.ok ? "ready" : "no code"}
            </span>
          </div>
        ))}
      </div>
      <p className="text-small text-text-dim">
        Following <span className="font-medium text-text">Aditi</span> through the run →
      </p>
    </FormShell>
  );
}

function ChooseForm() {
  return (
    <FormShell label="Agent chosen">
      <p className="text-body text-text">Holiday enquiry follow-up</p>
      <div className="flex flex-col gap-2">
        <span className="text-small text-text-dim">Fields to extract from the call</span>
        <div className="flex flex-wrap gap-1.5">
          <Tag>destination</Tag>
          <Tag>party_size</Tag>
          <Tag>budget</Tag>
          <Tag>timeline</Tag>
        </div>
      </div>
    </FormShell>
  );
}

function RunForm() {
  return (
    <FormShell label="Calling Aditi">
      <div className="flex items-center gap-3">
        <LiveLamp state="jade" size="sm" pulse label="On the call" />
        <span className="text-small text-text-dim">Live</span>
        <span className="ml-auto font-mono text-data tabular-nums text-text-mute">00:14</span>
      </div>
      <div className="h-14 w-full">
        <WaveCanvas pitch={6} />
      </div>
      <p className="text-body text-text">
        “Hi Aditi, this is CallFlow about your holiday enquiry — is now a good time?”
      </p>
    </FormShell>
  );
}

function TriageForm() {
  const fields = [
    { k: "outcome", v: "interested", tag: true },
    { k: "destination", v: "Dubai" },
    { k: "party_size", v: "4" },
  ];
  return (
    <FormShell label="Result for Aditi">
      <div className="divide-y divide-rule">
        {fields.map((f) => (
          <div key={f.k} className="flex items-center justify-between gap-3 py-1.5">
            <span className="font-mono text-data text-text-mute">{f.k}</span>
            {f.tag ? (
              <Tag mono={false}>{f.v}</Tag>
            ) : (
              <span className="text-body font-medium text-text">{f.v}</span>
            )}
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <LiveLamp state="jade" size="sm" label="Auto-closed" />
        <span className="text-small text-text-dim">Clean outcome — closed itself.</span>
      </div>
    </FormShell>
  );
}
