# CALL-E integration status — offering vs. usage vs. defects

Written 2026-08-08. Builds on `CALLE.md` (this session's prior research pass into the
vendor's public docs and OpenAPI spec) by adding one more source that pass didn't have:
the **actual installed SDK**, `calle-ai==0.6.0`
(`C:\Users\ARBAAZ\AppData\Roaming\Python\Python313\site-packages\calle`), pinned in
`apps/api/pyproject.toml`. Reading its source — `calls.py`, `goals.py`, `errors.py`,
`webhooks.py`, and the generated `attrs` models — gives ground truth that doesn't depend
on the docs site staying in sync with what's actually shipped, and let every claim below
be checked against real code rather than prose in three independent places where
possible: the public OpenAPI spec (re-fetched this pass), the SDK source, and
`apps/api/app/integrations/voice/engine.py` itself.

**Cross-check result: `CALLE.md` holds up.** Every endpoint, field, status enum, and all
23 error codes it documents match the SDK's generated models exactly (`CallStatus`,
`AttemptStatus`, `RecipientStatus`, `TranscriptSpeaker`, `APIErrorCode`,
`GoalRunErrorCode` — all read verbatim from
`calle/generated/models/*.py`). Nothing in it needed correcting. A handful of details
neither the public docs nor `CALLE.md` surfaced are folded into §1 below.

---

## 1. What CALL-E offers (the vendor's actual service surface)

**The service.** A fully-managed, natural-language outbound calling API: you send a task
description and (usually) a phone number, CALL-E's agent places the call, holds the
conversation, and hands back a structured result plus a judgment on whether the task was
actually accomplished. No bring-your-own-number/SIP surface exists anywhere in the API —
confirmed again this pass, nothing changed.

**Calls** (`POST /v1/calls`, `GET /v1/calls/{id}`, `GET /v1/calls/{id}/events`) — the
primitive this codebase uses:
- Request: `task` (free text, required), `recipients[]` (optional — the SDK's own
  `CreateCallRequest.recipients` docstring says to *omit* it "when the task text already
  contains the phone targets CALL-E should use," i.e. phone numbers can be embedded in
  the prose instead of passed structurally), `result_schema`, `recipient_result_schema`,
  `metadata` (fully free-form — the generated `CreateCallRequestMetadata` model is just an
  open `additionalProperties` bag, no required shape), `webhook_url`, optional
  `Idempotency-Key`.
- Each `recipient` carries `phones: string[]` (plural — a recipient can list more than one
  number to try), `locale`, `region`.
- Response is a `CallTask`: task-level `structured_result`, `summary`, `task_completed`
  (bool), `completion_confidence` (`{score: 0-1, label}`), `evidence[]`,
  `failure_code`/`failure_message`, and `recipients[]` — each with its own `status`,
  `structured_result` (only populated if `recipient_result_schema` was supplied),
  `summary`, and `attempts[]`. Each **attempt** (`CallTaskAttempt` in the SDK) carries
  `phone`, `status`, `started_at`/`completed_at`, `summary`, `transcript_turns[]`
  (`{offset_seconds, speaker: bot|user|unknown, text}`), `provider_call_id` (CALL-E's
  *own* upstream carrier's correlation id, for support escalations to CALL-E — not
  something a CallFlow customer would need), and failure detail.
- `result_schema`/`recipient_result_schema` support `type`/`properties`/`required`/
  `enum`/nested `object`/flat `array.items`/`description`/`additionalProperties: false`
  only — no `$ref`, `oneOf`/`anyOf`/`allOf`, recursion. `recipient_result_schema` also
  reserves `summary`, `status`, `transcript`, `call_id`, and timing field names — a
  custom schema can't reuse those.
