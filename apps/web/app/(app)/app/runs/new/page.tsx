'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useMemo, useState } from 'react';
import {
  ArrowsClockwiseIcon,
  CheckCircleIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/cn';
import { ConnectionBanner } from '@/components/app/connection-banner';
import { ContactGrid } from '@/components/app/contact-grid';
import { NotWiredNotice } from '@/components/app/settings-section';
import { Button } from '@/components/ui/button';
import { Field } from '@/components/ui/field';
import { Input, Textarea } from '@/components/ui/input';
import { Panel } from '@/components/ui/panel';
import { Tooltip } from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/toast';
import { api, type TelephonyNumber, type VoiceAgent } from '@/lib/api';
import { useAppStore } from '@/lib/app-store';
import {
  contextColumns,
  toContactInputs,
  type ParsedRow,
} from '@/lib/contacts';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession } from '@/lib/hooks/use-session';

/**
 * The run composer: an agent, the number(s) it calls from, and a sheet.
 *
 * Four stacked steps on one page, not a wizard. Someone starting their fifth run
 * of the day should be able to see everything at once and change any of it - a
 * wizard makes the second run as slow as the first.
 *
 * The number is chosen here rather than on the agent, which is what lets any
 * agent run through any connected carrier (ADR-8).
 */
export default function NewRunPage() {
  return (
    <Suspense fallback={<ComposerFallback />}>
      <RunComposer />
    </Suspense>
  );
}

/**
 * Reads `?agent=` to pre-select what a "Run" button sent it, which means it has
 * to sit inside a Suspense boundary - `useSearchParams` opts a route out of
 * prerendering otherwise.
 */
