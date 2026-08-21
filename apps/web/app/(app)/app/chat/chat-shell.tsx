'use client';

import { Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowLeftIcon,
  CheckIcon,
  PaperPlaneTiltIcon,
  PencilSimpleIcon,
  PlusIcon,
  TrashIcon,
  UsersIcon,
  XIcon,
} from '@phosphor-icons/react/dist/ssr';
import { Button } from '@/components/ui/button';
import { Checkbox, RadioGroup } from '@/components/ui/checkbox';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Field } from '@/components/ui/field';
import { Input, SearchInput, Textarea } from '@/components/ui/input';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import { WavesLoader } from '@/components/ui/waves-loader';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/cn';
import { formatAge, formatTimeOnly } from '@/lib/format';
import {
  api,
  type Channel,
  type ChannelKind,
  type ChatMessage,
  type Member,
} from '@/lib/api';
import { useOrgRealtime } from '@/lib/hooks/use-org-realtime';
import { useSession } from '@/lib/hooks/use-session';

const MESSAGE_PAGE_SIZE = 50;
/** How long to wait after the last keystroke before searching - avoids a
 * request per character while typing a name. */
const SEARCH_DEBOUNCE_MS = 300;
/** Roughly matches the space `<main>` actually gives this page once the
 * header row above it is accounted for - not exact (the header's own height
 * varies with the unread count text), so this leans a little short rather
 * than risk clipping the composer on a small screen. */
const PANES_HEIGHT = 'h-[calc(100dvh-15rem)] min-h-[420px] md:h-[calc(100dvh-12rem)]';

/** The `channel_id` a Realtime payload's changed row belongs to, from
 * whichever of `new`/`old` actually carries it - `old` is only a partial row
 * under Postgres's default replica identity, but `channel_id` is always
 * present there too: it's part of `channel_members`'s own primary key, and
 * `messages` never receives a real `DELETE` (soft delete is an `UPDATE`,
 * which always carries a full `new`). `null` means "couldn't tell", handled
 * by the caller as "refetch anyway" rather than as "definitely irrelevant". */
function payloadChannelId(payload: { new: unknown; old: unknown }): string | null {
  for (const row of [payload.new, payload.old]) {
    if (row && typeof row === 'object' && 'channel_id' in row) {
      const value = (row as { channel_id: unknown }).channel_id;
      if (typeof value === 'string') return value;
    }
  }
  return null;
}

/** A channel's display name: its own name, or - for a nameless DM - the other
 * member(s), since `channels.name` is deliberately null for that kind. */
function channelLabel(
  channel: Channel,
  currentUserId: string,
  namesById: Record<string, string>,
): string {
  if (channel.name) return channel.name;
  const others = channel.member_ids.filter((id) => id !== currentUserId);
  if (others.length === 0) return 'Just you';
  return others.map((id) => namesById[id] ?? 'Former teammate').join(', ');
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Highlights an `@Name` mention for every name that's an actual member of
 * this conversation - matched against the channel's own roster, not a bare
 * `@\w+` pattern, so a stray "@" in ordinary text (an email, a handle typed
 * for another app) never lights up as if it were a real mention. Longest
 * name first, so "@Jo" can't shadow a match for "@Jordan". */
function renderMessageBody(body: string, memberNames: string[]): React.ReactNode {
  const names = [...new Set(memberNames)].filter(Boolean).sort((a, b) => b.length - a.length);
  if (names.length === 0) return body;

  const pattern = new RegExp(`@(${names.map(escapeRegExp).join('|')})(?!\\w)`, 'g');
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(body)) !== null) {
    if (match.index > lastIndex) parts.push(body.slice(lastIndex, match.index));
    parts.push(
      <span key={match.index} className="font-semibold text-primary">
        {match[0]}
      </span>,
    );
    lastIndex = match.index + match[0].length;
  }
  parts.push(body.slice(lastIndex));
  return parts;
}

/** Debounced org-member search, shared by the create dialog, the add-member
 * dialog, and the chat page's own "start a conversation" search - all just
 * need "type a name, get back org-scoped results". */
function useMemberSearch(excludeUserId: string | null) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const timeout = setTimeout(() => {
      if (cancelled) return;
      setLoading(true);
      api
        .listMembers(query.trim() || undefined)
        .then((team) => {
          if (!cancelled) {
            setResults(team.members.filter((m) => m.user_id !== excludeUserId));
          }
        })
        .catch(() => undefined)
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timeout);
    };
  }, [query, excludeUserId]);

  return { query, setQuery, results, loading };
}

/** Keeps a loading indicator visible for at least `minMs` after it first
 * turns on, even if `active` flips back off sooner - a loader that flashes
 * for 20ms on a fast/cached fetch reads as a glitch, not as feedback. */
function useMinVisible(active: boolean, minMs: number): boolean {
  const [holding, setHolding] = useState(active);
  // Stamped from the effect below, never during render - `Date.now()` in a
  // render body is impure and the lint rule that says so is right.
  const startedAt = useRef<number | null>(null);

  // Reset during render, the same discipline `channelDetail`/`view` use below.
  if (active && !holding) {
    setHolding(true);
  }

  // Winds down only once `active` is false. The previous version armed this
  // timer off `holding` alone, so while `active` stayed true the two fought
  // each other forever: the timer cleared the flag, the next render set it
  // straight back, the effect re-ran and armed another. A component
  // re-rendering every `minMs` for as long as anything was loading - a good
  // part of why `/api/v1/me` was being refetched a dozen times a page - and a
  // floor that could never actually lift (`ISSUES.md` #125).
  useEffect(() => {
    if (active) {
      startedAt.current = Date.now();
      return;
    }
    if (!holding) return;
    const elapsed = startedAt.current === null ? minMs : Date.now() - startedAt.current;
    const timeout = setTimeout(() => setHolding(false), Math.max(0, minMs - elapsed));
    return () => clearTimeout(timeout);
  }, [active, holding, minMs]);

  return active || holding;
}

