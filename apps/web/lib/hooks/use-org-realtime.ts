'use client';

import { useEffect, useId, useRef } from 'react';
import type { RealtimePostgresChangesPayload } from '@supabase/supabase-js';
import { supabaseBrowser } from '@/lib/supabase/client';

/** Bursts (a fast back-and-forth, several members joining in a row) otherwise
 * cost one refetch per event - this coalesces a burst into the one refetch
 * that follows it, at a delay well under anything a person would notice. */
const DEBOUNCE_MS = 300;

/**
 * Live sync for one organisation's rows in a given table.
 *
 * `escalations` and `share_requests` were the first two tables in this product
 * wired to Supabase Realtime (`SYSTEM.md` F27); `channels`/`channel_members`/
 * `messages` (team chat) followed the same pattern rather than inventing a
 * second one - everything else is still 2.5s/4s polling.
 *
 * The `org_id=eq.${orgId}` filter is a bandwidth optimisation Supabase evaluates
 * server-side before it even considers sending an event - it is NOT the security
 * boundary. Each table's own `_select` RLS policy is what actually authorises
 * which rows a given subscriber receives events for at all - a teammate who
 * isn't a member of a channel, or isn't the assignee/owner an escalation or
 * share request is scoped to, never receives its events, no matter what this
 * hook's own filter says. Get the RLS policies right; this hook is only a
 * refetch trigger, never a permission check.
 *
 * On any insert/update/delete Realtime allows through, it calls
 * `onChange(payloads)` with every payload the debounce window coalesced - a
 * refetch, not a direct cache mutation, matching every other data-loading
 * pattern in `lib/app-store.tsx`. Payloads are passed through (not just an
 * empty trigger) so a caller watching one specific row - the currently open
 * chat conversation, say - can skip a refetch when NONE of them are about it,
 * rather than re-fetching on every org-wide event on the table. Callers that
 * don't need them (escalations, share requests) can just as well declare
 * `onChange: () => void` - the argument is harmless to ignore.
 *
 * The whole batch is delivered, not just the last payload in it: two events
 * landing within the same debounce window used to collapse to one callback
 * carrying only the most recent payload, which meant a caller filtering by
 * row id (chat's own `payloadChannelId` checks) silently dropped whichever
 * event lost the race - a message arriving in channel A while a burst was
 * mid-flight for channel B was never refetched at all. Accumulating into an
 * array and clearing it only when the timer actually fires keeps every event
 * while still coalescing the *refetch* to one per burst.
 */
export function useOrgRealtime(
  table: string,
  orgId: string | null,
  onChange: (payloads: RealtimePostgresChangesPayload<Record<string, unknown>>[]) => void,
): void {
  // A ref, not a dependency: the effect below re-subscribes when `table`/`orgId`
  // change, not merely because the caller passed a new function identity. Kept
  // current in its own effect rather than during render - a ref write belongs
  // outside render, same as any other side effect.
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  // supabase-js deduplicates `.channel(name)` calls by name within one client -
  // two independent callers of this hook for the same (table, orgId) (e.g. the
  // chat page's own list and the nav's unread-count badge, both watching
  // 'channels') would otherwise get handed back the *same* already-subscribed
  // channel object, and calling `.on()` on it a second time throws ("cannot add
  // postgres_changes callbacks ... after subscribe()") - silently breaking
  // Realtime for both. `useId()` gives each call site its own instance, so each
  // gets its own channel regardless of how many others watch the same table.
  const instanceId = useId();

  useEffect(() => {
    if (!orgId) return;

    let cancelled = false;
    let timeout: ReturnType<typeof setTimeout> | null = null;
    let pending: RealtimePostgresChangesPayload<Record<string, unknown>>[] = [];
    const supabase = supabaseBrowser();
    const channel = supabase
      .channel(`realtime:${table}:${orgId}:${instanceId}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table, filter: `org_id=eq.${orgId}` },
        (payload) => {
          if (cancelled) return;
          pending.push(payload);
          if (timeout) clearTimeout(timeout);
          timeout = setTimeout(() => {
            if (cancelled) return;
            const batch = pending;
            pending = [];
            onChangeRef.current(batch);
          }, DEBOUNCE_MS);
        },
      )
      .subscribe();

    return () => {
      cancelled = true;
      if (timeout) clearTimeout(timeout);
      void supabase.removeChannel(channel);
    };
  }, [table, orgId, instanceId]);
}
