'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { ConnectionBanner } from '@/components/app/connection-banner';
import { EscalationCard } from '@/components/app/escalation-card';
import { ShareRequestDialog } from '@/components/app/share-request-dialog';
import { TranscriptView } from '@/components/app/transcript-view';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/app/page-header';
import { DialogRoot, Sheet } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import {
  api,
  type Escalation,
  type EscalationDirectoryEntry,
  type Member,
  type ShareRequest,
} from '@/lib/api';
import { useAppStore } from '@/lib/app-store';
import { Checkbox } from '@/components/ui/checkbox';
import { countUrgency } from '@/lib/escalation-age';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession } from '@/lib/hooks/use-session';

type SortOrder = 'oldest' | 'newest';

/** How many escalations render before the sentinel loads another page. */
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
  const toast = useToast();
  const { escalations, phase, loadingEscalations, refreshEscalations } =
    useAppStore();
  const session = useSession();
  const canAssign =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('escalations:assign');
  const canResolve =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('escalations:resolve');
  const canRequest =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('sharing:request') &&
    session.profile.active.role === 'operator';
  const [sortOrder, setSortOrder] = useState<SortOrder>('oldest');
  const [agentFilter, setAgentFilter] = useState('all');
  const [reasonFilter, setReasonFilter] = useState('all');
  const [selected, setSelected] = useState<Escalation | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [resolvingMany, setResolvingMany] = useState(false);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [visibleCountKey, setVisibleCountKey] = useState(
    `${agentFilter}|${reasonFilter}|${sortOrder}`,
  );
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const hasActiveFilters = agentFilter !== 'all' || reasonFilter !== 'all';

  function clearFilters() {
    setAgentFilter('all');
    setReasonFilter('all');
  }

  // Filters/sort changing means the page resets to the top - adjusting state
  // during render (not an effect) is the React-blessed way to do this, see
  // CLAUDE.md's note on preferring derived state over syncing in an effect.
  const filterKey = `${agentFilter}|${reasonFilter}|${sortOrder}`;
  if (filterKey !== visibleCountKey) {
    setVisibleCountKey(filterKey);
    setVisibleCount(PAGE_SIZE);
    // Cleared with the filters: a selection made against one view then acted on
    // in another would resolve items the person can no longer see.
    setSelectedIds(new Set());
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
    if (agentFilter !== 'all') {
      list = list.filter((item) => (item.agent_name ?? '') === agentFilter);
    }
    if (reasonFilter !== 'all') {
      list = list.filter((item) => item.disposition_reason === reasonFilter);
    }
    return sortOrder === 'oldest' ? list : [...list].reverse();
  }, [openEscalations, agentFilter, reasonFilter, sortOrder]);

  // Derived from the rows on screen rather than a second fetch of the org's
  // agents: the name is already on every escalation, and a filter can only
  // usefully offer values that actually appear in the list.
  const agentOptions = useMemo(
    () =>
      [...new Set(openEscalations.map((e) => e.agent_name).filter(Boolean))]
        .sort() as string[],
    [openEscalations],
  );

  const visible = shown.slice(0, visibleCount);
  const hasMore = shown.length > visible.length;

  const urgent = useMemo(
    () => countUrgency(openEscalations.map((e) => e.created_at)),
    [openEscalations],
  );

  // "All" means all *shown*, not all loaded - the checkbox sits above a list
  // that is filtered and paged, and selecting rows nobody can see would make
  // the count in the button a number the person never agreed to.
  const allVisibleSelected =
    visible.length > 0 && visible.every((e) => selectedIds.has(e.id));

  function toggleAllVisible(checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      for (const item of visible) {
        if (checked) next.add(item.id);
        else next.delete(item.id);
      }
      return next;
    });
  }

  function toggleOne(id: string, checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  async function resolveSelected() {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    setResolvingMany(true);
    try {
      const result = await api.resolveEscalations(ids);
      setSelectedIds(new Set());
      refreshEscalations();
      toast({
        tone: 'success',
        title: `${result.resolved.length} resolved`,
        // Partial success is normal on a queue two people work at once, and
        // saying so beats silently claiming all twenty.
        body:
          result.skipped > 0
            ? `${result.skipped} had already been handled by someone else.`
            : undefined,
      });
    } catch (e) {
      toast({
        tone: 'error',
        title: "Those escalations weren't resolved",
        body: e instanceof Error ? e.message : undefined,
      });
    } finally {
      setResolvingMany(false);
    }
  }

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || !hasMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setVisibleCount((count) => count + PAGE_SIZE);
        }
      },
      { rootMargin: '200px' },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasMore]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Needs a person" figure={openEscalations.length} />

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
              Agent
            </p>
            <Select
              value={agentFilter}
              onValueChange={setAgentFilter}
              options={[
                { value: 'all', label: 'All agents' },
                ...agentOptions.map((name) => ({ value: name, label: name })),
              ]}
              ariaLabel="Filter by agent"
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

          {hasActiveFilters && (
            <Button
              variant="ghost"
              onClick={() => {
                setAgentFilter('all');
                setReasonFilter('all');
              }}
            >
              Clear filters
            </Button>
          )}
        </div>
      ) : null}

      {/* How much of the queue has gone stale. Stated up front because the
          sort order alone cannot say it: oldest-first tells you which item is
          worst, not whether anything has been waiting since yesterday. */}
      {urgent.overdue > 0 || urgent.ageing > 0 ? (
        <p className="text-small text-text-dim">
          {urgent.overdue > 0 ? (
            <span className="font-medium text-text">
              {urgent.overdue} overdue
            </span>
          ) : null}
          {urgent.overdue > 0 && urgent.ageing > 0 ? ' · ' : null}
          {urgent.ageing > 0 ? `${urgent.ageing} waiting a while` : null}
        </p>
      ) : null}

      {/* Bulk resolve. The case it exists for is specific: a run fails to reach
          twenty contacts, every one lands here as unreachable, and clearing them
          one card at a time is twenty clicks of the same decision. */}
      {canResolve && shown.length > 0 ? (
        <div className="flex flex-wrap items-center gap-3 border-b border-rule pb-3">
          <Checkbox
            checked={
              selectedIds.size === 0
                ? false
                : allVisibleSelected
                  ? true
                  : 'indeterminate'
            }
            onCheckedChange={toggleAllVisible}
            label={`Select all ${visible.length} shown`}
          />
          {selectedIds.size > 0 ? (
            <>
              <span className="text-small text-text-dim">
                {selectedIds.size} selected
              </span>
              <Button
                size="sm"
                loading={resolvingMany}
                onClick={() => void resolveSelected()}
              >
                Mark {selectedIds.size} resolved
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedIds(new Set())}
              >
                Clear selection
              </Button>
            </>
          ) : null}
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
                  selected={selectedIds.has(escalation.id)}
                  onSelectedChange={
                    canResolve
                      ? (checked) => toggleOne(escalation.id, checked)
                      : undefined
                  }
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

/**
 * Open escalations elsewhere in the org - contact + agent + current
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
                    {entry.agent_name}
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
