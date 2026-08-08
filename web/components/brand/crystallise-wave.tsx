"use client";

import { useRef } from "react";
import { useCanvasAnimation } from "@/lib/hooks/use-canvas-animation";
import { cn } from "@/lib/cn";

/**
 * The hero's voice signal, drawn as particles rather than bars — so that when the
 * line finishes it can physically settle into the typed result below it.
 *
 * The claim on the hero is that every call comes back as data. This animates that
 * sentence instead of captioning it: the particles that were the voice fall into
 * the rows and dissolve as the fields take over.
 *
 * The migration is downward and self-contained rather than aimed at the real row
 * elements. Measuring sibling DOM would couple this to the card's layout and break
 * the moment anything above it reflows.
 */

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

interface Particle {
  hx: number;
  j: number;
  sp: number;
  delay: number;
}

export function CrystalliseWave({
  text,
  progress = 1,
  speaking = false,
  settled = false,
  className,
}: {
  /** Seeds the shape, so the same line always draws the same waveform. */
  text: string;
  /** 0–1 through the spoken line; drives the playhead. */
  progress?: number;
  speaking?: boolean;
  /** Flip true when the line finishes — starts the settle. */
  settled?: boolean;
  className?: string;
}) {
  const particles = useRef<Particle[] | null>(null);
  const settleStart = useRef<number | null>(null);
  const wasSettled = useRef(false);

  const ref = useCanvasAnimation(
    ({ ctx, w, h, t, reduced }) => {
      if (!particles.current) {
        const n = Math.round(clamp(w * 1.1, 220, 620));
        const seedAt = (i: number) => text.charCodeAt(i % Math.max(1, text.length)) || 65;
        particles.current = Array.from({ length: n }, (_, i) => ({
          hx: i / n,
          j: (((seedAt(i) * 13) % 100) / 100 - 0.5) * 0.9,
          sp: 0.65 + ((seedAt(i * 3) % 60) / 100),
          delay: ((seedAt(i * 7) % 100) / 100) * 0.45,
        }));
      }

      // Latch the moment settling begins so the migration runs once, not on
      // every frame after `settled` flips.
      if (settled && !wasSettled.current) {
        wasSettled.current = true;
        settleStart.current = t;
      }
      if (!settled && wasSettled.current) {
        wasSettled.current = false;
        settleStart.current = null;
      }

      const s =
        reduced && settled
          ? 1
          : settleStart.current === null
            ? 0
            : clamp((t - settleStart.current) / 1.5, 0, 1);

      ctx.clearRect(0, 0, w, h);

      const mid = h * 0.46;
      const amp = h * 0.3;
      const lead = progress;
      // Canvas cannot read a CSS variable, and resolving one is a layout read —
      // so it happens once per frame rather than once per particle.
      const brass =
        getComputedStyle(document.documentElement).getPropertyValue("--lamp-brass").trim() ||
        "#c2871a";

      for (const q of particles.current) {
        const k = ease(clamp((s - q.delay) / (1 - q.delay || 1), 0, 1));

        const env = Math.sin(q.hx * Math.PI);
        const wobble = reduced ? 0 : Math.sin(q.hx * 26 + t * 2.1 * q.sp) * 0.5 + 0.5;
        const active = speaking && Math.abs(q.hx - lead) < 0.04;
        const voiceY =
          mid +
          (Math.sin(q.hx * 21 + q.j * 4) * Math.sin(q.hx * 7.7) * amp * env +
            q.j * amp * 0.5) *
            (active ? 1.25 : 1) *
            (0.85 + wobble * 0.15);

        // Settled target: centred in its own box, so the resolved trace reads
        // as a balanced hairline rather than sinking to the bottom edge and
        // leaving the space above it looking empty.
        const restY = h * 0.52 + q.j * 3;
        const x = q.hx * w;
        const y = lerp(voiceY, restY, k) - (k > 0 && k < 1 ? Math.sin(k * Math.PI) * 6 : 0);

        // Ahead of the playhead the signal is only faintly present.
        const spoken = q.hx <= lead;
        let alpha = spoken ? 0.75 : 0.18;
        // Settling brightens, then eases down to a quiet resting trace — never
        // to zero. Fading out entirely leaves a hole in the card where the
        // signal was, which reads as a rendering fault rather than a resolution.
        if (k > 0) alpha = k < 0.7 ? lerp(alpha, 0.95, k) : lerp(0.95, 0.3, (k - 0.7) / 0.3);

        ctx.fillStyle = active ? brass : `rgba(109, 120, 126, ${alpha.toFixed(3)})`;
        const size = lerp(2.2, 1.5, k);
        ctx.fillRect(x, y, size, size);
      }
    },
    { staticAt: 2 },
  );

  return (
    <canvas
      ref={ref}
      aria-hidden
      className={cn("block h-16 w-full", className)}
    />
  );
}
