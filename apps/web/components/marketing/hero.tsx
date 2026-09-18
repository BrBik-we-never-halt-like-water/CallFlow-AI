"use client";

import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Lamp } from "@/components/brand/lamp";
import { VoiceField } from "@/components/brand/voice-field";
import { CallBoard } from "@/components/marketing/call-board";
import { Stage, StageLayer } from "@/components/marketing/stage";
import { useMediaQuery } from "@/lib/hooks/use-external-store";
import { usePrefersReducedMotion } from "@/lib/hooks/use-typewriter";

/**
 * The hero pairs an argument with a run - now staged in depth.
 *
 * Left: the thesis and the two ways in. Right: the board, posed in perspective
 * with the two artefacts a run produces floating off its plane - a typed
 * result ahead of it, an escalation above it. The pose leans a few degrees
 * toward a fine pointer and holds still everywhere else.
 *
 * The claim changed with the product (ADR-8): runs are dialled by a voice
 * agent the operator briefs, so the headline leads with the agent and the
 * board remains the proof of volume - the one thing a single-call demo
 * structurally cannot show.
 */

/**
 * The hero's three proof points. Each one is checkable further down the page,
 * and each one survives the do-not-overclaim list: typed fields are collected
 * by a real in-call tool, carriers and model keys are the operator's own, and
 * the suppression list is the gate every dial passes.
 */
const HERO_PROOF: { title: string }[] = [
  { title: "Typed fields, straight off the call" },
  { title: "Your carrier, your model keys" },
  { title: "Suppression checked before every dial" },
];

/** Staggered entrance for the headline stack. */
const RISE = {
  hidden: { opacity: 0, y: 22 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] as const } },
};

export function Hero() {
  const reduced = usePrefersReducedMotion();
  // The pose belongs to the two-column layout. Stacked under the copy, a
  // full-width board wearing an 8° yaw reads as a rendering fault, and the
  // floating chips land on its rows instead of off its plane.
  const wide = useMediaQuery("(min-width: 1024px)");

  return (
    <section className="relative overflow-hidden">
      {/* A voice waveform across the top, fading down into the page and drifting
          a few pixels as it scrolls - the only whole-page parallax on the site,
          off under prefers-reduced-motion. */}
      <ParallaxGrid />

      {/* Exactly the viewport below the sticky header - the same box every
          `DeckSection` gets, so the hero owns the first screen and nothing else
          is on it. */}
      <div className="relative mx-auto flex min-h-[calc(100svh-var(--h-site-header))] max-w-(--container-marketing) flex-col justify-center px-4 py-10 sm:px-6">
        <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,480px)] lg:gap-16">
          {/* ---- Argument: rises in as a staggered stack --------------------- */}
          <motion.div
            className="flex flex-col gap-6"
            initial={reduced ? false : "hidden"}
            animate="show"
            variants={{ show: { transition: { staggerChildren: 0.1, delayChildren: 0.55 } } }}
          >
            <motion.h1
              variants={RISE}
              className="measure-display font-display text-display-xl text-text"
            >
              Brief an agent. It calls the whole list.
            </motion.h1>

            <motion.p variants={RISE} className="measure text-body-l text-text-dim">
              Build a voice agent from a plain-English brief — your carrier, your model
              keys, your fields to collect. It dials every contact, holds the
              conversation, and comes back with typed answers. Only the calls that need
              a person reach one.
            </motion.p>

            <motion.div variants={RISE} className="flex flex-wrap items-center gap-3 pt-1">
              <Button asChild size="lg">
                <Link href="/signup">Start free</Link>
              </Button>
              <Button asChild variant="secondary" size="lg">
                <Link href="/demo">Book a 15-min demo</Link>
              </Button>
            </motion.div>

            {/* The value-prop strip: the claim above, made checkable in one line
                each - a summary of what the sections below elaborate. */}
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

          {/* ---- The run itself, on the stage --------------------------------- */}
          <motion.div
            initial={reduced ? false : { opacity: 0, y: 22 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.75, ease: [0.22, 1, 0.36, 1] }}
          >
            <Stage restX={wide ? 5 : 0} restY={wide ? -8 : 0} tilt={wide} className="relative">
              {/* Atmosphere behind the board's plane. */}
              <StageLayer
                depth={1}
                aria-hidden
                className="pointer-events-none absolute -inset-12"
              >
                <div className="stage-glow size-full" />
              </StageLayer>

              <StageLayer depth={3} className="relative">
                <CallBoard reduced={reduced} />
              </StageLayer>

              {/* A typed result, floated off the board's plane: what a settled
                  row hands back. Decorative - the board's own summary already
                  tells a screen reader the whole story. */}
              <StageLayer
                depth={4}
                float
                aria-hidden
                className="pointer-events-none absolute -left-16 -top-5 hidden lg:block"
              >
                <div className="w-52 rounded-lg border border-rule bg-surface-raised p-3 shadow-md">
                  <p className="flex items-center justify-between gap-2 border-b border-rule pb-2">
                    <span className="eyebrow text-text-mute">Typed result</span>
                    <Lamp state="jade" size="sm" />
                  </p>
                  <dl className="mt-2 flex flex-col gap-1.5 font-mono text-data">
                    <div className="flex items-baseline justify-between gap-2">
                      <dt className="text-text-mute">decision</dt>
                      <dd className="text-text">&quot;renew&quot;</dd>
                    </div>
                    <div className="flex items-baseline justify-between gap-2">
                      <dt className="text-text-mute">callback_time</dt>
                      <dd className="text-text">&quot;Thu 4pm&quot;</dd>
                    </div>
                  </dl>
                  <p className="mt-2 text-label text-text-mute">recorded mid-call</p>
                </div>
              </StageLayer>

              {/* The other artefact: a row a person owns now. */}
              <StageLayer
                depth={5}
                float
                floatLate
                aria-hidden
                className="pointer-events-none absolute -bottom-6 -right-9 hidden lg:block"
              >
                <div className="w-56 rounded-lg border border-rule bg-surface-raised p-3 shadow-md">
                  <p className="flex items-center gap-2">
                    <Lamp state="flare" size="sm" />
                    <span className="text-small font-medium text-text">Needs a person</span>
                  </p>
                  <p className="mt-1.5 text-label text-text-mute">
                    Ended without decision — a person needs to ask.
                  </p>
                </div>
              </StageLayer>
            </Stage>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/**
 * The hero's eye-catching wave: a bold voice waveform across the top that fades
 * down into the page, drifting slightly on scroll. Off (a single resting frame)
 * under prefers-reduced-motion.
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
