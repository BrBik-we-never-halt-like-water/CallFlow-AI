# CALL-E — what it actually is and what it actually provides

Researched from the public docs (2026-08-07): [heycall-e.com](https://www.heycall-e.com/),
[docs.heycall-e.com](https://docs.heycall-e.com/), and the published
[OpenAPI spec](https://docs.heycall-e.com/openapi/calle.openapi.yaml). This is the vendor
CallFlow AI currently integrates through `apps/api/app/integrations/voice/engine.py`
(`calle-ai` package, aliased on import per CLAUDE.md's dependency-inversion rule).

**Everything below is what CALL-E's API contract actually says — not aspirational, not
inferred.** Where something isn't documented publicly, it's marked as such rather than guessed.

---

## 1. What it is

A developer-first API for making an AI agent place a real phone call and get a real-world
task done — not a scripted IVR/voice-bot builder. You describe the task in natural language;
CALL-E handles the conversation, tone, interruptions, and changing call conditions in real
time, then hands back a structured result.

**It is a fully-managed calling service.** Nothing in the public API surface lets you attach
your own Twilio/Plivo number or telephony trunk — CALL-E owns the dial, the number, and the
model. This matters architecturally: CALL-E is one calling *provider*, not infrastructure you
plug your own numbers into. A "use your own Twilio/Plivo number" feature is necessarily a
**separate, parallel voice provider**, not a mode of CALL-E.

## 2. Pricing (as published, early-stage — CALL-E states this isn't final)

- 200 free calls on signup.
- $0.05 per billable call afterward, flat rate.
- No published volume tiers, no published concept of a subscription plan.

## 3. Endpoints (from the OpenAPI spec)

### Calls — the primitive this codebase already uses
| Endpoint | Purpose |
|---|---|
| `POST /v1/calls` | Create an async call task |
| `GET /v1/calls/{call_id}` | Poll call state |
| `GET /v1/calls/{call_id}/events` | List developer-facing call events (cursor-paginated) |

**Create-call request:**

| Field | Type | Notes |
|---|---|---|
| `task` | string | Required — natural-language instruction |
| `recipients` | array | `{ phones: string[] (E.164), locale?: string (BCP 47), region?: string }` |
| `result_schema` | object | JSON Schema for the task-level extraction |
| `recipient_result_schema` | object | JSON Schema for *per-recipient* extraction — **not currently used by this codebase**, worth adopting for multi-recipient runs |
| `metadata` | object | Caller-owned, echoed back untouched |
| `webhook_url` | string | Per-request HTTPS callback — **not currently used**; this codebase only polls |
| `Idempotency-Key` (header) | string | Optional, 1–255 chars |

Result schemas support `type`/`properties`/`required`/`enum`/nested `object`/flat
`array.items`/`description`/`additionalProperties: false`. They do **not** support `$ref`,
`oneOf`/`anyOf`/`allOf`, or recursion — worth validating client-side before submission rather
than finding out from a 400.

**Call task response** carries `id` (`call_` prefixed), `status`, `structured_result`,
`summary`, `task_completed` (boolean judgment), `completion_confidence` (`{score: 0–1, label}`),
`evidence[]`, `failure_code`/`failure_message`, `created_at`/`completed_at`, and a
`recipients[]` array — each recipient carries its own `status`, `structured_result`, `summary`,
and an `attempts[]` array. Each **attempt** (a single dial) carries `phone`, `status`,
`transcript_turns[]` (`{offset_seconds, speaker: bot|user|unknown, text}`), `provider_call_id`,
and failure detail.

**Statuses:**
- `CallStatus` (task-level): `queued`, `in_progress`, `completed`, `failed`, `canceled`
- `RecipientStatus`: `pending`, `in_progress`, `completed`, `failed`, `skipped`
- `AttemptStatus`: `queued`, `dialing`, `in_progress`, `completed`, `failed`, `canceled`

Note the richer shape here than what this codebase currently models: `entities.py`'s
`CallOutcome` is flat (one outcome per contact), while CALL-E's actual shape is
task → recipients → attempts (a recipient can be redialled). Multi-attempt retry history
is available from CALL-E today and currently **discarded** — only the latest attempt's
fields make it into `CallOutcome`.

### Goals — not integrated in this codebase at all today
| Endpoint | Purpose |
|---|---|
| `GET /v1/goals` | List the caller's published Goals |
| `GET /v1/goals/{goal_id}` | Get a Goal + its published RunSpec (`input_schema`, `result_schema`) |
| `POST /v1/goals/{goal_id}/runs` | Create a Goal Run — single call against a pre-published task template |
| `GET /v1/goals/{goal_id}/runs/{goal_run_id}` | Poll a Goal Run |

A **Goal** is a pre-published, reusable task template with a declared `input_schema` (the
`variables` a caller must supply) and `result_schema` — i.e. CALL-E's own version of what this
codebase calls a "campaign," but managed and versioned on CALL-E's side rather than ours.
Creating a run **requires** an `Idempotency-Key` (unlike plain calls, where it's optional) and
takes `phone` + `variables` rather than a free-text `task`. `GoalRunError.code` enumerates
`call_failed`, `no_answer`, `declined`, `timed_out`, `canceled`, `result_invalid`,
`result_unavailable`, `result_failed` — a real, documented failure taxonomy CallFlow AI's own
`Disposition` enum could align with rather than inventing its own on top.

**Not evaluated yet:** whether migrating campaigns to be backed by CALL-E Goals (instead of
locally-defined `task` strings) is worth it — Goals version on CALL-E's side, which could mean
losing local control over campaign history, or could mean CALL-E enforcing schema stability
CallFlow doesn't have to re-implement. Flagged for a follow-up decision.

### Webhooks
`POST /calle/webhook` — your server receives terminal call events (`call.completed`,
`call.failed`, `call.result_validation_failed`), each carrying a full terminal `CallTask`
snapshot in `data`. Requires a `CALL-E-Event-Id` header on receipt (for de-duplication).
**This codebase does not implement a webhook receiver today** — `_poll_until_done()` in
`engine.py` polls every 2s instead. Given CALL-E supports webhooks natively, polling is the
choice this codebase made, not a CALL-E limitation — worth revisiting once runs are
persisted (polling an in-memory dict across a whole pm2 process lifetime is fine; polling
against Postgres at scale is a straightforward reason to switch to the webhook).

## 4. Error taxonomy (from the spec — a real, exhaustive list)

`invalid_request`, `unauthorized`, `forbidden`, `rate_limit_exceeded`, `insufficient_balance`,
`unsupported_region`, `unsupported_language`, `recipient_blocked`, `policy_violation`,
`call_not_ready`, `no_recipients`, `invalid_recipient`, `invalid_phone`,
`result_schema_invalid`, `recipient_result_schema_invalid`, `idempotency_conflict`,
`goal_not_published`, `goal_not_executable`, `goal_not_ready`, `schema_override_not_allowed`,
`variables_invalid`, `provider_unavailable`, `internal_error`, `not_found`.

This is exactly the kind of taxonomy CLAUDE.md's Substitutability section (§3, L) asks for —
"normalise errors into an internal taxonomy... retry policy keys off the internal name, never
a vendor string." Today `engine.py` re-raises `CalleAPIError` mostly as-is; mapping this list
onto the internal taxonomy CLAUDE.md describes (`invalid_number`, `no_answer`, `busy`,
`voicemail`, `provider_unavailable`, …) is real, scoped work a second voice-provider adapter
(Twilio/Plivo) would force anyway.

## 5. Explicitly not found in public docs (don't build against these as if confirmed)

- **Recording**: no confirmed field or endpoint for retrieving a call audio recording.
- **Custom/cloned voices**: no mention of selectable or clonable TTS voices.
- **Bring-your-own number / SIP trunk**: no mention anywhere in the public surface.
- **Rate limits**: no published numbers (requests/sec, concurrent calls).
- **Regions/languages supported**: no enumerated list found; `region`/`locale` are accepted
  as free-form BCP 47 / country-code strings, validated server-side (hence
  `unsupported_region`/`unsupported_language` error codes existing).

If any of these turn out to matter for a feature decision, they need a direct question to
CALL-E (`support@heycall-e.com`) or a dashboard/account-level check — not an assumption.

---

**Bottom line for CallFlow AI's architecture:** CALL-E is a great *voice-provider adapter*
candidate exactly as `engine.py` already treats it, but it is not — and cannot become — the
substrate for a "bring your own Twilio/Plivo number" feature. That feature needs its own,
separate adapter(s) behind the same `VoiceProvider` boundary FEATURES.md's F17 already calls
for. See the architecture doc for how the two coexist.
