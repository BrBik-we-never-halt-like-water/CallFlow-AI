'use client';

import { BroadcastIcon, FunnelIcon } from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';
import { ConnectionBanner } from '@/components/app/connection-banner';
import {
  DataTable,
  type Column,
  type SortState,
} from '@/components/app/data-table';
import { Lamp } from '@/components/brand/lamp';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/app/page-header';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { EmptyState } from '@/components/ui/empty-state';
import { SearchInput } from '@/components/ui/input';
import type { RunSummary } from '@/lib/api';
import { formatTimestamp } from '@/lib/format';
import { lampForRunStatus, type RunStatus } from '@/lib/lamp';
import { useAppStore } from '@/lib/app-store';
import { useSession } from '@/lib/hooks/use-session';

/**
 * This page no longer pins itself to the dark palette.
 *
 * It used to declare a `DARK_SCOPE_VARS` object re-scoping the generic
 * text/rule/surface/lamp tokens onto the `--dark-*` family, which forced
 * this one route dark regardless of the user's theme. That was right while
 * `/app` was mid-pivot and only some surfaces had converted; it is a bug now
 * that the shell carries `.dash` and the whole management surface follows
 * the theme. The bridge in globals.css already supplies exactly those
 * tokens, correctly, in both themes.
 */

const STATUS_FILTERS = (['running', 'completed', 'failed'] as RunStatus[]).map(
  (value) => ({ value, label: lampForRunStatus(value).label }),
);

