"use client";

import { useParams } from "next/navigation";
import { CampaignEditor } from "@/components/app/campaign-editor";
import { ConnectionBanner } from "@/components/app/connection-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { Eyebrow, Panel } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { Tag } from "@/components/ui/badge";
import { useAppStore } from "@/lib/app-store";

export default function EditCampaignPage() {
  const params = useParams<{ id: string }>();
  const id = typeof params?.id === "string" ? params.id : "";
  const { campaigns, phase, wakeSeconds } = useAppStore();

  const campaign = campaigns.find((c) => c.id === id);

  if (phase !== "up") {
    return (
      <div className="flex flex-col gap-6">
        <ConnectionBanner phase={phase} wakeSeconds={wakeSeconds} />
        {phase !== "down" ? (
          <div className="grid gap-6 lg:grid-cols-[55fr_45fr]">
            <div className="flex flex-col gap-4">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-64 w-full" />
            </div>
            <Skeleton className="h-80 w-full" />
          </div>
        ) : null}
      </div>
    );
  }

  if (!campaign) {
    return (
      <Panel>
        <EmptyState
          title="That campaign isn't here"
          body="It may have been deleted. Check the campaigns list for what's available."
        />
      </Panel>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <Eyebrow>Campaign</Eyebrow>
          {campaign.built_in ? <Tag>Template</Tag> : null}
        </div>
        <h1 className="font-display text-h2 text-text">{campaign.name}</h1>
        <p className="font-mono text-data text-text-mute">{campaign.id}</p>
      </div>

      <CampaignEditor existing={campaign} />
    </div>
  );
}
