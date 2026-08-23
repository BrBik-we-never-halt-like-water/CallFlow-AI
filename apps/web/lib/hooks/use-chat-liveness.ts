'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { supabaseBrowser } from '@/lib/supabase/client';

/**
 * Who is in this conversation right now, and who is mid-sentence.
 *
 * Deliberately **not** `useOrgRealtime`. That hook is `postgres_changes` - it
 * exists to notice committed rows, and a keystroke is not a row. Writing typing
 * to a table would mean an insert per keypress, a migration, an RLS policy and a
 * cleanup job, to store something that is worthless four seconds later.
 * Realtime's presence and broadcast channels carry exactly this kind of state
 * and touch no table at all.
 *
 * **One channel per conversation, not per organisation.** Presence for every
 * conversation in the sidebar would mean joining one channel per row, and the
 * only presence a reader acts on is the thread they have open.
 *
 * ## What this is safe to carry
 *
 * A broadcast channel is **not** covered by the `messages` RLS policy. Its name
 * contains the conversation's UUID, and RLS is what stops a non-member learning
 * that UUID in the first place - so membership gates *discovery*, not the
 * channel itself. That is weaker than the database path and the payloads are
 * chosen to match: a user id and a display name the organisation can already
 * see, never message text, never a draft. Someone holding a conversation id they
 * should not have could learn that a colleague is typing; they could not learn
 * what. Supabase's Realtime Authorization (RLS on `realtime.messages`) is what
 * would close that properly, and it needs its own migration - see `ISSUES.md`.
 */

/** How often a typist re-announces. Well under `TYPING_TTL_MS` so a continuous
 *  typist never flickers out between beats. */
const TYPING_THROTTLE_MS = 1_800;

/** How long a "typing" claim survives without a refresh. Covers one missed beat
 *  plus jitter; beyond that the indicator is lying and should clear itself. */
const TYPING_TTL_MS = 4_500;

export interface ChatLiveness {
  /** User ids present in this conversation, excluding the reader. */
  online: string[];
  /** User ids typing right now, excluding the reader. */
  typing: string[];
  /** Whether the reader's own subscription is live. `false` means presence and
   *  typing are unknown rather than empty, and the interface must not draw
   *  "nobody is here" from it. */
  connected: boolean;
  /** Call on each keystroke. Throttled internally, so calling it per character
   *  is the intended usage. */
  notifyTyping: () => void;
  /** Call when the draft is sent or cleared, so the other side's indicator
   *  drops immediately rather than waiting out the TTL. */
  notifyStopped: () => void;
}

const IDLE: ChatLiveness = {
  online: [],
  typing: [],
  connected: false,
  notifyTyping: () => {},
  notifyStopped: () => {},
};

/**
 * Everything the subscription observes, tagged with the conversation it came
 * from.
 *
 * One state object rather than three, and carrying its own `key`, so switching
 * conversations needs no reset: the render below simply ignores anything whose
 * key is not the open conversation. Resetting from an effect instead would be a
 * synchronous `setState` in an effect body - which the lint rule forbids for
 * good reason - and would still leave one frame showing the previous
 * conversation's presence in the new conversation's header.
 */
interface Observed {
  key: string | null;
  online: string[];
  typingAt: Record<string, number>;
  connected: boolean;
}

const NOTHING_OBSERVED: Observed = {
  key: null,
  online: [],
  typingAt: {},
  connected: false,
};

