/**
 * Makes `localhost:54321` inside the web container reach Kong.
 *
 * `NEXT_PUBLIC_SUPABASE_URL` is one value used from two places: the browser,
 * where it must be the published host port, and Next's middleware, which runs
 * inside the container where that port is nothing. Without this the middleware's
 * `getUser()` cannot reach GoTrue, every `/app` request looks signed-out, and
 * signing in loops straight back to `/login`.
 *
 * The obvious alternative - an internal URL for server-side clients - does not
 * work: `@supabase/ssr` derives the session cookie name from the URL's hostname,
 * so the two sides would read and write different cookies. Forwarding the port
 * keeps one URL, and keeps `lib/supabase/` ordinary Supabase code.
 */

import net from 'node:net';

const LISTEN_PORT = Number(process.env.BRIDGE_PORT ?? 54321);
const [TARGET_HOST, TARGET_PORT] = (process.env.BRIDGE_TARGET ?? 'kong:8000').split(':');

net
  .createServer((client) => {
    const upstream = net.connect(Number(TARGET_PORT), TARGET_HOST);
    client.pipe(upstream);
    upstream.pipe(client);
    // Either end closing is normal (keep-alive expiry, a cancelled fetch), and an
    // unhandled ECONNRESET here would take the whole dev server down with it.
    client.on('error', () => upstream.destroy());
    upstream.on('error', () => client.destroy());
  })
  .listen(LISTEN_PORT, '127.0.0.1', () => {
    console.log(`localhost:${LISTEN_PORT} -> ${TARGET_HOST}:${TARGET_PORT}`);
  });
