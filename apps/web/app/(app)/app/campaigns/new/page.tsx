'use client';

import { CampaignEditor } from '@/components/app/campaign-editor';

export default function NewCampaignPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="text-small font-bold text-text-mute">New campaign</p>
        <h1 className="font-display text-h2 text-text">Write the goal</h1>
        <p className="measure text-body text-text-dim">
          The goal decides whether this works - everything else is
          configuration.
        </p>
      </div>

      <CampaignEditor />
    </div>
  );
}
