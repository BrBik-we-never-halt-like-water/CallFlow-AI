# The voice-agent platform - design, not yet built

**Status: design only.** Nothing in this document is implemented. It exists so the
multi-week systems work below doesn't start as code before it's been thought through
once, end to end. Read [`CALLE.md`](CALLE.md) first - this doc assumes its findings.

---

## 0. What's already shipped (don't re-build this)

A lot of what a "voice agent platform" needs at the product layer already exists,
built during the org-scoped persistence and Settings work:

| Piece                                                              | Where                                                         | State                                                               |
| ------------------------------------------------------------------ | ------------------------------------------------------------- | ------------------------------------------------------------------- |
| Org-scoped API keys                                                | `api/v1/routes/api_keys.py`                                   | Real                                                                |
| Twilio/Plivo credential storage (Fernet-encrypted)                 | `api/v1/routes/integrations.py`, `provider_credentials` table | Real, but **stores credentials only** - nothing dials over them yet |
| Billing (usage display)                                            | `api/v1/routes/organisations.py` + `/api/health`              | Real for usage; no payment processor                                |
| Mandatory org setup, server-verified                               | `organisations.onboarded_at`, `OnboardingGate`                | Real                                                                |
| Dashboard rename, empty by default                                 | `app/(app)/app/page.tsx`                                      | Real                                                                |
| "5 more integrations" (Zapier, Slack, HubSpot, Salesforce, Sheets) | `settings/integrations/page.tsx`, `COMING_SOON`               | Listed as coming soon, not built                                    |
| dry_run removed everywhere                                         | -                                                             | Done, non-negotiable #8 in `CLAUDE.md`                              |

**What's actually left, and what this document is about:** a `VoiceProvider`
abstraction with more than one implementation, a way for an org to configure its own
conversational agent (STT + TTS + LLM, or a prebuilt one), and the routing logic that
decides which of those actually places a given call. None of this exists today -
`app/integrations/voice/engine.py` is a concrete, un-abstracted CALL-E client, and
that is the entire voice layer.

---

## 1. The `VoiceProvider` protocol

`CLAUDE.md`'s Substitutability section already states the rule: normalise errors into
an internal taxonomy, declare capabilities rather than assume them. This is that
protocol, concretely.

**P1 status: shipped**, in a deliberately smaller shape than the snippet below.
`app/integrations/voice/protocol.py` is real: `VoiceCapability`, `VoiceProvider`
(`Protocol`), and `NotImplementedForProvider` exist, and `EngineGateway` conforms -
`supports()` declares `STRUCTURED_EXTRACTION`/`LIVE_EVENTS` true, `RECORDING`/
`CUSTOM_AGENT` false (confirmed against the real `calle` SDK, which exposes `create`,
`create_and_wait`, `get`, `list_events`, `wait_for_result` - no cancel), and
`cancel_call()` raises `NotImplementedForProvider` rather than faking one. Two
deliberate scope cuts from the sketch below, so this stays a true no-behavior-change
refactor rather than a second rewrite of working code:

1. **Methods stay synchronous**, matching `EngineGateway`'s existing shape exactly -
   `campaign_runner.py` still wraps every call in `asyncio.to_thread()` itself, unchanged.
   Whether the protocol should be async-native (so a genuinely-async adapter like
   Twilio's REST client doesn't get pointlessly thread-wrapped) is a real question, but
   it can only be answered correctly once that adapter exists (P5) - deciding it now,
   with CALL-E as the only data point, would be guessing.
2. **No `CallHandle`/`CallStatus` normalised return type yet** - `start_call`/`get_call`
   still return the raw `JsonObject` CALL-E hands back, because `campaign_runner.py`'s
   `_extract_result`/`_extract_transcript` are deeply, usefully coupled to parsing that
   specific (multi-shape-across-versions) payload. Normalising the return shape before
   a second adapter's real payload exists to normalise _against_ would mean designing
   an interface from one example - the same "not an abstraction yet" trap CLAUDE.md
   warns about, just moved to the return type instead of the implementation count.

Both cuts are documented here so they're a tracked decision, not a silently abandoned
part of the design. Revisit both when P5 (Twilio/Plivo adapters) is actually built.

```python
# app/integrations/voice/protocol.py - new file. Nothing above this layer imports
# calle, twilio, or plivo directly; everything speaks this.

class VoiceCapability(str, Enum):
    RECORDING = "recording"
    STRUCTURED_EXTRACTION = "structured_extraction"   # result_schema, native
    LIVE_EVENTS = "live_events"                        # per-turn progress, not just terminal status
    CUSTOM_AGENT = "custom_agent"                      # can host a caller-supplied conversational agent

class DialFailure(str, Enum):
    """The internal taxonomy every adapter maps its own errors onto. Retry policy,
    triage, and the UI key off THIS, never a vendor error string."""
    INVALID_NUMBER = "invalid_number"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    VOICEMAIL = "voicemail"
    DECLINED = "declined"            # recipient hung up / refused early
    RATE_LIMITED = "rate_limited"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    POLICY_VIOLATION = "policy_violation"              # vendor-side compliance block
    INTERNAL = "internal"

class VoiceProvider(Protocol):
    def supports(self, capability: VoiceCapability) -> bool: ...

    async def start_call(
        self, *, task: str, phone: str, result_schema: JsonObject,
        metadata: JsonObject, idempotency_key: str,
    ) -> CallHandle: ...

    async def get_call(self, handle: CallHandle) -> CallStatus: ...

    async def cancel_call(self, handle: CallHandle) -> None: ...
    # Raises NotImplementedForProvider if not supported - the caller (campaign_runner)
    # checks supports(...) first and degrades with an explanation, per CLAUDE.md's I.
```

