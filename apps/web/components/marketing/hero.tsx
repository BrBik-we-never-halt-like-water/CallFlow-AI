"use client";

import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";
import { Tag } from "@/components/ui/badge";
import { Eyebrow } from "@/components/ui/panel";
import { VoiceField } from "@/components/brand/voice-field";
import { SpeechWave } from "@/components/brand/speech-wave";
import { usePrefersReducedMotion, useTypewriter } from "@/lib/hooks/use-typewriter";

/**
 * The hero pairs an argument with a proof.
 *
 * Left: the thesis and the two ways in. Right: a scripted call that plays once
 * on load. It starts as just the voice signal and the line being spoken; once
 * the line finishes, the card blooms open — expanding up and down from its
 * centre — to reveal the typed result. The bloom grows inside a reserved height,
 * so the left column never moves.
 *
 * Under `prefers-reduced-motion` the whole card renders finished on first paint.
 */

const DEFAULT_NAME = "Aditi";

/** The typed result the scripted run settles on — shown as labelled fields
    rather than raw JSON, so the readout reads as data arriving, not a code
    dump. Categorical fields get a tag; plain facts stay text. */
type ResultField = { label: string; value: string; tag?: boolean };
const RESULT_FIELDS: ResultField[] = [
  { label: "outcome", value: "interested", tag: true },
  { label: "sentiment", value: "positive", tag: true },
  { label: "destination", value: "Dubai" },
  { label: "party size", value: "4" },
];

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
    delayMs: 1000,
    durationMs: 2200,
    instant: reduced,
  });

  // Drives the waveform playhead: exactly how far through the line we are.
  const spokenProgress = SPOKEN.length
    ? Math.min(1, heard.output.length / SPOKEN.length)
    : 0;
  // Only "speaking" once characters are actually landing.
  const speaking = heard.output.length > 0 && !heard.done;

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
        <div className="grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,460px)] lg:gap-16">
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

          {/* ---- The proof: opens as the voice signal, then blooms into the
                  typed result — expanding up and down from the centre so the
                  left column never moves. ------------------------------------ */}
          <div className="grid">
            {/* Invisible copy at final size: reserves the column height so the
                card can grow without shifting anything beside it. */}
            <div aria-hidden className="invisible [grid-area:1/1]">
              <CardShell>
                <HeardBlock spoken={SPOKEN} output={SPOKEN} done />
                <ResultBlock />
              </CardShell>
            </div>

            {/* The live card, centred in the reserved space — so added height
                pushes its top up and its bottom down in equal measure. */}
            <div className="[grid-area:1/1] self-center">
              <CardShell>
                <HeardBlock
                  spoken={SPOKEN}
                  output={heard.output}
                  done={heard.done}
                  progress={spokenProgress}
                  speaking={speaking}
                  live
                />
                <ResultBlock animate={!reduced} show={reduced || heard.done} />
              </CardShell>
            </div>
          </div>
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

/**
 * A four-bar level meter — the universal "audio is playing" mark.
 *
 * Replaces a full-width waveform inside the card. At this width a waveform has
 * to be drawn from either uniform bars, which reads as a barcode, or fake
 * amplitude data, which is a picture of a sound nobody recorded. Neither earns
 * its space next to the sentence it is describing, and the field behind the
 * hero is already carrying the voice at full size.
 *
 * It moves only while the line is being spoken, and rests flat once it lands —
 * so it reports state rather than decorating.
 */
function LevelMeter({ speaking }: { speaking: boolean }) {
  return (
    <span aria-hidden className="flex h-3 items-end gap-[3px]">
      {[0, 1, 2, 3].map((i) => (
        <i
          key={i}
          className={cn(
            "w-[3px] origin-bottom rounded-[1px]",
            speaking ? "bg-lamp-brass" : "bg-rule-strong",
          )}
          style={{
            height: speaking ? "100%" : "34%",
            animation: speaking
              ? `talk 900ms var(--ease-inout) ${i * 130}ms infinite`
              : undefined,
          }}
        />
      ))}
    </span>
  );
}

function PanelBlock({
  label,
  trailing,
  children,
}: {
  label: string;
  /** Sits on the label row, right-aligned — for a small state mark. */
  trailing?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between gap-3">
        <Eyebrow>{label}</Eyebrow>
        {trailing}
      </div>
      {/* A fixed minimum height stops the panel resizing as text types in. */}
      <div className="min-h-16">{children}</div>
    </div>
  );
}

/**
 * The floating readout: soft gradient fill, bright top edge, no border, blocks
 * separated by air. Shared by the live card and the invisible sizer behind it.
 */
function CardShell({ children }: { children: React.ReactNode }) {
  return <div className="card-feature flex flex-col gap-6 p-6 sm:p-8">{children}</div>;
}

/**
 * Beat one: the line the contact hears, with a level meter on the label row.
 * A two-line reservation keeps this block's height steady as the line types in
 * and wraps.
 */
function HeardBlock({
  spoken,
  output,
  done,
  progress = 1,
  speaking = false,
  live = false,
}: {
  spoken: string;
  output: string;
  done: boolean;
  progress?: number;
  speaking?: boolean;
  live?: boolean;
}) {
  return (
    <PanelBlock label="What the caller hears" trailing={<LevelMeter speaking={speaking} />}>
      <div className="flex flex-col gap-4">
        <SpeechWave text={spoken} progress={progress} speaking={speaking} />
        <div className="relative">
          <p aria-hidden className="invisible text-body font-semibold">
            {`“${spoken}”`}
          </p>
          <p
            className={cn(
              "absolute inset-0 text-body font-semibold text-text",
              live && !done && "caret",
            )}
          >
            {output ? `“${output}${done ? "”" : ""}` : " "}
          </p>
        </div>
      </div>
    </PanelBlock>
  );
}

function ResultRow({ label, value, tag }: ResultField) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5">
      <span className="font-mono text-data text-text-mute">{label}</span>
      {tag ? (
        <Tag mono={false}>{value}</Tag>
      ) : (
        <span className="text-body font-medium text-text">{value}</span>
      )}
    </div>
  );
}

/**
 * Beat two: the typed fields the call returned, as labelled rows rather than raw
 * JSON. When `animate`, the block unfolds by height and opacity and the rows
 * arrive in sequence once `show` is true — the bloom that opens the card. The
 * static form (no `animate`) is what the invisible sizer uses to reserve height.
 */
function ResultBlock({ animate = false, show = true }: { animate?: boolean; show?: boolean }) {
  const header = <Eyebrow>What comes back</Eyebrow>;

  if (!animate) {
    return (
      <div className="flex flex-col gap-2.5">
        {header}
        <div className="divide-y divide-rule">
          {RESULT_FIELDS.map((f) => (
            <ResultRow key={f.label} {...f} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <motion.div
      className="overflow-hidden"
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: show ? "auto" : 0, opacity: show ? 1 : 0 }}
      transition={{ duration: 0.5, ease: EASE_OUT }}
    >
      <motion.div
        className="flex flex-col gap-2.5"
        initial="hidden"
        animate={show ? "show" : "hidden"}
        variants={{ show: { transition: { staggerChildren: 0.07, delayChildren: 0.12 } } }}
      >
        {header}
        <div className="divide-y divide-rule">
          {RESULT_FIELDS.map((f) => (
            <motion.div
              key={f.label}
              variants={{
                hidden: { opacity: 0, y: 6 },
                show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: EASE_OUT } },
              }}
            >
              <ResultRow {...f} />
            </motion.div>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}
