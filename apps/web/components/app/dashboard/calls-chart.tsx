'use client';

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from 'recharts';
import { Panel, PanelHeader, PillSelect } from './panel';
import type { Scope, ScopeOption } from './scope';
import { usePrefersReducedMotion } from '@/lib/hooks/use-external-store';

/** One month's calls. `placed` drives the bars, `completed` the line. */
export interface MonthPoint {
  month: string;
  placed: number;
  completed: number;
}

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/**
 * Calls per month: bars for volume, a line for completions.
 *
 * Two series rather than one because volume alone doesn't say whether the
 * calls worked - a tall bar with a low line is the shape worth noticing.
 *
 * Built on Recharts (already a dependency here - see
 * `components/ui/area-chart.tsx`) rather than the hand-rolled SVG this
 * replaces. That version drew a correct picture but had no transitions at
 * all: changing scope snapped the bars from one set of heights to another,
 * which reads as a glitch rather than as a change. Recharts interpolates
 * both series and brings its own hover handling, which is most of the reason
 * to use it here.
 */
export function CallsChart({
  data,
  scope,
  onScopeChange,
  scopeOptions,
  className,
}: {
  data: MonthPoint[] | null;
  scope: Scope;
  onScopeChange: (scope: Scope) => void;
  scopeOptions: ScopeOption[];
  className?: string;
}) {
  const reducedMotion = usePrefersReducedMotion();

  // An empty chart still draws its twelve months at zero rather than a
  // sentence in a blank box - the frame says what the panel will show.
  const points =
    data && data.length > 0
      ? data
      : MONTHS.map((month) => ({ month, placed: 0, completed: 0 }));

  return (
    <Panel className={className}>
      <PanelHeader title="Calls/month">
        {scopeOptions.length > 1 ? (
          <PillSelect
            label="Whose calls to show"
            value={scope}
            onChange={onScopeChange}
            options={scopeOptions}
          />
        ) : null}
      </PanelHeader>

      <div className="min-h-0 flex-1 px-2 pb-2">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={points}
            margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
          >
            <CartesianGrid
              vertical={false}
              stroke="var(--dash-chart-grid)"
              strokeDasharray="2 4"
            />

            <XAxis
              dataKey="month"
              tickLine={false}
              axisLine={false}
              tick={{ fill: 'var(--dash-text-mute)', fontSize: 9 }}
              interval={0}
              height={16}
            />

            <Tooltip
              cursor={{ fill: 'var(--dash-hover)', radius: 4 }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                const row = payload[0].payload as MonthPoint;
                return (
                  <div
                    className="rounded-[7px] px-2 py-1.5 text-[0.625rem] shadow-lg"
                    style={{
                      background: 'var(--dash-surface)',
                      border: '1px solid var(--dash-border)',
                      color: 'var(--dash-text)',
                    }}
                  >
                    <p className="font-semibold">{String(label)}</p>
                    <p style={{ color: 'var(--dash-text-dim)' }}>
                      {row.placed} placed · {row.completed} completed
                    </p>
                  </div>
                );
              }}
            />

            <Bar
              dataKey="placed"
              fill="var(--dash-chart-bar)"
              radius={[3, 3, 0, 0]}
              maxBarSize={18}
              isAnimationActive={!reducedMotion}
              animationDuration={420}
              animationEasing="ease-out"
            />

            <Line
              dataKey="completed"
              type="monotone"
              stroke="var(--dash-chart-line)"
              strokeWidth={2}
              dot={{ r: 2, fill: 'var(--dash-chart-line)', strokeWidth: 0 }}
              activeDot={{ r: 3.5, fill: 'var(--dash-chart-line)' }}
              isAnimationActive={!reducedMotion}
              animationDuration={420}
              animationEasing="ease-out"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
