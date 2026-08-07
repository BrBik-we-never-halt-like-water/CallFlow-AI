import { cn } from "@/lib/cn";

export interface AreaChartPoint {
  label: string;
  value: number;
}

/**
 * A labeled trend line — the bigger, axis-bearing sibling of `Sparkline`.
 *
 * Monochrome, deliberately: this is volume over time, not call-disposition
 * state, so it gets none of the five lamp colours — those are reserved for
 * meaning `Sparkline` and this chart don't carry.
 */
export function AreaChart({
  data,
  className,
  formatValue = (v) => String(v),
}: {
  data: AreaChartPoint[];
  className?: string;
  formatValue?: (value: number) => string;
}) {
  const w = 320;
  const h = 96;
  const padTop = 8;
  const padBottom = 20;
  const plotH = h - padTop - padBottom;

  const max = Math.max(1, ...data.map((d) => d.value));
  const step = data.length > 1 ? w / (data.length - 1) : 0;

  const points = data.map((d, i) => ({
    x: i * step,
    y: padTop + plotH - (d.value / max) * plotH,
    ...d,
  }));

  const line = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const area = `0,${h - padBottom} ${line} ${w},${h - padBottom}`;

  const summary = `${data.reduce((s, d) => s + d.value, 0)} calls over the last ${data.length} days`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className={cn("h-24 w-full", className)}
      role="img"
      aria-label={summary}
    >
      <line
        x1="0"
        y1={h - padBottom}
        x2={w}
        y2={h - padBottom}
        stroke="var(--rule)"
        strokeWidth="1"
        vectorEffect="non-scaling-stroke"
      />
      <polygon points={area} fill="color-mix(in oklab, var(--text) 8%, transparent)" />
      <polyline
        points={line}
        fill="none"
        stroke="var(--rule-strong)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      {points.map((p) => (
        <g key={p.label}>
          <circle cx={p.x} cy={p.y} r="2" fill="var(--surface-raised)" stroke="var(--rule-strong)" strokeWidth="1.25">
            <title>{`${p.label}: ${formatValue(p.value)}`}</title>
          </circle>
          <text
            x={p.x}
            y={h - 4}
            textAnchor={p.x < 8 ? "start" : p.x > w - 8 ? "end" : "middle"}
            className="font-mono"
            style={{ fontSize: "8px", fill: "var(--text-mute)" }}
          >
            {p.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
