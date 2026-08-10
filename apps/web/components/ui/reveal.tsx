'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { cn } from '@/lib/cn';

/**
 * Scroll reveal - opacity plus a small lift, once, never re-fired on scroll up.
 *
 * Built on Motion's `whileInView` with `once: true`. Content that fades back out and in
 * as you scroll past it a second time is the single thing that makes a page feel like a
 * template rather than a product.
 *
 * Under `prefers-reduced-motion` the element renders in its final state with no
 * transition at all - Motion's own hook is the source of truth for that, so it can never
 * disagree with the CSS.
 */
export function Reveal({
  children,
  delayMs = 0,
  /** Distance to travel. Keep it small; this is a settle, not an entrance. */
  y = 14,
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
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{
        duration: 0.42,
        delay: delayMs / 1000,
        // Matches --ease-out, so JS-driven and CSS-driven motion feel identical.
        ease: [0.22, 1, 0.36, 1],
      }}
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
  staggerMs = 60,
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
        // Capped so a long grid does not end with a visibly late final card.
        shown: {
          transition: {
            staggerChildren: staggerMs / 1000,
            delayChildren: 0.05,
          },
        },
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
  y = 14,
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
        hidden: { opacity: 0, y },
        shown: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
        },
      }}
    >
      {children}
    </motion.div>
  );
}
