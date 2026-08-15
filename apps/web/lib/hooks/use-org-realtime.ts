'use client';

import { useEffect, useId, useRef } from 'react';
import type { RealtimePostgresChangesPayload } from '@supabase/supabase-js';
import { supabaseBrowser } from '@/lib/supabase/client';

/** Bursts (a fast back-and-forth, several members joining in a row) otherwise
 * cost one refetch per event - this coalesces a burst into the one refetch
 * that follows it, at a delay well under anything a person would notice. */
const DEBOUNCE_MS = 300;

/**
 * Refetch trigger for Postgres Changes on one table, scoped to one organisation.
 *
 * The `org_id=eq.${orgId}` filter is a bandwidth optimisation Supabase evaluates
 * server-side before it even considers sending an event - it is NOT the security
 * boundary. For `channels`/`messages`, row-level security (`channels_select`/
 * `messages_select`, both requiring `is_channel_member`) is what actually
 * authorises which rows a Postgres Changes event is delivered for at all: a
 * teammate who isn't a member of a channel never receives its events, no matter
 * what this hook's own filter says. Get the RLS policies right (the migration);
 * this hook is only a refetch trigger, never a permission check.
 *
 * On any insert/update/delete Realtime allows through, it calls `onChange(payload)`
 * - a refetch, not a direct cache mutation, matching every other data-loading
 * pattern in `lib/app-store.tsx`. The payload is passed through (not just an
 * empty trigger) so a caller watching one specific row - the currently open
 * conversation, say - can skip a refetch for a change that plainly isn't
 * about it, rather than re-fetching on every org-wide event on the table.
 */
export function useOrgRealtime(
  table: string,
  orgId: string | null,
  onChange: (payload: RealtimePostgresChangesPayload<Record<string, unknown>>) => void,
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
    const supabase = supabaseBrowser();
    const channel = supabase
      .channel(`realtime:${table}:${orgId}:${instanceId}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table, filter: `org_id=eq.${orgId}` },
        (payload) => {
          if (cancelled) return;
          if (timeout) clearTimeout(timeout);
          timeout = setTimeout(() => {
            if (!cancelled) onChangeRef.current(payload);
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
