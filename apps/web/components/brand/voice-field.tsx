"use client";

import { useCanvasAnimation } from "@/lib/hooks/use-canvas-animation";
import { cn } from "@/lib/cn";

/**
 * The hero's atmosphere: one surface of particles that keeps changing its mind.
 *
 * A true surface rather than stacked 2D lines. Particles occupy a grid in x and
 * z, and the whole thing is projected through a camera — so near rows are
 * larger, brighter and further apart, distant rows compress toward the horizon,
 * and the depth is real rather than implied by drawing some dots smaller.
 *
 * It cycles through three formations and never stops:
 *
 *   FIELD  the rolling wave surface — the product listening
 *   GRID   the same particles flattened onto a lattice — the data it returns
 *   WAVE   the plane folded up into a wall reading as an audio waveform
 *
 * **The morph is positional, not a cross-fade, and that is the whole trick.**
 * Every particle keeps its identity across all three formations: `(xi, zi)`
 * indexes the same dot forever, and each formation is only a different answer
 * to "where does this dot belong, and how bright is it". A transition is then
 * an interpolation of that answer, so a dot visibly *travels* from the wave
 * crest to its lattice position to its place in the waveform. Cross-fading two
 * rendered images would have been far cheaper and would look like a slideshow —
 * the thing that makes this read as one object transforming is that no particle
 * is ever created or destroyed.
 *
 * Drawn far rows first so nearer particles land on top, which removes the need
 * to sort several thousand points every frame.
 *
 * Squares rather than circles: at this count `arc` costs several times more per
 * point, and below about 3px the shape is indistinguishable anyway.
 */

const COLS = 176;
const ROWS = 44;

/**
 * Alpha is quantised into this many buckets, each with a pre-built colour
 * string.
 *
 * The first version of this loop wrote `rgba(${rgb}, ${a.toFixed(3)})` and
 * assigned `fillStyle` once per particle — 16,000 string builds and 16,000
 * colour parses a frame, which measured 22.6fps with a 66.7ms worst frame.
 * Building the strings once and only reassigning `fillStyle` when the bucket
 * actually changes removes both. 48 steps is past the point where banding is
 * visible at these opacities (the whole range is 0.05–0.25 alpha).
 */
const ALPHA_STEPS = 48;
/** Camera distance to the nearest row / the furthest row. */
const Z_NEAR = 0.55;
const Z_FAR = 4.2;

/** The depth the surface folds up to when it becomes a waveform wall. */
const Z_WALL = 1.45;

/** Seconds each formation is held, and seconds spent travelling between them. */
const HOLD = 5;
const MORPH = 2.4;
const STEP = HOLD + MORPH;
const CYCLE = STEP * 3;

/**
 * How much of a morph is spent waiting for the sweep to reach you.
 *
 * 0 would move every particle in lockstep, which reads as the whole image
 * sliding rather than as a change travelling through a material. At 0.55 a
 * particle on the right edge only starts once the left edge is already
 * halfway, so the transformation crosses the field as a front.
 */
const SWEEP = 0.55;

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

/**
 * Feathers the two standing formations at their borders.
 *
 * The rolling field fades on its own: it recedes, so fog thins it toward the
 * horizon and perspective carries it off the sides. A wall sits at one constant
 * depth, so it gets neither - it ended as a hard-edged rectangle of dots
 * floating in the page, which reads as a clipping bug rather than a design.
 * Squared for a soft shoulder instead of a linear ramp, which still shows a
 * visible line where the fade begins.
 */
function edgeFade(xt: number, zt: number) {
  const fx = clamp(Math.min(xt, 1 - xt) / 0.2, 0, 1);
  const fy = clamp(Math.min(zt, 1 - zt) / 0.16, 0, 1);
  return fx * fx * (fy * fy);
}

/** Smootherstep: zero first and second derivative at both ends, so a morph has
 *  no detectable start or stop — the usual smoothstep still visibly "kicks". */
const ease = (p: number) => p * p * p * (p * (p * 6 - 15) + 10);

/**
 * The three formations, as scalar fields.
 *
 * Each writes depth, height and brightness for one particle into the scratch
 * below rather than returning an object: at 16,120 particles a frame, an
 * allocation per particle per formation is 2 million short-lived objects a
 * second, and the garbage collector shows up as periodic stutter.
 */
let outZ = 0;
let outY = 0;
let outLit = 0;

/** Per-frame constants for `field`'s slow frequency drift — one `sin`/`cos` a
 *  frame instead of one per particle. */
let phaseA = 0;
let phaseB = 0;

/**
 * Per-column caches, rebuilt once a frame.
 *
 * `wave`'s amplitude and `grid`'s vertical lines are functions of the column
 * alone — they do not vary down a row. Computed inline they ran once per
 * *particle*: four `Math.sin` and a `Math.pow` × 7,744 instead of × 176. That
 * showed up as `wave` sitting at 47.9fps with a 49.9ms worst frame on real GPU
 * hardware while the other two formations held 60.
 */
