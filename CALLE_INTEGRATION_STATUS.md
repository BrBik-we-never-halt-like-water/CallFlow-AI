# CALL-E integration status - offering vs. usage vs. defects

Written 2026-08-08. Builds on `CALLE.md` (this session's prior research pass into the
vendor's public docs and OpenAPI spec) by adding one more source that pass didn't have:
the **actual installed SDK**, `calle-ai==0.6.0`
(`C:\Users\ARBAAZ\AppData\Roaming\Python\Python313\site-packages\calle`), pinned in
`apps/api/pyproject.toml`. Reading its source - `calls.py`, `goals.py`, `errors.py`,
`webhooks.py`, and the generated `attrs` models - gives ground truth that doesn't depend
on the docs site staying in sync with what's actually shipped, and let every claim below
be checked against real code rather than prose in three independent places where
possible: the public OpenAPI spec (re-fetched this pass), the SDK source, and
`apps/api/app/integrations/voice/engine.py` itself.

**Cross-check result: `CALLE.md` holds up.** Every endpoint, field, status enum, and all
23 error codes it documents match the SDK's generated models exactly (`CallStatus`,
`AttemptStatus`, `RecipientStatus`, `TranscriptSpeaker`, `APIErrorCode`,
`GoalRunErrorCode` - all read verbatim from
`calle/generated/models/*.py`). Nothing in it needed correcting. A handful of details
neither the public docs nor `CALLE.md` surfaced are folded into §1 below.

**Update, 2026-08-09 (iterations 14-20): every gap and defect this doc originally tracked
as open is now fixed** - see `ISSUES.md` #55-#63 for the seven-module rebuild that closed
them, and each item's own entry below for exactly what changed. The one deliberate
exception is §2 item 1 (Goals API adoption), flagged from the start as its own
architectural decision rather than integration polish, and intentionally not revisited
here. Kept as a historical record rather than rewritten, per this repo's "nothing is
deleted, only re-statused" convention.

---

## 1. What CALL-E offers (the vendor's actual service surface)

**The service.** A fully-managed, natural-language outbound calling API: you send a task
description and (usually) a phone number, CALL-E's agent places the call, holds the
conversation, and hands back a structured result plus a judgment on whether the task was
actually accomplished. No bring-your-own-number/SIP surface exists anywhere in the API -
confirmed again this pass, nothing changed.

**Calls** (`POST /v1/calls`, `GET /v1/calls/{id}`, `GET /v1/calls/{id}/events`) - the
primitive this codebase uses:

- Request: `task` (free text, required), `recipients[]` (optional - the SDK's own
  `CreateCallRequest.recipients` docstring says to _omit_ it "when the task text already
  contains the phone targets CALL-E should use," i.e. phone numbers can be embedded in
  the prose instead of passed structurally), `result_schema`, `recipient_result_schema`,
  `metadata` (fully free-form - the generated `CreateCallRequestMetadata` model is just an
  open `additionalProperties` bag, no required shape), `webhook_url`, optional
  `Idempotency-Key`.
- Each `recipient` carries `phones: string[]` (plural - a recipient can list more than one
  number to try), `locale`, `region`.
- Response is a `CallTask`: task-level `structured_result`, `summary`, `task_completed`
  (bool), `completion_confidence` (`{score: 0-1, label}`), `evidence[]`,
  `failure_code`/`failure_message`, and `recipients[]` - each with its own `status`,
  `structured_result` (only populated if `recipient_result_schema` was supplied),
  `summary`, and `attempts[]`. Each **attempt** (`CallTaskAttempt` in the SDK) carries
  `phone`, `status`, `started_at`/`completed_at`, `summary`, `transcript_turns[]`
  (`{offset_seconds, speaker: bot|user|unknown, text}`), `provider_call_id` (CALL-E's
  _own_ upstream carrier's correlation id, for support escalations to CALL-E - not
  something a CallFlow customer would need), and failure detail.
