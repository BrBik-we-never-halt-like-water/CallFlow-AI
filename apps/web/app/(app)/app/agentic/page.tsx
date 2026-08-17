'use client';

import Link from 'next/link';
import { useState } from 'react';
import { AgentCard } from '@/components/app/agent-card';
import { VoiceField } from '@/components/brand/voice-field';
import { NotWiredNotice } from '@/components/app/settings-section';
import { SessionGate } from '@/components/app/session-gate';
import { Button } from '@/components/ui/button';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import {
  type AgentDraft,
  clearAgentDraftByKey,
  listUnsavedAgentDrafts,
  type StoredAgentDraft,
} from '@/lib/agent-draft';
import { cn } from '@/lib/cn';
import { api, type VoiceAgent } from '@/lib/api';
import { useScopedOrgId } from '@/lib/hooks/use-active-org';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession, type SessionProfile } from '@/lib/hooks/use-session';

export default function AgenticPage() {
  const session = useSession();
  return (
    <SessionGate session={session}>
      {(profile) => <AgenticContent profile={profile} />}
    </SessionGate>
  );
}

/**
 * An agent someone started and left. Deliberately not an `AgentCard`: this has
 * no id, no created-by, and nothing to run - offering the same affordances
 * would imply it exists on the server when it only exists in this browser.
 */
function DraftLeg({
  label,
  value,
  color,
}: {
  label: string;
  value: string | null;
  color: string;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="flex items-center gap-1.5">
        <span
          aria-hidden
          className="size-1.5 shrink-0 rounded-full"
          style={{ background: color }}
        />
        <span className="text-[0.625rem] uppercase tracking-[0.07em] text-text-mute">
          {label}
        </span>
      </span>
      <span className="truncate text-small text-text-dim">
        {value ?? 'Not set'}
      </span>
    </div>
  );
}

/**
 * An agent someone started and left. Deliberately not an `AgentCard`: this has
 * no id, no created-by, and nothing to run - offering the same affordances
 * would imply it exists on the server when it only exists in this browser.
 *
 * It shows the three legs because that is what distinguishes one draft from
 * another: with drafts keyed by configuration, "Untitled agent" twice is only
 * telling them apart by what they are built from.
 */
function DraftCard({
  draft,
  onDiscard,
}: {
  draft: AgentDraft;
  onDiscard: () => void;
}) {
  return (
    <Panel className="flex w-full flex-col gap-4 rounded-2xl p-4">
      <div className="flex items-start justify-between gap-3">
        <span className="min-w-0 truncate text-body font-medium text-text">
          {draft.name.trim() || 'Untitled agent'}
        </span>
        <span className="shrink-0 rounded-full border border-rule px-2 py-0.5 text-[0.6875rem] text-text-mute">
          Draft
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <DraftLeg
          label="Transcriber"
          value={draft.sttProvider}
          color="var(--leg-stt)"
        />
        <DraftLeg label="Model" value={draft.llmModel} color="var(--leg-llm)" />
        <DraftLeg
          label="Voice"
          value={draft.voiceId ?? draft.ttsProvider}
          color="var(--leg-tts)"
        />
      </div>

      <div className="mt-auto flex items-center gap-2">
        <Button asChild size="sm">
          <Link href="/app/agentic/new">Continue</Link>
        </Button>
        <Button variant="ghost" size="sm" onClick={onDiscard}>
          Discard
        </Button>
      </div>
    </Panel>
  );
}

