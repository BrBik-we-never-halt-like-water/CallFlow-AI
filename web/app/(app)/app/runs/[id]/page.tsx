"use client";

import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { LampStrip } from "@/components/brand/lamp-strip";
import { ConnectionBanner } from "@/components/app/connection-banner";
import { MaskedPhone } from "@/components/app/masked-phone";
import { TranscriptView } from "@/components/app/transcript-view";
import { LampBadge, Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogRoot } from "@/components/ui/dialog";
import { Sheet } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Eyebrow, Panel } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import type { Outcome } from "@/lib/api";
import { formatDuration, formatTimestamp } from "@/lib/format";
import { useProgressAnnouncement, useRunPoll } from "@/lib/hooks/use-run-poll";
import { countLamps, lampForOutcome, stripForRun } from "@/lib/lamp";
import { useAppStore } from "@/lib/app-store";

/**
 * The live run view.
 *
 * The lamp strip *is* the progress indicator   there is no progress bar. A bar says how
 * much is done; the strip says how it went, and on this screen the second question is
 * the one the operator actually has.
 */
export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = typeof params?.id === "string" ? params.id : null;
  const toast = useToast();
  const { phase, wakeSeconds, campaigns } = useAppStore();

  const [paused, setPaused] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [selected, setSelected] = useState<Outcome | null>(null);

  const { run, error, live, elapsed } = useRunPoll(runId, { paused });

  const settled = useMemo(
    () => (run ? run.outcomes.filter((o) => o.disposition !== "in_flight") : []),
    [run],
  );
  const lamps = useMemo(
    () => (run ? stripForRun(settled, run.total) : []),
    [run, settled],
  );
  const counts = useMemo(() => countLamps(lamps), [lamps]);

  const announcement = useProgressAnnouncement(counts.settled, run?.total ?? 0);
  const campaign = campaigns.find((c) => c.id === run?.campaign_id);

  // Newest first, with in-flight calls pinned to the top   an active call is the thing
  // the operator is most likely watching.
  const rows = useMemo(() => {
    if (!run) return [];
    return [...run.outcomes].sort((a, b) => {
      if (a.disposition === "in_flight" && b.disposition !== "in_flight") return -1;
      if (b.disposition === "in_flight" && a.disposition !== "in_flight") return 1;
      return b.created_at.localeCompare(a.created_at);
    });
  }, [run]);

  if (!run && phase !== "up") {
    return (
      <div className="flex flex-col gap-6">
        <ConnectionBanner phase={phase} wakeSeconds={wakeSeconds} />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex flex-col gap-6">
        {error ? (
          <Panel>
            <EmptyState
              title="That run couldn't be loaded"
              body={error}
              action={
                <Button variant="secondary" onClick={() => window.location.reload()}>
                  Try again
                </Button>
              }
            />
          </Panel>
        ) : (
          <>
            <Skeleton className="h-8 w-64" />
            <Panel className="flex flex-col gap-3 p-5">
              <Skeleton className="h-2.5 w-32" />
              <Skeleton className="h-4 w-full" />
            </Panel>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* ---- Header ------------------------------------------------------ */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <Eyebrow>Run</Eyebrow>
          <h1 className="font-display text-h2 text-text">
            {campaign?.name ?? run.campaign_id}
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-data text-text-mute">{run.id}</span>
            {run.dry_run ? <Tag>Dry run</Tag> : null}
            <Tag>{run.status}</Tag>
            <span className="font-mono text-data text-text-mute">
              {formatTimestamp(run.started_at)}
            </span>
          </div>
        </div>

        {/* Pause and Stop are always reachable while a run is live. */}
        {live ? (
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => setPaused((p) => !p)}>
              {paused ? "Resume updates" : "Pause run"}
            </Button>
            <Button variant="danger" onClick={() => setStopping(true)}>
              Stop run
            </Button>
          </div>
        ) : null}
      </div>

      {/* ---- Progress ---------------------------------------------------- */}
      <Panel
        className={cn(
          "flex flex-col gap-4 p-4 pl-4 sm:p-5",
          run.dry_run
            ? "border-l-2 border-l-[var(--lamp-ice)]"
            : "border-l-2 border-l-[var(--lamp-brass)]",
        )}
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <Eyebrow>{run.dry_run ? "Dry run · No credits spent" : "Live · Real calls"}</Eyebrow>
          {live ? (
            <span className="font-mono text-data tabular-nums text-text-mute">
              {formatDuration(elapsed)} elapsed
            </span>
          ) : null}
        </div>

        {/* Cold start: lamps in sequence, captioned. Never a spinner. */}
        {run.outcomes.length === 0 && live ? (
          <div className="flex flex-col gap-2">
            <LampStrip
              lamps={Array.from({ length: Math.min(run.total, 12) }, (_, i) => ({
                state: i < (Math.floor(elapsed * 1.5) % 13) ? ("brass" as const) : ("off" as const),
                label: "Starting",
              }))}
              size="md"
            />
            <p className="font-mono text-data text-text-dim">Waking the service…</p>
          </div>
        ) : (
          <LampStrip lamps={lamps} size="md" wrap counts />
        )}

        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-rule pt-3">
          <span className="font-mono text-data tabular-nums text-text">
            {counts.settled} of {run.total} settled
          </span>
          {paused ? (
            <span className="font-mono text-data text-lamp-brass-text">
              Updates paused   the run itself is still going
            </span>
          ) : null}
        </div>

        {/* One debounced announcement, not one per row. */}
        <p aria-live="polite" className="sr-only">
          {announcement}
        </p>

        {run.error ? (
          <p className="border-t border-rule pt-3 font-mono text-data text-lamp-flare-text">
            {run.error}
          </p>
        ) : null}
      </Panel>

      {/* ---- Results ----------------------------------------------------- */}
      <Panel className="flex flex-col gap-4 p-4 sm:p-5">
        <Eyebrow>Results</Eyebrow>

        {rows.length === 0 ? (
          <EmptyState
            title="Nothing has settled yet"
            body="Results appear here as each call ends. Nothing is lost while you wait."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-2xl border-collapse text-left">
              <caption className="sr-only">
                Results for this run, newest first. {countsSentence(counts)}
              </caption>
              <thead className="bg-surface-sunken">
                <tr className="border-b border-rule">
                  <th scope="col" className="eyebrow px-3 py-2 text-text-mute">
                    Outcome
                  </th>
                  <th scope="col" className="eyebrow px-3 py-2 text-text-mute">
                    Contact
                  </th>
                  <th scope="col" className="eyebrow px-3 py-2 text-text-mute">
                    Number
                  </th>
                  <th scope="col" className="eyebrow px-3 py-2 text-right text-text-mute">
                    Duration
                  </th>
                  <th scope="col" className="eyebrow px-3 py-2 text-text-mute">
                    Summary
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((outcome, i) => {
                  const lamp = lampForOutcome(outcome);
                  return (
                    <tr
                      key={`${outcome.contact_name}-${i}`}
                      onClick={() => setSelected(outcome)}
                      // Fade in, no transform: a new row must not shift the rows below it.
                      className="row-enter h-11 cursor-pointer border-b border-rule transition-colors last:border-0 hover:bg-surface-sunken"
                    >
                      <td className="px-3 py-2">
                        <LampBadge state={lamp.state} pulse={lamp.pulse}>
                          {lamp.label}
                        </LampBadge>
                      </td>
                      <td className="px-3 py-2 text-small text-text">{outcome.contact_name}</td>
                      <td className="px-3 py-2">
                        <MaskedPhone phone={outcome.phone_masked} />
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-data tabular-nums text-text-mute">
                        {formatDuration(outcome.duration_seconds)}
                      </td>
                      <td className="max-w-md truncate px-3 py-2 text-small text-text-dim">
                        {outcome.summary ?? outcome.disposition_reason ?? " "}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* ---- Transcript sheet -------------------------------------------- */}
      <DialogRoot open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        {selected ? (
          <Sheet title={selected.contact_name} description={`Run ${run.id}`}>
            <TranscriptView outcome={selected} />
          </Sheet>
        ) : null}
      </DialogRoot>

      {/* ---- Stop confirmation ------------------------------------------- */}
      <DialogRoot open={stopping} onOpenChange={setStopping}>
        <Dialog
          title="Stop this run?"
          description="Calls already placed keep their results. Contacts not yet reached will not be called."
          size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setStopping(false)}>
                Keep running
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  setStopping(false);
                  setPaused(true);
                  // The service has no stop endpoint yet, so say what actually happened
                  // rather than claiming the run was stopped.
                  toast({
                    tone: "warning",
                    title: "Updates stopped, run not cancelled",
                    body: "This deployment can't cancel a run in progress. Remaining calls will still be placed.",
                  });
                }}
              >
                Stop run
              </Button>
            </>
          }
        />
      </DialogRoot>
    </div>
  );
}

function countsSentence(counts: ReturnType<typeof countLamps>): string {
  return `${counts.closed} closed, ${counts.retry} queued for retry, ${counts.needsPerson} need a person.`;
}