function RunComposer() {
  const router = useRouter();
  const toast = useToast();
  const searchParams = useSearchParams();
  const session = useSession();
  const { health, phase, refresh } = useAppStore();

  const [agents, setAgents] = useState<VoiceAgent[]>([]);
  const [numbers, setNumbers] = useState<TelephonyNumber[]>([]);
  const [loadingNumbers, setLoadingNumbers] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const [rows, setRows] = useState<ParsedRow[]>([]);
  const [chosenAgentId, setChosenAgentId] = useState<string | null>(null);
  const [selectedNumberIds, setSelectedNumberIds] = useState<string[]>([]);
  const [runName, setRunName] = useState('');
  const [runInstruction, setRunInstruction] = useState('');
  const [starting, setStarting] = useState(false);

  useOrgScopedEffect(() => {
    api
      .listVoiceAgents()
      .then(setAgents)
      .catch(() => setAgents([]));
  }, []);

  useOrgScopedEffect(() => {
    setLoadingNumbers(true);
    api
      .listNumbers()
      .then(setNumbers)
      .catch(() => setNumbers([]))
      .finally(() => setLoadingNumbers(false));
  }, []);

  /**
   * The selected agent is derived, not synced.
   *
   * Precedence: an explicit choice in this session, then the `?agent=` a "Run"
   * button arrived with, then the first available. Deriving it means the right
   * agent is selected on the first render rather than after a corrective one.
   */
  const requested = searchParams.get('agent');
  const agentId =
    chosenAgentId ??
    (requested && agents.some((a) => a.id === requested)
      ? requested
      : (agents[0]?.id ?? ''));

  const agent = agents.find((a) => a.id === agentId);

  // Only a verified number with a trunk behind it can carry a call, and that
  // judgement is the server's - `diallable` arrives resolved so the client is
  // never comparing status strings.
  const diallable = useMemo(
    () => numbers.filter((n) => n.diallable),
    [numbers],
  );
  const unusable = useMemo(
    () => numbers.filter((n) => !n.diallable),
    [numbers],
  );

  const chosenNumbers = useMemo(
    () => diallable.filter((n) => selectedNumberIds.includes(n.id)),
    [diallable, selectedNumberIds],
  );

  const providers = useMemo(
    () => [...new Set(diallable.map((n) => n.provider))].sort(),
    [diallable],
  );

  const validRows = useMemo(() => rows.filter((r) => r.valid), [rows]);
  const contacts = useMemo(() => toContactInputs(rows), [rows]);
  const columns = useMemo(() => contextColumns(validRows), [validRows]);

  function toggleNumber(id: string) {
    setSelectedNumberIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  async function sync(provider: string) {
    setSyncing(true);
    try {
      const fresh = await api.syncNumbers(provider);
      // Replaces only this provider's rows: syncing Twilio must not drop the
      // Plivo numbers already on screen.
      setNumbers((prev) => [
        ...prev.filter((n) => n.provider !== provider),
        ...fresh,
      ]);
      toast({
        tone: 'success',
        title: `${fresh.length} ${fresh.length === 1 ? 'number' : 'numbers'} found`,
      });
    } catch (error) {
      toast({
        tone: 'error',
        title: "Couldn't read that account's numbers",
        body:
          error instanceof Error
            ? error.message
            : 'The carrier did not respond. Nothing changed.',
      });
    } finally {
      setSyncing(false);
    }
  }

  /**
   * Exactly why Start is blocked. Never a generic complaint.
   *
   * `calling_available` is checked *before* the number checks, and the order is
   * the point. It is a property of the deployment - LiveKit keys in the
   * server's environment - not of this organisation, and pointing a number at
   * LiveKit is what makes it diallable at all. With it false, connecting a
   * carrier cannot produce a diallable number however many times someone tries,
   * so leading with "connect a carrier" sends them to a page that cannot fix it
   * and they arrive back here reading the same sentence.
   */
  const blocker = useMemo<string | null>(() => {
    if (phase !== 'up') return 'Waiting for the service to respond.';
    if (!health?.calling_available) {
      return 'This deployment cannot place calls: it has no LiveKit credentials. Connecting a carrier will not change that - the server needs LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET and LIVEKIT_SIP_HOST.';
    }
    if (!agentId) {
      return agents.length === 0
        ? 'Build an agent first - it holds the prompt and the fields to collect.'
        : 'Pick an agent first.';
    }
    if (chosenNumbers.length === 0) {
      if (numbers.length === 0) {
        return 'No number to dial from yet. Connect a carrier in Integrations, then sync its numbers.';
      }
      if (diallable.length === 0) {
        return `Synced ${numbers.length === 1 ? 'a number' : `${numbers.length} numbers`}, but ${numbers.length === 1 ? 'it is' : 'none are'} ready to dial from yet - each has to be connected to a voice agent in Integrations before it can carry a call.`;
      }
      return 'Pick at least one number to call from.';
    }
    if (validRows.length === 0) {
      return rows.length === 0
        ? 'Add at least one contact.'
        : 'Every row has a problem. Fix one, or remove the invalid rows.';
    }
    return null;
  }, [
    phase,
    agentId,
    agents.length,
    chosenNumbers.length,
    diallable.length,
    numbers.length,
    validRows.length,
    rows.length,
    health,
  ]);

  async function start() {
    if (blocker) return;
    setStarting(true);
    try {
      const { run_id } = await api.startRun({
        voice_agent_id: agentId,
        number_ids: chosenNumbers.map((n) => n.id),
        contacts,
        name: runName.trim() || null,
        run_instruction: runInstruction.trim() || null,
      });
      toast({ tone: 'success', title: 'Run started' });
      refresh();
      router.push(`/app/runs/${run_id}`);
    } catch (error) {
      toast({
        tone: 'error',
        title: "That run wasn't started",
        body:
          error instanceof Error
            ? error.message
            : "The service didn't respond. Nothing was dialled.",
      });
    } finally {
      setStarting(false);
    }
  }

  // A viewer could once import contacts, edit rows, and reach a fully live
  // "Start" button (ISSUES.md #71). Blocked entirely rather than just disabling
  // Start, since a viewer can view data and scroll, not build a run that never
  // gets submitted.
  if (
    session.status === 'signed-in' &&
    !session.profile.permissions.includes('runs:start')
  ) {
    return (
      <div className="flex flex-col gap-6">
        <ComposerHeading />
        <NotWiredNotice>
          Your role can view runs but not start one. Ask an owner, admin, or
          operator in your organisation.
        </NotWiredNotice>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <ComposerHeading />

      <ConnectionBanner phase={phase} />

      {/* ---- 1 · Agent --------------------------------------------------- */}
      <Step
        n="01"
        title="Agent"
        detail="Who calls, what they say, and what they have to come back with."
      >
        {agents.length === 0 ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-small text-text-dim">
              No agents yet. An agent holds the voice, the prompt, and the
              fields a call has to collect.
            </p>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => router.push('/app/agentic')}
            >
              Build an agent
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <ul className="flex flex-col gap-2">
              {agents.map((option) => (
                <li key={option.id}>
                  <button
                    type="button"
                    aria-pressed={option.id === agentId}
                    onClick={() => setChosenAgentId(option.id)}
                    className={cn(
                      'flex w-full flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-3 text-left ring-1 transition-colors duration-(--dur-fast)',
                      'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--primary)',
                      option.id === agentId
                        ? 'bg-surface-raised ring-(--primary)'
                        : 'bg-surface ring-rule hover:ring-rule-strong',
                    )}
                  >
                    <span className="flex min-w-0 flex-col gap-0.5">
                      <span className="truncate text-body font-medium text-text">
                        {option.name}
                      </span>
                      <span className="truncate text-small text-text-mute">
                        {[
                          option.llm_model,
                          option.tts_provider,
                          option.stt_provider,
                        ]
                          .filter(Boolean)
                          .join(' · ') || 'No pipeline configured'}
                      </span>
                    </span>
                    <span className="shrink-0 font-mono text-data text-text-dim">
                      {option.collect_fields.length}{' '}
                      {option.collect_fields.length === 1 ? 'field' : 'fields'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>

            {agent && agent.collect_fields.length === 0 ? (
              <p className="text-small text-text-dim">
                This agent collects no fields, so calls come back as transcripts
                rather than as data. Add fields in the agent to change that.
              </p>
            ) : null}
          </div>
        )}
      </Step>

      {/* ---- 2 · Numbers ------------------------------------------------- */}
      <Step
        n="02"
        title="Call from"
        detail="Pick one number, some, or all. Calls are spread across whatever you choose."
      >
        <div className="flex flex-col gap-4">
          {loadingNumbers ? (
            <p className="font-mono text-data text-text-mute">
              Reading your numbers…
            </p>
          ) : diallable.length === 0 ? (
            // Three different situations, and sending all of them to
            // Integrations with the same sentence is what made this a loop:
            // someone connects a carrier, comes back, and is told to connect a
            // carrier. What is missing is different in each case, so the
            // sentence has to be too.
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-small text-text-dim">
                {numbers.length === 0
                  ? 'No carrier connected yet. Connect one and CallFlow will read the numbers that account holds.'
                  : unusable[0]?.last_error
                    ? unusable[0].last_error
                    : `${unusable.length === 1 ? 'The number' : `All ${unusable.length} numbers`} on your carrier ${unusable.length === 1 ? 'is' : 'are'} still being set up. Open Integrations to see why.`}
              </p>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => router.push('/app/integrations')}
              >
                Integrations
              </Button>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={diallable.length === 0}
                  onClick={() =>
                    setSelectedNumberIds(diallable.map((n) => n.id))
                  }
                >
                  Select all
                </Button>
                {selectedNumberIds.length > 0 ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedNumberIds([])}
                  >
                    Clear
                  </Button>
                ) : null}
                {providers.map((provider) => (
                  <Button
                    key={provider}
                    variant="ghost"
                    size="sm"
                    loading={syncing}
                    onClick={() => sync(provider)}
                  >
                    <ArrowsClockwiseIcon aria-hidden className="size-4" />
                    Sync {provider}
                  </Button>
                ))}
              </div>

              <ul className="grid gap-2 sm:grid-cols-2">
                {diallable.map((number) => {
                  const picked = selectedNumberIds.includes(number.id);
                  return (
                    <li key={number.id}>
                      <button
                        type="button"
                        aria-pressed={picked}
                        onClick={() => toggleNumber(number.id)}
                        className={cn(
                          'flex w-full items-center justify-between gap-3 rounded-xl px-4 py-3 text-left ring-1 transition-colors duration-(--dur-fast)',
                          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--primary)',
                          picked
                            ? 'bg-surface-raised ring-(--primary)'
                            : 'bg-surface ring-rule hover:ring-rule-strong',
                        )}
                      >
                        <span className="flex min-w-0 flex-col gap-0.5">
                          <span className="font-mono text-data tabular-nums text-text">
                            {number.phone_masked}
                          </span>
                          <span className="truncate text-small text-text-mute">
                            {number.label ?? number.provider}
                          </span>
                        </span>
                        {picked ? (
                          <CheckCircleIcon
                            aria-hidden
                            weight="fill"
                            className="size-5 shrink-0 text-(--primary)"
                          />
                        ) : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </>
          )}

          {/* Shown rather than hidden: a number that failed provisioning is the
              most likely reason someone cannot find the one they expected. */}
          {unusable.length > 0 ? (
            <details className="rounded-xl bg-surface-raised p-3 ring-1 ring-rule">
              <summary className="cursor-pointer text-small text-text-dim">
                {unusable.length}{' '}
                {unusable.length === 1 ? 'number is' : 'numbers are'} not ready
                to dial from
              </summary>
              <ul className="mt-3 flex flex-col gap-2">
                {unusable.map((number) => (
                  <li
                    key={number.id}
                    className="flex flex-wrap items-baseline gap-x-3 gap-y-1"
                  >
                    <WarningCircleIcon
                      aria-hidden
                      className="size-4 shrink-0 translate-y-0.5 text-lamp-brass-text"
                    />
                    <span className="font-mono text-data tabular-nums text-text">
                      {number.phone_masked}
                    </span>
                    <span className="text-small text-text-mute">
                      {number.last_error ?? number.status}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      </Step>

      {/* ---- 3 · Contacts ------------------------------------------------ */}
      <Step
        n="03"
        title="Contacts"
        detail="Name, phone, and a note. Any other column becomes that person's own context."
      >
        <div className="flex flex-col gap-3">
          <ContactGrid rows={rows} onChange={setRows} />
          {columns.length > 0 ? (
            <p className="text-small text-text-dim">
              Each contact brings its own{' '}
              <span className="font-mono text-data text-text">
                {columns.join(', ')}
              </span>{' '}
              into the conversation.
            </p>
          ) : null}
        </div>
      </Step>

      {/* ---- 4 · Run ----------------------------------------------------- */}
      <Step
        n="04"
        title="Run"
        detail="Name it, add anything specific to this run, then start dialling."
      >
        <div className="flex flex-col gap-4 pl-4 border-l-2 border-l-rule-strong">
          <div className="grid gap-4 md:grid-cols-2">
            <Field
              label="Name this run"
              hint="Optional. Shows in the runs list instead of the agent's name."
            >
              <Input
                value={runName}
                onChange={(e) => setRunName(e.target.value)}
                placeholder="December enquiries"
              />
            </Field>
            <Field
              label="Just for this run"
              hint="Optional. Added to every prompt in this run, so a one-off instruction does not mean editing a shared agent."
            >
              <Textarea
                rows={3}
                value={runInstruction}
                onChange={(e) => setRunInstruction(e.target.value)}
                placeholder="Mention that the office is closed on the 25th."
              />
            </Field>
          </div>

          <dl className="flex flex-wrap gap-x-8 gap-y-2 border-t border-rule pt-4">
            <Estimate label="Contacts" value={String(validRows.length)} />
            <Estimate
              label="Calling from"
              value={String(chosenNumbers.length)}
              detail={chosenNumbers.length === 1 ? 'number' : 'numbers'}
            />
            <Estimate
              label="Fields per call"
              value={String(agent?.collect_fields.length ?? 0)}
            />
          </dl>

          <div className="flex flex-wrap items-center gap-3">
            {blocker ? (
              <Tooltip content={blocker} wrapTrigger>
                <Button size="lg" disabled>
                  Start run
                </Button>
              </Tooltip>
            ) : (
              <Button size="lg" loading={starting} onClick={start}>
                Start run
              </Button>
            )}
            <Button
              variant="secondary"
              size="lg"
              onClick={() => router.push('/app/runs')}
            >
              Cancel
            </Button>
          </div>
        </div>
      </Step>
    </div>
  );
}

function ComposerHeading() {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-small font-bold text-text-mute">New run</p>
      <h1 className="font-display text-h2 text-text">Start a run</h1>
    </div>
  );
}

function ComposerFallback() {
  return (
    <div className="flex flex-col gap-6">
      <ComposerHeading />
      <Panel className="p-5">
        <p className="font-mono text-data text-text-mute">
          Loading the composer…
        </p>
      </Panel>
    </div>
  );
}

function Step({
  n,
  title,
  detail,
  children,
}: {
  n: string;
  title: string;
  detail: string;
  children: React.ReactNode;
}) {
  return (
    <Panel className="flex flex-col gap-5 p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <span className="mt-1 shrink-0 text-small font-bold text-text">
          {n}
        </span>
        <div className="flex flex-col gap-0.5">
          <h2 className="text-h3 font-medium text-text">{title}</h2>
          <p className="text-small text-text-dim">{detail}</p>
        </div>
      </div>
      {children}
    </Panel>
  );
}

function Estimate({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-small font-bold text-text-mute">{label}</dt>
      <dd className="font-mono text-data tabular-nums text-text">
        {value}
        {detail ? (
          <span className="ml-1.5 text-text-mute">{detail}</span>
        ) : null}
      </dd>
    </div>
  );
}
