'use client';

import { useParams } from 'next/navigation';
import { useMemo, useState } from 'react';
import {
  ClockIcon,
  HashIcon,
  PhoneIcon,
  QuotesIcon,
} from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/cn';
import { LampStrip } from '@/components/brand/lamp-strip';
import { ConnectionBanner } from '@/components/app/connection-banner';
import { MaskedPhone } from '@/components/app/masked-phone';
import { TranscriptView } from '@/components/app/transcript-view';
import { LampBadge, Tag } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import { api, type Outcome } from '@/lib/api';
import { formatDuration, formatTimestamp } from '@/lib/format';
import { useProgressAnnouncement, useRunPoll } from '@/lib/hooks/use-run-poll';
import {
  countLamps,
  lampForOutcome,
  lampForRunStatus,
  stripForRun,
} from '@/lib/lamp';
import { useAppStore } from '@/lib/app-store';
import { useToast } from '@/components/ui/toast';
import { useSession } from '@/lib/hooks/use-session';
import { PageHeader } from '@/components/app/page-header';

/**
 * The live run view.
 *
 * The lamp strip *is* the progress indicator - there is no progress bar. A bar says how
 * much is done; the strip says how it went, and on this screen the second question is
 * the one the operator actually has.
 *
 * A completed call opens as a centered dialog, not a side sheet: the transcript and its
 * result sit side by side (`TranscriptView`'s own two-column layout), and that pairing
 * reads best with room on both sides rather than pinned to one edge of the screen.
 */
