# RUNBOOK — Part 1: Voice Runtime, Telephony & CALL-E Removal

**Owner:** Het
**Source plan:** `PLATFORM_PIVOT_PLAN.md` — ADR-1, ADR-2, ADR-3, ADR-4 (schema + telephony half), ADR-7 (provisioning half), §9 (backend half), §11 (CALL-E removal), §12 Track A phases A0, A1 (telephony half), A2, A3.1/A3.2, A3.4
**Companion runbooks:** `RUNBOOK_ARBAAZ_PART_2.md` (voice-agent product surface, extraction/triage, Agentic UI), `RUNBOOK_JATIN_PART_3.md` (internal team chat)

---

## 0. Grounding — verified against the actual repo, not the plan's prose

Everything below was checked against the working tree on branch `jatin/config-resend` (identical to `origin/dev` and `origin/main` at the tables/routes level). Three things the plan states as background fact do **not** match this repo and you should not assume they do:

1. **No `apps/voice-runtime/` exists.** This is a greenfield deployable, not a refactor.
2. **No LiveKit, Twilio SDK, or Plivo SDK dependency exists anywhere** (`apps/api/pyproject.toml` has exactly 13 runtime deps, none of them telephony/media). You are adding all of it.
3. **CALL-E is real and fully wired**, not partially removed. `apps/api/app/integrations/voice/engine.py` (206 lines) imports the real `calle` SDK, `apps/api/app/services/campaign_runner.py` (429 lines) calls it directly, and `apps/api/app/api/v1/routes/webhooks.py` (108 lines) is a live, registered route. Your first job is deleting all of this for real, not "wrapping" it.

The plan's ADR-2/ADR-4 also cite `ISSUES.md #84`/`#85` as prior-art recursion fixes to follow. **Those issue numbers don't exist in this repo** — `ISSUES.md`'s last entry is `#76`. The *pattern* they refer to (a `SECURITY DEFINER` helper function to break RLS self-reference) is real and already in use — see `apps/api/alembic/versions/202608060050_initial_schema.py`'s `is_org_member`/`has_org_role`/`current_user_id` functions and their own docstring ("a policy on memberships that queried memberships directly would recurse infinitely"). Follow that actual code, not the issue numbers.

**Deployment model, confirmed from `ecosystem.config.js` and `DEPLOYMENT.md`:** single VM, pm2, two processes today (`callflow-api`, `callflow-web`), nginx in front, nothing containerized. Your new `apps/voice-runtime/` worker is a **third pm2 process** on this same VM (or a separate one — see §7), following the exact same absolute-path/`.venv`/single-worker conventions the existing config uses.

---

## 1. Objective and scope

Replace the single managed CALL-E vendor with a BYO-telephony stack: LiveKit as the real-time media/SIP substrate, Twilio and Plivo as the org's own carrier, OpenRouter as the metered LLM marketplace. You own everything between "an org has stored Twilio/Plivo credentials" and "a LiveKit Agents worker is running a live conversation on a real phone call," plus the wholesale deletion of CALL-E.

