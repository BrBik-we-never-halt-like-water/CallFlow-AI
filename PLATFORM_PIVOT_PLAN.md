# The platform pivot: multi-provider voice agents, team chat, and the end of CALL-E

**Status: design only, iterating.** Nothing in this document is implemented. It supersedes
`VOICE_AGENT_PLATFORM.md`'s P4/P5a/P5b sections (which designed a from-scratch media
runtime before LiveKit was chosen) while keeping its §1 Sarvam/Twilio/Plivo protocol
research and its general shape for §2 (the `voice_agents` data model). Read
`CLAUDE.md` first - every decision below is judged against its non-negotiables.
Read `VOICE_AGENT_PLATFORM.md`, `CALLE.md`, and `CALLE_INTEGRATION_STATUS.md` for the
prior research this builds on. This doc does not repeat their findings verbatim; it
cites them.

**Why this document exists, in the team's own words:** CALL-E - the single managed
vendor this product has dialled through since its first working version - became
unreliable ("not at all responsive") on top of a limitation that was always there
(no bring-your-own-number, confirmed in `CALLE_INTEGRATION_STATUS.md` §1: "No
bring-your-own-number/SIP surface exists anywhere in the API"). The team has decided,
independent of the outage, to move to a platform where an organisation brings its own
Twilio or Plivo number and configures its own conversational agent (BYO STT/TTS/LLM, or
a CallFlow-operated prebuilt one) - the model `VOICE_AGENT_PLATFORM.md` already sketched,
now built on **LiveKit** as the real-time media substrate rather than a hand-rolled
WebSocket media runtime, and monetised on the LLM side through **OpenRouter** rather than
one first-party model. Two decisions were made explicitly, not assumed, before any of the
research below happened:

1. **The "chat messaging system" is internal team chat** - teammates within one
   organisation messaging each other (channels and/or DMs), not contact-facing SMS/
   WhatsApp and not an in-agent text-chat channel. This determines the entire data model
   in §7.
2. **CALL-E removal is immediate and unconditional**, not staged behind a proven
   replacement. The product will have **no working outbound-calling capability** between
   CALL-E's removal and the new stack's first working phase - this is an accepted,
   deliberate gap, not an oversight. Every phase below is sequenced with that gap in mind:
   the fastest possible path to *any* real call going out again is the actual priority
   metric for Phase 1, not feature completeness.

**How this document was built**, since the user asked for the process to be visible: two
external deep-research passes (LiveKit/SIP/OpenRouter technical mechanics; competitive
market/differentiation), one narrower single-pass follow-up on three gaps the first
technical pass didn't resolve, and three internal codebase audits (the triage/escalation/
result-schema system, the RLS/permission/realtime patterns team chat must follow, and an
exact file-by-file CALL-E removal inventory) - all cited by URL or file:line throughout,
not asserted from memory. Every confirmed technical claim below survived independent
adversarial verification (a claim needed 2-of-3 independent attempts to *refute* it to
survive) unless explicitly marked otherwise. Where research came back empty or refuted,
that is stated plainly as an open item, not papered over with a plausible-sounding guess.

---

## Table of contents

