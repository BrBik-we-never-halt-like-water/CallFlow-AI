"use client";

import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/panel";
import { VoiceWave } from "./voice-wave";
import { usePrefersReducedMotion, useTypewriter } from "@/lib/hooks/use-typewriter";

/**
 * The hero pairs an argument with a proof.
 *
 * Left: the thesis and the two ways in. Right: a scripted call that plays once
 * on load — the line the contact hears, drawn as a voice waveform, then the
 * typed data that comes back. It shows the product's most characteristic moment
 * without a control to operate, and never shows an error: if the service is
 * unreachable the scripted sequence is all there ever was.
 *
 * Under `prefers-reduced-motion` both beats render finished on first paint.
 */

const DEFAULT_NAME = "Aditi";

/** The result the scripted run settles on. */
const SCRIPTED_RESULT = {
  outcome: "interested",
  sentiment: "positive",
  destination: "Dubai",
  party_size: 4,
} as const;

const RESULT_JSON = JSON.stringify(SCRIPTED_RESULT, null, 2);
const FIELD_COUNT = Object.keys(SCRIPTED_RESULT).length;

function spokenLine(name: string): string {
  const who = name.trim() || "there";
  return `Hi ${who}, this is CallFlow calling about your holiday enquiry. Is now a good time?`;
}

const SPOKEN = spokenLine(DEFAULT_NAME);

export function Hero() {
  const reduced = usePrefersReducedMotion();

  // Hold until the site loader has handed off (~1.5s), then play slowly so the
  // voice and the data feel like they are arriving, not racing. Beat one: the
  // line the contact hears. Beat two: the data that comes back.
  const heard = useTypewriter(SPOKEN, {
    delayMs: 1500,
    durationMs: 2200,
    instant: reduced,
  });
  const returned = useTypewriter(RESULT_JSON, {
    delayMs: 300,
    durationMs: 2400,
    instant: reduced,
    enabled: heard.done,
  });

  // The waveform's playhead rides the exact typing progress of the spoken line.
  const spokenProgress = SPOKEN.length
    ? Math.min(1, heard.output.length / SPOKEN.length)
    : 0;
  // Only "speaking" once characters are actually landing — so the wave rests at
  // its full shape during the wait, then sweeps as the line is spoken.
  const speaking = heard.output.length > 0 && !heard.done;

  return (
    <section className="relative overflow-hidden">
      {/* A quiet draughtsman's grid, drifting a few pixels as the page scrolls —
          the only parallax on the site, off under prefers-reduced-motion. */}
      <ParallaxGrid />

      <div className="relative mx-auto max-w-(--container-marketing) px-4 pb-(--space-section) pt-10 sm:px-6 sm:pt-16">
        <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,460px)] lg:gap-16">
          {/* ---- Argument ---------------------------------------------------- */}
          <div className="flex flex-col gap-6">
            <div className="flex items-center gap-3">
              <Eyebrow>AI calling desk</Eyebrow>
              <span aria-hidden className="h-px flex-1 bg-rule" />
            </div>

            <h1 className="measure-display font-display text-display-xl text-text">
              Every call comes back as data.
            </h1>

            <p className="measure text-body-l text-text-dim">
              CallFlow dials your list, holds a real conversation, and returns typed
              results. Only the calls that need a person reach one.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button asChild size="lg">
                <Link href="/signup">Start free</Link>
              </Button>
              <Button asChild variant="secondary" size="lg">
                <Link href="/demo">Book a 15-min demo</Link>
              </Button>
            </div>

            {/* A quiet proof row — what the product does, in three beats. */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-2 text-small text-text-mute">
              <span>Real conversations</span>
              <span aria-hidden className="h-3.5 w-px bg-rule" />
              <span>Typed results</span>
              <span aria-hidden className="h-3.5 w-px bg-rule" />
              <span>Human handoff when needed</span>
            </div>
          </div>

          {/* ---- The proof --------------------------------------------------- */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <Eyebrow>See a call resolve</Eyebrow>
              <span aria-hidden className="h-px flex-1 bg-rule" />
            </div>

            {/* A floating readout rather than a hard-edged card: soft gradient
                fill, bright top edge, no border, blocks separated by air. The
                caller line is led by a voice waveform drawn from the words. */}
            <div className="card-flow flex flex-col gap-6 p-6 sm:p-8">
              <PanelBlock label="What the caller hears">
                <div className="flex flex-col gap-4">
                  <VoiceWave
                    text={SPOKEN}
                    progress={spokenProgress}
                    speaking={speaking}
                  />
                  <p className={cn("text-body font-semibold text-text", !heard.done && "caret")}>
                    {heard.output ? `“${heard.output}${heard.done ? "”" : ""}` : " "}
                  </p>
                </div>
              </PanelBlock>

              <PanelBlock label="What comes back">
                <pre
                  className={cn(
                    "overflow-x-auto font-mono text-data text-text",
                    !returned.done && heard.done && "caret",
                  )}
                >
                  <code>{returned.output || " "}</code>
                </pre>
              </PanelBlock>

              <div className="flex items-center justify-between gap-3">
                <Eyebrow>Schema-validated</Eyebrow>
                <p className="font-mono text-data text-text-mute">{FIELD_COUNT} fields</p>
              </div>
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
        className="wave-field pointer-events-none absolute inset-x-0 top-0 h-[42rem]"
      />
    );
  }

  return (
    <motion.div
      aria-hidden
      style={{ y }}
      className="wave-field pointer-events-none absolute inset-x-0 -top-16 h-[46rem]"
    />
  );
}

function PanelBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2.5">
      <Eyebrow>{label}</Eyebrow>
      {/* A fixed minimum height stops the panel resizing as text types in. */}
      <div className="min-h-16">{children}</div>
    </div>
  );
}
