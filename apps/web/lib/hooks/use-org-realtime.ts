'use client';

import { useEffect } from 'react';
import { supabaseBrowser } from '@/lib/supabase/client';

/**
 * Live sync for one organisation's rows in a given table.
 *
 * Fires `onChange` whenever any row this organisation owns is inserted or
 * updated - the callback is the signal to refetch the real endpoint, not a
 * payload to merge by hand: Postgres Changes delivers bare row columns, not
 * whatever joined display fields (a contact's name, an assignee's name) the
 * real endpoint returns.
 *
 * `escalations` and `share_requests` are the two tables in this product
 * wired to Supabase Realtime so far (`SYSTEM.md` F27 - everything else is
 * still 2.5s/4s polling). Each table's own `_select` RLS policy is what
 * actually scopes which rows a given subscriber receives events for -
 * Supabase's Postgres Changes authorises every event against the
 * subscriber's session the same way a normal query would. The `org_id`
 * filter below is a bandwidth optimisation on top of that, evaluated
 * server-side before an event is even sent, not the security boundary
 * itself - never rely on it as one.
 */
export function useOrgRealtime(
  table: string,
  orgId: string | null,
  onChange: () => void,
): void {
  useEffect(() => {
    if (!orgId) return;

    const channel = supabaseBrowser()
      .channel(`${table}:${orgId}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table,
          filter: `org_id=eq.${orgId}`,
        },
        onChange,
      )
      .subscribe();

    return () => {
      void supabaseBrowser().removeChannel(channel);
    };
  }, [table, orgId, onChange]);
}