export default function RunsPage() {
  const router = useRouter();
  const session = useSession();
  const canStart =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('runs:start');
  const { runs, phase, loadingRuns } = useAppStore();
  const [sort, setSort] = useState<SortState>({
    id: 'started_at',
    dir: 'desc',
  });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<Set<RunStatus>>(new Set());

  // The name is resolved server-side and carried on the row: the client no
  // longer holds an agent list, and fetching one just to render a label would
  // be a step backwards.
  const agentName = (run: RunSummary) =>
    run.agent_name ?? run.name ?? 'Deleted agent';

  const hasFilters = query.trim().length > 0 || statusFilter.size > 0;

  function clearFilters() {
    setQuery('');
    setStatusFilter(new Set());
  }

  /**
   * Search matches the agent name or the status label - the filter menu
   * covers the same status facet more precisely, so the free-text box stays
   * useful for "which agent" without needing to also open a menu.
   */
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return runs.filter((run) => {
      if (statusFilter.size > 0 && !statusFilter.has(run.status)) {
        return false;
      }
      if (!needle) return true;
      const name = agentName(run).toLowerCase();
      const statusLabel = lampForRunStatus(run.status).label.toLowerCase();
      return name.includes(needle) || statusLabel.includes(needle);
    });
  }, [runs, query, statusFilter]);

  /**
   * Sorting and pagination are done here rather than server-side because the runs
   * endpoint returns the whole list in one response. The DataTable's contract is
   * server-driven either way, so this swaps for a real query without touching it.
   */
  const sorted = useMemo(() => {
    const list = [...filtered];
    list.sort((a, b) => {
      const dir = sort.dir === 'asc' ? 1 : -1;
      switch (sort.id) {
        case 'agent':
          return agentName(a).localeCompare(agentName(b)) * dir;
        case 'total':
          return (a.total - b.total) * dir;
        case 'completed':
          return (a.completed - b.completed) * dir;
        case 'status':
          return a.status.localeCompare(b.status) * dir;
        default:
          return a.started_at.localeCompare(b.started_at) * dir;
      }
    });
    return list;
  }, [filtered, sort]);

  // Clamped rather than reset in an effect: if a filter shrinks the result set
  // below the current page, the displayed page snaps back on its own, and it
  // un-snaps just as automatically if the filter is loosened again.
  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const paged = useMemo(
    () => sorted.slice((safePage - 1) * pageSize, safePage * pageSize),
    [sorted, safePage, pageSize],
  );

  const columns: Column<RunSummary>[] = [
    {
      id: 'agent',
      header: 'Agent',
      sortable: true,
      cell: (run) => (
        <span className="block truncate text-text">
          {agentName(run)}
        </span>
      ),
      value: (run) => agentName(run),
    },
    {
      id: 'status',
      header: 'Status',
      sortable: true,
      cell: (run) => {
        const lamp = lampForRunStatus(run.status);
        return (
          <span className="inline-flex items-center gap-2 text-text">
            <Lamp state={lamp.state} size="sm" pulse={lamp.pulse} />
            {lamp.label}
          </span>
        );
      },
      value: (run) => lampForRunStatus(run.status).label,
    },
    {
      id: 'completed',
      header: 'Settled',
      align: 'right',
      mono: true,
      sortable: true,
      cell: (run) => `${run.completed}/${run.total}`,
      value: (run) => run.completed,
    },
    {
      id: 'started_at',
      header: 'Started',
      align: 'right',
      mono: true,
      sortable: true,
      cell: (run) => formatTimestamp(run.started_at),
      value: (run) => run.started_at,
    },
  ];

  return (
    <div
      className="app-canvas -mx-4 -my-6 flex min-h-[calc(100dvh-var(--h-app-topbar))] flex-col gap-6 px-4 py-6 sm:-mx-6 sm:px-6"
    >
      <PageHeader title="Runs">
        <div className="flex flex-wrap items-center gap-2">
          <SearchInput
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onClear={() => setQuery('')}
            placeholder="Search runs"
            aria-label="Search runs"
            className="h-10 w-full rounded-full sm:w-64"
          />

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="secondary"
                size="md"
                aria-label="Filter runs by status"
                className="relative w-10 shrink-0 px-0"
              >
                <FunnelIcon aria-hidden className="size-4" />
                {statusFilter.size > 0 ? (
                  <span
                    aria-hidden
                    className="absolute right-1.5 top-1.5 size-1.5 rounded-full bg-text"
                  />
                ) : null}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Filter by status</DropdownMenuLabel>
              {STATUS_FILTERS.map((option) => (
                <DropdownMenuCheckboxItem
                  key={option.value}
                  checked={statusFilter.has(option.value)}
                  onCheckedChange={(checked) =>
                    setStatusFilter((current) => {
                      const next = new Set(current);
                      if (checked) next.add(option.value);
                      else next.delete(option.value);
                      return next;
                    })
                  }
                >
                  {option.label}
                </DropdownMenuCheckboxItem>
              ))}
              {statusFilter.size > 0 ? (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onSelect={() => setStatusFilter(new Set())}>
                    Clear filter
                  </DropdownMenuItem>
                </>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>

          {canStart ? (
            <Button asChild>
              <Link href="/app/runs/new">Start a run</Link>
            </Button>
          ) : null}
        </div>
      </PageHeader>

      <ConnectionBanner phase={phase} />

      <DataTable
        caption="Runs, with the agent, status, and start time."
        columns={columns}
        rows={paged}
        rowKey={(run) => run.id}
        loading={loadingRuns && runs.length === 0}
        sort={sort}
        onSortChange={setSort}
        page={safePage}
        pageSize={pageSize}
        totalRows={sorted.length}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
        onRowClick={(run) => router.push(`/app/runs/${run.id}`)}
        exportFileName="callflow-runs"
        mobileCard={(run) => {
          const lamp = lampForRunStatus(run.status);
          return (
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate text-small font-medium text-text">
                  {agentName(run)}
                </span>
              </div>
              <div className="flex items-center gap-2 text-text">
                <Lamp state={lamp.state} size="sm" pulse={lamp.pulse} />
                <span className="text-small">{lamp.label}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-data tabular-nums text-text">
                  {run.completed}/{run.total} settled
                </span>
                <span className="font-mono text-data text-text-mute">
                  {formatTimestamp(run.started_at)}
                </span>
              </div>
            </div>
          );
        }}
        empty={
          runs.length === 0 ? (
            <EmptyState
              icon={BroadcastIcon}
              title="No runs yet"
              body="Runs are how contacts get called."
              action={
                canStart ? (
                  <Button asChild>
                    <Link href="/app/runs/new">Start a run</Link>
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <EmptyState
              icon={BroadcastIcon}
              title={query ? `No matches for "${query}"` : 'No runs match this filter'}
              body="Try a different search, or clear the filters."
              action={
                hasFilters ? (
                  <Button variant="secondary" onClick={clearFilters}>
                    Clear filters
                  </Button>
                ) : undefined
              }
            />
          )
        }
      />
    </div>
  );
}
