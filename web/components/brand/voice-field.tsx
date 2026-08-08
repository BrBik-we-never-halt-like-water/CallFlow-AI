"use client";

import { useRef } from "react";
import { useCanvasAnimation } from "@/lib/hooks/use-canvas-animation";
import { cn } from "@/lib/cn";

/**
 * The hero's atmosphere: many small waves superimposing into one big messy
 * one, which periodically gathers into a grid and then breaks apart again.
 *
 * The mess is made of order. Ten thin bands each carry their own simple wave,
 * with its own frequency, phase and drift; what looks complicated is those ten
 * simple things crossing. That is also why it never repeats — the components
 * are modulated on slow, mutually prime cycles, so the composite keeps
 * becoming a different shape.
 *
 * Dots do not overlap while waving. Within a band they are evenly spaced at a
 * pitch wider than the largest diameter, and they sit exactly on their band's
 * line with no jitter, so a band stays a legible row of separate dots rather
 * than collapsing into a smear. Only band crossings put dots near each other,
 * which is the intended texture rather than a pile.
 *
 * The grid resolves upward from the waves' centre, taller than it is dense, so
 * the ordered state occupies the upper half of the hero where there is room
 * for it.
 */

interface P {
  /** Even position along its own band, 0–1. */
  u: number;
  band: number;
  /** Radius in CSS pixels. */
  r: number;
  speed: number;
  col: number;
  row: number;
  /** Per-particle lag so the field gathers raggedly, not as one block. */
  lag: number;
}

const BANDS = 10;
/** Horizontal pitch within a band, in CSS px. Must exceed the largest diameter. */
const PITCH = 10;
const R_MIN = 1.2;
const R_MAX = 3.7;

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

/** Seconds for one full waves → grid → waves pass. */
const CYCLE = 17;

export function VoiceField({ className }: { className?: string }) {
  const particles = useRef<P[] | null>(null);

  const ref = useCanvasAnimation(
    ({ ctx, w, h, t, reduced }) => {
      // Spacing is derived from the pitch, so widening the viewport adds dots
      // rather than stretching the gaps between them.
      const perBand = Math.max(40, Math.round(w / PITCH));
      const count = perBand * BANDS;
      const cols = Math.max(24, Math.min(52, Math.round(w / 26)));

      if (!particles.current || particles.current.length !== count) {
        particles.current = Array.from({ length: count }, (_, i) => {
          const band = i % BANDS;
          const idx = Math.floor(i / BANDS);
          const m = (i * 40503) % 1000;
          const n = (i * 2654435761) % 1000;
          return {
            // Even within the band — this is what keeps dots off each other.
            u: idx / perBand,
            band,
            r: R_MIN + Math.pow(m / 1000, 1.7) * (R_MAX - R_MIN),
            speed: 0.7 + (n % 400) / 1400,
            col: i % cols,
            row: Math.floor(i / cols),
            lag: (m % 280) / 1000,
          };
        });
      }

      ctx.clearRect(0, 0, w, h);

      const time = reduced ? 4 : t;
      const p = reduced ? 0 : (t % CYCLE) / CYCLE;

      const g =
        p < 0.5
          ? 0
          : p < 0.62
            ? ease(clamp((p - 0.5) / 0.12, 0, 1))
            : p < 0.76
              ? 1
              : p < 0.88
                ? 1 - ease(clamp((p - 0.76) / 0.12, 0, 1))
                : 0;

      const midY = h * 0.4;
      const rows = Math.ceil(count / cols);
      const colGap = Math.min(w * 0.72, 880) / Math.max(1, cols - 1);
      const rowGap = Math.min(13, h * 0.02);
      const gridX = (w - colGap * (cols - 1)) / 2;
      // Grow upward from the waves rather than around them: the bottom of the
      // grid sits just under the wave centre and the rest climbs into the
      // empty upper half.
      const gridBottom = midY + h * 0.06;
      const gridTop = gridBottom - rowGap * (rows - 1);

      for (const q of particles.current) {
        const k = ease(clamp((g - q.lag) / (1 - q.lag || 1), 0, 1));

        // ---- wave -----------------------------------------------------------
        const u = (q.u + time * 0.012 * q.speed) % 1;
        const env = Math.sin(u * Math.PI) ** 0.7;
        const ph = q.band * 1.31;

        // Two components per band, kept simple. The complexity in the picture
        // comes from ten bands crossing, not from one elaborate wave.
        const f1 = 2.2 + Math.sin(time * 0.057 + ph) * 0.9;
        const f2 = 4.6 + Math.cos(time * 0.039 + ph) * 1.5;
        const a1 = 1 + Math.sin(time * 0.047 + ph) * 0.38;
        const a2 = 0.42 + Math.cos(time * 0.031 + ph * 1.4) * 0.22;

        const shape =
          Math.sin(u * f1 * Math.PI + time * 0.4 + ph) * a1 +
          Math.sin(u * f2 * Math.PI - time * 0.27 + ph) * a2;

        const wx = u * w;
        // No jitter: the dot sits exactly on its band's line.
        const wy =
          midY + (q.band - (BANDS - 1) / 2) * h * 0.042 + shape * h * 0.062 * env;

        // ---- grid -----------------------------------------------------------
        const gx = gridX + q.col * colGap;
        const gy = gridTop + q.row * rowGap;

        const x = lerp(wx, gx, k);
        const y = lerp(wy, gy, k);

        const crest = Math.max(0, shape / 1.5);
        const weight = 0.4 + ((q.r - R_MIN) / (R_MAX - R_MIN)) * 0.6;
        const a = (0.09 + crest * 0.2 + k * 0.1) * weight * (0.35 + env * 0.65);

        ctx.beginPath();
        ctx.arc(x, y, q.r, 0, Math.PI * 2);
        ctx.fillStyle =
          k > 0.5 || q.band % 4 === 1
            ? `rgba(59, 47, 217, ${(a * 0.9).toFixed(3)})`
            : `rgba(14, 17, 20, ${a.toFixed(3)})`;
        ctx.fill();
      }
    },
    { staticAt: 4 },
  );

  return <canvas ref={ref} aria-hidden className={cn("block h-full w-full", className)} />;
}
