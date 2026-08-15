'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
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
import { Dialog, DialogRoot, Sheet } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Field } from '@/components/ui/field';
import { Input, SearchInput, Textarea } from '@/components/ui/input';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
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

/** Debounced org-member search, shared by the create dialog and the add-member
 * dialog - both just need "type a name, get back org-scoped results". */
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

export function ChatShell({ channelId }: { channelId: string | null }) {
  const session = useSession();
  const toast = useToast();
  const router = useRouter();

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
  const [createOpen, setCreateOpen] = useState(false);
  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [membersPanelOpen, setMembersPanelOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

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

  const namesById = useMemo(
    () => Object.fromEntries(members.map((m) => [m.user_id, m.name ?? m.email])),
    [members],
  );

  function openChannel(id: string) {
    router.push(`/app/chat/${id}`);
  }
  function closeChannel() {
    router.push('/app/chat');
  }

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

  useEffect(() => {
    if (!channelId) return;
    const id = channelId;
    let cancelled = false;
    api
      .getChannel(id)
      .then((channel) => {
        if (!cancelled) setChannelDetail({ channelId: id, status: 'ready', channel });
      })
      .catch(() => {
        if (!cancelled) setChannelDetail({ channelId: id, status: 'missing' });
      });
    return () => {
      cancelled = true;
    };
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
  useOrgRealtime('channel_members', orgId, (payload) => {
    refetchChannels();
    const changed = payloadChannelId(payload);
    if (changed === null || changed === channelId) {
      refetchChannelDetail();
    }
  });

  const selectedChannel = channelDetail.status === 'ready' ? channelDetail.channel : null;
  const canManageChannel =
    selectedChannel !== null &&
    (selectedChannel.created_by === currentUserId || isOrgAdminOrOwner);

  // --- messages --------------------------------------------------------------

  useEffect(() => {
    if (!channelId) return;
    const id = channelId;
    let cancelled = false;
    async function load() {
      try {
        const rows = await api.listMessages(id, { limit: MESSAGE_PAGE_SIZE });
        if (cancelled) return;
        setView({
          channelId: id,
          messages: rows,
          loading: false,
          hasMore: rows.length >= MESSAGE_PAGE_SIZE,
        });
        void api.markChannelRead(id).then(refetchChannels).catch(() => undefined);
      } catch (e) {
        if (cancelled) return;
        toast({
          title: "Couldn't load messages",
          body: e instanceof Error ? e.message : undefined,
          tone: 'error',
        });
        setView((current) =>
          current.channelId === id ? { ...current, loading: false } : current,
        );
      }
    }
    void load();
    return () => {
      cancelled = true;
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
  useOrgRealtime('messages', orgId, (payload) => refetchMessages(payloadChannelId(payload)));

  async function loadOlderMessages() {
    const id = view.channelId;
    if (!id || view.messages.length === 0 || loadingOlder) return;
    setLoadingOlder(true);
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
      toast({
        title: "Couldn't load earlier messages",
        body: e instanceof Error ? e.message : undefined,
        tone: 'error',
      });
    } finally {
      setLoadingOlder(false);
    }
  }

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

  const totalUnread = channels.reduce((sum, c) => sum + c.unread_count, 0);

  return (
    <div className="flex flex-col gap-6">
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
            New
          </Button>
        ) : null}
      </div>

      {loadingChannels ? (
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
            body="Start a channel or DM to talk with your team - contacts and campaigns stay separate from this."
            action={
              canSend ? (
                <Button variant="secondary" onClick={() => setCreateOpen(true)}>
                  Start a conversation
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
                  className="flex items-center justify-between gap-3 p-4"
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

      <DialogRoot
        open={channelId !== null}
        onOpenChange={(open) => !open && closeChannel()}
      >
        {channelDetail.status === 'missing' ? (
          <Sheet title="Conversation not found" description="Chat">
            <div className="p-4 md:p-5">
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
          </Sheet>
        ) : selectedChannel ? (
          <Sheet
            title={
              renaming ? (
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
              ) : currentUserId ? (
                channelLabel(selectedChannel, currentUserId, namesById)
              ) : (
                'Conversation'
              )
            }
            description={
              <span className="flex items-center gap-3">
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
            }
            footer={
              canSend ? (
                <form
                  className="flex w-full items-end gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void handleSend();
                  }}
                >
                  <Textarea
                    value={composerBody}
                    onChange={(e) => setComposerBody(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        void handleSend();
                      }
                    }}
                    placeholder="Write a message..."
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
              )
            }
          >
            <div className="flex flex-col gap-3 p-4 md:p-5">
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

              {view.loading ? (
                <>
                  <Skeleton className="h-10 w-2/3" />
                  <Skeleton className="h-10 w-1/2 self-end" />
                </>
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
                            {m.body}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </>
              )}
            </div>
          </Sheet>
        ) : (
          <Sheet title="Loading..." description="Chat">
            <div className="flex flex-col gap-3 p-4 md:p-5">
              <Skeleton className="h-10 w-2/3" />
              <Skeleton className="h-10 w-1/2 self-end" />
            </div>
          </Sheet>
        )}
      </DialogRoot>

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
