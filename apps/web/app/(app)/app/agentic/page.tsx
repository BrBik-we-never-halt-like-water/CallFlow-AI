'use client';

import { RobotIcon } from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { useState } from 'react';
import { AgentCard } from '@/components/app/agent-card';
import { NotWiredNotice } from '@/components/app/settings-section';
import { SessionGate } from '@/components/app/session-gate';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { api, type VoiceAgent } from '@/lib/api';
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

function AgenticContent({ profile }: { profile: SessionProfile }) {
  const toast = useToast();
  const canRead = profile.permissions.includes('agents:read');
  const canWrite = profile.permissions.includes('agents:write');
  const canDelete = profile.permissions.includes('agents:delete');

  const [agents, setAgents] = useState<VoiceAgent[] | null>(null);

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
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-2xl font-bold text-text">Agents</p>
        {canWrite ? (
          <Button asChild>
            <Link href="/app/agentic/new">Create agent</Link>
          </Button>
        ) : null}
      </div>

      <div className="flex flex-col gap-3">
        <p className="text-small font-bold text-text-mute">Your agents</p>

        {agents === null ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }, (_, i) => (
              <Panel key={i} className="panel-glass flex flex-col gap-3 p-4">
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-2/3" />
                <Skeleton className="mt-2 h-3 w-24" />
              </Panel>
            ))}
          </div>
        ) : agents.length === 0 ? (
          <Panel className="panel-glass">
            <EmptyState
              icon={RobotIcon}
              title="No agents yet"
              body="Create a voice agent and pick its speech, model, and voice providers."
              action={
                canWrite ? (
                  <Button asChild>
                    <Link href="/app/agentic/new">Create agent</Link>
                  </Button>
                ) : undefined
              }
            />
          </Panel>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {agents.map((agent) => (
              <li key={agent.id} className="flex">
                <AgentCard
                  agent={agent}
                  canDelete={canDelete}
                  onChanged={load}
                />
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <p className="text-small font-bold text-text-mute">Prebuilt</p>
        <NotWiredNotice>
          Prebuilt, ready-to-use agents are coming soon. For now, build your
          own with the providers you connect.
        </NotWiredNotice>
      </div>
    </div>
  );
}
