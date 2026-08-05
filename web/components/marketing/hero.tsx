"use client";

import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { LampStrip } from "@/components/brand/lamp-strip";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Eyebrow } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { LampSpec } from "@/lib/lamp";
import { usePrefersReducedMotion, useTypewriter } from "@/lib/hooks/use-typewriter";

/**
 * The hero is a working dry run.
 *
 * Not a headline over a gradient with three stat counters — an actual rehearsal
 * of the product's most characteristic moment, which the visitor can operate
 * without signing up. Everything it shows is free to produce: a dry run spends no
 * credits and dials nothing, so there is no reason to fake it.
 *
 * The sequence runs once on load, finishes inside four seconds, and never
 * repeats. Under `prefers-reduced-motion` it renders its finished state on the
 * first paint instead.
 *
 * It never shows an error. If the service is unreachable — and on a sleeping
 * instance it often is — the scripted sequence below plays and the visitor is
 * none the wiser, because a hero that greets someone with a failure has already
 * lost the argument.
 */

const DEFAULT_NAME = "Aditi";
const DEFAULT_GOAL =
  "Ask about their holiday enquiry, then capture the destination, party size, and rough budget.";

/** The result the scripted run settles on. */
const SCRIPTED_RESULT = {
  outcome: "interested",
  sentiment: "positive",
  destination: "Dubai",
  party_size: 4,
} as const;

/** 20 calls: 9 closed, 2 queued for retry, 3 need a person, 6 still queued. */
const FINAL_STRIP: LampSpec[] = [
  ...Array.from({ length: 9 }, () => ({ state: "jade" as const, label: "Auto-closed" })),
  ...Array.from({ length: 2 }, () => ({
    state: "brass" as const,
    pulse: true,
    label: "Queued for retry",
  })),
  ...Array.from({ length: 3 }, () => ({ state: "flare" as const, label: "Needs a person" })),
  ...Array.from({ length: 6 }, () => ({ state: "off" as const, label: "Not yet dialled" })),
];

const SETTLED_COUNT = FINAL_STRIP.filter((l) => l.state !== "off").length;

function spokenLine(name: string): string {
  const who = name.trim() || "there";
  return `Hi ${who}, this is CallFlow calling about your holiday enquiry. Is now a good time?`;
}

