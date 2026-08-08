"use client";

import { useRef } from "react";
import { useCanvasAnimation } from "@/lib/hooks/use-canvas-animation";
import { cn } from "@/lib/cn";

/**
 * The hero's atmosphere: voice becoming structure, over and over.
 *
 * A single particle field cycles between two states forever — a flowing stream
 * (the voice) and an ordered lattice of rows and columns (the typed record).
 * It never rests in either. Calls keep arriving, so the field keeps working,
 * which is the honest picture of a system that is always running.
 *
 * Structure comes from the lattice being real: columns are evenly spaced and
 * rows are on a fixed rhythm, so the ordered state reads as a grid of records
 * rather than a cloud that happens to be tidier. Each particle keeps its own
 * slot, so the same shape assembles every cycle instead of shimmering.
 *
 * Cheap on purpose — a few hundred 2px rects, no blur, no shadow, and the whole
 * loop is a single interpolation between two precomputed positions.
 */

interface P {
  /** Stream position along the width, 0–1. */
  sx: number;
  /** Vertical offset within its stream band. */
  sj: number;
  /** Which stream band it rides. */
  band: number;
  /** Lattice slot. */
  col: number;
  row: number;
  /** Per-particle lag, so the field assembles raggedly rather than as one block. */
  lag: number;
  speed: number;
}

const BANDS = 3;
const ROWS = 5;
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export function VoiceField({ className }: { className?: string }) {
  const particles = useRef<P[] | null>(null);

  const ref = useCanvasAnimation(
    ({ ctx, w, h, t, reduced }) => {
      const cols = Math.max(14, Math.min(34, Math.round(w / 44)));
      const count = cols * ROWS;

      if (!particles.current || particles.current.length !== count) {
        // Deterministic rather than random: the same field every load, and the
        // lattice always assembles into the same grid.
        particles.current = Array.from({ length: count }, (_, i) => {
          const col = i % cols;
          const row = Math.floor(i / cols) % ROWS;
          const n = (i * 2654435761) % 1000;
          return {
            sx: ((i * 37) % 1000) / 1000,
            sj: (n / 1000 - 0.5) * 1.6,
            band: i % BANDS,
            col,
            row,
            lag: (n % 260) / 1000,
            speed: 0.6 + (n % 400) / 1000,
          };
        });
      }

      ctx.clearRect(0, 0, w, h);

      // 0 → stream, 1 → lattice, and back. Held briefly at each end so both
      // states are legible rather than permanently mid-morph.
      const CYCLE = 11;
      const p = reduced ? 0.62 : (t % CYCLE) / CYCLE;
      const phase =
        p < 0.34 ? ease(clamp(p / 0.34, 0, 1)) : p < 0.62 ? 1 : 1 - ease(clamp((p - 0.62) / 0.3, 0, 1));

      const time = reduced ? 0 : t;
      const midY = h * 0.5;
      const latticeW = Math.min(w * 0.62, 760);
      const latticeX = (w - latticeW) / 2;
      const rowGap = Math.min(26, h * 0.045);
      const latticeY = midY - ((ROWS - 1) * rowGap) / 2;

      for (const q of particles.current) {
        const k = ease(clamp((phase - q.lag) / (1 - q.lag || 1), 0, 1));

        // Stream: drifting bands of voice.
        const drift = (q.sx + time * 0.02 * q.speed) % 1;
        const env = Math.sin(drift * Math.PI);
        const bandY = midY + (q.band - (BANDS - 1) / 2) * h * 0.13;
        const sx = drift * w;
        const sy =
          bandY +
          Math.sin(drift * 14 + q.band * 2 + time * 0.7) * h * 0.07 * env +
          q.sj * h * 0.02;

        // Lattice: an even grid of records.
        const lx = latticeX + (q.col / Math.max(1, cols - 1)) * latticeW;
        const ly = latticeY + q.row * rowGap;

        const x = lerp(sx, lx, k);
        const y = lerp(sy, ly, k);

        // Ordered particles warm toward the primary; streaming ones stay ink.
        // The ordered state carries more weight than the stream, so the moment
        // the field resolves is the moment it is most visible.
        const a = 0.09 + k * 0.17;
        ctx.fillStyle =
          k > 0.55
            ? `rgba(59, 47, 217, ${(a * 1.2).toFixed(3)})`
            : `rgba(14, 17, 20, ${a.toFixed(3)})`;
        // Ordered particles square up slightly, which reads as structure.
        const s = 2 + k;
        ctx.fillRect(x, y, s, s);
      }
    },
    { staticAt: 7 },
  );

  return <canvas ref={ref} aria-hidden className={cn("block h-full w-full", className)} />;
}
