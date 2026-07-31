const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type Disposition =
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

export interface Health {
  ok: boolean;
  dry_run_default: boolean;
  api_key_configured: boolean;
  max_calls_per_run: number;
  allowlist_active: boolean;
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
      /* non-JSON error body — keep the status message */
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
  getRun: (id: string) => req<Run>(`/api/runs/${id}`),
};
