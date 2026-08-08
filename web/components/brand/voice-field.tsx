"use client";

import { useCanvasAnimation } from "@/lib/hooks/use-canvas-animation";
import { cn } from "@/lib/cn";

/**
 * The hero's atmosphere: a surface of particles in perspective, rolling.
 *
 * A true surface rather than stacked 2D lines. Particles occupy a grid in x and
 * z, their height is a sum of travelling waves, and the whole thing is
 * projected through a camera — so near rows are larger, brighter and further
 * apart, distant rows compress toward the horizon, and the depth is real rather
 * than implied by drawing some dots smaller.
 *
 * Drawn far rows first so nearer particles land on top, which removes the need
 * to sort several thousand points every frame.
 *
 * Squares rather than circles: at this count `arc` costs several times more per
 * point, and below about 3px the shape is indistinguishable anyway.
 */

const COLS = 190;
const ROWS = 46;
/** Camera distance to the nearest row / the furthest row. */
const Z_NEAR = 0.55;
const Z_FAR = 4.2;

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

export function VoiceField({ className }: { className?: string }) {
  const ref = useCanvasAnimation(
    ({ ctx, w, h, t, reduced }) => {
      ctx.clearRect(0, 0, w, h);

      const time = reduced ? 5 : t;

      // Camera. The horizon sits above the hero's centre so the surface
      // recedes into the upper half and leaves the copy below it clear.
      const focal = h * 1.15;
      const horizonY = h * 0.31;
      const camHeight = 0.3;

      for (let zi = ROWS - 1; zi >= 0; zi--) {
        // Non-linear in z so rows bunch toward the horizon the way real
        // perspective does, rather than stepping evenly.
        const zt = zi / (ROWS - 1);
        const z = Z_NEAR + Math.pow(zt, 1.6) * (Z_FAR - Z_NEAR);
        const scale = focal / z;

        // Rows fade out as they approach the horizon.
        const fog = clamp(1 - Math.pow(zt, 1.4) * 0.92, 0, 1);
        if (fog <= 0.02) continue;

        const size = Math.max(0.7, scale * 0.0022);
        const drift = time * 0.42;

        for (let xi = 0; xi < COLS; xi++) {
          const xt = xi / (COLS - 1);
          const x = (xt - 0.5) * 5.2;

          // Three travelling components. Their sum is the surface; the
          // frequencies drift on slow, mutually prime cycles so the roll never
          // repeats exactly.
          const wave =
            Math.sin(x * 1.7 + z * 0.9 - drift * 1.5 + Math.sin(time * 0.05) * 0.8) * 0.5 +
            Math.sin(x * 3.1 - z * 1.6 + drift * 1.1) * 0.22 +
            Math.sin(x * 0.8 + z * 2.4 + drift * 0.7 + Math.cos(time * 0.037) * 1.2) * 0.3;

          const y = wave * 0.34;

          const sx = w * 0.5 + x * scale * 0.34;
          const sy = horizonY + (camHeight - y) * scale * 0.34;

          // Skip anything off-canvas before doing any paint work.
          if (sx < -8 || sx > w + 8 || sy < -8 || sy > h + 8) continue;

          // Crests catch the light; troughs sink away.
          const lit = clamp(0.5 + wave * 0.55, 0, 1);
          const a = (0.05 + lit * 0.2) * fog;

          ctx.fillStyle = `rgba(59, 47, 217, ${a.toFixed(3)})`;
          ctx.fillRect(sx, sy, size, size);
        }
      }
    },
    { staticAt: 5 },
  );

  return <canvas ref={ref} aria-hidden className={cn("block h-full w-full", className)} />;
}
