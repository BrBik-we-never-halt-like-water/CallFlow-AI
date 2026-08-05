"use client";

import { ArrowRightIcon, PhoneSlashIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { LampStrip } from "@/components/brand/lamp-strip";
import { ConnectionBanner } from "@/components/app/connection-banner";
import { EscalationCard } from "@/components/app/escalation-card";
import { MaskedPhone } from "@/components/app/masked-phone";
import { LampBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Eyebrow, Panel } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { Sparkline, Stat } from "@/components/ui/stat";
import { formatAge, formatDuration, formatPercent, formatTimestamp } from "@/lib/format";
import { lampForOutcome } from "@/lib/lamp";
import { useAppStore } from "@/lib/app-store";
import { FirstRunChecklist } from "./first-run-checklist";

/** The strip shows the most recent calls. 100 is the design's stated window. */
const STRIP_WINDOW = 100;

export default function OverviewPage() {
  const router = useRouter();
  const { phase, wakeSeconds, outcomes, runs, escalations, loadingRuns, campaigns } =
    useAppStore();

  const settled = useMemo(
    () => outcomes.filter((o) => o.disposition !== "in_flight"),
    [outcomes],
  );

  const recent = useMemo(() => settled.slice(0, STRIP_WINDOW), [settled]);
  const lamps = useMemo(() => recent.map(lampForOutcome), [recent]);

  const avgDuration = useMemo(() => {
    const withDuration = settled.filter((o) => o.duration_seconds != null);
    if (withDuration.length === 0) return null;
    return (
      withDuration.reduce((sum, o) => sum + (o.duration_seconds ?? 0), 0) /
      withDuration.length
    );
  }, [settled]);

  const autoClosedPct =
    settled.length > 0
      ? (settled.filter((o) => o.disposition === "auto_closed").length / settled.length) * 100
      : null;

  // Seven buckets of calls per day, oldest first. Derived from real timestamps rather
  // than invented, so an account with no history gets no sparkline at all.
  const sparkline = useMemo(() => {
    if (settled.length === 0) return [];
    // Anchored to the most recent result rather than to `Date.now()`, which would
    // be an impure read during render. Buckets follow the data, not the clock.
    const now = new Date(settled[0].created_at).getTime();
    const day = 86_400_000;
    return Array.from({ length: 7 }, (_, i) => {
      const from = now - (6 - i + 1) * day;
      const to = now - (6 - i) * day;
      return settled.filter((o) => {
        const at = new Date(o.created_at).getTime();
        return at >= from && at < to;
      }).length;
    });
  }, [settled]);

  const hasAnything = settled.length > 0 || runs.length > 0;

  if (phase !== "up" && !hasAnything) {
    return (
      <div className="flex flex-col gap-6">
        <PageTitle />
        <ConnectionBanner phase={phase} wakeSeconds={wakeSeconds} />
        {phase !== "down" ? <LoadingSkeleton /> : null}
      </div>
    );
  }

  // The empty dashboard is an onboarding surface, not a blank grid.
  if (!loadingRuns && !hasAnything) {
    return (
      <div className="flex flex-col gap-6">
        <PageTitle />
        <FirstRunChecklist hasCampaigns={campaigns.length > 0} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PageTitle />
      <ConnectionBanner phase={phase} wakeSeconds={wakeSeconds} />

      {/* ---- Stats ------------------------------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Calls this month"
          value={settled.length}
          detail={`${runs.length} ${runs.length === 1 ? "run" : "runs"}`}
          sparkline={
            sparkline.length > 0 ? (
              <Sparkline values={sparkline} label="Calls per day over the last week" />
            ) : undefined
          }
        />
        <Stat
          label="Auto-closed"
          value={autoClosedPct == null ? "—" : formatPercent(autoClosedPct)}
          detail="closed without a person"
          lamp={autoClosedPct != null ? "jade" : undefined}
        />
        <Stat
          label="Needs a person"
          value={escalations.length}
          detail={escalations.length > 0 ? "oldest first" : "nothing waiting"}
          lamp={escalations.length > 0 ? "flare" : undefined}
        />
        <Stat
          label="Average call"
          value={formatDuration(avgDuration)}
          detail="connected time"
        />
      </div>

      {/* ---- Outcome distribution: the page's visual anchor -------------- */}
      <Panel className="flex flex-col gap-4 p-4 sm:p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div className="flex flex-col gap-1">
            <Eyebrow>Outcome distribution</Eyebrow>
            <h2 className="font-display text-h3 text-text">
              The last {Math.min(settled.length, STRIP_WINDOW)}{" "}
              {settled.length === 1 ? "call" : "calls"}
            </h2>
          </div>
          <p className="font-mono text-data text-text-mute">Click a lamp to open the call</p>
        </div>

        {recent.length === 0 ? (
          <EmptyState
            icon={PhoneSlashIcon}
            title="Nothing has been dialled yet"
            body="Add a few contacts and run a campaign in dry mode. It costs nothing and shows you exactly what would happen."
            action={
              <Button asChild>
                <Link href="/app/runs/new">Start a run</Link>
              </Button>
            }
          />
        ) : (
          <LampStrip
            lamps={lamps}
            size="md"
            wrap
            counts
            onSelect={(index) => {
              const outcome = recent[index];
              if (outcome?.run_id) router.push(`/app/runs/${outcome.run_id}`);
            }}
          />
        )}
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        {/* ---- Needs a person preview ----------------------------------- */}
        <Panel className="flex flex-col gap-4 p-4 sm:p-5">
          <div className="flex items-center justify-between gap-2">
            <Eyebrow>Needs a person</Eyebrow>
            {escalations.length > 0 ? (
              <Link
                href="/app/escalations"
                className="inline-flex items-center gap-1 text-small font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
              >
                See all {escalations.length}
                <ArrowRightIcon aria-hidden className="size-3.5" />
              </Link>
            ) : null}
          </div>

          {escalations.length === 0 ? (
            <EmptyState
              title="Nothing needs you right now"
              body="Escalations land here when someone sounds frustrated, asks to opt out, or asks for a person."
            />
          ) : (
            <ul className="flex flex-col gap-3">
              {escalations.slice(0, 5).map((outcome, i) => (
                <li key={`${outcome.contact_name}-${i}`}>
                  <EscalationCard outcome={outcome} compact />
                </li>
              ))}
            </ul>
          )}
        </Panel>

        {/* ---- Recent runs ---------------------------------------------- */}
        <Panel className="flex flex-col gap-4 p-4 sm:p-5">
          <div className="flex items-center justify-between gap-2">
            <Eyebrow>Recent runs</Eyebrow>
            <Link
              href="/app/runs"
              className="inline-flex items-center gap-1 text-small font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
            >
              All runs
              <ArrowRightIcon aria-hidden className="size-3.5" />
            </Link>
          </div>

          {runs.length === 0 ? (
            <EmptyState
              title="No runs yet"
              body="Runs are how contacts get called. Start one in dry mode to see the pipeline end to end."
              action={
                <Button asChild size="sm">
                  <Link href="/app/runs/new">Start a run</Link>
                </Button>
              }
            />
          ) : (
            <ul className="flex flex-col">
              {runs.slice(0, 5).map((run) => (
                <li key={run.id} className="border-b border-rule last:border-0">
                  <Link
                    href={`/app/runs/${run.id}`}
                    className="-mx-2 flex items-center gap-3 rounded-sm px-2 py-2.5 transition-colors hover:bg-surface-hover"
                  >
                    <span className="min-w-0 flex-1 truncate text-small text-text">
                      {run.campaign_id}
                    </span>
                    {run.dry_run ? <LampBadge state="ice">Dry run</LampBadge> : null}
                    <span className="font-mono text-data tabular-nums text-text-mute">
                      {run.completed}/{run.total}
                    </span>
                    <span className="hidden font-mono text-data text-text-mute sm:inline">
                      {formatTimestamp(run.started_at)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      {/* ---- Latest results ---------------------------------------------- */}
      {settled.length > 0 ? (
        <Panel className="flex flex-col gap-4 p-4 sm:p-5">
          <Eyebrow>Latest results</Eyebrow>
          <ul className="flex flex-col">
            {settled.slice(0, 6).map((outcome, i) => {
              const lamp = lampForOutcome(outcome);
              return (
                <li
                  key={`${outcome.contact_name}-${i}`}
                  className="flex flex-wrap items-center gap-3 border-b border-rule py-2.5 last:border-0"
                >
                  <LampBadge state={lamp.state} pulse={lamp.pulse}>
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

function PageTitle() {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="flex flex-col gap-1">
        <Eyebrow>Overview</Eyebrow>
        <h1 className="font-display text-h2 text-text">How the calling is going</h1>
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
