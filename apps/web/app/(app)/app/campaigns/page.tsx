'use client';

import {
  MagnifyingGlassIcon,
  MegaphoneIcon,
  PlusIcon,
  SlidersIcon,
} from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';
import { CampaignCard } from '@/components/app/campaign-card';
import { ConnectionBanner } from '@/components/app/connection-banner';
import { ShareRequestDialog } from '@/components/app/share-request-dialog';
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
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { SearchInput } from '@/components/ui/input';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import {
  api,
  type Campaign,
  type CampaignDirectoryEntry,
  type ShareRequest,
} from '@/lib/api';
import { useAppStore } from '@/lib/app-store';
import { CAMPAIGN_DRAFT_KEY } from '@/lib/campaign-draft';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession } from '@/lib/hooks/use-session';
import type { RunStatus } from '@/lib/lamp';

type TypeFilter = 'all' | 'template' | 'custom';
type StatusFilter = 'all' | 'not_run' | RunStatus;

const STATUS_FILTER_LABEL: Record<StatusFilter, string> = {
  all: 'All',
  not_run: 'Not run yet',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
};

export default function CampaignsPage() {
  const router = useRouter();
  const toast = useToast();
  const session = useSession();
  const permissions =
    session.status === 'signed-in' ? session.profile.permissions : [];
  const canWrite = permissions.includes('campaigns:write');
  const canDelete = permissions.includes('campaigns:delete');
  const canStart = permissions.includes('runs:start');
  // Only an operator's own list is narrowed by Phase 1's RLS - admin/owner/
  // viewer already see every campaign above, so the directory would just
  // be a confusing, redundant second list for them.
  const showDirectory =
    session.status === 'signed-in' && session.profile.active.role === 'operator';
  const { campaigns, hydratedRuns, phase, refresh } = useAppStore();
  const [search, setSearch] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [pendingDelete, setPendingDelete] = useState<Campaign | null>(null);
  const [deleting, setDeleting] = useState(false);

  /** The most recent run per campaign, for each card's status lamp. */
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

  const builtInCount = campaigns.filter((c) => c.built_in).length;
  const customCount = campaigns.length - builtInCount;

  const shown = useMemo(() => {
    const query = search.trim().toLowerCase();
    return campaigns.filter((campaign) => {
      if (query && !campaign.name.toLowerCase().includes(query)) return false;
      if (typeFilter === 'template' && !campaign.built_in) return false;
      if (typeFilter === 'custom' && campaign.built_in) return false;
      if (statusFilter !== 'all') {
        const status = lastRunByCampaign.get(campaign.id)?.status ?? 'not_run';
        if (status !== statusFilter) return false;
      }
      return true;
    });
  }, [campaigns, search, typeFilter, statusFilter, lastRunByCampaign]);

  const filtersActive = typeFilter !== 'all' || statusFilter !== 'all';

  function clearFilters() {
    setTypeFilter('all');
    setStatusFilter('all');
  }

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
      /* storage unavailable - the editor opens empty, which is recoverable */
    }
    router.push('/app/campaigns/new');
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await api.deleteCampaign(pendingDelete.id);
      toast({ tone: 'success', title: 'Campaign deleted' });
      setPendingDelete(null);
      refresh();
      // The campaign list lives on the connection hook, which loads once - a reload is
      // the honest way to reflect the deletion until that becomes refetchable.
      router.refresh();
    } catch (error) {
      toast({
        tone: 'error',
        title: "That campaign wasn't deleted",
        body:
          error instanceof Error
            ? error.message
            : "The service didn't respond.",
      });
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-2xl font-bold text-text">Campaigns</p>

          <div className="flex items-center gap-2">
            {searchOpen || search ? (
              <SearchInput
                autoFocus={searchOpen}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                onClear={() => {
                  setSearch('');
                  setSearchOpen(false);
                }}
                onBlur={() => {
                  if (!search) setSearchOpen(false);
                }}
                placeholder="Search campaigns"
                aria-label="Search campaigns by name"
                className="h-10 w-48 rounded-full sm:w-64"
              />
            ) : (
              <button
                type="button"
                aria-label="Search campaigns"
                onClick={() => setSearchOpen(true)}
                className="flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-full border border-rule text-text-dim transition-colors hover:bg-surface-hover hover:text-text"
              >
                <MagnifyingGlassIcon aria-hidden weight="bold" className="size-4" />
              </button>
            )}

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  aria-label="Filter campaigns"
                  className={
                    'flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-full border transition-colors hover:bg-surface-hover ' +
                    (filtersActive
                      ? 'border-rule-strong text-text'
                      : 'border-rule text-text-dim hover:text-text')
                  }
                >
                  <SlidersIcon aria-hidden weight="bold" className="size-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuLabel>Type</DropdownMenuLabel>
                <DropdownMenuCheckboxItem
                  checked={typeFilter === 'template'}
                  onCheckedChange={(checked) =>
                    setTypeFilter(checked ? 'template' : 'all')
                  }
                >
                  Templates · {builtInCount}
                </DropdownMenuCheckboxItem>
                <DropdownMenuCheckboxItem
                  checked={typeFilter === 'custom'}
                  onCheckedChange={(checked) =>
                    setTypeFilter(checked ? 'custom' : 'all')
                  }
                >
                  Yours · {customCount}
                </DropdownMenuCheckboxItem>

                <DropdownMenuSeparator />

                <DropdownMenuLabel>Status</DropdownMenuLabel>
                {(['not_run', 'running', 'completed', 'failed'] as const).map(
                  (value) => (
                    <DropdownMenuCheckboxItem
                      key={value}
                      checked={statusFilter === value}
                      onCheckedChange={(checked) =>
                        setStatusFilter(checked ? value : 'all')
                      }
                    >
                      {STATUS_FILTER_LABEL[value]}
                    </DropdownMenuCheckboxItem>
                  ),
                )}

                {filtersActive ? (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onSelect={clearFilters}>
                      Clear filters
                    </DropdownMenuItem>
                  </>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>

            {canWrite ? (
              <Link
                href="/app/campaigns/new"
                aria-label="New campaign"
                className="flex size-10 shrink-0 items-center justify-center rounded-full border border-rule text-text-dim transition-colors hover:bg-surface-hover hover:text-text"
              >
                <PlusIcon aria-hidden weight="bold" className="size-4" />
              </Link>
            ) : null}
          </div>
        </div>

        <ConnectionBanner phase={phase} />

        {phase === 'connecting' ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }, (_, i) => (
              <Panel
                key={i}
                className="panel-glass flex flex-col gap-3 p-4"
              >
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-2/3" />
                <Skeleton className="mt-2 h-3 w-24" />
              </Panel>
            ))}
          </div>
        ) : campaigns.length === 0 ? (
          <Panel className="panel-glass">
            <EmptyState
              icon={MegaphoneIcon}
              title="No campaigns yet"
              body="Start from a template, or write your own."
              action={
                canWrite ? (
                  <Button asChild>
                    <Link href="/app/campaigns/new">New campaign</Link>
                  </Button>
                ) : undefined
              }
            />
          </Panel>
        ) : shown.length === 0 ? (
          <Panel className="panel-glass">
            <EmptyState
              icon={MegaphoneIcon}
              title="No campaigns match"
              body="Try a different search, or clear the filters."
              action={
                <Button variant="secondary" onClick={clearFilters}>
                  Clear filters
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
                  canWrite={canWrite}
                  canDelete={canDelete}
                  canStart={canStart}
                />
              </li>
            ))}
          </ul>
        )}

        {showDirectory ? (
          <TeamCampaignsDirectory ownedIds={new Set(campaigns.map((c) => c.id))} />
        ) : null}
      </div>

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
              <Button
                variant="secondary"
                onClick={() => setPendingDelete(null)}
              >
                Keep it
              </Button>
              <Button
                variant="danger"
                loading={deleting}
                onClick={confirmDelete}
              >
                Delete campaign
              </Button>
            </>
          }
        />
      </DialogRoot>
    </>
  );
}

