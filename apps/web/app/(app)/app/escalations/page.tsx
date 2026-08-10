'use client';

import { useCallback, useMemo, useState } from 'react';
import { cn } from '@/lib/cn';
import { ConnectionBanner } from '@/components/app/connection-banner';
import { EscalationCard } from '@/components/app/escalation-card';
import { TranscriptView } from '@/components/app/transcript-view';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import type { Outcome } from '@/lib/api';
import { useAppStore } from '@/lib/app-store';

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
  const { escalations, campaigns, phase, loadingRuns } = useAppStore();
  const [sortOrder, setSortOrder] = useState<SortOrder>('oldest');
  const [campaignFilter, setCampaignFilter] = useState('all');
  const [reasonFilter, setReasonFilter] = useState('all');
  const [selected, setSelected] = useState<Outcome | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [visibleCountKey, setVisibleCountKey] = useState(
    `${campaignFilter}|${reasonFilter}|${sortOrder}`,
  );

  const hasActiveFilters = campaignFilter !== 'all' || reasonFilter !== 'all';

  function clearFilters() {
    setCampaignFilter('all');
    setReasonFilter('all');
  }

  /** Reasons actually present, so the filter never offers an empty option. */
  const reasons = useMemo(() => {
    const found = new Set<string>();
    for (const item of escalations) {
      if (item.disposition_reason) found.add(item.disposition_reason);
    }
    return [...found];
  }, [escalations]);

  const shown = useMemo(() => {
    let list = escalations;
    if (campaignFilter !== 'all') {
      list = list.filter((item) => item.campaign_id === campaignFilter);
    }
    if (reasonFilter !== 'all') {
      list = list.filter((item) => item.disposition_reason === reasonFilter);
    }
    return sortOrder === 'oldest' ? list : [...list].reverse();
  }, [escalations, campaignFilter, reasonFilter, sortOrder]);

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
            {escalations.length === 0
              ? 'Nothing needs you'
              : `${escalations.length} waiting`}
          </h1>
          <p className="measure text-small text-text-dim">
            {escalations.length > 0
              ? 'Oldest first - the longest wait is the most expensive one.'
              : 'Escalations land here when someone sounds frustrated, asks to opt out, or asks for a person.'}
          </p>
        </div>
      </div>

      <ConnectionBanner phase={phase} />

      {escalations.length > 0 ? (
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

      {loadingRuns && escalations.length === 0 ? (
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
              escalations.length === 0
                ? 'Nothing needs you right now'
                : 'No escalations match those filters'
            }
            body={
              escalations.length === 0
                ? "When calls come in, they'll appear in this queue."
                : 'Clear the filters to see the whole queue.'
            }
            action={
              escalations.length > 0 ? (
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
            {visible.map((outcome, i) => (
              <li key={`${outcome.contact_name}-${outcome.created_at}-${i}`}>
                <EscalationCard
                  outcome={outcome}
                  onOpen={() => setSelected(outcome)}
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
