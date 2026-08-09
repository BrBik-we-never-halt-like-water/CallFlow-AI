'use client';

import {
  BroadcastIcon,
  FunnelIcon,
  MagnifyingGlassIcon,
} from '@phosphor-icons/react/dist/ssr';
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

/**
 * `.dark-panel-glass`/`.dark-chrome` (globals.css) re-scope the generic text/
 * rule/surface/lamp tokens for a dark surface, and - since the coherence pass
 * that consolidated the dark theme's cross-page findings - also
 * `--glass-surface`/`--glass-border`/`--glass-blur`, the composite tokens
 * `.panel-glass` (`Panel`, `DataTable`'s table wrapper) and
 * `.btn-glass-secondary` (`Button`) read directly. That fix does not reach
 * this page's own root, though: it wraps its content in `.dark-canvas`
 * (the ambient gradient), not `.dark-panel-glass`/`.dark-chrome` - putting
 * either of *those* here instead would paint over the gradient with a flat
 * glass fill, since both classes set their own `background`. So this object
 * still needs to declare the glass three itself, alongside the generic set -
 * and it cannot lean on the `--surface-raised`/`--rule-strong` overrides
 * below to do it *indirectly*, tempting as that looks (`--glass-surface`/
 * `--glass-border` are `color-mix()`s of exactly those two names): Tailwind's
 * `@theme inline` bakes `--glass-surface`/`--glass-border`'s own declaration
 * at `:root` into a static literal at build time, using `:root`'s own (light)
 * values, so overriding `--surface-raised`/`--rule-strong` further down the
 * tree never actually reaches them - confirmed by computed style, not
 * assumed. Only a direct redeclaration of the three names themselves, as
 * done here, works.
 */
const DARK_SCOPE_VARS: React.CSSProperties = {
  '--text': 'var(--dark-text)',
  '--text-dim': 'var(--dark-text-dim)',
  '--text-mute': 'var(--dark-text-mute)',
  '--rule': 'var(--dark-rule)',
  '--rule-strong': 'var(--dark-rule-strong)',
  '--surface-raised': 'var(--dark-surface)',
  '--surface-hover': 'var(--dark-surface-hover)',
  '--surface-sunken': 'var(--dark-surface-sunken)',
  '--glass-surface': 'var(--dark-glass-surface)',
  '--glass-border': 'var(--dark-glass-border)',
  '--glass-blur': 'var(--dark-glass-blur)',
  '--lamp-off': 'var(--dark-lamp-off)',
  '--lamp-ice': 'var(--dark-lamp-ice)',
  '--lamp-brass': 'var(--dark-lamp-brass)',
  '--lamp-jade': 'var(--dark-lamp-jade)',
  '--lamp-flare': 'var(--dark-lamp-flare)',
  '--lamp-off-text': 'var(--dark-lamp-off-text)',
  '--lamp-ice-text': 'var(--dark-lamp-ice-text)',
  '--lamp-brass-text': 'var(--dark-lamp-brass-text)',
  '--lamp-jade-text': 'var(--dark-lamp-jade-text)',
  '--lamp-flare-text': 'var(--dark-lamp-flare-text)',
} as React.CSSProperties;

const STATUS_FILTERS = (
  ['running', 'canceling', 'canceled', 'completed', 'failed'] as RunStatus[]
).map((value) => ({ value, label: lampForRunStatus(value).label }));

export default function RunsPage() {
  const router = useRouter();
  const { runs, campaigns, phase, loadingRuns } = useAppStore();
  const [sort, setSort] = useState<SortState>({
    id: 'started_at',
    dir: 'desc',
  });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [query, setQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<Set<RunStatus>>(new Set());

  const campaignName = (id: string) =>
    campaigns.find((c) => c.id === id)?.name ?? id;

  const hasFilters = query.trim().length > 0 || statusFilter.size > 0;

  function clearFilters() {
    setQuery('');
    setStatusFilter(new Set());
  }

  /**
   * Search matches the campaign name or the status label - the filter menu
   * covers the same status facet more precisely, so the free-text box stays
   * useful for "which campaign" without needing to also open a menu.
   */
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return runs.filter((run) => {
      if (statusFilter.size > 0 && !statusFilter.has(run.status)) {
        return false;
      }
      if (!needle) return true;
      const name = campaignName(run.campaign_id).toLowerCase();
      const statusLabel = lampForRunStatus(run.status).label.toLowerCase();
      return name.includes(needle) || statusLabel.includes(needle);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runs, query, statusFilter, campaigns]);

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
        case 'campaign':
          return (
            campaignName(a.campaign_id).localeCompare(
              campaignName(b.campaign_id),
            ) * dir
          );
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtered, sort, campaigns]);

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
      id: 'campaign',
      header: 'Campaign',
      sortable: true,
      cell: (run) => (
        <span className="block truncate text-text">
          {campaignName(run.campaign_id)}
        </span>
      ),
      value: (run) => campaignName(run.campaign_id),
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
      className="dark-canvas -mx-4 -my-6 flex min-h-[calc(100dvh-var(--h-app-topbar))] flex-col gap-6 px-4 py-6 sm:-mx-6 sm:px-6"
      style={DARK_SCOPE_VARS}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-small font-bold text-text-mute">Runs</p>
          <h1 className="font-display text-h2 text-text">
            Every run, newest first
          </h1>
          <p className="measure text-small text-text-dim">
            Outcomes update as calls settle.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {searchOpen || query ? (
            <SearchInput
              autoFocus={searchOpen}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onClear={() => {
                setQuery('');
                setSearchOpen(false);
              }}
              onBlur={() => {
                if (!query) setSearchOpen(false);
              }}
              placeholder="Search runs"
              aria-label="Search runs"
              className="h-10 w-48 rounded-full sm:w-64"
            />
          ) : (
            <button
              type="button"
              aria-label="Search runs"
              onClick={() => setSearchOpen(true)}
              className="flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-full border border-rule text-text-dim transition-colors hover:bg-surface-hover hover:text-text"
            >
              <MagnifyingGlassIcon aria-hidden weight="bold" className="size-4" />
            </button>
          )}

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

          <Button asChild>
            <Link href="/app/runs/new">Start a run</Link>
          </Button>
        </div>
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
                  {campaignName(run.campaign_id)}
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
                <Button asChild>
                  <Link href="/app/runs/new">Start a run</Link>
                </Button>
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