- Statuses (all confirmed against the SDK's generated `Literal` types, not just docs):
  `CallStatus` = `queued, in_progress, completed, failed, canceled`; `AttemptStatus`
  adds `dialing`; `RecipientStatus` = `pending, in_progress, completed, failed, skipped`.

**Goals** (`GET /v1/goals`, `GET /v1/goals/{id}`, `POST /v1/goals/{id}/runs`,
`GET /v1/goals/{id}/runs/{run_id}`) — not touched by this codebase at all. A Goal is a
published, versioned task template (`input_schema` + `result_schema`) managed on CALL-E's
side. Creating a run takes `phone` + `variables` (flat scalars only — the SDK's
`GoalVariables` type is `dict[str, str | int | float | bool]`, no nested objects/arrays)
and, unlike plain calls, **requires** an `Idempotency-Key`. `GoalRunError.code` is a
separate, smaller taxonomy: `call_failed, no_answer, declined, timed_out, canceled,
result_invalid, result_unavailable, result_failed`.

**Webhooks.** Two delivery paths exist, not one: a per-request `webhook_url` on
`POST /v1/calls`, **and** — per the SDK's own docstring on that field — "project-level
webhook delivery" configured outside the API entirely (presumably a CALL-E dashboard
setting), which fires independently of anything a call-request specifies. Events:
`call.completed`, `call.failed`, `call.result_validation_failed`, each carrying a full
terminal `CallTask` snapshot. Worth knowing if this is ever adopted: `calle.webhooks`'s
`verify()`/`unwrap()` HMAC-signature helpers are explicitly marked deprecated in the
SDK's own docstrings — *"CALL-E no longer sends timestamp or signature headers... current
CALL-E webhooks are unsigned... must not be used to parse current deliveries."* A future
receiver can't authenticate inbound webhooks by signature; it would need a different
trust mechanism (shared-secret path segment, IP allowlist, mTLS, etc.).

**Error taxonomy.** 23 codes, all reachable from `/v1/calls` or `/v1/goals` endpoints —
listed in full in `CALLE.md` §4 and confirmed verbatim against
`calle/generated/models/api_error_code.py`.

**Pricing/limits (unchanged from `CALLE.md`):** 200 free calls, $0.05/call flat
thereafter, both stated as early-stage/non-final. No cost or billing field appears
anywhere in the `CallTask`/`CallTaskAttempt` response shape — confirmed absent from the
SDK's models, not just undocumented, so "no billable flag... recorded" (already noted in
`SYSTEM.md`'s F20 gap row) is a real absence on CALL-E's side, not a CallFlow omission.
No rate-limit numbers, no enumerated region/language list, no recording, no custom/cloned
voices, no SIP/BYO-number — all still genuinely absent from every source checked
(spec, docs, SDK).

---

## 2. Integration gaps — what CALL-E offers that this codebase does not use yet

1. **Goals API — entirely unintegrated.** CallFlow's own "campaign" concept
   (`app/domain/campaigns.py`, a free-text `goal_template`) duplicates what a CALL-E Goal
   already is, but versioned on CALL-E's side instead of CallFlow's. Adopting it would be
   a real architectural decision (own the campaign definition vs. delegate it to the
   vendor), not a small addition — already flagged as an open question in `CALLE.md` §3,
   not re-litigated here.

2. **`task_completed` / `completion_confidence` / `evidence[]` — computed by CALL-E,
   discarded by CallFlow.** `app/domain/entities.py`'s `CallOutcome` has no field for any
   of the three, and `campaign_runner._extract_result()` only pulls `structured_result`.
   This is CALL-E's own judgment of whether the agent actually got the job done,
   independent of whatever custom `result_schema` a campaign defines — a low-confidence
   `completion_confidence` or `task_completed: false` on an otherwise "completed" call
   looks like exactly the kind of signal `triage.py` cares about (it currently infers
   everything from campaign-defined `extracted` fields like `sentiment`/
   `wants_human_callback`, with no fallback if a campaign's schema doesn't ask for them).
   Moderate work: thread three more fields through `_extract_result`/`CallOutcome`, then
   decide whether `triage()` should weight them — no structural change.

3. **Multi-recipient / multi-number-per-recipient batching.** CALL-E's `recipients[]`
   accepts many recipients per call, and each recipient's `phones[]` can list several
   numbers to try. `CampaignRunner` dials exactly one contact, one number, per call — a
   deliberate and reasonable fit for CallFlow's per-contact-row product model, not
   obviously worth changing. Flagging only because it's the reason CALL-E's richer
   task→recipient→attempt shape gets flattened to one `CallOutcome` per contact, and any
   retry history CALL-E already tracked in `attempts[]` is discarded (already noted in
   `CALLE.md`).

