'use client';

import { LockIcon, LockOpenIcon } from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Tag } from '@/components/ui/badge';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { Panel } from '@/components/ui/panel';
import { useToast } from '@/components/ui/toast';
import { api, type AiProvider, type VoiceAgent } from '@/lib/api';
import { cn } from '@/lib/cn';
import { ProviderIcon } from './agentic/provider-icons';

/**
 * Display names to sit beside each provider's mark. The marks themselves come
 * from `ProviderIcon`, which uses vendors' own published SVGs rather than a
 * reproduction from memory - see its own note on why that is not the same
 * thing as the guessed-wordmark problem the integrations page avoids.
 * Unknown or not-yet-catalogued provider ids still render (capitalised)
 * rather than disappearing.
 */
const AI_PROVIDER_LABEL: Partial<Record<AiProvider, string>> = {
  sarvam: 'Sarvam',
  deepgram: 'Deepgram',
  elevenlabs: 'ElevenLabs',
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
};

/** Carriers no longer come from a fixed pair. The provisioning work made
 *  `Provider` an open string driven by `domain/providers.py`'s registry, so a
 *  two-key map here would fail to name Telnyx or Vonage and would need editing
 *  every time a carrier is added. `providerLabel` already capitalises anything
 *  it does not recognise, which is the right behaviour for an open set. */
function providerLabel(id: string | null): string {
  if (!id) return 'Not set';
  return AI_PROVIDER_LABEL[id as AiProvider] ?? id.charAt(0).toUpperCase() + id.slice(1);
}

/** OpenRouter model ids are `vendor/model` - the vendor half is already
 *  carried by the mark beside it, so only the model half is printed. */
function modelLabel(id: string | null): string {
  if (!id) return 'Not set';
  return id.split('/').at(-1) ?? id;
}

function ProviderChip({
  role,
  id,
  label,
}: {
  role: string;
  id: string | null;
  label: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      {/* Larger than the 16px these started at: the mark is the only thing on
          the row carrying vendor identity, and at 16 it read as a bullet
          rather than as a logo. The empty-slot placeholder tracks it so an
          unset leg still lines up. */}
      {id ? (
        <ProviderIcon id={id} className="size-6" />
      ) : (
        <span
          aria-hidden
          className="size-6 shrink-0 rounded-xs border border-dashed border-rule-strong"
        />
      )}
      <dt className="w-14 shrink-0 text-[0.6875rem] text-text-mute">{role}</dt>
      <dd
        className={cn(
          'min-w-0 flex-1 truncate text-small',
          id ? 'text-text-dim' : 'text-text-mute',
        )}
      >
        {label}
      </dd>
    </div>
  );
}

/**
 * One voice agent's summary card.
 *
 * Edit is always offered - the editor re-checks `agents:write` itself, so
 * hiding it here would only be UX, not a real gate (same "client-side hiding
 * is not the gate" reasoning as the page's own `agents:read` check). Delete
 * owns its own confirm step, since - unlike `CampaignCard` - nothing above it
 * in the tree keeps a "pending delete" dialog of its own.
 */
