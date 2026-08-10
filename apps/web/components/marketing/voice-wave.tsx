import { useMemo } from 'react';
import { cn } from '@/lib/cn';

const BARS = 56;

/**
 * A speech envelope derived from the text itself, so the waveform *is* the line
 * being spoken: vowels peak, spaces and punctuation dip into pauses, consonants
 * sit in the middle. Deterministic - the same line always draws the same wave,
 * and changing the line reshapes it. No randomness, so it is safe to run in
 * render.
 */
function envelope(text: string): number[] {
  const s = text.replace(/[“”"]/g, '');
  const L = Math.max(s.length, 1);
  const out: number[] = [];
  for (let i = 0; i < BARS; i++) {
    const idx = Math.floor((i / BARS) * L);
    const c = s.charAt(idx) || ' ';
    const code = s.charCodeAt(idx) || 32;
    let h: number;
    if (/\s/.test(c)) h = 0.09;
    else if (/[.,?!;:]/.test(c)) h = 0.12;
    else if (/[aeiouAEIOU]/.test(c)) h = 0.62 + (code % 6) / 12;
    else h = 0.27 + (code % 9) / 20;
    const next = s.charCodeAt(idx + 1) || code;
    h *= 0.82 + (next % 10) / 32;
    out.push(Math.max(0.06, Math.min(1, h)));
  }
  return out;
}

/**
 * The hero's signature: a voice waveform for the line the caller hears.
 *
 * The bars are generated from the words themselves, and a playhead rides the
 * exact typing progress of the line above - so as the sentence types out, the
 * wave "speaks" left to right, the leading edge lifts, and the settled bars
 * hold the shape of what was said. When nothing is being spoken it rests at the
 * full envelope, dimmed.
 *
 * Decorative, so `aria-hidden`: the spoken line beside it carries the meaning.
 * Monochrome by design - colour on this page is reserved for call state.
 */
export function VoiceWave({
  text,
  progress,
  speaking,
  className,
}: {
  /** The full line being spoken - the wave's shape is derived from it. */
  text: string;
  /** 0–1 typing progress, so the wave stays in lockstep with the text. */
  progress: number;
  /** Whether the line is actively being spoken right now. */
  speaking: boolean;
  className?: string;
}) {
  const env = useMemo(() => envelope(text), [text]);

  return (
    <div
      aria-hidden
      className={cn(
        'flex h-12 w-full items-center gap-[2px] overflow-hidden',
        className,
      )}
    >
      {env.map((base, i) => {
        const pos = i / (BARS - 1);
        const spokenBar = !speaking || pos <= progress;
        const near = speaking && Math.abs(pos - progress) < 0.045;

        const height = spokenBar
          ? near
            ? Math.min(1, base * 1.4)
            : base
          : base * 0.14;
        const opacity = speaking ? (spokenBar ? (near ? 1 : 0.85) : 0.16) : 0.5;

        return (
          <span
            key={i}
            className={cn(
              'min-w-0 flex-1 rounded-full bg-text transition-[height,opacity] duration-150 ease-(--ease-out)',
              near && 'wave-active',
            )}
            style={{
              height: `${Math.max(12, height * 100)}%`,
              opacity,
            }}
          />
        );
      })}
    </div>
  );
}
