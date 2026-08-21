'use client';

import { useMemo, useState } from 'react';
import { ActivityTable, type ActivityRow, type ActivityTab } from './activity-table';
import { CallsChart, type MonthPoint } from './calls-chart';
import { CallsHeatmap, type DayCount } from './calls-heatmap';
import { CreditsCard } from './credits-card';
import { CyclingKpiCard, KpiCard, type Metric } from './kpi-cards';
import { AgentsPanel, RunsPanel } from './list-panels';
import {
  canSeeTeam,
  scopeOptions,
  type Scope,
  type SessionProfileLike,
} from './scope';
import type {
  Escalation,
  Outcome,
  RunSummary,
  TeamPerformance,
  VoiceAgent,
} from '@/lib/api';

/**
 * The dashboard: ten regions in one viewport, nothing but the panels
 * themselves scrolling.
 *
 * The grid is fixed-height by construction rather than by `height: 100vh`
 * on a wrapper - each row is sized in `grid-template-rows`, every panel is
 * `min-h-0`, and the panels scroll internally. That is what keeps a busy
 * organisation and an empty one rendering the same page.
 *
 * Three widths: sixteen columns at `xl`, two at `lg`, one below that - where
 * the grid relaxes and the page scrolls normally. Ten fixed panels in 950px
 * is right for a desktop operator and unreadable on a laptop half that tall;
 * forcing it would mean ten unreadable slivers.
 */