**CALL-E's error taxonomy → `DialFailure` mapping** (from `CALLE.md` §4, this is the
concrete work item, not a design question):

| CALL-E code                             | `DialFailure`                                                                      |
| --------------------------------------- | ---------------------------------------------------------------------------------- |
| `invalid_phone`, `invalid_recipient`    | `INVALID_NUMBER`                                                                   |
| `rate_limit_exceeded`                   | `RATE_LIMITED`                                                                     |
| `insufficient_balance`                  | `INSUFFICIENT_BALANCE`                                                             |
| `recipient_blocked`, `policy_violation` | `POLICY_VIOLATION`                                                                 |
| `provider_unavailable`                  | `PROVIDER_UNAVAILABLE`                                                             |
| everything else                         | `INTERNAL` (fail closed - an unmapped code should never look like a clean failure) |

`no_answer`/`busy`/`voicemail` aren't in CALL-E's _error_ taxonomy - they show up as
terminal `AttemptStatus` values instead (`CALLE.md` §3). The mapping lives in the
CALL-E adapter's result-parsing path, not its error path.

### The CALL-E adapter

Wraps the existing `EngineGateway` almost unchanged - it already does the right
thing, it just needs to implement the protocol and declare capabilities:
`STRUCTURED_EXTRACTION` and `LIVE_EVENTS` (`list_events`) yes; `RECORDING` and
`CUSTOM_AGENT` no (`CALLE.md` §5: recording isn't confirmed to exist in the public
API at all, and CALL-E owns the whole conversation - there's no hook for a
caller-supplied agent to drive the call instead of CALL-E's own model).

### The Twilio and Plivo adapters - a different kind of problem

Twilio and Plivo are **not** drop-in CALL-E replacements: they hand you a phone
call, not a conversation. Both stream the call's raw audio to a WebSocket URL you
provide (Twilio: [Media Streams](https://www.twilio.com/docs/voice/media-streams),
Plivo: Stream XML) - something has to be listening on that socket, running STT on
inbound audio, feeding it to an LLM, running TTS on the reply, and streaming audio
back, all under ~300ms round-trip or the conversation feels broken. That something is
this project's **Voice Agent** (§2) - Twilio/Plivo are the dial tone, the agent is
the person actually talking.

Consequence for the adapter itself: `TwilioProvider.start_call()` doesn't take a
`task` string at all - it takes a `voice_agent_id`, places the call via Twilio's REST
API, and points the Media Stream at the agent runtime (§3). `supports(CUSTOM_AGENT)`
is true; `supports(STRUCTURED_EXTRACTION)` is **not** something Twilio itself
provides - the agent runtime has to do the extraction and hand results back the same
way CALL-E's `result_schema` does today, or this codebase loses the one thing that
makes it not-a-transcript-scraper.

**This is a genuinely different runtime, not a new FastAPI route.** A request/response
API can't hold a ~30-minute bidirectional audio WebSocket per active call at
production concurrency without starving every other request. It needs to be:

- A **separate process** (own repo folder - `apps/voice-runtime/` - or its own
  deployable, not a route bolted onto `apps/api`), speaking WebSocket, holding one
  connection per active call for the call's duration.
- Talks to Postgres the same way `apps/api` does (org-scoped, `as_user`-equivalent)
  to read the Voice Agent's config and write outcomes when a call ends - or, more
  realistically, calls back into `apps/api`'s existing `runs_repo.append_outcome()`
  path over an internal HTTP call so persistence logic isn't duplicated.
  Consider a small first-party queue (Redis Streams or Postgres `LISTEN/NOTIFY`)
  between the two if the media runtime needs to hand off work asynchronously.
- Pinned to hardware near Twilio/Plivo's media edge if latency becomes a problem -
  not a decision to make until there's a working prototype to measure.

Do not build this until §2's Voice Agent model and at least one STT/TTS/LLM adapter
triad exist to actually plug into it - building the plumbing before there's an agent
to run through it has nothing to verify against.

---

## ADR-1: The media runtime's Twilio/Plivo adapter boundary

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Whoever builds P5

### Context

§1's research pass confirmed Twilio Media Streams and Plivo's audio-streaming feature
use **asymmetric** WebSocket vocabularies - not just different framing of the same
events, different event names on each side:

|                         | Twilio                                                | Plivo                                                    |
| ----------------------- | ----------------------------------------------------- | -------------------------------------------------------- |
| Inbound (vendor → app)  | `connected`, `start`, `media`, `stop`, `dtmf`, `mark` | `start`, `media`, `dtmf`, `playedStream`, `clearedAudio` |
| Outbound (app → vendor) | `media`, `mark`, `clear`                              | `playAudio`, `checkpoint`, `clearAudio`                  |

Despite the naming mismatch, the two protocols plausibly express the same six
underlying ideas - stream-start, inbound-audio-chunk, inbound-dtmf,
outbound-audio-chunk, outbound-flush/barge-in, playback-progress-marker - just with
different wire vocabularies and, likely, different edge-case guarantees (e.g. it's
unconfirmed whether Twilio echoes a playback-completion event the way Plivo's
`playedStream` does). That "plausibly, not confirmedly" is the crux of this decision.

The open question: should the P4 media runtime define one internal
`MediaChannel`-shaped protocol (mirroring `VoiceProvider`'s own pattern: normalise
into an internal vocabulary, one adapter per vendor translates at the edge), or should
Twilio's and Plivo's WebSocket handlers be fully separate, un-abstracted code paths
given the wire protocols don't actually match?

### Decision

**Build Twilio's handler first, fully un-abstracted. Do not design the shared
`MediaChannel` protocol until Plivo's handler is also being built, and extract it from
what the two real implementations actually have in common - not from the six
guessed-at primitives above.**

This is the _same_ discipline this session already applied one layer up, for the same
reason: P1 deliberately left `VoiceProvider`'s return type as CALL-E's raw
`JsonObject` rather than a normalised type, because "designing that normalisation from
a single _real_ vendor's data would be guessing, not abstracting" (§1's own words,
written before this ADR). The situation here is the mirror image - two vendors, zero
real implementations - but the same failure mode: an abstraction designed from
research and inference, before either adapter has been forced to actually satisfy it,
is still a guess. `CLAUDE.md`'s "an abstraction with one implementation is not an
abstraction" is usually read as "build the second implementation" - the less obvious
half is "and don't design the shape _before_ the first one either," which is the
half this decision is actually about.

Concretely: `TwilioMediaHandler` gets written as a direct WebSocket handler that
speaks Twilio's exact vocabulary (`connected`/`start`/`media`/`stop`/`dtmf`/`mark` in,
`media`/`mark`/`clear` out) and calls the `SpeechToText`/`TextToSpeech` adapters
(§2.2) directly - no intermediate abstraction layer between "Twilio's wire format"
and "raw audio bytes." When Plivo's handler is built (P5b), _then_ look at what the
two handlers' internal structure actually shares - likely something close to the six
primitives above, but confirmed by two real implementations instead of assumed from
two vendors' docs - and extract a shared internal protocol only if the sharing is
real, not merely plausible.