/** True once `active` has stayed true for `afterMs` without resolving.
 *
 * The backstop for a loading state that never ends. A loader says "wait"; it
 * cannot say "this is not going to finish", and after twenty seconds that is
 * the more honest thing to tell someone. */
function useStalled(active: boolean, afterMs: number): boolean {
  const [stalled, setStalled] = useState(false);

  // Cleared during render rather than from an effect, same discipline as
  // `useMinVisible` above: whatever was stalling has resolved.
  if (!active && stalled) {
    setStalled(false);
  }

  useEffect(() => {
    if (!active) return;
    const timeout = setTimeout(() => setStalled(true), afterMs);
    return () => clearTimeout(timeout);
  }, [active, afterMs]);

  return stalled;
}

/** The only thing that reads `useSearchParams()` - Next.js requires that to
 * sit under a `<Suspense>` boundary, and a Suspense boundary gets torn down
 * and rebuilt on navigation, which would wipe every bit of `ChatShell`'s own
 * state (channel list, search box, an open conversation) on every single
 * chat switch if `ChatShell` read it directly. Isolating it in this stateless
 * leaf means it's the only thing that ever remounts; it just reports the
 * current id upward. */
function ChannelIdSync({ onChange }: { onChange: (id: string | null) => void }) {
  const searchParams = useSearchParams();
  const id = searchParams.get('c');
  useEffect(() => {
    onChange(id);
  }, [id, onChange]);
  return null;
}

