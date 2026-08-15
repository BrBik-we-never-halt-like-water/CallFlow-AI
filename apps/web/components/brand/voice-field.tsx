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
 * **Circles, batched into one fill per opacity.** These were squares because
 * `arc` + `fill` per point costs several times a `fillRect` at this count — but
 * that is a per-*call* cost, not a per-circle one. The arcs are accumulated into
 * a `Path2D` per alpha bucket and filled ~47 times a frame instead of once per
 * particle. `DESIGN_NOTES.md` §21 has the measurements, including the one that
 * made the count drop from 176x44 to 124x32.
 */

const COLS = 124;
const ROWS = 32;

/** Every Nth column and row is a lattice line when the field becomes a grid. */
const GRID_EVERY_COL = 9;
const GRID_EVERY_ROW = 5;

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
const HOLD = 6.5;
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

/** Half the world-space width the field occupies. `x` runs -X_HALF..+X_HALF. */
const X_HALF = 2.6;

/**
 * How far past the canvas edge the standing formations reach.
 *
 * Mapping the world exactly onto the canvas width sounds right and is not: the
 * feathered border then eats its fade out of visible width, so a wall that
 * "spans the screen" reads as ~10% narrower than it is on each side. Overrunning
 * pushes most of the fade off-canvas and leaves the rest as a short dissolve at
 * the very edge.
 */
const WALL_OVERSCAN = 1.18;

/**
 * How much of the wall's width and height the border fade occupies.
 *
 * Combined with the overscan above, `EDGE_X` puts the fade in roughly the outer
 * 5% of the visible width - enough that the formation dissolves rather than
 * stopping, and no more than that.
 */
const EDGE_X = 0.12;
const EDGE_Y = 0.1;

/** How tall the two standing formations reach, in world units. */
const GRID_HEIGHT = 2.6;
const WAVE_HEIGHT = 2.7;

/**
 * Dot size per formation, as a multiplier on `DOT_RADIUS`.
 *
 * The rolling field's near rows sit at a third of the wall's depth, so
 * perspective already draws them two to three times larger than anything in the
 * grid or the waveform - one radius for all three left the field coarse and the
 * two walls fine. These pull the three back to roughly the same apparent
 * weight.
 */
const SIZE_FIELD = 0.78;
const SIZE_WALL = 1.38;

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
  const fx = clamp(Math.min(xt, 1 - xt) / EDGE_X, 0, 1);
  const fy = clamp(Math.min(zt, 1 - zt) / EDGE_Y, 0, 1);
  return fx * fx * (fy * fy);
}

/** Smootherstep: zero first and second derivative at both ends, so a morph has
 *  no detectable start or stop — the usual smoothstep still visibly "kicks". */
const ease = (p: number) => p * p * p * (p * (p * 6 - 15) + 10);

/**
 * The three formations, as scalar fields.
 *
 * Each writes depth, height, brightness and dot size for one particle into the
 * scratch below rather than returning an object: at several thousand particles
 * a frame, an allocation per particle per formation is millions of short-lived
 * objects a second, and the garbage collector shows up as periodic stutter.
 *
 * `outSize` interpolates through a morph like everything else, so a dot grows
 * or shrinks *while* it travels rather than snapping at either end.
 */
let outZ = 0;
let outY = 0;
let outLit = 0;
let outSize = 1;

/** Per-frame constants for `field`'s slow frequency drift — one `sin`/`cos` a
 *  frame instead of one per particle. */
let phaseA = 0;
let phaseB = 0;

/**
 * Per-column caches, rebuilt once a frame.
 *
 * `wave`'s amplitude and `grid`'s vertical lines are functions of the column
 * alone — they do not vary down a row. Computed inline they ran once per
 * *particle* rather than once per column, which showed up as `wave` sitting at
 * 47.9fps with a 49.9ms worst frame on real GPU hardware while the other two
 * formations held 60.
 */
const colXt = new Float32Array(COLS);
const colX = new Float32Array(COLS);
const colAmp = new Float32Array(COLS);
const colLineX = new Float32Array(COLS);