- `result_schema`/`recipient_result_schema` support `type`/`properties`/`required`/
  `enum`/nested `object`/flat `array.items`/`description`/`additionalProperties: false`
  only - no `$ref`, `oneOf`/`anyOf`/`allOf`, recursion. `recipient_result_schema` also
  reserves `summary`, `status`, `transcript`, `call_id`, and timing field names - a
  custom schema can't reuse those.
- Statuses (all confirmed against the SDK's generated `Literal` types, not just docs):
  `CallStatus` = `queued, in_progress, completed, failed, canceled`; `AttemptStatus`
  adds `dialing`; `RecipientStatus` = `pending, in_progress, completed, failed, skipped`.

**Goals** (`GET /v1/goals`, `GET /v1/goals/{id}`, `POST /v1/goals/{id}/runs`,
`GET /v1/goals/{id}/runs/{run_id}`) - not touched by this codebase at all. A Goal is a
published, versioned task template (`input_schema` + `result_schema`) managed on CALL-E's
side. Creating a run takes `phone` + `variables` (flat scalars only - the SDK's
`GoalVariables` type is `dict[str, str | int | float | bool]`, no nested objects/arrays)
and, unlike plain calls, **requires** an `Idempotency-Key`. `GoalRunError.code` is a
separate, smaller taxonomy: `call_failed, no_answer, declined, timed_out, canceled,
result_invalid, result_unavailable, result_failed`.

**Webhooks.** Two delivery paths exist, not one: a per-request `webhook_url` on
`POST /v1/calls`, **and** - per the SDK's own docstring on that field - "project-level
webhook delivery" configured outside the API entirely (presumably a CALL-E dashboard
setting), which fires independently of anything a call-request specifies. Events:
`call.completed`, `call.failed`, `call.result_validation_failed`, each carrying a full
terminal `CallTask` snapshot. Worth knowing if this is ever adopted: `calle.webhooks`'s
`verify()`/`unwrap()` HMAC-signature helpers are explicitly marked deprecated in the
SDK's own docstrings - _"CALL-E no longer sends timestamp or signature headers... current
CALL-E webhooks are unsigned... must not be used to parse current deliveries."_ A future
receiver can't authenticate inbound webhooks by signature; it would need a different
trust mechanism (shared-secret path segment, IP allowlist, mTLS, etc.).

**Error taxonomy.** 23 codes, all reachable from `/v1/calls` or `/v1/goals` endpoints -
listed in full in `CALLE.md` §4 and confirmed verbatim against
`calle/generated/models/api_error_code.py`.

**Pricing/limits (unchanged from `CALLE.md`):** 200 free calls, $0.05/call flat
thereafter, both stated as early-stage/non-final. No cost or billing field appears
anywhere in the `CallTask`/`CallTaskAttempt` response shape - confirmed absent from the
SDK's models, not just undocumented, so "no billable flag... recorded" (already noted in
`SYSTEM.md`'s F20 gap row) is a real absence on CALL-E's side, not a CallFlow omission.
No rate-limit numbers, no enumerated region/language list, no recording, no custom/cloned
voices, no SIP/BYO-number - all still genuinely absent from every source checked
(spec, docs, SDK).

---

## 2. Integration gaps - what CALL-E offers that this codebase does not use yet

1. **Goals API - entirely unintegrated.** CallFlow's own "campaign" concept
   (`app/domain/campaigns.py`, a free-text `goal_template`) duplicates what a CALL-E Goal
   already is, but versioned on CALL-E's side instead of CallFlow's. Adopting it would be
   a real architectural decision (own the campaign definition vs. delegate it to the
   vendor), not a small addition - already flagged as an open question in `CALLE.md` §3,
   not re-litigated here.

