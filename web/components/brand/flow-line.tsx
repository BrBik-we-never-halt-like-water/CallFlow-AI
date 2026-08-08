"use client";

import { useCanvasAnimation } from "@/lib/hooks/use-canvas-animation";
import { cn } from "@/lib/cn";

/**
 * One continuous stroke that carries the whole product in a single gesture: it
 * enters as the voice, flattens into a typed record as the words are understood,
 * then forks — most calls close themselves, a few need a person.
 *
 * Used as the divider between home-page sections, so the argument of the page and
 * the shape of the line advance together.
 *
 * Reduced motion renders the fork — the most informative moment — as a still.
 */

const PHASE = { morph: [0.3, 0.62], fork: [0.62, 0.95] } as const;

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export function FlowLine({
  className,
  /** Seconds for one full pass. */
  period = 11,
}: {
  className?: string;
  period?: number;
}) {
  const ref = useCanvasAnimation(
    ({ ctx, w, h, t, reduced }) => {
      const p = reduced ? 0.88 : (t % period) / period;
      const mid = h / 2;
      const seed = t * 1.4;
      ctx.clearRect(0, 0, w, h);

      const amp = Math.min(h * 0.3, 26);
      const yAt = (x: number) => {
        const env = Math.sin(x * Math.PI);
        const voice =
          mid + Math.sin(x * 30 + seed) * Math.sin(x * 6.4 + seed * 0.5) * amp * env;
        const record = mid + (Math.abs(((x * 14) % 1) - 0.5) < 0.045 ? -amp * 0.34 : 0);
        const m = ease(clamp((p - PHASE.morph[0]) / (PHASE.morph[1] - PHASE.morph[0]), 0, 1));
        return lerp(voice, record, m);
      };

      const forkT = clamp((p - PHASE.fork[0]) / (PHASE.fork[1] - PHASE.fork[0]), 0, 1);
      const ink = getComputedStyle(ctx.canvas).getPropertyValue("color").trim() || "#0e1114";

      ctx.lineWidth = 1.5;
      ctx.lineCap = "round";

      ctx.beginPath();
      for (let px = 0; px <= w; px += 2) {
        const y = yAt(px / w);
        if (px === 0) ctx.moveTo(px, y);
        else ctx.lineTo(px, y);
      }
      ctx.strokeStyle = ink;
      ctx.globalAlpha = 0.35 * (1 - forkT * 0.55);
      ctx.stroke();
      ctx.globalAlpha = 1;

      if (forkT > 0) {
        const from = w * 0.58;
        const branches: [string, number, number][] = [
          ["--lamp-jade", -1, 1],
          ["--lamp-flare", 1, 0.42],
        ];
        for (const [token, dir, weight] of branches) {
          const col = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
          ctx.beginPath();
          ctx.moveTo(from, mid);
          for (let px = from; px <= w; px += 2) {
            const k = (px - from) / (w - from);
            ctx.lineTo(px, mid + dir * k * k * amp * 1.5 * weight * forkT);
          }
          ctx.strokeStyle = col || ink;
          ctx.globalAlpha = forkT * 0.9;
          ctx.stroke();
          ctx.globalAlpha = 1;
        }
      }
    },
    { staticAt: 0 },
  );

  return (
    <div aria-hidden className={cn("text-text", className)}>
      <canvas ref={ref} className="block h-16 w-full" />
    </div>
  );
}
