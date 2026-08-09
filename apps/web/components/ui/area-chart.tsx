'use client';

import { useId } from 'react';
import {
  Bar,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from 'recharts';
import { cn } from '@/lib/cn';
import { usePrefersReducedMotion } from '@/lib/hooks/use-external-store';

export interface AreaChartPoint {
  label: string;
  value: number;
}

/** Which surface this chart is drawn on. `dark` swaps every colour for the
 * `--dark-*` tokens and adds a soft purple glow to the point markers - the
 * two decorative-accent hues (`--accent` for light, `--dark-bg-glow` for
 * dark) are kept independent by design (globals.css), so a page opting into
 * the dark glass material has to say so explicitly rather than relying on
 * token inheritance to guess it. */
export type AreaChartTone = 'light' | 'dark';

interface ToneColors {
  axisLine: string;
  tick: string;
  cursor: string;
  tooltipBorderClass: string;
  tooltipBgClass: string;
  tooltipLabelClass: string;
  tooltipValueClass: string;
  stem: string;
  dot: string;
  dotStroke: string;
  activeDot: string;
  pillBg: string;
  pillText: string;
  lastDot: string;
  glow: boolean;
}

const TONE: Record<AreaChartTone, ToneColors> = {
  light: {
    axisLine: 'var(--rule)',
    tick: 'var(--text-mute)',
    cursor: 'var(--rule-strong)',
    tooltipBorderClass: 'border-rule-strong',
    tooltipBgClass: 'bg-surface-raised',
    tooltipLabelClass: 'text-text-mute',
    tooltipValueClass: 'text-text',
    stem: 'var(--rule-strong)',
    dot: 'var(--accent)',
    dotStroke: 'var(--surface-raised)',
    activeDot: 'var(--accent)',
    pillBg: 'var(--surface-inverse)',
    pillText: 'var(--text-inverse)',
    lastDot: 'var(--text)',
    glow: false,
  },
  dark: {
    axisLine: 'var(--dark-rule)',
    tick: 'var(--dark-text-mute)',
    cursor: 'var(--dark-rule-strong)',
    tooltipBorderClass: 'border-dark-glass-border',
    tooltipBgClass: 'bg-dark-surface',
    tooltipLabelClass: 'text-dark-text-mute',
    tooltipValueClass: 'text-dark-text',
    stem: 'var(--dark-rule-strong)',
    // Flat fallbacks - `AreaChart` overrides these three to `url(#...)`
    // gradient references once it has an id to render `<defs>` against
    // (below), so the actual paint is the purple gradient, not this flat
    // value. Kept here so `TONE` stays a complete, self-describing map of
    // "what colour is this tone" even for a consumer that only reads the
    // static object. `--dark-bg-glow` - the same purple as the sidebar glow
    // and content-area gradient (globals.css) - rather than `--dark-accent`
    // (cyan), per the theme's purple pivot.
    dot: 'var(--dark-bg-glow)',
    dotStroke: 'var(--dark-surface)',
    activeDot: 'var(--dark-bg-glow)',
    // Flat fallback only - see `dot` above. Flat `--dark-bg-glow` itself
    // (#9333ea) clears just ~3.8:1 against near-black text, short of the
    // 4.5:1 text minimum, so this fallback (and the real gradient's two
    // stops, in `<defs>`) lighten it via `color-mix` first. 55% purple/45%
    // white computes (OKLab) to ~#c199f9, which clears ~8.9:1 against
    // `--dark-bg` - comfortably above the minimum, not just past it.
    pillBg: 'color-mix(in oklab, var(--dark-bg-glow) 55%, white)',
    // Near-black text (--dark-bg) against that lightened purple clears
    // ~8.9:1 (flat fallback) / ~7.5-10.5:1 across the real gradient's two
    // stops (both computed below) - the same "invert the callout" move the
    // light tone makes with --surface-inverse/--text-inverse, just paired
    // with a lighter purple instead of white-on-cyan.
    pillText: 'var(--dark-bg)',
    lastDot: 'var(--dark-bg-glow)',
    glow: true,
  },
};

interface DotRenderProps {
  cx?: number;
  cy?: number;
  index?: number;
  payload?: AreaChartPoint;
}

/**
 * Every point but the most recent is a small dot in the tone's accent colour.
 * The most recent point is the one value worth calling out without a hover -
 * a filled pill floating above it - the same way a reader's eye is meant to
 * land on "today" first. `glow` adds a soft drop-shadow halo to both, the
 * dark tone's "glowing chart" treatment.
 */
function makeDotRenderer(
  lastIndex: number,
  formatValue: (value: number) => string,
  tone: ToneColors,
) {
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
          fill={tone.dot}
          stroke={tone.dotStroke}
          strokeWidth={1.5}
          style={
            tone.glow
              ? {
                  filter:
                    'drop-shadow(0 0 4px color-mix(in oklab, var(--dark-bg-glow) 60%, transparent))',
                }
              : undefined
          }
        />
      );
    }

    const text = formatValue(payload.value);
    const pillWidth = Math.max(32, text.length * 6.5 + 18);
    return (
      <g
        key={`dot-${index}`}
        style={
          tone.glow
            ? {
                filter:
                  'drop-shadow(0 0 7px color-mix(in oklab, var(--dark-bg-glow) 75%, transparent))',
              }
            : undefined
        }
      >
        <rect
          x={cx - pillWidth / 2}
          y={cy - 30}
          width={pillWidth}
          height={20}
          rx={10}
          fill={tone.pillBg}
        />
        <text
          x={cx}
          y={cy - 16.5}
          textAnchor="middle"
          fontFamily="var(--font-mono)"
          fontSize={10}
          fontWeight={tone.glow ? 600 : 400}
          fill={tone.pillText}
        >
          {text}
        </text>
        <circle
          cx={cx}
          cy={cy}
          r={4.5}
          fill={tone.lastDot}
          stroke={tone.dotStroke}
          strokeWidth={1.5}
        />
      </g>
    );
  };
}

