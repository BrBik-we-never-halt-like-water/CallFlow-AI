import { ChatShell } from './chat-shell';

// `ChatShell` reads the open conversation from `useSearchParams()` (via the
// `ChannelIdSync` leaf, under its own `<Suspense>` boundary) - Next.js's
// route cache otherwise treats that as a static shell with one dynamic
// "hole" to resume per request, and serves the *cached* shell (`channelId`
// frozen at whatever it read on the very first request that built it) to
// every later visitor behind Cloudflare, which caches it same as any other
// static response. `force-dynamic` renders this page fresh every request -
// this route's whole body is a client component anyway, so there is no
// static-generation benefit being given up.
export const dynamic = 'force-dynamic';

export default function ChatPage() {
  return <ChatShell />;
}
