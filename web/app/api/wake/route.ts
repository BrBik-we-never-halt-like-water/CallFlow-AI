import { NextResponse } from "next/server";

/**
 * Keep-alive proxy for the backend.
 *
 * Render's free tier sleeps a service after ~15 minutes of no traffic, and a
 * cold start can take a couple of minutes — long enough that a judge opening
 * the dashboard would conclude it is broken.
 *
 * Hitting this route pings the API's cheapest endpoint from the server side,
 * where there is no CORS preflight and no browser timeout to fight. An
 * external cron can also hit it every 10 minutes to stop the API sleeping at
 * all.
 */

export const dynamic = "force-dynamic";

/**
 * Resolve the API base at REQUEST time, not module load.
 *
 * `NEXT_PUBLIC_*` values are inlined into the client bundle at build time, but
 * a server route reads them from the runtime environment — which is a
 * different thing and can be empty. Falling back to localhost here silently
 * points the server at itself, so we check a server-only var first and treat a
 * missing value as a real error instead of a bad default.
 */
function resolveApi(): string | null {
  const raw = (process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL)?.trim();
  if (!raw) return null;
  const withScheme = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
  return withScheme.replace(/\/+$/, "");
}

export async function GET() {
  const started = Date.now();
  const api = resolveApi();

  if (!api) {
    return NextResponse.json(
      {
        awake: false,
        error: "API_URL is not configured on the server",
        ms: 0,
      },
      { status: 500 },
    );
  }

  try {
    const res = await fetch(`${api}/`, {
      cache: "no-store",
      // Generous: a cold start is exactly the case this exists for.
      signal: AbortSignal.timeout(120_000),
    });

    return NextResponse.json({
      awake: res.ok,
      status: res.status,
      target: api,
      ms: Date.now() - started,
    });
  } catch (e) {
    return NextResponse.json(
      {
        awake: false,
        error: e instanceof Error ? `${e.name}: ${e.message}` : "unknown",
        target: api,
        ms: Date.now() - started,
      },
      { status: 503 },
    );
  }
}
