'use client';

import { useCallback, useMemo, useState } from 'react';
import { cn } from '@/lib/cn';
import { ConnectionBanner } from '@/components/app/connection-banner';
import { EscalationCard } from '@/components/app/escalation-card';
import { ShareRequestDialog } from '@/components/app/share-request-dialog';
import { TranscriptView } from '@/components/app/transcript-view';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import {
  api,
  type Campaign,
  type Escalation,
  type EscalationDirectoryEntry,
  type Member,
  type ShareRequest,
} from '@/lib/api';
import { useAppStore } from '@/lib/app-store';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession } from '@/lib/hooks/use-session';

type SortOrder = 'oldest' | 'newest';

/** How many cards render at once, and how many more load per scroll step -
 * the whole list already lives in memory (`useAppStore`'s hydrated runs),
 * so this bounds DOM node count for a long queue, not network requests. */
const PAGE_SIZE = 20;

/**
 * Needs a person - a worklist, not a table dump.
 *
 * Sorted oldest first by default, and that default is the design. The oldest escalation
 * is the most expensive one: somebody was frustrated, nobody has called them back, and
 * every hour that passes makes the callback harder. A newest-first list would bury
 * exactly the item that most needs attention.
 */
export default function EscalationsPage() {
  const { escalations, phase, loadingEscalations } = useAppStore();
  const session = useSession();
  const canAssign =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('escalations:assign');
  const canRequest =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('sharing:request') &&
    session.profile.active.role === 'operator';
  const [sortOrder, setSortOrder] = useState<SortOrder>('oldest');
  const [campaignFilter, setCampaignFilter] = useState('all');
  const [reasonFilter, setReasonFilter] = useState('all');
  const [selected, setSelected] = useState<Escalation | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [visibleCountKey, setVisibleCountKey] = useState(
    `${campaignFilter}|${reasonFilter}|${sortOrder}`,
  );

  const hasActiveFilters = campaignFilter !== 'all' || reasonFilter !== 'all';

  function clearFilters() {
    setCampaignFilter('all');
    setReasonFilter('all');
  }

  // Fetched once here, not per card - every EscalationCard on this page
  // would otherwise duplicate the same team-roster request for its own
  // "Reassign" picker.
  useOrgScopedEffect(() => {
    if (!canAssign) return;
    api
      .listMembers()
      .then((team) => setMembers(team.members))
      .catch(() => setMembers([]));
  }, [canAssign]);

  // For the campaign filter and each card's campaign-name tag - not part of
  // `useAppStore()`, which only ever hydrated recent runs' own campaigns,
  // not the org's full list.
  useOrgScopedEffect(() => {
    api
      .campaigns()
      .then(setCampaigns)
      .catch(() => setCampaigns([]));
  }, []);

  // A resolved escalation stays a real row now (ISSUES.md #7) rather than
  // vanishing from the list the moment it's actioned - this worklist still
  // only shows what's waiting, matching how it always read before.
  const openEscalations = useMemo(
    () => escalations.filter((e) => e.escalation_status === 'open'),
    [escalations],
  );

  /** Reasons actually present, so the filter never offers an empty option. */
  const reasons = useMemo(() => {
    const found = new Set<string>();
    for (const item of openEscalations) {
      if (item.disposition_reason) found.add(item.disposition_reason);
    }
    return [...found];
  }, [openEscalations]);

  const shown = useMemo(() => {
    let list = openEscalations;
    if (campaignFilter !== 'all') {
      list = list.filter((item) => item.campaign_id === campaignFilter);
    }
    if (reasonFilter !== 'all') {
      list = list.filter((item) => item.disposition_reason === reasonFilter);
    }
    return sortOrder === 'oldest' ? list : [...list].reverse();
  }, [openEscalations, campaignFilter, reasonFilter, sortOrder]);

  // A filter/sort change invalidates the current scroll window - starting over
  // at PAGE_SIZE avoids showing a tail end of items that no longer match, or a
  // window sized for a since-shrunk list. Adjusted during render (React's
  // documented pattern for resetting state from a prop-like change) rather
  // than in an effect, which would commit the stale window for one frame
  // before a second render corrected it.
  const nextVisibleCountKey = `${campaignFilter}|${reasonFilter}|${sortOrder}`;
  if (nextVisibleCountKey !== visibleCountKey) {
    setVisibleCountKey(nextVisibleCountKey);
    setVisibleCount(PAGE_SIZE);
  }

  const visible = useMemo(() => shown.slice(0, visibleCount), [shown, visibleCount]);
  const hasMore = visibleCount < shown.length;

  /**
   * Loads the next page when the sentinel below the list scrolls into view.
   * A `ref` callback rather than a `ref` object so the observer attaches
   * and detaches exactly when the sentinel itself mounts/unmounts (React
   * 19's ref-cleanup-function support) - it only exists while `hasMore` is
   * true, so there's nothing to observe once the whole list is showing.
   */
  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (!node) return;
      const observer = new IntersectionObserver((entries) => {
        if (entries[0]?.isIntersecting) {
          setVisibleCount((count) => count + PAGE_SIZE);
        }
      });
      observer.observe(node);
      return () => observer.disconnect();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [hasMore],
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-small font-bold text-text-mute">Needs a person</p>
          <h1 className="font-display text-h2 text-text">
            {openEscalations.length === 0
              ? 'Nothing needs you'
              : `${openEscalations.length} waiting`}
          </h1>
          <p className="measure text-small text-text-dim">
            {openEscalations.length > 0
              ? 'Oldest first - the longest wait is the most expensive one.'
              : 'Escalations land here when someone sounds frustrated, asks to opt out, or asks for a person.'}
          </p>
        </div>
      </div>

      <ConnectionBanner phase={phase} />

      {openEscalations.length > 0 ? (
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-44">
            <p className="mb-1.5 text-small font-bold text-text-mute">Sort</p>
            <Select
              value={sortOrder}
              onValueChange={(v) => setSortOrder(v as SortOrder)}
              options={[
                { value: 'oldest', label: 'Oldest first' },
                { value: 'newest', label: 'Newest first' },
              ]}
              ariaLabel="Sort escalations"
            />
          </div>

          <div className="w-52">
            <p className="mb-1.5 text-small font-bold text-text-mute">
              Campaign
            </p>
            <Select
              value={campaignFilter}
              onValueChange={setCampaignFilter}
              options={[
                { value: 'all', label: 'All campaigns' },
                ...campaigns.map((c) => ({ value: c.id, label: c.name })),
              ]}
              ariaLabel="Filter by campaign"
            />
          </div>

          {reasons.length > 0 ? (
            <div className="w-56">
              <p className="mb-1.5 text-small font-bold text-text-mute">
                Reason
              </p>
              <Select
                value={reasonFilter}
                onValueChange={setReasonFilter}
                options={[
                  { value: 'all', label: 'Any reason' },
                  ...reasons.map((reason) => ({
                    value: reason,
                    label: reason,
                  })),
                ]}
                ariaLabel="Filter by reason"
              />
            </div>
          ) : null}

          {/* Always mounted, space reserved either way - toggling this in
              and out of the layout (the previous behaviour) shifted every
              control next to it the instant a filter was picked, which read
              as the filter row "breaking" rather than just updating. */}
          <Button
            variant="ghost"
            onClick={clearFilters}
            className={cn(!hasActiveFilters && 'invisible')}
            aria-hidden={!hasActiveFilters}
            tabIndex={hasActiveFilters ? undefined : -1}
          >
            Clear filters
          </Button>
        </div>
      ) : null}

      {loadingEscalations && openEscalations.length === 0 ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }, (_, i) => (
            <Panel key={i} className="flex flex-col gap-3 p-4">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-64" />
              <Skeleton className="h-8 w-48" />
            </Panel>
          ))}
        </div>
      ) : shown.length === 0 ? (
        <Panel>
          <EmptyState
            title={
              openEscalations.length === 0
                ? 'Nothing needs you right now'
                : 'No escalations match those filters'
            }
            body={
              openEscalations.length === 0
                ? "When calls come in, they'll appear in this queue."
                : 'Clear the filters to see the whole queue.'
            }
            action={
              openEscalations.length > 0 ? (
                <Button variant="secondary" onClick={clearFilters}>
                  Clear filters
                </Button>
              ) : undefined
            }
          />
        </Panel>
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {visible.map((escalation) => (
              <li key={escalation.id}>
                <EscalationCard
                  escalation={escalation}
                  members={members}
                  campaigns={campaigns}
                  onOpen={() => setSelected(escalation)}
                />
              </li>
            ))}
          </ul>

          {hasMore ? (
            <div ref={sentinelRef} className="flex justify-center py-2">
              <Skeleton className="h-20 w-full" />
            </div>
          ) : null}
        </>
      )}

      {canRequest ? (
        <TeamEscalationsDirectory
          ownedIds={new Set(escalations.map((e) => e.id))}
        />
      ) : null}

      <DialogRoot
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        {selected ? (
          <Dialog
            title={selected.contact_name}
            description={selected.disposition_reason ?? 'Needs a person'}
            size="xl"
            contentClassName=""
          >
            <TranscriptView outcome={selected} />
          </Dialog>
        ) : null}
      </DialogRoot>
    </div>
  );
}

