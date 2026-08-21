'use client';

import { useParams } from 'next/navigation';
import { useState } from 'react';
import { AgentEditor } from '@/components/app/agentic/agent-editor';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { api, type VoiceAgent } from '@/lib/api';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { PageHeader } from '@/components/app/page-header';

/**
 * No voice-agent equivalent of `useAppStore` exists yet - this fetches the
 * list itself and finds the match client-side rather than building a store
 * just for this page.
 */
export default function EditAgentPage() {
  const params = useParams<{ id: string }>();
  const id = typeof params?.id === 'string' ? params.id : '';
  const toast = useToast();

  const [agents, setAgents] = useState<VoiceAgent[] | null>(null);

  useOrgScopedEffect(() => {
    api
      .listVoiceAgents()
      .then(setAgents)
      .catch(() => toast({ tone: 'error', title: "Couldn't load agents" }));
  });

  if (agents === null) {
    return (
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-8 w-64" />
        </div>
        <div className="flex max-w-3xl flex-col gap-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      </div>
    );
  }

  const agent = agents.find((a) => a.id === id);

  if (!agent) {
    return (
      <Panel>
        <EmptyState
          title="That agent isn't here"
          body="It may have been deleted. Check the agents list for what's available."
        />
      </Panel>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Agent" figure={agent.name} />

      <AgentEditor existing={agent} />
    </div>
  );
}
