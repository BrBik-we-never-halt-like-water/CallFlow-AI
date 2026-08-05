"use client";

import { motion, useReducedMotion } from "framer-motion";
import { Lamp } from "@/components/brand/lamp";

/**
 * The connective beat between home-page sections.
 *
 * A lamped hairline that draws itself outward from the centre lamps as it
 * scrolls into view — so the page reads as one current running through the
 * sections, a signal propagating down a spine, rather than stacked panels. Draws
 * once, never re-fires. Static under prefers-reduced-motion.
 */
export function FlowDivider() {
  const reduced = useReducedMotion();

  const half = (origin: "left" | "right") =>
    reduced ? (
      <span className="h-px flex-1 bg-rule" />
    ) : (
      <motion.span
        className={`h-px flex-1 bg-rule ${origin === "left" ? "origin-left" : "origin-right"}`}
        initial={{ scaleX: 0 }}
        whileInView={{ scaleX: 1 }}
        viewport={{ once: true, amount: 0.8 }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      />
    );

  return (
    <div className="mx-auto max-w-(--container-marketing) px-4 py-(--space-section) sm:px-6">
      <div className="flex items-center gap-3" role="separator">
        {half("right")}
        <span aria-hidden className="flex items-center gap-2.5">
          <Lamp state="jade" size="sm" />
          <Lamp state="brass" size="sm" />
          <Lamp state="flare" size="sm" />
        </span>
        {half("left")}
      </div>
    </div>
  );
}