4. **Live per-call events (`GET /v1/calls/{id}/events`).** `EngineGateway.list_events()`
   exists and `VoiceCapability.LIVE_EVENTS` is declared `supported=True`
   (`engine.py:69-71`), but nothing in `campaign_runner.py` or any route calls it —
   dashboard progress comes entirely from polling `get_call()`'s coarse `status` field.
   A capability is declared and plumbed but has no consumer. Small addition if pursued
   (a route + frontend hook to stream turn-by-turn progress instead of status-only), but
   see §3.6 for a real defect in the method as it stands today.

5. **Idempotency-Key as duplicate-request protection.** The header is sent
   (`campaign_runner.py:249`), but see §3.5 — the way the key is generated means it
   doesn't actually deliver the guarantee `Idempotency-Key` exists for.

---

## 3. Issues with what IS integrated

Ranked by how much it should worry someone, using this repo's `ISSUES.md` severity scale
(S1 breaks a guarantee/loses data, S2 a feature is broken or misleading in normal use, S3
wrong in an edge case, S4 cosmetic). None of these duplicate an existing `ISSUES.md`
entry — #37 (voice-engine error normalization) is the only prior CALL-E-related entry,
and items 3–4 below are gaps *in* that fix's coverage, not restatements of it. Not fixed,
per the brief — flagged for someone to act on.

### 1. Transcripts are very likely never actually captured — S2, highest priority

`campaign_runner._extract_transcript()` (lines 97–110) looks for a **top-level**
`transcript` / `transcript_text` / `asr_transcript` key on the call payload. No source
checked this session — not `CALLE.md`, not the freshly-refetched OpenAPI spec, not the
SDK's generated models — has a transcript field at the top level of a `CallTask`.
Every one of them agrees the real location is nested two levels down:
`recipients[N].attempts[M].transcript_turns[]`. The SDK's `get()`/`wait_for_result()`
(`calle/calls.py`) do zero reshaping — they return `response.json()` verbatim — so
`engine.py`'s `get_call()` hands `campaign_runner` exactly the raw, nested shape, and
`_extract_transcript` is checking keys that don't exist in it.

The function's own comment — *"The API has returned this under a few different keys
across versions, so we check the known candidates rather than assuming one shape"* —
reads like a guess rather than a confirmed fact, and `apps/api/tests/test_orchestrator.py`
never imports or exercises `_extract_transcript` at all (only `_extract_result` has
tests, at lines 219–229, and its recipients-branch fallback happens to include the real
`structured_result` key, which is why that one likely works). The practical effect: this
almost certainly means `CallOutcome.transcript` is `None` for every real call, and
`apps/web/components/app/transcript-view.tsx` — which renders "No transcript was
recorded for this call." whenever `outcome.transcript` is falsy (line 120) — would show
that message for every completed call regardless of what was actually said. Not
independently confirmed against a live CALL-E call in this pass (no API access here),
but every documented source agrees on the nested shape, and none support the flat one
the code checks.

### 2. One flaky status poll can orphan an otherwise-successful call — S2

`CampaignRunner._poll_until_done()` (lines 158–198) has no `try`/`except` around the
per-iteration `await asyncio.to_thread(self.gateway.get_call, call_id)` inside its `while`
loop. `poll_timeout_seconds` defaults to 900s at a 2s interval — up to ~450 HTTP requests
per call. Any single one of them raising — a transient `internal_error`/
`provider_unavailable` from `GET /v1/calls/{id}`, a dropped connection, a timeout —
propagates straight out of `_poll_until_done` into `run_one`'s outer `try` (lines
241–323) and marks the *entire call* `FAILED`, with a disposition of `RETRY` or
`UNREACHABLE` depending on classification. But failing to fetch a status update doesn't
stop the actual phone call at CALL-E — the conversation may complete successfully
moments later, with a perfectly good structured result sitting there that CallFlow never
comes back to collect, because it already gave up watching. Given CALL-E is explicitly
described as early-stage (`CALLE.md` §2), and this loop makes on the order of hundreds of
requests per call, a single hiccup mid-poll isn't a remote edge case. Worth prompt
attention: this can misreport a call a person actually answered and completed as
unreachable/failed.