export function useChatLiveness({
  channelId,
  userId,
  name,
}: {
  channelId: string | null;
  userId: string | null;
  /** Shown to other members. The organisation can already see it. */
  name: string | null;
}): ChatLiveness {
  const [observed, setObserved] = useState<Observed>(NOTHING_OBSERVED);

  // The live channel, for the send helpers below. A ref because those helpers
  // are called from event handlers, which must not re-run the effect.
  const channelRef = useRef<ReturnType<
    ReturnType<typeof supabaseBrowser>['channel']
  > | null>(null);
  const lastSentRef = useRef(0);
  const sweepRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!channelId || !userId) return;

    const supabase = supabaseBrowser();
    // Captured so every callback below writes under the conversation it belongs
    // to. A late event from a conversation the reader has already left updates a
    // key the render is no longer reading, rather than the open one.
    const key = channelId;
    // Keyed by user id so the same person in two tabs is one presence entry
    // rather than two, and so leaving one tab does not report them gone.
    const channel = supabase.channel(`chat:${channelId}`, {
      config: { presence: { key: userId } },
    });
    channelRef.current = channel;

    channel
      .on('presence', { event: 'sync' }, () => {
        const present = Object.keys(channel.presenceState()).filter(
          (id) => id !== userId,
        );
        setObserved((prev) => ({ ...prev, key, online: present }));
      })
      .on<{ userId: string }>(
        'broadcast',
        { event: 'typing' },
        ({ payload }) => {
          if (!payload?.userId || payload.userId === userId) return;
          setObserved((prev) => ({
            ...prev,
            key,
            typingAt: { ...prev.typingAt, [payload.userId]: Date.now() },
          }));
        },
      )
      .on<{ userId: string }>(
        'broadcast',
        { event: 'stopped' },
        ({ payload }) => {
          if (!payload?.userId) return;
          setObserved((prev) => {
            if (!(payload.userId in prev.typingAt)) return prev;
            const typingAt = { ...prev.typingAt };
            delete typingAt[payload.userId];
            return { ...prev, key, typingAt };
          });
        },
      )
      .subscribe((status) => {
        const live = status === 'SUBSCRIBED';
        setObserved((prev) => ({ ...prev, key, connected: live }));
        if (live) void channel.track({ userId, name: name ?? null });
      });

    // A tab that closes without running cleanup (a crash, a force-quit) leaves
    // its last "typing" claim behind. The sweep is what expires it, and it runs
    // on an interval rather than a timer per user so one straggler cannot pin a
    // timer for every member who ever typed.
    sweepRef.current = setInterval(() => {
      const cutoff = Date.now() - TYPING_TTL_MS;
      setObserved((prev) => {
        const live = Object.entries(prev.typingAt).filter(
          ([, at]) => at > cutoff,
        );
        return live.length === Object.keys(prev.typingAt).length
          ? prev
          : { ...prev, typingAt: Object.fromEntries(live) };
      });
    }, 1_000);

    return () => {
      if (sweepRef.current) clearInterval(sweepRef.current);
      channelRef.current = null;
      void channel.untrack();
      void supabase.removeChannel(channel);
    };
  }, [channelId, userId, name]);

  const notifyTyping = useCallback(() => {
    const channel = channelRef.current;
    if (!channel || !userId) return;
    const now = Date.now();
    if (now - lastSentRef.current < TYPING_THROTTLE_MS) return;
    lastSentRef.current = now;
    void channel.send({
      type: 'broadcast',
      event: 'typing',
      payload: { userId },
    });
  }, [userId]);

  const notifyStopped = useCallback(() => {
    const channel = channelRef.current;
    if (!channel || !userId) return;
    // Reset the throttle too: the next keystroke after a send should announce
    // immediately rather than sitting out the remainder of the window.
    lastSentRef.current = 0;
    void channel.send({
      type: 'broadcast',
      event: 'stopped',
      payload: { userId },
    });
  }, [userId]);

  // Anything observed under a different conversation is not this one's, so it is
  // dropped here rather than cleared from an effect.
  const current = observed.key === channelId ? observed : NOTHING_OBSERVED;
  const typing = useMemo(
    () => Object.keys(current.typingAt),
    [current.typingAt],
  );

  if (!channelId || !userId) return IDLE;
  return {
    online: current.online,
    typing,
    connected: current.connected,
    notifyTyping,
    notifyStopped,
  };
}