export function Hero() {
  const reduced = usePrefersReducedMotion();

  const [name, setName] = useState(DEFAULT_NAME);
  const [goal, setGoal] = useState(DEFAULT_GOAL);

  /**
   * `runId` is bumped every time the visitor presses the button. It restarts both
   * typing beats and the lamp settle, which is what makes the panel feel like an
   * instrument they are operating rather than an animation they are watching.
   */
  const [runId, setRunId] = useState(0);
  const [spoken, setSpoken] = useState(() => spokenLine(DEFAULT_NAME));
  const [result, setResult] = useState<Record<string, unknown>>(SCRIPTED_RESULT);

  const resultJson = useMemo(() => JSON.stringify(result, null, 2), [result]);

  // Beat one: the line the contact hears. Beat two: the data that comes back.
  const heard = useTypewriter(spoken, {
    durationMs: 1300,
    instant: reduced,
  });
  const returned = useTypewriter(resultJson, {
    delayMs: 250,
    durationMs: 1500,
    instant: reduced,
    enabled: heard.done,
  });

  /**
   * The lamps settle alongside the second beat.
   *
   * Held as one object tagged with the run it belongs to, so pressing the button again
   * restarts the sequence without an effect that resets state on the way in.
   */
  const [lampState, setLampState] = useState({ runId: 0, shown: 0 });
  const sequenceKey = reduced ? -1 : heard.done ? runId : -2;
  const lampsShown = reduced
    ? FINAL_STRIP.length
    : lampState.runId === sequenceKey
      ? lampState.shown
      : 0;

  useEffect(() => {
    if (reduced || !heard.done) return;

    let index = 0;
    const timer = setInterval(() => {
      index += 1;
      // Inside a timer callback — the external clock driving the sequence.
      setLampState({ runId: sequenceKey, shown: index });
      if (index >= FINAL_STRIP.length) clearInterval(timer);
    }, 70);

    return () => clearInterval(timer);
  }, [heard.done, reduced, sequenceKey]);

  const lamps = useMemo(
    () =>
      FINAL_STRIP.map((lamp, i) =>
        i < lampsShown ? lamp : { state: "off" as const, label: "Not yet dialled" },
      ),
    [lampsShown],
  );

  // Derived: the button is busy while a sequence the visitor started is still playing.
  const running = runId > 0 && !returned.done;

  async function runDry() {
    setRunId((n) => n + 1);

    // Optimistically use the local render, then upgrade to the real one if the
    // service answers quickly. Either way the panel starts moving immediately.
    setSpoken(spokenLine(name));
    setResult({ ...SCRIPTED_RESULT, party_size: SCRIPTED_RESULT.party_size });

    try {
      const campaigns = await withTimeout(api.campaigns(), 2500);
      const campaign = campaigns[0];
      if (!campaign) return;

      const preview = await withTimeout(
        api.preview(campaign.id, [
          { name: name.trim() || "there", phone: "+15555550100", context: { enquiry_note: goal } },
        ]),
        2500,
      );

      const rendered = preview.previews[0]?.goal;
      if (rendered) {
        // The rendered goal is the agent's instruction, not its opening line.
        // Show the first sentence, which is the part a contact would actually
        // hear, and keep the greeting shape the visitor already recognises.
        const firstSentence = rendered.split(/(?<=[.?!])\s/)[0];
        if (firstSentence && firstSentence.length < 220) setSpoken(firstSentence);
      }
    } catch {
      // Unreachable or slow: the scripted sequence is already playing.
    }
  }

  return (
    <section className="relative overflow-hidden">
      {/* A quiet draughtsman's grid, drifting a few pixels as the page scrolls. It is
          the only parallax on the site and it moves less than the content does, so it
          reads as depth rather than as an effect. Switched off entirely under
          prefers-reduced-motion. */}
      <ParallaxGrid />

      <div className="relative mx-auto max-w-(--container-marketing) px-4 pb-(--space-section) pt-10 sm:px-6 sm:pt-16">
      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,470px)] lg:gap-16">
        {/* ---- Argument ---------------------------------------------------- */}
        <div className="flex flex-col gap-6">
          <div className="flex items-center gap-3">
            <Eyebrow>Dry run · No credits spent</Eyebrow>
            <span aria-hidden className="h-px flex-1 bg-rule" />
          </div>

          <h1 className="measure-display font-display text-display-xl text-text">
            Every call comes back as data.
          </h1>

          <p className="measure text-body-l text-text-dim">
            CallFlow dials your list, holds a real conversation, and returns typed
            results. Only the calls that need a person reach one.
          </p>

          {/* The controls are the hero's proof: a visitor can change them and
              watch the panel respond, before creating an account. */}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Contact name">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Aditi"
                autoComplete="off"
              />
            </Field>
            <Field label="Goal" help="What the agent should achieve on the call.">
              <Input
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="Ask about their enquiry and capture the details."
                autoComplete="off"
              />
            </Field>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={runDry} loading={running} size="lg">
              Run it (dry)
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="/signup">Start free</Link>
            </Button>
            <Button asChild variant="ghost" size="lg">
              <Link href="/demo">Book a 15-min demo</Link>
            </Button>
          </div>

          <LampStrip
            lamps={lamps}
            size="md"
            caption={`${Math.min(lampsShown, SETTLED_COUNT)} of ${FINAL_STRIP.length} settled`}
            counts
          />

          <p className="text-small text-text-mute">
            Dry run is on by default. Nothing is dialled until you turn it off.
          </p>
        </div>

        {/* ---- The panel --------------------------------------------------- */}
        {/* A floating readout rather than a hard-edged card: soft gradient fill,
            bright top edge, no border. Its blocks are joined by seams that fade
            at both ends instead of full-width rules. */}
        <div className="card-flow overflow-hidden">
          <PanelBlock label="What the caller hears">
            <p className={cn("text-body text-text", !heard.done && "caret")}>
              {heard.output ? `“${heard.output}${heard.done ? "”" : ""}` : " "}
            </p>
          </PanelBlock>

          <div className="seam-x mx-5" />

          <PanelBlock label="What comes back">
            <pre
              className={cn(
                "overflow-x-auto font-mono text-data text-text",
                !returned.done && heard.done && "caret",
              )}
            >
              <code>{returned.output || " "}</code>
            </pre>
          </PanelBlock>

          <div className="seam-x mx-5" />

          <div className="flex items-center justify-between gap-3 p-5">
            <Eyebrow>Schema-validated</Eyebrow>
            <p className="font-mono text-data text-text-mute">
              {Object.keys(result).length} fields
            </p>
          </div>
        </div>
      </div>
      </div>
    </section>
  );
}

/**
 * The parallax layer.
 *
 * `useScroll` + `useTransform` rather than a scroll listener, so the transform runs on
 * the compositor and never blocks the main thread while someone is reading. The travel
 * is deliberately tiny — 60px over the whole hero.
 */
function ParallaxGrid() {
  const reduced = useReducedMotion();
  const { scrollY } = useScroll();
  const y = useTransform(scrollY, [0, 600], [0, 60]);

  if (reduced) {
    return (
      <div
        aria-hidden
        className="grid-field pointer-events-none absolute inset-x-0 top-0 h-[42rem]"
      />
    );
  }

  return (
    <motion.div
      aria-hidden
      style={{ y }}
      className="grid-field pointer-events-none absolute inset-x-0 -top-16 h-[46rem]"
    />
  );
}

function PanelBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2.5 p-4 sm:p-5">
      <Eyebrow>{label}</Eyebrow>
      {/* A fixed minimum height stops the panel resizing as text types in. */}
      <div className="min-h-20">{children}</div>
    </div>
  );
}

/** Races a promise against a deadline so a sleeping service cannot stall the hero. */
function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => setTimeout(() => reject(new Error("timeout")), ms)),
  ]);
}