for (let i = 0; i < COLS; i++) {
  const xt = i / (COLS - 1);
  colXt[i] = xt;
  colX[i] = (xt - 0.5) * 2 * X_HALF;
  // Indexed, not sampled. A `cos^22` ridge was continuous in x, so whether a
  // lattice line landed on a column of particles or fell between two of them
  // depended on COLS - the lines faded out entirely when the count changed.
  colLineX[i] = i % GRID_EVERY_COL === 0 ? 1 : 0;
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
  outSize = SIZE_FIELD;
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
  const lineY = Math.round(zt * (ROWS - 1)) % GRID_EVERY_ROW === 0 ? 1 : 0;
  const onLine = lineX || lineY;

  outZ = Z_WALL;
  outY = up * GRID_HEIGHT + breath;
  outLit = (0.26 + onLine * 0.74) * edgeFade(xt, zt);
  // The filler between lines is drawn smaller as well as dimmer. It reads as a
  // lattice either way, the lines carry more weight for the contrast, and the
  // ~85% of particles that are not on a line stop costing full fill rate.
  outSize = onLine ? SIZE_WALL : SIZE_WALL * 0.66;
}

function wave(xi: number, xt: number, zt: number, _x: number, _z: number, _time: number) {
  // Depth collapses: the ground plane stands up into a wall facing the camera,
  // so `zt` stops meaning distance and starts meaning height within the band.
  const across = zt - 0.5;

  // Read from the per-column cache: the envelope is a function of x and time
  // only, so it is the same for every particle in this column.
  const amp = colAmp[xi];

  outZ = Z_WALL;
  outY = across * amp * WAVE_HEIGHT;
  // Brightest at the crest of the band, falling away toward the axis, so the
  // waveform has an edge rather than being a solid block.
  outLit = clamp(0.25 + Math.abs(across) * 1.6 * amp * 3, 0, 1) * edgeFade(xt, zt);
  outSize = SIZE_WALL;
}

const FORMATIONS = [field, grid, wave] as const;

