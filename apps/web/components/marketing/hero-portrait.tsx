'use client';

import Image from 'next/image';
import { motion, useScroll, useTransform } from 'framer-motion';
import { useRef } from 'react';
import { usePrefersReducedMotion } from '@/lib/hooks/use-typewriter';
import { cn } from '@/lib/cn';

/**
 * The hero's right half: a person mid-call, with the conversation floating over
 * them.
 *
 * Replaces the single large "what the caller hears / what comes back" card. That
 * card said the same thing this does and said it as a spreadsheet - the product
 * is a voice on a phone, and a face reads as that instantly where a table of
 * typed fields reads as a schema. The typed result did not disappear; it moved
 * to the section below, where there is room to show it properly.
 *
 * ## Depth, per `epic-design`'s layer model
 *
 * - **depth-0** the photograph, scaled slightly past its frame so a parallax
 *   drift never exposes an edge, and blurred a touch at its own edges by the
 *   mask rather than by a filter (a full-bleed `blur()` is a compositor layer
 *   the whole section then pays for).
 * - **depth-2** the two conversation cards, drifting at a different rate from
 *   the photo so they read as sitting in front of it rather than printed on it.
 * - the mask itself is the transition: the photo is cut by a soft radial on
 *   mobile and a vertical feather on desktop, so it *joins* the single page
 *   ground rather than sitting in a rectangle on top of it. That is the whole
 *   reason it survives §27's one-ground rule without reintroducing a band.
 *
 * ## What is deliberately not here
 *
 * No `filter: blur()` on the image, no `width`/`height` animation, and the
 * parallax is `transform` only - the three things `epic-design` names as the
 * usual causes of a scroll-driven hero dropping frames.
 */
export function HeroPortrait({
  /** The line the contact is hearing, as it arrives. Drives the live card. */
  output,
  speaking,
  className,
}: {
  output: string;
  speaking: boolean;
  className?: string;
}) {
  const reduced = usePrefersReducedMotion();
  const ref = useRef<HTMLDivElement>(null);

  // Scoped to this element, not the window: the hero is the first screen, so a
  // window-scoped progress would be near zero for its whole life on screen.
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start start', 'end start'],
  });

  // The photo travels slower than the page and the cards faster, which is the
  // whole of the depth illusion. Small numbers on purpose - a hero that slides
  // 200px reads as broken rather than as deep.
  const photoY = useTransform(scrollYProgress, [0, 1], ['0%', '12%']);
  const cardsY = useTransform(scrollYProgress, [0, 1], ['0%', '-18%']);
  const fade = useTransform(scrollYProgress, [0, 0.75], [1, 0]);

  return (
    <div
      ref={ref}
      className={cn('relative isolate h-full min-h-80 lg:min-h-[34rem]', className)}
    >
      {/* depth-0 -- the photograph. `aria-hidden` on the wrapper and an empty
          alt: it is atmosphere, and the headline beside it already says what the
          product does. A screen reader gains nothing from "man smiling at a
          phone" and loses the time it takes to say it. */}
      <motion.div
        aria-hidden
        // The bleed lives on the photo, not on the wrapper. A photo that stops
        // short of the edge reads as a picture placed on the page; one that runs
        // off it reads as the page being a photograph. Putting this on the
        // wrapper instead moved the whole coordinate space the cards are
        // positioned in, and sent the agent card off-screen.
        className="hero-portrait-mask absolute inset-y-0 left-0 -z-10 right-[calc(50%-50vw)]"
        style={reduced ? undefined : { y: photoY }}
      >
        <Image
          src="/marketing/hero-caller.webp"
          alt=""
          fill
          priority
          sizes="(min-width: 1024px) 46vw, 100vw"
          // The subject sits low and centre-left in the source (~47% across,
          // ~68% down). Left at the default `50% 50%` a tall crop frames the
          // wall behind him instead of him, which is what the first pass shipped.
          className="scale-105 object-cover object-[47%_68%]"
        />
      </motion.div>

      {/* depth-2 -- the conversation, floating. Two cards, not a transcript: the
          point is that a machine and a person are taking turns, and two turns
          is the smallest number that shows a turn. */}
      <motion.div
        className="relative h-full"
        style={reduced ? undefined : { y: cardsY, opacity: fade }}
      >
        <TurnCard
          className="absolute right-4 top-8 sm:right-8 lg:-right-4"
          who="Agent"
          line={speaking ? 'Listening…' : 'Ready'}
          tone="agent"
          live={speaking}
        />
        <TurnCard
          className="absolute bottom-10 left-0 max-w-[17rem] sm:left-2 lg:-left-8"
          who="Caller"
          line={output || '…'}
          tone="caller"
        />
      </motion.div>
    </div>
  );
}

/**
 * One turn in the conversation.
 *
 * The bars are the only colour, and they are the lamp family's own - `jade` for
 * the person, `--primary` for the agent. Not decoration: which of the two is
 * talking is the one thing a glance should get, and CLAUDE.md §10 keeps colour
 * that carries meaning away from anything that does not.
 */
function TurnCard({
  who,
  line,
  tone,
  live = false,
  className,
}: {
  who: string;
  line: string;
  tone: 'agent' | 'caller';
  live?: boolean;
  className?: string;
}) {
  return (
    <figure
      className={cn(
        'panel-glass flex max-w-xs items-center gap-3 rounded-2xl border px-3.5 py-3',
        className,
      )}
    >
      <Bars tone={tone} live={live} />
      <figcaption className="min-w-0">
        <span className="block text-label font-semibold uppercase tracking-[0.12em] text-text-mute">
          {who}
        </span>
        <span className="block truncate text-small text-text">{line}</span>
      </figcaption>
    </figure>
  );
}

/** Five bars. Animated by CSS, not by state - a per-frame React update for
 *  decoration is the cheapest thing to get wrong at this size. */
function Bars({ tone, live }: { tone: 'agent' | 'caller'; live: boolean }) {
  return (
    <span
      aria-hidden
      data-live={live || undefined}
      className={cn('turn-bars', tone === 'agent' ? 'turn-bars-agent' : 'turn-bars-caller')}
    >
      {[0, 1, 2, 3, 4].map((i) => (
        <i key={i} />
      ))}
    </span>
  );
}
