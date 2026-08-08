"use client";

import { useEffect, useRef, useState } from "react";

export { usePrefersReducedMotion } from "./use-external-store";

export interface TypewriterOptions {
  /** Wait this long before the first character. */
  delayMs?: number;
  /** Total time to type the whole string, regardless of its length. */
  durationMs?: number;
  /** Skip the animation and land on the finished string. */
  instant?: boolean;
  /** Hold at empty until this flips true. */
  enabled?: boolean;
}

/**
 * Types a string out over a fixed duration.
 *
 * Duration rather than characters-per-second: the hero has a hard budget of under four
 * seconds for the whole sequence, so each beat needs to take the time it was given no
 * matter how long its text is.
 *
 * The reset-when-the-text-changes is done during render by comparing against the last
 * rendered inputs, which is React's sanctioned way to derive state from props. Doing it
 * in an effect would render once with the previous string still on screen.
 */
export function useTypewriter(
  text: string,
  { delayMs = 0, durationMs = 1200, instant = false, enabled = true }: TypewriterOptions = {},
): { output: string; done: boolean } {
  const finished = instant || !enabled ? (enabled ? text : "") : "";

  const [state, setState] = useState(() => ({
    key: `${text}|${instant}|${enabled}`,
    output: finished,
    done: instant && enabled,
  }));

  const key = `${text}|${instant}|${enabled}`;
  if (state.key !== key) {
    // Render-phase adjustment. React re-runs this component immediately with the new
    // state and discards the in-progress render, so nothing stale is ever painted.
    setState({ key, output: finished, done: instant && enabled });
  }

  const frame = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled || instant) return;

    let start: number | null = null;
    const total = Math.max(1, durationMs);

    function step(now: number) {
      if (start === null) start = now;
      const elapsed = now - start - delayMs;

      if (elapsed < 0) {
        frame.current = requestAnimationFrame(step);
        return;
      }

      const progress = Math.min(1, elapsed / total);
      const sliced = text.slice(0, Math.ceil(progress * text.length));

      // Inside a rAF callback, not the effect body   this is the external clock
      // driving React, which is what an effect is for.
      setState({ key, output: sliced, done: progress >= 1 });

      if (progress < 1) frame.current = requestAnimationFrame(step);
    }

    frame.current = requestAnimationFrame(step);

    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [text, delayMs, durationMs, instant, enabled, key]);

  return { output: state.output, done: state.done };
}