### Options Considered

#### Option A: Shared `MediaChannel` protocol designed now, both adapters implement it from day one

| Dimension        | Assessment                                                              |
| ---------------- | ----------------------------------------------------------------------- |
| Complexity       | Low upfront (one interface, two implementations against it)             |
| Cost             | Real: if the guessed shape is wrong, both adapters need rework, not one |
| Scalability      | N/A at this layer                                                       |
| Team familiarity | Matches `VoiceProvider`'s own established pattern - cheap to learn      |

**Pros:** Consistent with how `VoiceProvider` already looks; a future third telephony
vendor has an obvious shape to conform to from day one.
**Cons:** Designed from research (docs + inference about likely shared semantics),
not from two working implementations - exactly the "guessing, not abstracting" trap
§1 already named and avoided once this session. If Twilio's `mark` and Plivo's
`playedStream`/`checkpoint` turn out not to line up the way this ADR guesses, the
abstraction has to be reworked _and_ both adapters retrofitted to it.

#### Option B: Twilio and Plivo handlers fully separate, permanently, no shared layer ever

| Dimension        | Assessment                                                                                        |
| ---------------- | ------------------------------------------------------------------------------------------------- |
| Complexity       | Low now, but two call-routing branches (§3) forever, not one                                      |
| Cost             | Duplicated connection-lifecycle/reconnect/error-handling logic across both handlers, indefinitely |
| Scalability      | N/A at this layer                                                                                 |
| Team familiarity | No new pattern to learn, but also no reuse of the one just established                            |

**Pros:** Zero risk of forcing a bad-fit abstraction onto a real protocol difference.
**Cons:** Throws away real, likely shared plumbing (connection lifecycle, backpressure,
reconnect-on-drop, the STT/TTS hand-off itself) that has nothing to do with the
vocabulary mismatch - that plumbing doesn't care whether the event was called `mark`
or `checkpoint`. Permanently forgoing any abstraction is itself a guess (that nothing
is truly shared), just the opposite-direction one from Option A.

#### Option C (chosen): Twilio first, un-abstracted - extract the shared layer from two real implementations

| Dimension        | Assessment                                                                                         |
| ---------------- | -------------------------------------------------------------------------------------------------- |
| Complexity       | Lowest for P5a (one handler, no interface to satisfy); a real refactor at P5b                      |
| Cost             | The refactor at P5b is real, bounded work - but informed by two working systems instead of guesses |
| Scalability      | N/A at this layer                                                                                  |
| Team familiarity | Reuses the _reasoning_ from P1's own precedent, not the pattern itself yet                         |

