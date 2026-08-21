'use client';

import { AgentEditor } from '@/components/app/agentic/agent-editor';
import { PageHeader } from '@/components/app/page-header';

export default function NewAgentPage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-1.5">
        <PageHeader title="New agent" />
      </div>

      <AgentEditor />
    </div>
  );
}
