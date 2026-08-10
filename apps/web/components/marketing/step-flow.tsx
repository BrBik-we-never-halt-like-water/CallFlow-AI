"use client";

import { useEffect, useRef } from "react";

/**
 * The signal rail.
 *
 * A straight line at rest. A small wave-burst travels along it left → right; as
 * it arrives at each station the burst flattens and the dot blips green, then a
 * fresh burst carries on to the next station — a signal pulsing down a wire. It
 * lands on the last (far-right) station, rests straight for a beat, then a new
 * burst sweeps in from the left again.
 *
 * Driven by `activeIndex` (shared with the numbers below, so they light in
 * step), animated on a canvas render loop. Desktop only; steps stack on mobile,
 * and under prefers-reduced-motion it renders a plain static line.
 */

const TRAVEL_MS = 900; // burst travel time between two stations
const SETTLE_MS = 300; // how fast the burst flattens once it arrives
const SIGMA = 48; // burst half-width, px
const WAVELENGTH = 46; // px — longer reads smoother
const AMP = 6; // px
const OMEGA = 0.007; // internal oscillation, rad/ms — slower undulation
const GAP = 24; // matches the steps grid `lg:gap-6` (1.5rem)

export function StepFlow({
  activeIndex,
  count,
  reduced,
}: {
  activeIndex: number;
  count: number;
  reduced: boolean;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const anim = useRef({ active: -1, prev: -1, start: 0, arrived: 0, pc: -SIGMA });

  // Record each hand-off so the render loop can carry the burst from the old
  // station to the new one. Positions are computed in the loop from the live
  // width, so a resize mid-travel stays correct.
  useEffect(() => {
    const a = anim.current;
    a.prev = a.active;
    a.active = activeIndex;
    a.start = performance.now();
    a.arrived = 0;
  }, [activeIndex]);

  useEffect(() => {
    if (reduced) return;
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resolve = (name: string) => {
      const probe = document.createElement("span");
      probe.style.cssText = `color:var(${name});display:none`;
      wrap.appendChild(probe);
      const c = getComputedStyle(probe).color;
      wrap.removeChild(probe);
      return c;
    };
    const colRule = resolve("--rule-strong");
    const colJade = resolve("--lamp-jade");
    const colSurface = resolve("--surface");

    let raf = 0;
    let W = 0;
    let H = 0;
    const resize = () => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      W = wrap.clientWidth;
      H = wrap.clientHeight;
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      canvas.style.width = `${W}px`;
      canvas.style.height = `${H}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);

    // A node centred over each card — a timeline above the row. Symmetric:
    // first and last sit an equal inset from the edges. Mirrors the steps grid
    // (4 equal columns with GAP between).
    const dotX = (i: number) => {
      if (count <= 1) return W / 2;
      const colW = (W - (count - 1) * GAP) / count;
      return i * (colW + GAP) + colW / 2;
    };

    const draw = (t: number) => {
      const a = anim.current;
      const mid = H / 2;
      const resting = a.active < 0 || a.active >= count;

      let amp = 0;
      if (!resting) {
        // Sweep in from off-screen left on a fresh start / loop; otherwise carry
        // the burst forward from the previous station.
        const carry = a.prev >= 0 && a.prev < count && a.active > a.prev;
        const fromX = carry ? dotX(a.prev) : -SIGMA * 1.5;
        const toX = dotX(a.active);
        const u = Math.min(1, (t - a.start) / TRAVEL_MS);
        a.pc = fromX + (toX - fromX) * (1 - Math.pow(1 - u, 3));
        if (u >= 1 && !a.arrived) a.arrived = t;
        amp = a.arrived ? AMP * Math.max(0, 1 - (t - a.arrived) / SETTLE_MS) : AMP;
      }

      ctx.clearRect(0, 0, W, H);

      // The wire: straight everywhere, wavy only under the travelling burst.
      ctx.beginPath();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = colRule;
      ctx.globalAlpha = 0.6;
      for (let x = 0; x <= W; x += 2) {
        const d = x - a.pc;
        const env = amp ? Math.exp(-(d * d) / (2 * SIGMA * SIGMA)) : 0;
        const y = mid + amp * env * Math.sin((d / WAVELENGTH) * Math.PI * 2 + t * OMEGA);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;

      // Stations. The one the burst has reached blips green and holds until the
      // burst moves on; a surface halo keeps each dot clear of the wire.
      for (let i = 0; i < count; i++) {
        const x = dotX(i);
        ctx.beginPath();
        ctx.fillStyle = colSurface;
        ctx.arc(x, mid, 6, 0, Math.PI * 2);
        ctx.fill();

        const lit = i === a.active && a.arrived > 0;
        let r = 4;
        if (lit) {
          const since = t - a.arrived;
          const pop = since < 320 ? 1 + 0.5 * Math.sin(Math.min(1, since / 320) * Math.PI) : 1;
          r = 4.5 * pop;
          ctx.shadowColor = colJade;
          ctx.shadowBlur = 12;
          ctx.fillStyle = colJade;
        } else {
          ctx.shadowBlur = 0;
          ctx.fillStyle = colRule;
        }
        ctx.beginPath();
        ctx.arc(x, mid, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [reduced, count]);

  if (reduced) {
    return (
      <div aria-hidden className="relative mb-6 hidden h-6 w-full grid-cols-4 gap-6 lg:grid">
        <span
          className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2"
          style={{ background: "var(--rule-strong)" }}
        />
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="relative flex justify-center">
            <span
              className="absolute top-1/2 size-2 -translate-y-1/2 rounded-full ring-4 ring-surface"
              style={{ background: "var(--rule-strong)" }}
            />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div ref={wrapRef} aria-hidden className="relative mb-6 hidden h-6 w-full lg:block">
      <canvas
        ref={canvasRef}
        className="h-full w-full [mask-image:linear-gradient(to_right,transparent,#000_5%,#000_95%,transparent)] [-webkit-mask-image:linear-gradient(to_right,transparent,#000_5%,#000_95%,transparent)]"
      />
    </div>
  );
}
