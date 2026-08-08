"use client";

import { useMemo } from "react";
import { cn } from "@/lib/cn";

/**
 * A waveform actually derived from the line being spoken.
 *
 * Every bar is one character of the sentence, and its height comes from what
 * that character sounds like: open vowels carry the most energy, voiced
 * consonants less, unvoiced consonants least, and spaces and punctuation are
 * near silence. So the gaps in the waveform fall on the gaps between words, and
 * the loud parts fall on the syllables — which is why this reads as speech
 * rather than as the row of identical ticks it replaces.
 *
 * It is a model of speech, not a recording of one. Nobody has measured this
 * sentence; the shape is inferred from its letters. That is honest for a
 * scripted hero demo, and it is the reason the bars carry a small deterministic
 * variation rather than pretending to a precision they do not have.
 */

/** Rough articulatory energy per character, 0 (silence) to 1 (open vowel). */
function energyOf(ch: string): number {
  const c = ch.toLowerCase();
  if (c === " ") return 0.04;
  if (",.?!;:—".includes(c)) return 0.02;
  if ("aeo".includes(c)) return 1;
  if ("iu".includes(c)) return 0.82;
  if ("y".includes(c)) return 0.7;
  if ("mnlrwv".includes(c)) return 0.6;
  if ("bdgjz".includes(c)) return 0.5;
  if ("ptkcqx".includes(c)) return 0.34;
  if ("fsh".includes(c)) return 0.28;
  return 0.45;
}

export function SpeechWave({
  text,
  progress,
  speaking = false,
  className,
}: {
  /** The full line. Bar count follows its length. */
  text: string;
  /** 0–1 through the line; drives the playhead. */
  progress: number;
  speaking?: boolean;
  className?: string;
}) {
  const bars = useMemo(
    () =>
      Array.from(text, (ch, i) => {
        // A small deterministic wobble so consecutive identical letters do not
        // draw as a flat block, without inventing detail that isn't there.
        const jitter = ((text.charCodeAt(i) * (i + 7)) % 24) / 100;
        return Math.max(0.06, Math.min(1, energyOf(ch) * (0.82 + jitter)));
      }),
    [text],
  );

  return (
    <div aria-hidden className={cn("flex h-9 items-center gap-px", className)}>
      {bars.map((amp, i) => {
        const at = i / bars.length;
        const head = speaking && Math.abs(at - progress) < 1.6 / bars.length;
        const said = at < progress;
        return (
          <i
            key={i}
            className={cn(
              "min-h-px flex-1 rounded-[1px] transition-[background-color] duration-100",
              head ? "bg-lamp-brass" : said ? "bg-text-dim" : "bg-rule",
            )}
            style={{ height: `${(amp * (head ? 108 : said ? 92 : 46)).toFixed(1)}%` }}
          />
        );
      })}
    </div>
  );
}
