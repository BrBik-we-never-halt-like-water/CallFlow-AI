import { NextResponse } from "next/server";

/**
 * Keep-alive proxy for the backend.
 *
 * Render's free tier sleeps a service after ~15 minutes of no traffic, and a
 * cold start can take a couple of minutes   long enough that a visitor would
 * conclude the app is broken. Pinging from the server side avoids the CORS
 * preflight and browser timeout that make this hard from the client.
 */

export const dynamic = "force-dynamic";

/** Public fallback, used when the environment gives us nothing usable. */
const PUBLIC_API = "https://callflow-api.onrender.com";

/**
 * An internal Render address (`callflow-api`, `callflow-api:10000`) is not
 * reachable from here and produces an opaque "fetch failed". Anything without
 * a dot   or with a non-standard port   is treated as internal.
 */
function isPublicHost(url: string): boolean {
  try {
    const { hostname, port } = new URL(url);
    if (hostname === "localhost" || /^\d+\.\d+\.\d+\.\d+$/.test(hostname)) return true;
    if (!hostname.includes(".")) return false;
    // Render's internal wiring appends :10000; public URLs use 80/443.
    return port === "" || port === "80" || port === "443";
  } catch {
    return false;
  }
}

function normalise(raw: string): string {
  const withScheme = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
  return withScheme.replace(/\/+$/, "");
}

/**
 * Resolve the API base at REQUEST time.
 *
 * Tries the configured values first, but silently falls back to the known
 * public URL rather than failing when the environment holds an internal
 * address   the wake path must keep working even when config drifts.
 */
function resolveApi(): { url: string; source: string } {
  for (const [source, raw] of [
    ["API_URL", process.env.API_URL],
    ["NEXT_PUBLIC_API_URL", process.env.NEXT_PUBLIC_API_URL],
  ] as const) {
    const value = raw?.trim();
    if (!value) continue;
    const url = normalise(value);
    if (isPublicHost(url)) return { url, source };
  }
  return { url: PUBLIC_API, source: "fallback" };
}

export async function GET() {
  const started = Date.now();
  const { url, source } = resolveApi();

  try {
    const res = await fetch(`${url}/`, {
      cache: "no-store",
      // Generous: a cold start is exactly the case this exists for.
      signal: AbortSignal.timeout(120_000),
    });

    return NextResponse.json({
      awake: res.ok,
      status: res.status,
      target: url,
      source,
      ms: Date.now() - started,
    });
  } catch (e) {
    return NextResponse.json(
      {
        awake: false,
        error: e instanceof Error ? `${e.name}: ${e.message}` : "unknown",
        target: url,
        source,
        ms: Date.now() - started,
      },
      { status: 503 },
    );
  }
}
