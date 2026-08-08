'use client';

import { useMemo, useState } from 'react';
import { ConnectionBanner } from '@/components/app/connection-banner';
import { EscalationCard } from '@/components/app/escalation-card';
import { TranscriptView } from '@/components/app/transcript-view';
import { Button } from '@/components/ui/button';
import { DialogRoot, Sheet } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import type { Outcome } from '@/lib/api';
import { useAppStore } from '@/lib/app-store';

type SortOrder = 'oldest' | 'newest';

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

          {(campaignFilter !== 'all' || reasonFilter !== 'all') && (
            <Button
              variant="ghost"
              onClick={() => {
                setCampaignFilter('all');
                setReasonFilter('all');
              }}
            >
              Clear filters
            </Button>
          )}
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
                <Button
                  variant="secondary"
                  onClick={() => {
                    setCampaignFilter('all');
                    setReasonFilter('all');
                  }}
                >
                  Clear filters
                </Button>
              ) : undefined
            }
          />
        </Panel>
      ) : (
        <ul className="flex flex-col gap-3">
          {shown.map((outcome, i) => (
            <li key={`${outcome.contact_name}-${outcome.created_at}-${i}`}>
              <EscalationCard
                outcome={outcome}
                onOpen={() => setSelected(outcome)}
              />
            </li>
          ))}
        </ul>
      )}

      <DialogRoot
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        {selected ? (
          <Sheet
            title={selected.contact_name}
            description={selected.disposition_reason ?? 'Needs a person'}
          >
            <TranscriptView outcome={selected} />
          </Sheet>
        ) : null}
      </DialogRoot>
    </div>
  );
}
