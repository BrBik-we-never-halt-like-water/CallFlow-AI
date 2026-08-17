'use client';

import {
  ChartLineUpIcon,
  PhoneOutgoingIcon,
  PhoneSlashIcon,
  PhoneCallIcon,
  PlusIcon,
  QuotesIcon,
  TrendDownIcon,
  TrendUpIcon,
} from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { Lamp } from '@/components/brand/lamp';
import { ConnectionBanner } from '@/components/app/connection-banner';
import { InviteDialog } from '@/components/app/invite-dialog';
import { MaskedPhone } from '@/components/app/masked-phone';
import { TeamControls } from '@/components/app/overview-org-section';
import { AreaChart } from '@/components/ui/area-chart';
import { LampBadge, Tag } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { formatAge, formatDuration } from '@/lib/format';
import { countLamps, lampForOutcome, type LampState } from '@/lib/lamp';
import {
  api,
  type Outcome,
  type Team,
  type TeamPerformance,
} from '@/lib/api';
import { useAppStore } from '@/lib/app-store';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession } from '@/lib/hooks/use-session';

/**
 * The bottom-right grid slot (Twisty's "Proposal Progress") is a stat-trio,
 * not a donut - three columns divided by a hairline, each a count over a
 * label, matching that slot's own proportions better than a circle does.
 * Deliberately just these three, in this order: the two states that need a
 * decision (a person, or another try) before the one that's already settled.
 * `off`/"Skipped" still exists as data - it's just not one of
 * the three columns this specific slot has room for.
 */
const DISPOSITION_STAT_TRIO: {
  state: LampState;
  label: string;
  match: (d: string) => boolean;
}[] = [
  {
    state: 'flare',
    label: 'Needs a person',
    match: (d) => d === 'escalated' || d === 'unreachable',
  },
  { state: 'brass', label: 'Retrying', match: (d) => d === 'retry' },
  { state: 'jade', label: 'Auto-closed', match: (d) => d === 'auto_closed' },
];

/** The strip shows the most recent calls. 100 is the design's stated window. */
const STRIP_WINDOW = 100;

/*
 * `DARK_SCOPE_STYLE` used to live here - an inline object re-scoping the
 * generic colour tokens to their `--dark-*` equivalents on this page's own
 * wrapper, because at the time nothing above it could. Three separate tasks
 * had re-derived that same block independently (this page, the runs page,
 * `DataTable`), which is the usual sign that a thing belongs one level up.
 *
 * It belongs on `:root`, and that is where it is now: `[data-theme='dark']`
 * (globals.css) repoints every one of those tokens for the whole document, so
 * a page no longer has to know the theme exists. Deleted rather than kept as a
 * no-op, because an inline `style` beats a stylesheet on specificity and would
 * silently pin this page to dark forever - it would be the one surface the
 * theme toggle could not move.
 */

/*
 * `PRIMARY_CTA_STYLE` is gone for the same reason as `DARK_SCOPE_STYLE` above,
 * and it is worth saying why explicitly, because the reasoning that justified
 * it was correct right up until it wasn't.
 *
 * It pinned this page's primary buttons to `--dark-accent`, because `--primary`
 * was the light theme's indigo and this page was permanently dark: `#3b2fd9`
 * clears 8.09:1 for its white label but only 2.52:1 against `--dark-bg`, so it
 * sank into the page, while `#4f46e5` clears both at 6.29:1 and 3.24:1.
 *
 * All of that is still true - and it is now `[data-theme='dark']`'s job, where
 * it says exactly that. `--primary` resolves to `#3b2fd9` in light and
 * `#4f46e5` in dark, so the button is correct in both without an override.
 * Keeping the inline style would have inverted its own purpose: an inline
 * `background` outranks the stylesheet, so these buttons would have stayed
 * dark-indigo on a white page.
 */

