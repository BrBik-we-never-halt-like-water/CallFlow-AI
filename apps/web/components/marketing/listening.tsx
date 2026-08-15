"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { useCanvasAnimation } from "@/lib/hooks/use-canvas-animation";
import { usePrefersReducedMotion } from "@/lib/hooks/use-external-store";

/**
 * The section where the product is simply running.
 *
 * The field never settles — calls keep arriving, so the signal keeps moving.
 * Results crystallise out of it one at a time: the newest steps to the front and
 * the ones before it fall back in depth rather than scrolling away, so the stack
 * reads as a queue being worked rather than a list being rendered.
 *
 * Two separate mechanisms on purpose. The waveform is canvas, because a few
 * hundred drifting particles are cheap there and expensive as DOM. The cards are
 * DOM, because they carry real text that has to stay selectable, translatable
 * and readable by a screen reader.
 */

interface Result {
  who: string;
  line: string;
  fields: { k: string; v: string }[];
  tone: "jade" | "flare";
}

/**
 * The queue behind the stack.
 *
 * The card stack shows results *arriving*; this shows the run they arrive from,
 * so the section reads as a system under load rather than one card at a time.
 * Numbers are masked, the same way every surface in the product masks them
 * (`lib/format/phone.ts`) — a marketing page is not an exemption.
 */
const QUEUE: { name: string; phone: string; state: string; lamp: string }[] = [
  { name: "Aditi Sharma", phone: "+91*******210", state: "in conversation", lamp: "bg-lamp-brass" },
  { name: "Rahul Verma", phone: "+91*******884", state: "dialling", lamp: "bg-lamp-brass" },
  { name: "Meera Joshi", phone: "+91*******051", state: "closed itself", lamp: "bg-lamp-jade" },
  { name: "Karan Shah", phone: "+91*******377", state: "needs a person", lamp: "bg-lamp-flare" },
  { name: "Nisha Rao", phone: "+91*******629", state: "queued", lamp: "bg-lamp-off" },
  { name: "Vikram Desai", phone: "+91*******145", state: "queued", lamp: "bg-lamp-off" },
];

const RESULTS: Result[] = [
  {
    who: "Admissions follow-up",
    line: "“Yes — I've accepted the offer, I just need the fee deadline.”",
    fields: [
      { k: "outcome", v: "enrolled" },
      { k: "sentiment", v: "positive" },
      { k: "needs", v: "fee deadline" },
    ],
    tone: "jade",
  },
  {
    who: "Appointment recovery",
    line: "“Tomorrow at three works. Put me down for that.”",
    fields: [
      { k: "outcome", v: "rebooked" },
      { k: "slot", v: "Tomorrow 15:00" },
      { k: "sentiment", v: "positive" },
    ],
    tone: "jade",
  },
  {
    who: "Lead qualification",
    line: "“I'd rather talk to an actual person about the pricing.”",
    fields: [
      { k: "outcome", v: "asked for a person" },
      { k: "qualified", v: "true" },
      { k: "escalated", v: "immediately" },
    ],
    tone: "flare",
  },
  {
    who: "Recruiting screening",
    line: "“I'm on a month's notice and I can do hybrid.”",
    fields: [
      { k: "notice_period", v: "30 days" },
      { k: "work_mode", v: "hybrid" },
      { k: "sentiment", v: "positive" },
    ],
    tone: "jade",
  },
];