const colXt = new Float32Array(COLS);
const colX = new Float32Array(COLS);
const colAmp = new Float32Array(COLS);
const colLineX = new Float32Array(COLS);

for (let i = 0; i < COLS; i++) {
  const xt = i / (COLS - 1);
  colXt[i] = xt;
  colX[i] = (xt - 0.5) * 5.2;
  // Time-invariant, so this one is computed once for the life of the module.
  colLineX[i] = Math.pow(Math.abs(Math.cos(xt * Math.PI * 13)), 22);
}

/**
 * `z` and the sweep-phase terms are constant for a whole row or a whole frame,
 * so they are computed once by the caller and handed in. Left inside these
 * functions they were `Math.pow` and two `Math.sin` per *particle* for values
 * that changed 54 times a frame, not 12,000.
 */
function field(_xi: number, xt: number, zt: number, x: number, z: number, time: number) {
  const drift = time * 0.42;
  // Three travelling components. Their sum is the surface; the frequencies
  // drift on slow, mutually prime cycles so the roll never repeats exactly.
  const wave =
    Math.sin(x * 1.7 + z * 0.9 - drift * 1.5 + phaseA) * 0.5 +
    Math.sin(x * 3.1 - z * 1.6 + drift * 1.1) * 0.22 +
    Math.sin(x * 0.8 + z * 2.4 + drift * 0.7 + phaseB) * 0.3;

  outZ = z;
  outY = wave * 0.34;
  outLit = clamp(0.5 + wave * 0.55, 0, 1);
}

function grid(xi: number, xt: number, zt: number, x: number, _z: number, time: number) {
  // A *vertical* lattice, not a floor. Like `wave` below, depth collapses to a
  // single plane and `zt` stops meaning distance - it becomes height up the
  // wall. Drawn as a receding ground plane this read as perspective floor
  // tiling, which says "3D scene"; standing it up makes it read as a grid of
  // records, which is what the section is actually about.
  const up = zt - 0.5;

  // A slow swell so the lattice breathes instead of sitting dead.
  const breath = Math.sin(x * 0.6 + time * 0.5) * 0.02;

  // The lattice is brightness, not position: every particle stays on its own
  // node, and the ones standing on a major line are simply lit. Moving them
  // onto lines instead would leave gaps the eye reads as missing data.
  const lineX = colLineX[xi];
  const lineY = Math.pow(Math.abs(Math.cos(zt * Math.PI * 7)), 16);
  const onLine = clamp(lineX + lineY, 0, 1);

  outZ = Z_WALL;
  outY = up * 1.55 + breath;
  outLit = (0.14 + onLine * 0.86) * edgeFade(xt, zt);
}

function wave(xi: number, xt: number, zt: number, _x: number, _z: number, _time: number) {
  // Depth collapses: the ground plane stands up into a wall facing the camera,
  // so `zt` stops meaning distance and starts meaning height within the band.
  const across = zt - 0.5;

  // Read from the per-column cache: the envelope is a function of x and time
  // only, so it is the same for every particle in this column.
  const amp = colAmp[xi];

  outZ = Z_WALL;
  outY = across * amp * 2.1;
  // Brightest at the crest of the band, falling away toward the axis, so the
  // waveform has an edge rather than being a solid block.
  outLit = clamp(0.25 + Math.abs(across) * 1.6 * amp * 3, 0, 1) * edgeFade(xt, zt);
}