2. **`task_completed` / `completion_confidence` / `evidence[]` - computed by CALL-E,
   discarded by CallFlow.**

   **FIXED - iteration 19, `ISSUES.md` #62 (module 6 of the CALL-E integration
   rebuild).** Re-confirmed against the *live* OpenAPI spec before building against it
   (task-level only, never per-recipient - this doc's original wording was accurate).
   All three now live on `CallOutcome`; `triage()` escalates on an explicit
   `task_completed: False`, ranked below the explicit human-said-so signals
   (do_not_call/wants_human/frustration) and above the plain status-based buckets.
   `completion_confidence`/`evidence` are threaded through and persisted but
   deliberately not weighted in `triage()` - a softer, fuzzier signal than a boolean
   judgment, left as data rather than another precedence branch.

3. **Multi-recipient / multi-number-per-recipient batching.** CALL-E's `recipients[]`
   accepts many recipients per call, and each recipient's `phones[]` can list several
   numbers to try. `CampaignRunner` dials exactly one contact, one number, per call - a
   deliberate and reasonable fit for CallFlow's per-contact-row product model, not
   obviously worth changing - **this part stays as-is.**

   The retry-history half is **FIXED - iteration 19, `ISSUES.md` #62**: CALL-E's full
   `attempts[]` history is now preserved on `CallOutcome.attempts` instead of discarding
   every attempt but the one `_final_attempt()` picks for the transcript.

4. **Live per-call events (`GET /v1/calls/{id}/events`).**

   **FIXED (backend) - iteration 20, `ISSUES.md` #63 (module 7 of the CALL-E integration
   rebuild).** `GET /api/v1/runs/{run_id}/calls/{provider_call_id}/events` now proxies
   `EngineGateway.list_events()` on demand. One correction to this section's original
   framing: the endpoint's actual shape turned out to be a **developer/ops event log**
   (`debug`/`info`/`warning`/`error` levels, a human-readable `message`, the `status` at
   that moment) - not a turn-by-turn *conversation* stream the way "live progress" implied
   when this doc was first written. Still a real improvement over status-only polling: every
   transition gets its own timestamp (a fast run of states between two 2-second polls is
   otherwise invisible), plus warning/error diagnostics polling has no way to surface at all.
   **Frontend consumption (an actual dashboard control to view this) is intentionally not
   part of this fix** - flagged to the user as a separate, explicit follow-up rather than
   scope creep into UI work this backend-only rebuild didn't set out to do.

5. **Idempotency-Key as duplicate-request protection.** The header is sent
   (`campaign_runner.py:249`), but see §3.5 - the way the key is generated means it
   doesn't actually deliver the guarantee `Idempotency-Key` exists for.

---

## 3. Issues with what IS integrated

Ranked by how much it should worry someone, using this repo's `ISSUES.md` severity scale
(S1 breaks a guarantee/loses data, S2 a feature is broken or misleading in normal use, S3
wrong in an edge case, S4 cosmetic).

