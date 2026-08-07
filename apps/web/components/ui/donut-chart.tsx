import { cn } from "@/lib/cn";
import type { LampState } from "@/lib/lamp";

export interface DonutSegment {
  label: string;
  value: number;
  state: LampState;
}

const STROKE: Record<LampState, string> = {
  off: "var(--lamp-off)",
  ice: "var(--lamp-ice)",
  brass: "var(--lamp-brass)",
  jade: "var(--lamp-jade)",
  flare: "var(--lamp-flare)",
};

/**
 * The one chart on this page allowed to use the lamp colours as fill — a
 * disposition breakdown genuinely *is* call-state meaning, not decoration.
 *
 * Colour is never the only carrier: every segment is named and counted in the
 * legend beside it, matching the rule `LampBadge` already follows everywhere else.
 */
export function DonutChart({
  segments,
  className,
}: {
  segments: DonutSegment[];
  className?: string;
}) {
  const total = segments.reduce((s, seg) => s + seg.value, 0);
  const r = 15.9155; // circumference works out to 100, so percentages are exact
  const circumference = 2 * Math.PI * r;

  let cumulative = 0;
  const arcs = segments
    .filter((seg) => seg.value > 0)
    .map((seg) => {
      const length = total > 0 ? (seg.value / total) * circumference : 0;
      const offset = cumulative;
      cumulative += length;
      return { ...seg, length, offset };
    });

  return (
    <div className={cn("flex items-center gap-4", className)}>
      <svg
        viewBox="0 0 40 40"
        className="size-24 shrink-0 -rotate-90"
        role="img"
        aria-label={
          total === 0
            ? "No settled calls yet"
            : segments
                .filter((s) => s.value > 0)
                .map((s) => `${s.value} ${s.label}`)
                .join(", ")
        }
      >
        {total === 0 ? (
          <circle cx="20" cy="20" r={r} fill="none" stroke="var(--rule)" strokeWidth="6" />
        ) : (
          arcs.map((arc) => (
            <circle
              key={arc.label}
              cx="20"
              cy="20"
              r={r}
              fill="none"
              stroke={STROKE[arc.state]}
              strokeWidth="6"
              strokeDasharray={`${arc.length} ${circumference - arc.length}`}
              strokeDashoffset={-arc.offset}
            />
          ))
        )}
      </svg>

      <ul className="flex min-w-0 flex-1 flex-col gap-1.5">
        {segments.map((seg) => (
          <li key={seg.label} className="flex items-center gap-2 text-small">
            <span
              aria-hidden
              className="size-2 shrink-0 rounded-full"
              style={{ backgroundColor: STROKE[seg.state] }}
            />
            <span className="min-w-0 flex-1 truncate text-text-dim">{seg.label}</span>
            <span className="font-mono text-data tabular-nums text-text">{seg.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
