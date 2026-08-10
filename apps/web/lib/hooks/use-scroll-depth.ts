"use client";

import { useEffect, useRef } from "react";
import { usePrefersReducedMotion } from "./use-external-store";

/**
 * Gives every section in a deck a sense of depth as it scrolls.
 *
 * Each registered child gets a `--d` custom property: 1 when its centre sits on
 * the viewport's centre, falling toward 0 as it moves away. CSS turns that into
 * scale, opacity and a receding veil, so the section you are reading sits in
 * front and the ones around it fall back.
 *
 * Driven from JS rather than `animation-timeline: view()`, which is Chromium-only
 * at the time of writing — this behaves the same in Safari and Firefox, and the
 * easing curve stays ours rather than the UA's.
 *
 * Only transform, opacity and a pseudo-element's opacity are animated. Blurring
 * a full-viewport section forces a large compositor layer for every section on
 * the page, which is where this pattern usually starts dropping frames; the
 * receding effect is a veil instead, and real blur is reserved for the header.
 */
export function useScrollDepth<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T | null>(null);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const root = ref.current;
    // Under reduced motion every section simply stays at full presence — the
    // default `--d: 1` in CSS already does that, so nothing needs to run.
    if (!root || reduced) return;

    const sections = Array.from(
      root.querySelectorAll<HTMLElement>("[data-deck-section]"),
    );
    if (!sections.length) return;

    let raf = 0;
    let queued = false;

    const measure = () => {
      queued = false;
      const vh = window.innerHeight || 1;
      for (const el of sections) {
        const r = el.getBoundingClientRect();
        // Fully outside the viewport, plus a margin: leave it parked rather
        // than writing a property nobody can see.
        if (r.bottom < -vh * 0.5 || r.top > vh * 1.5) continue;
        const centre = r.top + r.height / 2;
        const dist = Math.abs(centre - vh / 2) / vh;
        const d = Math.max(0, Math.min(1, 1 - dist * 1.25));
        // Ease so the front of the curve is flat — a section reads as fully
        // present for most of the time it is on screen, and only recedes as it
        // genuinely leaves.
        el.style.setProperty("--d", (d * d * (3 - 2 * d)).toFixed(3));
      }
    };

    const onScroll = () => {
      if (queued) return;
      queued = true;
      raf = requestAnimationFrame(measure);
    };

    measure();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [reduced]);

  return ref;
}
