/** Public API URL, used when the environment holds nothing reachable. */
const PUBLIC_API = "https://callflow-api.onrender.com";

/**
 * Is this a hostname a browser can actually resolve?
 *
 * Render's `fromService` helpers are traps: `property: host` yields a bare
 * service name ("callflow-api") and `hostport` yields an internal address
 * ("callflow-api:10000"). Both look plausible in config and both fail with an
 * opaque "fetch failed" at runtime.
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

function resolveBase(raw: string | undefined): string {
  const value = raw?.trim();
  if (!value) {
    // No config at all: local dev.
    return typeof window !== "undefined" && window.location.hostname !== "localhost"
      ? PUBLIC_API
      : "http://127.0.0.1:8000";
  }

  const withScheme = /^https?:\/\//i.test(value) ? value : `https://${value}`;
  const cleaned = withScheme.replace(/\/+$/, "");

  if (!isPublicHost(cleaned)) {
    console.warn(
      `[callflow] NEXT_PUBLIC_API_URL is "${cleaned}", which is not reachable ` +
        `from a browser. Falling back to ${PUBLIC_API}.`,
    );
    return PUBLIC_API;
  }

  return cleaned;
}

const BASE = resolveBase(process.env.NEXT_PUBLIC_API_URL);

export type Disposition =
  | "in_flight"
  | "auto_closed"
  | "escalated"
  | "retry"
  | "unreachable"
  | "skipped";

export type Sentiment = "positive" | "neutral" | "negative" | "unknown";

export interface Campaign {
  id: string;
  name: string;
  region: string | null;
  language: string | null;
  outcome_fields: Record<string, string>;
  goal_template: string;
  goal_preview: string;
  built_in: boolean;
}

export type FieldType = "string" | "boolean" | "integer" | "number";

export interface CampaignField {
  key: string;
  type: FieldType;
  description: string;
}

export interface CampaignDraft {
  name: string;
  goal_template: string;
  extra_fields: CampaignField[];
  region?: string | null;
  language?: string | null;
  escalate_on_negative?: boolean;
}

export interface Outcome {
  contact_name: string;
  phone_masked: string;
  campaign_id: string;
  status: string;
  run_id: string | null;
  transcript: string | null;
  summary: string | null;
  sentiment: Sentiment;
  sentiment_reason: string | null;
  extracted: Record<string, unknown>;
  disposition: Disposition;
  disposition_reason: string | null;
  dry_run: boolean;
  error: string | null;
  duration_seconds: number | null;
  created_at: string;
}

export interface RunStats {
  completed: number;
  total: number;
  escalated: number;
  auto_closed: number;
  needs_human_pct: number;
}

export interface Run {
  id: string;
  campaign_id: string;
  total: number;
  dry_run: boolean;
  status: "running" | "completed" | "failed";
  started_at: string;
  finished_at: string | null;
  outcomes: Outcome[];
  error: string | null;
  stats: RunStats;
}

/**
 * A run as it appears in the list endpoint   no outcomes, plus a settled count.
 * The full run has to be fetched by id.
 */
export interface RunSummary {
  id: string;
  campaign_id: string;
  total: number;
  dry_run: boolean;
  status: "running" | "completed" | "failed";
  started_at: string;
  finished_at: string | null;
  error: string | null;
  completed: number;
}

export interface Limits {
  used_today: number;
  daily_budget: number;
  per_window: number;
  window_minutes: number;
}

export interface Health {
  ok: boolean;
  dry_run_default: boolean;
  api_key_configured: boolean;
  max_calls_per_run: number;
  allowlist_active: boolean;
  limits?: Limits;
}

export interface ContactInput {
  name: string;
  phone: string;
  context?: Record<string, string>;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    let message = `Request failed: ${res.status}`;
    try {
      const body = await res.json();
      // FastAPI puts validation and HTTPException messages under `detail`.
      if (typeof body?.detail === "string") message = body.detail;
      else if (Array.isArray(body?.detail)) {
        message = body.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ");
      }
    } catch {
      /* non-JSON error body   keep the status message */
    }
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<Health>("/api/health"),
  campaigns: () => req<Campaign[]>("/api/campaigns"),
  createCampaign: (draft: CampaignDraft) =>
    req<Campaign>("/api/campaigns", {
      method: "POST",
      body: JSON.stringify(draft),
    }),
  deleteCampaign: (id: string) =>
    req<void>(`/api/campaigns/${id}`, { method: "DELETE" }),
  preview: (campaign_id: string, contacts: ContactInput[]) =>
    req<{ previews: { name: string; goal?: string; error?: string }[] }>(
      "/api/preview",
      { method: "POST", body: JSON.stringify({ campaign_id, contacts }) },
    ),
  startRun: (campaign_id: string, contacts: ContactInput[], dry_run: boolean) =>
    req<{ run_id: string; dry_run: boolean; total: number }>("/api/runs", {
      method: "POST",
      body: JSON.stringify({ campaign_id, contacts, dry_run }),
    }),
  listRuns: () => req<RunSummary[]>("/api/runs"),
  getRun: (id: string) => req<Run>(`/api/runs/${id}`),
};