/**
 * What else exists to ask for - name and owner only, never a teammate's
 * goal template or fields (role-based UI roadmap, Phase 4). Only rendered
 * for operators; RLS already narrows the main list above to their own, so
 * this is the one place they can see - and request - the rest.
 */
function TeamCampaignsDirectory({ ownedIds }: { ownedIds: Set<string> }) {
  const toast = useToast();
  const [directory, setDirectory] = useState<CampaignDirectoryEntry[] | null>(
    null,
  );
  const [myRequests, setMyRequests] = useState<ShareRequest[]>([]);
  const [target, setTarget] = useState<CampaignDirectoryEntry | null>(null);

  function load() {
    api
      .campaignDirectory()
      .then(setDirectory)
      .catch(() => setDirectory([]));
    api
      .listShareRequests()
      .then(setMyRequests)
      .catch(() => toast({ tone: 'error', title: "Couldn't load your requests" }));
  }

  useOrgScopedEffect(() => {
    load();
  });

  const notMine = (directory ?? []).filter((c) => !ownedIds.has(c.id));
  const pendingFor = new Set(
    myRequests
      .filter((r) => r.resource_type === 'campaign' && r.status === 'pending')
      .map((r) => r.resource_id),
  );

  if (directory !== null && notMine.length === 0) return null;

  return (
    <>
      <Panel className="dark-panel-glass flex flex-col gap-3 p-5 sm:p-6">
        <div className="flex flex-col gap-1">
          <p className="text-small font-bold text-text-mute">
            Team campaigns
          </p>
          <p className="text-small text-text-dim">
            Campaigns your teammates made. Ask to use one - they decide.
          </p>
        </div>

        {directory === null ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : (
          <ul className="flex flex-col divide-y divide-rule">
            {notMine.map((entry) => (
              <li
                key={entry.id}
                className="flex flex-wrap items-center justify-between gap-3 py-2.5"
              >
                <div className="flex min-w-0 flex-col">
                  <span className="truncate text-small font-medium text-text">
                    {entry.name}
                  </span>
                  <span className="text-small text-text-dim">
                    {entry.owner_name || 'Unowned'}
                  </span>
                </div>
                {pendingFor.has(entry.id) ? (
                  <Button variant="secondary" size="sm" disabled>
                    Requested
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setTarget(entry)}
                  >
                    Request access
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <ShareRequestDialog
        open={target !== null}
        onOpenChange={(open) => !open && setTarget(null)}
        resourceType="campaign"
        resourceId={target?.id ?? null}
        resourceLabel={target?.name ?? ''}
        onRequested={load}
      />
    </>
  );
}
