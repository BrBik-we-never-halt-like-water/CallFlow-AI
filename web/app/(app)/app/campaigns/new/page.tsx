"use client";

import { CampaignEditor } from "@/components/app/campaign-editor";
import { Eyebrow } from "@/components/ui/panel";

export default function NewCampaignPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Eyebrow>New campaign</Eyebrow>
        <h1 className="font-display text-h2 text-text">Write the goal</h1>
        <p className="measure text-body text-text-dim">
          The goal is the part that decides whether this works. Everything else is
          configuration.
        </p>
      </div>

      <CampaignEditor />
    </div>
  );
}
