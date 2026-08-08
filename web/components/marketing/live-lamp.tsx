"use client";

import { useRef } from "react";
import { useInView, useReducedMotion } from "framer-motion";
import { Lamp, type LampSize } from "@/components/brand/lamp";
import type { LampState } from "@/lib/lamp";

/**
 * A lamp that lights up as it scrolls into view.
 *
 * It starts unlit and runs its relay-settle the moment it enters the viewport,
 * so a row reads as coming alive with meaning rather than arriving pre-lit  
 * the product's signature moment, on the marketing page. Lit immediately (no
 * flicker) under prefers-reduced-motion.
 */
export function LiveLamp({
  state,
  size = "md",
  pulse = false,
  label,
}: {
  state: LampState;
  size?: LampSize;
  pulse?: boolean;
  label: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.8 });
  const reduced = useReducedMotion();
  const lit = reduced || inView;

  return (
    <span ref={ref} className="inline-flex">
      <Lamp state={lit ? state : "off"} size={size} pulse={pulse} label={label} />
    </span>
  );
}