export function ChatShell() {
  const session = useSession();
  const toast = useToast();
  const router = useRouter();
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const pendingOlderScrollRef = useRef<{ height: number; top: number } | null>(null);

  // The open conversation lives in a query param (`?c=`), not a `[id]` route
  // segment - Next.js remounts a dynamic-segment page component on every
  // change to its own param (this is by design, not a bug: `[id]/page.tsx`
  // is meant to be able to treat the param as a fresh identity), which was
  // wiping the channel list, search box, and everything else on every single
  // chat switch. `ChannelIdSync` below reports the current value in via
  // `setChannelId` instead of this component reading `useSearchParams()`
  // directly, so it's that leaf - not this whole component - that sits under
  // the `<Suspense>` boundary Next.js requires for it.
  const [channelId, setChannelId] = useState<string | null>(null);

  const orgId =
    session.status === 'signed-in' ? session.profile.active.org_id : null;
  const currentUserId =
    session.status === 'signed-in' ? session.profile.user_id : null;
  const canSend =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('messages:send');
  const isOrgAdminOrOwner =
    session.status === 'signed-in' &&
    (session.profile.active.role === 'admin' ||
      session.profile.active.role === 'owner');

  const [channels, setChannels] = useState<Channel[]>([]);
  const [loadingChannels, setLoadingChannels] = useState(true);
  const [members, setMembers] = useState<Member[]>([]);
  const [composerBody, setComposerBody] = useState('');
  const [sending, setSending] = useState(false);
  const [startingDm, setStartingDm] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [membersPanelOpen, setMembersPanelOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  // `start` is the index into `composerBody` where the triggering "@" sits,
  // so a picked name can be spliced in at the right place regardless of
  // where else in the message the cursor has since moved.
  const [mention, setMention] = useState<{ query: string; start: number } | null>(null);

  const dmSearch = useMemberSearch(currentUserId);

  // The open conversation's own record - fetched by id directly rather than
  // found in `channels`, so a conversation reached by URL resolves correctly
  // even before (or instead of) the list finishing its own fetch. `'missing'`
  // means the id doesn't exist or isn't visible to this caller - RLS
  // (`channels_select`) returns nothing either way, so this is also how a
  // cross-organisation id typed into the URL bar gets rejected.
  type ChannelDetail =
    | { channelId: string | null; status: 'idle' }
    | { channelId: string; status: 'loading' }
    | { channelId: string; status: 'missing' }
    | { channelId: string; status: 'ready'; channel: Channel };
  const [channelDetail, setChannelDetail] = useState<ChannelDetail>({
    channelId: null,
    status: 'idle',
  });
  // Reset during render the instant the URL's channel id changes - same
  // discipline `view` below (and `use-run-poll.ts`'s `runId`) already use -
  // so a newly opened conversation never briefly shows the previous one's
  // detail while the fetch below is in flight.
  if (channelDetail.channelId !== channelId) {
    setChannelDetail(
      channelId ? { channelId, status: 'loading' } : { channelId: null, status: 'idle' },
    );
  }

  const [view, setView] = useState<{
    channelId: string | null;
    messages: ChatMessage[];
    loading: boolean;
    hasMore: boolean;
  }>({ channelId: null, messages: [], loading: false, hasMore: false });
  if (view.channelId !== channelId) {
    setView({ channelId, messages: [], loading: channelId !== null, hasMore: false });
  }
  const [loadingOlder, setLoadingOlder] = useState(false);
  const showMessagesLoader = useMinVisible(view.loading, 900);

  const namesById = useMemo(
    () => Object.fromEntries(members.map((m) => [m.user_id, m.name ?? m.email])),
    [members],
  );

  function openChannel(id: string) {
    setMention(null);
    router.push(`/app/chat?c=${id}`, { scroll: false });
  }
  function closeChannel() {
    router.push('/app/chat', { scroll: false });
  }

  /**
   * Close the open conversation when the active organisation changes.
   *
   * The channel list and member list both key on `orgId` and refetch on a
   * switch, but the open conversation lives in the `?c=` query param, which
   * survives one - so the right-hand pane went on showing the previous
   * organisation's conversation, and its already-fetched messages, while the
   * list beside it had moved on (`ISSUES.md` #127). RLS stops any *new* read
   * of that channel, but nothing un-renders what was already on screen.
   *
   * A channel id from another organisation has no meaning in this one, so the
   * honest result is no conversation selected rather than an error about one
   * the reader never opened. The first run is skipped: `orgId` arrives as null
   * and then resolves, which is not a switch.
   */
  const lastOrgId = useRef<string | null>(null);
  useEffect(() => {
    if (!orgId) return;
    const previous = lastOrgId.current;
    lastOrgId.current = orgId;
    if (previous !== null && previous !== orgId && channelId !== null) {
      router.replace('/app/chat', { scroll: false });
    }
  }, [orgId, channelId, router]);

  // --- channel list --------------------------------------------------------

  useEffect(() => {
    if (!orgId) return;
    let cancelled = false;
    async function load() {
      try {
        const rows = await api.listChannels();
        if (!cancelled) setChannels(rows);
      } catch (e) {
        if (!cancelled) {
          toast({
            title: "Couldn't load chat",
            body: e instanceof Error ? e.message : undefined,
            tone: 'error',
          });
        }
      } finally {
        if (!cancelled) setLoadingChannels(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [orgId, toast]);

  function refetchChannels() {
    if (!orgId) return;
    api.listChannels().then(setChannels).catch(() => undefined);
  }
  useOrgRealtime('channels', orgId, refetchChannels);

  useEffect(() => {
    if (!orgId) return;
    let cancelled = false;
    api
      .listMembers()
      .then((team) => {
        if (!cancelled) setMembers(team.members);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  // --- the open conversation's own record -----------------------------------

  // Guarded by "is this still the channel on screen?", NOT by an effect-scoped
  // `cancelled` flag. The two are not equivalent, and the difference was a bug
  // we shipped: a cleanup running between request and response discarded a
  // perfectly good 200 and left `status: 'loading'` set forever, because only
  // the resolve and reject paths ever move it off 'loading'. The result was a
  // conversation stuck on its loader with no error and nothing in the console
  // (`ISSUES.md` #124). Comparing the id keeps the protection that mattered -
  // a slow response for a channel the reader has already navigated away from
  // is still ignored - without letting effect lifecycle strand the state.
  useEffect(() => {
    if (!channelId) return;
    const id = channelId;
    api
      .getChannel(id)
      .then((channel) =>
        setChannelDetail((current) =>
          current.channelId === id ? { channelId: id, status: 'ready', channel } : current,
        ),
      )
      .catch(() =>
        setChannelDetail((current) =>
          current.channelId === id ? { channelId: id, status: 'missing' } : current,
        ),
      );
  }, [channelId]);

  function refetchChannelDetail() {
    if (!channelId) return;
    const id = channelId;
    api
      .getChannel(id)
      .then((channel) => setChannelDetail({ channelId: id, status: 'ready', channel }))
      .catch(() => setChannelDetail({ channelId: id, status: 'missing' }));
  }
  // Membership changes (add/remove) aren't reflected by the 'channels' or
  // 'messages' subscriptions above - a third table needs its own watch, or an
  // add/remove elsewhere never appears here without a manual refresh.
  // `refetchChannels()` stays unconditional - a membership change anywhere
  // can add or remove a channel from the caller's own list. The open
  // conversation's detail only needs refetching when the change was actually
  // about it, not any other channel in the organisation.
  useOrgRealtime('channel_members', orgId, (payloads) => {
    refetchChannels();
    const relevant = payloads.some((payload) => {
      const changed = payloadChannelId(payload);
      return changed === null || changed === channelId;
    });
    if (relevant) {
      refetchChannelDetail();
    }
  });

  const selectedChannel = channelDetail.status === 'ready' ? channelDetail.channel : null;
  // A conversation that never resolves has to end in something a person can
  // act on. Whatever the cause - a stalled request, a state transition that
  // never lands - an indefinite spinner tells the reader nothing and offers
  // them nothing, which is how this page burned a day (`ISSUES.md` #125).
  const channelStalled = useStalled(channelDetail.status === 'loading', 20_000);
  const canManageChannel =
    selectedChannel !== null &&
    (selectedChannel.created_by === currentUserId || isOrgAdminOrOwner);
  const channelMemberNames = useMemo(
    () => (selectedChannel ? selectedChannel.member_ids.map((id) => namesById[id]).filter((n): n is string => Boolean(n)) : []),
    [selectedChannel, namesById],
  );

  // --- messages --------------------------------------------------------------

  useEffect(() => {
    if (!channelId) return;
    const id = channelId;
    // Same id guard as the channel-detail effect above, and for the same
    // reason: the `cancelled` flag this used to carry threw away a successful
    // 200 and left `loading: true` with no way back, so the message list span
    // on its loader forever (`ISSUES.md` #124). The error path already guarded
    // by id - the success path now matches it.
    let stale = false;
    async function load() {
      try {
        const rows = await api.listMessages(id, { limit: MESSAGE_PAGE_SIZE });
        setView((current) =>
          current.channelId === id
            ? {
                channelId: id,
                messages: rows,
                loading: false,
                hasMore: rows.length >= MESSAGE_PAGE_SIZE,
              }
            : current,
        );
        // A side effect, not state: only worth doing while this conversation
        // is still the one open, so it stays behind the effect-scoped flag.
        if (!stale) {
          void api.markChannelRead(id).then(refetchChannels).catch(() => undefined);
        }
      } catch (e) {
        if (!stale) {
          toast({
            title: "Couldn't load messages",
            body: e instanceof Error ? e.message : undefined,
            tone: 'error',
          });
        }
        setView((current) =>
          current.channelId === id ? { ...current, loading: false } : current,
        );
      }
    }
    void load();
    return () => {
      stale = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channelId, toast]);

  // Scoped to whichever channel actually changed - without this, one message
  // sent anywhere else in the organisation that the caller happens to belong
  // to re-fetched and re-marked-read whatever conversation was open here,
  // for every open tab in the org, on every send.
  function refetchMessages(changedChannelId: string | null) {
    const id = view.channelId;
    if (!id || (changedChannelId !== null && changedChannelId !== id)) return;
    api
      .listMessages(id, { limit: Math.max(view.messages.length, MESSAGE_PAGE_SIZE) })
      .then((rows) =>
        setView((current) =>
          current.channelId === id
            ? { ...current, messages: rows, hasMore: rows.length >= MESSAGE_PAGE_SIZE }
            : current,
        ),
      )
      .then(() => {
        // A live update while the conversation is open counts as read too.
        void api.markChannelRead(id).then(refetchChannels).catch(() => undefined);
      })
      .catch(() => undefined);
  }
  useOrgRealtime('messages', orgId, (payloads) => {
    // At most one refetch per burst, even if several payloads in it are
    // relevant - refetchMessages always re-lists the full current state, so a
    // second call back-to-back would just re-fetch the same result.
    for (const payload of payloads) {
      const changed = payloadChannelId(payload);
      if (changed === null || changed === view.channelId) {
        refetchMessages(changed);
        return;
      }
    }
  });

  async function loadOlderMessages() {
    const id = view.channelId;
    if (!id || view.messages.length === 0 || loadingOlder) return;
    setLoadingOlder(true);
    const container = messagesContainerRef.current;
    if (container) {
      pendingOlderScrollRef.current = { height: container.scrollHeight, top: container.scrollTop };
    }
    try {
      const older = await api.listMessages(id, {
        before: view.messages[0].created_at,
        beforeId: view.messages[0].id,
        limit: MESSAGE_PAGE_SIZE,
      });
      setView((current) =>
        current.channelId === id
          ? {
              ...current,
              messages: [...older, ...current.messages],
              hasMore: older.length >= MESSAGE_PAGE_SIZE,
            }
          : current,
      );
    } catch (e) {
      pendingOlderScrollRef.current = null;
      toast({
        title: "Couldn't load earlier messages",
        body: e instanceof Error ? e.message : undefined,
        tone: 'error',
      });
    } finally {
      setLoadingOlder(false);
    }
  }

  // Scrolled to the newest message on first load and on every append (a sent
  // message, a live one arriving, opening a different conversation) - a
  // fixed-height scrollable pane doesn't do this on its own the way a
  // naturally-growing page would. `loadOlderMessages` is the one exception:
  // it anchors the view to whatever was on screen instead, or paging in
  // history would otherwise yank the reader back down to the bottom.
  // `showMessagesLoader` is a dependency too: real content doesn't actually
  // reach the DOM until that floor clears, which can happen a render or two
  // after `view.messages` itself changed.
  useLayoutEffect(() => {
    if (showMessagesLoader) return;
    const container = messagesContainerRef.current;
    if (!container) return;
    const pending = pendingOlderScrollRef.current;
    if (pending) {
      container.scrollTop = container.scrollHeight - pending.height + pending.top;
      pendingOlderScrollRef.current = null;
      return;
    }
    container.scrollTop = container.scrollHeight;
  }, [view.channelId, view.messages, showMessagesLoader]);

  async function handleSend() {
    const body = composerBody.trim();
    if (!body || !channelId || sending) return;
    setSending(true);
    try {
      const sent = await api.sendMessage(channelId, body);
      setView((current) =>
        current.channelId === channelId
          ? { ...current, messages: [...current.messages, sent] }
          : current,
      );
      setComposerBody('');
      setMention(null);
    } catch (e) {
      toast({
        title: 'Message not sent',
        body: e instanceof Error ? e.message : undefined,
        tone: 'error',
      });
    } finally {
      setSending(false);
    }
  }

  async function handleSaveEdit(messageId: string) {
    const body = editValue.trim();
    if (!body || !channelId) return;
    try {
      const updated = await api.editMessage(channelId, messageId, body);
      setView((current) => ({
        ...current,
        messages: current.messages.map((m) => (m.id === messageId ? updated : m)),
      }));
      setEditingId(null);
    } catch (e) {
      toast({
        title: "Couldn't save that edit",
        body: e instanceof Error ? e.message : undefined,
        tone: 'error',
      });
    }
  }

  async function handleDeleteMessage(messageId: string) {
    if (!channelId) return;
    try {
      await api.deleteMessage(channelId, messageId);
      setView((current) => ({
        ...current,
        messages: current.messages.filter((m) => m.id !== messageId),
      }));
    } catch (e) {
      toast({
        title: "Couldn't delete that message",
        body: e instanceof Error ? e.message : undefined,
        tone: 'error',
      });
    }
  }

  async function handleRename() {
    const name = renameValue.trim();
    if (!name || !channelId) return;
    try {
      const updated = await api.renameChannel(channelId, name);
      setChannelDetail({ channelId, status: 'ready', channel: updated });
      refetchChannels();
      setRenaming(false);
      toast({ title: 'Renamed', tone: 'success' });
    } catch (e) {
      toast({
        title: "Couldn't rename",
        body: e instanceof Error ? e.message : undefined,
        tone: 'error',
      });
    }
  }

  async function handleAddMember(userId: string) {
    if (!channelId) return;
    try {
      await api.addChannelMember(channelId, userId);
      refetchChannelDetail();
      refetchChannels();
      setAddMemberOpen(false);
      toast({ title: 'Added', tone: 'success' });
    } catch (e) {
      toast({
        title: "Couldn't add that person",
        body: e instanceof Error ? e.message : undefined,
        tone: 'error',
      });
    }
  }

  async function handleRemoveMember(userId: string) {
    if (!channelId) return;
    try {
      await api.removeChannelMember(channelId, userId);
      if (userId === currentUserId) {
        // Leaving your own conversation - nothing left here to look at.
        refetchChannels();
        closeChannel();
        return;
      }
      refetchChannelDetail();
      refetchChannels();
    } catch (e) {
      toast({
        title: "Couldn't remove that person",
        body: e instanceof Error ? e.message : undefined,
        tone: 'error',
      });
    }
  }

  // Starting a DM is idempotent server-side (the same pair always converges
  // on the same channel), so this never has to check "do we already have a
  // conversation with them" itself - just ask, and open whatever comes back.
  async function handleStartDirectMessage(userId: string) {
    setStartingDm(userId);
    try {
      const created = await api.createChannel({ kind: 'dm', member_ids: [userId] });
      setChannels((current) =>
        current.some((c) => c.id === created.id) ? current : [created, ...current],
      );
      dmSearch.setQuery('');
      openChannel(created.id);
    } catch (e) {
      toast({
        title: "Couldn't start that conversation",
        body: e instanceof Error ? e.message : undefined,
        tone: 'error',
      });
    } finally {
      setStartingDm(null);
    }
  }

  // --- @mentions ---------------------------------------------------------

  const mentionCandidates = useMemo(() => {
    if (!mention || !selectedChannel) return [];
    const q = mention.query.toLowerCase();
    return selectedChannel.member_ids
      .filter((id) => id !== currentUserId)
      .map((id) => ({ id, name: namesById[id] ?? 'Former teammate' }))
      .filter((m) => m.name.toLowerCase().includes(q))
      .slice(0, 6);
  }, [mention, selectedChannel, namesById, currentUserId]);

  function handleComposerChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const value = e.target.value;
    const cursor = e.target.selectionStart ?? value.length;
    setComposerBody(value);

    const upToCursor = value.slice(0, cursor);
    const match = /(?:^|\s)@(\w*)$/.exec(upToCursor);
    setMention(match ? { query: match[1], start: upToCursor.length - match[1].length - 1 } : null);
  }

  function selectMention(name: string) {
    if (!mention) return;
    const before = composerBody.slice(0, mention.start);
    const after = composerBody.slice(mention.start + 1 + mention.query.length);
    setComposerBody(`${before}@${name} ${after}`);
    setMention(null);
    composerRef.current?.focus();
  }

  const totalUnread = channels.reduce((sum, c) => sum + c.unread_count, 0);
  const showListPane = channelId === null;
  const dmSearchActive = dmSearch.query.trim().length > 0;

  return (
    <div className="flex flex-col gap-4">
      <Suspense fallback={null}>
        <ChannelIdSync onChange={setChannelId} />
      </Suspense>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-small font-bold text-text-mute">Chat</p>
          <h1 className="font-display text-h2 text-text">
            Team chat
            {totalUnread > 0 ? (
              <span className="ml-2 align-middle text-body text-lamp-flare-text">
                {totalUnread} unread
              </span>
            ) : null}
          </h1>
          <p className="measure text-small text-text-dim">
            Channels and DMs between teammates in your organisation.
          </p>
        </div>
        {canSend ? (
          <Button onClick={() => setCreateOpen(true)}>
            <PlusIcon aria-hidden className="size-4" />
            New group
          </Button>
        ) : null}
      </div>

      <div className={cn('flex min-h-0 gap-4', PANES_HEIGHT)}>
        {/* --- conversation list + start-a-chat search ---------------------- */}
        <div
          className={cn(
            'w-full min-h-0 flex-col gap-3 md:flex md:w-[320px] md:shrink-0',
            showListPane ? 'flex' : 'hidden',
          )}
        >
          {canSend ? (
            <SearchInput
              value={dmSearch.query}
              onChange={(e) => dmSearch.setQuery(e.target.value)}
              onClear={() => dmSearch.setQuery('')}
              placeholder="Search a teammate to message..."
              aria-label="Search teammates to start a conversation"
            />
          ) : null}

          <div className="min-h-0 flex-1 overflow-y-auto pt-2">
            {dmSearchActive ? (
              dmSearch.loading ? (
                <p className="p-2 text-small text-text-mute">Searching...</p>
              ) : dmSearch.results.length === 0 ? (
                <p className="p-2 text-small text-text-mute">No teammates match that search.</p>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {dmSearch.results.map((m) => (
                    <li key={m.user_id}>
                      <button
                        type="button"
                        disabled={startingDm !== null}
                        onClick={() => void handleStartDirectMessage(m.user_id)}
                        className="w-full text-left"
                      >
                        <Panel interactive className="flex items-center justify-between gap-3 p-3">
                          <span className="flex flex-col">
                            <span className="font-medium text-text">{m.name ?? m.email}</span>
                            <span className="text-small text-text-mute">{m.email}</span>
                          </span>
                          {startingDm === m.user_id ? (
                            <span className="text-small text-text-mute">Starting...</span>
                          ) : null}
                        </Panel>
                      </button>
                    </li>
                  ))}
                </ul>
              )
            ) : loadingChannels ? (
              <div className="flex flex-col gap-3">
                {Array.from({ length: 3 }, (_, i) => (
                  <Panel key={i} className="flex items-center gap-3 p-4">
                    <Skeleton className="size-8 rounded-full" />
                    <Skeleton className="h-4 w-40" />
                  </Panel>
                ))}
              </div>
            ) : channels.length === 0 ? (
              <Panel>
                <EmptyState
                  title="No conversations yet"
                  body="Search a teammate above to start a DM, or start a group - contacts and campaigns stay separate from this."
                  action={
                    canSend ? (
                      <Button variant="secondary" onClick={() => setCreateOpen(true)}>
                        Start a group
                      </Button>
                    ) : undefined
                  }
                />
              </Panel>
            ) : (
              <ul className="flex flex-col gap-2">
                {channels.map((channel) => (
                  <li key={channel.id}>
                    <button
                      type="button"
                      onClick={() => openChannel(channel.id)}
                      className="w-full text-left"
                    >
                      <Panel
                        interactive
                        className={cn(
                          'flex items-center justify-between gap-3 p-4',
                          channel.id === channelId && 'border-primary/40 bg-primary/5',
                        )}
                      >
                        <div className="flex flex-col gap-0.5">
                          <p className="font-medium text-text">
                            {currentUserId
                              ? channelLabel(channel, currentUserId, namesById)
                              : (channel.name ?? 'DM')}
                          </p>
                          <p className="text-small text-text-mute">
                            {channel.kind === 'dm' ? 'Direct message' : 'Channel'} ·{' '}
                            {channel.member_ids.length}{' '}
                            {channel.member_ids.length === 1 ? 'member' : 'members'}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          {channel.unread_count > 0 ? (
                            <span
                              className="flex min-w-5 items-center justify-center rounded-full px-1.5 py-0.5 text-label font-bold text-white"
                              style={{ background: 'var(--lamp-flare)' }}
                            >
                              {channel.unread_count > 99 ? '99+' : channel.unread_count}
                            </span>
                          ) : null}
                          <span className="text-small text-text-mute">
                            {formatAge(channel.created_at)}
                          </span>
                        </div>
                      </Panel>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* --- the open conversation, inline (not a modal) so the list stays
            visible alongside it on md+ screens, and switching conversations
            never means closing one first ---------------------------------- */}
        <div
          className={cn(
            'min-h-0 min-w-0 flex-1 md:flex',
            showListPane ? 'hidden' : 'flex',
          )}
        >
          {!channelId ? (
            <Panel className="flex flex-1 items-center justify-center">
              <EmptyState
                title="Select a conversation"
                body="Pick a chat from the list, or search a teammate to start a new one."
              />
            </Panel>
          ) : channelDetail.status === 'missing' ? (
            <Panel className="flex flex-1 flex-col">
              <div className="flex items-center gap-2 border-b border-rule p-4 md:hidden">
                <button type="button" aria-label="Back to chats" onClick={closeChannel}>
                  <ArrowLeftIcon aria-hidden className="size-4" />
                </button>
              </div>
              <div className="flex flex-1 items-center justify-center p-4 md:p-5">
                <EmptyState
                  title="This conversation isn't available"
                  body="It may not exist, or you may not be a member of it."
                  action={
                    <Button variant="secondary" onClick={closeChannel}>
                      Back to Chat
                    </Button>
                  }
                />
              </div>
            </Panel>
          ) : selectedChannel ? (
            // Gated on the channel having loaded, and nothing else. This used
            // to also require `!showChannelLoader`, which put a 500ms cosmetic
            // anti-flicker floor in charge of whether the entire conversation -
            // header, message list and composer - existed. Any way for that
            // floor to stay raised (and `useMinVisible` above had one) turned a
            // presentation detail into a conversation that never opens, which
            // is exactly what shipped (`ISSUES.md` #125). A loading floor may
            // delay content inside a panel; it must never decide whether the
            // panel renders.
            <Panel className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="flex items-start justify-between gap-4 border-b border-rule p-4 md:p-5">
                <div className="flex min-w-0 flex-1 items-start gap-2">
                  <button
                    type="button"
                    aria-label="Back to chats"
                    className="mt-0.5 shrink-0 md:hidden"
                    onClick={closeChannel}
                  >
                    <ArrowLeftIcon aria-hidden className="size-4" />
                  </button>
                  <div className="flex min-w-0 flex-col gap-1">
                    {renaming ? (
                      <form
                        className="flex items-center gap-2"
                        onSubmit={(e) => {
                          e.preventDefault();
                          void handleRename();
                        }}
                      >
                        <Input
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          autoFocus
                          maxLength={80}
                          className="h-8 text-h3"
                        />
                        <button type="submit" aria-label="Save name" className="shrink-0">
                          <CheckIcon aria-hidden className="size-4" />
                        </button>
                        <button
                          type="button"
                          aria-label="Cancel"
                          className="shrink-0"
                          onClick={() => setRenaming(false)}
                        >
                          <XIcon aria-hidden className="size-4" />
                        </button>
                      </form>
                    ) : (
                      <p className="truncate font-display text-h3 text-text">
                        {currentUserId
                          ? channelLabel(selectedChannel, currentUserId, namesById)
                          : 'Conversation'}
                      </p>
                    )}
                    <span className="flex flex-wrap items-center gap-3 text-small text-text-mute">
                      <span>{selectedChannel.kind === 'dm' ? 'Direct message' : 'Channel'}</span>
                      <button
                        type="button"
                        className="flex items-center gap-1 underline decoration-dotted underline-offset-2 hover:text-text"
                        onClick={() => setMembersPanelOpen((v) => !v)}
                      >
                        <UsersIcon aria-hidden className="size-3.5" />
                        {selectedChannel.member_ids.length}{' '}
                        {selectedChannel.member_ids.length === 1 ? 'member' : 'members'}
                      </button>
                      {canManageChannel && selectedChannel.kind === 'channel' && !renaming ? (
                        <button
                          type="button"
                          className="flex items-center gap-1 underline decoration-dotted underline-offset-2 hover:text-text"
                          onClick={() => {
                            setRenameValue(selectedChannel.name ?? '');
                            setRenaming(true);
                          }}
                        >
                          <PencilSimpleIcon aria-hidden className="size-3.5" />
                          Rename
                        </button>
                      ) : null}
                    </span>
                  </div>
                </div>
              </div>

              <div
                ref={messagesContainerRef}
                className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4 md:p-5"
              >
                {membersPanelOpen ? (
                  <Panel sunken className="flex flex-col gap-2 p-3">
                    <div className="flex items-center justify-between">
                      <p className="text-small font-bold text-text-mute">Members</p>
                      {canSend ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setAddMemberOpen(true)}
                        >
                          <PlusIcon aria-hidden className="size-3.5" />
                          Add
                        </Button>
                      ) : null}
                    </div>
                    <ul className="flex flex-col gap-1.5">
                      {selectedChannel.member_ids.map((id) => (
                        <li
                          key={id}
                          className="flex items-center justify-between gap-2 text-small"
                        >
                          <span className="text-text">
                            {id === currentUserId ? 'You' : (namesById[id] ?? 'Former teammate')}
                            {id === selectedChannel.created_by ? (
                              <span className="ml-1.5 text-label text-text-mute">creator</span>
                            ) : null}
                          </span>
                          {id === currentUserId || canManageChannel ? (
                            <button
                              type="button"
                              className="text-text-mute hover:text-lamp-flare-text"
                              onClick={() => void handleRemoveMember(id)}
                            >
                              {id === currentUserId ? 'Leave' : 'Remove'}
                            </button>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </Panel>
                ) : null}

                {showMessagesLoader ? (
                  <div className="flex flex-1 items-center justify-center">
                    <WavesLoader />
                  </div>
                ) : view.messages.length === 0 ? (
                  <p className="py-8 text-center text-small text-text-mute">
                    No messages yet - say hello.
                  </p>
                ) : (
                  <>
                    {view.hasMore ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="self-center"
                        loading={loadingOlder}
                        onClick={() => void loadOlderMessages()}
                      >
                        Load earlier messages
                      </Button>
                    ) : null}
                    {view.messages.map((m) => {
                      const mine = m.sender_id === currentUserId;
                      const isEditing = editingId === m.id;
                      return (
                        <div
                          key={m.id}
                          className={`group flex max-w-[85%] flex-col gap-0.5 ${mine ? 'ml-auto items-end' : 'items-start'}`}
                        >
                          <p className="flex items-center gap-1.5 text-label text-text-mute">
                            <span>
                              {mine ? 'You' : (m.sender_name ?? 'Former teammate')} ·{' '}
                              {formatTimeOnly(m.created_at)}
                              {m.edited_at ? ' · edited' : ''}
                            </span>
                            {mine && !isEditing ? (
                              <span className="hidden items-center gap-1 group-hover:inline-flex">
                                <button
                                  type="button"
                                  aria-label="Edit message"
                                  onClick={() => {
                                    setEditingId(m.id);
                                    setEditValue(m.body);
                                  }}
                                >
                                  <PencilSimpleIcon aria-hidden className="size-3" />
                                </button>
                                <button
                                  type="button"
                                  aria-label="Delete message"
                                  onClick={() => void handleDeleteMessage(m.id)}
                                >
                                  <TrashIcon aria-hidden className="size-3" />
                                </button>
                              </span>
                            ) : null}
                          </p>
                          {isEditing ? (
                            <form
                              className="flex w-full items-end gap-1.5"
                              onSubmit={(e) => {
                                e.preventDefault();
                                void handleSaveEdit(m.id);
                              }}
                            >
                              <Textarea
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                autoFocus
                                className="min-h-9"
                                maxLength={4000}
                              />
                              <button type="submit" aria-label="Save">
                                <CheckIcon aria-hidden className="size-4" />
                              </button>
                              <button
                                type="button"
                                aria-label="Cancel"
                                onClick={() => setEditingId(null)}
                              >
                                <XIcon aria-hidden className="size-4" />
                              </button>
                            </form>
                          ) : (
                            <p
                              className={`measure rounded-md px-3 py-2 text-small ${
                                mine
                                  ? 'bg-surface-inverse text-text-inverse'
                                  : 'border border-rule bg-surface-raised text-text'
                              }`}
                            >
                              {renderMessageBody(m.body, channelMemberNames)}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </>
                )}
              </div>

              <div className="border-t border-rule p-4 md:p-5">
                {canSend ? (
                  <form
                    className="relative flex w-full items-end gap-2"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void handleSend();
                    }}
                  >
                    {mention && mentionCandidates.length > 0 ? (
                      <Panel className="absolute bottom-full left-0 z-10 mb-2 w-64 p-1.5">
                        <ul className="flex flex-col gap-0.5">
                          {mentionCandidates.map((m) => (
                            <li key={m.id}>
                              <button
                                type="button"
                                className="w-full rounded-sm px-2 py-1.5 text-left text-small hover:bg-surface-hover"
                                onClick={() => selectMention(m.name)}
                              >
                                {m.name}
                              </button>
                            </li>
                          ))}
                        </ul>
                      </Panel>
                    ) : null}
                    <Textarea
                      ref={composerRef}
                      value={composerBody}
                      onChange={handleComposerChange}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          void handleSend();
                        }
                        if (e.key === 'Escape' && mention) setMention(null);
                      }}
                      placeholder="Write a message... (@ to mention someone)"
                      className="min-h-10 flex-1"
                      maxLength={4000}
                    />
                    <Button
                      type="submit"
                      disabled={!composerBody.trim()}
                      loading={sending}
                    >
                      <PaperPlaneTiltIcon aria-hidden className="size-4" />
                    </Button>
                  </form>
                ) : (
                  <p className="text-small text-text-mute">
                    Your role can read this conversation but not post to it.
                  </p>
                )}
              </div>
            </Panel>
          ) : channelStalled ? (
            <Panel className="flex flex-1 items-center justify-center p-4 md:p-5">
              <EmptyState
                title="This conversation didn't open"
                body="It has been loading for a while without finishing. Retrying usually clears it."
                action={
                  <Button variant="secondary" onClick={refetchChannelDetail}>
                    Try again
                  </Button>
                }
              />
            </Panel>
          ) : (
            <Panel className="flex flex-1 items-center justify-center p-4 md:p-5">
              <WavesLoader />
            </Panel>
          )}
        </div>
      </div>

      <DialogRoot open={createOpen} onOpenChange={setCreateOpen}>
        {createOpen ? (
          <CreateChannelDialog
            currentUserId={currentUserId}
            onCancel={() => setCreateOpen(false)}
            onCreated={(created) => {
              setChannels((current) => [created, ...current]);
              openChannel(created.id);
              setCreateOpen(false);
              toast({ title: 'Conversation started', tone: 'success' });
            }}
          />
        ) : null}
      </DialogRoot>

      <DialogRoot open={addMemberOpen} onOpenChange={setAddMemberOpen}>
        {addMemberOpen && selectedChannel ? (
          <AddMemberDialog
            currentUserId={currentUserId}
            existingMemberIds={selectedChannel.member_ids}
            onCancel={() => setAddMemberOpen(false)}
            onAdd={(userId) => void handleAddMember(userId)}
          />
        ) : null}
      </DialogRoot>
    </div>
  );
}

function CreateChannelDialog({
  currentUserId,
  onCancel,
  onCreated,
}: {
  currentUserId: string | null;
  onCancel: () => void;
  onCreated: (channel: Channel) => void;
}) {
  const toast = useToast();
  const [kind, setKind] = useState<ChannelKind>('channel');
  const [name, setName] = useState('');
  const [memberIds, setMemberIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const search = useMemberSearch(currentUserId);

  async function handleSubmit() {
    if (kind === 'channel' && !name.trim()) {
      setError('Give this channel a name.');
      return;
    }
    if (kind === 'dm' && memberIds.length !== 1) {
      setError('Pick exactly one teammate for a DM.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.createChannel({
        kind,
        name: kind === 'channel' ? name.trim() : null,
        member_ids: memberIds,
      });
      onCreated(created);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Couldn't create it.";
      setError(message);
      toast({ title: 'Not created', body: message, tone: 'error' });
    } finally {
      setSubmitting(false);
    }
  }

  // A picked member might not be in the current search results (e.g. picked,
  // then typed a different search) - keep their label available regardless.
  const pickable = useMemo(() => {
    const byId = new Map(search.results.map((m) => [m.user_id, m]));
    return byId;
  }, [search.results]);

  return (
    <Dialog
      title="New conversation"
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={() => void handleSubmit()} loading={submitting}>
            Create
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Type">
          <RadioGroup
            name="channel-kind"
            value={kind}
            onValueChange={(v) => setKind(v as ChannelKind)}
            options={[
              { value: 'channel', label: 'Channel', hint: 'Named, any number of teammates' },
              { value: 'dm', label: 'Direct message', hint: 'Just you and one teammate' },
            ]}
          />
        </Field>

        {kind === 'channel' ? (
          <Field label="Name" required error={error && !name.trim() ? error : null}>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. launch-team"
              maxLength={80}
            />
          </Field>
        ) : null}

        <Field
          label={kind === 'dm' ? 'Teammate' : 'Members'}
          help={kind === 'channel' ? "You're added automatically." : undefined}
          error={error && kind === 'dm' && memberIds.length !== 1 ? error : null}
        >
          <SearchInput
            value={search.query}
            onChange={(e) => search.setQuery(e.target.value)}
            onClear={() => search.setQuery('')}
            placeholder="Search teammates by name or email..."
            aria-label="Search organisation members"
            className="mb-2"
          />
          {search.loading ? (
            <p className="text-small text-text-mute">Searching...</p>
          ) : search.results.length === 0 ? (
            <p className="text-small text-text-mute">
              {search.query
                ? 'No teammates match that search.'
                : 'No other teammates in this organisation yet.'}
            </p>
          ) : kind === 'dm' ? (
            <RadioGroup
              name="dm-member"
              value={memberIds[0] ?? ''}
              onValueChange={(v) => setMemberIds([v])}
              options={search.results.map((m) => ({
                value: m.user_id,
                label: m.name ?? m.email,
              }))}
            />
          ) : (
            <div className="flex flex-col gap-2">
              {search.results.map((m) => (
                <Checkbox
                  key={m.user_id}
                  label={m.name ?? m.email}
                  checked={memberIds.includes(m.user_id)}
                  onCheckedChange={(checked) =>
                    setMemberIds((current) =>
                      checked
                        ? [...current, m.user_id]
                        : current.filter((id) => id !== m.user_id),
                    )
                  }
                />
              ))}
            </div>
          )}
          {/* Picked members outside the current search results still count. */}
          {kind === 'channel' &&
            memberIds
              .filter((id) => !pickable.has(id))
              .map((id) => (
                <Checkbox key={id} label={id} checked onCheckedChange={() => undefined} />
              ))}
        </Field>
      </div>
    </Dialog>
  );
}

function AddMemberDialog({
  currentUserId,
  existingMemberIds,
  onCancel,
  onAdd,
}: {
  currentUserId: string | null;
  existingMemberIds: string[];
  onCancel: () => void;
  onAdd: (userId: string) => void;
}) {
  const search = useMemberSearch(currentUserId);
  const candidates = search.results.filter((m) => !existingMemberIds.includes(m.user_id));

  return (
    <Dialog title="Add people" footer={<Button variant="ghost" onClick={onCancel}>Close</Button>}>
      <div className="flex flex-col gap-3">
        <SearchInput
          value={search.query}
          onChange={(e) => search.setQuery(e.target.value)}
          onClear={() => search.setQuery('')}
          placeholder="Search teammates by name or email..."
          aria-label="Search organisation members"
        />
        {search.loading ? (
          <p className="text-small text-text-mute">Searching...</p>
        ) : candidates.length === 0 ? (
          <p className="text-small text-text-mute">Everyone matching that search is already here.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {candidates.map((m) => (
              <li key={m.user_id}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-left text-small hover:bg-surface-hover"
                  onClick={() => onAdd(m.user_id)}
                >
                  <span>{m.name ?? m.email}</span>
                  <PlusIcon aria-hidden className="size-4 text-text-mute" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Dialog>
  );
}
