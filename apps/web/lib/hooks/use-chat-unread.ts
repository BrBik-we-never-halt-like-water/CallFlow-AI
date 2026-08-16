'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useOrgRealtime } from '@/lib/hooks/use-org-realtime';
import { useSession } from '@/lib/hooks/use-session';

/**
 * Total unread messages across every conversation, for the "Chat" nav badge.
 *
 * Deliberately its own small fetch rather than reading from `AppStoreProvider`
 * (`lib/app-store.tsx`) - that store is deep, shared infrastructure for
 * runs/escalations/safety, and chat's own page already does its own channel
 * fetching for the list view. Keeping the badge's data self-contained here
 * costs one extra small request but means a mistake in this hook can't
 * regress the dashboard/runs/escalations the store already powers.
 */
export function useChatUnreadCount(): number {
  const session = useSession();
  const orgId =
    session.status === 'signed-in' ? session.profile.active.org_id : null;

  // Tagged with the org it belongs to, reset during render the instant the
  // org changes - same discipline `chat-shell.tsx`'s `view`/`channelDetail`
  // use for their own id-keyed state - rather than a synchronous setState at
  // the top of an effect.
  const [state, setState] = useState<{ orgId: string | null; count: number }>({
    orgId: null,
    count: 0,
  });
  if (state.orgId !== orgId) {
    setState({ orgId, count: 0 });
  }

  function refetch() {
    if (!orgId) return;
    api
      .getUnreadCount()
      .then(({ unread_count }) =>
        setState((current) => (current.orgId === orgId ? { orgId, count: unread_count } : current)),
      )
      .catch(() => undefined);
  }

  useEffect(() => {
    if (!orgId) return;
    let cancelled = false;
    api
      .getUnreadCount()
      .then(({ unread_count }) => {
        if (!cancelled) setState({ orgId, count: unread_count });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  // A new message, a mark-as-read, or a membership change (added to/removed
  // from a conversation) can all change this total.
  useOrgRealtime('channels', orgId, refetch);
  useOrgRealtime('messages', orgId, refetch);
  useOrgRealtime('channel_members', orgId, refetch);

  return state.count;
}
