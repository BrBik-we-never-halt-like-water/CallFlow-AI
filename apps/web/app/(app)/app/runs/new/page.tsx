'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useMemo, useState } from 'react';
import { cn } from '@/lib/cn';
import { ConnectionBanner } from '@/components/app/connection-banner';
import { ContactGrid } from '@/components/app/contact-grid';
import { guardsFromSafety, SafetyBar } from '@/components/app/safety-bar';
import { Button } from '@/components/ui/button';
import { Field } from '@/components/ui/field';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { Tooltip } from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api';
import { useAppStore } from '@/lib/app-store';
import { renderGoalPreview } from '@/lib/campaign-fields';
import { toContactInputs, type ParsedRow } from '@/lib/contacts';

/**
 * The run composer.
 *
 * Three stacked steps on one page, not a wizard. Someone starting their fifth run of
 * the day should be able to see everything at once and change any of it - a wizard
 * makes the second run as slow as the first, and hides the safety state behind a step
 * you have already clicked past.
 */
export default function NewRunPage() {
  return (
    <Suspense fallback={<ComposerFallback />}>
      <RunComposer />
    </Suspense>
  );
}

/**
 * The composer reads the `?campaign=` parameter to pre-select what a "Run" button sent
 * it, which means it has to sit inside a Suspense boundary - `useSearchParams` opts a
 * route out of prerendering otherwise.
 */
function RunComposer() {
  const router = useRouter();
  const toast = useToast();
  const searchParams = useSearchParams();
  const { campaigns, health, safetySettings, phase, refresh } = useAppStore();

  const [rows, setRows] = useState<ParsedRow[]>([]);
  const [chosenId, setChosenId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  /**
   * The selected campaign is derived, not synced.
   *
   * Precedence: an explicit choice in this session, then the `?campaign=` a "Run" button
   * arrived with, then the first available. Deriving it means the correct campaign is
   * selected on the very first render rather than after a corrective one.
   */
  const requested = searchParams.get('campaign');
  const campaignId =
    chosenId ??
    (requested && campaigns.some((c) => c.id === requested)
      ? requested
      : (campaigns[0]?.id ?? ''));
  const setCampaignId = setChosenId;

  const campaign = campaigns.find((c) => c.id === campaignId);
  const validRows = useMemo(() => rows.filter((r) => r.valid), [rows]);
  const contacts = useMemo(() => toContactInputs(rows), [rows]);

  const guards = useMemo(
    () => guardsFromSafety(safetySettings),
    [safetySettings],
  );

  const ceiling = safetySettings?.max_calls_per_run ?? null;
  const overCeiling = ceiling !== null && validRows.length > ceiling;

  /** Exactly why Start is blocked. Never a generic complaint. */
  const blocker = useMemo<string | null>(() => {
    if (phase !== 'up') return 'Waiting for the service to respond.';
    if (!campaignId) return 'Pick a campaign first.';
    if (validRows.length === 0) {
      return rows.length === 0
        ? 'Add at least one contact.'
        : 'Every row has a problem. Fix one, or remove the invalid rows.';
    }
    if (!health?.api_key_configured) {
      return "No Voice API key is configured - calls can't be placed yet.";
    }
    if (overCeiling) {
      return `This run has ${validRows.length} contacts but the per-run ceiling is ${ceiling}. Raise the ceiling in Settings → Safety, or remove some rows.`;
    }
    return null;
  }, [
    phase,
    campaignId,
    validRows.length,
    rows.length,
    health,
    overCeiling,
    ceiling,
  ]);

  async function start() {
    if (blocker) return;
    setStarting(true);
    try {
      const { run_id } = await api.startRun(campaignId, contacts);
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

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="text-small font-bold text-text-mute">New run</p>
        <h1 className="font-display text-h2 text-text">Start a run</h1>
      </div>

      <ConnectionBanner phase={phase} />

      {/* ---- 1 · Contacts ------------------------------------------------ */}
      <Step
        n="01"
        title="Contacts"
        detail="Every row is validated before anything is dialled."
      >
        <ContactGrid rows={rows} onChange={setRows} />
      </Step>

      {/* ---- 2 · Campaign ----------------------------------------------- */}
      <Step n="02" title="Campaign" detail="What each contact will hear.">
        <div className="flex flex-col gap-4">
          <div className="max-w-md">
            <Field label="Campaign" required>
              <Select
                value={campaignId}
                onValueChange={setCampaignId}
                options={campaigns.map((c) => ({
                  value: c.id,
                  label: c.name,
                  hint: c.built_in ? 'Template' : undefined,
                }))}
                placeholder={
                  campaigns.length === 0
                    ? 'No campaigns available'
                    : 'Pick a campaign'
                }
                disabled={campaigns.length === 0}
              />
            </Field>
          </div>

          {campaign ? (
            <Panel sunken className="flex flex-col gap-2 p-4">
              <p className="text-small font-bold text-text-mute">
                {validRows[0]
                  ? `What ${validRows[0].name.split(' ')[0] || 'the first contact'} will hear`
                  : 'What each contact will hear'}
              </p>
              <div className="max-h-56 overflow-y-auto whitespace-pre-wrap font-mono text-data text-text">
                {renderGoalPreview(campaign.goal_template, {
                  name: validRows[0]?.name || 'there',
                  context: {
                    enquiry_note: validRows[0]?.note || 'no note on file',
                    appointment_time: 'tomorrow at 4pm',
                  },
                })}
              </div>
            </Panel>
          ) : null}
        </div>
      </Step>

      {/* ---- 3 · Run ---------------------------------------------------- */}
      <Step
        n="03"
        title="Run"
        detail="The guards below apply to every call in this run."
      >
        <div className="flex flex-col gap-4 pl-4 border-l-2 border-l-rule-strong">
          <SafetyBar guards={guards} />

          <dl className="flex flex-wrap gap-x-8 gap-y-2 border-t border-rule pt-4">
            <Estimate label="Contacts" value={String(validRows.length)} />
            {ceiling !== null ? (
              <Estimate
                label="Per-run ceiling"
                value={String(ceiling)}
                warn={overCeiling}
              />
            ) : null}
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

function ComposerFallback() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="text-small font-bold text-text-mute">New run</p>
        <h1 className="font-display text-h2 text-text">Start a run</h1>
      </div>
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
  warn = false,
}: {
  label: string;
  value: string;
  detail?: string;
  warn?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-small font-bold text-text-mute">{label}</dt>
      <dd
        className={cn(
          'font-mono text-data tabular-nums',
          warn ? 'text-lamp-flare-text' : 'text-text',
        )}
      >
        {value}
        {detail ? (
          <span className="ml-1.5 text-text-mute">{detail}</span>
        ) : null}
      </dd>
    </div>
  );
}
