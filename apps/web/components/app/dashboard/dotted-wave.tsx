'use client';

import { useEffect, useRef } from 'react';
import { cn } from '@/lib/cn';

/**
 * A window onto one continuous waveform, drawn inside a card.
 *
 * Every instance samples the *same* global wave - the canvas measures where
 * it sits inside the grid and draws only that horizontal and vertical slice.
 * So the crests line up across the gaps between cards, as if the cards were
 * separate screens showing one picture, while the gaps themselves stay
 * empty. That is the whole effect: a single wave, cut into pieces by the
 * card edges rather than repeated per card.
 *
 * The waveform itself is the hero's (`components/brand/wave-canvas.tsx`).
 *
 * The motion is the point: dots move *through* the wave rather than the
 * whole field sliding sideways, which is what makes it read as a voice
 * rather than as a drifting texture. `amp()` below is the hero's function -
 * three layered sines, two travelling against one, under a centre-weighted
 * envelope - so both surfaces are literally the same waveform at different
 * scales.
 *
 * Drawn on a canvas for the same reason the hero is: this is per-frame
 * geometry for a few hundred points, which is cheap to paint and expensive
 * to express as animated DOM. Every instance shares one `requestAnimationFrame`
 * loop, so a page with both cards still costs a single frame callback, and
 * the loop stops entirely when the last card unmounts.
 */

type Draw = (t: number) => void;

const callbacks = new Set<Draw>();
let rafId: number | null = null;
let startTs: number | null = null;

function loop(ts: number) {
  if (startTs === null) startTs = ts;
  const t = (ts - startTs) / 1000;
  callbacks.forEach((cb) => cb(t));
  rafId = requestAnimationFrame(loop);
}

function register(cb: Draw) {
  callbacks.add(cb);
  if (rafId === null) rafId = requestAnimationFrame(loop);
}

function unregister(cb: Draw) {
  callbacks.delete(cb);
  if (callbacks.size === 0 && rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
    startTs = null;
  }
}

/** The hero's layered travelling sine, unchanged. */
function amp(x: number, t: number, seed: number) {
  const env = Math.sin(Math.PI * x);
  const w =
    Math.sin(x * 20 - t * 2.1 + seed) * 0.55 +
    Math.sin(x * 12 + t * 1.3 + seed) * 0.32 +
    Math.sin(x * 34 - t * 3.0) * 0.18;
  return env * env * w;
}

const ROWS = 4;
/** Dot pitch in CSS px; smaller is denser. */
const PITCH = 11;

export function DottedWave({
  seed = 0,
  /** How many rows of dots to draw. The full-bleed backdrop wants more than
   *  a single card does, since it spans the whole grid rather than one box. */
  rows = ROWS,
  /** Peak alpha of the first row; later rows fade from it. */
  alpha = 0.42,
  className,
}: {
  seed?: number;
  rows?: number;
  alpha?: number;
  className?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const reduce = window.matchMedia?.(
      '(prefers-reduced-motion: reduce)',
    ).matches;

    // Canvas cannot read a CSS variable, so the brand token is resolved once
    // here against the card itself - which is inside `.dash`, where
    // `--dash-brand` is actually defined.
    const color =
      getComputedStyle(canvas)
        .getPropertyValue('--dash-brand')
        .trim() || '#f04a49';

    // Where this card sits inside the grid, as fractions 0..1. Remeasured on
    // resize, because the window it should draw changes with the layout.
    let win = { x0: 0, x1: 1, y0: 0, y1: 1 };

    let dpr = 1;
    const size = () => {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.max(1, canvas.clientWidth * dpr);
      canvas.height = Math.max(1, canvas.clientHeight * dpr);

      // The grid is the wave's coordinate space - the element the cards are
      // laid out in, so every card measures against the same box.
      const field = canvas.closest('.dash-grid') as HTMLElement | null;
      const box = canvas.getBoundingClientRect();
      const fieldBox = field?.getBoundingClientRect();
      if (!fieldBox || fieldBox.width === 0 || fieldBox.height === 0) return;

      win = {
        x0: (box.left - fieldBox.left) / fieldBox.width,
        x1: (box.right - fieldBox.left) / fieldBox.width,
        y0: (box.top - fieldBox.top) / fieldBox.height,
        y1: (box.bottom - fieldBox.top) / fieldBox.height,
      };
    };
    size();
    const ro = new ResizeObserver(size);
    ro.observe(canvas);
    const fieldEl = canvas.closest('.dash-grid');
    if (fieldEl) ro.observe(fieldEl);

    const draw = (t: number) => {
      const W = canvas.width;
      const H = canvas.height;
      if (W === 0 || H === 0) return;

      const columns = Math.max(10, Math.floor(canvas.clientWidth / PITCH));
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = color;

      // Rows belong to the *grid*, not to this card: each row's baseline is
      // a fraction of the whole grid's height, and the card draws only the
      // ones that fall inside its own vertical window. Two cards side by
      // side therefore show the same rows at the same heights.
      const spanY = win.y1 - win.y0 || 1;
      const spanX = win.x1 - win.x0 || 1;

      for (let row = 0; row < rows; row += 1) {
        const rowT = t - row * 0.16;
        ctx.globalAlpha = Math.max(0.04, alpha - row * (alpha / rows));

        // Baseline in grid space, then mapped into this canvas.
        const gridY = (row + 0.7) / (rows + 0.4);
        const localY = ((gridY - win.y0) / spanY) * H;
        // Rows far outside the card contribute nothing - skip the work.
        if (localY < -H * 0.4 || localY > H * 1.4) continue;

        for (let i = 0; i < columns; i += 1) {
          const local = i / (columns - 1);
          // The sample point in *grid* space: this is what makes the wave
          // continuous. A card on the right samples the right of the wave.
          const gx = win.x0 + local * spanX;
          const cx = local * W;
          // Amplitude scales with the grid's height, not the card's, so a
          // short card shows a shallow slice rather than its own full swing.
          const cy = localY + amp(gx, rowT, seed) * (H / spanY) * 0.16;
          const r = Math.max(0.7, 1.6 - row * 0.16) * dpr;

          ctx.beginPath();
          ctx.arc(cx, cy, Math.max(0.6 * dpr, r), 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    };

    // A single resting frame under reduced motion: the texture still exists,
    // it just does not move.
    if (reduce) {
      draw(0);
      return () => ro.disconnect();
    }

    register(draw);
    return () => {
      unregister(draw);
      ro.disconnect();
    };
  }, [seed, rows, alpha]);

  return (
    <canvas
      ref={ref}
      aria-hidden
      className={cn(
        'pointer-events-none absolute inset-0 size-full',
        className,
      )}
    />
  );
}
