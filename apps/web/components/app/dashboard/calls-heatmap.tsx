'use client';

import { Panel, PanelHeader, PillSelect } from './panel';

/** Calls on one calendar day. `date` is `YYYY-MM-DD`. */
export interface DayCount {
  date: string;
  calls: number;
}

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/** Every heatmap square, in px. */
const CELL = 8;
const GAP = 3;

/**
 * Calls per day across a year - one square per day, weeks as columns.
 *
 * The whole year at day resolution (365 or 366 squares) rather than a
 * summary: the point of a heatmap is spotting a single unusual day and the
 * rhythm of a week, and both disappear the moment days are averaged into
 * months.
 *
 * Columns are weeks, rows are weekdays, so a column is one Sunday-to-Saturday
 * span and reading across a row shows every Monday of the year. The first and
 * last columns are part-weeks wherever January 1st falls, which is why the
 * grid is built from an actual date walk rather than from `365 / 7`.
 *
 * Intensity is ranked against the year's own busiest day, so a quiet year
 * still shows its shape instead of a uniform wash of the palest tint.
 */
export function CallsHeatmap({
  data,
  year,
  onYearChange,
  yearOptions,
  className,
}: {
  data: DayCount[] | null;
  year: string;
  onYearChange: (year: string) => void;
  yearOptions: { value: string; label: string }[];
  className?: string;
}) {
  return (
    <Panel className={className}>
      <PanelHeader title="Call activity">
        {yearOptions.length > 0 ? (
          <PillSelect
            label="Year"
            value={year}
            onChange={onYearChange}
            options={yearOptions}
          />
        ) : null}
      </PanelHeader>

      <div className="min-h-0 flex-1 overflow-hidden px-3.5 pb-2">
        {/* Empty still draws the full year at the zero tint - the shape of
            the thing is the useful part, and a sentence in a blank box is
            not. */}
        <HeatmapGrid days={data ?? []} year={year} />
      </div>
    </Panel>
  );
}

interface Cell {
  date: string;
  calls: number;
  weekday: number;
  week: number;
}

function HeatmapGrid({ days, year }: { days: DayCount[]; year: string }) {
  const counts = new Map(days.map((day) => [day.date, day.calls]));

  const yearNumber = Number(year);
  const cells: Cell[] = [];
  let peak = 1;

  // Walk the real calendar rather than counting to 365: the leap day and the
  // weekday January 1st lands on both change the grid, and neither is
  // derivable from the length alone.
  const cursor = new Date(yearNumber, 0, 1);
  const firstWeekday = cursor.getDay();

  while (cursor.getFullYear() === yearNumber) {
    const iso = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, '0')}-${String(cursor.getDate()).padStart(2, '0')}`;
    const calls = counts.get(iso) ?? 0;
    if (calls > peak) peak = calls;

    const dayOfYear = Math.floor(
      (cursor.getTime() - new Date(yearNumber, 0, 1).getTime()) / 86_400_000,
    );

    cells.push({
      date: iso,
      calls,
      weekday: cursor.getDay(),
      week: Math.floor((dayOfYear + firstWeekday) / 7),
    });

    cursor.setDate(cursor.getDate() + 1);
  }

  const weeks = cells.length === 0 ? 53 : cells[cells.length - 1].week + 1;

  // Where each month's first day sits, so the axis labels line up with the
  // column that actually starts that month.
  const monthStarts = MONTHS.map((label, index) => {
    const first = cells.find(
      (cell) => Number(cell.date.slice(5, 7)) === index + 1,
    );
    return { label, week: first?.week ?? 0 };
  });

  function tint(calls: number): string {
    if (calls === 0) return 'var(--dash-heat-0)';
    const ratio = calls / peak;
    if (ratio <= 0.25) return 'var(--dash-heat-1)';
    if (ratio <= 0.5) return 'var(--dash-heat-2)';
    if (ratio <= 0.75) return 'var(--dash-heat-3)';
    return 'var(--dash-heat-4)';
  }

  const byPosition = new Map(
    cells.map((cell) => [`${cell.weekday}-${cell.week}`, cell]),
  );

  const columns = `repeat(${weeks}, minmax(0, 1fr))`;

  return (
    <div className="flex h-full min-h-0 flex-col justify-center gap-1">
      <div className="flex">
        <div className="min-w-0 flex-1">
          <div
            className="grid"
            style={{
              gridTemplateColumns: columns,
              gridTemplateRows: `repeat(7, ${CELL}px)`,
              gap: `${GAP}px`,
              gridAutoFlow: 'column',
            }}
          >
            {Array.from({ length: weeks * 7 }, (_, index) => {
              const week = Math.floor(index / 7);
              const weekday = index % 7;
              const cell = byPosition.get(`${weekday}-${week}`);

              // Before January 1st or after December 31st - the part-weeks
              // at each end. Drawn as a hole, not a zero-call day.
              if (!cell) {
                return <span key={index} style={{ height: CELL }} />;
              }

              const shade = tint(cell.calls);
              return (
                <span
                  key={index}
                  className="group/cell relative"
                  style={{ height: CELL }}
                >
                  <span
                    className="block size-full rounded-[2px]"
                    style={{ background: shade }}
                  />
                  {/* A real tooltip rather than `title`: the native one is a
                      hard-edged OS box that cannot be styled and takes a
                      second to appear. */}
                  <span
                    role="tooltip"
                    className="pointer-events-none absolute bottom-[calc(100%+5px)] left-1/2 z-20 hidden -translate-x-1/2 whitespace-nowrap rounded-[6px] px-1.5 py-1 text-[0.5625rem] font-medium shadow-lg group-hover/cell:block"
                    style={{
                      background: shade,
                      // A zero-call day's tint is near the card surface, so
                      // its label needs the normal text colour; every lit
                      // cell is saturated enough to carry white.
                      color:
                        cell.calls === 0 ? 'var(--dash-text-dim)' : '#ffffff',
                      border: '1px solid var(--dash-border)',
                    }}
                  >
                    {MONTHS[Number(cell.date.slice(5, 7)) - 1]}{' '}
                    {Number(cell.date.slice(8, 10))} · {cell.calls}{' '}
                    {cell.calls === 1 ? 'call' : 'calls'}
                  </span>
                </span>
              );
            })}
          </div>

          {/* Month axis. Each label is placed at the column its month starts
              in, so it sits over the right part of the grid. */}
          <div
            className="mt-1 grid"
            style={{ gridTemplateColumns: columns, gap: `${GAP}px` }}
          >
            {monthStarts.map(({ label, week }) => (
              <span
                key={label}
                className="text-[0.5rem] leading-none"
                style={{
                  gridColumn: `${week + 1} / span 4`,
                  color: 'var(--dash-text-mute)',
                }}
              >
                {label}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div
        className="flex shrink-0 items-center justify-end gap-1 text-[0.5625rem]"
        style={{ color: 'var(--dash-text-mute)' }}
      >
        <span>Less</span>
        {[0, 1, 2, 3, 4].map((step) => (
          <span
            key={step}
            aria-hidden
            className="size-2 rounded-[2px]"
            style={{ background: `var(--dash-heat-${step})` }}
          />
        ))}
        <span>More</span>
      </div>
    </div>
  );
}