1. [What's already true - the reuse map](#1-whats-already-true---the-reuse-map)
2. [ADR-1: LiveKit replaces the from-scratch media runtime](#adr-1-livekit-replaces-the-from-scratch-media-runtime)
3. [ADR-2: SIP trunking topology for BYO Twilio/Plivo numbers](#adr-2-sip-trunking-topology-for-byo-twilioplivo-numbers)
4. [ADR-3: LiveKit Cloud for V1, not self-hosted](#adr-3-livekit-cloud-for-v1-not-self-hosted)
5. [ADR-4: the `voice_agents` data model and STT/TTS/LLM adapters](#adr-4-the-voice_agents-data-model-and-sttttsllm-adapters)
6. [ADR-5: extraction and completeness checking - a genuinely new module](#adr-5-extraction-and-completeness-checking---a-genuinely-new-module)
7. [ADR-6: internal team chat](#adr-6-internal-team-chat)
8. [ADR-7: OpenRouter as the LLM marketplace + billing model](#adr-7-openrouter-as-the-llm-marketplace--billing-model)
9. [The revised call-routing model](#9-the-revised-call-routing-model)
10. [Market differentiation - what to actually build, evidence-graded](#10-market-differentiation---what-to-actually-build-evidence-graded)
11. [CALL-E removal - the exact checklist](#11-call-e-removal---the-exact-checklist)
12. [Phased roadmap](#12-phased-roadmap)
13. [Open items requiring a vendor conversation or a follow-up pass](#13-open-items-requiring-a-vendor-conversation-or-a-follow-up-pass)
14. [Explicitly out of scope for V1](#14-explicitly-out-of-scope-for-v1)

---

## 1. What's already true - the reuse map

From the internal audits (agents `a1288fd1d5fc80432`, `a1eaf2a5ad090760c`,
`a8189f9188a09af17`), not re-derived here:

| Piece | State | Source |
|---|---|---|
| Four-role permission system, RLS-enforced multi-tenancy | Real, mature, the template every new table below follows | `apps/api/app/auth/permissions.py`, `CLAUDE.md` §4b |
| Peer-to-peer resource sharing (`share_requests`) | Real, shipped this round - the per-command-policy, `SECURITY DEFINER`-helper RLS pattern is the exact template §7 (chat) follows | `202608101100_share_requests.py` |
| Real, persisted, assignable escalations | Real, shipped this round - reused almost unchanged by §6's new triage rule | `202608100900_escalations_and_credit_allocations.py` |
| Generic Realtime hook (`useOrgRealtime`) | Already accepts an arbitrary table name - **no code change needed** for chat's realtime wiring, only correct RLS (see §7) | `apps/web/lib/hooks/use-org-realtime.ts:25-51` |
| `provider_credentials` table | Already generic enough (identifier+secret pair) to hold Sarvam/OpenRouter credentials unchanged - only its `check` constraint needs widening | `apps/api/app/database/repositories/provider_credentials.py`, constraint at `202608071600_provider_credentials.py:83` |
| `triage()`'s precedence-ordered disposition logic | Mostly vendor-neutral and reused as-is; **one rung (`task_completed is False`) is CALL-E-proprietary and vanishes** unless the new extraction step is deliberately prompted to produce an equivalent (§6) | `apps/api/app/domain/triage.py:39-89` |
| `result_schema`/`outcome_fields`/"required" checkbox | Exists, user-configurable today, **but nothing downstream has ever checked it** - confirmed not a partial implementation, a complete no-op past schema construction | `apps/api/app/domain/result_schemas.py`, campaign editor `required` checkbox, audit `a1eaf2a5ad090760c` §2 |
| Credit reservation, suppression check, concurrency semaphore, idempotency-key pattern (`campaign_runner.py`) | Vendor-agnostic, reused unchanged - only the dial/poll loop itself (CALL-E-specific) is replaced | Audit `a8189f9188a09af17` §2 |
| `TEAM_COLLABORATION_ROADMAP.md` Phase 3 (notifications) | Not chat, but the nearest existing precedent for per-user (not per-org) Realtime scoping - unbuilt, not blocking chat, but worth building alongside it (§12) | `TEAM_COLLABORATION_ROADMAP.md:220-249` |

**The one contradiction this plan must resolve, not inherit:** a live public docs page
(`apps/web/app/(marketing)/docs/result-schemas/page.mdx:48-55`) states as product
philosophy that "nothing is required... a field being missing... belongs in your triage
reading of the results, not in forcing the agent." §6 below builds exactly the feature
that philosophy argues against. That page needs rewriting as part of §6 shipping, not
left standing as a contradiction.

**What is explicitly unaffected - stated directly, since a completeness review found
this plan only ever discussed what's *new* and never once stated the negative.** Every
page and system this document doesn't mention is unchanged, on purpose, not by omission:

- **Contacts** (`/app/contacts`) - untouched. Nothing in this pivot changes contact
  storage, CSV import, or the suppression list; a `voice_agent`/campaign dials a contact
  the same way regardless of which telephony/STT/TTS/LLM stack is behind it.
- **Organisation** (`/app/organisation` - org settings, Team, and now Sharing tabs) -
  untouched. Role management, invitations, and peer-to-peer resource sharing keep working
  exactly as they do today; nothing in ADR-1 through ADR-7 modifies `permissions.py`'s
  *existing* entries, `share_requests`, or the org-membership model - only *adds* new
  permission entries (`AGENTS_*`, `MESSAGES_*`) alongside them, the same way `Phase 4`
  sharing added `SHARING_REQUEST` without touching anything that came before it.
- **Settings** (Safety, API keys, Billing) - untouched, except Integrations, which
  already stores Twilio/Plivo credentials today and simply gains real *use* for them
  (ADR-2) rather than changing shape.
- **Dashboard, the existing five-item primary nav, Campaigns, Runs** - untouched in
  structure; Campaigns gains one new optional field (`voice_agent_id`) and Runs gains a
  new rejection case at start-time (§9) - additive, not a redesign of either page.
- **The entire role/permission/RLS/multi-tenancy foundation** - untouched as
  architecture; every new table in this plan (`voice_agents`, `telephony_provisioning`,
  `channels`, `channel_members`, `messages`) *follows* that foundation's own established
  patterns rather than introducing a competing one, per §1's own reuse-map table above.

---

## ADR-1: LiveKit replaces the from-scratch media runtime

**Status:** Accepted · **Date:** 2026-08-11 · **Supersedes:** `VOICE_AGENT_PLATFORM.md`'s
P4 ("Media runtime... a working prototype... itself multiple weeks") and its own ADR-1
(Twilio-first-unabstracted, extract-later-from-two-real-implementations).

### Context

`VOICE_AGENT_PLATFORM.md` §1 correctly identified that Twilio Media Streams and Plivo's
audio-streaming feature use asymmetric WebSocket vocabularies, and its own ADR-1 decided
to build a raw `TwilioMediaHandler` first, un-abstracted, rather than guess a shared
`MediaChannel` protocol before a second real implementation existed. That was the right
call **given the premise that CallFlow would build the media runtime itself.** That
premise is what changed: the team has since decided to build on LiveKit, which already
*is* the abstraction both vendors' asymmetric protocols get normalised into - confirmed
this round (deep-research pass, task `wlbyf1fxr`): LiveKit's SIP integration bridges
both Twilio and Plivo into the same internal concept (a room with SIP participants), and
LiveKit Agents provides one plugin framework across STT/TTS/LLM regardless of which
telephony vendor is on the other end of the call.

### Decision

**Do not build `apps/voice-runtime/` as a raw WebSocket media server. Build it as a
LiveKit Agents worker process** (Python, `livekit-agents` SDK) that joins a room, runs
the org's configured STT→LLM→TTS pipeline, and exits when the call ends. LiveKit itself
(Cloud or self-hosted, see ADR-3) owns the SFU, the SIP bridge, and the Twilio/Plivo
**media/audio** protocol asymmetry `VOICE_AGENT_PLATFORM.md`'s ADR-1 was designed around
- that specific asymmetry (differing WebSocket message vocabularies for audio streaming)
never reaches CallFlow's own code. **This claim is narrower than it first sounds, and
ADR-2 finds the real exception**: SIP-*trunk provisioning* is a different layer from
media streaming, and Twilio's own auth limitation there (no username/password on
inbound trunks) does reach CallFlow's provisioning code, in the form of a small
TwiML-serving endpoint ADR-2 scopes explicitly. Read "none of that reaches CallFlow's
code" as "the hard media-protocol problem `VOICE_AGENT_PLATFORM.md` originally scoped
weeks against," not as "Twilio and Plivo become fully interchangeable everywhere."

**What CallFlow's code actually has to own, concretely** (confirmed, not assumed - all
four load-bearing findings are 3-0 verified in `wlbyf1fxr`):

1. **SIP trunk provisioning** per org, per provider (ADR-2) - a one-time setup flow when
   an org connects a number, not a per-call concern.
2. **Originating outbound calls** via LiveKit's `CreateSIPParticipant` API - confirmed
   this is *not* passive; LiveKit "does not passively bridge audio... you need to
   explicitly create a SIP participant" for every outbound call. This is the direct
   replacement for `campaign_runner.py`'s `gateway.start_call()` call site.
3. **The Agents worker itself** - wiring the org's chosen STT/TTS/LLM plugins into a
   LiveKit Agents pipeline, running the system prompt, handing the resulting transcript
   back to `apps/api` for persistence.
4. **Everything already vendor-agnostic in `campaign_runner.py`** (credit reservation,
   suppression check, the concurrency/idempotency pattern) - reused, not rebuilt, per the
   removal audit (`a8189f9188a09af17` §2).

This collapses `VOICE_AGENT_PLATFORM.md`'s P4/P5a/P5b (three phases, "multiple weeks, not
days, even with one vendor and one test number") into what §12 below schedules as a
single phase - not because the work became trivial, but because the *specific* hardest
part that doc scoped weeks against (hand-rolling two vendors' asymmetric WebSocket
protocols and their reconnect/backpressure/barge-in semantics) is now LiveKit's problem,
not CallFlow's.

### What does NOT change from the old design

- The `VoiceProvider` protocol (`apps/api/app/integrations/voice/protocol.py`) stays as
  the pattern precedent, even though nothing implements it against LiveKit directly (the
  worker process, not `apps/api`, is what talks to LiveKit) - `apps/api`'s own boundary
  is now "talk to the LiveKit server API to create rooms/SIP participants," which
  deserves the same one-file-owns-the-vendor-import treatment.
- §1's Sarvam findings (Saarika STT, Bulbul TTS, dual auth-header support) are unchanged
  and now map directly onto real, existing LiveKit plugins (`livekit-plugins-sarvam`,
  confirmed published by LiveKit itself - see ADR-4).

### Consequences

- A **new deployable** is required: `apps/voice-runtime/` (or similar), a long-running
  process distinct from `apps/api`'s request/response FastAPI app - this was already
  true in the old design and remains true; LiveKit doesn't remove the need for CallFlow
  to run *an* agent process, it removes the need for that process to speak raw SIP/RTP.
- `apps/api` needs a new internal boundary: whatever calls LiveKit's server APIs
  (room creation, `CreateSIPParticipant`, dispatch-rule management) - likely inside the
  new run-start path, replacing `campaign_runner.py`'s CALL-E call.
- The worker process needs its own way to write outcomes back - reusing
  `runs_repo.append_outcome()` over an internal call, per the old doc's own suggestion,
  rather than duplicating persistence logic in a second codebase.

---

## ADR-2: SIP trunking topology for BYO Twilio/Plivo numbers

**Status:** Accepted · **Date:** 2026-08-11

### Context

Confirmed this round (task `wlbyf1fxr`, all findings 3-0 verified except where noted):
bringing an org's own Twilio or Plivo number into a LiveKit room is **standard SIP
trunking in both directions, not a proprietary bridging API**, but inbound and outbound
are genuinely two separate configurations, and Twilio and Plivo differ in real,
non-cosmetic ways:

- **Inbound** (a call arrives at the org's number, needs to reach a LiveKit room): the
  org's carrier trunk's Origination URI is pointed at a LiveKit SIP endpoint; LiveKit
  requires its own **inbound trunk** resource (tied to the number) plus **at least one
  dispatch rule** (which can create a room per caller dynamically) before it accepts
  anything.
- **Outbound** (CallFlow places a call from the org's own number): LiveKit does **not**
  passively bridge this - the platform must call LiveKit's `CreateSIPParticipant` API
  explicitly, against a separately-configured, credential-authenticated **outbound
  trunk** (a different LiveKit-side object from the inbound trunk/dispatch-rule pair).
- **Twilio specifics:** the Elastic SIP Trunk's domain must end in `pstn.twilio.com`;
  outbound auth uses a Twilio *credential list* that must match LiveKit's outbound-trunk
  config; **Twilio's inbound trunks do not support username/password authentication at
  all** (a TwiML-based workaround is required) - confirmed via LiveKit's own docs
  stating support "varies by provider" with Twilio named as the exception.
- **Plivo specifics:** the inbound origination URI needs an explicit
  `;transport=tcp` (or `tls`) parameter; outbound authentication produces a **Termination
  SIP Domain** (`<trunk_id>.zt.plivo.com`) plus username/password, fed into a separate
  LiveKit outbound trunk.

### Decision

**Treat "connect a number" as a real provisioning workflow with four steps, not a
credential paste-in** - and **automate as much of it as the Twilio/Plivo REST APIs
allow**, since CallFlow already stores the org's full API credentials (`integrations.py`)
and can act on their behalf rather than sending them to configure their own SIP trunk by
hand in a second vendor's console:

1. Org pastes Twilio/Plivo credentials (unchanged from today's Integrations flow).
2. CallFlow's backend calls LiveKit's server API to create the inbound trunk + a dispatch
   rule, and the outbound trunk with generated credentials, for that org+number.
3. CallFlow's backend calls Twilio's/Plivo's own REST API to configure that org's SIP
   trunk's Origination URI (pointing at the LiveKit endpoint from step 2) and, for
   outbound, register the matching credential list/termination domain - **automatically**,
   using the org's already-stored credentials, rather than asking them to click through
   Twilio's or Plivo's console.
4. A verification call (a short automated test call, or a documented manual check) before
   the number is marked "connected" in the UI - **CLAUDE.md's non-negotiable #9** ("never
   show a success state for something that did not happen") applies directly here: a
   number that's stored but not actually wired end-to-end must not show as connected.

This is also flagged in §10 as a candidate differentiator: doing steps 2-3
programmatically, instead of handing the org a setup guide, is real UX work none of the
surveyed competitors' docs describe doing for their customers.

### Consequences

- **The actual table, not a gesture at one**: `public.telephony_provisioning` (defined in
  ADR-4, alongside `voice_agents` since it's what a `voice_agent`'s
  `telephony_credential_id` connection attempt actually produces) - one row per
  provisioning attempt, an explicit `pending/provisioning/verified/failed` status, an
  idempotency key so a retried attempt can't double-create LiveKit trunks, and
  `last_error` for an honest failure reason. This closes what the first draft of this
  ADR only named without designing.
- The "connect a number" flow becomes genuinely more complex than today's Integrations
  tab - a real multi-step, resumable workflow, not a credential paste-in.
- Twilio's inbound auth limitation (no username/password) means the inbound path needs a
  small TwiML-serving endpoint on CallFlow's side for Twilio specifically - **this is a
  real asymmetry with ADR-1's own framing** ("none of that asymmetry reaches CallFlow's
  own code at all") worth flagging plainly rather than smoothing over: ADR-1's claim
  holds for the *media/audio* protocol asymmetry (Twilio's/Plivo's differing WebSocket
  vocabularies, which genuinely stay inside LiveKit), but not for *SIP-trunk
  provisioning*, where Twilio's specific auth limitation does reach CallFlow's own
  provisioning code. Two different layers, two different answers - see ADR-1's own
  "What does NOT change" section for the corrected, narrower claim.

---

## ADR-3: LiveKit Cloud for V1, not self-hosted

**Status:** Accepted, with an explicit caveat · **Date:** 2026-08-11

### Context

The first research pass explicitly **failed to produce verified pricing** - candidate
figures were refuted on re-verification (task `wlbyf1fxr`). A targeted single-pass
follow-up (task `a4dd2040c00553c37`, direct fetch of `livekit.com/pricing` and
`kb.livekit.io`, 2026-08-11) got real numbers this time:

| Tier | Monthly | WebRTC participant-min included | Overage | SIP telephony included | SIP overage | US local inbound | Bandwidth |
|---|---|---|---|---|---|---|---|
| Build | $0 | 5,000 min | - | 1,000 min | - | 50 min | 50GB |
| Ship | $50 | 150,000 min | $0.0005/min | 5,000 min | $0.004/min | 100 min, then $0.01/min | 250GB, then $0.12/GB |
| Scale | $500 | 1.5M min | $0.0004/min | 50,000 min | $0.003/min | 1,000 min, then $0.01/min | 3TB, then $0.10/GB |
| Enterprise | custom | - | - | - | - | - | - |

Agent-session minutes are included separately (Build 1,000 / Ship 5,000 / Scale 50,000;
concurrent sessions 5/20/up to 600) - **the specific overage rate once those run out was
not found on the primary pricing page itself** (only via third-party SEO summaries, not
independently confirmed - do not use a $0.01/min agent-session figure without re-checking
directly against the live page at commit time).

**Self-hosting, concretely** (`docs.livekit.io/transport/self-hosting/`,
`github.com/livekit/sip`): the SIP bridge (`livekit/sip`) is a **separate service** from
the core media server, communicating with it over Redis, needing its own public IP and
open SIP (5060) + RTP (10000-20000) ports, with TLS and clustering required for a real
production deployment - this is not "run one Docker container," it's operating a second
network-facing service with its own port-range/firewall requirements on top of the SFU
itself.

**India latency**: LiveKit confirms an `ap-south` (Mumbai) region and claims ~1.67s
end-to-end latency for a GPT-4o+Cartesia+Deepgram stack co-located there (~1s faster than
routing cross-region) - this figure is **LiveKit's own blog, not independently
benchmarked**; treat as directional, not a committed SLA.

### Decision

**Start V1 on LiveKit Cloud, on the Ship tier** ($50/mo, the first tier with meaningful
included telephony minutes and a real overage rate rather than a hard cap) - now backed by
real numbers, not just the infra-ops-maturity argument alone:

1. **No infra-ops team exists at this company today**, and self-hosting means operating a
   second network-facing service (the SIP bridge) with its own port/firewall/clustering
   requirements - confirmed a materially bigger commitment than "self-host is just
   cheaper," not merely asserted.
2. **The org already trusts managed infrastructure for its hardest problem** (Supabase),
   the same bet for the same reason.
3. **The numbers are now concrete enough to model a per-call cost**: a typical 3-minute
   call at Ship-tier overage rates is roughly 3 WebRTC participant-minutes (~$0.0015,
   agent + caller both connected) + 3 SIP-trunking minutes (~$0.012) + whatever the
   still-unconfirmed agent-session overage adds - **confirm that last figure before
   finalising ADR-7's per-call cost model**, everything else here is real.
4. **Deploy to the `ap-south` (Mumbai) region for India-originating traffic** given the
   confirmed region exists, revisiting only if a working prototype's measured latency
   (not the vendor's own blog number) says otherwise.

Migrating to self-hosted later remains available and is not a one-way door - revisit once
call volume actually justifies operating the SIP bridge as production infrastructure.

---

## ADR-4: the `voice_agents` data model and STT/TTS/LLM adapters

**Status:** Accepted, revising `VOICE_AGENT_PLATFORM.md` §2.1-2.2 · **Date:** 2026-08-11

### What's confirmed and changes the old sketch

1. **An official `livekit-plugins-sarvam` package exists**, published by LiveKit itself
   (not a third-party community package) - STT via Sarvam's Saarika models, TTS via
   Bulbul, **and** an OpenAI-compatible LLM interface for Sarvam-hosted models with
   tool-calling (task `wlbyf1fxr`, 3-0/2-1 verified). This means the Sarvam adapter work
   `VOICE_AGENT_PLATFORM.md` §2.2-2.3 scoped as build-and-test-from-scratch is instead
   **integrate an existing, first-party-maintained plugin** - materially less work, and
   no need for the recorded-fixture/fake-WebSocket-server testing strategy that doc
   designed for a from-scratch adapter (§2.3 of the old doc becomes moot; LiveKit's own
   plugin is what needs trusting, the same way this codebase already trusts `asyncpg`
   without hand-testing Postgres's own wire protocol).
2. **OpenRouter is natively supported**, not a workaround: LiveKit's `openai` plugin
   ships a dedicated `with_openrouter()` factory (default base URL
   `https://openrouter.ai/api/v1`, resolves `OPENROUTER_API_KEY`, supports OpenRouter-
   specific fallback-model lists and provider-routing preferences) as a thin wrapper over
   the same generic `base_url`/`api_key` override every OpenAI-compatible provider uses.
   No separate plugin package - just `livekit-agents[openai]`.
3. **The `llm_provider = 'openrouter'` case needs a model field the old schema didn't
   have.** OpenRouter is one credential proxying *many* models - unlike Sarvam (one
   provider, effectively one model per slot), an org's agent needs to record *which*
   OpenRouter-listed model it's configured to use, not just that it uses OpenRouter.

### Decision - revised schema

**Adversarial review caught two real gaps in the first draft, both fixed below: no
schema link between an agent and the number it dials from (§9's own routing check
presupposes this exists), and no RLS at all on a table holding references to STT/TTS/LLM
*credentials* - a materially sensitive omission given `CLAUDE.md`'s own multi-tenancy
non-negotiable.**

```sql
create table public.voice_agents (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organisations(id) on delete cascade,
  name text not null,
  kind text not null check (kind in ('custom', 'prebuilt')),

  stt_provider text,             -- e.g. 'sarvam'
  stt_credential_id uuid references public.provider_credentials(id),
  tts_provider text,             -- e.g. 'sarvam'
  tts_credential_id uuid references public.provider_credentials(id),
  llm_provider text,             -- e.g. 'openrouter', 'sarvam'
  llm_credential_id uuid references public.provider_credentials(id),
  llm_model text,                -- NEW: e.g. 'anthropic/claude-sonnet-4' - required when
                                  -- llm_provider = 'openrouter', since one credential
                                  -- proxies many models; null/ignored otherwise.

  -- NEW - closes the adversarial review's routing gap: which number this agent
  -- dials from. One number per agent for V1 (simplest correct model - an org
  -- with multiple agents connects a number per agent, not a shared pool yet;
  -- revisit only if a real org asks for shared-number routing).
  telephony_provider text,        -- 'twilio' | 'plivo', null until connected
  telephony_credential_id uuid references public.provider_credentials(id),

  prebuilt_persona text,          -- kind = 'prebuilt' only
  system_prompt text,
  voice_id text,

  created_at timestamptz not null default now(),
  created_by uuid references public.users(id) on delete set null
);

-- NEW - closes the adversarial review's ADR-2 idempotency gap: the actual
-- pending/provisioning/verified/failed state machine ADR-2's consequences
-- named but never defined. One row per voice_agent's telephony connection
-- attempt, not per voice_agent, so a failed attempt can be retried (a new
-- row) without losing the history of what was tried before - the same
-- "never delete, only re-statused" instinct this codebase already applies
-- to ISSUES.md, applied to infrastructure state instead of bug reports.
create table public.telephony_provisioning (
  id uuid primary key default gen_random_uuid(),
  voice_agent_id uuid not null references public.voice_agents(id) on delete cascade,
  org_id uuid not null references public.organisations(id) on delete cascade,
  status text not null default 'pending'
    check (status in ('pending', 'provisioning', 'verified', 'failed')),
  idempotency_key text not null,   -- one attempt = one key, matching the
                                    -- `campaign_runner.py` idempotency-key
                                    -- pattern this ADR's own consequences
                                    -- cited but didn't actually reuse - retrying
                                    -- the same attempt (e.g. a UI double-click,
                                    -- or a step-3 retry after step-2 succeeded)
                                    -- must not re-run an already-completed step.
  livekit_inbound_trunk_id text,
  livekit_outbound_trunk_id text,
  livekit_dispatch_rule_id text,
  carrier_termination_domain text,  -- Plivo's <trunk_id>.zt.plivo.com, null for Twilio
  last_error text,                  -- the honest reason if status = 'failed' -
                                     -- CLAUDE.md's error-writing convention applies
                                     -- here same as anywhere else in the product
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (voice_agent_id, idempotency_key)
);

alter table public.provider_credentials
  drop constraint provider_credentials_provider_check;  -- was: check (provider in ('twilio','plivo'))
alter table public.provider_credentials
  add constraint provider_credentials_provider_not_blank check (provider <> '');
```

**Idempotency/rollback behaviour, made explicit** (closing the adversarial review's ADR-2
gap): if step 2 (LiveKit trunk creation) succeeds but step 3 (Twilio/Plivo Origination-URI
update) fails, the row stays `provisioning` with `last_error` set - **retrying the same
attempt (same idempotency key) must check what's already been created and skip it**,
never blindly re-run step 2 and orphan a second LiveKit trunk. The UI surfaces `failed`
with `last_error` verbatim (never a generic "something went wrong," per `CLAUDE.md`'s
error-writing convention) and offers "try again," which starts a **new** row/key, not a
silent retry of the stuck one - so a permanently-broken first attempt doesn't block a
clean second one, and the failed attempt's diagnostic trail isn't overwritten.

**RLS and permissions - the real omission adversarial review found.** `voice_agents`
holds references to STT/TTS/LLM *credentials*; `telephony_provisioning` records
infrastructure identifiers. Both need the full four-part tenant-table treatment
`CLAUDE.md` §4b requires (enable + force RLS, per-command policies, grant) - the same
standard this doc's own §1 table already cited as "the template every new table below
follows" but didn't actually apply here in the first draft:

```sql
alter table public.voice_agents enable row level security;
alter table public.voice_agents force row level security;
alter table public.telephony_provisioning enable row level security;
alter table public.telephony_provisioning force row level security;

create policy voice_agents_select on public.voice_agents for select
  using (public.is_org_member(org_id));

create policy voice_agents_insert on public.voice_agents for insert
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

create policy voice_agents_update on public.voice_agents for update
  using (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

create policy voice_agents_delete on public.voice_agents for delete
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy telephony_provisioning_select on public.telephony_provisioning for select
  using (public.is_org_member(org_id));

create policy telephony_provisioning_insert on public.telephony_provisioning for insert
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

create policy telephony_provisioning_update on public.telephony_provisioning for update
  using (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

grant select, insert, update, delete on public.voice_agents to authenticated;
grant select, insert, update on public.telephony_provisioning to authenticated;
```

**The `provider_credentials` constraint-widening decision, made explicitly:** rather than
growing the `check` list forever (`in ('twilio','plivo','sarvam','openrouter', ...)`, one
migration per future vendor), drop it to a plain non-empty check and validate the allowed
set at the application layer (`Literal[...]` in the Pydantic model, matching how
`Provider` is already typed in `integrations.py`). Adding a sixth STT vendor later
becomes an app-code change, not a migration - a deliberate simplification, not an
oversight, given how many provider slots this design already has (STT, TTS, LLM ×
however many vendors each).

**New permissions** (`apps/api/app/auth/permissions.py`, following the exact existing
enum-plus-role-set pattern): `Permission.AGENTS_READ` (every role, matching viewer's
see-everything-read-only pattern elsewhere), `Permission.AGENTS_WRITE` (operator and
above - creating/editing an agent or connecting a number is a "spend the org's money and
credentials" action, the same tier as `CAMPAIGNS_WRITE`/`RUNS_START`), and
`Permission.AGENTS_DELETE` (admin/owner only, matching `CAMPAIGNS_DELETE`'s own
precedent of deletion needing a higher bar than creation).

**Everyone with `voice_agents:write` sees every agent's credentials in the org** - deliberately, not an oversight: unlike campaigns' `created_by = self` narrowing for
operators (Phase 1's per-creator visibility silo), a voice agent's STT/TTS/LLM/telephony
configuration is *infrastructure*, not personal work product - an operator building a
campaign against a teammate's agent needs to see that it exists and is configured, the
same breadth logic that makes `provider_credentials` itself already org-wide rather than
per-creator. If this turns out wrong once real usage exists, narrowing it later is a
policy change, not a schema change.

**Campaigns keep their own `voice_agent_id`** (nullable FK, per the old doc's §3) -
resolved at run-start, same altitude as `goal_template`. Nothing about campaigns' own
`result_schema`/`outcome_fields` changes - see ADR-5 for why extraction moves, not the
schema that describes what to extract.

### STT/TTS/LLM protocol interfaces - unchanged from the old sketch, confirmed still correct

```python
class SpeechToText(Protocol):
    async def transcribe_stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[TranscriptChunk]: ...

class TextToSpeech(Protocol):
    async def synthesize_stream(self, text: str, *, voice_id: str) -> AsyncIterator[bytes]: ...

class ConversationalLLM(Protocol):
    async def respond(self, history: list[Turn], *, system_prompt: str) -> AsyncIterator[str]: ...
```

Streaming-only, per the old doc's own §2.0 reasoning (nothing in this platform ever has a
pre-recorded file waiting to be transcribed) - unchanged and still correct. **These
protocols are arguably now LiveKit Agents' own plugin interfaces, not a CallFlow
abstraction over them** - worth a real "do we need our own Protocol layer at all, or do
we just depend on `livekit-agents`'s plugin typing directly" question at implementation
time, flagged in §13, not decided here without a working prototype to check it against
(the same "don't design a layer before there's something to test it against" discipline
`VOICE_AGENT_PLATFORM.md`'s own ADR-1 already modelled once).

### The Agentic tab - the actual UI surface, named and specced, not implied

**A completeness review of the first draft found this gap directly: the user's own term
is "Agentic tab," and the first draft only ever said "Agents tab" while never giving it a
route, a nav entry, or a page structure - a data model alone isn't a UI spec.** Corrected
here, using the user's own naming:

- **Route:** `/app/agentic`, a new top-level entry in `apps/web/components/layout/
  app-nav.tsx`'s `PRIMARY_NAV_ITEMS` (alongside Dashboard/Campaigns/Runs/Needs a person/
  Contacts - the existing five-item primary nav list) - not buried under Settings, since
  creating and connecting an agent is now a first-run-blocking action (§9), not an
  occasional configuration change the way Integrations is.
- **Two sections on the page**, matching `VOICE_AGENT_PLATFORM.md` §4's own original
  split, kept because it's still the right shape:
  - **"Your agents"** - a list of this org's `voice_agents` rows (name, kind,
    STT/TTS/LLM provider summary, connected-number status from
    `telephony_provisioning`, which campaigns reference it), each opening an editor:
    name → STT provider+credential → TTS provider+credential → LLM provider+credential
    (+ model, when `llm_provider = 'openrouter'` - ADR-4 point 3) → system prompt →
    voice selection → **Connect a number** (the ADR-2 provisioning flow, surfaced as its
    own step with the pending/provisioning/verified/failed state visible, not hidden
    behind a spinner).
  - **"Prebuilt"** - the CallFlow-operated agent (A4.3), purchasable/usable directly, no
    STT/TTS/LLM configuration beyond a persona pick.
- **Permission-gated per ADR-4's new `Permission.AGENTS_READ`/`AGENTS_WRITE`/
  `AGENTS_DELETE`** - viewer sees the list read-only (matching their pattern everywhere
  else in the product), operator and above can create/edit, admin/owner can delete -
  the nav item itself still shows for every role (read access), consistent with how
  Campaigns/Runs already work rather than hiding the whole tab from viewer.

### New API surface - the routes/models this data model actually needs

**A completeness review also found this gap: the first draft had SQL and RLS but zero
new Pydantic request/response models or route signatures, despite `CLAUDE.md`'s own rule
that "every API response is a declared Pydantic model."** Named here, not fully
implemented (this is still a design doc):

```python
# apps/api/app/api/v1/routes/voice_agents.py - new file, prefix /api/v1/voice-agents

class VoiceAgentIn(BaseModel):
    name: str
    kind: Literal["custom", "prebuilt"]
    stt_provider: str | None = None
    stt_credential_id: UUID | None = None
    tts_provider: str | None = None
    tts_credential_id: UUID | None = None
    llm_provider: str | None = None
    llm_credential_id: UUID | None = None
    llm_model: str | None = None          # required when llm_provider == "openrouter"
    prebuilt_persona: str | None = None   # kind == "prebuilt" only
    system_prompt: str | None = None
    voice_id: str | None = None

class VoiceAgentOut(VoiceAgentIn):
    id: UUID
    org_id: UUID
    telephony_status: Literal["disconnected", "pending", "provisioning", "verified", "failed"]
    created_at: datetime
    created_by: UUID | None

# GET   /api/v1/voice-agents                  - list, AGENTS_READ
# POST  /api/v1/voice-agents                   - create, AGENTS_WRITE
# PATCH /api/v1/voice-agents/{id}               - update, AGENTS_WRITE
# DELETE /api/v1/voice-agents/{id}              - AGENTS_DELETE

class ConnectNumberIn(BaseModel):
    provider: Literal["twilio", "plivo"]
    credential_id: UUID   # an existing provider_credentials row (Settings -> Integrations)

class ProvisioningStatusOut(BaseModel):
    status: Literal["pending", "provisioning", "verified", "failed"]
    last_error: str | None

# POST /api/v1/voice-agents/{id}/connect-number  - AGENTS_WRITE, starts ADR-2's flow,
#      idempotent on repeat calls with the same body (matches campaign_runner.py's own
#      idempotency-key convention) - returns a ProvisioningStatusOut immediately
#      (pending), the actual provisioning runs as a background task per this codebase's
#      existing `BackgroundTasks` pattern (runs.py's own start_run shape)
# GET  /api/v1/voice-agents/{id}/connect-number  - poll ProvisioningStatusOut
```

```python
# apps/api/app/api/v1/routes/messages.py - new file, prefix /api/v1
# (ADR-6)

class ChannelIn(BaseModel):
    kind: Literal["channel", "dm"]
    name: str | None = None       # required for kind == "channel", ignored for "dm"
    member_ids: list[UUID]        # the other participant(s); caller is added automatically

class ChannelOut(BaseModel):
    id: UUID
    kind: Literal["channel", "dm"]
    name: str | None
    member_ids: list[UUID]
    created_at: datetime

class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

class MessageOut(BaseModel):
    id: UUID
    channel_id: UUID
    sender_id: UUID | None
    sender_name: str | None
    body: str
    created_at: datetime
    edited_at: datetime | None

# GET  /api/v1/channels                      - list mine, MESSAGES_READ
# POST /api/v1/channels                      - create (calls create_channel(), ADR-6), MESSAGES_SEND
# GET  /api/v1/channels/{id}/messages        - MESSAGES_READ (RLS narrows to membership regardless)
# POST /api/v1/channels/{id}/messages        - MESSAGES_SEND
```

---

## ADR-5: extraction and completeness checking - a genuinely new module

**Status:** Accepted · **Date:** 2026-08-11

### Context

Confirmed by the internal audit (`a1eaf2a5ad090760c` §2, §4), not assumed: **this feature
does not exist today, not even partially.** A campaign can already mark a result-schema
field `required` (the editor's checkbox, `result_schemas.py`'s `BASE_REQUIRED`/`required`
construction) - but that value is used exactly once, to build the JSON Schema CALL-E was
asked to satisfy, and nothing downstream has ever re-checked `extracted` against it.
Worse, a live public docs page currently states the *opposite* as deliberate philosophy.
This is exactly the feature the user asked for: "did we fill all the fields... if not,
why" - flagged and actionable, not silently absorbed into a generic disposition.

The second, related problem: CALL-E used to hand back its own holistic
`task_completed`/`completion_confidence`/`evidence` judgment as part of every call
response - `triage.py`'s rule 4 (`task_completed is False → ESCALATED`) depends on it,
and it has no equivalent from a raw LiveKit+LLM pipeline unless something is deliberately
built to produce one.

### Decision

**Extraction becomes a CallFlow-owned pipeline step, not a vendor feature - the org's own
configured LLM (via its `voice_agent`) does what CALL-E used to do, driven by a prompt
CallFlow constructs.** Concretely, once a call's transcript is available:

1. CallFlow builds an extraction prompt from the campaign's *existing, unchanged*
   `result_schema` (nothing about how a campaign declares what it wants extracted
   changes) plus the full transcript, and calls the org's configured LLM
   (`ConversationalLLM`/OpenRouter) for a structured JSON response matching that schema -
   the same one-`result_schema`-per-campaign model that already exists, just executed by
   CallFlow's own code instead of CALL-E's. **This call goes through the same
   per-org OpenRouter key ADR-7 provisions** - not a separate credential - so its usage
   is automatically part of that org's metered total, with no separate billing path to
   maintain.
2. The prompt *also* asks for a holistic completion judgment - the direct replacement for
   CALL-E's `task_completed` - so `triage.py`'s rule 4 has something to read again. This
   is a concrete prompt-engineering deliverable, not just plumbing: the extraction prompt
   needs to be designed and tested like any other product surface, not treated as an
   infrastructure detail.
3. **New, pure, no-I/O function** (matching `triage.py`'s own SRP convention -
   `CLAUDE.md` §3 holds this file up as the exemplar precisely because it has no I/O):
   `check_extraction_completeness(extracted: dict, required: list[str]) -> list[str]` -
   returns the required keys that came back missing or null. Lives in `domain/`,
   alongside `triage.py`, tested the same way.
4. **New orthogonal field on `CallOutcome`**: `missing_required_fields: list[str]`
   (empty list = complete; stored as `text[]`, **decided, not left open** - a Postgres
   native array, not `jsonb`, since it's always a flat list of field names with no
   nesting, and `text[]` supports a plain `array_length(...) > 0` filter for the
   escalations-UI badge in §12's A4.1 directly, without a `jsonb` containment operator).
   Orthogonal to `disposition`, not a replacement for it - a call can be `auto_closed`
   (nothing sentiment-wise went wrong) and still be missing a required field, because the
   contact simply never volunteered it.
5. **New triage rule - placed correctly this iteration, after an adversarial review
   caught the first draft's placement was wrong.** The original draft inserted the new
   rule between rule 4 (`task_completed`) and rule 5 (negative-sentiment retry) - but
   rules 5-7 all cover calls that **never had a real chance to provide the data at all**
   (a negative-sentiment call worth one retry, a busy/no-answer/voicemail non-connect, a
   failed/canceled non-connect) - checking those for "missing fields" and escalating
   would override a more useful, more actionable "worth retrying" signal with a less
   useful "fields missing" one, for calls where of course the fields are missing, nothing
   happened yet. **Corrected placement: only check completeness for a call that actually
   reached `completed` status** - i.e., replace the old, unconditional rule 8
   (`status == "completed" → AUTO_CLOSED`) with a completeness-gated pair:

   ```python
   elif status == "completed" and missing_required_fields:
       ESCALATED, reason=f"Missing required fields: {', '.join(missing_required_fields)}"
   elif status == "completed":
       AUTO_CLOSED   # unchanged - only reached once fields aren't missing
   ```

   This reuses the **existing, unmodified** escalations machinery for free (confirmed in
   the audit: `escalations` carries no disposition/reason of its own, everything is
   joined from `call_outcomes` - so a new escalating disposition reason needs zero new
   schema on `escalations` itself), and correctly leaves rules 5-7's own retry/unreachable
   signal as the more informative one for calls that never got a real chance to fill the
   form in the first place.
6. **Extraction's own failure mode - the real gap an adversarial review found, addressed
   directly rather than left implicit.** If the extraction LLM call itself times out, hits
   a rate limit, or returns malformed JSON, the *original* design left `extracted = {}`
   and `task_completed = None`, meaning the call would fall through rule 4 (`None is not
   False`) all the way to the *unconditional* old rule 8 and silently render as
   `AUTO_CLOSED` - a real, false "this call was fine" success state for a call CallFlow
   never actually finished processing, precisely what `CLAUDE.md` non-negotiable #9
   forbids. **Fix**: an extraction failure (after its own bounded retry - transient
   rate-limits/timeouts deserve a couple of attempts, the same instinct
   `campaign_runner.py`'s own `_RETRYABLE_FAILURES` already applies to the dial itself)
   is treated as if *every* required field were missing, with a distinct reason text
   that says so plainly rather than reusing the "fields missing" wording verbatim -
   `ESCALATED, reason="Structured extraction failed - review the transcript directly"` -
   so a human reviewing the escalations worklist can immediately tell "the agent had the
   conversation but didn't get the data" apart from "CallFlow's own extraction step
   broke," which need different follow-up (a coaching/prompt problem vs. an
   infrastructure problem).

### Consequences

- New column on `call_outcomes`: `missing_required_fields text[]` (type now decided, not
  left as an open either/or) - the one real schema addition this ADR needs beyond what's
  already there.
- The result-schema docs page (`apps/web/app/(marketing)/docs/result-schemas/page.mdx`)
  needs rewriting - its current "nothing is required, that's the point" framing directly
  contradicts what's being built. This is not optional cleanup; shipping the feature
  while the public docs describe its absence as a deliberate design choice is exactly the
  kind of "never show a success state for something that did not happen" violation
  `CLAUDE.md` warns against, just in documentation form rather than UI.
- The extraction prompt is now a real, per-org cost (one more LLM call per finished call)
  - already accounted for in ADR-7's billing design (point 1 above), not a separate
    tracking problem, but genuinely additive to the per-call cost model in ADR-3's worked
    example, which only totalled WebRTC/SIP minutes - update that estimate once a real
    extraction-prompt token count exists to measure against.
- `AttemptSummary`/`attempts[]` (modelled on CALL-E's own redial-within-one-task
  semantics) likely doesn't map cleanly onto a LiveKit-based call, where each dial is
  plausibly its own room/session rather than a nested "attempt" - flagged in §13, not
  resolved here, since it needs a working prototype to know what LiveKit's own retry
  semantics actually look like.

---

## ADR-6: internal team chat

**Status:** Accepted · **Date:** 2026-08-11

### Context

Confirmed by the internal audit (`a1288fd1d5fc80432`): **nothing chat-shaped exists in
this repo today** - no table, no route, no component, across a full-repo search. The
"already planned" chat system left zero trace here; it must be designed from scratch,
following patterns this codebase has already proven work (per-command RLS policies,
`SECURITY DEFINER` helpers where a policy would otherwise need to see across tables it
can't directly query, the generic `useOrgRealtime` hook).

**The one finding that must not be treated as optional:** `useOrgRealtime`'s `org_id`
filter is confirmed to be a bandwidth optimisation, evaluated server-side before an event
is sent - **not the security boundary**. Both the hook's own docstring and the existing
Realtime migrations state this explicitly. For escalations/share_requests this doesn't
matter (every org member is allowed to know *something* exists, even if role/ownership
narrows the content). For a DM or a private channel, it matters completely: **the
`messages_select`/`channels_select` RLS policies themselves must check channel
membership**, or every teammate would receive every DM's Realtime event (the JS-side
`org_id=eq.` filter would still show it to them, since RLS - not the filter - is what
Postgres Changes actually authorises against).

### Decision - data model

```sql
create table public.channels (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organisations(id) on delete cascade,
  kind text not null check (kind in ('channel', 'dm')),
  name text,                      -- null for kind = 'dm'
  created_by uuid references public.users(id) on delete set null,
  created_at timestamptz not null default now()
);

create table public.channel_members (
  channel_id uuid not null references public.channels(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  joined_at timestamptz not null default now(),
  primary key (channel_id, user_id)
);

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organisations(id) on delete cascade,  -- denormalised,
                                          -- same reasoning `escalations.org_id` already
                                          -- uses despite being derivable via channel_id -
                                          -- direct RLS/index without a join.
  channel_id uuid not null references public.channels(id) on delete cascade,
  sender_id uuid references public.users(id) on delete set null,
  body text not null,
  created_at timestamptz not null default now(),
  edited_at timestamptz,
  deleted_at timestamptz          -- soft delete: a hard-deleted row re-checked by RLS on
                                   -- a lagging Realtime event is exactly the kind of
                                   -- edge case worth avoiding for free.
);
```

**RLS - corrected after adversarial review caught a real recursion bug in the first
draft.** The first draft's `channel_members_select` queried `public.channel_members`
from inside a policy *on* `public.channel_members` (aliased `cm2`, but still the same
table) - exactly the shape `ISSUES.md` already documents twice as a real, reproduced bug:
`initial_schema`'s own comment ("a policy on memberships that queried memberships
directly would recurse infinitely") and iteration 28's `#84` (`runs_select`/
`escalations_select` recursing through each other). Worse, that draft's `channels_select`
queries `channel_members`, and `channel_members_select`'s admin/owner branch queried
`channels` right back - the identical *cross-table* mutual-recursion `#84` already hit
once. **Both cycles are fixed the same way this codebase already fixed `#84`**: a
`SECURITY DEFINER` helper that resolves membership without re-triggering RLS internally,
the same pattern `is_org_member()`/`has_org_role()` already use.

```sql
create or replace function public.is_channel_member(target_channel uuid)
returns boolean language sql stable security definer set search_path = public, pg_temp
as $$
  select exists (
    select 1 from public.channel_members
    where channel_id = target_channel and user_id = public.current_user_id()
  );
$$;

create or replace function public.channel_org_id(target_channel uuid)
returns uuid language sql stable security definer set search_path = public, pg_temp
as $$
  select org_id from public.channels where id = target_channel;
$$;

alter table public.channels enable row level security;
alter table public.channels force row level security;
alter table public.channel_members enable row level security;
alter table public.channel_members force row level security;
alter table public.messages enable row level security;
alter table public.messages force row level security;

create policy channels_select on public.channels for select
  using (public.is_channel_member(id));

create policy channel_members_select on public.channel_members for select
  using (
    public.is_channel_member(channel_id)
    or public.has_org_role(public.channel_org_id(channel_id),
                            array['owner','admin']::public.org_role[])
  );

create policy messages_select on public.messages for select
  using (public.is_channel_member(channel_id));

create policy messages_insert on public.messages for insert
  with check (sender_id = public.current_user_id() and public.is_channel_member(channel_id));

-- Adding a teammate to an existing channel (not the creation path - see below,
-- creation goes through create_channel() to avoid the RETURNING/#85 trap).
create policy channel_members_insert on public.channel_members for insert
  with check (
    public.is_channel_member(channel_id)
    and public.is_org_member(public.channel_org_id(channel_id))
  );

grant select, insert on public.channels, public.channel_members, public.messages
  to authenticated;
```

Both helper functions call into `channel_members`/`channels` themselves, but - the same
reasoning `is_org_member()`'s own migration comment already gives - "running inside a
`SECURITY DEFINER` function bypasses RLS and breaks the cycle," since the function body
runs with the definer's privileges, not the caller's RLS-checked session. This is not a
new pattern; it's the third table in this codebase to need it (`memberships`, then
`runs`/`escalations`, now `channels`/`channel_members`) - worth noting in case a fourth
one benefits from recognising the shape earlier next time.

**No admin-approval gate on creating a DM/channel or adding yourself to one you were
invited into** - unlike `share_requests`' owner-must-approve model, chat membership is
opt-in social structure, not a resource grant. **Creation goes through a `SECURITY
DEFINER` function, not a plain client-side `INSERT ... RETURNING`** - the same
architectural lesson `#85` (this session's own campaign-clone bug) already forced once:
a caller inserting a channel isn't yet a `channel_members` row when that insert's
`RETURNING` clause gets checked against `channels_select`, which - correctly - requires
membership. `create_organisation()` already solves the identical shape (insert the org,
seat the first member, atomically, bypassing RLS for that one operation); this reuses it:

```sql
create or replace function public.create_channel(
  target_org uuid, target_kind text, target_name text, member_ids uuid[]
)
returns uuid language plpgsql security definer set search_path = public, pg_temp as $$
declare new_channel_id uuid;
begin
  if not public.is_org_member(target_org) then
    raise exception 'not a member of this organisation';
  end if;
  insert into public.channels (org_id, kind, name, created_by)
    values (target_org, target_kind, target_name, public.current_user_id())
    returning id into new_channel_id;
  insert into public.channel_members (channel_id, user_id)
    select new_channel_id, unnest(member_ids || array[public.current_user_id()]);
  return new_channel_id;
end;
$$;
```

Adding someone to an *existing* channel later is a plain, RLS-governed
`channel_members` insert (`with check (is_channel_member(channel_id))` -
plus `is_org_member` on the invitee, checked in `channel_members_insert`) - safe as a
regular insert precisely because the app never asks for that insert's row back via
`RETURNING`, so the `RETURNING`-triggers-`SELECT`-policy trap `#85` hit doesn't apply
there the way it would for the channel's own creation.

**Permissions:** `Permission.MESSAGES_READ` (every role, including viewer - opening the
chat surface at all is a breadth question the same way viewing the dashboard is, not a
resource-visibility one) and `Permission.MESSAGES_SEND` (operator and above - viewer
stays read-only everywhere, unchanged from the existing product philosophy). **Resource
visibility itself is entirely `channel_members`, not role** - a viewer who isn't a member
of a given DM cannot see it, exactly the same way an operator who isn't assigned an
escalation can't see it either; role governs whether the feature surface exists for you
at all, membership governs which specific rows you get. This is the identical two-layer
split the audit confirmed `escalations` already uses (role for breadth, a row-level
relationship for narrowing) - not a new pattern, an application of the existing one.

**Realtime:** reuse `useOrgRealtime('messages', orgId, refetch)` and
`useOrgRealtime('channels', orgId, refetch)` **unchanged** - the hook already accepts an
arbitrary table name. The org-level subscription is still correctly *scoped* down to only
the caller's own channels once RLS narrows the subsequent refetch query - no frontend
hook work needed, only getting the RLS policies above right.

### Consequences

- Two new migrations (tables+RLS+realtime-publication, following the `share_requests`
  migration as the literal template) and two new frontend surfaces (a channel list +
  message view, structurally closer to the existing Escalations worklist pattern than to
  anything net-new).
- `TEAM_COLLABORATION_ROADMAP.md` Phase 3 (notifications) is not a prerequisite for chat
  and chat is not a prerequisite for it, but they're natural to schedule adjacently -
  both need the same per-user (not per-org) Realtime-scoping thinking, and a message-
  received notification is an obvious future Phase-3 notification `type` once both exist.
  Not bundled into this pivot's phases (§12) unless the team wants to pull it forward.

---

## ADR-7: OpenRouter as the LLM marketplace + billing model

**Status:** Partially accepted - the LiveKit-integration half is confirmed; the
billing/margin half is genuinely open, see §13 · **Date:** 2026-08-11

### What's confirmed

- OpenRouter is natively wireable into a LiveKit Agents pipeline via the `with_openrouter()`
  factory on the OpenAI plugin (ADR-4) - this part needs no further research to start
  building against.
- Streaming is supported (`stream: true`, SSE) - required for conversational latency,
  confirmed present in OpenRouter's own docs (task `wlbyf1fxr` source list included
  `openrouter.ai/docs/api/reference/streaming`, though the specific claim about
  usage-data-in-the-final-chunk did not make it into this round's confirmed-findings set
  - re-check at implementation time, see §13).
- Per-request model switching is a `model` field on the request - this is why ADR-4 added
  `llm_model` to the `voice_agents` schema; without it, "an org's agent uses OpenRouter"
  is underspecified.

### What's now confirmed (single-pass follow-up, task `a4dd2040c00553c37`, fetched 2026-08-11)

- **OpenRouter adds no per-token markup of its own**: its FAQ states directly, "We never
  mark-up the pricing of the underlying providers, and you'll always pay the same as the
  provider's listed price." OpenRouter's own revenue is a **credit-purchase fee** (5.5%,
  minimum $0.80, via Stripe; 5% via crypto) charged when credits are bought, not a
  per-request markup. This means whatever CallFlow charges an org on top is the *entire*
  margin on the LLM leg - there's no vendor markup already baked in to account for.
- **A real, programmatic reseller mechanism exists**: OpenRouter's provisioning-API-keys
  feature (`POST /api/v1/keys`) is explicitly documented for a *platform* issuing "unique
  API keys for each customer instance" - each key gets its own spend `limit` with a
  `limitReset` cadence (daily/weekly/monthly), can be disabled, and exposes
  `usage`/`usage_daily`/`usage_weekly`/`usage_monthly`/`limit_remaining` readable per key.
  This is precisely "we will charge them accordingly" made concrete: **one OpenRouter key
  provisioned per CallFlow org** (not one shared key for the whole platform), CallFlow
  reads back that org's real usage from OpenRouter directly, and applies its own markup
  when billing the org - no separate in-house token-counting/reconciliation system needed
  to know what an org actually consumed.
- **Streaming usage data is not a documented hard guarantee.** The only evidence found is
  an SDK code comment ("Final chunk includes usage stats"), not a formal contract in
  OpenRouter's own docs. Do not bill solely off the last streamed chunk without a
  fallback - reconcile periodically against the provisioning API's own `usage` fields
  (confirmed reliable above), which exist for exactly this reason.

### Decision

**Provision one OpenRouter API key per organisation** (via the provisioning-API keys
feature, called from `apps/api` using CallFlow's own OpenRouter management key - itself
stored the same way every other vendor secret is, via `provider_credentials` or a
dedicated platform-level secret, not per-org `provider_credentials` since this key isn't
the org's own credential, it's one CallFlow issues *to* them), with a `limit` set from
whatever the org's plan/billing model allows, and read `usage` back periodically (a
scheduled job, not just trusting the final SSE chunk) as the source of truth for what to
charge. CallFlow's own markup percentage/model is a pricing decision for later (§13 -
genuinely a business call, not an engineering one), but the *mechanism* to meter and cap
per-org usage is now fully specified and unblocked to build.

**Also record locally** (per-org, per-`voice_agent_id`) the same usage figures pulled
from OpenRouter, the same way `member_credit_allocations`/`used_today` already track
call-volume - correctness-through-redundancy against OpenRouter's own numbers, not a
replacement for them.

**Both legs of LLM usage go through this same per-org key - stated explicitly, since an
adversarial review found the first draft only really discussed the conversational leg.**
ADR-5's post-call extraction step (the structured-extraction + completion-judgment call)
is *also* billed through the org's own provisioned OpenRouter key, not a second,
separately-tracked credential - so the usage/limit/markup mechanism above already covers
it without a second metering path to build or reconcile. The two legs are
distinguishable in CallFlow's own local usage ledger by tagging each recorded usage row
with which pipeline step produced it (conversational turn vs. post-call extraction) -
useful for understanding cost composition per call, not required for billing correctness,
since both draw from the same capped, metered key regardless.

---

## 9. The revised call-routing model

With CALL-E gone entirely (not kept as a zero-setup fallback, per the user's explicit,
unconditional removal decision), `VOICE_AGENT_PLATFORM.md` §3's four-branch decision tree
collapses to one real path - there is no more "org configured nothing" branch that
quietly degrades to a working default:

```
start_run(campaign_id, contacts)
  │
  ├─ campaign has no voice_agent_id, OR the agent has no verified connected number
  │    → reject at run-start with an honest, specific error ("This campaign needs a
  │      voice agent with a connected phone number before it can start a run" - never a
  │      silent fallback, since there is nothing left to fall back to)
  │
  └─ campaign's voice_agent has a verified connected number (Twilio or Plivo, ADR-2)
       → CallFlow's backend calls LiveKit's CreateSIPParticipant to originate the call
         via the org's own trunk (ADR-2), the LiveKit Agents worker (ADR-1) joins the
         room running the agent's configured STT/TTS/LLM, the conversation happens,
         the transcript persists, extraction + completeness checking runs (ADR-5),
         triage() (revised) assigns a disposition, an escalation is created if needed -
         unchanged downstream of that point.
```

**Direct consequence for onboarding:** a brand-new organisation cannot place a single
call until it has configured at least one voice agent *and* connected at least one
verified number - a materially heavier first-run requirement than today's
"nothing to configure, CALL-E just works." This needs its own honest empty-state on the
Campaigns/Runs pages (not a blocking modal like the mandatory org-name gate - a new
signup should be able to explore the rest of the dashboard before being forced through
agent setup), and should be treated as a first-class onboarding design problem in its own
right in Phase 1 (§12), not an afterthought once the backend plumbing exists.

---

## 10. Market differentiation - what to actually build, evidence-graded

From the competitive deep-research pass (task `w1gib7vw2`) - graded by how well the
underlying claim survived adversarial verification, not presented as one flat list of
equally-certain facts.

### Confirmed table stakes - do not market these as breakthroughs

- **BYO telephony via Twilio/SIP is already real on at least two major competitors**:
  Retell supports broad SIP-trunk BYO (Twilio, Telnyx, Vonage, "any other SIP-trunk-
  capable provider," high confidence, primary-doc-verified); Vapi has a dedicated
  BYO-Twilio path (`byo-phone-number` provider + `byo-sip-trunk` credential, plus a
  simpler dashboard import flow). **The whole premise of "bring your own number" is
  parity, not differentiation** - the differentiation has to be in what's layered on top
  (below), and in doing the provisioning itself better (ADR-2's automation decision).

### Confirmed real white space - evidence-graded high confidence

**The specific combination CallFlow is building - granular per-resource permissions,
peer-to-peer resource sharing, per-teammate credit/usage tracking, and internal team
chat, layered on a genuinely open BYO-provider voice stack - is not offered as a bundle
by any surveyed competitor with surviving evidence:**

- Vapi's team collaboration is real but shallow: shared workspaces, teammate invites,
  coarse roles (Editor/Admin, later Viewer) - no granular per-permission scopes, no
  peer-to-peer resource sharing, no per-teammate credit attribution.
- Retell's three-tier RBAC (Admin/Developer/Member) makes **Member strictly read-only** -
  "Cannot create, edit, or delete resources," barred from billing entirely. No
  resource-sharing mechanism of any kind.
- **No competitor has any documented per-seat/per-teammate credit or usage attribution**
  at all (confirmed absent on Retell specifically; not found - not "confirmed absent," a
  real gap in the evidence - for the others).
- **No competitor offers a genuine LLM marketplace/aggregator.** What exists is
  fragmented: Vapi (broadest - BYOK plus a curated provider list plus a self-hosted
  escape hatch, still Vapi-mediated selection, not an open router), Retell (a fixed,
  vendor-curated dropdown of ~15-20 named models - real choice, not an aggregator),
  Bland (zero choice, two proprietary bundled tiers only). **Bolna is the closest
  analog** - confirmed per-language STT/TTS switching, and a LiteLLM-backed multi-LLM
  integration list that *includes OpenRouter itself as one option* - but frames itself as
  an orchestration/infra layer, not a customer-facing marketplace UI; nobody has built
  "pick any OpenRouter-listed model from a dropdown, we handle the billing" as an actual
  product surface.
- **Internal team chat was not found, positively or negatively, for any competitor** -
  the research question assumed its absence rather than confirming it; treat this as a
  real blind spot (§13), not proof no competitor has it.

### Real, sourced pain points to design against (not speculation)

The research question's "what do sales teams actually complain about" half initially came
back empty (refuted 0-3 on the first pass); a single-pass follow-up (task
`a4dd2040c00553c37`) found real evidence by going to G2/Trustpilot directly instead of
comparison blogs - and explicitly discarded several fabricated-sounding Hacker News quotes
an earlier internal check couldn't verify against HN's own search API, rather than
reporting them. What survived:

- **Latency is the #1 named complaint on Vapi specifically**: "sometimes the latency is
  within 800-1000ms and sometimes it goes up to 4-5s" (G2). This is a direct argument for
  ADR-3's region-pinning decision (`ap-south` for India traffic) and for treating latency
  as a measured, monitored product metric from Phase 1 onward, not an afterthought.
- **Reliability/support, not just features, drives real damage claims**: a Trustpilot
  review describes "$50k in damages" from downtime triggered by an unannounced UI/API
  change. Directly relevant to how CALL-E's own instability triggered this entire pivot -
  the lesson generalises: whatever CallFlow ships needs a visible status/incident
  communication practice, not just working code (this repo already has a `/status` page
  and `DEPLOYMENT.md` - extend that discipline to the new voice-agent stack specifically).
- **Retell reviewers want better interruption handling and lack international-number
  support** - the second point is worth noting given CallFlow's own India+US target
  market spans exactly the kind of "international" telephony some competitors apparently
  don't handle well.
- **A real, practitioner-reported LiveKit+Twilio integration failure mode exists**
  (GitHub issue `livekit/agents#3605`, surfaced during the technical research pass,
  task `wlbyf1fxr`): an inbound Twilio call bridges to a LiveKit agent, the greeting
  plays, then the agent goes silent with no further audio - a real, documented gotcha in
  exactly the integration this plan is building, worth a specific test case in Phase 1
  rather than discovering it live.

### Candidate breakthroughs this plan should actually pursue, ranked

1. **The bundle itself** (permissions + sharing + per-teammate credits + chat + open BYO
   voice stack) - confirmed absent on the two competitors with complete surviving
   evidence (Vapi, Retell); **genuinely unknown, not confirmed absent, for Synthflow,
   Air.ai, Cognigy, Vocode and Bland** (§13 item 6) - those four simply weren't checked
   on this axis. The claim that stands without qualification is narrower and still
   strong: *the two most fully-documented competitors* don't have this combination. This
   is already what §12 schedules; the differentiation is in finishing all of it, not
   adding something new.
2. **A real, customer-facing model marketplace on top of OpenRouter** (browse/pick from
   OpenRouter's actual model list in the Agentic tab, not a fixed curated dropdown) -
   confirmed nobody does this today, and ADR-7 already specifies the metering mechanism
   to make it billable per org.
3. **Automated SIP-trunk provisioning** (ADR-2) instead of a setup-guide-and-hope-they-
   follow-it flow - not confirmed as something any competitor's own docs describe doing.
4. **Visible latency/reliability as a monitored, marketed property**, directly answering
   the #1 sourced complaint against the closest analog competitor (Vapi) - a genuine,
   evidence-backed positioning angle, not a guess.

---

## 11. CALL-E removal - the exact checklist

From the internal removal audit (`a8189f9188a09af17`) - graded by disposition, not one
flat "delete everything" instruction, since some of this survives unchanged.

### Delete outright - no replacement needed, the concept itself no longer exists

- `apps/api/pyproject.toml` - the `calle-ai>=0.6.0` dependency pin.
- `apps/api/app/integrations/voice/engine.py` (whole file) - the vendor SDK boundary
  itself. Its *role* (sole importer of a vendor SDK, aliased on the way in) is the
  pattern the LiveKit-facing code in ADR-1 should replicate, not anything in its body.
- `apps/api/app/api/v1/routes/webhooks.py` (whole file) - CALL-E's own event-delivery
  webhook. LiveKit/Twilio/Plivo have entirely different event-delivery mechanisms; there
  is no "swap the implementation" version of this file, only a differently-shaped
  successor if one turns out to be needed once the LiveKit worker's own event model is
  understood.
- `apps/api/tests/test_engine.py`, `test_webhooks.py`, `test_run_events.py` - test
  CALL-E SDK types and routes directly; delete alongside the code they test.
- CALL-E env vars: `CALLE_API_KEY`, `CALLE_DEFAULT_REGION`, `CALLE_DEFAULT_LANGUAGE`
  (`.env.example`, `core/config.py:45-47`), `CALLFLOW_WEBHOOK_SECRET` (`config.py:64-74`,
  `require_api_key()` at :155-161) - though `CALLFLOW_PUBLIC_API_URL` may be reused for
  whatever new webhook/callback target the LiveKit worker needs, not deleted blind.

### Rewrite from scratch - the concept survives, the implementation cannot

- `apps/api/app/domain/outcome_extraction.py` (whole file) - every extraction function
  parses CALL-E's specific `recipients[0].attempts[].transcript_turns[]` shape. A LiveKit
  agent's transcript comes from the agent runtime's own persistence, not this shape. Only
  the *pipeline pattern* (`_resolve_outcome` → `triage()`) is worth keeping as a template,
  per ADR-5's own extraction step replacing what this file used to do.
- `apps/api/app/api/v1/routes/runs.py:493-552` (`get_call_events`/`DeveloperEventOut`) -
  proxies CALL-E's developer event log; rewrite only if LiveKit room events turn out to
  need an analogous per-call log surface, not assumed necessary.
- `apps/api/tests/test_orchestrator.py` - the safety/credit/retry *assertions* are
  reusable in spirit (and several already are, confirmed unrelated to CALL-E per the
  credit-enforcement work already shipped this session); every fixture using
  `EngineAPIError`/`EngineConnectionError` needs a new adapter's own exception types.

### Keep the shape, swap the guts - no vendor-specific rewrite needed

- `apps/api/app/integrations/voice/protocol.py` - `VoiceProvider`/`VoiceCapability` stays
  as the pattern precedent (ADR-1's own "What does NOT change" section).
- `apps/api/app/services/campaign_runner.py` - the credit-reservation lock, suppression
  check, concurrency semaphore, and idempotency-key pattern are vendor-agnostic and
  reused unchanged; only the CALL-E dial/poll loop itself (`gateway.start_call()`,
  `_poll_until_done()`, `_await_settled_duration()`) is void under LiveKit's
  event-driven (not polling) model.
- `apps/api/app/domain/entities.py` - `DialFailure` is already vendor-neutral and
  survives untouched. `CallOutcome.task_completed`/`completion_confidence_*`/`evidence`
  and `AttemptSummary` are CALL-E-task/recipients/attempts-shaped; the columns can stay
  (ADR-5 repopulates `task_completed`'s role via the new extraction prompt) but
  `AttemptSummary`'s specific "redial within one call task" semantics likely doesn't
  map onto LiveKit (flagged in §13, not resolved without a working prototype).
- `apps/api/app/domain/triage.py` - the precedence-ordered `triage()` logic is fully
  vendor-neutral (rules 1-3, 5-9); only rule 4 (`task_completed`) needs its input
  signal replaced, not the function's own structure (ADR-5).
- Historical migrations (`202608091200_calle_webhook_run_lookup.py`,
  `202608091600_call_outcome_completion_signals.py`) - **never edited, per this repo's
  "nothing is deleted, only re-statused" convention** (`ISSUES.md`'s own stated policy).
  A follow-up migration drops/repoints `lookup_run_owner_for_webhook()` once
  `webhooks.py` is deleted; the historical record of why the columns exist stays as-is.
- `provider_credentials` - unchanged in shape, only its `check` constraint widens
  (ADR-4) - it was already generic enough for Sarvam/OpenRouter/LiveKit secrets without
  a new column.

### Documentation and gap-map entries that close out, not "re-fix"

- `ISSUES.md` #52-#63, #80, #82 - already **FIXED**, but reference CALL-E's real payload
  shape throughout; moot once removed, not bugs to revisit.
- `SYSTEM.md` F17 ("Voice provider abstraction," ⚠️ Partial - "no second adapter") is the
  one genuinely open, CALL-E-framed gap-map item this entire pivot replaces outright.
- `SYSTEM.md` F20 ("Call execution... polling only, no webhooks") is already stale prose
  (webhooks shipped iteration 18) and becomes moot regardless of this pivot.
- `SYSTEM.md`'s API reference entry for `POST /api/v1/webhooks/calle/{secret}` becomes
  dead documentation the moment §1's webhook file is deleted.

---

## 12. Phased roadmap

**Two independent tracks, not one sequential list.** Track A (the voice-agent pivot
itself) and Track B (internal team chat) share no code, no schema, and no data model -
chat touches roles/RLS/Realtime, the voice pivot touches telephony/media/LLM extraction.
**Track B can start immediately and run the entire time Track A is in progress** - there
is no dependency in either direction. This is the single biggest parallelisation
opportunity in this plan, and scheduling chat "after" the voice work (as a naive reading
of the user's own message order might suggest) would waste it for no reason.

### Track A - the voice-agent pivot

#### Phase A0 - CALL-E removal + an honest "calling is unavailable" state

*Ships:* the unconditional removal decision, made real, without a single silent failure
mode anywhere a call-start action exists.

| Module | What | Depends on | Parallel with |
|---|---|---|---|
| A0.1 | Delete CALL-E code (§11 "delete outright" list) | - | A0.3, A0.4 |
| A0.2 | Strip/stub `campaign_runner.py`'s CALL-E-specific calls so the app still boots (keep everything ADR-1 marks reusable) | A0.1 | - |
| A0.3 | Update `ISSUES.md`/`SYSTEM.md` gap-map entries (§11's documentation list) | - | A0.1, A0.4 |
| A0.4 | **Every** "Start a run" entry point (composer, dashboard shortcuts) shows an honest `NotWiredNotice` - CLAUDE.md non-negotiable #9 is not optional here | - | A0.1, A0.3 |

**A0.2 is the one real sequencing constraint in this phase** - everything else is
parallelisable across two or three people/agents in the same day.

#### Phase A1 - first real call, one org, one provider, one STT/TTS/LLM vendor

*Ships:* the actual proof that the new architecture works end-to-end - Sarvam STT/TTS,
OpenRouter LLM, one Twilio number, one test org. This is the phase that matters most for
closing A0's calling-capability gap, and it should be resourced accordingly.

| Module | What | Depends on | Parallel with |
|---|---|---|---|
| A1.1 | `voice_agents` table + `provider_credentials` constraint widening (ADR-4) | A0.1 | A1.5 |
| A1.2 | Twilio SIP trunk provisioning (ADR-2) - **manual/semi-manual for this phase**, full automation is A2.2 | A1.1 | A1.3 |
| A1.3 | `apps/voice-runtime/` skeleton: LiveKit Agents worker, Sarvam STT/TTS plugin, `with_openrouter()` LLM wiring (ADR-1, ADR-4) | A1.1 | A1.2, A1.5 |
| A1.4 | Outbound call origination from `apps/api` (`CreateSIPParticipant`, replacing `campaign_runner.py`'s old dial call) | A1.2, A1.3 | - |
| A1.5 | Extraction + completeness pipeline (ADR-5) - **fully independent of LiveKit**, buildable and testable against a hand-supplied transcript before any real call exists | A0.2 | A1.1, A1.2, A1.3 |
| A1.6 | Agentic tab (frontend, minimal - route, nav entry, "Your agents" section per ADR-4): create one custom agent, connect one number | A1.1 | A1.2, A1.3, A1.5 |
| A1.7 | End-to-end integration: one real call through the full pipeline | A1.4, A1.5, A1.6 | - |

**A1.5 deserves explicit flagging as an early, parallel task** - it's pure domain logic
(a prompt + a comparison function), needs no LiveKit account, no Twilio number, and no
working media runtime to start, and it's directly on the user's own explicit
requirements list (the "did we get all the fields" feature). Do not schedule it last
just because it's described after the telephony work in this document's own ADR order.

#### Phase A2 - Plivo + provisioning automation

*Ships:* the second telephony provider, and ADR-2's automated (not manual) connect-a-
number flow for both.

| Module | What | Depends on | Parallel with |
|---|---|---|---|
| A2.1 | Plivo SIP trunk provisioning (mirrors A1.2) | A1.7 | A2.2 (Twilio half) |
| A2.2 | Automate ADR-2 steps 2-3 (CallFlow calls Twilio's/Plivo's own REST API on the org's behalf) - Twilio half can start once A1.2 exists; Plivo half needs A2.1 | A1.2 (Twilio half) / A2.1 (Plivo half) | A2.1 |
| A2.3 | "Connect a number" UI state machine (pending → provisioning → verified → failed) | A2.2 | - |

#### Phase A3 - the LLM marketplace + a second STT/TTS vendor + billing

*Ships:* differentiator #2 from §10 (a real, customer-facing OpenRouter model picker,
not a fixed dropdown), the metered billing mechanism from ADR-7, and the second adapter
per slot that proves BYO isn't a single-vendor lie (`VOICE_AGENT_PLATFORM.md`'s own rule,
still correct).

| Module | What | Depends on | Parallel with |
|---|---|---|---|
| A3.1 | OpenRouter provisioning-API integration - one key per org (ADR-7) | A1.7 | A3.3, A3.4 |
| A3.2 | Usage metering + periodic reconciliation job | A3.1 | A3.3, A3.4 |
| A3.3 | Agentic tab - real OpenRouter model browser/picker | A1.6 | A3.1, A3.2, A3.4 |
| A3.4 | Second STT/TTS adapter (e.g. Deepgram and/or ElevenLabs, per `VOICE_AGENT_PLATFORM.md` §2.2's own first+second table) | A1.3 | A3.1, A3.2, A3.3 |

**A3.1/A3.2 and A3.3/A3.4 are two genuinely independent pairs** - a billing engineer and
a frontend+integrations engineer (or two agents) can work this phase fully in parallel.

#### Phase A4 - the "Needs a person" tab keeps its name, route, and existing job - it gains one new capability

*Ships:* **the "Needs a person" tab (`/app/escalations`) is not renamed, not restructured,
and not replaced - it continues doing exactly what it does today** (sentiment-driven
escalation, human-request detection, frustration detection, the existing worklist,
assign/resolve) **and additionally surfaces the one new signal this whole pivot was asked
to add**: whether the fields the campaign's creator wanted extracted were actually filled
in, and if not, why - visibly distinct from a sentiment-driven escalation, not folded
into it anonymously. Also ships the CallFlow-operated prebuilt agent
(`VOICE_AGENT_PLATFORM.md`'s own "falls out of BYO almost for free" observation, still
true).

| Module | What | Depends on | Parallel with |
|---|---|---|---|
| A4.1 | "Needs a person" worklist: filter/badge distinguishing "missing required fields" (ADR-5's new escalation reason) from sentiment-driven escalations - same page, same route, one new visual distinction | A1.5 | A4.2, A4.3 |
| A4.2 | Campaign editor: surface "N required fields" more prominently now that they're enforced, not decorative | A1.5 | A4.1, A4.3 |
| A4.3 | Prebuilt agent (CallFlow's own STT/TTS/LLM credentials through the same runtime, `kind = 'prebuilt'`) | A1.3, A3.4 | A4.1, A4.2 |

### Track B - internal team chat (ADR-6)

*Ships in parallel with all of Track A - zero shared code or schema.*

| Module | What | Depends on | Parallel with |
|---|---|---|---|
| B1 | `channels`/`channel_members`/`messages` migration + RLS (ADR-6's exact policies) | - | B3 |
| B2 | Frontend: channel list + message view (structurally close to the Escalations worklist pattern) - build against the API contract in ADR-4's new-API-surface section from day one, against a mocked response; swap to the real endpoint once B1 lands | - (mocked contract) for the UI itself; needs B1 only for real, non-mocked data | B1, B3 |
| B3 | `Permission.MESSAGES_READ`/`MESSAGES_SEND` wiring | B1 | B2 |

### Suggested allocation if running this with parallel subagents/engineers today

Given the dependency graph above, a genuinely parallel kickoff looks like: **one track on
A0 (removal + honest empty states), one track on A1.5 (extraction/completeness - no
external dependency at all), one track on B1-B3 (chat, entirely independent)** - three
concurrent workstreams from day one with zero contention, converging on A1's end-to-end
test once A0 and the LiveKit/Twilio plumbing (A1.1-A1.4) land.

---

## 13. Open items requiring a vendor conversation or a follow-up pass

Named explicitly so none of these get silently assumed away - each one blocks a specific,
named decision, not "more research would be nice":

1. **LiveKit Cloud's agent-session overage rate** (ADR-3) - the primary pricing page
   didn't state it; only third-party summaries did, and those weren't independently
   confirmed. Blocks: finalising ADR-7's exact per-call cost model. Action: fetch
   `livekit.com/pricing` directly again at implementation time, or ask LiveKit sales.
2. **CallFlow's own markup percentage on OpenRouter usage** (ADR-7) - the *mechanism*
   is fully specified (provision a key per org, meter via the provisioning API); the
   *number* is a business/pricing decision, not an engineering one, and deliberately
   left open here.
3. **`AttemptSummary`/`attempts[]`'s fate** (ADR-4, §11) - CALL-E's own "redial within
   one call task" model may not map onto LiveKit, where each dial is plausibly its own
   room/session. Needs a working A1 prototype to answer with real data, not guessed.
4. **Whether `SpeechToText`/`TextToSpeech`/`ConversationalLLM` need a CallFlow-owned
   `Protocol` layer at all**, versus depending on `livekit-agents`'s own plugin typing
   directly (ADR-4) - flagged, not decided, for the same "don't design an abstraction
   before there's something real to check it against" reason `VOICE_AGENT_PLATFORM.md`'s
   own ADR-1 already modelled once.
5. **Whether Twilio's inbound no-username/password limitation needs a dedicated
   TwiML-serving endpoint on CallFlow's own side** (ADR-2) - confirmed as a real
   asymmetry between the two adapters; the exact shape of the workaround needs
   implementation-time investigation against a real Twilio trunk, not design-time
   guessing.
6. **Do Synthflow, Air.ai, Cognigy, or Vocode have anything resembling granular RBAC,
   resource sharing, per-seat billing, or team chat?** (§10) - no evidence either
   confirms or refutes this for the current competitive survey; a real blind spot in
   the "confirmed white space" claim, not fatal to it (Vapi and Retell alone already
   support the conclusion), but worth closing before repeating the claim publicly.
7. **Is Bolna's marketed "per-locale LLM switching" actually implemented and
   documented**, or is it aspirational language from a funding-round interview that
   outpaces the shipped product? (§10) - bears on how close the nearest competitor
   analog to CallFlow's own OpenRouter-marketplace idea actually is.
8. **A genuine, non-vendor-sourced latency benchmark for India-originating SIP/voice
   traffic** (ADR-3) - the only figure found is LiveKit's own blog post; treat the
   ~1.67s number as directional until A1's own working prototype produces a real,
   measured number against actual Sarvam+OpenRouter+Twilio/Plivo traffic, not a
   different vendor combination.

---

## 14. Explicitly out of scope for V1

Named so a missing feature doesn't get mistaken for an oversight later, matching this
codebase's own established convention (`CAPABILITIES.md`'s "What isn't built yet"
section, `TEAM_COLLABORATION_ROADMAP.md`'s "explicitly out of scope" list):

- **A self-hosted LiveKit deployment** - ADR-3's decision is Cloud-first; self-hosting is
  a real, available future option, not a V1 task.
- **A third telephony provider beyond Twilio/Plivo** - the user named exactly these two;
  a third (e.g. Telnyx, confirmed cheaper in the team's own CPaaS research doc) is a
  future consideration, not scoped here.
- **A general audit log or notification inbox** (`TEAM_COLLABORATION_ROADMAP.md` Phase 3,
  still unbuilt) - chat (Track B) does not require it, and it is not bundled into either
  track's phases above, though scheduling it adjacent to chat once both exist is a
  reasonable future call.
- **CallFlow's own markup percentage/pricing tiers for OpenRouter usage or per-minute
  telephony costs** - the mechanism is designed (ADR-7); the actual numbers are a pricing
  decision for the business side, deliberately not made here.
- **A third-party, non-vendor-sourced performance/latency audit** - Phase A1's own working
  prototype produces the first real measurement; a formal audit is a later, optional step
  once there's production traffic to audit.
- **Contact-facing messaging (SMS/WhatsApp) or an in-agent text-chat channel** - explicitly
  ruled out by the user's own clarification that "the chat messaging system" means
  internal team chat; either of these would be a separate, future feature with its own
  plan, not folded into Track B.
- **Migrating existing CALL-E-era historical call data into any new shape** - historical
  `call_outcomes` rows stay exactly as they are (CALL-E-shaped `attempts`/`task_completed`
  and all); nothing in this plan proposes backfilling or reinterpreting them.