function AgenticContent({ profile }: { profile: SessionProfile }) {
  const toast = useToast();
  const canRead = profile.permissions.includes('agents:read');
  const canWrite = profile.permissions.includes('agents:write');
  const canDelete = profile.permissions.includes('agents:delete');

  const [agents, setAgents] = useState<VoiceAgent[] | null>(null);
  // Lazy initialiser, not an effect: `react-hooks/set-state-in-effect` is an
  // error here, and this only ever runs on the client - `SessionGate` has
  // already resolved a session by the time this renders, so there is no
  // server pass whose markup this could disagree with.
  const scopedOrgId = useScopedOrgId();
  const [drafts, setDrafts] = useState<StoredAgentDraft[]>(() =>
    typeof window === 'undefined' ? [] : listUnsavedAgentDrafts(scopedOrgId),
  );
  const [tab, setTab] = useState<'agents' | 'drafts'>('agents');

  function load() {
    if (!canRead) return;
    api
      .listVoiceAgents()
      .then(setAgents)
      .catch(() => toast({ tone: 'error', title: "Couldn't load agents" }));
  }

  useOrgScopedEffect(() => {
    load();
  });

  // Every role holds `agents:read` today, so this shouldn't normally trigger -
  // but the nav hiding this page is UX, not the gate, and the page has to
  // check for itself the same way `settings/integrations` does for its own
  // read permission.
  if (!canRead) {
    return (
      <div className="flex flex-col gap-6">
        <p className="text-2xl font-bold text-text">Agents</p>
        <NotWiredNotice>
          Agents aren&apos;t visible to your role. Ask an owner or admin in
          your organisation if you need one built.
        </NotWiredNotice>
      </div>
    );
  }

  return (
    // `isolate` makes this the stacking context the field's `-z-10` resolves
    // against. Without it that z-index escapes to the page root and lands
    // behind `.app-canvas`'s own background, which paints over it - the field
    // renders, and is simply never visible.
    <div className="relative isolate flex flex-col gap-8">
      {/* The hero's own voice field, quieter.
          Dimmed with `opacity`, not `--field-gain`: the canvas reads that
          variable off `document.documentElement` once a frame, so setting it
          on this wrapper would do nothing and only look like it should. The
          radial mask fades it out before it reaches the cards, where it would
          otherwise compete with every provider mark on the page. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -top-8 -z-10 h-96 opacity-40 [mask-image:radial-gradient(ellipse_80%_70%_at_50%_30%,#000_20%,transparent_78%)] [-webkit-mask-image:radial-gradient(ellipse_80%_70%_at_50%_30%,#000_20%,transparent_78%)]"
      >
        <VoiceField />
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          <h1 className="font-display text-h2 text-text">Agents</h1>
        </div>
        {canWrite ? (
          <Button asChild>
            <Link href="/app/agentic/new">Create agent</Link>
          </Button>
        ) : null}
      </div>

      {/* Words and a divider, not a filled control: there are two of these and
          they sit under a page title that already says where you are. A
          segmented track drew a full-width slab for a choice this small. */}
      <div role="tablist" aria-label="Agents or drafts" className="flex items-center gap-3">
        <TabLink
          selected={tab === 'agents'}
          onSelect={() => setTab('agents')}
        >
          Agents
        </TabLink>
        <span aria-hidden className="text-rule-strong">
          |
        </span>
        <TabLink
          selected={tab === 'drafts'}
          onSelect={() => setTab('drafts')}
        >
          {drafts.length ? `Drafts (${drafts.length})` : 'Drafts'}
        </TabLink>
      </div>

      {tab === 'agents' ? (
        agents === null ? (
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }, (_, i) => (
              <li key={i}>
                <Panel className="flex flex-col gap-3 rounded-2xl p-4">
                  <Skeleton className="h-5 w-40" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-2/3" />
                  <Skeleton className="mt-2 h-3 w-24" />
                </Panel>
              </li>
            ))}
          </ul>
        ) : agents.length === 0 ? (
          <EmptyLine>No agents created.</EmptyLine>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {agents.map((agent) => (
              <li key={agent.id} className="flex">
                <AgentCard
                  agent={agent}
                  canDelete={canDelete}
                  onChanged={load}
                  currentUserId={profile.user_id}
                />
              </li>
            ))}
          </ul>
        )
      ) : drafts.length === 0 ? (
        <EmptyLine>No drafts.</EmptyLine>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {drafts.map((entry) => (
            <li key={entry.key} className="flex">
              <DraftCard
                draft={entry.draft}
                onDiscard={() => {
                  clearAgentDraftByKey(entry.key);
                  setDrafts(listUnsavedAgentDrafts(scopedOrgId));
                }}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Selection is carried by weight and colour alone - the only two things that
 *  can mark a choice once the control has no surface of its own. */
function TabLink({
  selected,
  onSelect,
  children,
}: {
  selected: boolean;
  onSelect: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={selected}
      onClick={onSelect}
      className={cn(
        'rounded-xs text-body transition-colors duration-(--dur-fast)',
        'focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-(--primary)',
        selected
          ? 'font-medium text-text'
          : 'text-text-mute hover:text-text-dim',
      )}
    >
      {children}
    </button>
  );
}

/** Centred, so an empty tab reads as "nothing here" rather than as a page that
 *  failed to finish loading its left column. */
function EmptyLine({ children }: { children: React.ReactNode }) {
  return (
    <p className="py-16 text-center text-small text-text-mute">{children}</p>
  );
}
