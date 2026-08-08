"use client";

import { useCanvasAnimation } from "@/lib/hooks/use-canvas-animation";
import { cn } from "@/lib/cn";

/**
 * The hero's atmosphere: layered ribbons of voice, flowing.
 *
 * A bar-chart waveform is a *reading* of a voice — a flat measurement. This is
 * the thing itself: five translucent ribbons at different depths, each drifting
 * at its own speed and phase, overlapping into something that moves like breath
 * rather than ticking like a meter.
 *
 * Depth comes from three cues layered together, which is what stops it reading
 * as a flat squiggle: further ribbons are slower, fainter and shorter in
 * amplitude, and the near ones cross in front of them.
 *
 * Filled shapes rather than strokes, at low alpha, so overlaps accumulate into
 * denser bands the way real layered translucency does. Reduced motion gets one
 * still frame of the same composition, not an empty box.
 */

interface Ribbon {
  /** 0 = furthest back, 1 = nearest. Drives speed, alpha and amplitude. */
  depth: number;
  phase: number;
  freq: number;
  drift: number;
}

const RIBBONS: Ribbon[] = [
  { depth: 0.15, phase: 0.0, freq: 1.7, drift: 0.055 },
  { depth: 0.35, phase: 1.9, freq: 2.4, drift: 0.085 },
  { depth: 0.55, phase: 3.4, freq: 1.3, drift: 0.12 },
  { depth: 0.78, phase: 5.1, freq: 2.9, drift: 0.17 },
  { depth: 1.0, phase: 2.3, freq: 1.9, drift: 0.24 },
];

export function VoiceField({ className }: { className?: string }) {
  const ref = useCanvasAnimation(
    ({ ctx, w, h, t, reduced }) => {
      ctx.clearRect(0, 0, w, h);
      const time = reduced ? 4.2 : t;

      for (const r of RIBBONS) {
        const mid = h * (0.44 + (1 - r.depth) * 0.06);
        const amp = h * (0.06 + r.depth * 0.2);
        const thickness = h * (0.02 + r.depth * 0.075);
        const speed = time * r.drift;

        // The ribbon is one closed shape: a top edge out, a bottom edge back.
        const edge = (x: number, side: 1 | -1) => {
          const u = x / w;
          const env = Math.sin(u * Math.PI) ** 0.7; // tapers at both ends
          const body =
            Math.sin(u * Math.PI * 2 * r.freq + r.phase + speed * 6) *
              amp *
              env +
            Math.sin(u * Math.PI * 2 * (r.freq * 2.3) - speed * 4) * amp * 0.28 * env;
          return mid + body + (side * thickness * env) / 2;
        };

        ctx.beginPath();
        for (let x = 0; x <= w; x += 6) ctx.lineTo(x, edge(x, 1));
        for (let x = w; x >= 0; x -= 6) ctx.lineTo(x, edge(x, -1));
        ctx.closePath();

        // Near ribbons are warmer toward the primary, far ones stay neutral —
        // a colour cue for depth on top of the geometric one.
        const g = ctx.createLinearGradient(0, 0, w, 0);
        const a = 0.05 + r.depth * 0.11;
        g.addColorStop(0, `rgba(59, 47, 217, ${(a * 0.5).toFixed(3)})`);
        g.addColorStop(0.45, `rgba(14, 17, 20, ${a.toFixed(3)})`);
        g.addColorStop(1, `rgba(59, 47, 217, ${(a * 0.35).toFixed(3)})`);
        ctx.fillStyle = g;
        ctx.fill();
      }
    },
    { staticAt: 4.2 },
  );

  return (
    <canvas
      ref={ref}
      aria-hidden
      className={cn("block h-full w-full", className)}
    />
  );
}
