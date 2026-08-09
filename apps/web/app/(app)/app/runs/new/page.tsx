'use client';

import {
  CaretDownIcon,
  PlusIcon,
  SlidersHorizontalIcon,
} from '@phosphor-icons/react/dist/ssr';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useMemo, useRef, useState } from 'react';
import { ConnectionBanner } from '@/components/app/connection-banner';
import { ContactGrid } from '@/components/app/contact-grid';
import { NotWiredNotice } from '@/components/app/settings-section';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { Tooltip } from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/toast';
import { api, type Campaign } from '@/lib/api';
import { useAppStore } from '@/lib/app-store';
import { renderGoalPreview } from '@/lib/campaign-fields';
import { toContactInputs, type ParsedRow } from '@/lib/contacts';
import { isE164, normalisePhone } from '@/lib/format/phone';
import { useSession } from '@/lib/hooks/use-session';

/**
 * The run composer.
 *
 * One flat, single-column page, not a wizard and not a dashboard of boxes.
 * Campaign and this run's own guard overrides are picked from two dialogs
 * opened off the header, so the page itself is just the contacts table -
 * unboxed, not nested inside its own card - with the guard bar and the
 * Start/Cancel buttons in one bar at the bottom, sticky on wide screens so
 * they stay reachable while a long list scrolls.
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
  const session = useSession();
  const { campaigns, health, safetySettings, phase, refresh } = useAppStore();

  const [rows, setRows] = useState<ParsedRow[]>([]);
  const [chosenId, setChosenId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [campaignDialogOpen, setCampaignDialogOpen] = useState(false);
  const [settingsDialogOpen, setSettingsDialogOpen] = useState(false);
  /**
   * Generated once per submit attempt and kept across a failed retry - so
   * resubmitting after a dropped connection (the request may have actually
   * reached the server) replays the same, already-accepted run instead of
   * risking a second real batch of calls. Cleared only on success, when the
   * key has done its job and the composer is about to navigate away.
   */
  const idempotencyKeyRef = useRef<string | null>(null);

  // --- This run's own guard overrides --------------------------------------
  // Tighten-only, mirroring the backend's `apply_run_override` exactly (see
  // its own docstring for why): a run may ask for less than the organisation
  // allows, never more. Blank means "use the organisation's own value."
  const [runCeiling, setRunCeiling] = useState('');
  const [runAllowlist, setRunAllowlist] = useState('');

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

  const orgCeiling = safetySettings?.max_calls_per_run ?? null;

  /** What the ceiling actually will be for this run - the organisation's own
   * value, tightened by whatever's set in the run-settings dialog. Computed
   * client-side too (not just trusted to the API's own capping) so the
   * estimate and the blocker message are honest before the request is ever
   * sent. */
  const effectiveCeiling = useMemo(() => {
    const requestedCeiling = Number(runCeiling);
    if (!runCeiling.trim() || !Number.isFinite(requestedCeiling) || requestedCeiling <= 0) {
      return orgCeiling;
    }
    return orgCeiling !== null ? Math.min(requestedCeiling, orgCeiling) : requestedCeiling;
  }, [runCeiling, orgCeiling]);

  const runAllowlistNumbers = useMemo(
    () =>
      runAllowlist
        .split(',')
        .map((n) => normalisePhone(n.trim()))
        .filter(Boolean),
    [runAllowlist],
  );
  const badAllowlistEntry = runAllowlistNumbers.find((n) => !isE164(n));
  const hasRunOverride = runCeiling.trim().length > 0 || runAllowlistNumbers.length > 0;

  const overCeiling = effectiveCeiling !== null && validRows.length > effectiveCeiling;

  /** Exactly why Start is blocked. Never a generic complaint. */
  const blocker = useMemo<string | null>(() => {
    if (phase !== 'up') return 'Waiting for the service to respond.';
    if (!campaignId) return 'Add a campaign first.';
    if (validRows.length === 0) {
      return rows.length === 0
        ? 'Add at least one contact.'
        : 'Every row has a problem. Fix one, or remove the invalid rows.';
    }
    if (!health?.api_key_configured) {
      return "No Voice API key is configured - calls can't be placed yet.";
    }
    if (badAllowlistEntry) {
      return `"${badAllowlistEntry}" in this run's allowlist isn't a valid E.164 number. Fix it in Run settings.`;
    }
    if (overCeiling) {
      return `This run has ${validRows.length} contacts but the ceiling for this run is ${effectiveCeiling}. Raise it in Run settings, remove some rows, or raise the organisation's own ceiling in Settings → Safety.`;
    }
    return null;
  }, [
    phase,
    campaignId,
    validRows.length,
    rows.length,
    health,
    badAllowlistEntry,
    overCeiling,
    effectiveCeiling,
  ]);

  async function start() {
    if (blocker) return;
    setStarting(true);
    if (!idempotencyKeyRef.current) {
      idempotencyKeyRef.current = crypto.randomUUID();
    }
    try {
      const { run_id } = await api.startRun(
        campaignId,
        contacts,
        idempotencyKeyRef.current,
        {
          max_calls_per_run: runCeiling.trim() ? Number(runCeiling) : undefined,
          allowlist: runAllowlistNumbers.length > 0 ? runAllowlistNumbers : undefined,
        },
      );
      idempotencyKeyRef.current = null;
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

  // This whole composer had no permission check at all - a viewer could
  // import contacts, edit rows, and reach a fully live "Start" button
  // (ISSUES.md #71). Blocked entirely rather than just disabling Start,
  // since a viewer can view data and scroll, not build a run that never
  // gets submitted.
  if (
    session.status === 'signed-in' &&
    !session.profile.permissions.includes('runs:start')
  ) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-1">
          <p className="text-small font-bold text-text-mute">New run</p>
          <h1 className="font-display text-h2 text-text">Start a run</h1>
        </div>
        <NotWiredNotice>
          Your role can view runs but not start one. Ask an owner, admin, or
          operator in your organisation.
        </NotWiredNotice>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-small font-bold text-text-mute">New run</p>
          <h1 className="font-display text-h2 text-text">Start a run</h1>
          <p className="measure text-small text-text-dim">
            Add contacts, then start the run.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => setCampaignDialogOpen(true)}
          >
            {campaign ? (
              <>
                {campaign.name}
                <CaretDownIcon aria-hidden className="size-3.5" />
              </>
            ) : (
              <>
                <PlusIcon aria-hidden className="size-4" />
                Add campaign
              </>
            )}
          </Button>
          <Button
            variant="secondary"
            className="relative"
            onClick={() => setSettingsDialogOpen(true)}
          >
            <SlidersHorizontalIcon aria-hidden className="size-4" />
            Run settings
            {hasRunOverride ? (
              <span
                aria-hidden
                className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-text"
              />
            ) : null}
          </Button>

          <span aria-hidden className="mx-1 h-6 w-px bg-rule" />

          <Button variant="secondary" onClick={() => router.push('/app/runs')}>
            Cancel
          </Button>
          {blocker ? (
            <Tooltip content={blocker} wrapTrigger>
              <Button disabled>Start run</Button>
            </Tooltip>
          ) : (
            <Button loading={starting} onClick={start}>
              Start run
            </Button>
          )}
        </div>
      </div>

      <ConnectionBanner phase={phase} />

      <ContactGrid rows={rows} onChange={setRows} />

      <CampaignDialog
        open={campaignDialogOpen}
        onOpenChange={setCampaignDialogOpen}
        campaigns={campaigns}
        campaignId={campaignId}
        onSelect={(id) => {
          setCampaignId(id);
          setCampaignDialogOpen(false);
        }}
        previewName={validRows[0]?.name}
        previewNote={validRows[0]?.note}
      />

      <RunSettingsDialog
        open={settingsDialogOpen}
        onOpenChange={setSettingsDialogOpen}
        orgCeiling={orgCeiling}
        runCeiling={runCeiling}
        onRunCeilingChange={setRunCeiling}
        runAllowlist={runAllowlist}
        onRunAllowlistChange={setRunAllowlist}
        badAllowlistEntry={badAllowlistEntry}
      />
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


/** Picks the campaign this run will use, with a live preview of the goal. */
function CampaignDialog({
  open,
  onOpenChange,
  campaigns,
  campaignId,
  onSelect,
  previewName,
  previewNote,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  campaigns: Campaign[];
  campaignId: string;
  onSelect: (id: string) => void;
  previewName?: string;
  previewNote?: string;
}) {
  const campaign = campaigns.find((c) => c.id === campaignId);

  return (
    <DialogRoot open={open} onOpenChange={onOpenChange}>
      <Dialog
        title="Campaign"
        description="What every contact in this run will hear."
        footer={
          <Button onClick={() => onOpenChange(false)}>Done</Button>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label="Campaign" required>
            <Select
              value={campaignId}
              onValueChange={onSelect}
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

          {campaign ? (
            <Panel sunken className="flex flex-col gap-2 p-4">
              <p className="text-small font-bold text-text-mute">
                {previewName
                  ? `What ${previewName.split(' ')[0] || 'the first contact'} will hear`
                  : 'What each contact will hear'}
              </p>
              <div className="max-h-56 overflow-y-auto whitespace-pre-wrap font-mono text-data text-text">
                {renderGoalPreview(campaign.goal_template, {
                  name: previewName || 'there',
                  context: {
                    enquiry_note: previewNote || 'no note on file',
                    appointment_time: 'tomorrow at 4pm',
                  },
                })}
              </div>
            </Panel>
          ) : null}
        </div>
      </Dialog>
    </DialogRoot>
  );
}

/** This run's own tightened guards - see `apply_run_override`'s docstring
 * (backend, `app/domain/safety.py`) for the tighten-only rule this mirrors. */
function RunSettingsDialog({
  open,
  onOpenChange,
  orgCeiling,
  runCeiling,
  onRunCeilingChange,
  runAllowlist,
  onRunAllowlistChange,
  badAllowlistEntry,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgCeiling: number | null;
  runCeiling: string;
  onRunCeilingChange: (value: string) => void;
  runAllowlist: string;
  onRunAllowlistChange: (value: string) => void;
  badAllowlistEntry?: string;
}) {
  return (
    <DialogRoot open={open} onOpenChange={onOpenChange}>
      <Dialog
        title="Run settings"
        description="Tighten this organisation's own safety guards for this run only - never looser than what's set in Settings → Safety."
        size="sm"
        footer={<Button onClick={() => onOpenChange(false)}>Done</Button>}
      >
        <div className="flex flex-col gap-4">
          <Field
            label="Ceiling for this run"
            hint={
              orgCeiling !== null
                ? `Optional - up to the organisation's own ${orgCeiling}. Leave blank to use it as-is.`
                : 'Optional. Leave blank to use the organisation default.'
            }
          >
            <Input
              type="number"
              min={1}
              max={orgCeiling ?? undefined}
              placeholder={orgCeiling !== null ? String(orgCeiling) : undefined}
              value={runCeiling}
              onChange={(e) => onRunCeilingChange(e.target.value)}
            />
          </Field>
          <Field
            label="Extra allowlist for this run"
            hint="Optional, comma-separated. Narrows the organisation's own allowlist further - never widens it."
            error={
              badAllowlistEntry
                ? `"${badAllowlistEntry}" isn't a valid E.164 number.`
                : undefined
            }
          >
            <Input
              value={runAllowlist}
              onChange={(e) => onRunAllowlistChange(e.target.value)}
              placeholder="+919876543210, +15555550100"
            />
          </Field>
        </div>
      </Dialog>
    </DialogRoot>
  );
}