export function VoiceField({ className }: { className?: string }) {
  const ref = useCanvasAnimation(
    ({ ctx, w, h, t, reduced }) => {
      ctx.clearRect(0, 0, w, h);
      ctx.globalAlpha = 1;

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
      const style = getComputedStyle(document.documentElement);
      const accent =
        style.getPropertyValue("--field-ink").trim() ||
        style.getPropertyValue("--primary").trim() ||
        "#3b2fd9";
      const rgb = hexToRgb(accent);
      ctx.fillStyle = `rgb(${rgb})`;

      // Applied to the final opacity rather than folded into ALPHA_BASE/RANGE,
      // which would push the buckets past ALPHA_STEPS and quietly lose the top
      // of the range to clamping.
      const gain = Number.parseFloat(style.getPropertyValue("--field-gain")) || 1;

      // Slow drift terms: per frame, not per particle.
      phaseA = Math.sin(time * 0.05) * 0.8;
      phaseB = Math.cos(time * 0.037) * 1.2;

      /**
       * Horizontal spread, solved per frame so the standing formations reach
       * both edges of whatever width they are given.
       *
       * `x` is world-space and was projected through a fixed 0.34, which made
       * the wall a fixed multiple of the canvas *height* — on a wide viewport it
       * ended as a band floating in the middle with bare page either side. This
       * solves the other way round: pick the horizontal factor that maps the
       * world-x range onto the full canvas width at the wall's depth, so the
       * grid and the waveform always span it. Vertical keeps the original 0.34,
       * or the perspective would shear.
       */
      const wallScale = focal / Z_WALL;
      const spreadX = ((w * 0.5) / (X_HALF * wallScale)) * WALL_OVERSCAN;

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
          let dotSize = outSize;

          if (morphing) {
            // The sweep: a particle's own progress is offset by where it stands,
            // then re-normalised so everyone still finishes exactly on time.
            const p = ease(clamp((raw - (xt * 0.75 * SWEEP + rowDelay)) / (1 - SWEEP), 0, 1));
            if (p > 0) {
              shapeB(xi, xt, zt, x, zBase, time);
              z += (outZ - z) * p;
              y += (outY - y) * p;
              lit += (outLit - lit) * p;
              dotSize += (outSize - dotSize) * p;
            }
          }

          const scale = focal / z;

          // Rows fade toward the horizon. Derived from the *live* depth rather
          // than the row index, so a particle standing up into the waveform
          // wall brightens as it comes forward instead of staying hazy.
          const fogT = (z - Z_NEAR) / (Z_FAR - Z_NEAR);
          const fog = clamp(1 - fogT * fogT * 0.92, 0, 1);
          if (fog <= 0.02) continue;

          const sx = w * 0.5 + x * scale * spreadX;
          const sy = horizonY + (camHeight - y) * scale * 0.34;

          // Skip anything off-canvas before doing any paint work. The field's
          // near rows now genuinely overrun the sides, so this culls more than
          // it used to rather than less.
          if (sx < -8 || sx > w + 8 || sy < -8 || sy > h + 8) continue;

          // Bucket 0 is below the point where a dot is distinguishable from the
          // page, and the feathered edges put a lot of particles there.
          // Skipping them is free contrast and free frame time.
          let bucket = ((ALPHA_BASE + lit * ALPHA_RANGE) * fog * ALPHA_SCALE) | 0;
          if (bucket < 1) continue;
          if (bucket > ALPHA_STEPS - 1) bucket = ALPHA_STEPS - 1;

          const r = scale * DOT_RADIUS * dotSize;
          const path = buckets[bucket] ?? (buckets[bucket] = new Path2D());
          // `arc` alone would draw a line from wherever the subpath left off,
          // joining every dot in the bucket into one blob.
          path.moveTo(sx + r, sy);
          path.arc(sx, sy, r < 0.6 ? 0.6 : r, 0, TAU);
        }
      }

      // One fill per opacity, not one draw call per particle - which is what
      // buys real circles for slightly less than the squares cost. A
      // per-particle `drawImage` blit, the obvious first idea, measured two
      // orders of magnitude worse than either (`DESIGN_NOTES.md` §21).
      //
      // The tradeoff is that back-to-front ordering now only holds within a
      // bucket. At these opacities, with dots this sparse, overlap between two
      // different buckets is rare and invisible when it happens.
      for (let b = 1; b < ALPHA_STEPS; b++) {
        const path = buckets[b];
        if (!path) continue;
        ctx.globalAlpha = clamp(alphaOf(b) * gain, 0, 1);
        ctx.fill(path);
        buckets[b] = null;
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
 * larger (`DOT_RADIUS`). It is still background - it sits behind a headline and
 * must never compete with it - but it now reads as a thing rather than a haze.
 */
const ALPHA_BASE = 0.09;
const ALPHA_RANGE = 0.34;
const ALPHA_MAX = ALPHA_BASE + ALPHA_RANGE;

/** Particle radius as a fraction of the projected scale. */
const DOT_RADIUS = 0.0022;
const ALPHA_SCALE = ALPHA_STEPS / ALPHA_MAX;
const TAU = Math.PI * 2;

/**
 * One accumulating path per opacity, reused across frames.
 *
 * Module-level rather than per-frame: 47 `Path2D` allocations sixty times a
 * second is exactly the sort of churn the scratch variables above exist to
 * avoid. Each is dropped as it is filled and rebuilt on demand next frame -
 * `Path2D` has no clear.
 */
const buckets: (Path2D | null)[] = new Array(ALPHA_STEPS).fill(null);

/**
 * The opacity a bucket represents.
 *
 * This was a table of pre-built `rgba(...)` strings assigned to `fillStyle`
 * per particle. With one fill per bucket, opacity is a plain number on
 * `globalAlpha` set 47 times a frame — no cache, no string, no colour re-parse.
 */
const alphaOf = (bucket: number) => (bucket + 0.5) / ALPHA_SCALE;

/** `--primary` is authored as a hex token; the canvas needs its channels. */
function hexToRgb(hex: string): string {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const n = Number.parseInt(full, 16);
  if (!Number.isFinite(n) || full.length !== 6) return "59, 47, 217";
  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`;
}
