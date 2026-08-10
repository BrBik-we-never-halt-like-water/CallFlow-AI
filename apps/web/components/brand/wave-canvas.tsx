'use client';

import { useEffect, useRef } from 'react';
import { cn } from '@/lib/cn';

/**
 * A live voice waveform on a canvas - the bold, structural counterpart to the
 * CSS spine. Used as card mastheads, call-row voices, and section bands.
 *
 * All instances share ONE requestAnimationFrame loop (registered below), so a
 * page full of waveforms costs a single frame callback. The loop only runs while
 * at least one canvas is mounted and the tab is visible, and it never starts
 * under prefers-reduced-motion (a single resting frame is drawn instead).
 */

type Draw = (t: number) => void;

const callbacks = new Set<Draw>();
let rafId: number | null = null;
let startTs: number | null = null;

function loop(ts: number) {
  if (startTs === null) startTs = ts;
  const t = (ts - startTs) / 1000;
  callbacks.forEach((cb) => cb(t));
  rafId = requestAnimationFrame(loop);
}

function register(cb: Draw) {
  callbacks.add(cb);
  if (rafId === null) rafId = requestAnimationFrame(loop);
}

function unregister(cb: Draw) {
  callbacks.delete(cb);
  if (callbacks.size === 0 && rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
    startTs = null;
  }
}

/** Layered travelling sine - loudest in the centre, tapering to the ends. */
function amp(x: number, t: number, seed: number) {
  const env = Math.sin(Math.PI * x);
  const w =
    Math.sin(x * 20 - t * 2.1 + seed) * 0.55 +
    Math.sin(x * 12 + t * 1.3 + seed) * 0.32 +
    Math.sin(x * 34 - t * 3.0) * 0.18;
  return env * env * w;
}

export function WaveCanvas({
  tone = 'ink',
  seed = 0,
  /** Bar pitch in CSS px; smaller = denser. */
  pitch = 8,
  className,
}: {
  tone?: 'ink' | 'inverse';
  seed?: number;
  pitch?: number;
  className?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const reduce =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    const color =
      tone === 'inverse'
        ? '#ffffff'
        : getComputedStyle(document.documentElement)
            .getPropertyValue('--text')
            .trim() || '#0b0f12';

    let dpr = 1;
    const size = () => {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.max(1, canvas.clientWidth * dpr);
      canvas.height = Math.max(1, canvas.clientHeight * dpr);
    };
    size();
    const ro = new ResizeObserver(size);
    ro.observe(canvas);

    const draw = (t: number) => {
      const W = canvas.width;
      const H = canvas.height;
      const cy = H / 2;
      const n = Math.max(16, Math.floor(canvas.clientWidth / pitch));
      const gap = W / n;
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = color;
      for (let i = 0; i < n; i++) {
        const x = i / (n - 1);
        const a = Math.abs(amp(x, t, seed));
        const h = a * (H * 0.42) + H * 0.05;
        const bw = Math.max(1.6 * dpr, gap * 0.5);
        const px = i * gap + gap / 2;
        ctx.globalAlpha = 0.22 + a * 0.7;
        if (ctx.roundRect) {
          ctx.beginPath();
          ctx.roundRect(px - bw / 2, cy - h, bw, h * 2, bw / 2);
          ctx.fill();
        } else {
          ctx.fillRect(px - bw / 2, cy - h, bw, h * 2);
        }
      }
      ctx.globalAlpha = 1;
    };

    // A resize can arrive before the first frame; draw once immediately so the
    // waveform is never blank, then either animate or rest.
    draw(seed);
    if (reduce) {
      return () => ro.disconnect();
    }
    register(draw);
    return () => {
      unregister(draw);
      ro.disconnect();
    };
  }, [tone, seed, pitch]);

  return (
    <canvas
      ref={ref}
      aria-hidden
      className={cn('block h-full w-full', className)}
    />
  );
}