/**
 * A labeled lollipop chart - the bigger, axis-bearing sibling of `Sparkline`.
 *
 * Individual vertical stems from the baseline to each value, not a connected
 * line - each day's volume is its own reading, not a continuous quantity
 * being tracked between days. The stems and fill stay monochrome; this is
 * volume over time, not call-disposition state, so it gets none of the five
 * lamp colours. The point markers use the tone's decorative accent instead
 * (`--accent` for light, a `--dark-bg-glow` purple gradient for dark - never
 * a lamp hue), so marking "here's a day's value" can't be mistaken for
 * call/run/escalation state. Built on
 * Recharts - a `Bar` (thin enough to read as a stem) for the baseline-to-
 * value line, a `Line` with its own stroke suppressed purely to carry the
 * per-point `dot` renderer - rather than hand-rolled SVG, so animation,
 * resize, and the tooltip come from a maintained library instead of this
 * file re-deriving them.
 */
export function AreaChart({
  data,
  className,
  formatValue = (v) => String(v),
  tone = 'light',
}: {
  data: AreaChartPoint[];
  className?: string;
  formatValue?: (value: number) => string;
  tone?: AreaChartTone;
}) {
  const reducedMotion = usePrefersReducedMotion();
  // Unique per instance (not a fixed string) so a second dark chart on the
  // same page - none exists today, but this is a `components/ui/` primitive
  // - doesn't collide on the same `id` inside one SVG document. Colons from
  // `useId()` are stripped: valid in an `id` attribute, but a documented
  // footgun in older WebKit's `url(#...)` fragment matching.
  const instanceId = useId().replace(/:/g, '');
  const dotGradientId = `area-chart-dot-glow-${instanceId}`;
  const pillGradientId = `area-chart-pill-glow-${instanceId}`;
  const baseColors = TONE[tone];
  // The purple gradient (defined in `<defs>` below) replaces the flat
  // fallbacks `TONE.dark` declares for these three fields - see the
  // comments on `dot`/`pillBg` above for why a flat fill needs lightening
  // in the first place.
  const colors: ToneColors =
    tone === 'dark'
      ? {
          ...baseColors,
          dot: `url(#${dotGradientId})`,
          activeDot: `url(#${dotGradientId})`,
          lastDot: `url(#${dotGradientId})`,
          pillBg: `url(#${pillGradientId})`,
        }
      : baseColors;
  const summary = `${data.reduce((s, d) => s + d.value, 0)} calls over the last ${data.length} days`;
  const renderDot = makeDotRenderer(data.length - 1, formatValue, colors);

  return (
    <div
      className={cn('h-28 w-full', className)}
      role="img"
      aria-label={summary}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={data}
          margin={{ top: 26, right: 4, bottom: 0, left: 4 }}
        >
          {tone === 'dark' ? (
            <defs>
              {/* Point markers: a "glowing orb" - bright violet centre
                  fading to the exact ambient `--dark-bg-glow` purple at the
                  rim, tying each dot to the same hue as the sidebar glow and
                  content-area gradient. Decorative (no text over a dot), so
                  the 3:1 non-text contrast floor applies, not 4.5:1 - the
                  rim colour clears ~3.56:1 against the card composite. */}
              <radialGradient id={dotGradientId} cx="50%" cy="50%" r="50%">
                <stop
                  offset="0%"
                  style={{
                    stopColor:
                      'color-mix(in oklab, var(--dark-bg-glow) 55%, white)',
                  }}
                />
                <stop
                  offset="100%"
                  style={{ stopColor: 'var(--dark-bg-glow)' }}
                />
              </radialGradient>
              {/* "Today" callout pill: a subtler sheen across two lightened
                  purples (both `color-mix`d from `--dark-bg-glow`, never a
                  new hex) - this one carries text, so both stops stay
                  within the range that clears 4.5:1 against `--dark-bg`
                  (near-black) text: ~10.5:1 and ~7.5:1 respectively. */}
              <linearGradient id={pillGradientId} x1="0" y1="0" x2="1" y2="0">
                <stop
                  offset="0%"
                  style={{
                    stopColor:
                      'color-mix(in oklab, var(--dark-bg-glow) 45%, white)',
                  }}
                />
                <stop
                  offset="100%"
                  style={{
                    stopColor:
                      'color-mix(in oklab, var(--dark-bg-glow) 65%, white)',
                  }}
                />
              </linearGradient>
            </defs>
          ) : null}
          <XAxis
            dataKey="label"
            axisLine={{ stroke: colors.axisLine }}
            tickLine={false}
            tick={{
              fontFamily: 'var(--font-mono)',
              fontSize: 8,
              fill: colors.tick,
            }}
            interval={0}
          />
          <Tooltip
            cursor={{ stroke: colors.cursor, strokeWidth: 1 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const point = payload[0]?.payload as AreaChartPoint | undefined;
              if (!point) return null;
              return (
                <div
                  className={cn(
                    'rounded-sm border px-2.5 py-1.5 shadow-sm',
                    colors.tooltipBorderClass,
                    colors.tooltipBgClass,
                  )}
                >
                  <p
                    className={cn(
                      'font-mono text-label',
                      colors.tooltipLabelClass,
                    )}
                  >
                    {point.label}
                  </p>
                  <p
                    className={cn(
                      'font-mono text-data tabular-nums',
                      colors.tooltipValueClass,
                    )}
                  >
                    {formatValue(point.value)}
                  </p>
                </div>
              );
            }}
          />
          <Bar
            dataKey="value"
            barSize={2}
            fill={colors.stem}
            isAnimationActive={false}
          />
          <Line
            dataKey="value"
            stroke="transparent"
            dot={renderDot}
            activeDot={{
              r: 4.5,
              fill: colors.activeDot,
              stroke: colors.dotStroke,
              strokeWidth: 2,
            }}
            isAnimationActive={!reducedMotion}
            animationDuration={300}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
