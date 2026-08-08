"use client";

import { useEffect, useRef, useState } from "react";
import { usePrefersReducedMotion } from "./use-external-store";

/**
 * Reveal-on-scroll, fired once at 20% visibility and never re-fired on scroll up.
 *
 * The "never again" part is the design requirement: content that fades back out and in
 * as you scroll past it a second time is the thing that makes a page feel like a
 * template.
 *
 * Under reduced motion the element is simply shown   `shown` is derived rather than set,
 * so there is no render where the content is hidden from someone who asked for less
 * animation.
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T | null>(null);
  const reduced = usePrefersReducedMotion();
  const [observed, setObserved] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node || observed || reduced) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setObserved(true);
            observer.disconnect();
          }
        }
      },
      { threshold: 0.2 },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [observed, reduced]);

  return { ref, shown: reduced || observed };
}