export default function OverviewPage() {
  const session = useSession();
  const { phase, outcomes, runs, campaigns, escalations, loadingRuns } =
    useAppStore();
  const canInvite =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('team:invite');
  const canStart =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('runs:start');
  const canReadTeam =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('runs:read_team');

  const settled = useMemo(
    () => outcomes.filter((o) => o.disposition !== 'in_flight'),
    [outcomes],
  );

  const recent = useMemo(() => settled.slice(0, STRIP_WINDOW), [settled]);
  const lamps = useMemo(() => recent.map(lampForOutcome), [recent]);
  const outcomeCounts = useMemo(() => countLamps(lamps), [lamps]);

  const avgDuration = useMemo(() => {
    const withDuration = settled.filter((o) => o.duration_seconds != null);
    if (withDuration.length === 0) return null;
    return (
      withDuration.reduce((sum, o) => sum + (o.duration_seconds ?? 0), 0) /
      withDuration.length
    );
  }, [settled]);

  // Seven day-labeled buckets, oldest first. Derived from real timestamps rather
  // than invented, so an account with no history gets no chart at all.
  const volumeSeries = useMemo(() => {
    if (settled.length === 0) return [];
    // Anchored to the most recent result rather than to `Date.now()`, which would
    // be an impure read during render. Buckets follow the data, not the clock.
    const now = new Date(settled[0].created_at).getTime();
    const day = 86_400_000;
    return Array.from({ length: 7 }, (_, i) => {
      const from = now - (6 - i + 1) * day;
      const to = now - (6 - i) * day;
      const value = settled.filter((o) => {
        const at = new Date(o.created_at).getTime();
        return at >= from && at < to;
      }).length;
      return {
        label: new Date(to - 1).toLocaleDateString(undefined, {
          weekday: 'narrow',
        }),
        value,
      };
    });
  }, [settled]);

  const weekTotal = useMemo(
    () => volumeSeries.reduce((sum, d) => sum + d.value, 0),
    [volumeSeries],
  );

  // A real week-over-week comparison, from the same real timestamps as
  // `volumeSeries` - not fabricated. With no full prior week to compare
  // against, there's nothing honest to show, so the pill is omitted rather
  // than printing a misleading +100%.
  const trend = useMemo(() => {
    if (settled.length === 0) return null;
    const now = new Date(settled[0].created_at).getTime();
    const day = 86_400_000;
    const currentCount = settled.filter((o) => {
      const at = new Date(o.created_at).getTime();
      return at > now - 7 * day && at <= now;
    }).length;
    const previousCount = settled.filter((o) => {
      const at = new Date(o.created_at).getTime();
      return at > now - 14 * day && at <= now - 7 * day;
    }).length;
    if (previousCount === 0) return null;
    const pct = Math.round(
      ((currentCount - previousCount) / previousCount) * 100,
    );
    return { pct, up: pct >= 0 };
  }, [settled]);

  const dispositionBreakdown = useMemo(
    () =>
      DISPOSITION_STAT_TRIO.map(({ state, label, match }) => ({
        state,
        label,
        value: settled.filter((o) => match(o.disposition)).length,
      })),
    [settled],
  );

  const hasAnything = settled.length > 0 || runs.length > 0;

  // Skeleton while there's nothing to show yet - connecting, or runs still loading.
  // Once real data exists, never fall back to this, even on a background refetch.
  if ((phase !== 'up' || loadingRuns) && !hasAnything) {
    return (
      <div className="relative isolate min-h-full">
        <div
          aria-hidden
          className="app-canvas absolute -inset-x-4 -inset-y-6 -z-10 sm:-inset-x-6"
        />
        <div className="flex flex-col gap-6">
          <PageTitle session={session} canStart={canStart} />
          <ConnectionBanner phase={phase} />
          {phase !== 'down' ? <LoadingSkeleton /> : null}
        </div>
      </div>
    );
  }

  return (
    <div className="relative isolate min-h-full">
      {/* The dark canvas + indigo glow, bled into `<main>`'s own padding
          (AppShell, out of scope for this task) via negative inset rather
          than negative margin, so it fills the space that padding already
          reserves instead of creating any new page overflow. `isolate`
          gives this wrapper its own stacking context so the backdrop's
          negative z-index is only ever compared against its own sibling,
          regardless of `template.tsx`'s `.page-enter` transform animation
          (which briefly creates its own stacking context on every route
          change and, without `isolate` here, let the ancestor `.app-canvas`
          wash paint in front of the backdrop for that ~240ms window -
          confirmed with the browser's computed stacking order, not just
          inferred from spec-reading). */}
      <div
        aria-hidden
        className="app-canvas absolute -inset-x-4 -inset-y-6 -z-10 sm:-inset-x-6"
      />

      <div className="flex flex-col gap-6">
        <PageTitle session={session} canStart={canStart} />
        <ConnectionBanner phase={phase} />

        {/* ---- The Twisty-mapped grid: ~60/40, left column a hero chart over
            two secondary cards, right column a taller list over a stat-trio -
            same slots, same proportions, our own cards and data. ------------ */}
        <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
          {/* ================= Left column (~60%) ================= */}
          <div className="flex flex-col gap-6">
            <Panel className="panel-glass flex flex-col gap-4 p-5 sm:p-7">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                    <ChartLineUpIcon aria-hidden className="size-4.5" />
                  </span>
                  <div className="flex flex-col">
                    <p className="text-small font-bold text-text">Volume</p>
                    <p className="text-small text-text-mute">Last 7 days</p>
                  </div>
                </div>
                {trend ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-rule bg-surface-hover px-2.5 py-1 text-small font-medium text-text">
                    {trend.up ? (
                      <TrendUpIcon
                        aria-hidden
                        className="size-3.5 text-primary"
                      />
                    ) : (
                      <TrendDownIcon
                        aria-hidden
                        className="size-3.5 text-text-mute"
                      />
                    )}
                    {trend.pct > 0 ? '+' : ''}
                    {trend.pct}% vs last week
                  </span>
                ) : null}
              </div>

              {volumeSeries.length > 0 ? (
                <AreaChart data={volumeSeries} />
              ) : (
                <p className="py-6 text-center text-small text-text-dim">
                  No calls yet
                </p>
              )}
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="font-display text-h2 text-text tabular-nums">
                  {weekTotal}
                </span>
                <span className="text-small text-text-dim">
                  call{weekTotal === 1 ? '' : 's'} settled this week
                </span>
              </div>
            </Panel>

            {/* ---- Team (55%) + next move (45%) ----------------------------
                `NextMoveCard` only has one message left ("place your first
                call") now that "bring in a teammate" - a second invite entry
                point duplicating `TeamPreview`'s own "+" - was retired. Once
                a run exists there's nothing left for this slot to say, so it
                disappears and Team grows to fill the row. */}
            <div
              className={
                runs.length > 0
                  ? 'grid gap-4'
                  : 'grid gap-4 sm:grid-cols-[11fr_9fr]'
              }
            >
              <TeamPreview canInvite={canInvite} />
              {runs.length > 0 ? null : <NextMoveCard canStart={canStart} />}
            </div>
          </div>

          {/* ================= Right column (~40%) ================= */}
          <div className="flex flex-col gap-6">
            {/* ---- Needs a person: taller, full right-column width -------- */}
            <Panel
              interactive
              className="panel-glass flex flex-1 flex-col gap-4 p-5 sm:p-6"
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-small font-bold text-text-mute">
                  Needs a person
                </p>
                {escalations.length > 0 ? (
                  <Link
                    href="/app/escalations"
                    className="text-small font-medium text-text hover:text-text-dim"
                  >
                    See all {escalations.length}
                  </Link>
                ) : null}
              </div>

              {escalations.length === 0 ? (
                <EmptyState
                  title="Nothing needs you right now"
                  body="Frustration, opt-outs, or requests for a person land here."
                />
              ) : (
                <ul className="flex flex-col divide-y divide-rule">
                  {escalations.slice(0, 5).map((outcome, i) => (
                    <li key={`${outcome.contact_name}-${i}`}>
                      <NeedsPersonRow outcome={outcome} />
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            {/* ---- Disposition, as a stat-trio ------------------------------
                Deviation, flagged per the brief: no sparkline under each
                number yet (there's no Sparkline component in this codebase
                to wire one from today - the brief's own accepted fallback for
                "more work than it's worth right now" is a resized donut; this
                goes one step further into the actual stat-trio shape since the
                layout cost of that was low, just without the sparkline detail). */}
            <Panel className="panel-glass flex flex-col gap-4 p-5 sm:p-6">
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-small font-bold text-text-mute">
                  Disposition
                </p>
                <span className="text-small tabular-nums text-text-mute">
                  {formatDuration(avgDuration)} avg
                </span>
              </div>
              {settled.length > 0 ? (
                <div className="grid grid-cols-3 divide-x divide-rule">
                  {dispositionBreakdown.map((item) => (
                    <div
                      key={item.label}
                      className="flex flex-col gap-1 px-3 first:pl-0 last:pr-0"
                    >
                      <span className="font-display text-h3 text-text tabular-nums">
                        {item.value}
                      </span>
                      <p className="truncate text-small font-bold text-text-mute">
                        {item.label}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-6 text-center text-small text-text-dim">
                  No calls yet
                </p>
              )}
            </Panel>
          </div>
        </div>

        {/* ---- Outcome distribution: the page's visual anchor, full width --
            The count-per-disposition row below is the primary visual, not a
            single lamp standing in for the whole distribution - at the volumes
            this page usually shows, one dot (or one donut slice) reads as far
            more definitive than the sample backing it. A zero count still
            renders, dimmed: "0 need a person" is real information. --------- */}
        <div className="signal-field rounded-xl">
          <Panel className="panel-glass flex flex-col gap-5 p-5 sm:p-7">
            <div className="flex flex-col gap-1">
              <p className="text-small font-bold text-text-mute">
                Outcome distribution
              </p>
              <h2 className="font-display text-h3 text-text">
                The last {Math.min(settled.length, STRIP_WINDOW)}{' '}
                {settled.length === 1 ? 'call' : 'calls'}
              </h2>
            </div>

            {recent.length === 0 ? (
              <EmptyState
                icon={PhoneSlashIcon}
                title="Nothing has been dialled yet"
                body="Add contacts and start a run."
                action={
                  canStart ? (
                    <Button asChild>
                      <Link href="/app/runs/new">Start a run</Link>
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-data">
                <OutcomeCount
                  state="jade"
                  n={outcomeCounts.closed}
                  label="closed"
                />
                <OutcomeCount
                  state="brass"
                  n={outcomeCounts.retry}
                  label="retry"
                  pulse
                />
                <OutcomeCount
                  state="flare"
                  n={outcomeCounts.needsPerson}
                  label="need a person"
                />
              </div>
            )}
          </Panel>
        </div>

        {/* ---- Recent runs --------------------------------------------------- */}
        <Panel
          interactive
          className="panel-glass flex flex-col gap-4 p-5 sm:p-6"
        >
          <div className="flex items-center justify-between gap-2">
            <p className="text-small font-bold text-text-mute">Recent runs</p>
            <Link
              href="/app/runs"
              className="text-small font-medium text-text hover:text-text-dim"
            >
              All runs
            </Link>
          </div>

          {runs.length === 0 ? (
            <EmptyState
              title="No runs yet"
              body="Runs are how contacts get called."
              action={
                canStart ? (
                  <Button asChild size="sm">
                    <Link href="/app/runs/new">Start a run</Link>
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <ul className="flex flex-col">
              {runs.slice(0, 5).map((run) => {
                const name =
                  campaigns.find((c) => c.id === run.campaign_id)?.name ??
                  run.campaign_id;
                return (
                  <li
                    key={run.id}
                    className="border-b border-rule last:border-0"
                  >
                    <Link
                      href={`/app/runs/${run.id}`}
                      className="-mx-2 flex items-center gap-3 rounded-md px-2 py-2.5 transition-colors hover:bg-surface-hover"
                    >
                      <span
                        aria-hidden
                        className="flex size-8 shrink-0 items-center justify-center rounded-md bg-surface-inverse text-small font-medium text-text-inverse"
                      >
                        {name.charAt(0).toUpperCase()}
                      </span>
                      <span className="min-w-0 flex-1 truncate text-small text-text">
                        {name}
                      </span>
                      <LampBadge
                        state={run.completed >= run.total ? 'jade' : 'brass'}
                        pulse={run.completed < run.total}
                      >
                        {run.completed}/{run.total}
                      </LampBadge>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        {/* ---- Recent calls ---------------------------------------------- */}
        {settled.length > 0 ? (
          <Panel className="panel-glass flex flex-col gap-1 p-5 sm:p-6">
            <p className="pb-2 text-small font-bold text-text-mute">
              Recent calls
            </p>
            <ul className="flex flex-col">
              {settled.slice(0, 6).map((outcome, i) => {
                const lamp = lampForOutcome(outcome);
                const campaign = campaigns.find(
                  (c) => c.id === outcome.campaign_id,
                );
                return (
                  <li
                    key={`${outcome.contact_name}-${i}`}
                    className="flex flex-wrap items-center gap-3 border-b border-rule py-3 last:border-0"
                  >
                    {/* CallFlow only ever dials out - there's no inbound leg
                        to distinguish - so this stays a fixed "outbound"
                        glyph rather than a direction toggle with nothing to
                        toggle. */}
                    <PhoneOutgoingIcon
                      aria-hidden
                      className="size-3.5 shrink-0 text-text-mute"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-small text-text">
                        {outcome.contact_name}
                      </p>
                      <MaskedPhone
                        phone={outcome.phone_masked}
                        className="text-label"
                      />
                    </div>
                    {campaign ? (
                      <Tag mono={false} className="shrink-0">
                        {/* `truncate` on `Tag`'s own inline-flex root doesn't
                            reliably render the ellipsis in Chrome - it needs
                            a block-level box of its own to clip against. */}
                        <span className="block max-w-32 truncate">
                          {campaign.name}
                        </span>
                      </Tag>
                    ) : null}
                    <span className="inline-flex shrink-0 items-center gap-1.5 text-small text-text">
                      <Lamp state={lamp.state} size="sm" pulse={lamp.pulse} />
                      {lamp.label}
                    </span>
                    <span className="w-16 shrink-0 text-right font-mono text-data tabular-nums text-text-mute">
                      {formatDuration(outcome.duration_seconds)}
                    </span>
                  </li>
                );
              })}
            </ul>
          </Panel>
        ) : null}

        {canReadTeam ? <TeamPerformancePanel /> : null}
      </div>
    </div>
  );
}

const OUTCOME_COUNT_TEXT: Record<LampState, string> = {
  off: 'text-lamp-off-text',
  ice: 'text-lamp-ice-text',
  brass: 'text-lamp-brass-text',
  jade: 'text-lamp-jade-text',
  flare: 'text-lamp-flare-text',
};

/** One bucket of the outcome-distribution legend: a lamp-coloured chip, a
 * count, and a label. A zero count still renders - dimmed to `off`, rather
 * than dropped - because "0 need a person" is real information worth seeing. */
function OutcomeCount({
  state,
  n,
  label,
  pulse,
}: {
  state: LampState;
  n: number;
  label: string;
  pulse?: boolean;
}) {
  const isZero = n === 0;
  return (
    <span className="inline-flex items-center gap-1.5">
      <Lamp state={isZero ? 'off' : state} size="sm" pulse={!isZero && pulse} />
      <span
        className={
          isZero
            ? 'tabular-nums text-text-mute'
            : `tabular-nums ${OUTCOME_COUNT_TEXT[state]}`
        }
      >
        {n} {label}
      </span>
    </span>
  );
}

/** The last thing they said before this got escalated - the one line that
 * usually explains the decision faster than any typed field can. */
function lastTranscriptTurn(transcript: string | null): string | null {
  if (!transcript) return null;
  const turns = transcript.split('\n').filter(Boolean);
  return turns.at(-1) ?? null;
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/**
 * One row of the "Needs a person" worklist preview: avatar, name + age, a
 * muted/label-forward urgency indicator (`LampBadge` - text is the primary
 * signal, the tinted pill background is the secondary accent, never a bold
 * saturated fill), the last thing the contact said, the sentiment behind the
 * escalation, and a real link into the worklist where the actual actions
 * (call back, reassign, mark resolved) live. Named "Review", not "Takeover" -
 * this product has no live call-transfer feature, and CLAUDE.md §4 #9 rules
 * out labelling a link with a verb it can't actually perform.
 */
function NeedsPersonRow({ outcome }: { outcome: Outcome }) {
  const quote = lastTranscriptTurn(outcome.transcript);
  const sentimentLine =
    outcome.sentiment !== 'unknown'
      ? [capitalise(outcome.sentiment), outcome.sentiment_reason]
          .filter(Boolean)
          .join(' - ')
      : outcome.disposition_reason;

  return (
    <div className="flex flex-col gap-2.5 py-3 first:pt-0 last:pb-0">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span
            aria-hidden
            className="flex size-9 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-small font-medium text-text"
          >
            {outcome.contact_name.charAt(0).toUpperCase()}
          </span>
          <div className="flex min-w-0 flex-col">
            <p className="truncate text-small font-medium text-text">
              {outcome.contact_name}
            </p>
            <span className="font-mono text-data text-text-mute">
              {formatAge(outcome.created_at)}
            </span>
          </div>
        </div>
        <LampBadge state="flare" className="shrink-0">
          Needs a person
        </LampBadge>
      </div>

      {quote ? (
        <blockquote className="flex items-start gap-1.5 border-l-2 border-rule pl-3 text-small text-text-dim italic">
          <QuotesIcon
            aria-hidden
            weight="fill"
            className="mt-0.5 size-3 shrink-0 text-text-mute"
          />
          <span className="min-w-0">{quote}</span>
        </blockquote>
      ) : null}

      {sentimentLine ? (
        <p className="truncate text-small text-text-mute">{sentimentLine}</p>
      ) : null}

      <Link
        href="/app/escalations"
        className="self-start text-small font-medium text-text hover:text-text-dim"
      >
        Review &rarr;
      </Link>
    </div>
  );
}

/**
 * Everything an admin/owner/viewer needs to see about a teammate at a
 * glance - calls made, run status, open "needs a person" items, and their
 * slice of the daily budget - gated the same way as the Volume chart's own
 * team breadth (`runs:read_team`; an operator's own numbers are already
 * everywhere else on this page, and the org-wide RLS narrowing would return
 * nothing for them here anyway). Deliberately its own full-width section
 * below the main grid, not squeezed into the Volume card - this many
 * columns needs the width, and the existing 2-column layout above stays
 * exactly as it was rather than getting more crowded.
 */
function TeamPerformancePanel() {
  const [rows, setRows] = useState<TeamPerformance[] | null>(null);

  useOrgScopedEffect(() => {
    api
      .teamPerformance()
      .then((data) =>
        setRows([...data].sort((a, b) => b.total_calls - a.total_calls)),
      )
      .catch(() => setRows([]));
  });

  if (rows !== null && rows.length === 0) return null;

  return (
    <Panel className="dark-panel-glass flex flex-col gap-4 p-5 sm:p-6">
      <p className="text-small font-bold text-text-mute">Team performance</p>

      {rows === null ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-max text-small">
            <thead>
              <tr className="border-b border-rule text-left text-text-mute">
                <th className="py-2 pr-4 font-bold">Teammate</th>
                <th className="py-2 pr-4 text-right font-bold">Calls</th>
                <th className="py-2 pr-4 text-right font-bold">Closed</th>
                <th className="py-2 pr-4 text-right font-bold">
                  Runs active
                </th>
                <th className="py-2 pr-4 text-right font-bold">
                  Runs completed
                </th>
                <th className="py-2 pr-4 text-right font-bold">
                  Runs failed
                </th>
                <th className="py-2 pr-4 text-right font-bold">
                  Needs a person
                </th>
                <th className="py-2 text-right font-bold">Credits today</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.user_id ?? row.name ?? 'unknown'}
                  className="border-b border-rule last:border-0"
                >
                  <td className="py-2.5 pr-4">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-rule bg-surface-sunken text-[0.65rem] font-medium text-text">
                        {(row.name?.trim() || '?').charAt(0).toUpperCase()}
                      </span>
                      <span className="min-w-0 truncate text-text">
                        {row.name?.trim() || 'Removed teammate'}
                      </span>
                    </div>
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-data tabular-nums text-text">
                    {row.total_calls}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-data tabular-nums text-text-mute">
                    {row.calls_closed}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-data tabular-nums text-text-mute">
                    {row.runs_active}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-data tabular-nums text-text-mute">
                    {row.runs_completed}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-mono text-data tabular-nums text-text-mute">
                    {row.runs_failed}
                  </td>
                  <td className="py-2.5 pr-4 text-right">
                    {row.open_escalations > 0 ? (
                      <span className="inline-flex items-center gap-1.5 font-mono text-data tabular-nums text-lamp-flare-text">
                        <Lamp state="flare" size="sm" />
                        {row.open_escalations}
                      </span>
                    ) : (
                      <span className="font-mono text-data tabular-nums text-text-mute">
                        0
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 text-right font-mono text-data tabular-nums text-text-mute">
                    {row.daily_allocation > 0
                      ? `${row.credits_used_today} / ${row.daily_allocation}`
                      : 'unallocated'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

/** Who's on this - a quiet counterpart to the run/escalation data around it. */
function TeamPreview({ canInvite }: { canInvite: boolean }) {
  const [team, setTeam] = useState<Team | null>(null);
  const [inviting, setInviting] = useState(false);

  function load() {
    api
      .listMembers()
      .then(setTeam)
      .catch(() => setTeam(null));
  }

  useOrgScopedEffect(() => {
    void load();
  });

  const members = team?.members ?? [];
  const shown = members.slice(0, 3);

  return (
    <Panel className="panel-glass flex flex-col gap-3 p-5 sm:p-6">
      <div className="flex items-center justify-between gap-2">
        <p className="text-small font-bold text-text-mute">Team</p>
        <div className="flex items-center gap-1.5">
          <Link
            href="/app/organisation?tab=team"
            className="text-small font-medium text-text hover:text-text-dim"
          >
            Manage
          </Link>
          {canInvite ? (
            <button
              type="button"
              onClick={() => setInviting(true)}
              aria-label="Invite a teammate"
              className="flex size-7 items-center justify-center rounded-full bg-surface-sunken text-text-dim transition-colors hover:bg-surface-hover hover:text-text"
            >
              <PlusIcon aria-hidden className="size-3.5" />
            </button>
          ) : null}
        </div>
      </div>

      {team === null ? (
        <div className="flex items-center gap-2">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="size-8 rounded-full" />
          ))}
        </div>
      ) : shown.length === 0 ? (
        <p className="text-small text-text-dim">Just you here so far.</p>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {shown.map((m) => (
            <li key={m.user_id} className="flex items-center gap-2.5">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-full border border-rule bg-surface-sunken text-small font-medium text-text">
                {(m.name?.trim() || m.email).charAt(0).toUpperCase()}
              </span>
              <span className="min-w-0 flex-1 truncate text-small text-text">
                {m.name?.trim() || m.email}
              </span>
              <Tag>{m.role}</Tag>
            </li>
          ))}
        </ul>
      )}

      {canInvite ? (
        <InviteDialog
          open={inviting}
          onOpenChange={setInviting}
          onInvited={load}
        />
      ) : null}
    </Panel>
  );
}

/** The one deliberately warmer card on the page - an invitation to the single
 * next action while there isn't one yet. Only rendered before the first run;
 * once any run exists, `TeamPreview` grows to fill this row instead (this
 * card's other message, "Bring in a teammate", was a second invite entry
 * point duplicating `TeamPreview`'s own "+" - retired, not repurposed). */
function NextMoveCard({ canStart }: { canStart: boolean }) {
  return (
    <Panel className="panel-glass flex flex-col gap-3 p-5 sm:p-6">
      <span className="flex size-10 items-center justify-center rounded-full bg-primary/15">
        <PhoneCallIcon aria-hidden className="size-5 text-primary" />
      </span>
      <div className="flex flex-col gap-1">
        <h3 className="font-display text-h4 text-text">
          Place your first call
        </h3>
        <p className="text-small text-text-dim">
          Add contacts and start a run.
        </p>
      </div>
      {canStart ? (
        <Button asChild size="sm" className="mt-1 self-start">
          <Link href="/app/runs/new">Start a run</Link>
        </Button>
      ) : null}
    </Panel>
  );
}

function PageTitle({
  session,
  canStart,
}: {
  session: ReturnType<typeof useSession>;
  canStart: boolean;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex flex-col gap-1">
        <TeamControls session={session} />
      </div>
      <div className="flex items-center gap-2">
        {/* Relocated here from the sidebar footer - this header row (not a
            persistent top bar, which this product deliberately doesn't have)
            is the one place every page-level action already lives, so it's
            also the one reachable spot for a preference control without
            reintroducing a top bar just to hold it. Trade-off: only reachable
            from the Dashboard now, not every /app/* page. */}
        <ThemeToggle />
        <Button asChild variant="secondary">
          <Link href="/app/campaigns">Campaigns</Link>
        </Button>
        {canStart ? (
          <Button asChild>
            <Link href="/app/runs/new">Start a run</Link>
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Panel key={i} className="panel-glass flex flex-col gap-3 p-4">
            <Skeleton className="h-2.5 w-20" />
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-2.5 w-24" />
          </Panel>
        ))}
      </div>
      <Panel className="panel-glass flex flex-col gap-3 p-5">
        <Skeleton className="h-2.5 w-32" />
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-3 w-full" />
      </Panel>
    </div>
  );
}
