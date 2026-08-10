"use client";

import { useId, useMemo } from "react";
import { cn } from "@/lib/cn";

/**
 * A smooth waveform envelope, derived from the line being spoken.
 *
 * The data is still the sentence: every character contributes energy according
 * to what it sounds like — open vowels most, voiced consonants less, unvoiced
 * least, spaces and punctuation near silence. So the envelope narrows between
 * words and swells on syllables.
 *
 * Drawn as one continuous mirrored shape rather than a row of bars. Bars are
 * inherently steppy at this size and read as a barcode; a filled envelope reads
 * as sound. The curve is smoothed twice — once by averaging neighbouring
 * characters, then again by fitting a Catmull-Rom spline through the result —
 * so no single letter can put a spike in it.
 *
 * The spoken part is revealed by a clip rectangle that grows with progress,
 * which keeps a single shape on screen: nothing is drawn twice and the boundary
 * between said and unsaid stays exactly on the playhead.
 */

/** Rough articulatory energy per character, 0 (silence) to 1 (open vowel). */
function energyOf(ch: string): number {
  const c = ch.toLowerCase();
  if (c === " ") return 0.05;
  if (",.?!;:—".includes(c)) return 0.03;
  if ("aeo".includes(c)) return 1;
  if ("iu".includes(c)) return 0.82;
  if (c === "y") return 0.7;
  if ("mnlrwv".includes(c)) return 0.6;
  if ("bdgjz".includes(c)) return 0.5;
  if ("ptkcqx".includes(c)) return 0.34;
  if ("fsh".includes(c)) return 0.28;
  return 0.45;
}

const W = 1000;
const H = 100;
const MID = H / 2;

/** Catmull-Rom through the points, emitted as cubic beziers. */
function smoothPath(pts: { x: number; y: number }[]): string {
  if (pts.length < 2) return "";
  let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${c1x.toFixed(2)} ${c1y.toFixed(2)}, ${c2x.toFixed(2)} ${c2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }
  return d;
}

export function SpeechWave({
  text,
  progress,
  speaking = false,
  className,
}: {
  text: string;
  /** 0–1 through the line. */
  progress: number;
  speaking?: boolean;
  className?: string;
}) {
  // Unique per instance. The hero renders this twice — once live, once inside
  // an invisible copy that reserves the card height — and a shared clipPath id
  // makes the live shape reference the hidden one, which clips it away.
  const id = useId();

  const path = useMemo(() => {
    const raw = Array.from(text, energyOf);

    // Average each character with its neighbours: one loud letter in a quiet
    // word should lift the envelope, not spike it.
    const smoothed = raw.map((_, i) => {
      const a = raw[i - 1] ?? raw[i];
      const b = raw[i];
      const c = raw[i + 1] ?? raw[i];
      return (a + b * 2 + c) / 4;
    });

    // A gentle overall swell, so the line does not start and end at full height.
    const top = smoothed.map((amp, i) => {
      const u = i / Math.max(1, smoothed.length - 1);
      const env = 0.55 + Math.sin(u * Math.PI) * 0.45;
      return { x: u * W, y: MID - amp * env * (MID - 6) };
    });
    const bottom = [...top].reverse().map((p) => ({ x: p.x, y: MID + (MID - p.y) }));

    return `${smoothPath(top)} L ${W} ${MID} ${smoothPath(bottom).replace(/^M[^C]*/, "")} Z`;
  }, [text]);

  const pct = Math.max(0, Math.min(1, progress));

  return (
    <svg
      aria-hidden
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={cn("block h-10 w-full overflow-visible", className)}
    >
      <defs>
        <clipPath id={id}>
          {/* Grows with the playhead; the spoken fill is the same shape seen
              through this window. */}
          <rect x="0" y="0" width={W * pct} height={H} />
        </clipPath>
      </defs>

      {/* Colours go through `style`, not the `fill` attribute: a presentation
          attribute does not resolve var(), so fill="var(--x)" silently renders
          as black or nothing depending on the browser. */}

      {/* Unspoken: the whole envelope, quiet. */}
      <path d={path} style={{ fill: "var(--rule)" }} />

      {/* Spoken: the same shape, revealed. */}
      <path d={path} style={{ fill: "var(--text-dim)" }} clipPath={`url(#${id})`} />

      {speaking ? (
        <line
          x1={W * pct}
          x2={W * pct}
          y1="4"
          y2={H - 4}
          style={{ stroke: "var(--lamp-brass)" }}
          strokeWidth="3"
          strokeLinecap="round"
        />
      ) : null}
    </svg>
  );
}
