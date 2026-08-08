"use client";

import { motion } from "framer-motion";
import { usePrefersReducedMotion } from "@/lib/hooks/use-external-store";

/**
 * A heading that arrives word by word.
 *
 * Each word rises and settles on a short stagger, so a title reads as being
 * spoken rather than switched on — which is the right register for a product
 * whose whole subject is speech.
 *
 * Split on words, never on characters. Per-letter animation shreds the word
 * shapes a reader recognises, and it hands a screen reader a string of single
 * letters. Words keep the sentence intact: the markup is still a heading
 * containing text, and each word carries its own space so selection and
 * wrapping behave normally.
 *
 * Fires once when scrolled into view and never replays — a title that
 * re-animates every time you pass it is what makes a page feel like a template.
 */
export function KineticText({
  text,
  className,
  /** Seconds between consecutive words. */
  stagger = 0.045,
  /** Seconds before the first word. */
  delay = 0,
}: {
  text: string;
  className?: string;
  stagger?: number;
  delay?: number;
}) {
  const reduced = usePrefersReducedMotion();
  const words = text.split(" ");

  if (reduced) return <span className={className}>{text}</span>;

  return (
    <motion.span
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount: 0.4 }}
      variants={{ show: { transition: { staggerChildren: stagger, delayChildren: delay } } }}
      // The whole string stays readable to assistive tech as one label; the
      // per-word spans below are presentational.
      aria-label={text}
    >
      {words.map((word, i) => (
        <motion.span
          key={`${word}-${i}`}
          aria-hidden
          // inline-block is what allows a transform; the trailing space sits
          // outside it so words still break and select naturally.
          className="inline-block will-change-transform"
          variants={{
            hidden: { opacity: 0, y: "0.4em" },
            show: {
              opacity: 1,
              y: 0,
              transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
            },
          }}
        >
          {word}
          {i < words.length - 1 ? " " : null}
        </motion.span>
      ))}
    </motion.span>
  );
}
