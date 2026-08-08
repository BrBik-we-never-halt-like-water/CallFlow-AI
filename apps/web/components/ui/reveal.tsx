"use client";

import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/cn";

/** Shared reveal easing + entrance shape, so every section arrives the same way. */
const EASE = [0.22, 1, 0.36, 1] as const;
const HIDDEN = { opacity: 0, y: 28, scale: 0.98, filter: "blur(6px)" };
const SHOWN = { opacity: 1, y: 0, scale: 1, filter: "blur(0px)" };

/**
 * Scroll reveal — the element rises, settles, and sharpens from a soft blur as it
 * enters view, once, never re-fired on scroll up. This is the page's baseline
 * movement: with it on every section, the page reads as arriving rather than sitting
 * still. Under `prefers-reduced-motion` it renders finished with no transition.
 */
export function Reveal({
  children,
  delayMs = 0,
  /** Extra travel distance for a bolder entrance where a section wants one. */
  y = 28,
  className,
}: {
  children: React.ReactNode;
  delayMs?: number;
  y?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();

  if (reduced) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={cn(className)}
      initial={{ ...HIDDEN, y }}
      whileInView={SHOWN}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.6, delay: delayMs / 1000, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

/**
 * Staggered children. Used for card grids, where a single group fade reads as flat and
 * per-card `Reveal`s with hand-written delays get out of sync the moment one is added.
 */
export function RevealGroup({
  children,
  className,
  staggerMs = 90,
}: {
  children: React.ReactNode;
  className?: string;
  staggerMs?: number;
}) {
  const reduced = useReducedMotion();

  if (reduced) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="shown"
      viewport={{ once: true, amount: 0.15 }}
      variants={{
        hidden: {},
        shown: { transition: { staggerChildren: staggerMs / 1000, delayChildren: 0.05 } },
      }}
    >
      {children}
    </motion.div>
  );
}

/** A child of `RevealGroup`. Inherits the parent's stagger. */
export function RevealItem({
  children,
  className,
  y = 28,
}: {
  children: React.ReactNode;
  className?: string;
  y?: number;
}) {
  const reduced = useReducedMotion();

  if (reduced) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      variants={{
        hidden: { ...HIDDEN, y },
        shown: { ...SHOWN, transition: { duration: 0.6, ease: EASE } },
      }}
    >
      {children}
    </motion.div>
  );
}
