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
 * morphs in place through the pipeline — her validated row, the campaign goal,
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
    title: "Choose a campaign",
    body: "Start from a template or write your own goal, and pick the fields to extract.",
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
    <section id="how-it-works" className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          eyebrow="How it works"
          title="Watch one contact become a triaged result."
        />
      </Reveal>

      <div className="mt-10 grid items-start gap-10 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)] lg:gap-16">
        <StepTracker step={step} onSelect={setStep} reduced={reduced} />
        <Reveal delayMs={80}>
          <MorphCard step={step} reduced={reduced} />
        </Reveal>
      </div>
    </section>
  );
}

/**
 * The vertical pipeline tracker. A line fills jade up to the current stage; each
 * stage's node lights as the signal reaches it, and only the current stage shows
 * its description — keeping the column quiet. Stages are clickable to jump.
 */
function StepTracker({
  step,
  onSelect,
  reduced,
}: {
  step: number;
  onSelect: (i: number) => void;
  reduced: boolean;
}) {
  const fill = STEPS.length > 1 ? (step / (STEPS.length - 1)) * 100 : 0;

  return (
    <Reveal>
      {/* Titles keep a constant height; the description sits in a fixed-height
          slot below, so switching steps never changes the column height (which
          would shove the sections underneath). */}
      <ol className="relative flex flex-col gap-6 pl-8">
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
                className="group relative flex w-full items-baseline gap-2 py-0.5 text-left"
              >
                <span
                  aria-hidden
                  className="absolute top-1/2 -left-8 flex size-[18px] -translate-y-1/2 items-center justify-center rounded-full bg-surface ring-1 ring-rule"
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
              </button>
            </li>
          );
        })}
      </ol>

      <div className="mt-6 min-h-[4.5rem] border-t border-rule pt-4">
        <AnimatePresence mode="wait">
          <motion.p
            key={step}
            initial={reduced ? false : { opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? { opacity: 0 } : { opacity: 0, y: -4 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="max-w-[38ch] text-small text-text-dim"
          >
            {STEPS[step].body}
          </motion.p>
        </AnimatePresence>
      </div>
    </Reveal>
  );
}

/** The demo card: the same contact's data, morphing between the four forms. */
function MorphCard({ step, reduced }: { step: number; reduced: boolean }) {
  const forms = [<LoadForm key="l" />, <ChooseForm key="c" />, <RunForm key="r" />, <TriageForm key="t" />];

  return (
    <div className="card-flow relative flex h-[16.5rem] flex-col justify-center overflow-hidden p-6 sm:p-8">
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
    <FormShell label="Campaign chosen">
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
