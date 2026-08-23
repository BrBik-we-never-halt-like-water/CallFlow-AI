"use client";

import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { VoiceField } from "@/components/brand/voice-field";
import { usePrefersReducedMotion } from "@/lib/hooks/use-typewriter";

/**
 * The hero is the argument, on its own.
 *
 * It had a second column: first a card showing a scripted call, then a
 * photograph with two conversation cards floating over it. Both are gone. The
 * `Listening` section immediately below already renders settled calls with
 * their typed fields, in more space and at the point in the page where the
 * claim is being proved rather than made - so the hero was showing the same
 * thing one screen earlier and smaller.
 *
 * Under `prefers-reduced-motion` the whole card renders finished on first paint.
 */

/** Shared easing for the bloom — a soft, water-like ease-out. */
const EASE_OUT = [0.22, 1, 0.36, 1] as const;

/**
 * The hero's three proof points. Each one is checkable further down the page —
 * that is the point of a hero strip, and why the wording here is the claim
 * rather than the explanation.
 */
const HERO_PROOF: { title: string }[] = [
  {
    title: "Schema-validated fields",
    },
  {
    title: "Only escalations reach a person",
  },
  {
    title: "Guarded before it dials",
  },
];

/** Staggered entrance for the headline stack. */
const RISE = {
  hidden: { opacity: 0, y: 22 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: EASE_OUT } },
};


export function Hero() {
  const reduced = usePrefersReducedMotion();


  return (
    <section className="relative overflow-hidden">
      {/* A quiet draughtsman's grid, drifting a few pixels as the page scrolls —
          the only parallax on the site, off under prefers-reduced-motion. */}
      <ParallaxGrid />

      {/* Exactly the viewport below the sticky header — the same box every
          `DeckSection` gets, so the hero owns the first screen and nothing else
          is on it.

          This used to be capped at 660px on the reasoning that a sliver of the
          next section is what tells a reader there is more below. That reads as
          a section that failed to fill rather than as an invitation, and it is
          the one thing the deck layout exists to prevent everywhere else on
          this page. Scroll affordance comes from the deck's own snap and from
          the section that follows being a full screen of its own, not from
          leaking 200px of it into this one. */}
      <div className="relative mx-auto flex min-h-[calc(100svh-var(--h-site-header))] max-w-(--container-marketing) flex-col justify-center px-4 py-10 sm:px-6">
        <div className="grid items-center gap-10 lg:flex-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,46%)] lg:items-stretch lg:gap-16">
          {/* ---- Argument: rises in as a staggered stack --------------------- */}
          <motion.div
            className="flex flex-col gap-6"
            initial={reduced ? false : "hidden"}
            animate="show"
            // Begin mid-way through the loader's fade so the headline is nearly
            // risen the instant the splash clears (~1.45s) — closes the gap while
            // still finishing in view, not behind the loader.
            variants={{ show: { transition: { staggerChildren: 0.1, delayChildren: 0.55 } } }}
          >
            <motion.h1
              variants={RISE}
              className="measure-display font-display text-display-xl text-text"
            >
              Every call comes back as data.
            </motion.h1>

            <motion.p variants={RISE} className="measure text-body-l text-text-dim">
              Dial your whole list. Get typed results back. Only the calls that need a
              person reach one.
            </motion.p>

            <motion.div variants={RISE} className="flex flex-wrap items-center gap-3 pt-1">
              <Button asChild size="lg">
                <Link href="/signup">Start free</Link>
              </Button>
              <Button asChild variant="secondary" size="lg">
                <Link href="/demo">Book a 15-min demo</Link>
              </Button>
            </motion.div>

            {/* The value-prop strip. A hero states the claim; this is the three
                things that make it checkable, one line each — deliberately a
                summary of what the sections below elaborate, which is a hero's
                job, not duplication of them. */}
            <motion.ul
              variants={RISE}
              className="mt-2 flex flex-col gap-3 border-t border-rule pt-6 sm:flex-row sm:gap-8"
            >
              {HERO_PROOF.map((p) => (
                <li key={p.title} className="flex flex-col gap-1 sm:flex-1">
                  <span className="text-small font-medium text-text">{p.title}</span>
                </li>
              ))}
            </motion.ul>
          </motion.div>

        </div>
      </div>
    </section>
  );
}

/**
 * The hero's eye-catching wave: a bold voice waveform across the top that fades
 * down into the page, drifting slightly on scroll. Replaces the faint grid so
 * the "voice" reads immediately. Off (a single resting frame) under
 * prefers-reduced-motion.
 */
function ParallaxGrid() {
  const reduced = useReducedMotion();
  const { scrollY } = useScroll();
  // Two layers at different rates: the field drifts slower than the page, which
  // is what makes it sit behind rather than on the surface.
  const y = useTransform(scrollY, [0, 700], [0, 90]);

  const band = <VoiceField />;
  const cls =
    "pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_86%_74%_at_50%_42%,#000_28%,transparent_84%)] [-webkit-mask-image:radial-gradient(ellipse_86%_74%_at_50%_42%,#000_28%,transparent_84%)]";

  if (reduced) {
    return (
      <div aria-hidden className={cls}>
        {band}
      </div>
    );
  }

  return (
    <motion.div aria-hidden style={{ y }} className={cls}>
      {band}
    </motion.div>
  );
}

