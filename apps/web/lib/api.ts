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
  /** The run this outcome belongs to — always the real run id now (see provider_call_id). */
  run_id: string | null;
  /** The voice provider's own call id, if a live call was placed. */
  provider_call_id: string | null;
  transcript: string | null;
  summary: string | null;
  sentiment: Sentiment;
  sentiment_reason: string | null;
  extracted: Record<string, unknown>;
  disposition: Disposition;
  disposition_reason: string | null;
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
  status: "running" | "completed" | "failed";
  started_at: string;
  finished_at: string | null;
  outcomes: Outcome[];
  error: string | null;
  stats: RunStats;
}

/**
 * A run as it appears in the list endpoint — no outcomes, plus a settled count.
 * The full run has to be fetched by id.
 */
export interface RunSummary {
  id: string;
  campaign_id: string;
  total: number;
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

/** The org a request acts against, when the caller belongs to more than one. */
export const ACTIVE_ORG_KEY = "callflow.active_org_id";

export interface Organisation {
  id: string;
  name: string;
  slug: string;
  logo_url: string | null;
  role: string;
}

export interface Member {
  user_id: string;
  name: string | null;
  email: string;
  avatar_url: string | null;
  role: string;
  joined_at: string;
}

export interface PendingInvite {
  id: string;
  email: string;
  role: string;
  expires_at: string;
  created_at: string;
}

export interface Team {
  members: Member[];
  pending: PendingInvite[];
}

export interface InvitationPreview {
  valid: boolean;
  reason: string | null;
  org_name: string | null;
  role: string | null;
  email: string | null;
}

export interface Profile {
  user_id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  last_used_at: string | null;
  created_at: string;
}

/** Only the create response ever carries the full key — shown once, never again. */
export interface ApiKeyCreated extends ApiKey {
  key: string;
}

export type Provider = "twilio" | "plivo";

export interface ProviderCredential {
  provider: Provider;
  label: string | null;
  phone_number: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderCredentialInput {
  identifier: string;
  secret: string;
  phone_number?: string;
  label?: string;
}

/**
 * Bearer token + active-org header for the authenticated endpoints.
 *
 * Imported lazily so `lib/api.ts` stays usable from contexts that never touch
 * Supabase (none today, but it keeps this module's only browser dependency opt-in).
 */
async function authHeaders(): Promise<Record<string, string>> {
  const { supabaseBrowser } = await import("@/lib/supabase/client");
  const {
    data: { session },
  } = await supabaseBrowser().auth.getSession();

  const headers: Record<string, string> = {};
  if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;

  try {
    const orgId = localStorage.getItem(ACTIVE_ORG_KEY);
    if (orgId) headers["X-Org-Id"] = orgId;
  } catch {
    /* private mode or blocked storage — fall back to the server's default org */
  }

  return headers;
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

async function authReq<T>(path: string, init?: RequestInit): Promise<T> {
  return req<T>(path, { ...init, headers: { ...(await authHeaders()), ...init?.headers } });
}

export const api = {
  health: () => req<Health>("/api/health"),
  campaigns: () => authReq<Campaign[]>("/api/v1/campaigns"),
  createCampaign: (draft: CampaignDraft) =>
    authReq<Campaign>("/api/v1/campaigns", {
      method: "POST",
      body: JSON.stringify(draft),
    }),
  deleteCampaign: (id: string) =>
    authReq<void>(`/api/v1/campaigns/${id}`, { method: "DELETE" }),
  preview: (campaign_id: string, contacts: ContactInput[]) =>
    authReq<{ previews: { name: string; goal?: string; error?: string }[] }>(
      "/api/v1/campaigns/preview",
      { method: "POST", body: JSON.stringify({ campaign_id, contacts }) },
    ),
  startRun: (campaign_id: string, contacts: ContactInput[]) =>
    authReq<{ run_id: string; total: number }>("/api/v1/runs", {
      method: "POST",
      body: JSON.stringify({ campaign_id, contacts }),
    }),
  listRuns: () => authReq<RunSummary[]>("/api/v1/runs"),
  getRun: (id: string) => authReq<Run>(`/api/v1/runs/${id}`),

  // --- organisations, team, profile — authenticated -----------------------
  listOrganisations: () => authReq<Organisation[]>("/api/v1/organisations"),
  createOrganisation: (name: string) =>
    authReq<Organisation>("/api/v1/organisations", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  updateActiveOrganisation: (patch: { name?: string; logo_url?: string }) =>
    authReq<Organisation>("/api/v1/organisations/me", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  completeOnboarding: (name: string) =>
    authReq<Organisation>("/api/v1/organisations/me/complete-onboarding", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  deleteActiveOrganisation: () =>
    authReq<void>("/api/v1/organisations/me", { method: "DELETE" }),
  listMembers: () => authReq<Team>("/api/v1/organisations/me/members"),
  inviteMember: (email: string, role: string) =>
    authReq<PendingInvite>("/api/v1/organisations/me/invitations", {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),
  revokeInvitation: (id: string) =>
    authReq<void>(`/api/v1/organisations/me/invitations/${id}`, { method: "DELETE" }),
  setMemberRole: (userId: string, role: string) =>
    authReq<void>(`/api/v1/organisations/me/members/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),
  removeMember: (userId: string) =>
    authReq<void>(`/api/v1/organisations/me/members/${userId}`, { method: "DELETE" }),
  previewInvitation: (token: string) =>
    req<InvitationPreview>(`/api/v1/invitations/${token}`),
  acceptInvitation: (token: string) =>
    authReq<{ org_id: string; org_name: string; org_slug: string; role: string }>(
      `/api/v1/invitations/${token}/accept`,
      { method: "POST" },
    ),
  updateProfile: (patch: { name?: string; avatar_url?: string }) =>
    authReq<Profile>("/api/v1/me", { method: "PATCH", body: JSON.stringify(patch) }),

  // --- API keys ------------------------------------------------------------
  listApiKeys: () => authReq<ApiKey[]>("/api/v1/api-keys"),
  createApiKey: (name: string) =>
    authReq<ApiKeyCreated>("/api/v1/api-keys", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  revokeApiKey: (id: string) => authReq<void>(`/api/v1/api-keys/${id}`, { method: "DELETE" }),

  // --- integrations ----------------------------------------------------------
  listProviderCredentials: () => authReq<ProviderCredential[]>("/api/v1/integrations/providers"),
  connectProvider: (provider: Provider, body: ProviderCredentialInput) =>
    authReq<ProviderCredential>(`/api/v1/integrations/providers/${provider}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  disconnectProvider: (provider: Provider) =>
    authReq<void>(`/api/v1/integrations/providers/${provider}`, { method: "DELETE" }),
};