/** Calendar order, so derived months sort correctly rather than by count. */
const MONTH_ORDER = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function Dashboard({
  profile,
  members,
  runs,
  agents,
  outcomes,
  escalations,
  monthlyCalls,
  dailyCalls,
  loading,
}: {
  profile: SessionProfileLike | null;
  members: TeamPerformance[] | null;
  runs: RunSummary[] | null;
  agents: VoiceAgent[] | null;
  outcomes: Outcome[] | null;
  escalations: Escalation[] | null;
  /** Null until an endpoint backs it - the chart says so rather than guessing. */
  monthlyCalls: MonthPoint[] | null;
  /** Null until an endpoint backs it - see `monthlyCalls`. */
  dailyCalls: DayCount[] | null;
  loading: boolean;
}) {
  // `all` where the role can see the team, `mine` where it cannot - a role
  // without `runs:read_team` is never offered `all`, so defaulting to it
  // blindly would leave the trigger showing a value absent from its own menu.
  //
  // Tracked as "has the user chosen yet" rather than seeded once, because
  // `profile` is null on the first render: seeding from it would freeze the
  // default at `mine` for everyone, since the session only arrives later.
  const teamVisible = canSeeTeam(profile);
  const defaultScope: Scope = teamVisible ? 'all' : 'mine';
  const [chartScope, setChartScope] = useState<Scope | null>(null);
  const [runScope, setRunScope] = useState<Scope | null>(null);
  const [agentScope, setAgentScope] = useState<Scope | null>(null);
  const [tab, setTab] = useState<ActivityTab>('all');
  const [month, setMonth] = useState('current');
  // Years the loaded outcomes actually span, newest first - not a fixed
  // range, so the menu never offers a year with nothing in it. Falls back to
  // the current year before any data arrives.
  const years = useMemo(() => {
    const seen = new Set<string>();
    for (const row of outcomes ?? []) {
      if (!row.created_at) continue;
      const date = new Date(row.created_at);
      if (!Number.isNaN(date.getTime())) seen.add(String(date.getFullYear()));
    }
    if (seen.size === 0) seen.add(String(new Date().getFullYear()));
    return [...seen].sort().reverse();
  }, [outcomes]);

  const [year, setYear] = useState<string | null>(null);

  // One list for every selector on the page - Mine, All, then each teammate
  // by name. Built once here rather than per panel so the three controls can
  // never drift out of step with each other.
  const options = useMemo(
    () => scopeOptions(profile, members),
    [profile, members],
  );

  const callMetrics = useMemo<Metric[]>(() => {
    const rows = outcomes ?? [];
    const completed = rows.filter((row) => row.status === 'completed').length;
    const retried = rows.filter((row) => row.status === 'retried').length;
    return [
      {
        label: 'Calls placed today',
        labelLines: ['Calls placed', 'Today'],
        value: rows.length,
      },
      { label: 'Completed', value: completed },
      { label: 'Retried', value: retried },
    ];
  }, [outcomes]);

  const openEscalations = (escalations ?? []).filter(
    (row) => row.escalation_status === 'open',
  ).length;

  const runCalls = (runs ?? []).reduce((total, run) => total + run.total, 0);

  // Derived from the outcomes already loaded rather than left empty. There
  // is still no time-series endpoint (§ the page's own note), so this covers
  // only the calls the dashboard has in hand - honest for "what happened
  // recently", not a billing-grade history. When an endpoint exists, both of
  // these become props again and this goes away.
  // Who started each run, so an outcome can be attributed to a person: an
  // `Outcome` carries only its `run_id`, and the run is what records who
  // started it.
  const runOwner = useMemo(
    () => new Map((runs ?? []).map((run) => [run.id, run.started_by])),
    [runs],
  );

  const derivedMonthly = useMemo<MonthPoint[] | null>(() => {
    const rows = outcomes ?? [];
    if (rows.length === 0) return null;

    const wanted = chartScope ?? defaultScope;
    const byMonth = new Map<string, { placed: number; completed: number }>();
    for (const row of rows) {
      // `all` is every row; `mine` is the signed-in user's; anything else is
      // a teammate's own user id, picked from the same menu.
      if (wanted !== 'all') {
        const owner = row.run_id ? runOwner.get(row.run_id) : null;
        const target = wanted === 'mine' ? profile?.user_id : wanted;
        if (!owner || owner !== target) continue;
      }
      if (!row.created_at) continue;
      const date = new Date(row.created_at);
      if (Number.isNaN(date.getTime())) continue;
      const key = date.toLocaleString(undefined, { month: 'short' });
      const bucket = byMonth.get(key) ?? { placed: 0, completed: 0 };
      bucket.placed += 1;
      if (row.disposition === 'auto_closed') bucket.completed += 1;
      byMonth.set(key, bucket);
    }

    return MONTH_ORDER.map((month) => ({
      month,
      ...(byMonth.get(month) ?? { placed: 0, completed: 0 }),
    }));
  }, [outcomes, chartScope, defaultScope, runOwner, profile]);

  const derivedDaily = useMemo<DayCount[] | null>(() => {
    const rows = outcomes ?? [];
    if (rows.length === 0) return null;

    const byDay = new Map<string, number>();
    for (const row of rows) {
      if (!row.created_at) continue;
      const date = new Date(row.created_at);
      if (Number.isNaN(date.getTime())) continue;
      const key = date.toISOString().slice(0, 10);
      byDay.set(key, (byDay.get(key) ?? 0) + 1);
    }
    if (byDay.size === 0) return null;

    return [...byDay.entries()].map(([date, calls]) => ({ date, calls }));
  }, [outcomes]);

  const activityRows = useMemo<ActivityRow[]>(() => {
    // `Outcome` carries only `voice_agent_id`, so the name is resolved from
    // the agent list the dashboard already loads. The column previously
    // showed `contact_name` - the person who was *called*, not the agent
    // that called them, which made every row name the wrong party.
    const agentNames = new Map(
      (agents ?? []).map((agent) => [agent.id, agent.name]),
    );

    const fromOutcomes = (outcomes ?? []).map((row, index) => ({
      id: `outcome-${row.provider_call_id ?? index}`,
      category:
        row.status === 'completed'
          ? ('completed' as const)
          : ('runs' as const),
      caller: row.contact_name,
      contact: row.phone_masked,
      agent: row.voice_agent_id ? (agentNames.get(row.voice_agent_id) ?? null) : null,
      run: row.run_id,
      status: row.status,
    }));

    const fromEscalations = (escalations ?? [])
      .filter((row) => row.escalation_status === 'open')
      .map((row) => ({
        id: `escalation-${row.id}`,
        category: 'needs_person' as const,
        caller: row.contact_name,
        contact: row.phone_masked,
        agent: row.agent_name,
        run: row.run_id,
        status: 'needs_person',
      }));

    return [...fromEscalations, ...fromOutcomes];
  }, [outcomes, escalations, agents]);

  return (
    <div
      className={[
        'dash-grid grid min-h-0 gap-3 px-3 pb-0 pt-2.5',
        'grid-cols-1',
        // `fr` rows need a *definite* grid height to resolve against. As a
        // plain flex child the grid's height stays `auto` no matter how
        // bounded its parent is, so every row sizes to its content and the
        // whole grid runs past the screen - `flex-1` is not a substitute
        // here. The explicit height is what makes the track sizing work.
        //
        // Only `xl` gets it. Two columns at `lg` puts the ten panels in six
        // rows, and six rows in 950px leaves every panel too short to read -
        // so `lg` keeps content-sized rows and lets the page scroll.
        'lg:grid-cols-2',
        // Sixteen columns, so the left/right split can sit off-centre: the
        // left stack (credits, counts, runs) takes 7/16 and the analytics
        // column 9/16. Eight columns could only express an even half.
        'xl:h-[calc(100dvh-var(--dash-chrome))] xl:[grid-template-columns:repeat(16,minmax(0,1fr))]',
        // Three rows. Row 1: credits, the 2x2 counts, and the chart. Row 2:
        // runs and agents on the left half, the heatmap on the right - same
        // footprint as the chart above it. Row 3: the activity table, full
        // width.
        'xl:[grid-template-rows:minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.62fr)]',
      ].join(' ')}
    >
      {/* Row 1 - credits, the four counts, and the chart. */}
      <CreditsCard
        members={members}
        outcomes={outcomes}
        loading={loading}
        className="lg:col-span-1 lg:row-start-1 xl:[grid-column:1/4] xl:row-start-1"
      />

      <div className="grid grid-cols-2 grid-rows-2 gap-3 lg:col-span-1 lg:row-start-1 xl:[grid-column:4/8] xl:row-start-1">
        <CyclingKpiCard metrics={callMetrics} />
        <KpiCard
          metric={{
            label: 'Needs a person',
            labelLines: ['Needs a', 'Person'],
            value: escalations === null ? null : openEscalations,
          }}
        />
        <KpiCard
          metric={{
            label: 'Run calls',
            value: runs === null ? null : runCalls,
          }}
        />
        <KpiCard
          metric={{
            label: 'Agents',
            value: agents === null ? null : agents.length,
          }}
        />
      </div>

      <CallsChart
        data={monthlyCalls ?? derivedMonthly}
        scope={chartScope ?? defaultScope}
        onScopeChange={setChartScope}
        scopeOptions={options}
        className="min-h-[220px] lg:col-span-1 xl:[grid-column:8/17] xl:row-start-1 xl:min-h-0"
      />
      <CallsHeatmap
        data={dailyCalls ?? derivedDaily}
        year={year ?? years[0]}
        onYearChange={setYear}
        yearOptions={years.map((value) => ({ value, label: value }))}
        className="min-h-[220px] lg:col-span-1 xl:[grid-column:8/17] xl:row-start-2 xl:min-h-0"
      />

      {/* Row 2 - runs and agents on the left half; the heatmap on the right
          shares the chart's footprint exactly. */}
      <RunsPanel
        runs={runs}
        loading={loading}
        scope={runScope ?? defaultScope}
        onScopeChange={setRunScope}
        scopeOptions={options}
        className="min-h-[260px] lg:col-span-1 xl:[grid-column:1/4] xl:row-start-2 xl:min-h-0"
      />
      <AgentsPanel
        agents={agents}
        loading={loading}
        scope={agentScope ?? defaultScope}
        onScopeChange={setAgentScope}
        scopeOptions={options}
        className="min-h-[260px] lg:col-span-1 xl:[grid-column:4/8] xl:row-start-2 xl:min-h-0"
      />

      {/* Row 3 - the activity table, full width. */}
      <ActivityTable
        rows={activityRows}
        loading={loading}
        tab={tab}
        onTabChange={setTab}
        month={month}
        onMonthChange={setMonth}
        monthOptions={[{ value: 'current', label: 'This month' }]}
        className="min-h-[280px] lg:col-span-2 xl:[grid-column:1/17] xl:row-start-3 xl:min-h-0"
      />
    </div>
  );
}
