"use client";

import { useRef } from "react";
import { useCanvasAnimation } from "@/lib/hooks/use-canvas-animation";
import { cn } from "@/lib/cn";

/**
 * The hero's atmosphere: waves of voice, drawn in particles, never repeating.
 *
 * Three bands drift across the width, and the shape of each is a sum of three
 * sine components whose frequency, amplitude and phase are themselves modulated
 * on slow, mutually prime cycles. The result never settles into a loop you can
 * catch — the wave keeps becoming a different wave, which is the honest picture
 * of a line that is always carrying a different call.
 *
 * Particles rather than a stroke so the bands can overlap into denser regions
 * the way layered translucency does, and so the field reads as made of many
 * small events rather than one drawn line.
 *
 * Sits above centre. Weight low in the frame fights the headline for the
 * bottom half of the hero, where the copy and the buttons live.
 */

interface P {
  /** Position along the width, 0–1. */
  u: number;
  /** Which band it rides. */
  band: number;
  /** Vertical jitter within the band, so bands have thickness. */
  j: number;
  /** Per-particle drift rate. */
  speed: number;
}

const BANDS = 3;

export function VoiceField({ className }: { className?: string }) {
  const particles = useRef<P[] | null>(null);

  const ref = useCanvasAnimation(
    ({ ctx, w, h, t, reduced }) => {
      // Density is what makes a particle wave read as a wave rather than as
      // scatter: below roughly one particle every 2px of band, the eye gets
      // dots instead of a line.
      const count = Math.round(Math.min(2400, Math.max(900, w * 1.6)));

      if (!particles.current || particles.current.length !== count) {
        // Deterministic: the same field on every load, no hydration flicker.
        particles.current = Array.from({ length: count }, (_, i) => {
          const n = (i * 2654435761) % 1000;
          return {
            u: i / count,
            band: i % BANDS,
            j: (n / 1000 - 0.5) * 1.7,
            speed: 0.55 + (n % 500) / 1000,
          };
        });
      }

      ctx.clearRect(0, 0, w, h);

      const time = reduced ? 3.6 : t;
      // Above centre: the lower half of the hero belongs to the copy.
      const midY = h * 0.38;
      const amp = h * 0.1;

      for (const q of particles.current) {
        // Horizontal drift, wrapped — the band is always travelling.
        const u = (q.u + time * 0.014 * q.speed) % 1;
        const x = u * w;

        // Taper at both ends so the bands dissolve rather than being cut off.
        const env = Math.sin(u * Math.PI) ** 0.8;

        // Three components, each with its own slowly modulated frequency and
        // amplitude. Mutually prime periods mean the combined shape does not
        // return to itself on any short cycle.
        const bandPhase = q.band * 2.1;
        const f1 = 3.1 + Math.sin(time * 0.07 + bandPhase) * 1.4;
        const f2 = 6.7 + Math.cos(time * 0.043 + bandPhase) * 2.2;
        const f3 = 11.3 + Math.sin(time * 0.031 - bandPhase) * 3.1;

        const a1 = 1 + Math.sin(time * 0.053 + bandPhase) * 0.45;
        const a2 = 0.55 + Math.cos(time * 0.037 + bandPhase * 1.7) * 0.3;
        const a3 = 0.22 + Math.sin(time * 0.029 + bandPhase * 0.6) * 0.14;

        const shape =
          Math.sin(u * f1 * Math.PI + time * 0.5 + bandPhase) * a1 +
          Math.sin(u * f2 * Math.PI - time * 0.33 + bandPhase) * a2 +
          Math.sin(u * f3 * Math.PI + time * 0.21) * a3;

        const bandOffset = (q.band - (BANDS - 1) / 2) * h * 0.1;
        const y = midY + bandOffset + shape * amp * env + q.j * h * 0.005;

        // Crests carry more weight than troughs, so the wave has a lit edge.
        const crest = Math.max(0, shape / 1.8);
        const a = (0.07 + crest * 0.2) * (0.3 + env * 0.7);
        ctx.fillStyle =
          q.band === 1
            ? `rgba(59, 47, 217, ${(a * 0.85).toFixed(3)})`
            : `rgba(14, 17, 20, ${a.toFixed(3)})`;
        ctx.fillRect(x, y, 2, 2);
      }
    },
    { staticAt: 3.6 },
  );

  return <canvas ref={ref} aria-hidden className={cn("block h-full w-full", className)} />;
}
