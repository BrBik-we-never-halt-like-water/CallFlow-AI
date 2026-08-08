"use client";

import { useRef } from "react";
import { useCanvasAnimation } from "@/lib/hooks/use-canvas-animation";
import { cn } from "@/lib/cn";

/**
 * The hero's atmosphere: heavy waves of voice that periodically resolve into a
 * grid, then break apart into waves again.
 *
 * The cycle is the argument. Speech arrives as something loose and physical,
 * settles into an ordered record, and the line immediately fills with the next
 * call — so the field is never finished, and it spends most of its time as
 * waves because that is what the product is mostly doing.
 *
 * Chunky by design. The dots vary in size across a wide range, which is what
 * makes a particle field read as weight and texture rather than as a thin
 * dotted line; the size is a property of the particle, so the same dot stays
 * the same dot through the whole cycle. Bigger dots also carry slightly more
 * alpha, so the wave has body at its crest and thins toward the edges.
 *
 * Order comes from the grid being genuinely regular — even columns, fixed row
 * rhythm, each particle keeping one slot — which is what stops the resolved
 * state looking like a tidier accident.
 */

interface P {
  /** Position along the width, 0–1. */
  u: number;
  band: number;
  /** Vertical jitter within the band. */
  j: number;
  /** Radius in CSS pixels — the source of the chunkiness. */
  r: number;
  speed: number;
  /** Grid slot. */
  col: number;
  row: number;
  /** Per-particle lag so the field gathers raggedly, not as one block. */
  lag: number;
}

const BANDS = 3;
const ROWS = 6;
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

/** Seconds for one full waves → grid → waves pass. */
const CYCLE = 17;

export function VoiceField({ className }: { className?: string }) {
  const particles = useRef<P[] | null>(null);

  const ref = useCanvasAnimation(
    ({ ctx, w, h, t, reduced }) => {
      const cols = Math.max(16, Math.min(30, Math.round(w / 52)));
      // Six per grid slot: the grid stays regular while the wave state has enough
      // bodies to read as a mass rather than a sprinkle.
      const count = cols * ROWS * 6;

      if (!particles.current || particles.current.length !== count) {
        // Deterministic so the same field draws on every load and the grid
        // always assembles into the same arrangement.
        particles.current = Array.from({ length: count }, (_, i) => {
          const n = (i * 2654435761) % 1000;
          const m = (i * 40503) % 1000;
          return {
            u: i / count,
            band: i % BANDS,
            j: (n / 1000 - 0.5) * 1.9,
            // A wide spread, weighted small, so a few heavy dots read as
            // texture against many light ones.
            r: 1.1 + Math.pow(m / 1000, 2.1) * 4.6,
            speed: 0.55 + (n % 500) / 1000,
            col: i % cols,
            row: Math.floor(i / cols) % ROWS,
            lag: (m % 300) / 1000,
          };
        });
      }

      ctx.clearRect(0, 0, w, h);

      const time = reduced ? 4 : t;
      const p = reduced ? 0 : (t % CYCLE) / CYCLE;

      // Mostly waves. The grid is a brief resolve, not half the loop.
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

      const midY = h * 0.38;
      const amp = h * 0.15;
      const gridW = Math.min(w * 0.68, 820);
      const gridX = (w - gridW) / 2;
      const rowGap = Math.min(30, h * 0.05);
      const gridY = midY - ((ROWS - 1) * rowGap) / 2;

      for (const q of particles.current) {
        const k = ease(clamp((g - q.lag) / (1 - q.lag || 1), 0, 1));

        // ---- wave position -------------------------------------------------
        const u = (q.u + time * 0.013 * q.speed) % 1;
        const env = Math.sin(u * Math.PI) ** 0.75;
        const bandPhase = q.band * 2.1;

        // Frequencies and amplitudes drift on slow, mutually prime cycles, so
        // the wave keeps becoming a different wave instead of looping.
        const f1 = 2.6 + Math.sin(time * 0.061 + bandPhase) * 1.1;
        const f2 = 5.3 + Math.cos(time * 0.041 + bandPhase) * 1.8;
        const a1 = 1 + Math.sin(time * 0.049 + bandPhase) * 0.4;
        const a2 = 0.48 + Math.cos(time * 0.033 + bandPhase * 1.6) * 0.26;

        const shape =
          Math.sin(u * f1 * Math.PI + time * 0.44 + bandPhase) * a1 +
          Math.sin(u * f2 * Math.PI - time * 0.3 + bandPhase) * a2;

        const wx = u * w;
        const wy =
          midY +
          (q.band - (BANDS - 1) / 2) * h * 0.11 +
          shape * amp * env +
          q.j * h * 0.011;

        // ---- grid position -------------------------------------------------
        const gx = gridX + (q.col / Math.max(1, cols - 1)) * gridW;
        const gy = gridY + q.row * rowGap;

        const x = lerp(wx, gx, k);
        const y = lerp(wy, gy, k);

        // Heavier dots hold more weight; crests hold more than troughs.
        const crest = Math.max(0, shape / 1.6);
        const weight = 0.35 + (q.r / 5.7) * 0.65;
        const a = (0.1 + crest * 0.24 + k * 0.12) * weight * (0.35 + env * 0.65);

        ctx.beginPath();
        ctx.arc(x, y, q.r, 0, Math.PI * 2);
        ctx.fillStyle =
          k > 0.5 || q.band === 1
            ? `rgba(59, 47, 217, ${(a * 0.9).toFixed(3)})`
            : `rgba(14, 17, 20, ${a.toFixed(3)})`;
        ctx.fill();
      }
    },
    { staticAt: 4 },
  );

  return <canvas ref={ref} aria-hidden className={cn("block h-full w-full", className)} />;
}
