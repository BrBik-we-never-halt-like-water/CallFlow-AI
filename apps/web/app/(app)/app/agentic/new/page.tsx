'use client';

import { AgentEditor } from '@/components/app/agentic/agent-editor';

export default function NewAgentPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="text-small font-bold text-text-mute">Agentic</p>
        <h1 className="font-display text-h2 text-text">New agent</h1>
        <p className="measure text-body text-text-dim">
          Pick a speech-to-text, text-to-speech, and model provider, write the
          system prompt, and connect a number to dial from.
        </p>
      </div>

      <AgentEditor />
    </div>
  );
}
