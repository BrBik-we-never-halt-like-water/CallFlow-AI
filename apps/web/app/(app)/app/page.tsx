'use client';

import {
  PhoneSlashIcon,
  PhoneCallIcon,
  PlusIcon,
} from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { Lamp } from '@/components/brand/lamp';
import { ConnectionBanner } from '@/components/app/connection-banner';
import { EscalationCard } from '@/components/app/escalation-card';
import { InviteDialog } from '@/components/app/invite-dialog';
import { MaskedPhone } from '@/components/app/masked-phone';
import { TeamControls } from '@/components/app/overview-org-section';
import { AreaChart } from '@/components/ui/area-chart';
import { LampBadge, Tag } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import { formatAge, formatDuration } from '@/lib/format';
import { countLamps, lampForOutcome, type LampState } from '@/lib/lamp';
import { api, type Team } from '@/lib/api';
import { useAppStore } from '@/lib/app-store';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession } from '@/lib/hooks/use-session';

/**
 * The bottom-right grid slot (Twisty's "Proposal Progress") is a stat-trio,
 * not a donut — three columns divided by a hairline, each a count over a
 * label, matching that slot's own proportions better than a circle does.
 * Deliberately just these three, in this order: the two states that need a
 * decision (a person, or another try) before the one that's already settled.
 * `off`/"Skipped" still exists as data — it's just not one of
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

export default function OverviewPage() {
  const session = useSession();
  const { phase, outcomes, runs, campaigns, escalations, loadingRuns } =
    useAppStore();
  const canInvite =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('team:invite');

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

  // Skeleton while there's nothing to show yet — connecting, or runs still loading.
  // Once real data exists, never fall back to this, even on a background refetch.
  if ((phase !== 'up' || loadingRuns) && !hasAnything) {
    return (
      <div className="flex flex-col gap-6">
        <PageTitle session={session} />
        <ConnectionBanner phase={phase} />
        {phase !== 'down' ? <LoadingSkeleton /> : null}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PageTitle session={session} />
      <ConnectionBanner phase={phase} />

      {/* ---- The Twisty-mapped grid: ~60/40, left column a hero chart over
          two secondary cards, right column a taller list over a stat-trio —
          same slots, same proportions, our own cards and data. ------------ */}
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        {/* ================= Left column (~60%) ================= */}
        <div className="flex flex-col gap-6">
          <div className="hero-flow flex flex-col gap-3 p-5 sm:p-7">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-small font-bold text-text-mute">Volume, last 7 days</p>
              <span className="text-small tabular-nums text-text-mute">
                {runs.length} {runs.length === 1 ? 'run' : 'runs'}
              </span>
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
                {settled.length}
              </span>
              <span className="text-small text-text-dim">
                call{settled.length === 1 ? '' : 's'} settled this week
              </span>
            </div>
          </div>

          {/* ---- Team (55%) + next move (45%) ----------------------------
              `NextMoveCard` only has one message left ("place your first
              call") now that "bring in a teammate" — a second invite entry
              point duplicating `TeamPreview`'s own "+" — was retired. Once
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
            {runs.length > 0 ? null : <NextMoveCard />}
          </div>
        </div>

        {/* ================= Right column (~40%) ================= */}
        <div className="flex flex-col gap-6">
          {/* ---- Needs a person: taller, full right-column width -------- */}
          <Panel interactive className="flex flex-1 flex-col gap-4 p-5 sm:p-6">
            <div className="flex items-center justify-between gap-2">
              <p className="text-small font-bold text-text-mute">Needs a person</p>
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
                body="Escalations land here when someone sounds frustrated, asks to opt out, or asks for a person."
              />
            ) : (
              <ul className="flex flex-col">
                {escalations.slice(0, 5).map((outcome, i) => (
                  <li key={`${outcome.contact_name}-${i}`}>
                    <EscalationCard outcome={outcome} compact />
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {/* ---- Disposition, as a stat-trio ------------------------------
              Deviation, flagged per the brief: no sparkline under each
              number yet (there's no Sparkline component in this codebase
              to wire one from today — the brief's own accepted fallback for
              "more work than it's worth right now" is a resized donut; this
              goes one step further into the actual stat-trio shape since the
              layout cost of that was low, just without the sparkline detail). */}
          <Panel className="flex flex-col gap-4 p-5 sm:p-6">
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-small font-bold text-text-mute">Disposition</p>
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
                    <p className="truncate text-small font-bold text-text-mute">{item.label}</p>
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
          single lamp standing in for the whole distribution — at the volumes
          this page usually shows, one dot (or one donut slice) reads as far
          more definitive than the sample backing it. A zero count still
          renders, dimmed: "0 need a person" is real information. --------- */}
      <div className="signal-field rounded-xl">
        <Panel className="flex flex-col gap-5 p-5 sm:p-7">
          <div className="flex flex-col gap-1">
            <p className="text-small font-bold text-text-mute">Outcome distribution</p>
            <h2 className="font-display text-h3 text-text">
              The last {Math.min(settled.length, STRIP_WINDOW)}{' '}
              {settled.length === 1 ? 'call' : 'calls'}
            </h2>
          </div>

          {recent.length === 0 ? (
            <EmptyState
              icon={PhoneSlashIcon}
              title="Nothing has been dialled yet"
              body="Add a few contacts and start a run — results appear here as calls settle."
              action={
                <Button asChild>
                  <Link href="/app/runs/new">Start a run</Link>
                </Button>
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
      <Panel interactive className="flex flex-col gap-4 p-5 sm:p-6">
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
            body="Runs are how contacts get called. Start one to see the pipeline end to end."
            action={
              <Button asChild size="sm">
                <Link href="/app/runs/new">Start a run</Link>
              </Button>
            }
          />
        ) : (
          <ul className="flex flex-col">
            {runs.slice(0, 5).map((run) => {
              const name =
                campaigns.find((c) => c.id === run.campaign_id)?.name ??
                run.campaign_id;
              return (
                <li key={run.id} className="border-b border-rule last:border-0">
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

      {/* ---- Latest results ---------------------------------------------- */}
      {settled.length > 0 ? (
        <Panel className="flex flex-col gap-4 p-5 sm:p-6">
          <p className="text-small font-bold text-text-mute">Latest results</p>
          <ul className="flex flex-col">
            {settled.slice(0, 6).map((outcome, i) => {
              const lamp = lampForOutcome(outcome);
              return (
                <li
                  key={`${outcome.contact_name}-${i}`}
                  className="flex flex-wrap items-center gap-3 border-b border-rule py-3 last:border-0"
                >
                  <LampBadge
                    state={lamp.state}
                    pulse={lamp.pulse}
                    className="text-small"
                  >
                    {lamp.label}
                  </LampBadge>
                  <span className="min-w-0 flex-1 truncate text-small text-text">
                    {outcome.contact_name}
                  </span>
                  <MaskedPhone phone={outcome.phone_masked} />
                  <span className="font-mono text-data tabular-nums text-text-mute">
                    {formatDuration(outcome.duration_seconds)}
                  </span>
                  <span className="font-mono text-data text-text-mute">
                    {formatAge(outcome.created_at)}
                  </span>
                </li>
              );
            })}
          </ul>
        </Panel>
      ) : null}
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
 * count, and a label. A zero count still renders — dimmed to `off`, rather
 * than dropped — because "0 need a person" is real information worth seeing. */
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

/** Who's on this — a quiet counterpart to the run/escalation data around it. */
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
    <Panel className="flex flex-col gap-3 p-5 sm:p-6">
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

/** The one deliberately warmer card on the page — an invitation to the single
 * next action while there isn't one yet. Only rendered before the first run;
 * once any run exists, `TeamPreview` grows to fill this row instead (this
 * card's other message, "Bring in a teammate", was a second invite entry
 * point duplicating `TeamPreview`'s own "+" — retired, not repurposed). */
function NextMoveCard() {
  return (
    <div className="hero-flow flex flex-col gap-3 p-5 sm:p-6">
      <span className="flex size-10 items-center justify-center rounded-full bg-accent-wash">
        <PhoneCallIcon aria-hidden className="size-5 text-accent-text" />
      </span>
      <div className="flex flex-col gap-1">
        <h3 className="font-display text-h4 text-text">
          Place your first call
        </h3>
        <p className="text-small text-text-dim">
          Add a few contacts and start a run — this card turns into your weekly
          trend once one settles.
        </p>
      </div>
      <Button asChild size="sm" className="mt-1 self-start">
        <Link href="/app/runs/new">Start a run</Link>
      </Button>
    </div>
  );
}

function PageTitle({ session }: { session: ReturnType<typeof useSession> }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex flex-col gap-1">
        <TeamControls session={session} />
      </div>
      <div className="flex gap-2">
        <Button asChild variant="secondary">
          <Link href="/app/campaigns">Campaigns</Link>
        </Button>
        <Button asChild>
          <Link href="/app/runs/new">Start a run</Link>
        </Button>
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Panel key={i} className="flex flex-col gap-3 p-4">
            <Skeleton className="h-2.5 w-20" />
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-2.5 w-24" />
          </Panel>
        ))}
      </div>
      <Panel className="flex flex-col gap-3 p-5">
        <Skeleton className="h-2.5 w-32" />
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-3 w-full" />
      </Panel>
    </div>
  );
}
