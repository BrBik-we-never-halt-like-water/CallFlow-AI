import { cn } from "@/lib/cn";
import { Lamp } from "@/components/brand/lamp";
import type { LampState } from "@/lib/lamp";
import { Panel } from "./panel";

/**
 * A single figure: the value in the display face, the label in mono.
 *
 * The split is the point. Display face for the number a human reads, mono for
 * the label naming what the machine measured — the same distinction the rest of
 * the product draws between authored and produced text.
 */
export function Stat({
  label,
  value,
  /** Small print under the value — a delta, a denominator, a window. */
  detail,
  /** A lamp, only where the figure genuinely describes call state. */
  lamp,
  sparkline,
  className,
}: {
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  lamp?: LampState;
  sparkline?: React.ReactNode;
  className?: string;
}) {
  return (
    <Panel className={cn("flex flex-col gap-3 p-4", className)}>
      <div className="flex items-center gap-2">
        {lamp ? <Lamp state={lamp} size="sm" /> : null}
        <p className="eyebrow text-text-mute">{label}</p>
      </div>

      <p className="font-display text-[2rem] leading-none tabular-nums text-text">{value}</p>

      {detail ? <p className="font-mono text-data text-text-dim">{detail}</p> : null}
      {sparkline ? <div className="mt-auto pt-1">{sparkline}</div> : null}
    </Panel>
  );
}

/**
 * Seven-day sparkline. No axes, no legend, no gradient fill — a shape, not a
 * chart. Rendered as a hairline path in the rule colour so it reads as texture
 * beside the figure rather than competing with it.
 */
export function Sparkline({
  values,
  className,
  label,
}: {
  values: number[];
  className?: string;
  /** Screen readers get the trend as a sentence; the shape is decorative. */
  label?: string;
}) {
  if (values.length < 2) return null;

  const w = 100;
  const h = 24;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    // 1px inset top and bottom so the stroke never clips.
    const y = h - 1 - ((v - min) / span) * (h - 2);
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className={cn("h-6 w-full", className)}
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
    >
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke="var(--rule-strong)"
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