export function Listening({ className }: { className?: string }) {
  const reduced = usePrefersReducedMotion();
  const [i, setI] = useState(0);

  useEffect(() => {
    if (reduced) return;
    const id = window.setInterval(() => setI((n) => n + 1), 3600);
    return () => clearInterval(id);
  }, [reduced]);

  const canvasRef = useCanvasAnimation(({ ctx, w, h, t, reduced: still }) => {
    ctx.clearRect(0, 0, w, h);
    const rows = 3;
    const per = Math.round(Math.min(240, Math.max(90, w / 6)));
    const ink = getComputedStyle(document.documentElement)
      .getPropertyValue("--text")
      .trim();

    for (let r = 0; r < rows; r++) {
      const baseY = h * (0.3 + r * 0.2);
      const speed = 0.16 + r * 0.07;
      const amp = h * (0.06 + r * 0.018);
      for (let n = 0; n < per; n++) {
        const u = n / per;
        // Drift: the field never resolves, it just keeps travelling.
        const x = ((u + (still ? 0 : t * speed * 0.06)) % 1) * w;
        const env = Math.sin(u * Math.PI * 2 + r);
        const y =
          baseY +
          Math.sin(u * 26 + r * 2 + (still ? 0 : t * 0.9)) * amp * env +
          Math.sin(u * 61 - (still ? 0 : t * 0.5)) * amp * 0.3;
        const a = 0.05 + Math.abs(env) * 0.09;
        ctx.fillStyle = ink
          ? `color-mix(in oklab, ${ink} ${(a * 100).toFixed(1)}%, transparent)`
          : `rgba(14,17,20,${a})`;
        ctx.fillRect(x, y, 2, 2);
      }
    }
  });

  return (
    <div className={cn("relative", className)}>
      {/* The signal, always running, behind everything. Masked so it fades out
          rather than ending at a hard edge. */}
      <canvas
        ref={canvasRef}
        aria-hidden
        className="pointer-events-none absolute inset-0 h-full w-full [mask-image:radial-gradient(ellipse_78%_70%_at_50%_50%,#000_35%,transparent_82%)] [-webkit-mask-image:radial-gradient(ellipse_78%_70%_at_50%_50%,#000_35%,transparent_82%)]"
      />

      <div className="relative grid items-center gap-12 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <div className="flex flex-col gap-5">
          <h2 className="measure-display font-display text-h2 text-text">
            The line never goes quiet.
          </h2>
          <p className="measure text-body-l text-text-dim">
            Calls keep landing while you are reading this. Each one resolves into
            typed fields on its own, and only the ones that asked for a person
            ever reach your team.
          </p>
          <p
            className="flex items-center gap-2 text-small text-text-mute"
            aria-live="off"
          >
            <span className="relative flex size-2">
              {!reduced ? (
                <span className="absolute inline-flex size-2 animate-ping rounded-full bg-lamp-jade opacity-60" />
              ) : null}
              <span className="relative inline-flex size-2 rounded-full bg-lamp-jade" />
            </span>
            Live results, cycling
          </p>

          {/* The run underneath the results. Six rows is enough to read as a
              queue without becoming a table nobody scans. */}
          <ul className="mt-2 flex flex-col divide-y divide-rule border-y border-rule">
            {QUEUE.map((c) => (
              <li key={c.name} className="flex items-center gap-3 py-2.5">
                <span className={cn("size-2 shrink-0 rounded-full", c.lamp)} />
                <span className="min-w-0 flex-1 truncate text-small text-text">{c.name}</span>
                <span className="hidden font-mono text-data text-text-mute sm:block">
                  {c.phone}
                </span>
                <span className="w-32 shrink-0 text-right text-small text-text-dim">
                  {c.state}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {/* The stack. Newest in front; the two behind it step back in depth
            rather than leaving, so the section shows a queue being worked. */}
        {/* Scales with the viewport for the same reason the morph card does:
            this sits inside a one-screen-tall section, so a flat rem height is
            a promise the short viewports can't keep. */}
        <div className="relative h-[clamp(15rem,32vh,22rem)]">
          {RESULTS.map((r, idx) => {
            // Distance behind the front card, wrapped so the stack is a loop.
            const depth = (idx - i + RESULTS.length * 100) % RESULTS.length;
            const hidden = depth > 2;
            return (
              <article
                key={r.who}
                aria-hidden={depth !== 0}
                className={cn(
                  "card-raised absolute inset-x-0 top-0 flex flex-col gap-4 p-6",
                  "transition-[transform,opacity] duration-700 ease-(--ease-out)",
                  hidden && "pointer-events-none",
                )}
                style={{
                  // Enough separation that the stack reads as a queue at a
                  // glance. At a smaller offset the cards behind are only
                  // visible as a hairline and the depth is lost.
                  transform: `translateY(${depth * 26}px) scale(${1 - depth * 0.07})`,
                  opacity: hidden ? 0 : 1 - depth * 0.42,
                  zIndex: RESULTS.length - depth,
                }}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-small font-medium text-text-dim">{r.who}</span>
                  <span
                    className={cn(
                      "size-2 rounded-full",
                      r.tone === "jade" ? "bg-lamp-jade" : "bg-lamp-flare",
                    )}
                  />
                </div>

                <p className="text-body font-medium text-text">{r.line}</p>

                <dl className="flex flex-col">
                  {r.fields.map((f) => (
                    <div
                      key={f.k}
                      className="flex items-center justify-between gap-3 border-b border-rule py-2 last:border-0"
                    >
                      <dt className="font-mono text-data text-text-mute">{f.k}</dt>
                      <dd className="text-small font-medium text-text">{f.v}</dd>
                    </div>
                  ))}
                </dl>
              </article>
            );
          })}
        </div>
      </div>

      {/* The section is a full screen, and the argument above fills about half
          of it. Rather than pad the gap, it carries the numbers that make the
          claim concrete — the same figures the dashboard reports. */}
      <dl className="relative mt-(--deck-gap) grid grid-cols-2 gap-x-8 gap-y-6 border-t border-rule pt-(--deck-gap) sm:grid-cols-4">
        {[
          { n: "18,402", l: "calls closed themselves last month" },
          { n: "6.1%", l: "reached a person" },
          { n: "01:12", l: "median call length" },
          { n: "0", l: "dialled outside your guards" },
        ].map((s) => (
          <div key={s.l} className="flex flex-col gap-1">
            <dt className="font-mono text-h3 tabular-nums text-text">{s.n}</dt>
            <dd className="measure text-small text-text-dim">{s.l}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