**You own:**
- Deleting CALL-E from the codebase (backend half — Part 2 owns the frontend "calling unavailable" messaging, see §6).
- `apps/voice-runtime/` — the new deployable (LiveKit Agents worker).
- The SIP trunk provisioning workflow for Twilio and Plivo (ADR-2).
- `apps/api`'s new boundary that talks to LiveKit's server API (room creation, `CreateSIPParticipant`, dispatch rules).
- The `telephony_provisioning` table, its repository, and the connect-a-number background job.
- Outbound call origination that replaces `campaign_runner.py`'s CALL-E dial call.
- OpenRouter per-org key provisioning + usage metering (ADR-7's mechanism, not its pricing).
- The second STT/TTS adapter (A3.4).
- Deployment config for the new process.

**You do NOT own** (Part 2's job — don't touch these beyond the one coordination point in §6):
- `voice_agents` CRUD API/Pydantic models, the Agentic tab UI, extraction/completeness domain logic, `triage.py` changes, Needs-a-person UI, the OpenRouter model-picker UI, the result-schemas docs rewrite.

**You do NOT own** (Part 3's job, zero overlap):
- Anything under `channels`/`messages`/chat.

---

## 2. Dependencies and assumptions

- **No dependency on Part 2 or Part 3 to start.** CALL-E removal (§3) has zero prerequisites.
- **Part 2 depends on you** for: the `voice_agents`/`telephony_provisioning` migration (they build CRUD routes and the Agentic tab against it — see §6), and eventually the working `apps/voice-runtime/` for the first real end-to-end call test.
- **You depend on a human, not another developer**, for four things no amount of code produces: a LiveKit Cloud account + API key/secret (ADR-3, Ship tier, `ap-south` region), a test Twilio account + a real number, a test Plivo account + a real number, and an OpenRouter account with a management API key. Escalate immediately if these aren't provisioned — you cannot test past a certain point without them (see §9's mock-first strategy for what to do while waiting).
- **Assumption carried from the plan, flagged as unconfirmed:** LiveKit Cloud's exact agent-session overage rate (ADR-3 open item #1) and whether Twilio's inbound no-username/password limitation needs a dedicated TwiML endpoint on CallFlow's side (ADR-2 open item #5) are both genuinely open — budget investigation time for both during A1, don't assume the plan's numbers are final.

---

## 3. Task list — CALL-E removal (Phase A0, backend half)

Do this first. It's small, has zero external dependencies, and unblocks everything else by leaving the codebase in a compilable, bootable state with an honest "not available" behavior instead of dead vendor code.

### P1-T1 — Delete CALL-E outright

| Action | File |
|---|---|
| Remove dependency | `apps/api/pyproject.toml` line 7: `"calle-ai>=0.6.0",` |
| Delete whole file | `apps/api/app/integrations/voice/engine.py` |
| Delete whole file | `apps/api/app/api/v1/routes/webhooks.py` |
| Delete whole file | `apps/api/tests/test_engine.py` (140 lines, 7 tests) |
| Delete whole file | `apps/api/tests/test_webhooks.py` (280 lines, 6 tests) |
| Delete whole file | `apps/api/tests/test_run_events.py` (258 lines, 6 tests) |
| Remove router include | `apps/api/app/main.py` — find and remove the `webhooks` router import/`app.include_router(...)` line |
| Remove env vars | `apps/api/app/core/config.py` lines 45–47 (`api_key`, `default_region`, `default_language` — the `CALLE_*` fields) and lines 66–74 (`webhook_secret` — `CALLFLOW_WEBHOOK_SECRET`) |
| Remove `require_api_key()` | `apps/api/app/core/config.py` lines 155–161 — no longer has a caller once `engine.py` is gone |
| Update `.env.example` | Remove `CALLE_API_KEY`, `CALLE_DEFAULT_REGION`, `CALLE_DEFAULT_LANGUAGE` (lines 1–12) and `CALLFLOW_WEBHOOK_SECRET` (lines 48–53) |
| **Keep, do not delete** | `CALLFLOW_PUBLIC_API_URL` (`config.py` lines 60–66) — you will likely reuse it for whatever callback URL the LiveKit worker or webhook needs; do not delete blind, re-evaluate once P1-T3/P1-T4 are designed |
| **Keep, do not delete** | `apps/api/app/integrations/voice/protocol.py` — `VoiceProvider`/`VoiceCapability` stays as the pattern precedent per the plan's ADR-1 "what does NOT change" section. Nothing implements it directly yet; leave it alone until you have a second real reason to touch it |

Also remove, in `apps/api/app/api/v1/routes/runs.py`:
- The `get_call_events` route (lines 341–400) and its two response models `DeveloperEventOut` (lines 58–69) and `CallEventsOut` (lines 72–74) — this proxies CALL-E's own developer event log; there is no LiveKit equivalent yet, and none is assumed necessary (per the plan's §11 "rewrite only if LiveKit room events turn out to need an analogous log surface").
- The `EngineGateway`/`EngineAPIError`/`EngineConnectionError`/`EngineTimeoutError`/`classify_error` import block (lines 36–42) — only used by `get_call_events`.
- Leave `start_run`, `list_runs`, `team_summary`, `get_run` untouched — none of them import the engine.

