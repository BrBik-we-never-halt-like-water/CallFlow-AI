"use client";

import { MegaphoneIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { CampaignCard } from "@/components/app/campaign-card";
import { ConnectionBanner } from "@/components/app/connection-banner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogRoot } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Eyebrow, Panel } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabPanel } from "@/components/ui/disclosure";
import { useToast } from "@/components/ui/toast";
import { api, type Campaign } from "@/lib/api";
import { useAppStore } from "@/lib/app-store";
import { CAMPAIGN_DRAFT_KEY } from "@/lib/campaign-draft";

export default function CampaignsPage() {
  const router = useRouter();
  const toast = useToast();
  const { campaigns, hydratedRuns, phase, wakeSeconds, refresh } = useAppStore();
  const [filter, setFilter] = useState("all");
  const [pendingDelete, setPendingDelete] = useState<Campaign | null>(null);
  const [deleting, setDeleting] = useState(false);

  /** The most recent run per campaign, for each card's mini strip. */
  const lastRunByCampaign = useMemo(() => {
    const map = new Map<string, (typeof hydratedRuns)[number]>();
    for (const run of hydratedRuns) {
      const existing = map.get(run.campaign_id);
      if (!existing || run.started_at > existing.started_at) {
        map.set(run.campaign_id, run);
      }
    }
    return map;
  }, [hydratedRuns]);

  const builtIn = campaigns.filter((c) => c.built_in);
  const custom = campaigns.filter((c) => !c.built_in);
  const shown = filter === "templates" ? builtIn : filter === "custom" ? custom : campaigns;

  /**
   * Duplicating hands the source campaign to the editor as a draft rather than
   * creating it immediately. A duplicate you have not looked at is rarely what you
   * wanted, and this way the copy is named and reviewed before it exists.
   */
  function duplicate(campaign: Campaign) {
    try {
      sessionStorage.setItem(
        CAMPAIGN_DRAFT_KEY,
        JSON.stringify({
          name: `${campaign.name} copy`,
          goal_template: campaign.goal_template,
          region: campaign.region,
          language: campaign.language,
          outcome_fields: campaign.outcome_fields,
        }),
      );
    } catch {
      /* storage unavailable   the editor opens empty, which is recoverable */
    }
    router.push("/app/campaigns/new?from=duplicate");
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await api.deleteCampaign(pendingDelete.id);
      toast({ tone: "success", title: "Campaign deleted" });
      setPendingDelete(null);
      refresh();
      // The campaign list lives on the connection hook, which loads once   a reload is
      // the honest way to reflect the deletion until that becomes refetchable.
      router.refresh();
    } catch (error) {
      toast({
        tone: "error",
        title: "That campaign wasn't deleted",
        body: error instanceof Error ? error.message : "The service didn't respond.",
      });
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <Eyebrow>Campaigns</Eyebrow>
          <h1 className="font-display text-h2 text-text">What you&apos;re calling about</h1>
        </div>
        <Button asChild>
          <Link href="/app/campaigns/new">New campaign</Link>
        </Button>
      </div>

      <ConnectionBanner phase={phase} wakeSeconds={wakeSeconds} />

      <Tabs
        value={filter}
        onValueChange={setFilter}
        tabs={[
          { value: "all", label: "All", count: campaigns.length },
          { value: "templates", label: "Templates", count: builtIn.length },
          { value: "custom", label: "Yours", count: custom.length },
        ]}
      >
        <TabPanel value={filter} className="pt-6">
          {phase === "connecting" || phase === "waking" ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 3 }, (_, i) => (
                <Panel key={i} className="flex flex-col gap-3 p-4">
                  <Skeleton className="h-5 w-40" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-2/3" />
                  <Skeleton className="mt-2 h-3 w-24" />
                </Panel>
              ))}
            </div>
          ) : shown.length === 0 ? (
            <Panel>
              <EmptyState
                icon={MegaphoneIcon}
                title={filter === "custom" ? "You haven't made one yet" : "No campaigns yet"}
                body="A campaign is a goal written in plain English plus the fields you want back from every call."
                action={
                  <Button asChild>
                    <Link href="/app/campaigns/new">New campaign</Link>
                  </Button>
                }
              />
            </Panel>
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {shown.map((campaign) => (
                <li key={campaign.id} className="flex">
                  <CampaignCard
                    campaign={campaign}
                    lastRun={lastRunByCampaign.get(campaign.id)}
                    onDuplicate={duplicate}
                    onDelete={setPendingDelete}
                  />
                </li>
              ))}
            </ul>
          )}
        </TabPanel>
      </Tabs>

      <DialogRoot
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
      >
        <Dialog
          title="Delete this campaign?"
          description={
            pendingDelete
              ? `“${pendingDelete.name}” will be removed. Runs that already used it keep their results.`
              : undefined
          }
          size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setPendingDelete(null)}>
                Keep it
              </Button>
              <Button variant="danger" loading={deleting} onClick={confirmDelete}>
                Delete campaign
              </Button>
            </>
          }
        />
      </DialogRoot>
    </div>
  );
}
