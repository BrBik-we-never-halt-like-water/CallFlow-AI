'use client';

import { AgentEditor } from '@/components/app/agentic/agent-editor';

export default function NewAgentPage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-display text-h2 text-text">New Agent</h1>
      </div>

      <AgentEditor />
    </div>
  );
}