export function AgentCard({
  agent,
  canDelete,
  onChanged,
  currentUserId,
}: {
  agent: VoiceAgent;
  /** `agents:delete`. */
  canDelete: boolean;
  onChanged: () => void;
  /**
   * Who is looking, from the page's already-resolved session.
   *
   * Passed in rather than read from `useSession()` here: that hook holds its
   * own state per component and starts every one at `loading`, so a grid of
   * cards each began not knowing who the viewer was, printed "by <owner>",
   * and then removed it a moment later when its own fetch landed. Switching
   * tabs remounts them and it happens again.
   */
  currentUserId: string;
}) {
  const toast = useToast();
  const showAttribution =
    !!agent.created_by_name && agent.created_by !== currentUserId;

  const [pendingDelete, setPendingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [activating, setActivating] = useState(false);

  async function makeActive() {
    setActivating(true);
    try {
      await api.keepAgent(agent.id);
      toast({
        tone: 'success',
        title: `${agent.name} is now active`,
        // Says what it cost, because on a one-agent plan this necessarily takes
        // the slot from something else and finding that out later is worse.
        body: 'Whichever agent it replaced is now locked.',
      });
      onChanged();
    } catch (error) {
      toast({
        tone: 'error',
        title: "That agent wasn't activated",
        body:
          error instanceof Error
            ? error.message
            : "The service didn't respond.",
      });
    } finally {
      setActivating(false);
    }
  }

  async function confirmDelete() {
    setDeleting(true);
    try {
      await api.deleteVoiceAgent(agent.id);
      toast({ tone: 'success', title: 'Agent deleted' });
      setPendingDelete(false);
      onChanged();
    } catch (error) {
      toast({
        tone: 'error',
        title: "That agent wasn't deleted",
        body:
          error instanceof Error
            ? error.message
            : "The service didn't respond.",
      });
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      {/* The whole card is the link to the editor, with delete as the one
          control that opts out of it - a card whose only affordance was a
          small "Edit" button in its corner made the other 90% of the surface
          dead space. */}
      <Panel
        interactive={!agent.locked}
        className="group/agent relative flex w-full flex-col gap-5 overflow-hidden p-5"
      >
        {agent.locked ? <LockedOverlay agent={agent} busy={activating} onUnlock={makeActive} /> : null}

        {/* Everything below is inert while locked: blurred, unreadable to a
            screen reader, and untabbable. Without `pointer-events-none` and
            `inert` the card-wide link underneath would still be clickable
            through the blur, so a locked card would quietly behave like an
            unlocked one for anyone using a keyboard. */}
        <div
          className={
            agent.locked
              ? 'pointer-events-none flex select-none flex-col gap-5 blur-[3px] saturate-50 opacity-55'
              : 'contents'
          }
          inert={agent.locked}
        >
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col gap-1">
            <h3 className="min-w-0 truncate font-display text-h4 text-text">
              <Link
                href={`/app/agentic/${agent.id}`}
                className="outline-none after:absolute after:inset-0 after:rounded-[inherit] focus-visible:after:ring-2 focus-visible:after:ring-primary"
              >
                {agent.name}
              </Link>
            </h3>
            {showAttribution ? (
              <p className="truncate text-[0.6875rem] text-text-mute">
                by {agent.created_by_name}
              </p>
            ) : null}
          </div>
          {/* No "Locked" tag here - it would sit behind the blur, saying the
              same thing the overlay says in front of it. */}
          {agent.kind === 'prebuilt' ? <Tag>Prebuilt</Tag> : null}
        </div>

        {/* The category prefixes (STT/TTS/LLM) are gone: the mark identifies
            the vendor, and the order is fixed, so repeating the leg name on
            every chip was three words of text per card carrying nothing. */}
        <dl className="flex flex-col gap-2.5">
          <ProviderChip
            role="Hears"
            id={agent.stt_provider}
            label={providerLabel(agent.stt_provider)}
          />
          <ProviderChip
            role="Thinks"
            id={agent.llm_model}
            label={modelLabel(agent.llm_model)}
          />
          <ProviderChip
            role="Speaks"
            id={agent.tts_provider}
            label={providerLabel(agent.tts_provider)}
          />
          <ProviderChip
            role="Dials"
            id={agent.telephony_provider}
            label={
              agent.telephony_provider
                ? providerLabel(agent.telephony_provider)
                : 'No number'
            }
          />
        </dl>

        {/* Above the card-wide link's pseudo-element, or these would be
            unclickable. Edit names what the whole card already does - the
            surface stays the target, but nothing about a card says "click me
            to edit" until something does. */}
        <div className="relative z-10 mt-auto flex items-center justify-end gap-1">
          <Button asChild variant="ghost" size="sm">
            <Link href={`/app/agentic/${agent.id}`}>Edit</Link>
          </Button>
          {canDelete ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPendingDelete(true)}
            >
              Delete
            </Button>
          ) : null}
        </div>
        </div>
      </Panel>

      <DialogRoot
        open={pendingDelete}
        onOpenChange={(open) => !deleting && setPendingDelete(open)}
      >
        <Dialog
          title="Delete this agent?"
          description={`"${agent.name}" will be removed and can't be recovered.`}
          size="sm"
          footer={
            <>
              <Button
                variant="secondary"
                onClick={() => setPendingDelete(false)}
              >
                Keep it
              </Button>
              <Button
                variant="danger"
                loading={deleting}
                onClick={() => void confirmDelete()}
              >
                Delete agent
              </Button>
            </>
          }
        />
      </DialogRoot>
    </>
  );
}


/**
 * What sits over a locked agent: the reason, and the two ways out.
 *
 * A blur alone reads as a rendering fault, so the overlay has to say *why* the
 * card is unreadable. The lock is the affordance and the label together - the
 * icon alone would be decoration, and on its own a padlock is as easily read as
 * "secure" as "unavailable".
 *
 * The card underneath is `inert` rather than merely blurred, so this is the only
 * thing reachable by pointer or keyboard. Blur is a visual effect; without
 * inerting it, tabbing still lands on links nobody can read.
 *
 * Ink and surface only - no lamp colour. The five lamp colours mean call state
 * (CLAUDE.md §4 #10), and an agent locked by a plan has nothing to do with how a
 * call went.
 */
function LockedOverlay({
  agent,
  busy,
  onUnlock,
}: {
  agent: VoiceAgent;
  busy: boolean;
  onUnlock: () => Promise<void>;
}) {
  return (
    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 rounded-[inherit] bg-surface/70 p-5 text-center backdrop-blur-[2px]">
      <span className="flex size-10 items-center justify-center rounded-full bg-surface-sunken">
        <LockIcon aria-hidden weight="bold" className="size-5 text-text-mute" />
      </span>

      <div className="flex flex-col gap-1">
        <p className="text-small font-medium text-text">Locked by your plan</p>
        <p className="measure text-[0.6875rem] leading-relaxed text-text-dim">
          Nothing was deleted. Make{' '}
          <span className="text-text-mute">{agent.name}</span> the active agent,
          or upgrade to run more than one.
        </p>
      </div>

      <div className="flex items-center gap-1.5">
        <Button size="sm" loading={busy} onClick={() => void onUnlock()}>
          <LockOpenIcon aria-hidden weight="bold" className="size-4" />
          Make active
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link href="/app/billing">Upgrade</Link>
        </Button>
      </div>
    </div>
  );
}