const FORMATIONS = [field, grid, wave] as const;

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

      // Where in the cycle we are. Under reduced motion the whole schedule is
      // bypassed: one formation, held, no travel — the picture is still there,
      // it simply never changes. Someone who asked for less motion should not
      // be handed the most animated thing on the page.
      const phase = reduced ? 0 : (time % CYCLE) / STEP;
      const from = reduced ? 0 : Math.floor(phase) % 3;
      const to = (from + 1) % 3;
      // 0 while holding, ramping 0->1 across the morph window.
      const raw = reduced ? 0 : clamp((phase - Math.floor(phase) - HOLD / STEP) / (MORPH / STEP), 0, 1);
      const morphing = raw > 0 && raw < 1;

      const shapeA = FORMATIONS[from];
      const shapeB = FORMATIONS[to];

      // The accent, read once a frame rather than per particle: this is the one
      // value that has to follow the theme, and `getComputedStyle` inside the
      // inner loop would be 12,000 style resolutions a frame.
      const accent =
        getComputedStyle(document.documentElement).getPropertyValue("--primary").trim() ||
        "#3b2fd9";
      const palette = paletteFor(hexToRgb(accent));

      // Slow drift terms: per frame, not per particle.
      phaseA = Math.sin(time * 0.05) * 0.8;
      phaseB = Math.cos(time * 0.037) * 1.2;

      let styleIndex = -1;

      // The waveform envelope, once per column per frame rather than once per
      // particle. Only worth filling when a wave is actually on screen.
      if (from === 2 || to === 2) {
        for (let i = 0; i < COLS; i++) {
          const x = colX[i];
          colAmp[i] =
            Math.abs(
              Math.sin(x * 2.3 - time * 1.6) * 0.55 +
                Math.sin(x * 5.7 + time * 2.1) * 0.28 +
                Math.sin(x * 11.3 - time * 3.4) * 0.14,
            ) *
              // A slow travelling envelope so the waveform swells and quiets
              // along its length instead of being uniformly loud.
              (0.45 + Math.abs(Math.sin(x * 0.7 + time * 0.55)) * 0.55) +
            0.04;
        }
      }

      for (let zi = ROWS - 1; zi >= 0; zi--) {
        const zt = zi / (ROWS - 1);
        // Per-row, not per-particle: this `pow` used to run once per column
        // for a value that only changes once per row.
        const zBase = Z_NEAR + Math.pow(zt, 1.6) * (Z_FAR - Z_NEAR);
        const rowDelay = zt * 0.25 * SWEEP;

        for (let xi = 0; xi < COLS; xi++) {
          const xt = colXt[xi];
          const x = colX[xi];

          shapeA(xi, xt, zt, x, zBase, time);
          let z = outZ;
          let y = outY;
          let lit = outLit;

          if (morphing) {
            // The sweep: a particle's own progress is offset by where it stands,
            // then re-normalised so everyone still finishes exactly on time.
            const p = ease(clamp((raw - (xt * 0.75 * SWEEP + rowDelay)) / (1 - SWEEP), 0, 1));
            if (p > 0) {
              shapeB(xi, xt, zt, x, zBase, time);
              z += (outZ - z) * p;
              y += (outY - y) * p;
              lit += (outLit - lit) * p;
            }
          }

          const scale = focal / z;

          // Rows fade toward the horizon. Derived from the *live* depth rather
          // than the row index, so a particle standing up into the waveform
          // wall brightens as it comes forward instead of staying hazy.
          const fogT = (z - Z_NEAR) / (Z_FAR - Z_NEAR);
          const fog = clamp(1 - fogT * fogT * 0.92, 0, 1);
          if (fog <= 0.02) continue;

          const sx = w * 0.5 + x * scale * 0.34;
          const sy = horizonY + (camHeight - y) * scale * 0.34;

          // Skip anything off-canvas before doing any paint work.
          if (sx < -8 || sx > w + 8 || sy < -8 || sy > h + 8) continue;

          // Quantised, and only re-assigned when the bucket actually changes.
          // Neighbouring particles nearly always share one, so this collapses
          // ~12,000 colour parses a frame into a few hundred.
          // Bucket 0 is below the point where a dot is distinguishable from the
          // page, and the feathered wall edges put a lot of particles there.
          // Skipping them is free contrast *and* free frame time - larger dots
          // cost fill rate, and this is where it comes back from.
          const bucket = ((ALPHA_BASE + lit * ALPHA_RANGE) * fog * ALPHA_SCALE) | 0;
          if (bucket < 1) continue;
          if (bucket !== styleIndex) {
            styleIndex = bucket;
            ctx.fillStyle = palette[bucket < 0 ? 0 : bucket > ALPHA_STEPS - 1 ? ALPHA_STEPS - 1 : bucket];
          }

          const size = scale * DOT_SCALE;
          const s = size < DOT_MIN ? DOT_MIN : size;
          ctx.fillRect(sx, sy, s, s);
        }
      }
    },
    { staticAt: 5 },
  );

  return <canvas ref={ref} aria-hidden className={cn("block h-full w-full", className)} />;
}

/**
 * Alpha floor and range per particle, and the maximum the two can reach.
 *
 * Raised from `0.05 + lit*0.2`: at that range the field was atmosphere you had
 * to look for rather than something the eye registers. The dots are also drawn
 * larger (`DOT_SCALE`). It is still background - it sits behind a headline and
 * must never compete with it - but it now reads as a thing rather than a haze.
 */
const ALPHA_BASE = 0.09;
const ALPHA_RANGE = 0.34;
const ALPHA_MAX = ALPHA_BASE + ALPHA_RANGE;

/** Particle size as a fraction of the projected scale. */
const DOT_SCALE = 0.0034;
const DOT_MIN = 1;
const ALPHA_SCALE = ALPHA_STEPS / ALPHA_MAX;

/**
 * The pre-built colour strings, rebuilt only when the accent changes — which is
 * once, or twice if the theme is toggled. Cached against the channel string
 * rather than rebuilt per frame: 48 `toFixed` calls a frame is nothing, but it
 * is also entirely avoidable.
 */
let paletteKey = "";
let paletteCache: string[] = [];

function paletteFor(rgb: string): string[] {
  if (rgb === paletteKey) return paletteCache;
  paletteKey = rgb;
  paletteCache = Array.from(
    { length: ALPHA_STEPS },
    (_, i) => `rgba(${rgb}, ${((i + 0.5) / ALPHA_SCALE).toFixed(3)})`,
  );
  return paletteCache;
}

/** `--primary` is authored as a hex token; the canvas needs its channels. */
function hexToRgb(hex: string): string {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = Number.parseInt(full, 16);
  if (!Number.isFinite(n) || full.length !== 6) return "59, 47, 217";
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`;
}
