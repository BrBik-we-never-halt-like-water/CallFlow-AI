'use client';

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { cn } from '@/lib/cn';
import type { LampState } from '@/lib/lamp';

export interface DonutSegment {
  label: string;
  value: number;
  state: LampState;
}

const FILL: Record<LampState, string> = {
  off: 'var(--lamp-off)',
  ice: 'var(--lamp-ice)',
  brass: 'var(--lamp-brass)',
  jade: 'var(--lamp-jade)',
  flare: 'var(--lamp-flare)',
};

/**
 * The one chart on this page allowed to use the lamp colours as fill - a
 * disposition breakdown genuinely *is* call-state meaning, not decoration.
 *
 * Colour is never the only carrier: every segment is named and counted in the
 * legend beside it, matching the rule `LampBadge` already follows everywhere else.
 * Built on Recharts, but the five colours still come only from the lamp tokens -
 * nothing here reaches for a library default palette.
 */
export function DonutChart({
  segments,
  className,
}: {
  segments: DonutSegment[];
  className?: string;
}) {
  const total = segments.reduce((s, seg) => s + seg.value, 0);
  const present = segments.filter((seg) => seg.value > 0);
  const label =
    total === 0
      ? 'No settled calls yet'
      : present.map((s) => `${s.value} ${s.label}`).join(', ');

  return (
    <div className={cn('flex items-center gap-4', className)}>
      <div className="size-24 shrink-0" role="img" aria-label={label}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            {total === 0 ? (
              <Pie
                data={[{ label: 'empty', value: 1 }]}
                dataKey="value"
                innerRadius="72%"
                outerRadius="92%"
                stroke="none"
                isAnimationActive={false}
              >
                <Cell fill="var(--rule)" />
              </Pie>
            ) : (
              <Pie
                data={present}
                dataKey="value"
                nameKey="label"
                innerRadius="72%"
                outerRadius="92%"
                startAngle={90}
                endAngle={-270}
                stroke="var(--surface-raised)"
                strokeWidth={1}
                animationDuration={300}
              >
                {present.map((seg) => (
                  <Cell key={seg.label} fill={FILL[seg.state]} />
                ))}
              </Pie>
            )}
            {total > 0 ? (
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const seg = payload[0]?.payload as DonutSegment | undefined;
                  if (!seg) return null;
                  return (
                    <div className="rounded-sm border border-rule-strong bg-surface-raised px-2.5 py-1.5 shadow-sm">
                      <p className="font-mono text-label text-text-mute">
                        {seg.label}
                      </p>
                      <p className="font-mono text-data tabular-nums text-text">
                        {seg.value}
                      </p>
                    </div>
                  );
                }}
              />
            ) : null}
          </PieChart>
        </ResponsiveContainer>
      </div>

      <ul className="flex min-w-0 flex-1 flex-col gap-1.5">
        {segments.map((seg) => (
          <li key={seg.label} className="flex items-center gap-2 text-small">
            <span
              aria-hidden
              className="size-2 shrink-0 rounded-full"
              style={{ backgroundColor: FILL[seg.state] }}
            />
            <span className="min-w-0 flex-1 truncate text-text-dim">
              {seg.label}
            </span>
            <span className="font-mono text-data tabular-nums text-text">
              {seg.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
