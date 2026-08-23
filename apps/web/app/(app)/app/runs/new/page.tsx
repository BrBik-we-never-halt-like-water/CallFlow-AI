'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useMemo, useRef, useState } from 'react';
import {
  ArrowsClockwiseIcon,
  CheckIcon,
  PhoneIcon,
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
import { PageHeader } from '@/components/app/page-header';

const SECTIONS = ['agent', 'numbers', 'contacts', 'run'] as const;
type SectionId = (typeof SECTIONS)[number];

const SECTION_LABEL: Record<SectionId, string> = {
  agent: 'Agent',
  numbers: 'Call from',
  contacts: 'Contacts',
  run: 'Run',
};

/**
 * The run composer: an agent, the number(s) it calls from, and a sheet.
 *
 * Four stacked sections on one page, not a wizard. Someone starting their fifth run
 * of the day should be able to see everything at once and change any of it - a
 * wizard makes the second run as slow as the first. The strip above them is a
 * progress *summary*, not a gate: every section is always reachable, clicking a
 * strip segment just scrolls to it.
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

  const sectionRefs = useRef<Partial<Record<SectionId, HTMLDivElement | null>>>({});

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

  const done: Record<SectionId, boolean> = {
    agent: Boolean(agentId),
    numbers: selectedNumberIds.length > 0,
    contacts: validRows.length > 0,
    run: Boolean(agentId) && selectedNumberIds.length > 0 && validRows.length > 0,
  };

  function scrollToSection(id: SectionId) {
    sectionRefs.current[id]?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
  }

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

      {/* ---- Progress strip ----------------------------------------------
          A summary of the same four sections below, not a second copy of
          their content and not a gate - every section stays reachable
          regardless of order. Clicking a segment scrolls to it, which is the
          whole reason this is a row of buttons and not a row of labels. */}
      <ProgressStrip done={done} onSelect={scrollToSection} />

      {/* ---- 1 · Agent --------------------------------------------------- */}
      <Section
        id="agent"
        ref={(el) => {
          sectionRefs.current.agent = el;
        }}
        index={1}
        title="Agent"
        detail="Who calls, what they say, and what they have to come back with."
        done={done.agent}
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
            {/* A deck, not a list: agents as cards on a horizontal snap
                track, flicked through on touch and scrolled on desktop, with
                the chosen one held in brand. Radio semantics, so arrow keys
                move the choice the way the swipe does. */}
            <ul
              role="radiogroup"
              aria-label="Which agent calls"
              className="dash-scroll-x -mx-1 flex snap-x snap-mandatory gap-3 px-1 pb-1"
            >
              {agents.map((option) => {
                const chosen = option.id === agentId;
                const initial = option.name.trim().charAt(0).toUpperCase() || '?';
                return (
                  <li key={option.id} className="w-56 shrink-0 snap-start">
                    <button
                      type="button"
                      role="radio"
                      aria-checked={chosen}
                      onClick={() => setChosenAgentId(option.id)}
                      className={cn(
                        'flex h-full w-full flex-col gap-3 rounded-xl border px-4 py-3.5 text-left',
                        'transition-[border-color,box-shadow,transform] duration-(--dur-micro)',
                        'focus-visible:outline-none',
                      )}
                      style={
                        chosen
                          ? {
                              borderColor: 'var(--dash-brand)',
                              background: 'var(--dash-brand-soft)',
                              boxShadow:
                                '0 0 0 3px color-mix(in oklab, var(--dash-brand) 18%, transparent)',
                            }
                          : {
                              borderColor: 'var(--dash-border)',
                              background: 'var(--dash-surface)',
                            }
                      }
                    >
                      <div className="flex items-center gap-2.5">
                        <span
                          aria-hidden
                          className="flex size-8 shrink-0 items-center justify-center rounded-full text-[0.8125rem] font-semibold"
                          style={{
                            background: 'var(--dash-brand-soft)',
                            color: 'var(--dash-brand-ink)',
                          }}
                        >
                          {initial}
                        </span>
                        <span
                          className="truncate text-[0.8125rem] font-semibold"
                          style={{ color: 'var(--dash-text)' }}
                        >
                          {option.name}
                        </span>
                      </div>
                      <span className="flex flex-col gap-0.5">
                        {[
                          option.llm_model,
                          option.tts_provider,
                          option.stt_provider,
                        ]
                          .filter(Boolean)
                          .slice(0, 3)
                          .map((part) => (
                            <span
                              key={String(part)}
                              className="truncate text-[0.6875rem]"
                              style={{ color: 'var(--dash-text-mute)' }}
                            >
                              {part}
                            </span>
                          ))}
                      </span>
                      <span
                        className="dash-num mt-auto flex items-center gap-1 text-[0.6875rem] font-medium"
                        style={{
                          color: chosen
                            ? 'var(--dash-brand-ink)'
                            : 'var(--dash-text-dim)',
                        }}
                      >
                        {chosen ? (
                          <CheckIcon aria-hidden weight="bold" className="size-3" />
                        ) : null}
                        {option.collect_fields.length}{' '}
                        {option.collect_fields.length === 1 ? 'field' : 'fields'}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>

            {agent && agent.collect_fields.length === 0 ? (
              <p className="text-small text-text-dim">
                This agent collects no fields, so calls come back as transcripts
                rather than as data. Add fields in the agent to change that.
              </p>
            ) : null}
          </div>
        )}
      </Section>

      {/* ---- 2 · Numbers ------------------------------------------------- */}
      <Section
        id="numbers"
        ref={(el) => {
          sectionRefs.current.numbers = el;
        }}
        index={2}
        title="Call from"
        detail="Pick one number, some, or all. Calls are spread across whatever you choose."
        done={done.numbers}
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

              <ul className="grid gap-2.5 sm:grid-cols-2">
                {diallable.map((number) => {
                  const picked = selectedNumberIds.includes(number.id);
                  return (
                    <li key={number.id}>
                      <button
                        type="button"
                        aria-pressed={picked}
                        onClick={() => toggleNumber(number.id)}
                        className={cn(
                          'flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left ring-1 transition-colors duration-(--dur-fast)',
                          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--primary)',
                          picked
                            ? 'bg-surface-raised ring-(--primary)'
                            : 'bg-surface ring-rule hover:ring-rule-strong',
                        )}
                      >
                        <span
                          aria-hidden
                          className={cn(
                            'flex size-9 shrink-0 items-center justify-center rounded-full transition-colors duration-(--dur-fast)',
                            picked
                              ? 'bg-(--primary) text-(--primary-on)'
                              : 'bg-surface-sunken text-text-mute',
                          )}
                        >
                          {picked ? (
                            <CheckIcon aria-hidden weight="bold" className="size-4" />
                          ) : (
                            <PhoneIcon aria-hidden className="size-4" />
                          )}
                        </span>
                        <span className="flex min-w-0 flex-col gap-0.5">
                          <span className="font-mono text-data tabular-nums text-text">
                            {number.phone_masked}
                          </span>
                          <span className="truncate text-small text-text-mute">
                            {number.label ?? number.provider}
                          </span>
                        </span>
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
      </Section>

      {/* ---- 3 · Contacts ------------------------------------------------ */}
      <Section
        id="contacts"
        ref={(el) => {
          sectionRefs.current.contacts = el;
        }}
        index={3}
        title="Contacts"
        detail="Name, phone, and a note. Any other column becomes that person's own context."
        done={done.contacts}
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
      </Section>

      {/* ---- 4 · Run ----------------------------------------------------- */}
      <Section
        id="run"
        ref={(el) => {
          sectionRefs.current.run = el;
        }}
        index={4}
        title="Run"
        detail="Name it, add anything specific to this run, then start dialling."
        done={done.run}
        last
      >
        <div className="flex flex-col gap-5">
          {/* `items-start`, because a one-line input and a multi-row textarea
              never have equal natural height - stretching both to the row's
              tallest child (CSS Grid's default) leaves the shorter field
              sitting in a box padded with dead space nobody put there on
              purpose. Each field now only ever takes its own height. */}
          <div className="grid items-start gap-4 md:grid-cols-2">
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
              // Kept to one line deliberately: this hint sits beside "Name
              // this run"'s single-line hint, and a wrapped second line here
              // was what actually broke the alignment - it pushed this
              // column's own textarea down past where the input beside it
              // starts, so the two boxes' top edges never lined up despite
              // their labels doing so.
              label="Just for this run"
              hint="Optional. Appended to every prompt in this run - not saved to the agent."
            >
              <Textarea
                rows={2}
                value={runInstruction}
                onChange={(e) => setRunInstruction(e.target.value)}
                placeholder="Mention that the office is closed on the 25th."
              />
            </Field>
          </div>

          <dl className="grid grid-cols-3 gap-3 rounded-xl border border-rule bg-surface-sunken p-4">
            <Estimate label="Contacts" value={validRows.length} />
            <Estimate
              label={chosenNumbers.length === 1 ? 'Number' : 'Numbers'}
              value={chosenNumbers.length}
            />
            <Estimate
              label={
                (agent?.collect_fields.length ?? 0) === 1
                  ? 'Field per call'
                  : 'Fields per call'
              }
              value={agent?.collect_fields.length ?? 0}
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
      </Section>
    </div>
  );
}

function ComposerHeading() {
  return <PageHeader title="Start a run" />;
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

/**
 * The four sections, as an always-clickable summary row.
 *
 * Not a wizard's step indicator - nothing here is locked, and the number
 * beside each label is a count, not a gate. It exists so a glance at the top
 * of a long page answers "what's left", and a click gets there without a
 * scroll.
 */
function ProgressStrip({
  done,
  onSelect,
}: {
  done: Record<SectionId, boolean>;
  onSelect: (id: SectionId) => void;
}) {
  const doneCount = SECTIONS.filter((id) => done[id]).length;

  return (
    <Panel className="p-3 sm:p-4" flat>
      <div className="flex items-center gap-1 sm:gap-2">
        {SECTIONS.map((id, i) => {
          const isDone = done[id];
          const isLast = i === SECTIONS.length - 1;
          return (
            <div key={id} className="flex flex-1 items-center gap-1 sm:gap-2">
              <button
                type="button"
                onClick={() => onSelect(id)}
                className={cn(
                  'group flex min-w-0 flex-1 cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-left',
                  'transition-colors duration-(--dur-micro) hover:bg-surface-hover',
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    'flex size-6 shrink-0 items-center justify-center rounded-full font-mono text-[0.6875rem] font-semibold transition-colors duration-(--dur-base)',
                  )}
                  style={
                    isDone
                      ? { background: 'var(--dash-brand)', color: 'var(--dash-brand-on)' }
                      : {
                          background: 'var(--dash-neutral-soft)',
                          color: 'var(--dash-neutral-ink)',
                        }
                  }
                >
                  {isDone ? (
                    <CheckIcon aria-hidden weight="bold" className="size-3" />
                  ) : (
                    i + 1
                  )}
                </span>
                <span
                  className="truncate text-small font-medium"
                  style={{ color: 'var(--dash-text)' }}
                >
                  {SECTION_LABEL[id]}
                </span>
              </button>
              {!isLast ? (
                <span
                  aria-hidden
                  className="h-px w-4 shrink-0 sm:w-8"
                  style={{
                    background: isDone
                      ? 'var(--dash-brand)'
                      : 'var(--dash-border)',
                  }}
                />
              ) : null}
            </div>
          );
        })}
        <span className="dash-num hidden shrink-0 pl-2 text-small font-medium text-text-mute sm:inline">
          {doneCount}/{SECTIONS.length}
        </span>
      </div>
    </Panel>
  );
}

/**
 * One section of the run pipeline.
 *
 * `id` gives each section a real anchor the progress strip scrolls to.
 * `done` lights the index badge once the section has what it needs, so a
 * glance down the page shows how much of the run is assembled without
 * reading the strip at all.
 */
const Section = ({
  ref,
  id,
  index,
  title,
  detail,
  done = false,
  last = false,
  children,
}: {
  ref?: React.Ref<HTMLDivElement>;
  id: SectionId;
  index: number;
  title: string;
  detail: string;
  done?: boolean;
  /** Kept for API symmetry with the old rail; unused now that sections are
   *  full-width cards rather than nodes on a line. */
  last?: boolean;
  children: React.ReactNode;
}) => {
  void last;
  return (
    <div ref={ref} id={id} className="panel-enter scroll-mt-4">
      <Panel className="flex flex-col gap-4 p-4 sm:p-6">
        <div className="flex items-start gap-3">
          <span
            aria-hidden
            className="flex size-7 shrink-0 items-center justify-center rounded-full font-mono text-[0.75rem] font-semibold transition-colors duration-(--dur-base)"
            style={
              done
                ? { background: 'var(--dash-brand)', color: 'var(--dash-brand-on)' }
                : {
                    background: 'var(--dash-neutral-soft)',
                    color: 'var(--dash-neutral-ink)',
                  }
            }
          >
            {done ? <CheckIcon aria-hidden weight="bold" className="size-3.5" /> : index}
          </span>
          <div className="flex flex-col gap-0.5 pt-0.5">
            <h2
              className="text-[0.75rem] font-semibold uppercase tracking-[0.05em]"
              style={{ color: 'var(--dash-text)' }}
            >
              {title}
            </h2>
            <p className="text-small text-text-dim">{detail}</p>
          </div>
        </div>
        {children}
      </Panel>
    </div>
  );
};

function Estimate({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center gap-0.5 text-center">
      <dd className="dash-num text-[1.5rem] font-semibold leading-none text-text">
        {value}
      </dd>
      <dt className="text-small text-text-mute">{label}</dt>
    </div>
  );
}
