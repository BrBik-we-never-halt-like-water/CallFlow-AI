'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/cn';
import { usePrefersReducedMotion } from '@/lib/hooks/use-external-store';
import { DottedWave } from './dotted-wave';

/** A single metric: the number, what it counts, and an optional qualifier. */
export interface Metric {
  label: string;
  value: number | null;
  /** A label too long for one line is given as its lines instead, e.g.
   *  `['Calls placed', 'Today']`. The shorter line is then justified to the
   *  width of the longer one, so the block reads as a tidy stack rather
   *  than as a ragged wrap. Single-string labels stay on one line. */
  labelLines?: string[];
}

/**
 * Number top-right, label beneath it on the left.
 *
 * The number is the thing being read, so it gets the corner and the size;
 * the label only says which number it is. `items-start` rather than
 * centring, so the figure sits at the top of the card the way the credits
 * card's does - the two rows then agree.
 */
function MetricBody({ metric }: { metric: Metric }) {
  const lines = metric.labelLines ?? [metric.label];
  // The longest line sets the block's width; every other line is stretched
  // to fill it (`text-align: justify` on a forced line break), so a two-line
  // label reads as one rectangle rather than as a ragged wrap.
  const widest = lines.reduce((a, b) => (b.length > a.length ? b : a), '');

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-start justify-between gap-2">
        <span
          className="min-w-0 shrink-0 font-medium uppercase leading-[1.3]"
          style={{ color: 'var(--dash-figure-label)' }}
        >
          {lines.map((line) => (
            <span
              key={line}
              className="block whitespace-nowrap text-[0.5rem]"
              style={
                // Only the shorter lines need stretching; the widest one
                // already defines the width and must not be spaced out.
                line === widest
                  ? { letterSpacing: '0.05em' }
                  : {
                      textAlignLast: 'justify',
                      textAlign: 'justify',
                      // Reserve the widest line's measure so justify has
                      // something to spread against.
                      width: `${widest.length}ch`,
                    }
              }
            >
              {line}
            </span>
          ))}
        </span>
        <p
          className="dash-num shrink-0 text-[2.25rem] font-semibold leading-none"
          style={{ color: 'var(--dash-figure)' }}
        >
          {metric.value === null ? '—' : metric.value.toLocaleString()}
        </p>
      </div>
    </div>
  );
}

/** One count. The three static cards in the KPI row. */
export function KpiCard({
  metric,
  className,
}: {
  metric: Metric;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'dash-card dash-wave-host flex flex-col px-3.5 py-3',
        className,
      )}
    >
      <DottedWave rows={7} alpha={0.28} />
      <MetricBody metric={metric} />
    </div>
  );
}

const CYCLE_MS = 4500;

/**
 * One card that cycles through several call metrics.
 *
 * Auto-advance is a real cost in a dashboard someone reads rather than
 * watches, so it is bounded three ways: it pauses while hovered or focused
 * (you never lose the number you were reading), it stops entirely for
 * anyone who prefers reduced motion, and the dots let you take over. The
 * whole set is always in the DOM for screen readers, so cycling never
 * hides a value from assistive tech.
 */
export function CyclingKpiCard({
  metrics,
  className,
}: {
  metrics: Metric[];
  className?: string;
}) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const reducedMotion = usePrefersReducedMotion();
  const count = metrics.length;

  // `index` can outrun the array when metrics shrink between renders.
  const safeIndex = count === 0 ? 0 : index % count;

  const holding = paused || reducedMotion || count < 2;

  useEffect(() => {
    if (holding) return;
    const timer = window.setInterval(
      () => setIndex((current) => current + 1),
      CYCLE_MS,
    );
    return () => window.clearInterval(timer);
  }, [holding]);

  if (count === 0) return null;

  const current = metrics[safeIndex];

  return (
    <div
      className={cn(
        'dash-card dash-wave-host flex flex-col px-3.5 pb-5 pt-3',
        className,
      )}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
    >
      <DottedWave rows={7} alpha={0.28} />

      {/* aria-live is off: an unattended rotation announcing itself every few
          seconds is noise. The full list below carries the values instead. */}
      <div aria-hidden className="min-w-0">
        <MetricBody metric={current} />
      </div>

      <ul className="sr-only">
        {metrics.map((metric) => (
          <li key={metric.label}>
            {metric.label}: {metric.value === null ? 'unavailable' : metric.value}
          </li>
        ))}
      </ul>

      {count > 1 ? (
        <div className="absolute inset-x-0 bottom-1.5 flex items-center justify-center gap-1">
          {metrics.map((metric, dotIndex) => (
            <button
              key={metric.label}
              type="button"
              aria-label={`Show ${metric.label}`}
              aria-current={dotIndex === safeIndex}
              onClick={() => setIndex(dotIndex)}
              className="size-1.5 rounded-full transition-opacity"
              style={{
                background:
                  dotIndex === safeIndex
                    ? 'var(--dash-brand)'
                    : 'var(--dash-border-strong)',
              }}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