**Status as of iteration 16 (2026-08-09):** items 1–3 were fixed in iteration 13
(`ISSUES.md` #52/#53) shortly after this doc was first written; items 4/6/7 were fixed in
iteration 14 (`ISSUES.md` #55/#56/#57, module 1 of the CALL-E integration rebuild); item 5
was fixed in iteration 16 (`ISSUES.md` #59, module 3). All seven items in this section are
now fixed - the original write-up for each is kept below anyway, per this repo's
"nothing is deleted, only re-statused" convention (`ISSUES.md`'s own header).

### 1. Transcripts are very likely never actually captured - S2, highest priority

**FIXED - iteration 13, `ISSUES.md` #52.**

`campaign_runner._extract_transcript()` (lines 97–110) looks for a **top-level**
`transcript` / `transcript_text` / `asr_transcript` key on the call payload. No source
checked this session - not `CALLE.md`, not the freshly-refetched OpenAPI spec, not the
SDK's generated models - has a transcript field at the top level of a `CallTask`.
Every one of them agrees the real location is nested two levels down:
`recipients[N].attempts[M].transcript_turns[]`. The SDK's `get()`/`wait_for_result()`
(`calle/calls.py`) do zero reshaping - they return `response.json()` verbatim - so
`engine.py`'s `get_call()` hands `campaign_runner` exactly the raw, nested shape, and
`_extract_transcript` is checking keys that don't exist in it.

The function's own comment - _"The API has returned this under a few different keys
across versions, so we check the known candidates rather than assuming one shape"_ -
reads like a guess rather than a confirmed fact, and `apps/api/tests/test_orchestrator.py`
never imports or exercises `_extract_transcript` at all (only `_extract_result` has
tests, at lines 219–229, and its recipients-branch fallback happens to include the real
`structured_result` key, which is why that one likely works). The practical effect: this
almost certainly means `CallOutcome.transcript` is `None` for every real call, and
`apps/web/components/app/transcript-view.tsx` - which renders "No transcript was
recorded for this call." whenever `outcome.transcript` is falsy (line 120) - would show
that message for every completed call regardless of what was actually said. Not
independently confirmed against a live CALL-E call in this pass (no API access here),
but every documented source agrees on the nested shape, and none support the flat one
the code checks.

### 2. One flaky status poll can orphan an otherwise-successful call - S2

**FIXED - iteration 13, `ISSUES.md` #53.**

`CampaignRunner._poll_until_done()` (lines 158–198) has no `try`/`except` around the
per-iteration `await asyncio.to_thread(self.gateway.get_call, call_id)` inside its `while`
loop. `poll_timeout_seconds` defaults to 900s at a 2s interval - up to ~450 HTTP requests
per call. Any single one of them raising - a transient `internal_error`/
`provider_unavailable` from `GET /v1/calls/{id}`, a dropped connection, a timeout -
propagates straight out of `_poll_until_done` into `run_one`'s outer `try` (lines
241–323) and marks the _entire call_ `FAILED`, with a disposition of `RETRY` or
`UNREACHABLE` depending on classification. But failing to fetch a status update doesn't
stop the actual phone call at CALL-E - the conversation may complete successfully
moments later, with a perfectly good structured result sitting there that CallFlow never
comes back to collect, because it already gave up watching. Given CALL-E is explicitly
described as early-stage (`CALLE.md` §2), and this loop makes on the order of hundreds of
requests per call, a single hiccup mid-poll isn't a remote edge case. Worth prompt
attention: this can misreport a call a person actually answered and completed as
unreachable/failed.

### 3. `CalleConnectionError` is a distinct exception the classifier never sees - S3

**FIXED - iteration 13, folded into the `ISSUES.md` #53 fix.**

The SDK raises three different things on request failure: `CalleAPIError` (has `.code`,
what `classify_error()` maps), `CalleTimeoutError` (also handled), and
**`CalleConnectionError`** - raised in both `calle/calls.py` and `calle/goals.py` when
`httpx.HTTPError` occurs before a response is received (DNS failure, connection refused,
TLS error). `engine.py` imports only `CalleAPIError` and `CalleTimeoutError`
(lines 24–25); `CalleConnectionError` is never imported or caught anywhere in
`campaign_runner.py`, so it falls into the generic `except Exception` (line 309) and is
stored as `DialFailure.INTERNAL` / `Disposition.UNREACHABLE` - the _non-retryable_
bucket - via the exact code path issue #37 added specifically to distinguish transient
from permanent failures. A network blip reaching CALL-E's API is about as transient as
`provider_unavailable` (which _is_ mapped and _is_ retryable); today it's classified the
opposite way.

### 4. Some real, reachable error codes still fall through to an unhelpful message - S3

**FIXED - iteration 14, `ISSUES.md` #55.** (The schema-related codes are mapped to
`INTERNAL` explicitly now, same runtime behaviour as before - the up-front,
before-any-dial `result_schema` validation this write-up suggests turned out to have no
current caller: `build_result_schema()` only ever composes a flat `type: object` schema
from campaign fields, which can't produce a `$ref`/`oneOf`/recursive shape today, so that
part of the idea was left undone rather than built speculatively.)

`engine.py`'s `_ERROR_CODE_MAP` (lines 44–57) maps 12 of the 23 documented codes. The
unmapped ones that are actually reachable from `/v1/calls` (as opposed to the
Goals-only codes, which are correctly irrelevant since Goals aren't used) include
`result_schema_invalid`, `recipient_result_schema_invalid`, `invalid_request`,
`call_not_ready`, `idempotency_conflict`, and `not_found`. These fail closed to
`DialFailure.INTERNAL` per the fail-closed design (correct and intentional per the
code's own comment, lines 39–43) - but the resulting operator-facing message,
_"Call could not be completed: internal,"_ misrepresents what actually happened for the
schema-related ones: a campaign's `result_schema` using an unsupported JSON Schema
feature (`$ref`, `oneOf`, etc. - genuinely unsupported per §1) is a fixable
_configuration_ problem, not an infrastructure fault, and would fail identically for
every contact in the run rather than failing the run once, up front, with an actionable
message.

### 5. The idempotency key is regenerated per attempt, defeating its own purpose - S3

**FIXED - iteration 16, `ISSUES.md` #59.** The key is now `f"{run_id}:{phone_hash(phone)}"`
- stable per (run, contact), distinct across runs. Closes the idempotency half of `#54`;
the `_calls_made`-increment-timing half was closed in iteration 17, module 4 (`ISSUES.md`
#60), which also replaced the strictly-sequential dialing loop with bounded concurrency -
see that entry, not duplicated here since it's an orchestration-level change rather than a
CALL-E protocol-usage gap (this doc's own scope).

`campaign_runner.py:249` builds the key as
`f"{campaign.id}-{contact.phone}-{uuid.uuid4().hex[:8]}"` - a fresh random suffix on
every single `start_call` invocation. `Idempotency-Key` exists to protect exactly one
scenario: the create-call request reaches CALL-E and a call gets placed, but the success
response is lost in transit (timeout, connection drop) before CallFlow sees it. A retry
with the _same_ key would let CALL-E recognize the duplicate and return the existing
call instead of dialing again; a retry with a new random key - which is what happens
today, on every attempt - cannot be recognized as a duplicate at all. Given CLAUDE.md's
non-negotiable #8 (every run dials for real, no dry-run gate) and #6 (idempotency), this
is a real, if narrow, path to a genuine second phone call to the same person on retry -
worth deciding deliberately rather than leaving as an accident of the current key format.

### 6. Minor: a vendor-named key leaks above the integration boundary - S4

**FIXED - iteration 14, `ISSUES.md` #56.** Removed rather than moved - nothing required it.

`campaign_runner.py:233` (in `services/`, above `integrations/voice/`) builds
`metadata = {"call-e/customerMetadata": {...}}` - embedding a literal `"call-e/"`-prefixed
key outside `engine.py`. `metadata` is fully free-form on CALL-E's side (confirmed - the
generated `CreateCallRequestMetadata` model is just an open dict, no required shape or
namespacing), so this isn't wrong, just a small, easy-to-fix breach of CLAUDE.md's
dependency-inversion rule that no file above `engine.py` should speak the vendor's name.

### 7. Minor: `list_events()` drops cursor pagination - S4

**FIXED - iteration 14, `ISSUES.md` #57.**

`EngineGateway.list_events()` (`engine.py:154-156`) only forwards `limit` to the SDK,
never `cursor`, even though `CalleCalls.list_events()` accepts one and the endpoint is
documented as cursor-paginated. Moot today since nothing calls this method (§2.4), but
worth fixing before anything does - otherwise only the first page of a long call's
events would ever be reachable through this gateway.