**Pros:** Never designs an abstraction from fewer than two real data points, matching
the standard this codebase already set for itself at the `VoiceProvider` layer. The
P5a→P5b sequencing also means Twilio (which has by far the better-documented,
partner-blog-validated protocol, §1) ships first and is usable on its own before Plivo
exists at all - real, working value lands before the abstraction question is even
asked for real.
**Cons:** Slower to a "clean" architecture than Option A on paper; requires discipline
to actually do the extraction at P5b rather than let two un-abstracted handlers
calcify into permanent Option B by default by never doing the second pass.

### Trade-off Analysis

The real axis isn't "abstraction vs. no abstraction" - it's **when** the abstraction
gets designed relative to when it's checked against reality. Option A pays the
guessing-risk cost immediately, on the first line of code. Option B pays a duplication
cost forever by refusing to ever pay the guessing-risk cost. Option C pays neither
upfront: it defers the abstraction question to the one moment it can actually be
answered correctly (two real handlers to compare), at the cost of requiring someone to
actually go back and do the comparison rather than ship two forever-separate handlers
and call it done.

### Consequences

- P5 is now explicitly two sub-phases, not one: **P5a** (Twilio handler, un-abstracted,
  ships value on its own) and **P5b** (Plivo handler + the extraction pass over both).
  §5's roadmap table should reflect this split when P5 is scheduled.
- Whoever does P5b must budget real time for the extraction, not just "add Plivo" -
  reviewing P5a's handler for what's genuinely vendor-specific vs. genuinely shared
  (connection lifecycle, reconnect, STT/TTS hand-off, backpressure) is its own task.
- If P5b's extraction finds the two handlers share almost nothing beyond generic
  WebSocket plumbing, Option C converges to Option B honestly - which is a fine
  outcome; the point was not building Option A's guess, not forcing an abstraction to
  exist.

### Action Items

1. [ ] When P5 starts: build `TwilioMediaHandler` directly against Twilio's confirmed
       protocol (§1), no intermediate abstraction.
2. [ ] Do not create a `MediaChannel`/`TelephonyProvider`-style protocol file until
       Plivo's handler exists to compare against.
3. [ ] At P5b, do the extraction pass explicitly - don't let "add Plivo" quietly become
       "copy-paste Twilio's handler with different event names" without checking.
4. [ ] Update §5's roadmap table to show P5a/P5b as the two real steps this ADR implies.

---

### Sarvam AI - confirmed against primary docs (docs.sarvam.ai), not guessed

Deep-research pass, 2026-08-07: 23 primary sources fetched, 25 extracted claims
independently adversarially verified (each claim checked against the vendor's own docs
by a separate agent instructed to try to refute it). Findings below are only the ones
that survived that check; two early draft claims were caught overreaching and are noted
as refuted so they don't get load-bearing weight later.

- **STT, TTS, and the LLM are three separate, independently callable APIs** on one base
  URL (`https://api.sarvam.ai`) - `/speech-to-text`, `/text-to-speech`,
  `/v1/chat/completions` - plus Translation, Transliteration, and Language ID as further
  separate endpoints. Confirmed, not a bundled "agent" product.
- **STT has three modes, not one**: synchronous REST (files under 30s), an async Batch
  API (files up to 2h, up to 20 files/job, speaker diarization up to 20 speakers), and a
  Realtime WebSocket API (`saaras:v3-realtime`, "true partial transcripts," sub-150ms
  time-to-first-token in its "Fast" mode). An early draft claim - "Sarvam STT is
  real-time-only over WebSocket, no batch/REST alternative" - was checked and **refuted**:
  the batch and REST paths are real and documented; don't design the adapter as if only
  streaming exists.
- **STT streaming is WAV or raw PCM only** (`pcm_s16le`/`pcm_l16`/`pcm_raw`) - not
  mp3/aac/ogg. Sample rate 16kHz (default/recommended) or 8kHz (telephony), and it must
  be set identically at both the WebSocket-connect step and the per-chunk transcribe
  call, or transcription quality degrades. Batch/REST STT accepts 10+ formats.
- **TTS (Bulbul v3, 30+ voices, 11 languages** - the 10 Indian languages plus English in
  an Indian accent) also has both a batch mode (REST, ≤2500 chars/request, returns
  base64 WAV) and a streaming mode (HTTP POST or a persistent WebSocket, ≤3500
  chars/request for HTTP streaming, ≤2500 chars/message and **under 500 recommended for
  lowest latency** over WebSocket). Output codecs include telephony-ready **mu-law and
  PCM LINEAR16 directly** - no transcoding needed before handing audio to Twilio/Plivo.
  A raw `wss://api.sarvam.ai/` endpoint with an `Api-Subscription-Key` handshake header
  is documented (AsyncAPI spec page) alongside the SDK wrapper, so a non-SDK Python
  adapter can speak the protocol directly rather than depending on Sarvam's own SDK.
- **LLM**: `POST /v1/chat/completions`, model `sarvam-105b` (128K context; `sarvam-30b`
  also exists), OpenAI-compatible request/response shape including `stream: true` for
  server-sent-event streaming, tool calling, and structured JSON output.
- **Auth accepts both** a custom `api-subscription-key` header **and** a standard
  `Authorization: Bearer <key>` header on every endpoint (documented as simultaneous
  support, explicitly for OpenAI-compatible tooling) - an early draft claim that it was
  "a custom header rather than Bearer/OAuth" was checked and **refuted** on this exact
  point; either header works.
