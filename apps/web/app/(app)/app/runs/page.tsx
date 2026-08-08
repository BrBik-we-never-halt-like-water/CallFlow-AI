"use client";

import { BroadcastIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ConnectionBanner } from "@/components/app/connection-banner";
import { DataTable, type Column, type SortState } from "@/components/app/data-table";
import { LampBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { RunSummary } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { lampForRunStatus } from "@/lib/lamp";
import { useAppStore } from "@/lib/app-store";

export default function RunsPage() {
  const router = useRouter();
  const { runs, campaigns, phase, loadingRuns } = useAppStore();
  const [sort, setSort] = useState<SortState>({ id: "started_at", dir: "desc" });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const campaignName = (id: string) => campaigns.find((c) => c.id === id)?.name ?? id;

  /**
   * Sorting and pagination are done here rather than server-side because the runs
   * endpoint returns the whole list in one response. The DataTable's contract is
   * server-driven either way, so this swaps for a real query without touching it.
   */
  const sorted = useMemo(() => {
    const list = [...runs];
    list.sort((a, b) => {
      const dir = sort.dir === "asc" ? 1 : -1;
      switch (sort.id) {
        case "campaign":
          return campaignName(a.campaign_id).localeCompare(campaignName(b.campaign_id)) * dir;
        case "total":
          return (a.total - b.total) * dir;
        case "completed":
          return (a.completed - b.completed) * dir;
        case "status":
          return a.status.localeCompare(b.status) * dir;
        default:
          return a.started_at.localeCompare(b.started_at) * dir;
      }
    });
    return list;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runs, sort, campaigns]);

  const paged = useMemo(
    () => sorted.slice((page - 1) * pageSize, page * pageSize),
    [sorted, page, pageSize],
  );

  const columns: Column<RunSummary>[] = [
    {
      id: "campaign",
      header: "Campaign",
      sortable: true,
      cell: (run) => (
        <span className="flex items-center gap-2">
          <span className="truncate">{campaignName(run.campaign_id)}</span>
        </span>
      ),
      value: (run) => campaignName(run.campaign_id),
    },
    {
      id: "status",
      header: "Status",
      sortable: true,
      cell: (run) => {
        const lamp = lampForRunStatus(run.status);
        return (
          <LampBadge state={lamp.state} pulse={lamp.pulse}>
            {lamp.label}
          </LampBadge>
        );
      },
      value: (run) => run.status,
    },
    {
      id: "completed",
      header: "Settled",
      align: "right",
      mono: true,
      sortable: true,
      cell: (run) => `${run.completed}/${run.total}`,
      value: (run) => run.completed,
    },
    {
      id: "started_at",
      header: "Started",
      align: "right",
      mono: true,
      sortable: true,
      cell: (run) => formatTimestamp(run.started_at),
      value: (run) => run.started_at,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-small font-bold text-text-mute">Runs</p>
          <h1 className="font-display text-h2 text-text">Every run, newest first</h1>
          <p className="measure text-small text-text-dim">
            One row per batch of contacts dialled toward a single goal — outcomes update
            as calls settle.
          </p>
        </div>
        <Button asChild>
          <Link href="/app/runs/new">Start a run</Link>
        </Button>
      </div>

      <ConnectionBanner phase={phase} />

      <DataTable
        caption="Runs, with the campaign, status, and start time."
        columns={columns}
        rows={paged}
        rowKey={(run) => run.id}
        loading={loadingRuns && runs.length === 0}
        sort={sort}
        onSortChange={setSort}
        page={page}
        pageSize={pageSize}
        totalRows={runs.length}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
        onRowClick={(run) => router.push(`/app/runs/${run.id}`)}
        exportFileName="callflow-runs"
        mobileCard={(run) => (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate text-small font-medium text-text">
                {campaignName(run.campaign_id)}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-data tabular-nums text-text-mute">
                {run.completed}/{run.total} settled
              </span>
              <span className="font-mono text-data text-text-mute">
                {formatTimestamp(run.started_at)}
              </span>
            </div>
          </div>
        )}
        empty={
          <EmptyState
            icon={BroadcastIcon}
            title="No runs yet"
            body="Runs are how contacts get called. Start one to see the pipeline end to end."
            action={
              <Button asChild>
                <Link href="/app/runs/new">Start a run</Link>
              </Button>
            }
          />
        }
      />
    </div>
  );
}
