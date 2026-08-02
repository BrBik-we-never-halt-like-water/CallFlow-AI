import { NextResponse } from "next/server";

/**
 * Keep-alive proxy for the backend.
 *
 * Render's free tier sleeps a service after ~15 minutes of no traffic, and a
 * cold start can take several minutes — long enough that a judge opening the
 * dashboard would conclude it is broken.
 *
 * Hitting this route pings the API's cheapest endpoint from the server side,
 * where there is no CORS preflight and no browser timeout to fight. An
 * external cron can also hit it every 10 minutes to stop the API sleeping at
 * all.
 */

const API = (() => {
  const raw = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!raw) return "http://127.0.0.1:8000";
  const withScheme = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
  return withScheme.replace(/\/+$/, "");
})();

export const dynamic = "force-dynamic";

export async function GET() {
  const started = Date.now();

  try {
    const res = await fetch(`${API}/`, {
      cache: "no-store",
      // Generous: a cold start is exactly the case this exists for.
      signal: AbortSignal.timeout(120_000),
    });

    return NextResponse.json({
      awake: res.ok,
      status: res.status,
      ms: Date.now() - started,
    });
  } catch (e) {
    return NextResponse.json(
      {
        awake: false,
        error: e instanceof Error ? e.name : "unknown",
        ms: Date.now() - started,
      },
      { status: 503 },
    );
  }
}