### 3. `CalleConnectionError` is a distinct exception the classifier never sees — S3

The SDK raises three different things on request failure: `CalleAPIError` (has `.code`,
what `classify_error()` maps), `CalleTimeoutError` (also handled), and
**`CalleConnectionError`** — raised in both `calle/calls.py` and `calle/goals.py` when
`httpx.HTTPError` occurs before a response is received (DNS failure, connection refused,
TLS error). `engine.py` imports only `CalleAPIError` and `CalleTimeoutError`
(lines 24–25); `CalleConnectionError` is never imported or caught anywhere in
`campaign_runner.py`, so it falls into the generic `except Exception` (line 309) and is
stored as `DialFailure.INTERNAL` / `Disposition.UNREACHABLE` — the *non-retryable*
bucket — via the exact code path issue #37 added specifically to distinguish transient
from permanent failures. A network blip reaching CALL-E's API is about as transient as
`provider_unavailable` (which *is* mapped and *is* retryable); today it's classified the
opposite way.

### 4. Some real, reachable error codes still fall through to an unhelpful message — S3

`engine.py`'s `_ERROR_CODE_MAP` (lines 44–57) maps 12 of the 23 documented codes. The
unmapped ones that are actually reachable from `/v1/calls` (as opposed to the
Goals-only codes, which are correctly irrelevant since Goals aren't used) include
`result_schema_invalid`, `recipient_result_schema_invalid`, `invalid_request`,
`call_not_ready`, `idempotency_conflict`, and `not_found`. These fail closed to
`DialFailure.INTERNAL` per the fail-closed design (correct and intentional per the
code's own comment, lines 39–43) — but the resulting operator-facing message,
*"Call could not be completed: internal,"* misrepresents what actually happened for the
schema-related ones: a campaign's `result_schema` using an unsupported JSON Schema
feature (`$ref`, `oneOf`, etc. — genuinely unsupported per §1) is a fixable
*configuration* problem, not an infrastructure fault, and would fail identically for
every contact in the run rather than failing the run once, up front, with an actionable
message.

### 5. The idempotency key is regenerated per attempt, defeating its own purpose — S3

`campaign_runner.py:249` builds the key as
`f"{campaign.id}-{contact.phone}-{uuid.uuid4().hex[:8]}"` — a fresh random suffix on
every single `start_call` invocation. `Idempotency-Key` exists to protect exactly one
scenario: the create-call request reaches CALL-E and a call gets placed, but the success
response is lost in transit (timeout, connection drop) before CallFlow sees it. A retry
with the *same* key would let CALL-E recognize the duplicate and return the existing
call instead of dialing again; a retry with a new random key — which is what happens
today, on every attempt — cannot be recognized as a duplicate at all. Given CLAUDE.md's
non-negotiable #8 (every run dials for real, no dry-run gate) and #6 (idempotency), this
is a real, if narrow, path to a genuine second phone call to the same person on retry —
worth deciding deliberately rather than leaving as an accident of the current key format.

### 6. Minor: a vendor-named key leaks above the integration boundary — S4

`campaign_runner.py:233` (in `services/`, above `integrations/voice/`) builds
`metadata = {"call-e/customerMetadata": {...}}` — embedding a literal `"call-e/"`-prefixed
key outside `engine.py`. `metadata` is fully free-form on CALL-E's side (confirmed — the
generated `CreateCallRequestMetadata` model is just an open dict, no required shape or
namespacing), so this isn't wrong, just a small, easy-to-fix breach of CLAUDE.md's
dependency-inversion rule that no file above `engine.py` should speak the vendor's name.

### 7. Minor: `list_events()` drops cursor pagination — S4

`EngineGateway.list_events()` (`engine.py:154-156`) only forwards `limit` to the SDK,
never `cursor`, even though `CalleCalls.list_events()` accepts one and the endpoint is
documented as cursor-paginated. Moot today since nothing calls this method (§2.4), but
worth fixing before anything does — otherwise only the first page of a long call's
events would ever be reachable through this gateway.