export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = typeof params?.id === 'string' ? params.id : null;
  const { phase } = useAppStore();

  const toast = useToast();
  const session = useSession();
  const [paused, setPaused] = useState(false);
  const [selected, setSelected] = useState<Outcome | null>(null);
  const [confirmingStop, setConfirmingStop] = useState(false);
  const [stopping, setStopping] = useState(false);

  const { run, error, live, elapsed, refresh } = useRunPoll(runId, { paused });

  // Whoever may start a run may stop one. The server enforces the same rule
  // plus ownership (an operator can only stop their own); this just keeps the
  // button off a screen where pressing it would always be refused.
  const canStop =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('runs:start');

  async function stopRun() {
    if (!runId) return;
    setStopping(true);
    try {
      const result = await api.stopRun(runId);
      setConfirmingStop(false);
      toast({
        tone: 'success',
        title: 'Run stopping',
        body:
          result.not_yet_dialled > 0
            ? `${result.not_yet_dialled} ${result.not_yet_dialled === 1 ? 'contact' : 'contacts'} won't be dialled. Calls already in progress will finish.`
            : 'Every contact had already been dialled. Calls in progress will finish.',
      });
      // Pull the new state now rather than waiting up to 2.5s for the next
      // tick - the button has to stop offering an action it already took.
      refresh();
    } catch (e) {
      toast({
        tone: 'error',
        title: "That run wasn't stopped",
        body: e instanceof Error ? e.message : 'The service did not respond.',
      });
    } finally {
      setStopping(false);
    }
  }

  const settled = useMemo(
    () =>
      run ? run.outcomes.filter((o) => o.disposition !== 'in_flight') : [],
    [run],
  );
  const lamps = useMemo(
    () => (run ? stripForRun(settled, run.total) : []),
    [run, settled],
  );
  const counts = useMemo(() => countLamps(lamps), [lamps]);

  const announcement = useProgressAnnouncement(counts.settled, run?.total ?? 0);
  // Carried on the run and resolved server-side; a run whose agent was
  // removed still has to render.
  const agentName = run?.agent_name ?? null;

  // Newest first, with in-flight calls pinned to the top - an active call is the thing
  // the operator is most likely watching.
  const rows = useMemo(() => {
    if (!run) return [];
    return [...run.outcomes].sort((a, b) => {
      if (a.disposition === 'in_flight' && b.disposition !== 'in_flight')
        return -1;
      if (b.disposition === 'in_flight' && a.disposition !== 'in_flight')
        return 1;
      return b.created_at.localeCompare(a.created_at);
    });
  }, [run]);

  if (!run && phase !== 'up') {
    return (
      <div className="flex flex-col gap-6">
        <ConnectionBanner phase={phase} />
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
                <Button
                  variant="secondary"
                  onClick={() => window.location.reload()}
                >
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

  const runLamp = lampForRunStatus(run.status, run.stopping);
  const remaining = Math.max(0, run.total - counts.settled);

  return (
    <div className="flex flex-col gap-6">
      {/* ---- Header ------------------------------------------------------ */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <PageHeader title="Run" figure={agentName ?? undefined} />
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-mono text-data text-text-mute">{run.id}</span>
            <span aria-hidden className="text-text-mute">
              ·
            </span>
            <LampBadge state={runLamp.state} pulse={runLamp.pulse}>
              {runLamp.label}
            </LampBadge>
            <span aria-hidden className="text-text-mute">
              ·
            </span>
            <span className="font-mono text-data text-text-mute">
              {formatTimestamp(run.started_at)}
            </span>
          </div>
        </div>

        {/* Two genuinely different actions, and the old interface had only one
            button doing neither clearly. "Pause run" stopped this screen
            polling and nothing else - it never touched a call, which the page
            had to explain in a comment nobody reading it could see. Now the
            wording matches what each one does: one stops the dialling, the
            other stops the updating. */}
        {live ? (
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => setPaused((p) => !p)}>
              {paused ? 'Resume updates' : 'Pause updates'}
            </Button>
            {canStop && !run.stopping ? (
              <Button variant="secondary" onClick={() => setConfirmingStop(true)}>
                Stop run
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>

      {/* ---- Progress ---------------------------------------------------- */}
      <Panel className="panel-enter flex flex-col gap-5 p-4 sm:p-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex items-end gap-3">
            <p className="dash-num text-[2.5rem] font-semibold leading-none text-text">
              {counts.settled}
            </p>
            <div className="flex flex-col pb-0.5">
              <span className="text-small font-bold text-text-mute">
                of {run.total} settled
              </span>
              <span className="text-small text-text-mute">Live · Real calls</span>
            </div>
          </div>

          {live ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-rule bg-surface-sunken px-2.5 py-1 font-mono text-data tabular-nums text-text-mute">
              <ClockIcon aria-hidden className="size-3.5" />
              {formatDuration(elapsed)} elapsed
            </span>
          ) : null}
        </div>

        {/* Before the first outcome lands: lamps in sequence, captioned. Never a spinner. */}
        {run.outcomes.length === 0 && live ? (
          <div className="flex flex-col gap-2">
            <LampStrip
              lamps={Array.from(
                { length: Math.min(run.total, 12) },
                (_, i) => ({
                  state:
                    i < Math.floor(elapsed * 1.5) % 13
                      ? ('brass' as const)
                      : ('off' as const),
                  label: 'Starting',
                }),
              )}
              size="md"
            />
            <p className="font-mono text-data text-text-dim">
              Dialling the first contacts…
            </p>
          </div>
        ) : (
          <LampStrip lamps={lamps} size="md" wrap counts />
        )}

        {paused ? (
          <p className="border-t border-rule pt-3 font-mono text-data text-lamp-brass-text">
            Updates paused - the run itself is still going
          </p>
        ) : null}

        {/* Says exactly what a stop did and did not do. Without this the run
            sits on "Stopping" with live calls still landing, and it looks like
            the button failed rather than like it is doing the one thing it
            promised. */}
        {run.stopping ? (
          <p className="border-t border-rule pt-3 text-small text-text-dim">
            <span className="font-medium text-text">Stopping.</span> No further
            contacts will be dialled
            {run.stopped_by_name ? ` - stopped by ${run.stopped_by_name}` : ''}.
            Calls already in conversation are being left to finish, and this run
            closes once they report back.
          </p>
        ) : null}

        {run.status === 'stopped' ? (
          <p className="border-t border-rule pt-3 text-small text-text-dim">
            This run was stopped
            {run.stopped_by_name ? ` by ${run.stopped_by_name}` : ''} before it
            reached every contact. Anyone not dialled is listed below with that
            reason.
          </p>
        ) : null}

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

      {/* ---- What this run was told -------------------------------------- */}
      {/* All three were persisted from the very first run and never read back,
          so a finished run could not be audited against its own instructions.
          `run_instruction` is the one that matters: it was appended to every
          prompt in the batch, and without it "why did they all say that?" has
          no answer. */}
      {run.name || run.run_instruction || run.numbers.length > 0 ? (
        <Panel
          className="panel-enter flex flex-col gap-4 p-4 sm:p-6"
          style={{ animationDelay: '60ms' }}
        >
          <p className="text-small font-bold text-text-mute">This run</p>

          <div className="grid gap-4 sm:grid-cols-2">
            {run.name ? (
              <InfoItem icon={HashIcon} label="Name">
                <p className="text-small text-text">{run.name}</p>
              </InfoItem>
            ) : null}

            {run.numbers.length > 0 ? (
              <InfoItem
                icon={PhoneIcon}
                label={
                  run.numbers.length === 1
                    ? 'Called from'
                    : `Called from ${run.numbers.length} numbers`
                }
              >
                <ul className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                  {run.numbers.map((number) => (
                    <li key={number.id} className="flex items-center gap-1.5">
                      <MaskedPhone phone={number.phone_masked} />
                      <span className="text-small text-text-mute">
                        {number.label ?? number.provider}
                      </span>
                      {/* A run is permanent and a number is not: a line retired
                          since this run still has to name itself here, and
                          saying it is retired is more useful than implying it is
                          still live. */}
                      {number.status !== 'verified' ? (
                        <Tag>{number.status}</Tag>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </InfoItem>
            ) : null}

            {run.run_instruction ? (
              <InfoItem
                icon={QuotesIcon}
                label="Added to every prompt"
                className="sm:col-span-2"
              >
                <blockquote className="measure border-l-2 border-rule pl-3 text-small text-text-dim">
                  {run.run_instruction}
                </blockquote>
              </InfoItem>
            ) : null}
          </div>
        </Panel>
      ) : null}

      {/* ---- Results ----------------------------------------------------- */}
      <Panel
        className="panel-enter flex flex-col gap-4 p-4 sm:p-6"
        style={{ animationDelay: '120ms' }}
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-small font-bold text-text-mute">Results</p>
          {rows.length > 0 && remaining > 0 ? (
            <span className="font-mono text-data text-text-mute">
              {remaining} still to come
            </span>
          ) : null}
        </div>

        {rows.length === 0 ? (
          <EmptyState
            title="Nothing has settled yet"
            body="Results appear here as each call ends. Nothing is lost while you wait."
          />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-rule">
            <table className="w-full min-w-2xl border-collapse text-left">
              <caption className="sr-only">
                Results for this run, newest first. {countsSentence(counts)}
              </caption>
              <thead className="bg-surface-sunken">
                <tr className="border-b border-rule">
                  <th
                    scope="col"
                    className="text-small font-bold px-3 py-2.5 text-text-mute"
                  >
                    Outcome
                  </th>
                  <th
                    scope="col"
                    className="text-small font-bold px-3 py-2.5 text-text-mute"
                  >
                    Contact
                  </th>
                  <th
                    scope="col"
                    className="text-small font-bold px-3 py-2.5 text-text-mute"
                  >
                    Number
                  </th>
                  <th
                    scope="col"
                    className="text-small font-bold px-3 py-2.5 text-right text-text-mute"
                  >
                    Duration
                  </th>
                  <th
                    scope="col"
                    className="text-small font-bold px-3 py-2.5 text-text-mute"
                  >
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
                      className="row-enter group h-12 cursor-pointer border-b border-rule transition-colors last:border-0 hover:bg-surface-sunken"
                    >
                      <td className="px-3 py-2">
                        <LampBadge state={lamp.state} pulse={lamp.pulse}>
                          {lamp.label}
                        </LampBadge>
                      </td>
                      <td className="px-3 py-2 text-small text-text">
                        {outcome.contact_name}
                      </td>
                      <td className="px-3 py-2">
                        <MaskedPhone phone={outcome.phone_masked} />
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-data tabular-nums text-text-mute">
                        {formatDuration(outcome.duration_seconds)}
                      </td>
                      <td className="max-w-md truncate px-3 py-2 text-small text-text-dim">
                        {outcome.summary ?? outcome.disposition_reason ?? '-'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* ---- Stop confirmation ------------------------------------------- */}
      {/* Confirmed rather than immediate, because it cannot be undone: there is
          no resume, and the contacts it skips are only reachable again by
          starting a new run. The copy states both halves of what happens, since
          "stop" reasonably reads as "hang up on everyone" and that is exactly
          what it does not do. */}
      <DialogRoot open={confirmingStop} onOpenChange={setConfirmingStop}>
        <Dialog
          title="Stop this run?"
          description={`${remaining} of ${run.total} contacts have not been dialled yet.`}
          footer={
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() => setConfirmingStop(false)}
              >
                Keep dialling
              </Button>
              <Button loading={stopping} onClick={() => void stopRun()}>
                Stop run
              </Button>
            </div>
          }
        >
          <div className="flex flex-col gap-3 text-small text-text-dim">
            <p>
              Dialling stops immediately. Anyone not yet called is recorded as
              not dialled, so this run&apos;s numbers stay honest.
            </p>
            <p>
              <span className="font-medium text-text">
                Calls already in conversation are not cut off.
              </span>{' '}
              They finish naturally and their transcripts and results arrive as
              usual. The run closes once the last one reports back.
            </p>
            <p>This cannot be undone - a stopped run cannot be resumed.</p>
          </div>
        </Dialog>
      </DialogRoot>

      {/* ---- Call detail --------------------------------------------------
          A centered dialog, not a side sheet - `TranscriptView` is a two-column
          layout (conversation next to its own result), and that pairing reads
          best with room on both sides rather than pinned to one edge, where the
          conversation column would forever be the narrower of the two. `size="full"`
          is the record-inspection size `Dialog` was built for. */}
      <DialogRoot
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        {selected ? (
          <Dialog
            size="full"
            title={selected.contact_name}
            description={`Run ${run.id}`}
          >
            <TranscriptView outcome={selected} />
          </Dialog>
        ) : null}
      </DialogRoot>
    </div>
  );
}

function InfoItem({
  icon: IconComponent,
  label,
  children,
  className,
}: {
  icon: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }>;
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <p className="flex items-center gap-1.5 text-small font-bold text-text-mute">
        <IconComponent aria-hidden className="size-3.5" />
        {label}
      </p>
      {children}
    </div>
  );
}

function countsSentence(counts: ReturnType<typeof countLamps>): string {
  return `${counts.closed} closed, ${counts.retry} queued for retry, ${counts.needsPerson} need a person.`;
}
