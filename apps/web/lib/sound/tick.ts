'use client';

import { useStoredString } from '@/lib/hooks/use-external-store';

/**
 * The detent click a wheel picker makes as a value passes under the selection
 * band, synthesised rather than loaded - a 12ms blip is a handful of lines of
 * WebAudio and no network request, and an audio file for it would be a larger
 * download than the code that replaces it.
 */

const MUTE_KEY = 'callflow.tick-muted';

let context: AudioContext | null = null;

/**
 * Created on first use, never at import: constructing an AudioContext before a
 * user gesture leaves it `suspended` in every browser, and doing it at module
 * scope would also break server rendering.
 */
function audioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  if (context) return context;

  const Ctor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!Ctor) return null;

  try {
    context = new Ctor();
    return context;
  } catch {
    return null;
  }
}

function muted(): boolean {
  try {
    return localStorage.getItem(MUTE_KEY) === 'true';
  } catch {
    return false;
  }
}

/**
 * Build and unsuspend the context ahead of the first sound.
 *
 * A suspended context resumes asynchronously, so the *first* `playTick()` of a
 * session schedules its blip against a clock that has not started yet and
 * lands audibly late. Calling this from the gesture that is about to cause
 * ticks - pressing a preset - moves that cost off the sound itself.
 */
export function primeTick(): void {
  if (muted()) return;
  const ctx = audioContext();
  if (ctx && ctx.state === 'suspended') void ctx.resume();
}

export function playTick(): void {
  if (muted()) return;

  const ctx = audioContext();
  if (!ctx) return;
  // A scroll gesture is what triggers this, so resuming here is allowed.
  if (ctx.state === 'suspended') void ctx.resume();

  const now = ctx.currentTime;
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();

  oscillator.type = 'square';
  oscillator.frequency.value = 2_000;

  // A hard attack and a near-immediate exponential decay: the ear reads that
  // envelope as a mechanical click rather than a tone. Ramping to a tiny
  // non-zero value because exponentialRampToValueAtTime rejects exactly zero.
  gain.gain.setValueAtTime(0.06, now);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.012);

  oscillator.connect(gain).connect(ctx.destination);
  oscillator.start(now);
  oscillator.stop(now + 0.02);
}

export function useTickMuted(): [boolean, (next: boolean) => void] {
  const [raw, setRaw] = useStoredString(MUTE_KEY, 'false');
  return [raw === 'true', (next) => setRaw(next ? 'true' : 'false')];
}
