/** Public API URL, used when the environment holds nothing reachable. */
const PUBLIC_API = 'https://callflow-api.onrender.com';

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
    if (hostname === 'localhost' || /^\d+\.\d+\.\d+\.\d+$/.test(hostname))
      return true;
    if (!hostname.includes('.')) return false;
    // Render's internal wiring appends :10000; public URLs use 80/443.
    return port === '' || port === '80' || port === '443';
  } catch {
    return false;
  }
}

function resolveBase(raw: string | undefined): string {
  const value = raw?.trim();
  if (!value) {
    // No config at all: local dev.
    return typeof window !== 'undefined' &&
      window.location.hostname !== 'localhost'
      ? PUBLIC_API
      : 'http://127.0.0.1:8000';
  }

  const withScheme = /^https?:\/\//i.test(value) ? value : `https://${value}`;
  const cleaned = withScheme.replace(/\/+$/, '');

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
  | 'in_flight'
  | 'auto_closed'
  | 'escalated'
  | 'retry'
  | 'unreachable'
  | 'skipped';

export type Sentiment = 'positive' | 'neutral' | 'negative' | 'unknown';

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

export type FieldType = 'string' | 'boolean' | 'integer' | 'number';

export interface CampaignField {
  key: string;
  type: FieldType;
  description: string;
  required?: boolean;
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
  /** The run this outcome belongs to - always the real run id now (see provider_call_id). */
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

/**
 * A real, persisted "needs a person" item - a superset of `Outcome`, so it
 * can be handed anywhere an `Outcome` is expected (the transcript sheet,
 * `lampForOutcome`) with no adapter. `escalation_status` is this
 * escalation's own open/resolved lifecycle; `status` is the call's own
 * status, same meaning as `Outcome.status`.
 */
export interface Escalation extends Outcome {
  id: string;
  campaign_id: string;
  escalation_status: 'open' | 'resolved';
  assigned_to: string | null;
  assigned_to_name: string | null;
  assigned_by: string | null;
  assigned_by_name: string | null;
  resolved_by: string | null;
  resolved_by_name: string | null;
  resolved_at: string | null;
}

export type ShareResourceType = 'campaign' | 'escalation';
export type ShareRequestStatus = 'pending' | 'approved' | 'rejected';

/** Name + owner only - never a campaign's goal, fields, or results. What an
 *  operator sees to decide what's worth requesting (Phase 4). */
export interface CampaignDirectoryEntry {
  id: string;
  name: string;
  owner_user_id: string | null;
  owner_name: string | null;
}

/** Contact + campaign + current owner for an *open* escalation - never the
 *  transcript, sentiment, or disposition detail. */
export interface EscalationDirectoryEntry {
  id: string;
  contact_name: string;
  campaign_name: string;
  owner_user_id: string | null;
  owner_name: string | null;
}

export interface ShareRequest {
  id: string;
  resource_type: ShareResourceType;
  resource_id: string;
  resource_name: string | null;
  status: ShareRequestStatus;
  message: string | null;
  created_at: string;
  decided_at: string | null;
  requested_by: string;
  requested_by_name: string | null;
  owner_user_id: string;
  owner_name: string | null;
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
  status: 'running' | 'completed' | 'failed';
  started_at: string;
  finished_at: string | null;
  outcomes: Outcome[];
  error: string | null;
  stats: RunStats;
}

/**
 * A run as it appears in the list endpoint - no outcomes, plus a settled count.
 * The full run has to be fetched by id.
 */
export interface RunSummary {
  id: string;
  campaign_id: string;
  total: number;
  status: 'running' | 'completed' | 'failed';
  started_at: string;
  finished_at: string | null;
  error: string | null;
  completed: number;
}

/** The deployment's own defaults - `/api/health` is unauthenticated, so this is
 * never any one organisation's live usage. See `SafetySettings` for that. */
export interface Limits {
  daily_budget: number;
  per_window: number;
  window_minutes: number;
}

export interface Health {
  ok: boolean;
  /** Whether this deployment can actually place a call. False for the whole
   * voice-platform migration - CALL-E is removed and LiveKit origination is
   * not wired up yet - so every surface must say so rather than offering a
   * Start button that cannot work. */
  calling_available: boolean;
  max_calls_per_run: number;
  allowlist_active: boolean;
  limits?: Limits;
}

/** An organisation's own safety overrides, merged onto the deployment defaults,
 * plus that organisation's real, live rate-limit usage. */
export interface SafetySettings {
  allowlist: string[];
  max_calls_per_run: number;
  calls_per_window: number;
  window_minutes: number;
  daily_budget: number;
  used_today: number;
}

export interface ContactInput {
  name: string;
  phone: string;
  context?: Record<string, string>;
}

/** The org a request acts against, when the caller belongs to more than one. */
export const ACTIVE_ORG_KEY = 'callflow.active_org_id';

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

export interface TeamMemberSummary {
  user_id: string | null;
  name: string | null;
  avatar_url: string | null;
  total_runs: number;
  total_calls: number;
}

export interface TeamPerformance {
  user_id: string | null;
  name: string | null;
  avatar_url: string | null;
  total_runs: number;
  runs_active: number;
  runs_completed: number;
  runs_failed: number;
  total_calls: number;
  calls_closed: number;
  open_escalations: number;
  daily_allocation: number;
  credits_used_today: number;
}

export interface MyCredits {
  daily_allocation: number;
  used_today: number;
}

/**
 * A plan's ceilings. `null` means unlimited, never a sentinel — and `0` is a
 * real, enforced value, so never collapse the two with a falsiness check.
 */
export interface Entitlements {
  max_voice_agents: number | null;
  max_seats: number | null;
  max_organisations: number | null;
  max_ai_integrations: number | null;
  daily_call_budget: number | null;
  llm_spend_limit_usd: number;
}

/** What the organisation has actually used, against `Entitlements`. */
export interface EntitlementUsage {
  voice_agents: number;
  seats: number;
  organisations: number;
  ai_integrations: number;
  calls_today: number;
}

/**
 * Prices come from the gateway, not from `lib/pricing.ts` — it is the Merchant
 * of Record and holds the price of record. `amount_minor` is an integer in the
 * currency's smallest unit; render it with `formatMinorUnits`.
 */
export interface PlanPrice {
  amount_minor: number;
  currency: string;
  period: 'monthly' | 'annual';
}

export interface PlanOption {
  plan_id: string;
  name: string;
  entitlements: Entitlements;
  /** Empty when the plan has no checkout — enterprise is invoiced. */
  prices: PlanPrice[];
  self_serve: boolean;
  current: boolean;
}

export type SubscriptionStatus =
  | 'pending'
  | 'active'
  | 'on_hold'
  | 'cancelled'
  | 'expired'
  | 'failed';

export interface Subscription {
  status: SubscriptionStatus;
  plan_id: string;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  /** Why a renewal failed, shown verbatim to an owner. */
  last_error: string | null;
}

export interface PaymentRecord {
  /** False when the payment hasn't settled, or the gateway issues no invoice. */
  has_receipt: boolean;
  id: string;
  amount_minor: number;
  currency: string;
  status: 'succeeded' | 'failed' | 'refunded';
  description: string | null;
  paid_at: string | null;
}

/* --- platform admin (docs/PLATFORM_ADMIN.md) --------------------------------
   Every one of these 404s for anyone without a `platform_admins` row, so a
   non-admin never distinguishes "no permission" from "no such route". */

export interface PlatformOrg {
  org_id: string;
  name: string;
  slug: string;
  plan_id: string;
  has_override: boolean;
  member_count: number;
  agent_count: number;
  run_count: number;
  created_at: string;
}

export interface EntitlementOverride {
  org_id: string;
  max_voice_agents: number | null;
  max_seats: number | null;
  max_organisations: number | null;
  max_ai_integrations: number | null;
  daily_call_budget: number | null;
  llm_spend_limit_usd: number | null;
  /** Limits with no ceiling at all. `null` above means "inherit the plan", which
   *  is a different thing - hence two channels rather than one. */
  unlimited: string[];
  note: string | null;
  updated_at: string;
}

export interface PlatformAuditEntry {
  id: string;
  actor_user_id: string | null;
  action: string;
  target_org_id: string | null;
  reason: string;
  created_at: string;
}

export interface OverrideInput {
  max_voice_agents: number | null;
  max_seats: number | null;
  max_organisations: number | null;
  max_ai_integrations: number | null;
  daily_call_budget: number | null;
  unlimited: string[];
  note: string | null;
  reason: string;
}

export interface BillingOverview {
  plan_id: string;
  plan_name: string;
  /**
   * `null` for an organisation that has never subscribed, and for an enterprise
   * account on an invoiced deal — neither is an error state, so both must render
   * as a plan without a subscription rather than as a failure.
   */
  subscription: Subscription | null;
  entitlements: Entitlements;
  usage: EntitlementUsage;
  /**
   * What runs actually stop at today. Distinct from
   * `entitlements.daily_call_budget`, which is what the *plan* permits: a
   * deployment default or the org's own Settings → Safety value can be lower, and
   * the lower one wins. Show this on the meter, or the page promises a number
   * runs will not honour.
   */
  effective_daily_call_budget: number;
  /** True when a platform admin has set a negotiated limit on this org. */
  has_custom_limits: boolean;
  payments: PaymentRecord[];
  /**
   * False on a deployment with no gateway key. The Billing page uses this to keep
   * saying "no payment processor is connected" rather than offering an upgrade
   * button that would run against a stub and take no money (CLAUDE.md §4 #9).
   */
  payments_configured: boolean;
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

/** Only the create response ever carries the full key - shown once, never again. */
export interface ApiKeyCreated extends ApiKey {
  key: string;
}

export interface Suppression {
  id: string;
  phone_masked: string;
  source: string;
  reason: string | null;
  suppressed_at: string;
}

export type ChannelKind = 'channel' | 'dm';

export interface Channel {
  id: string;
  kind: ChannelKind;
  name: string | null;
  created_by: string | null;
  member_ids: string[];
  unread_count: number;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  channel_id: string;
  sender_id: string | null;
  sender_name: string | null;
  body: string;
  created_at: string;
  edited_at: string | null;
}

/** Whatever the API's catalogue says it supports - not a hard-coded pair.
 * The list used to live here *and* on the server; the two drifting is how a
 * provider becomes selectable in the UI and unstorable by the API. */
export type Provider = string;

/** What a credential is for. The first four mirror `voice_agents`' own columns
 * so an organisation can see it needs one of each before a call is possible;
 * the last three have no feature behind them yet - see `wired`. */
export type ProviderRole =
  | 'telephony'
  | 'transcriber'
  | 'voice'
  | 'intelligence'
  | 'storage'
  | 'automation'
  | 'observability';

/** How a vendor lets you connect. Only some host a login - a "Connect with X"
 * button on a vendor that offers none would be a success state for something
 * that never happens. */
export type ConnectMethod = 'oauth' | 'api_key';

/** One input on a provider's connect form, described by the server so this
 * client can render a vendor it has never heard of. */
export interface CredentialField {
  key: string;
  label: string;
  /** Masked on entry and never returned by any read endpoint. */
  secret: boolean;
  required: boolean;
  placeholder: string;
  help: string | null;
  /** A service-account JSON needs a textarea, not a single line. */
  multiline: boolean;
}

export interface ProviderSpec {
  id: Provider;
  name: string;
  /** A vendor can serve several - one Deepgram key does speech in and out. */
  roles: ProviderRole[];
  connect: ConnectMethod;
  summary: string;
  fields: CredentialField[];
  docs_url: string;
  /** False means the credential is stored and nothing reads it yet. The card
   * says so rather than showing it as connected. */
  wired: boolean;
  /** One key proxies many models, so the agent must also name which to run. */
  needs_model: boolean;
  /** A short constraint worth stating on the card. */
  note: string | null;
}

export interface ProviderCredential {
  provider: Provider;
  label: string | null;
  phone_number: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderCredentialInput {
  /** Keyed by the provider's own `CredentialField.key` values. The server
   * rejects a key the provider never declared rather than dropping it. */
  fields: Record<string, string>;
  phone_number?: string;
  label?: string;
}

export type AiProvider =
  | 'sarvam'
  | 'deepgram'
  | 'elevenlabs'
  | 'openai'
  | 'openrouter';

export interface AiProviderCredential {
  provider: AiProvider;
  label: string | null;
  created_at: string;
  updated_at: string;
}

export interface AiProviderCredentialInput {
  api_key: string;
  label?: string;
}

/** Same two vendors as `Provider` - named separately because a voice agent's
 *  telephony assignment is its own concept from the integrations-tab
 *  credential, not because the value set differs. */
export type TelephonyProvider = Provider;

export interface ProviderCatalogEntry {
  id: string;
  category: 'stt' | 'tts' | 'llm';
  name: string;
  vendor: string;
  cost_note: string;
  latency_note: string;
  quality_note: string;
  preview_available: boolean;
  /** The same figures as the `*_note` strings, in machine units, so the
   *  builder can draw a comparable breakdown per leg. Null where the vendor
   *  bills in a unit the field doesn't cover - see `catalog.py`. */
  latency_ms: number | null;
  /** STT and TTS bill per minute of audio; LLM entries carry the two token
   *  fields instead. */
  cost_per_min_usd: number | null;
  cost_per_1m_input_usd: number | null;
  cost_per_1m_output_usd: number | null;
  voice_options: string[];
  connected: boolean;
}

export interface TelephonyOption {
  provider: TelephonyProvider;
  connected: boolean;
  phone_number_masked: string | null;
}

export interface ProviderCatalog {
  stt: ProviderCatalogEntry[];
  tts: ProviderCatalogEntry[];
  llm: ProviderCatalogEntry[];
  telephony: TelephonyOption[];
}

export interface VoiceAgentDraft {
  name: string;
  kind?: 'custom' | 'prebuilt';
  stt_provider?: string | null;
  tts_provider?: string | null;
  llm_provider?: string | null;
  llm_model?: string | null;
  voice_id?: string | null;
  system_prompt?: string | null;
  prebuilt_persona?: string | null;
  telephony_provider?: TelephonyProvider | null;
  /** What the agent has to come back with. Same shape as a campaign's
   *  `extra_fields` - both end up as structured call results. */
  collect_fields?: CampaignField[];
}

export interface VoiceAgent {
  id: string;
  org_id: string;
  name: string;
  kind: 'custom' | 'prebuilt';
  stt_provider: string | null;
  tts_provider: string | null;
  llm_provider: string | null;
  llm_model: string | null;
  voice_id: string | null;
  system_prompt: string | null;
  prebuilt_persona: string | null;
  telephony_provider: TelephonyProvider | null;
  /** What the agent has to come back with from a call. Same shape as a
   *  campaign's `extra_fields` - both become structured call results. */
  collect_fields: CampaignField[];
  created_at: string;
  created_by: string | null;
  created_by_name: string | null;
  created_by_avatar_url: string | null;
}

export interface VoicePreviewRequest {
  provider: string;
  kind: 'stt' | 'tts';
  text?: string;
  voice_id?: string;
  audio_base64?: string;
  language?: string;
}

export interface VoicePreviewResult {
  available: boolean;
  reason: string | null;
  audio_base64: string | null;
  transcript: string | null;
}

/**
 * Bearer token + active-org header for the authenticated endpoints.
 *
 * Imported lazily so `lib/api.ts` stays usable from contexts that never touch
 * Supabase (none today, but it keeps this module's only browser dependency opt-in).
 */
async function authHeaders(): Promise<Record<string, string>> {
  const { supabaseBrowser } = await import('@/lib/supabase/client');
  const {
    data: { session },
  } = await supabaseBrowser().auth.getSession();

  const headers: Record<string, string> = {};
  if (session?.access_token)
    headers.Authorization = `Bearer ${session.access_token}`;

  try {
    const orgId = localStorage.getItem(ACTIVE_ORG_KEY);
    if (orgId) headers['X-Org-Id'] = orgId;
  } catch {
    /* private mode or blocked storage - fall back to the server's default org */
  }

  return headers;
}

/**
 * A request that has not answered by now is not going to.
 *
 * `fetch()` has no default timeout, so a server that accepts a connection and
 * then never replies - the API waiting on an exhausted database pool is the
 * case that prompted this - leaves the promise pending forever. Every loader
 * in the app is driven by one of these promises, so "forever" renders as a
 * spinner that never resolves and never errors, with nothing in the console
 * (`ISSUES.md` #122). Well above the API's own 30s query ceiling, so a slow
 * query still returns its real error rather than being cut off here.
 */
const REQUEST_TIMEOUT_MS = 45_000;

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
      cache: 'no-store',
      signal: init?.signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (error) {
    // Two different failures reach here and they need different advice: the
    // timeout above means the server took the request and went quiet, which
    // is not something the reader can fix by checking their wifi.
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      throw new Error(
        `The service accepted the request but never answered (waited ${
          REQUEST_TIMEOUT_MS / 1000
        }s). It may be overloaded - try again in a moment.`,
      );
    }
    // fetch() itself throwing means the request never reached a server at
    // all - DNS, a dropped connection, a dev server mid-restart. The raw
    // `TypeError: Failed to fetch` is meaningless to whoever is looking at
    // the toast, so this is the one place that translates it, rather than
    // every caller of the API client reinventing the same catch.
    throw new Error(
      "The service didn't respond. Check your connection and try again.",
    );
  }
  if (!res.ok) {
    let message = `Request failed: ${res.status}`;
    try {
      const body = await res.json();
      // FastAPI puts validation and HTTPException messages under `detail`.
      if (typeof body?.detail === 'string') message = body.detail;
      else if (Array.isArray(body?.detail)) {
        message = body.detail
          .map((d: { msg?: string }) => d.msg)
          .filter(Boolean)
          .join('; ');
      }
    } catch {
      /* non-JSON error body - keep the status message */
    }
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function authReq<T>(path: string, init?: RequestInit): Promise<T> {
  return req<T>(path, {
    ...init,
    headers: { ...(await authHeaders()), ...init?.headers },
  });
}

export const api = {
  health: () => req<Health>('/api/health'),
  campaigns: () => authReq<Campaign[]>('/api/v1/campaigns'),
  createCampaign: (draft: CampaignDraft) =>
    authReq<Campaign>('/api/v1/campaigns', {
      method: 'POST',
      body: JSON.stringify(draft),
    }),
  updateCampaign: (id: string, draft: CampaignDraft) =>
    authReq<Campaign>(`/api/v1/campaigns/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(draft),
    }),
  deleteCampaign: (id: string) =>
    authReq<void>(`/api/v1/campaigns/${id}`, { method: 'DELETE' }),
  preview: (campaign_id: string, contacts: ContactInput[]) =>
    authReq<{ previews: { name: string; goal?: string; error?: string }[] }>(
      '/api/v1/campaigns/preview',
      { method: 'POST', body: JSON.stringify({ campaign_id, contacts }) },
    ),
  startRun: (campaign_id: string, contacts: ContactInput[]) =>
    authReq<{ run_id: string; total: number }>('/api/v1/runs', {
      method: 'POST',
      body: JSON.stringify({ campaign_id, contacts }),
    }),
  listRuns: () => authReq<RunSummary[]>('/api/v1/runs'),
  getRun: (id: string) => authReq<Run>(`/api/v1/runs/${id}`),
  /** Stops a run from dialling further contacts. Can't interrupt a call
   *  already in progress - see the endpoint's own docstring. */
  cancelRun: (id: string) =>
    authReq<{ status: string }>(`/api/v1/runs/${id}/cancel`, {
      method: 'POST',
    }),
  teamSummary: () =>
    authReq<TeamMemberSummary[]>('/api/v1/runs/team-summary'),

  // --- escalations - authenticated -----------------------------------------
  listEscalations: () => authReq<Escalation[]>('/api/v1/escalations'),
  escalationDirectory: () =>
    authReq<EscalationDirectoryEntry[]>('/api/v1/escalations/directory'),
  assignEscalation: (id: string, userId: string) =>
    authReq<void>(`/api/v1/escalations/${id}/assign`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    }),
  resolveEscalation: (id: string) =>
    authReq<void>(`/api/v1/escalations/${id}/resolve`, { method: 'POST' }),

  // --- sharing (Phase 4) - authenticated ------------------------------------
  campaignDirectory: () =>
    authReq<CampaignDirectoryEntry[]>('/api/v1/campaigns/directory'),
  listShareRequests: () => authReq<ShareRequest[]>('/api/v1/share-requests'),
  createShareRequest: (
    resourceType: ShareResourceType,
    resourceId: string,
    message?: string,
  ) =>
    authReq<ShareRequest>('/api/v1/share-requests', {
      method: 'POST',
      body: JSON.stringify({
        resource_type: resourceType,
        resource_id: resourceId,
        message: message || undefined,
      }),
    }),
  approveShareRequest: (id: string) =>
    authReq<void>(`/api/v1/share-requests/${id}/approve`, { method: 'POST' }),
  rejectShareRequest: (id: string) =>
    authReq<void>(`/api/v1/share-requests/${id}/reject`, { method: 'POST' }),

  // --- team performance + credits - authenticated --------------------------
  teamPerformance: () =>
    authReq<TeamPerformance[]>('/api/v1/organisations/me/team-performance'),
  myCredits: () =>
    authReq<MyCredits>('/api/v1/organisations/me/members/me/credits'),
  setMemberCredits: (userId: string, dailyAllocation: number) =>
    authReq<void>(`/api/v1/organisations/me/members/${userId}/credits`, {
      method: 'PATCH',
      body: JSON.stringify({ daily_allocation: dailyAllocation }),
    }),

  // --- platform admin ------------------------------------------------------
  platformOrgs: (search?: string) =>
    authReq<PlatformOrg[]>(
      `/api/v1/platform/organisations${search ? `?search=${encodeURIComponent(search)}` : ''}`,
    ),
  platformOverride: (orgId: string) =>
    authReq<EntitlementOverride | null>(
      `/api/v1/platform/organisations/${orgId}/entitlements`,
    ),
  // `reason` is mandatory server-side and lands in the audit log beside the
  // before/after state. There is no unaudited variant of either of these.
  platformSetPlan: (orgId: string, planId: string, reason: string) =>
    authReq<void>(`/api/v1/platform/organisations/${orgId}/plan`, {
      method: 'PUT',
      body: JSON.stringify({ plan_id: planId, reason }),
    }),
  platformSetOverride: (orgId: string, body: OverrideInput) =>
    authReq<void>(`/api/v1/platform/organisations/${orgId}/entitlements`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  platformAudit: (limit = 100) =>
    authReq<PlatformAuditEntry[]>(`/api/v1/platform/audit?limit=${limit}`),

  // --- billing -------------------------------------------------------------
  /**
   * The plan ladder with the gateway's live prices, for the marketing site.
   *
   * `req`, not `authReq`: the public pages have no session, and adding a bearer
   * header they cannot produce is what would make a pricing section render empty
   * for every visitor who is not already a customer. `current` is always false
   * here - there is no organisation to be current for.
   */
  publicPlans: () => req<PlanOption[]>('/api/v1/public/billing/plans'),
  billingPlans: () => authReq<PlanOption[]>('/api/v1/billing/plans'),
  billingOverview: () => authReq<BillingOverview>('/api/v1/billing/subscription'),
  /**
   * The gateway's invoice PDF for one payment, as a blob.
   *
   * Fetched rather than linked because the endpoint needs the session's bearer
   * token - a plain `<a href>` sends no Authorization header and would 401. The
   * caller turns the blob into an object URL and revokes it.
   */
  paymentReceipt: async (paymentId: string): Promise<Blob> => {
    const res = await fetch(
      `${BASE}/api/v1/billing/payments/${paymentId}/receipt`,
      { headers: await authHeaders(), cache: 'no-store' },
    );
    if (!res.ok) {
      throw new Error(
        res.status === 404
          ? 'No receipt is available for this payment yet.'
          : "The receipt couldn't be fetched. Try again in a moment.",
      );
    }
    return res.blob();
  },
  // `idempotencyKey` is the caller's own retry token: reusing it resumes the
  // same checkout instead of opening a second one, the same contract
  // `connectNumber` already has. Generate it once per button press, not per
  // render, or a re-render starts a new subscription attempt.
  startCheckout: (planId: string, period: 'monthly' | 'annual', idempotencyKey: string) =>
    authReq<{ checkout_url: string }>('/api/v1/billing/checkout', {
      method: 'POST',
      body: JSON.stringify({ plan_id: planId, period, idempotency_key: idempotencyKey }),
    }),
  changePlan: (planId: string, period: 'monthly' | 'annual') =>
    authReq<Subscription>('/api/v1/billing/change-plan', {
      method: 'POST',
      body: JSON.stringify({ plan_id: planId, period }),
    }),
  cancelSubscription: () =>
    authReq<Subscription>('/api/v1/billing/cancel', { method: 'POST' }),
  // Pulls whatever the gateway actually holds and applies it. For when a webhook
  // never arrived - the payment succeeded but nothing told us.
  syncBilling: () =>
    authReq<{ applied: boolean; detail: string }>('/api/v1/billing/sync', {
      method: 'POST',
    }),

  // --- organisations, team, profile - authenticated -----------------------
  listOrganisations: () => authReq<Organisation[]>('/api/v1/organisations'),
  createOrganisation: (name: string) =>
    authReq<Organisation>('/api/v1/organisations', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  updateActiveOrganisation: (patch: { name?: string; logo_url?: string }) =>
    authReq<Organisation>('/api/v1/organisations/me', {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),
  completeOnboarding: (name: string) =>
    authReq<Organisation>('/api/v1/organisations/me/complete-onboarding', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  deleteActiveOrganisation: () =>
    authReq<void>('/api/v1/organisations/me', { method: 'DELETE' }),
  listMembers: (q?: string) =>
    authReq<Team>(
      `/api/v1/organisations/me/members${q ? `?q=${encodeURIComponent(q)}` : ''}`,
    ),
  inviteMember: (email: string, role: string) =>
    authReq<PendingInvite>('/api/v1/organisations/me/invitations', {
      method: 'POST',
      body: JSON.stringify({ email, role }),
    }),
  revokeInvitation: (id: string) =>
    authReq<void>(`/api/v1/organisations/me/invitations/${id}`, {
      method: 'DELETE',
    }),
  setMemberRole: (userId: string, role: string) =>
    authReq<void>(`/api/v1/organisations/me/members/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    }),
  removeMember: (userId: string) =>
    authReq<void>(`/api/v1/organisations/me/members/${userId}`, {
      method: 'DELETE',
    }),
  previewInvitation: (token: string) =>
    req<InvitationPreview>(`/api/v1/invitations/${token}`),
  acceptInvitation: (token: string) =>
    authReq<{
      org_id: string;
      org_name: string;
      org_slug: string;
      role: string;
    }>(`/api/v1/invitations/${token}/accept`, { method: 'POST' }),
  updateProfile: (patch: { name?: string; avatar_url?: string }) =>
    authReq<Profile>('/api/v1/me', {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),

  // --- safety ----------------------------------------------------------------
  getSafetySettings: () => authReq<SafetySettings>('/api/v1/safety'),
  updateSafetySettings: (patch: {
    allowlist: string[];
    max_calls_per_run: number;
    calls_per_window: number;
    window_minutes: number;
    daily_budget: number;
  }) =>
    authReq<SafetySettings>('/api/v1/safety', {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),

  // --- API keys ------------------------------------------------------------
  listApiKeys: () => authReq<ApiKey[]>('/api/v1/api-keys'),
  createApiKey: (name: string) =>
    authReq<ApiKeyCreated>('/api/v1/api-keys', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  revokeApiKey: (id: string) =>
    authReq<void>(`/api/v1/api-keys/${id}`, { method: 'DELETE' }),

  // --- suppression list ------------------------------------------------------
  listSuppressions: () => authReq<Suppression[]>('/api/v1/suppressions'),
  addSuppression: (phone: string, reason?: string) =>
    authReq<Suppression>('/api/v1/suppressions', {
      method: 'POST',
      body: JSON.stringify({ phone, reason }),
    }),
  removeSuppression: (id: string) =>
    authReq<void>(`/api/v1/suppressions/${id}`, { method: 'DELETE' }),

  // --- integrations ----------------------------------------------------------
  listProviderCatalogue: () =>
    authReq<ProviderSpec[]>('/api/v1/integrations/catalogue'),
  listProviderCredentials: () =>
    authReq<ProviderCredential[]>('/api/v1/integrations/providers'),
  exchangeOAuthCode: (
    provider: Provider,
    body: { code: string; code_verifier?: string },
  ) =>
    authReq<ProviderCredential>(
      `/api/v1/integrations/providers/${provider}/oauth/exchange`,
      { method: 'POST', body: JSON.stringify(body) },
    ),
  connectProvider: (provider: Provider, body: ProviderCredentialInput) =>
    authReq<ProviderCredential>(`/api/v1/integrations/providers/${provider}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  disconnectProvider: (provider: Provider) =>
    authReq<void>(`/api/v1/integrations/providers/${provider}`, {
      method: 'DELETE',
    }),

  // --- voice agents + ai providers (Agentic tab) ----------------------------
  listVoiceAgents: () => authReq<VoiceAgent[]>('/api/v1/voice-agents'),
  createVoiceAgent: (draft: VoiceAgentDraft) =>
    authReq<VoiceAgent>('/api/v1/voice-agents', {
      method: 'POST',
      body: JSON.stringify(draft),
    }),
  updateVoiceAgent: (id: string, draft: VoiceAgentDraft) =>
    authReq<VoiceAgent>(`/api/v1/voice-agents/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(draft),
    }),
  deleteVoiceAgent: (id: string) =>
    authReq<void>(`/api/v1/voice-agents/${id}`, { method: 'DELETE' }),
  voiceProviderCatalog: () =>
    authReq<ProviderCatalog>('/api/v1/voice-agents/providers'),
  previewVoice: (body: VoicePreviewRequest) =>
    authReq<VoicePreviewResult>('/api/v1/voice-agents/preview', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  listAiProviderCredentials: () =>
    authReq<AiProviderCredential[]>('/api/v1/ai-providers'),
  connectAiProvider: (provider: AiProvider, body: AiProviderCredentialInput) =>
    authReq<AiProviderCredential>(`/api/v1/ai-providers/${provider}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  disconnectAiProvider: (provider: AiProvider) =>
    authReq<void>(`/api/v1/ai-providers/${provider}`, { method: 'DELETE' }),

  // --- internal team chat ---------------------------------------------------
  listChannels: () => authReq<Channel[]>('/api/v1/channels'),
  // A dedicated cheap aggregate for the nav badge - not derived from
  // listChannels(), which pays for every channel's full member list on every
  // call. This one is mounted app-wide (every page, not just /app/chat), so
  // it has to stay a single small query regardless of group size.
  getUnreadCount: () =>
    authReq<{ unread_count: number }>('/api/v1/channels/unread-count'),
  getChannel: (channelId: string) =>
    authReq<Channel>(`/api/v1/channels/${channelId}`),
  createChannel: (draft: {
    kind: ChannelKind;
    name?: string | null;
    member_ids: string[];
  }) =>
    authReq<Channel>('/api/v1/channels', {
      method: 'POST',
      body: JSON.stringify(draft),
    }),
  renameChannel: (channelId: string, name: string) =>
    authReq<Channel>(`/api/v1/channels/${channelId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),
  addChannelMember: (channelId: string, userId: string) =>
    authReq<void>(`/api/v1/channels/${channelId}/members`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    }),
  removeChannelMember: (channelId: string, userId: string) =>
    authReq<void>(`/api/v1/channels/${channelId}/members/${userId}`, {
      method: 'DELETE',
    }),
  markChannelRead: (channelId: string) =>
    authReq<void>(`/api/v1/channels/${channelId}/read`, { method: 'POST' }),
  listMessages: (
    channelId: string,
    opts?: { before?: string; beforeId?: string; limit?: number },
  ) => {
    const params = new URLSearchParams();
    if (opts?.before) params.set('before', opts.before);
    if (opts?.beforeId) params.set('before_id', opts.beforeId);
    if (opts?.limit) params.set('limit', String(opts.limit));
    const qs = params.toString();
    return authReq<ChatMessage[]>(
      `/api/v1/channels/${channelId}/messages${qs ? `?${qs}` : ''}`,
    );
  },
  sendMessage: (channelId: string, body: string) =>
    authReq<ChatMessage>(`/api/v1/channels/${channelId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    }),
  editMessage: (channelId: string, messageId: string, body: string) =>
    authReq<ChatMessage>(`/api/v1/channels/${channelId}/messages/${messageId}`, {
      method: 'PATCH',
      body: JSON.stringify({ body }),
    }),
  deleteMessage: (channelId: string, messageId: string) =>
    authReq<void>(`/api/v1/channels/${channelId}/messages/${messageId}`, {
      method: 'DELETE',
    }),
};
