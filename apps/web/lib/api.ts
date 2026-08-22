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

export type FieldType = 'string' | 'boolean' | 'integer' | 'number';

/**
 * One thing an agent has to establish while the call is happening.
 *
 * `required` is load-bearing rather than advisory: a completed call missing a
 * required answer is escalated to a person, with this field's `description`
 * becoming what they are told to ask (ADR-5).
 */
export interface CollectField {
  key: string;
  type: FieldType;
  description: string;
  required?: boolean;
}

/** One number the organisation owns, as a picker needs it. */
export interface TelephonyNumber {
  id: string;
  provider: string;
  /** Masked. The full number is a separate, permissioned reveal. */
  phone_masked: string;
  label: string | null;
  status: string;
  /** Whether a run may dial from it - resolved server-side from the domain's
   *  own rule, so the client never compares status strings. */
  diallable: boolean;
  last_error: string | null;
  last_synced_at: string | null;
}

/** One attempt at pointing a number at LiveKit. `status` plus `last_error` is
 *  the whole of what the screen needs - the trunk ids are LiveKit's internal
 *  handles and an operator can do nothing with them. */
export interface NumberProvisioning {
  id: string;
  voice_agent_id: string;
  status: string;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface Outcome {
  contact_name: string;
  phone_masked: string;
  /** Which agent held the conversation. Null on rows written before ADR-8. */
  voice_agent_id: string | null;
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
  /** The organisation's own business fields, kept apart from `extracted` so a
   *  field named `sentiment` cannot rewrite triage's own input. */
  collected: Record<string, unknown>;
  /** Required fields the call ended without. Empty means complete. */
  missing_required_fields: string[];
  /** What a person still has to ask, in the agent's own words. */
  handoff_questions: string[];
  /** Which of the organisation's lines placed the call, masked. */
  from_number_masked: string | null;
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
  /** The agent whose call this was. Resolved server-side. */
  agent_name: string | null;
  escalation_status: 'open' | 'resolved';
  assigned_to: string | null;
  assigned_to_name: string | null;
  assigned_by: string | null;
  assigned_by_name: string | null;
  resolved_by: string | null;
  resolved_by_name: string | null;
  resolved_at: string | null;
}

export type ShareResourceType = 'escalation';
export type ShareRequestStatus = 'pending' | 'approved' | 'rejected';

/** Contact + agent + current owner for an *open* escalation - never the
 *  transcript, sentiment, or disposition detail. */
export interface EscalationDirectoryEntry {
  id: string;
  contact_name: string;
  agent_name: string | null;
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

/**
 * What starting a run needs.
 *
 * The number lives here rather than on the agent (ADR-8), which is what lets one
 * agent dial through any carrier the organisation has connected.
 */
/** One row of an uploaded spreadsheet, as the server read it. */
export interface SheetRow {
  row: number;
  name: string;
  /** Masked. The full number travels only inside `contact`. */
  phone_masked: string;
  note: string;
  context: Record<string, string>;
  valid: boolean;
  error: string | null;
  /** Ready to post straight back in `contacts`, or null when the row cannot be
   *  dialled. Built server-side so the context rules live in one place. */
  contact: ContactInput | null;
}

export interface ParsedSheet {
  rows: SheetRow[];
  /** Context columns found across the sheet - what each contact brings into
   *  its own conversation. */
  context_columns: string[];
}

export interface StartRunBody {
  voice_agent_id: string;
  /** One, several, or every verified number. A run with none is refused. */
  number_ids: string[];
  contacts: ContactInput[];
  name?: string | null;
  /** Appended to every prompt in this run, so a one-off instruction does not
   *  mean editing an agent the whole organisation shares. */
  run_instruction?: string | null;
  allocation_strategy?: 'round_robin' | 'area_affinity';
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
  voice_agent_id: string | null;
  /** Resolved server-side: the client holds no agent list to look it up in. */
  agent_name: string | null;
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
  voice_agent_id: string | null;
  agent_name: string | null;
  name: string | null;
  total: number;
  status: 'running' | 'completed' | 'failed';
  started_at: string;
  finished_at: string | null;
  error: string | null;
  completed: number;
  /** Who started the run. Returned by the list endpoint; null on rows
   *  written before attribution existed. */
  started_by: string | null;
  started_by_name: string | null;
  started_by_avatar_url: string | null;
}

/** The deployment's own defaults - `/api/health` is unauthenticated, so this is
 * never any one organisation's live usage. */
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
  /** Today's credit ceiling for this member, in credits. 0 means unset. */
  daily_allocation: number;
  credits_used_today: number;
}

export interface InvitationPreview {
  valid: boolean;
  reason: string | null;
  org_name: string | null;
  role: string | null;
  email: string | null;
  /** The invited address already has a CallFlow account, so this person needs
   *  to sign in rather than create one. */
  account_exists: boolean;
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
  /** When *you* pinned this conversation. Per-member: pinning it does not
   *  move it in anyone else's list. Null when not pinned. */
  pinned_at: string | null;
  /** Where *you* dragged it. Null means never placed by hand, which sorts
   *  by recency. */
  sort_order: number | null;
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
  /** Whether CallFlow can prove a credential for this vendor is real - whether
   * a probe is declared for it. Separate from `wired`, and a vendor can be
   * either, both, or neither: it decides whether Re-check is worth offering,
   * and why an unconfirmed key says "Can't be confirmed" rather than implying a
   * retry would help. */
  verifiable: boolean;
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
  /** Whether the vendor confirmed these credentials. `null` when the check
   *  could not be completed - no probe for this vendor, it was unreachable,
   *  or the key is scoped too narrowly to verify. */
  verified?: boolean | null;
  verification_note?: string | null;
  /** When the vendor last confirmed *these* credentials - the durable half of
   *  the same answer.
   *
   *  `verified` above describes only the request that returned it, so it is
   *  null on every read. This survives, which is what lets a card say
   *  "Connected" for a reason rather than falling back to `wired` - that being
   *  "does a call read this vendor", not "does this key work". `null` is the
   *  absence of a claim, never a failure. */
  verified_at?: string | null;
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
  /** What the agent has to come back with. Same shape as the run composer's
   *  `extra_fields` - both end up as structured call results. */
  collect_fields?: CollectField[];
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
   *  own field editor - both become structured call results. */
  collect_fields: CollectField[];
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

/**
 * The session is gone - the token expired, was revoked, or never existed.
 *
 * A named type rather than a message match: every screen that loads data has to
 * tell this apart from a genuine failure, and comparing strings would break the
 * moment the API rewords a message.
 */
export class SessionExpiredError extends Error {
  constructor() {
    super('Your session has ended. Sign in again to continue.');
    this.name = 'SessionExpiredError';
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        // A multipart upload must set its own Content-Type: the boundary is
        // generated per request, and naming the type here without one produces
        // a body the server cannot parse.
        ...(init?.body instanceof FormData
          ? {}
          : { 'Content-Type': 'application/json' }),
        ...init?.headers,
      },
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
    // 401 is not "something went wrong", it is "your session ended", and the
    // two need different endings: one is a toast, the other is a trip back to
    // the login page. Without this distinction an expired session surfaced as
    // whatever the calling screen says when it cannot load - the run detail
    // page reported the run missing, which sent people looking for a deleted
    // run that was sitting in the database the whole time (`ISSUES.md` #174).
    if (res.status === 401) {
      throw new SessionExpiredError();
    }
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
  startRun: (body: StartRunBody) =>
    authReq<{ run_id: string; total: number }>('/api/v1/runs', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  listRuns: () => authReq<RunSummary[]>('/api/v1/runs'),
  /** Read an .xlsx into contact rows. Nothing is dialled or stored - the rows
   *  come back for review, exactly as a pasted CSV is reviewed. */
  parseSheet: (file: File) => {
    const body = new FormData();
    body.append('file', file);
    return authReq<ParsedSheet>('/api/v1/runs/parse-sheet', {
      method: 'POST',
      body,
    });
  },
  getRun: (id: string) => authReq<Run>(`/api/v1/runs/${id}`),
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

  // --- team performance - authenticated ------------------------------------
  teamPerformance: () =>
    authReq<TeamPerformance[]>('/api/v1/organisations/me/team-performance'),

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
  /** Ask the vendor again about a credential already on file.
   *
   *  The one case connect-time checking cannot reach: a key revoked or rotated
   *  at the vendor's end, or one saved while they were unreachable. Throws with
   *  the vendor's own refusal when it no longer works, and clears
   *  `verified_at` either way rather than deleting the credential. */
  verifyProvider: (provider: Provider) =>
    authReq<ProviderCredential>(
      `/api/v1/integrations/providers/${provider}/verify`,
      { method: 'POST' },
    ),

  // --- voice agents + ai providers (Agentic tab) ----------------------------
  // --- the numbers an organisation owns -------------------------------------
  listNumbers: (provider?: string) =>
    authReq<TelephonyNumber[]>(
      `/api/v1/telephony/numbers${provider ? `?provider=${provider}` : ''}`,
    ),
  /** Ask the carrier what the account actually holds. Idempotent. */
  syncNumbers: (provider: string) =>
    authReq<TelephonyNumber[]>(
      `/api/v1/telephony/numbers/sync?provider=${provider}`,
      { method: 'POST' },
    ),
  /**
   * Point a number at LiveKit so a run can dial from it.
   *
   * This is the step between "the carrier says we own this number" and "a run
   * may dial from it": it creates the LiveKit trunks and the dispatch rule,
   * configures the carrier, and marks the number verified. Without it a synced
   * number stays `discovered` and every run composer reports no line to dial
   * from, however many carriers are connected.
   *
   * `idempotencyKey` is the retry token: reusing it *resumes* the attempt
   * instead of starting a second one, which is what stops a double-click from
   * creating a second pair of LiveKit trunks that nobody ever cleans up.
   */
  connectNumber: (
    voiceAgentId: string,
    body: {
      provider: string;
      /** The synced number to connect. Numbers are masked everywhere they are
       *  shown, so the id is the only handle the client has - the server
       *  resolves it to the real E.164. */
      number_id: string;
      idempotency_key: string;
    },
  ) =>
    authReq<NumberProvisioning>(
      `/api/v1/voice-agents/${voiceAgentId}/connect-number`,
      { method: 'POST', body: JSON.stringify(body) },
    ),
  numberProvisioningStatus: (voiceAgentId: string) =>
    authReq<NumberProvisioning>(
      `/api/v1/voice-agents/${voiceAgentId}/connect-number`,
    ),
  setNumberStatus: (numberId: string, status: 'verified' | 'disabled') =>
    authReq<TelephonyNumber>(`/api/v1/telephony/numbers/${numberId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),

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
  pinChannel: (channelId: string, pinned: boolean) =>
    authReq<void>(`/api/v1/channels/${channelId}/pin`, {
      method: 'PATCH',
      body: JSON.stringify({ pinned }),
    }),
  reorderChannel: (channelId: string, sortOrder: number) =>
    authReq<void>(`/api/v1/channels/${channelId}/order`, {
      method: 'PATCH',
      body: JSON.stringify({ sort_order: sortOrder }),
    }),
  deleteChannel: (channelId: string) =>
    authReq<void>(`/api/v1/channels/${channelId}`, { method: 'DELETE' }),
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
