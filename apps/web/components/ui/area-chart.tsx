"use client";

import { Bar, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { cn } from "@/lib/cn";

export interface AreaChartPoint {
  label: string;
  value: number;
}

interface DotRenderProps {
  cx?: number;
  cy?: number;
  index?: number;
  payload?: AreaChartPoint;
}

/**
 * Every point but the most recent is a small `--accent` dot. The most recent
 * point is the one value worth calling out without a hover — solid `--text`,
 * with its value floating above it in a permanent pill, the same way a
 * reader's eye is meant to land on "today" first.
 */
function makeDotRenderer(lastIndex: number, formatValue: (value: number) => string) {
  return function renderDot(props: DotRenderProps) {
    const { cx, cy, index, payload } = props;
    if (cx == null || cy == null || index == null || !payload) return <g />;

    if (index !== lastIndex) {
      return (
        <circle
          key={`dot-${index}`}
          cx={cx}
          cy={cy}
          r={3.5}
          fill="var(--accent)"
          stroke="var(--surface-raised)"
          strokeWidth={1.5}
        />
      );
    }

    const text = formatValue(payload.value);
    const pillWidth = Math.max(32, text.length * 6.5 + 18);
    return (
      <g key={`dot-${index}`}>
        <rect
          x={cx - pillWidth / 2}
          y={cy - 30}
          width={pillWidth}
          height={20}
          rx={10}
          fill="var(--surface-inverse)"
        />
        <text
          x={cx}
          y={cy - 16.5}
          textAnchor="middle"
          fontFamily="var(--font-mono)"
          fontSize={10}
          fill="var(--text-inverse)"
        >
          {text}
        </text>
        <circle cx={cx} cy={cy} r={4.5} fill="var(--text)" stroke="var(--surface-raised)" strokeWidth={1.5} />
      </g>
    );
  };
}

/**
 * A labeled lollipop chart — the bigger, axis-bearing sibling of `Sparkline`.
 *
 * Individual vertical stems from the baseline to each value, not a connected
 * line — each day's volume is its own reading, not a continuous quantity
 * being tracked between days. The stems and fill stay monochrome; this is
 * volume over time, not call-disposition state, so it gets none of the five
 * lamp colours. The point markers use `--accent` instead: a decorative-only
 * colour (globals.css), never a state colour, so marking "here's a day's
 * value" with it can't be mistaken for a lamp. Built on Recharts — a `Bar`
 * (thin enough to read as a stem) for the baseline-to-value line, a `Line`
 * with its own stroke suppressed purely to carry the per-point `dot` renderer
 * — rather than hand-rolled SVG, so animation, resize, and the tooltip come
 * from a maintained library instead of this file re-deriving them.
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
  const summary = `${data.reduce((s, d) => s + d.value, 0)} calls over the last ${data.length} days`;
  const renderDot = makeDotRenderer(data.length - 1, formatValue);

  return (
    <div
      className={cn("h-28 w-full", className)}
      role="img"
      aria-label={summary}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 26, right: 4, bottom: 0, left: 4 }}>
          <XAxis
            dataKey="label"
            axisLine={{ stroke: "var(--rule)" }}
            tickLine={false}
            tick={{ fontFamily: "var(--font-mono)", fontSize: 8, fill: "var(--text-mute)" }}
            interval={0}
          />
          <Tooltip
            cursor={{ stroke: "var(--rule-strong)", strokeWidth: 1 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const point = payload[0]?.payload as AreaChartPoint | undefined;
              if (!point) return null;
              return (
                <div className="rounded-sm border border-rule-strong bg-surface-raised px-2.5 py-1.5 shadow-sm">
                  <p className="font-mono text-label text-text-mute">{point.label}</p>
                  <p className="font-mono text-data tabular-nums text-text">
                    {formatValue(point.value)}
                  </p>
                </div>
              );
            }}
          />
          <Bar dataKey="value" barSize={2} fill="var(--rule-strong)" isAnimationActive={false} />
          <Line
            dataKey="value"
            stroke="transparent"
            dot={renderDot}
            activeDot={{ r: 4.5, fill: "var(--accent)", stroke: "var(--surface-raised)", strokeWidth: 2 }}
            isAnimationActive
            animationDuration={300}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
