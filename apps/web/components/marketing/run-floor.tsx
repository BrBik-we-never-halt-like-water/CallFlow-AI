"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView, useReducedMotion } from "framer-motion";
import { VoiceField } from "@/components/brand/voice-field";
import { Eyebrow } from "@/components/ui/panel";
import { cn } from "@/lib/cn";

/**
 * The floor: the volume claim, said once, lit word by word.
 *
 * Every other proof on this page is a panel - a board, a card, a queue. This
 * one is the page itself: the particle field (the same object the hero keeps
 * in its background) fills the screen, and the section's single sentence
 * lights itself the moment the section comes into view - the reader watches,
 * nothing is asked of them. Leaving and returning plays it again. The field's
 * dots are atmosphere in the brand ink, deliberately *not* lamp-coloured -
 * thousands of dots painted as call states would claim a meaning this
 * simulation doesn't have.
 *
 * The three facts under the sentence survive the do-not-overclaim list:
 * settled rows carry typed answers, credit is metered per second in integer
 * paise, and stopping a run stops dialling without cutting off anyone
 * mid-sentence.
 */

const SENTENCE =
  "One agent dials the whole list, holds every conversation, types what it learns — and hands you only the calls that need a person.";

const WORDS = SENTENCE.split(" ");

/** ~9 words a second: deliberate enough to follow, brisk enough to finish. */
const WORD_MS = 110;

const FACTS = [
  { lead: "Typed answers", rest: "on every settled row" },
  { lead: "Per-second metering", rest: "in integer paise" },
  { lead: "Stop is polite", rest: "live calls get to finish" },
] as const;

export function RunFloor() {
  const reduced = !!useReducedMotion();
  const sceneRef = useRef<HTMLDivElement>(null);
  const inView = useInView(sceneRef, { amount: 0.4 });

  const [lit, setLit] = useState(0);

  // Reset during render when the section leaves the screen, so scrolling back
  // finds the sentence ready to play again - the render-phase key-compare
  // pattern this codebase uses instead of resetting in an effect.
  const [wasInView, setWasInView] = useState(inView);
  if (wasInView !== inView) {
    setWasInView(inView);
    if (!inView) setLit(0);
  }

  useEffect(() => {
    if (reduced || !inView) return;
    // Wall-clock rather than one-word-per-fire: throttled timers would light
    // the sentence in slow motion; deriving from elapsed time keeps the pace
    // and just coarsens the steps.
    const startedAt = performance.now();
    const id = setInterval(() => {
      const n = Math.min(
        WORDS.length,
        Math.floor((performance.now() - startedAt) / WORD_MS),
      );
      setLit((current) => (current === n ? current : n));
    }, WORD_MS);
    return () => clearInterval(id);
  }, [reduced, inView]);

  const litShown = reduced ? WORDS.length : lit;
  const showFacts = reduced || lit >= WORDS.length;

  return (
    // Sized to sit inside a standard deck section (which brings its own
    // vertical padding), tall enough that the field reads as a floor rather
    // than a band.
    <div
      ref={sceneRef}
      className="relative flex min-h-[clamp(420px,64svh,720px)] items-center overflow-hidden"
    >
      {/* The field, full-bleed behind the sentence, feathered so it dissolves
          into the page rather than ending at a rectangle. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_92%_82%_at_50%_46%,#000_30%,transparent_88%)] [-webkit-mask-image:radial-gradient(ellipse_92%_82%_at_50%_46%,#000_30%,transparent_88%)]"
      >
        <VoiceField />
      </div>

      <div className="relative mx-auto w-full max-w-(--container-marketing) px-4 py-(--space-section) sm:px-6">
        <Eyebrow>The run</Eyebrow>

        {/* One sentence, lighting itself. Real text throughout - a screen
            reader reads the whole claim regardless of how far it has lit. */}
        <p className="measure-display mt-4 font-display text-display-l text-text">
          {WORDS.map((word, i) => (
            <span key={i} className="floor-word" data-lit={i < litShown ? "" : undefined}>
              {word}
              {i < WORDS.length - 1 ? " " : ""}
            </span>
          ))}
        </p>

        <motion.dl
          initial={false}
          animate={showFacts ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 }}
          transition={{ duration: 0.42, delay: showFacts ? 0.3 : 0, ease: [0.22, 1, 0.36, 1] }}
          className={cn(
            "mt-12 grid gap-6 border-t border-rule pt-8 sm:grid-cols-3",
            !showFacts && "pointer-events-none",
          )}
        >
          {FACTS.map((fact) => (
            <div key={fact.lead} className="flex flex-col gap-1">
              <dt className="text-small font-medium text-text">{fact.lead}</dt>
              <dd className="text-small text-text-dim">{fact.rest}</dd>
            </div>
          ))}
        </motion.dl>
      </div>
    </div>
  );
}