/**
 * Open escalations elsewhere in the org - contact + campaign + current
 * owner only, never the transcript or reasoning chain (role-based UI
 * roadmap, Phase 4). Only rendered for operators with `sharing:request`.
 */
function TeamEscalationsDirectory({ ownedIds }: { ownedIds: Set<string> }) {
  const toast = useToast();
  const [directory, setDirectory] = useState<
    EscalationDirectoryEntry[] | null
  >(null);
  const [myRequests, setMyRequests] = useState<ShareRequest[]>([]);
  const [target, setTarget] = useState<EscalationDirectoryEntry | null>(null);

  function load() {
    api
      .escalationDirectory()
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

  const notMine = (directory ?? []).filter((e) => !ownedIds.has(e.id));
  const pendingFor = new Set(
    myRequests
      .filter((r) => r.resource_type === 'escalation' && r.status === 'pending')
      .map((r) => r.resource_id),
  );

  if (directory !== null && notMine.length === 0) return null;

  return (
    <>
      <Panel className="dark-panel-glass flex flex-col gap-3 p-5 sm:p-6">
        <div className="flex flex-col gap-1">
          <p className="text-small font-bold text-text-mute">
            Team escalations
          </p>
          <p className="text-small text-text-dim">
            Open items assigned to teammates. Offer to help - they decide.
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
                    {entry.contact_name}
                  </span>
                  <span className="text-small text-text-dim">
                    {entry.campaign_name}
                    {entry.owner_name ? ` · ${entry.owner_name}` : ''}
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
                    Request to help
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
        resourceType="escalation"
        resourceId={target?.id ?? null}
        resourceLabel={target?.contact_name ?? ''}
        onRequested={load}
      />
    </>
  );
}
