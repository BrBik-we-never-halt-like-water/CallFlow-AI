"use client";

import { useCallback, useEffect, useRef } from "react";
import { useTheme } from "./use-theme";
import { usePrefersReducedMotion } from "./use-external-store";

export interface CanvasFrame {
  ctx: CanvasRenderingContext2D;
  /** CSS pixels, not device pixels — the context is already scaled. */
  w: number;
  h: number;
  /** Seconds since the loop started. Frozen at `staticAt` under reduced motion. */
  t: number;
  reduced: boolean;
}

/**
 * Drives a canvas from a draw function, and stops driving it when nobody is looking.
 *
 * Three things this exists to get right, all of which are easy to miss when a canvas
 * effect is written inline in a component:
 *
 * 1. **It pauses off-screen.** An IntersectionObserver cancels the frame loop when the
 *    canvas scrolls out of view. Several of these run on one page; without it every one
 *    of them burns a phone's battery while sitting below the fold.
 * 2. **It respects reduced motion by drawing, not by hiding.** One frame is rendered at
 *    `staticAt` so the picture is still there — someone who asked for less animation gets
 *    the finished image, not an empty box.
 * 3. **It re-scales on resize.** Canvas backing store is set from devicePixelRatio, so
 *    the drawing stays sharp and the draw function can work in plain CSS pixels.
 * 4. **It repaints when the theme changes.** A draw function that resolves a CSS token
 *    is correct while it animates and wrong the moment it stops: under reduced motion
 *    one frame is painted and never again, so a theme switch left the old theme's ink
 *    on the canvas until a reload. Pixels a canvas has already drawn do not restyle
 *    themselves - the theme has to be a reason to draw.
 */
export function useCanvasAnimation(
  draw: (frame: CanvasFrame) => void,
  { staticAt = 0, paused = false }: { staticAt?: number; paused?: boolean } = {},
) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const reduced = usePrefersReducedMotion();
  const { resolved: theme } = useTheme();

  // Held in a ref so a new inline draw function on every render does not tear
  // down and restart the loop. Assigned in an effect rather than during render:
  // writing a ref while rendering is what `react-hooks/refs` exists to catch,
  // and the loop only ever reads it from a frame callback, which runs after.
  const drawRef = useRef(draw);
  useEffect(() => {
    drawRef.current = draw;
  });

  const sized = useRef({ w: 0, h: 0 });
  const ctxRef = useRef<CanvasRenderingContext2D | null>(null);

  /**
   * Measure and (re)allocate the backing store. Called on mount and on resize -
   * never per frame.
   *
   * It used to run inside the frame loop, which cost two of the most expensive
   * things you can do sixty times a second: `getBoundingClientRect()` forces a
   * layout, and assigning `width`/`height` throws away the canvas backing store
   * and allocates a new one. During a scroll - when the browser is already busy
   * laying out - that is the whole jitter (`ISSUES.md` #130). The size only
   * changes when the element changes size, and a `ResizeObserver` already knows
   * when that happens.
   */
  const size = useCallback(() => {
    const cv = ref.current;
    if (!cv) return null;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const rect = cv.getBoundingClientRect();
    const w = Math.max(1, rect.width);
    const h = Math.max(1, rect.height);
    const nextW = Math.round(w * dpr);
    const nextH = Math.round(h * dpr);

    // Guarded: assigning the same number still clears the canvas.
    if (cv.width !== nextW || cv.height !== nextH || !ctxRef.current) {
      cv.width = nextW;
      cv.height = nextH;
      const ctx = cv.getContext("2d");
      if (!ctx) return null;
      // The transform is part of the backing store, so it is reinstated here
      // and only here.
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctxRef.current = ctx;
    }

    sized.current = { w, h };
    return { ctx: ctxRef.current, w, h };
  }, []);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;

    let raf = 0;
    let start = 0;
    let visible = false;

    // Reads the cached context and dimensions - no measuring, no reallocation.
    // `size()` runs on mount and from the ResizeObserver below.
    const frame = (now: number) => {
      const ctx = ctxRef.current;
      if (!ctx) return;
      if (!start) start = now;
      const { w, h } = sized.current;
      drawRef.current({ ctx, w, h, t: (now - start) / 1000, reduced: false });
      raf = requestAnimationFrame(frame);
    };

    const still = () => {
      const s = size();
      if (!s) return;
      drawRef.current({ ...s, t: staticAt, reduced: true });
    };

    if (reduced || paused) {
      still();
      // Still needs to survive a resize, even when it never animates.
      const ro = new ResizeObserver(still);
      ro.observe(cv);
      return () => ro.disconnect();
    }

    // Measured once up front, so the first frame has a context and dimensions
    // to draw with.
    size();

    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting && !visible) {
            visible = true;
            start = 0;
            raf = requestAnimationFrame(frame);
          } else if (!e.isIntersecting && visible) {
            visible = false;
            cancelAnimationFrame(raf);
          }
        }
      },
      { threshold: 0 },
    );
    io.observe(cv);

    const ro = new ResizeObserver(() => {
      size();
    });
    ro.observe(cv);

    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      ro.disconnect();
    };
  }, [reduced, paused, staticAt, size, theme]);

  return ref;
}