- **Model naming note**: `Saarika` (an older STT model name) is being phased out in
  favour of `Saaras v3`/`v3-realtime` per Sarvam's own changelog and model pages - build
  the adapter against Saaras, not Saarika.
- **Already proven in production telephony**: Plivo publishes an official integration
  guide wiring Sarvam STT + an LLM + Sarvam TTS into a live phone call via Plivo's own
  audio-streaming/Pipecat pipeline (using OpenAI's GPT-4o as the LLM leg in that specific
  example, not Sarvam's) - real-world confirmation this triad works over a live call,
  not just in isolation.
- **Not found**: concrete pricing. No source in this pass surfaced a pricing page or
  number - still an open item before committing to Sarvam as the default BYO option.

### Twilio Media Streams - confirmed, and it answers part of §3's open question

- **Exactly six WebSocket message types**, Twilio → server: `connected`, `start`,
  `media`, `stop` (all streams), plus `dtmf` and `mark` (bidirectional-only - see below).
- **Audio format is fixed, not configurable**: `audio/x-mulaw`, 8000 Hz, mono, base64,
  with an explicit warning against including file-type header bytes in the payload.
- **Two TwiML verbs, two different capabilities**: `<Start><Stream>` is
  **unidirectional** (Twilio → server only; stoppable only by `<Stop>` TwiML or ending
  the call). `<Connect><Stream>` is **bidirectional** - the server can send `media`
  (play audio into the live call), `mark` (playback-completion tracking), and `clear`
  (flush buffered audio - this is the barge-in primitive) messages back. A separate
  Stream resource REST API can also start/control a stream on an already-live call
  without editing TwiML.
- **Outbound call + stream, concretely**: `client.calls.create(to=..., from_=<your own
Twilio number>, twiml=<Response><Connect><Stream url="wss://...">)`. `from_` is the
  literal mechanism for "the org's own number" - Twilio requires it be a number the
  account owns or a verified caller ID. There's no separate "attach a stream" call at
  creation time; the stream is just a verb inside the TwiML the call is created with.
  Stream URLs must be `wss://` - plain `ws://` is rejected.
  Auth is HTTP Basic (Account SID + Auth Token; Twilio recommends API Keys for
  production instead). New/default accounts are rate-limited to **1 outbound call per
  second** via this endpoint - relevant to `CampaignRunner`'s pacing once a Twilio
  adapter exists.
- **Directly answers half of §3's open question**: Twilio's own official engineering
  blog publishes a working reference implementation that proxies a live call's audio
  **bidirectionally to a third-party real-time AI service mid-call** (OpenAI's Realtime
  API over its own WebSocket) and relays the synthesized reply back into the call. So
  Twilio itself has no architectural barrier to this - the still-open half is whether
  **CALL-E** (not Twilio) exposes anything similar; this research pass didn't check
  CALL-E's own docs, so that half of the question is unresolved, not answered, by this
  finding - don't conflate "Twilio can do it" with "CALL-E can do it."

### Plivo - confirmed, and its protocol is NOT a drop-in match for Twilio's

- **Audio format**: mu-law 8kHz (`audio/x-mulaw;rate=8000`) is the default/recommended
  (native, no transcoding); linear PCM (`audio/x-l16`) at 8kHz or 16kHz is also offered.
- **Important: the message vocabulary is asymmetric, unlike Twilio's shared
  connected/start/media/stop set on both sides.** Plivo → server events are `start`,
  `media`, `dtmf`, `playedStream`, `clearedAudio`. Server → Plivo events use a
  _different_ vocabulary: `playAudio`, `checkpoint`, `clearAudio`. A `PlivoProvider`
  adapter's WebSocket handling cannot share a single "Twilio-shaped" message translator
  with the Twilio adapter - budget for two distinct, adapter-owned protocol
  implementations, not one shared media-runtime parser with a vendor flag.
- **Outbound call + stream, two viable shapes, one with a caveat**: (a) `POST
/v1/Account/{AUTH_ID}/Call/` with `to`, `from` (the org's own Plivo number),
  `answer_url` - Plivo fetches call-control XML from that URL once answered, and that
  XML can embed the `<Stream>` verb directly; or (b) a separate `calls.start_stream(
call_uuid, service_url, bidirectional=True)` REST call attached to an already-live
  call - but `call_uuid` for that must come from Plivo's `answer_url` callback
  parameters, not the initial call-creation response (which only returns
  `api_id`/`request_uuid`). **Caveat, lower confidence** (a GitHub issue on Plivo's own
  Python SDK repo, not vendor docs): at least one developer hit a "Stream consumed"
  exception and immediate disconnection following the two-step `start_stream()` path,
  with no visible maintainer resolution - prefer shape (a) (`<Stream>` embedded directly
  in the `answer_url` response) until (b) is verified directly against a real account.
- Recording can run concurrently with streaming via a separate `recordSession="true"`
  attribute on the same `<Stream>` element.

**What this means for P5 (§5's roadmap):** Twilio and Plivo adapters cannot share one
generic "telephony WebSocket" implementation inside the media runtime - the message
shapes genuinely differ. Each needs its own adapter-side protocol translator conforming
to whatever the runtime's internal (normalised) audio-event interface turns out to be.

---

## 2. The Voice Agent - a new data entity

**P3 status: refined design, still not built.** Revised 2026-08-07 against the real
Sarvam/Twilio/Plivo findings in §1 - the version below supersedes the original sketch
on three points: the batch/streaming scoping decision, the credential model, and how
an adapter gets tested pre-launch. Full system-design pass (requirements → data model
→ deep dive → scale → trade-offs) below; skip to the schema if you just need the DDL.

### 2.0 Requirements

**Functional.** An org configures a conversational agent from STT + TTS + LLM
providers it supplies credentials for (BYO), or picks a CallFlow-operated prebuilt
agent with no configuration. A campaign references an agent (§3's `voice_agent_id`).
The agent must produce: a transcript stream from inbound call audio, and a synthesized
audio stream from LLM text output - both **low-latency enough for a live phone call**
(CLAUDE.md's ~300ms round-trip bar, cited in §1).

**Non-functional.** This is the one requirement that reshapes everything below: **only
the streaming mode of any STT/TTS vendor is in scope.** Sarvam's own docs (§1) confirm
STT and TTS each have a batch/REST mode too - genuinely useful for other products
(async transcription, bulk audio generation), completely useless here. Nothing in this
platform ever has a pre-recorded audio file sitting around waiting to be transcribed;
audio arrives as a live stream from a Twilio/Plivo Media Stream, or doesn't exist yet.
Designing `SpeechToText`/`TextToSpeech` to cover both modes "for completeness" would
be exactly the speculative-design CLAUDE.md warns against - a second, unused code path
per adapter, forever.

**Constraints.** No Sarvam/Twilio/Plivo credentials exist for this project today (§2.3
covers how that's tested around, not ignored). No media runtime exists yet (P4,
blocked on this section). Existing `provider_credentials` table is the only encrypted
credential storage in the codebase - reuse it, per CLAUDE.md's "never build a second
X" instinct, already applied once in the original sketch and reaffirmed below.

### 2.1 Data model

```sql
create table public.voice_agents (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organisations(id) on delete cascade,
  name text not null,
  kind text not null check (kind in ('custom', 'prebuilt')),

  -- kind = 'custom' only. Each references provider_credentials - same table
  -- Twilio/Plivo secrets already use, widened (see below), not a new one.
  stt_provider text,             -- e.g. 'sarvam', 'deepgram'
  stt_credential_id uuid references public.provider_credentials(id),
  tts_provider text,              -- e.g. 'sarvam', 'elevenlabs'
  tts_credential_id uuid references public.provider_credentials(id),
  llm_provider text,               -- e.g. 'sarvam', 'openai', 'anthropic'
  llm_credential_id uuid references public.provider_credentials(id),

  -- kind = 'prebuilt' only.
  prebuilt_persona text,          -- which off-the-shelf voice/persona was purchased

  system_prompt text,             -- the goal-template equivalent for this agent
  voice_id text,                  -- TTS voice selection, provider-specific string
  created_at timestamptz not null default now(),
  created_by uuid references public.users(id) on delete set null
);
```

`provider_credentials.provider`'s check constraint (`in ('twilio', 'plivo')`) still
needs widening in the same migration that adds this table - unchanged from the
original sketch. **One real addition from the auth-model finding in §1**: Sarvam
accepts a credential as _either_ an `api-subscription-key` header _or_ a standard
`Authorization: Bearer` header - same secret value, two different header shapes, and
which one a request needs depends on the adapter, not the stored credential. That
decision belongs entirely inside the Sarvam adapter (§2.2), not the schema - a
`provider_credentials` row stays "an identifier plus one encrypted secret," exactly
its existing shape for Twilio/Plivo, with no new column. Getting this wrong would
have meant either a speculative `auth_scheme` column with one real value forever
(single-vendor, unjustified) or a schema change every time a future STT/TTS/LLM
vendor's auth model differs slightly - both worse than the adapter just knowing.

### 2.2 STT / TTS / LLM adapters - streaming-only, same `Protocol` pattern as `VoiceProvider`

```python
class SpeechToText(Protocol):
    async def transcribe_stream(self, audio: AsyncIterator[bytes]) -> AsyncIterator[TranscriptChunk]: ...

class TextToSpeech(Protocol):
    async def synthesize_stream(self, text: str, *, voice_id: str) -> AsyncIterator[bytes]: ...

class ConversationalLLM(Protocol):
    async def respond(self, history: list[Turn], *, system_prompt: str) -> AsyncIterator[str]: ...
```

Unchanged from the original sketch - confirmed correct, not merely un-revisited.
§2.0 already made the batch-vs-streaming call: these three methods are the whole
interface, deliberately. No `transcribe_batch`/`synthesize_batch` twin methods, ever,
unless a real, non-telephony use case for this platform shows up first.

**Telephony protocol asymmetry stays out of this layer, on purpose.** §1's finding
that Twilio's and Plivo's WebSocket message vocabularies don't match (different event
names, different send-back shapes) does **not** touch these three Protocols - they
already take/return raw audio bytes or plain text, with zero telephony awareness. That
separation, chosen before the asymmetry was confirmed, turns out to be exactly right:
translating Twilio's/Plivo's own wire format into a plain `AsyncIterator[bytes]` is
P4's media runtime's job, once, per telephony vendor - `SpeechToText`/`TextToSpeech`
adapters never need to know which phone vendor is even involved. One clean layer
boundary absorbs a vendor-asymmetry finding that could otherwise have forced two
divergent STT/TTS adapter shapes.

**First adapters to build** (concrete, not "and others"):

| Slot | First-party adapter                                                                                                                             | Second, for BYO to mean something                                                               |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| STT  | **Sarvam** (`saaras:v3-realtime`, confirmed real streaming WS endpoint, §1)                                                                     | Deepgram (English-first, low-latency streaming, industry baseline to compare against)           |
| TTS  | **Sarvam** (Bulbul v3 streaming WS, outputs mu-law/PCM directly - no transcoding step needed before handing audio to a Twilio/Plivo `<Stream>`) | ElevenLabs (highest-quality English voices, the thing people mean by "human-like")              |
| LLM  | **Sarvam** (`sarvam-105b`, OpenAI-compatible `/v1/chat/completions`, confirmed streaming via SSE)                                               | Anthropic or OpenAI, via whichever SDK this repo already trusts for latency-sensitive streaming |

One adapter per slot proves the interface; the second proves it's not a
single-vendor lie, per the same rule `CLAUDE.md` states for `VoiceProvider` itself -
and per P1's own gap (`ISSUES.md`, this session's review), the _stub_ for tests should
land in the same PR as the first real adapter this time, not as a later addition.

### 2.3 Testing a Sarvam adapter with no Sarvam account

No credentials exist for this project yet - the adapter cannot be "tested against the
real thing" the way `EngineGateway`/CALL-E's tests can't either, but CALL-E's own
tests don't hit the network (see `apps/api/tests/test_engine.py`), and this shouldn't
either, for the same reason: a test suite that needs a live paid account to pass is a
test suite that doesn't run in CI.

1. **Recorded-fixture unit tests.** §1's research pass already captured real Sarvam
   WebSocket message shapes (config/text/flush/ping for TTS; the STT streaming
   response shape) straight from primary docs. Freeze those as fixture payloads and
   test the adapter's parsing/framing logic against them - this catches "the adapter
   misreads Sarvam's own documented protocol," the highest-value bug class, without
   any network call.
2. **A fake WebSocket server for integration-style tests**, matching the pattern
   `apps/api/tests/test_engine.py`'s `FakeGateway`/`FailingGateway` already
   establishes for CALL-E: a local `websockets`-based stub server speaking exactly the
   fixture protocol from step 1, so `SarvamSTT.transcribe_stream()` runs its real
   connect/send/receive loop against something, not a mock of its own internals.
3. **Explicit "not configured" vs. "credentials rejected" as two different states**,
   not one generic failure - this platform is going to be run by people who haven't
   signed up for Sarvam yet. `NotImplementedForProvider`-style clarity (already the
   pattern for `VoiceProvider.cancel_call()`) beats a bare exception here too.
4. **A manual, human-run smoke-test checklist** (not automated) for the day real
   credentials do arrive - one real streaming STT call, one real streaming TTS call,
   one real chat-completion call, each checked against the fixture shapes from step 1
   to catch "the docs were stale" before it reaches a live phone call.

None of this requires Sarvam credentials to exist before P3 starts. It does mean the
first real adapter PR should include its own fixtures, not defer them.

### 2.4 Is missing Sarvam pricing a blocker?

**Not for building the adapter. Possibly, for defaulting to it in product UI.** These
are two different decisions on two different timelines, and conflating them would
either stall real engineering work behind a sales conversation, or commit to a public
default before knowing what it costs to stand behind:

- **Adapter build (P3, engineering):** no pricing dependency at all. The `SpeechToText`/
  `TextToSpeech`/`ConversationalLLM` protocols, the `voice_agents` schema, and a Sarvam
  adapter conforming to all three can be built and tested (§2.3) with zero knowledge of
  Sarvam's pricing. Proceed now.
- **"Sarvam is the recommended/pre-selected default" in the Agents tab (§4, product):**
  genuinely blocked. §1's research pass fetched primary technical docs exhaustively and
  found zero pricing pages - consistent with usage-based API pricing being gated behind
  a sales conversation or a dashboard login, not a public rate card. Recommending a
  specific vendor by default, in a product that resells access to it, without knowing
  the margin, is a real business risk CLAUDE.md's "never show a false success state"
  spirit extends to by analogy - don't imply a considered recommendation that isn't
  actually informed yet. Get real pricing (a sales conversation, or a Sarvam dashboard
  signup) before §4 ships a default; until then, the Agents tab can list Sarvam as _an_
  option alongside its BYO peers with no default pre-selected.

### The "prebuilt" agent

### The "prebuilt" agent

A first-party voice agent CallFlow itself operates and charges for - WebRTC-enabled,
tuned for backchanneling and low latency, no configuration required. Architecturally
this is just `kind = 'prebuilt'` with no BYO credentials: the same media runtime
(§1) runs it, using CallFlow's own STT/TTS/LLM credentials instead of the org's. It
is not a separate system - it's the zero-config path through the one that BYO also
uses, which is exactly why building BYO first is right: the prebuilt agent falls out
of it almost for free once the runtime and one adapter triad exist.

---

## 3. Call-routing decision tree

Given an org's configuration, `POST /api/v1/runs` needs to decide which path a call
takes. The cleanest shape: **campaigns don't change, runs gain a resolved provider.**

```
start_run(campaign_id, contacts)
  │
  ├─ org has no connected Twilio/Plivo AND no voice_agent configured
  │    → CALL-E, exactly as today (the default, zero-setup path)
  │
  ├─ org has a connected number but no voice_agent
  │    → not a valid combination yet: a phone number with nothing to talk needs
  │      either CALL-E behind it (not supported - CALL-E owns its own numbers,
  │      CALLE.md §1) or an agent. Reject at the campaign/run-start layer with an
  │      honest error, not a silent fallback to CALL-E.
  │
  ├─ org has a voice_agent, kind = 'custom' or 'prebuilt', AND a connected number
  │    → TwilioProvider/PlivoProvider dials via the org's own number, media
  │      streams to the agent runtime (§1), running that agent's configured
  │      STT/TTS/LLM (or CallFlow's own, for 'prebuilt')
  │
  └─ org has a voice_agent but no connected number
       → the agent has no phone to dial from. Two sub-options, pick one and say
         so in the UI rather than silently choosing: (a) reject until a number is
         connected, or (b) let the agent's *conversation* run while CALL-E places
         the actual dial - genuinely harder (CALL-E doesn't expose a way to hand
         its live audio to a third party mid-call, unconfirmed either way per
         CALLE.md §5) and shouldn't be assumed possible until checked with CALL-E
         directly. **Still genuinely unconfirmed** after the 2026-08-07 research
         pass above - that pass confirmed Twilio and Plivo can both do a live
         mid-call handoff to a third party (§1), which answers nothing about
         CALL-E specifically, since no agent in that pass checked CALL-E's own
         docs for this. Don't read the Twilio/Plivo findings as resolving this.
```

Data model: a nullable `voice_agent_id` on `campaigns` (an agent is a property of
_what this campaign sounds like_, same altitude as `goal_template`), resolved at
run-start time alongside the campaign itself - not a new field on the run-start
request body. `resolve_campaign()` in `api/v1/routes/campaigns.py` is the one place
that already resolves everything else about a campaign; the provider decision
belongs there too.

---

## 4. The Agents tab

New Settings-adjacent surface (or its own top-level nav item - this needs the same
"where does this actually live" judgment call `overview-org-section.tsx`'s docstring
already made once for org switching; don't guess, ask when it's time to build this).
Two sections:

- **Your agents** - list of `voice_agents` rows for this org, create/edit/delete, each
  showing kind, provider triad (or "Prebuilt"), and which campaigns use it.
- **Prebuilt** - the CallFlow-operated agent, purchasable/usable directly, no
  configuration beyond picking a persona.

Creating a custom agent is a form: name → STT provider + credential → TTS provider +
credential → LLM prov021 provider + credential → system prompt → voice selection -
structurally identical to the existing Integrations tab's `ConnectDialog`, extended
with three provider pickers instead of one.

---

## 5. Phased roadmap

| Phase   | Ships                                                                                                                                                  | Depends on                                               |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------- |
| **P1**  | ✅ Shipped. `VoiceProvider` protocol + CALL-E adapter conforms to it (no behavior change, pure refactor)                                               | Nothing - do this first, it de-risks everything after it |
| **P2**  | Error taxonomy mapping (CALL-E → `DialFailure`), used in retry policy and the UI's failure messages                                                    | P1                                                       |
| **P3**  | `voice_agents` table, STT/TTS/LLM protocols, Sarvam adapter for all three slots (prove the model end-to-end with one vendor before adding a second)    | P1                                                       |
| **P4**  | Media runtime (`apps/voice-runtime/`) - a working prototype: one active call, Sarvam-only, no BYO choice yet, talking over a single test Twilio number | P3                                                       |
| **P5a** | `TwilioMediaHandler` - un-abstracted, speaks Twilio's confirmed protocol directly (ADR-1, §1)                                                          | P4                                                       |
| **P5b** | `PlivoMediaHandler` + the extraction pass over both handlers for whatever's actually shared (ADR-1 - do not skip the extraction step)                  | P5a                                                      |
| **P6**  | Second adapter per STT/TTS/LLM slot (BYO becomes real, not single-vendor)                                                                              | P3                                                       |
| **P7**  | Agents tab (frontend), call-routing decision tree wired into `POST /api/v1/runs`                                                                       | P5b, P6                                                  |
| **P8**  | Prebuilt agent product (CallFlow's own credentials through the same runtime)                                                                           | P7                                                       |

**Honest scope note:** P1–P3 are ordinary application work, roughly what the last
several sessions on this repo have looked like. P4 is a real-time systems project -
a persistent low-latency media service is a different discipline from a request/response
API, and "a working prototype" at P4 is itself multiple weeks, not days, even with
one vendor and one test number. Nothing past P3 should be scheduled with the same
confidence as the work already shipped this session.