### P1-T2 — Stub `campaign_runner.py` so the app boots (coordination point — see §6 before touching this file)

`apps/api/app/services/campaign_runner.py` imports `EngineGateway`/`EngineAPIError`/`EngineConnectionError`/`EngineTimeoutError`/`classify_error`/`TERMINAL` from the file you just deleted (lines 31–38), and `CampaignRunner.gateway`, `run_one()`, and `_poll_until_done()` all call into it directly. The whole file will fail to import the moment `engine.py` is gone.

**Do the minimum to keep the module importable and the app booting, honestly reporting "not available" — do not build a real placeholder pipeline.**

1. Remove the `from app.integrations.voice.engine import (...)` block (lines 31–38).
2. Remove `_RETRYABLE_FAILURES`/`_POLL_RETRYABLE_FAILURES` (they reference `DialFailure` values that stay meaningful, but nothing produces `EngineAPIError` to classify anymore — keep the frozensets, drop the docstring's CALL-E-specific reasoning, or leave a one-line TODO pointing at P1-T4).
3. Replace `run_one()`'s dial+poll body (roughly lines 340–427: the `try/except (EngineAPIError, ...)` block) with a single, honest failure:
   ```python
   # Real dial/poll implementation lands in P1-T4 (LiveKit CreateSIPParticipant).
   # Until then this must fail loudly, never silently — CLAUDE.md non-negotiable #9.
   return base.model_copy(
       update={
           "status": "FAILED",
           "error": DialFailure.PROVIDER_UNAVAILABLE.value,
           "disposition": Disposition.SKIPPED,
           "disposition_reason": "Calling is not available yet — the voice platform migration is in progress.",
       }
   )
   ```
4. Delete `_poll_until_done()` and the `gateway` property entirely (nothing calls them once the above lands) — don't leave dead code.
5. **Land this as its own small commit/PR the same day**, and tell whoever owns Part 2 the moment it merges — they will build their extraction-pipeline call site on top of this exact stub (see §6). Do not bundle this with any of P1-T3 onward; it needs to be reviewable and mergeable in isolation.

Run `pytest -q` in `apps/api` after this — `test_orchestrator.py` (806 lines) will have failing fixtures that construct `EngineAPIError`/`EngineConnectionError` (grep confirmed at least 8 call sites: lines 135, 146, 159, 691, 703, 726, 738, 763, 779, 793, 800). **Do not try to keep every one of these tests green right now.** Delete or `@pytest.mark.skip(reason="CALL-E removed, rewritten in P1-T7")` the ones that construct engine-specific exceptions; keep the ones testing `render_goal`, `check_dial_allowed`, and pure retry-classification logic that doesn't need the engine's exception types (see P1-T7 for the real rewrite).

### P1-T3 — Documentation

- `SYSTEM.md` §4 (backend modules table) and §5 (API reference): remove the `integrations/voice/engine.py`, `api/v1/routes/webhooks.py` rows and the `POST /api/v1/webhooks/calle/{secret}` and `GET /api/v1/runs/{run_id}/calls/{provider_call_id}/events` endpoint docs.
- `SYSTEM.md`'s F17 ("Voice provider abstraction") and F20 ("Call execution... polling only") gap-map entries: mark closed/superseded per the plan's §11.
- `ISSUES.md`: add a new entry (next number is **#77**, not #86 — verify with `grep '^### #' ISSUES.md | tail -1` before you write it, in case Part 2/3 land entries first) documenting the CALL-E removal as a deliberate, planned change, not a bug.

---

## 4. Task list — first real call (Phase A1, your half)

### P1-T4 — `apps/voice-runtime/` skeleton (ADR-1)

New deployable. Python, `livekit-agents` SDK. This process joins a LiveKit room, runs the org's configured STT→LLM→TTS pipeline, and exits when the call ends.

**Structure to create:**
```
apps/voice-runtime/
├── pyproject.toml          # livekit-agents, livekit-plugins-sarvam, livekit-plugins-openai (for with_openrouter())
├── app/
│   ├── worker.py           # entrypoint: joins room, runs pipeline
│   ├── config.py           # env → frozen dataclass, same pattern as apps/api/app/core/config.py
│   └── pipeline.py         # wires STT/TTS/LLM plugins per the room's job metadata
└── tests/
```

**Technical approach:**
- Mirror `apps/api/app/core/config.py`'s pattern exactly (frozen dataclass, `os.getenv` with defaults, loaded once at import) — this codebase has an established convention, don't invent a new one.
- The worker needs to know, per dispatched job, which org/`voice_agent` it's serving (so it can pick STT/TTS/LLM credentials) — this comes from whatever metadata `apps/api` attaches when it calls `CreateSIPParticipant` (coordinate the exact shape with P1-T6 below; you're writing both sides).
- Confirmed via ADR-4: `livekit-plugins-sarvam` is a real, LiveKit-maintained package (STT via Saarika, TTS via Bulbul). Confirmed via ADR-7: `livekit-agents[openai]`'s `with_openrouter()` factory is the LLM wiring — no separate OpenRouter plugin package.
- Per §13 open item #4 (explicitly *not* decided in the plan): don't build a CallFlow-owned `Protocol` layer over `SpeechToText`/`TextToSpeech`/`ConversationalLLM` before you have a working prototype to check it against. Depend on `livekit-agents`'s own plugin typing directly for now — this mirrors the exact "don't abstract before a second real implementation exists" discipline this codebase already applied once to `VoiceProvider` (see `protocol.py`'s own docstring).
- Transcript handoff: reuse `runs_repo.append_outcome()` over an internal call (per the plan's own suggestion), not a duplicated persistence path in the new codebase. Concretely this means either (a) the worker calls back into `apps/api` over an authenticated internal HTTP endpoint you add, or (b) the worker writes to Postgres directly using the same `database.as_user()`/service-role pattern — **pick (a)**: a second codebase talking to Postgres directly duplicates connection pooling, RLS-role-switching, and redaction logic that `apps/api` already owns; an internal HTTP call keeps the "only two ways into the database" rule (`CLAUDE.md` §4b) true without a third path.

**Expected inputs/outputs:** Input = a LiveKit room dispatch with job metadata (org id, voice_agent id, campaign goal text, contact info). Output = a call transcript + terminal status, POSTed to an internal `apps/api` endpoint you define alongside P1-T6 (e.g. `POST /internal/v1/calls/{call_id}/complete` — authenticate with a shared secret or a service-role API key, not a Supabase session, following the exact `database.anonymous()` + narrow-lookup pattern the deleted `webhooks.py` used).

### P1-T5 — SIP trunk provisioning (ADR-2), manual/semi-manual for this phase

Full four-step workflow (org pastes credentials → CallFlow calls LiveKit's server API to create inbound trunk + dispatch rule + outbound trunk → CallFlow calls Twilio's/Plivo's own REST API to configure Origination URI → verification call). **For A1, only Twilio, and manual/semi-manual is acceptable** — full automation of steps 2–3 for both providers is A2 (P1-T9 below).

**New files:**
- `apps/api/app/integrations/livekit/__init__.py`
- `apps/api/app/integrations/livekit/client.py` — the **only** file that imports the LiveKit server SDK, aliased on import (`from livekit import api as _VendorApi`), following the exact pattern `engine.py` used for CALL-E (`CLAUDE.md` §2's "vendor SDK import outside `app/integrations/{vendor}/`" rule, and §3's Dependency Inversion example). Owns: room creation, `CreateSIPParticipant`, inbound-trunk + dispatch-rule creation, outbound-trunk creation.
- `apps/api/app/integrations/telephony/twilio.py` — the only file that calls Twilio's own REST API (Origination URI update, credential-list registration). Twilio's inbound trunks don't support username/password auth (ADR-2) — investigate the TwiML-workaround shape here (§13 open item #5) before assuming a design.
- `apps/api/app/database/repositories/telephony_provisioning.py` — CRUD for the table below.

**Migration — you own this, Part 2 consumes it (see §6 for the handoff).** Follow the exact template in `apps/api/alembic/versions/202608071600_provider_credentials.py` (enable + force RLS, per-command policies, grant to `authenticated` — the four-part tenant-table treatment `CLAUDE.md` §4b requires). The plan's ADR-4 gives you the full SQL for both `voice_agents` and `telephony_provisioning`; reproduce it verbatim except:
- **Widen, don't drop, the existing constraint carefully**: `provider_credentials_provider_check` currently reads `provider in ('twilio', 'plivo')` (confirmed at `apps/api/app/database/models.py:255` and the migration above). ADR-4 says drop it to a plain non-empty check. Do this in the **same migration** as the two new tables, since it's one coherent schema change.
- The `telephony_provisioning` table is yours end-to-end (status machine, idempotency key, `last_error`). The `voice_agents` table's STT/TTS/LLM/name/prompt columns are Part 2's concern, but you're writing the same `CREATE TABLE` statement — see §6 for exactly how to split the work without both of you editing the same migration file at the same time.

**Idempotency, made concrete (ADR-4's own explicit callout):** if LiveKit trunk creation succeeds but the Twilio/Plivo REST call fails, the row stays `provisioning` with `last_error` set. A retry with the *same* idempotency key must check what already exists (query `telephony_provisioning` for existing `livekit_inbound_trunk_id`/`livekit_outbound_trunk_id` before creating new ones) rather than blindly re-running step 2 and orphaning a second LiveKit trunk. "Try again" from the UI (Part 2's job) starts a **new** row/key, never retries the stuck one in place.

### P1-T6 — Outbound call origination (A1.4)

Replaces `campaign_runner.py`'s old `gateway.start_call()` call site (the one you stubbed in P1-T2).

- New method on `apps/api/app/integrations/livekit/client.py`: wraps `CreateSIPParticipant`.
- Update `campaign_runner.py`'s `run_one()`: replace the P1-T2 stub with a real call into this new module. **This is the second and last time you touch this file** — coordinate the exact call signature with Part 2 first (they own the code immediately downstream of this call, the extraction/triage step — see §6).
- The `_idempotency_key()` method (lines 256–277) is vendor-agnostic and reusable as-is — LiveKit's `CreateSIPParticipant` should be called with this same key so a retried request can't double-dial.
- `render_goal()` (from `app/domain/goal_rendering.py`, re-exported via `campaign_runner.py`) is unchanged — the rendered goal text becomes the job metadata / system-prompt input the worker (P1-T4) receives.

### P1-T7 — Rewrite `test_orchestrator.py`'s engine-specific fixtures

You broke this file in P1-T2 by deleting `EngineAPIError`/`EngineConnectionError`. Now that P1-T6 gives you a real replacement, go back and:
- Replace every fixture that raises `EngineAPIError`/`EngineConnectionError` (grep for `from app.integrations.voice.engine import` — 8+ call sites) with equivalents against your new LiveKit client module's own exception types (define a small internal exception taxonomy the same shape `DialFailure` already provides — do **not** invent a second failure vocabulary; map LiveKit/Twilio/Plivo errors onto the existing `DialFailure` enum in `app/domain/entities.py`, the same job `classify_error()` used to do for CALL-E).
- Keep every assertion that isn't engine-specific (the credit-reservation lock, suppression check, concurrency semaphore, idempotency-key tests) — these are vendor-agnostic per the plan's own §11 audit and should not be touched, only re-pointed at your new fixtures.

---

## 5. Task list — Phase A2 (Plivo + provisioning automation) and A3.1/A3.2/A3.4

### P1-T8 — Plivo SIP trunk provisioning
Mirrors P1-T5 for Plivo: inbound origination URI needs an explicit `;transport=tcp` (or `tls`) parameter (ADR-2); outbound auth produces a Termination SIP Domain (`<trunk_id>.zt.plivo.com`) + username/password. New file: `apps/api/app/integrations/telephony/plivo.py`, same one-vendor-per-file rule as Twilio.

### P1-T9 — Automate ADR-2 steps 2–3 for both providers
Turn P1-T5/P1-T8's manual/semi-manual flow into: CallFlow's backend calls Twilio's/Plivo's own REST API automatically, using the org's already-stored `provider_credentials`, rather than asking the org to click through the vendor's own console. This is flagged in the plan (§10) as a real, defensible differentiator — worth doing properly, not rushing.

### P1-T10 — OpenRouter provisioning-API integration (ADR-7, your half)
- New file: `apps/api/app/integrations/openrouter/client.py` — the only file importing/calling OpenRouter's provisioning API (`POST /api/v1/keys`).
- Provision **one OpenRouter key per organisation**, called from `apps/api` using CallFlow's own OpenRouter management key (a platform-level secret in `config.py`, **not** a per-org `provider_credentials` row — this key isn't the org's own credential, it's one CallFlow issues *to* them).
- Set a `limit`/`limitReset` per org's plan/billing tier.
- New repository + small table (or reuse a column on `organisations` if a single key-id/limit pair suffices — check with Part 2 before deciding, since they're the ones reading usage back into UI).
- Usage metering job: periodic read of `usage`/`usage_daily`/`limit_remaining` from OpenRouter's provisioning API (not solely the final SSE chunk — the plan explicitly warns streaming usage data isn't a documented hard guarantee). A simple scheduled task is enough; no new job-queue infrastructure — this codebase has no existing background-job system beyond FastAPI's `BackgroundTasks`, so a periodic task kicked by `BackgroundTasks` + a stored "last reconciled at" timestamp, or a cron-triggered script calling into a repository function, is proportionate. Don't introduce Celery/RQ for one recurring job.
- **Owed to Arbaaz, and worth landing early rather than as an afterthought:** their extraction/completion-judgment LLM call (their `RUNBOOK_ARBAAZ_PART_2.md` P2-T2) needs to resolve "the configured `ConversationalLLM` for this org's voice_agent" without importing an OpenRouter/LiveKit SDK into their own code — that's the whole point of the vendor-boundary rule. Expose a small, deliberately thin function here, e.g. `apps/api/app/integrations/openrouter/client.py::get_conversational_llm(voice_agent) -> ConversationalLLM`, resolving the org's provisioned key + the `voice_agent`'s `llm_model` into something that satisfies ADR-4's `ConversationalLLM` protocol shape (`respond(history, *, system_prompt) -> AsyncIterator[str]`). Tell Part 2 the exact function signature as soon as it exists — don't make them guess it or stub around a moving target for longer than necessary.

### P1-T11 — Second STT/TTS adapter (A3.4)
Add a second vendor (Deepgram and/or ElevenLabs, per the plan's own reference to `VOICE_AGENT_PLATFORM.md` §2.2) inside `apps/voice-runtime/`. This is what actually proves the BYO stack isn't a single-vendor lie — per `CLAUDE.md`'s own Substitutability rule ("an abstraction with one implementation is not an abstraction").

---

## 6. Integration points and shared work — read before touching any of these files

| Shared item | What you do | What Part 2 does | How to sequence it |
|---|---|---|---|
| `apps/api/app/services/campaign_runner.py` | P1-T2 (stub the dial call), then P1-T6 (real LiveKit origination call) | Adds the extraction/triage call site immediately after your dial call returns, and the §9 run-start rejection logic (in `routes/runs.py`, not this file) | **You go first.** Land P1-T2 (the stub) as an isolated, fast PR on day one. Tell Part 2 the exact shape of the `CallOutcome` your stub/real call returns before they build against it. After that, you only touch this file once more, for P1-T6 — give Part 2 a heads-up before that PR so they can rebase past it. |
| `voice_agents` / `telephony_provisioning` migration | You author the full migration (ADR-4's SQL), since `telephony_provisioning` and the RLS/idempotency design is your core deliverable | Consumes the `voice_agents` table's STT/TTS/LLM/name/prompt columns for their CRUD API and Agentic tab | **Don't block Part 2 on this.** Tell them the exact column list from ADR-4 on day one (it's fully specified in the plan already — `id, org_id, name, kind, stt_provider, stt_credential_id, tts_provider, tts_credential_id, llm_provider, llm_credential_id, llm_model, telephony_provider, telephony_credential_id, prebuilt_persona, system_prompt, voice_id, created_at, created_by`) so they can build their Pydantic models and stub their repository against that shape immediately, without waiting for your migration to merge. Land the real migration as soon as you can — don't gold-plate it. |
| `apps/api/app/api/v1/routes/voice_agents.py` | You own the `POST .../{id}/connect-number` and `GET .../{id}/connect-number` endpoints (ADR-4's provisioning status polling) | Owns the `GET/POST/PATCH/DELETE` CRUD endpoints on the same resource | **Use two separate files, not one.** The plan's own ADR-4 draft lumps both concerns into one `routes/voice_agents.py` file — don't. Put your two endpoints in `apps/api/app/api/v1/routes/telephony.py` (still under the `/api/v1/voice-agents/{id}/connect-number` path prefix if you want the URL to match the plan exactly — the file that defines a route doesn't have to match the file's own name) and let Part 2 keep `voice_agents.py` for CRUD only. This is the single highest-value conflict-avoidance move in the whole plan — do it even though the plan doesn't ask for it. |
| `apps/api/app/auth/permissions.py` | No edits from you | Adds `Permission.AGENTS_READ`/`AGENTS_WRITE`/`AGENTS_DELETE` | Not your file. If you need a permission check inside your connect-number endpoint, import `Permission.AGENTS_WRITE` — don't add a new enum value for it. |
| `apps/api/app/api/v1/routes/runs.py` | You delete `get_call_events` (P1-T1) | Adds the §9 run-start rejection ("this campaign needs a voice agent with a connected number") inside `start_run()` | **You go first.** Your deletion is part of CALL-E removal (day one). Part 2's addition comes later, once `voice_agents` exists to check against. No real conflict if sequenced this way — different lines, different PRs, weeks apart. |
| `.env.example` / `config.py` | You remove CALL-E vars (P1-T1), add LiveKit/Twilio/Plivo/OpenRouter vars (P1-T4 onward) | No edits expected | Low risk — you're the only editor for the vars you're adding. |
| `ecosystem.config.js` / `DEPLOYMENT.md` | You add the third pm2 process entry once `apps/voice-runtime/` exists (P1-T4) | No edits expected | Follow the file's own documented port-allocation convention (`ss -ltnp` before claiming a port — see the file's own header comment) and the existing `ponytail:` comment style (single worker, `.venv`-resolved interpreter). |

**Do not wait on Part 2 to start.** Everything in §3 (CALL-E removal) and §4's LiveKit/SIP work (P1-T4, P1-T5) has zero dependency on their output. The only real rendezvous point is the end-to-end first call test (A1.7), which needs both your P1-T6 and their extraction pipeline + Agentic tab UI (to create a test voice agent) — that's a scheduled integration milestone, not a blocking dependency for your day-to-day work.

---

## 7. Technical approach notes

- **Deployment shape for `apps/voice-runtime/`:** it's a long-running worker process, not a request/response FastAPI app — don't build an HTTP server into it beyond whatever health-check endpoint pm2/nginx needs. Confirm with whoever owns infra whether it runs on the same VM as `apps/api`/`apps/web` (simplest, matches today's single-VM model) or a separate box (only justified once call volume argues for it — not a V1 decision per the plan's own ADR-3 reasoning about avoiding premature infra complexity).
- **Region:** deploy against LiveKit Cloud's `ap-south` (Mumbai) region for India-originating traffic (ADR-3) — revisit only once a working prototype's *measured* latency (not LiveKit's own blog number) says otherwise.
- **Vendor SDK boundary discipline:** every new integration (`livekit/client.py`, `telephony/twilio.py`, `telephony/plivo.py`, `openrouter/client.py`) must alias vendor imports on the way in, exactly like `engine.py` did (`from calle import CalleClient as _VendorClient`). This is a repo-wide non-negotiable (`CLAUDE.md` §2/§3), not a suggestion.
- **Fail closed:** if LiveKit Cloud, Twilio, or Plivo is unreachable during provisioning or origination, the row/call must land in an explicit `failed` state with a real `last_error`, never silently retry forever or report success.

---

## 8. Testing requirements

- `apps/api/app/integrations/livekit/client.py`, `telephony/twilio.py`, `telephony/plivo.py`, `openrouter/client.py`: unit tests against a stubbed/mocked vendor client, same shape as `tests/test_engine.py`'s `StubVoiceProvider` pattern — CLAUDE.md's Substitutability rule ("write the second adapter, even if it is only a stub for tests") applies to your new vendors too.
- `telephony_provisioning` repository: a test that a retried idempotency key does **not** create a second LiveKit trunk when the first attempt already succeeded partway.
- **Cross-tenant RLS test required** for both new tables (`CLAUDE.md` §7 checklist item — "a policy that looks right and permits a cross-tenant read is the most expensive bug available here"). Follow `apps/api/tests/test_rls_isolation.py`'s existing pattern: hit the database directly as two different orgs, assert org B never sees org A's `voice_agents`/`telephony_provisioning` rows.
- `apps/voice-runtime/`: at minimum, a test that the pipeline wiring picks the correct STT/TTS/LLM plugin given a voice_agent's stored provider fields, without needing a live LiveKit room (mock the plugin factories).
- Re-run `pytest -q` in `apps/api` after every CALL-E-removal step (P1-T1/T2) — don't let the suite sit broken between commits.
- `ruff check app tests` must stay clean per `CLAUDE.md` §6/§7 — this includes your new `apps/voice-runtime/` if it lands inside the same lint scope, or its own `ruff` config if it's a separate `pyproject.toml` (it is, per §4's file tree — configure `ruff` for it too).

---

## 9. Working around missing vendor accounts

If LiveKit/Twilio/Plivo/OpenRouter accounts aren't provisioned yet when you start:
1. Build `apps/voice-runtime/`'s pipeline wiring and `apps/api`'s `livekit/client.py`/`telephony/*.py` against the vendor SDKs' documented interfaces, with unit tests against stubs (per §8) — this is real, mergeable progress with zero live-account dependency.
2. Do not fabricate a "looks like it works" demo against a stub and report it as a working call — `CLAUDE.md` non-negotiable #9 applies to your own status reporting, not just user-facing UI.
3. Escalate the account provisioning as a blocker the moment you can't make further real progress without it — don't sit on it silently.

---

## 10. Validation checklist / Definition of Done

- [ ] `calle-ai` no longer appears anywhere in `apps/api/pyproject.toml` or its lockfile.
- [ ] `apps/api/app/integrations/voice/engine.py`, `apps/api/app/api/v1/routes/webhooks.py`, and their three test files are deleted, not stubbed.
- [ ] `CALLE_API_KEY`/`CALLE_DEFAULT_REGION`/`CALLE_DEFAULT_LANGUAGE`/`CALLFLOW_WEBHOOK_SECRET` are gone from `config.py` and `.env.example`.
- [ ] `apps/api` boots and `pytest -q` runs (not necessarily 100% green immediately after P1-T2, but importable and not crash-looping) with CALL-E fully removed.
- [ ] `apps/voice-runtime/` exists as an independently runnable process with its own `pyproject.toml`, passes `ruff check`, and has at least one real test.
- [ ] A real LiveKit room can be created and a `CreateSIPParticipant` call placed against a test Twilio number (manual verification acceptable for A1; automated for A2).
- [ ] `telephony_provisioning` table exists with full RLS (enable + force, per-command policies, grant) and a passing cross-tenant isolation test.
- [ ] Retrying the same `connect-number` idempotency key after a partial failure does not create a second LiveKit trunk (tested, not just reasoned about).
- [ ] One OpenRouter key is successfully provisioned per test org, with usage readable back via the provisioning API.
- [ ] A second STT/TTS vendor is wired into `apps/voice-runtime/` and passes the same pipeline-wiring test as the first.
- [ ] `ecosystem.config.js` has a third app entry for the voice-runtime process, using a port confirmed free via `ss -ltnp`, and `DEPLOYMENT.md` documents it.
- [ ] `SYSTEM.md` and `ISSUES.md` are updated per §3's documentation subtasks.
- [ ] End-to-end: one real phone call placed through the full pipeline (LiveKit + Twilio + your chosen STT/TTS + OpenRouter LLM), transcript persisted back through `runs_repo.append_outcome()` — this is the milestone that closes Phase A1 and requires coordination with Part 2 (their extraction/triage step must exist to see this outcome triaged correctly).
