# RUNBOOK — Part 2: Voice Agent Data Model, Extraction/Triage & Product Surface

**Owner:** Arbaaz
**Source plan:** `PLATFORM_PIVOT_PLAN.md` — ADR-4 (schema consumption + Agentic tab + API surface), ADR-5 (extraction/completeness, whole), ADR-7 (billing UI half), §9 (frontend/run-start half), §11 (CALL-E removal, frontend + domain half), §12 Track A phases A0 (frontend half), A1 (product half), A3.3, A4
**Companion runbooks:** `RUNBOOK_HET_PART_1.md` (voice runtime, telephony, CALL-E removal backend), `RUNBOOK_JATIN_PART_3.md` (internal team chat)

---

## 0. Grounding — verified against the actual repo

Read `RUNBOOK_HET_PART_1.md` §0 first — the same three facts apply to you: no `voice_agents`/`telephony_provisioning` tables exist yet, no `apps/voice-runtime/` exists, CALL-E is fully wired and real. Additional facts specific to your half, verified directly:

- **`triage.py`'s current rule order matches ADR-5's description exactly**, line for line. The file is 93 lines; the rule you're replacing is literally lines 83–85:
  ```python
  elif status == "completed":
      updates["disposition"] = Disposition.AUTO_CLOSED
      updates["disposition_reason"] = "Conversation completed with no escalation signals."
  ```
  This is the *only* rule you touch — rules 1–7 above it (do-not-call, human request, frustration, `task_completed is False`, negative-sentiment retry, busy/no-answer/voicemail, failed/canceled) are untouched, confirmed vendor-neutral.
- **The "required" checkbox already exists and already reaches the schema.** `apps/api/app/domain/result_schemas.py`'s `build_result_schema()` already appends a campaign's `extra_required` fields onto `BASE_REQUIRED`, and `apps/api/app/api/v1/routes/campaigns.py`'s `_validate_and_build_fields()` (lines 125–156) already collects `required` from each field's checkbox and passes it to `build_result_schema(properties, required)`. **Nothing downstream has ever read `result_schema["required"]` back against what actually came out of a call** — that check is entirely what you're building. You are not adding the "required" concept; you're adding its enforcement.
- **The escalations worklist is not a database table.** `apps/web/lib/app-store.tsx` derives `escalations` as `outcomes.filter(outcome => lampForOutcome(outcome).state === 'flare')` (line 189) — purely client-side, from whatever `GET /api/v1/runs/{id}` returns. `apps/web/lib/lamp.ts` maps `disposition === 'escalated'` to lamp state `'flare'` (line 54). **This means your new triage rule (which sets `disposition = ESCALATED` when fields are missing) will show up in the existing "Needs a person" worklist automatically, with zero frontend plumbing beyond adding the new field to the `Outcome` type and rendering a distinguishing badge.** Don't rebuild the escalation-detection mechanism — it already exists and already works the way you need it to.
- **`ISSUES.md`'s last entry is `#76`**, not `#84`/`#85` as the plan's ADR-5/ADR-6 cite — those specific issue numbers don't exist in this repo. Re-verify with `grep '^### #' ISSUES.md | tail -1` before adding your own entry, in case Part 1 or Part 3 land one first.
- **No `apps/web/lib/hooks/use-org-realtime.ts` exists** — not your concern (Part 3 builds it), but don't assume any Realtime plumbing is available to reuse; your polling-based patterns (`use-run-poll.ts`) are the only live-update mechanism that exists today, and are what your "connect a number" status polling (A2.3) should follow.

---

## 1. Objective and scope

You own everything an organisation actually configures and sees for the voice-agent pivot: the `voice_agents` CRUD API, the Agentic tab, the extraction-and-completeness pipeline that replaces what CALL-E used to hand back for free, the `triage.py` change that acts on it, the Needs-a-person and campaign-editor UI updates, the OpenRouter model-picker UI, the prebuilt-agent UI, and the honest "calling isn't available" messaging while Part 1's runtime doesn't exist yet.

**You own:**
- `app/domain/extraction.py` (new) — `check_extraction_completeness()`, pure, no I/O.
- The LLM-calling extraction/completion-judgment step (ADR-5) — this has I/O (an LLM call), so it lives in `app/services/`, not `app/domain/`.
- `app/domain/triage.py`'s one new rule.
- `app/domain/entities.py`'s `CallOutcome.missing_required_fields` field + its migration.
- `apps/api/app/api/v1/routes/voice_agents.py` — CRUD only (list/create/update/delete), Pydantic models.
- The Agentic tab (`/app/agentic`), nav entry, "Your agents" + "Prebuilt" sections, connect-a-number UI state machine.
- Needs-a-person worklist's missing-fields badge/filter (A4.1).
- Campaign editor's "N required fields" prominence (A4.2).
- OpenRouter model-picker UI (A3.3).
- Prebuilt agent UI (A4.3).
- `apps/web/app/(marketing)/docs/result-schemas/page.mdx` rewrite.
- §9's run-start rejection UX + the honest "calling unavailable" empty states (A0.4) while Part 1's runtime is incomplete.

**You do NOT own:** `apps/voice-runtime/`, LiveKit/Twilio/Plivo integration code, the `telephony_provisioning` table/repository, OpenRouter key *provisioning* (you consume the usage numbers it produces, you don't call the provisioning API yourself), chat (Part 3).

---

## 2. Dependencies and assumptions

- **A1.5 (extraction/completeness domain logic) has zero external dependency and should be your first task.** It's a prompt + a comparison function, testable against a hand-supplied transcript — no LiveKit account, no Twilio number, no working media runtime needed. The plan itself calls this out explicitly as the task most likely to be scheduled too late by mistake; don't do that.
- **You depend on Part 1** for: the `voice_agents`/`telephony_provisioning` migration (they author it — see their runbook §6 — but they've committed to telling you the column list on day one so you don't have to wait for the migration to merge before writing your Pydantic models and a local stub repository), and eventually the real LiveKit runtime for end-to-end testing (A1.7).
- **Part 1 depends on you** for nothing to start their CALL-E removal or LiveKit/SIP work, but does depend on your extraction pipeline existing before the first real end-to-end call test means anything (a call with no completeness check is just a transcript).
- **Joint design decision required with Part 1 before A1.4/A1.5 integration lands** (flagged honestly, not glossed over — the plan itself leaves this open in §13): under CALL-E, `campaign_runner.py` synchronously polled a call to a terminal status and then ran extraction/triage in the same request-response-shaped flow. Under LiveKit, the call is event-driven — Part 1's worker finishes a call and reports back asynchronously, likely via an internal HTTP callback into `apps/api` (see their runbook §4, P1-T4). **You need to agree with Part 1, before either of you writes the integration code, on: (a) the exact internal endpoint/payload shape the worker calls back with, and (b) whether that endpoint's handler calls directly into your extraction pipeline, or whether `campaign_runner.py` still owns that step somehow.** The recommended shape (stated here so you have a concrete proposal to bring to that conversation, not a blank page): Part 1's internal completion-callback handler calls a single function you own, e.g. `app/services/extraction_runner.py::resolve_and_triage(campaign, result_schema, transcript, escalate_on_negative) -> CallOutcome`, mirroring exactly how the old (deleted) `webhooks.py` called into `outcome_extraction.py`'s `_resolve_outcome()`. This keeps the vendor-facing boundary (Part 1's) separate from the triage domain logic (yours), the same separation of concerns `CLAUDE.md` already asks for.

---

## 3. Task list — extraction and completeness (ADR-5) — start here

### P2-T1 — `check_extraction_completeness()` (pure domain function)

New file `apps/api/app/domain/extraction.py`, sibling to `triage.py`, following its exact conventions (module docstring, no I/O, fully unit-testable):

```python
def check_extraction_completeness(extracted: dict[str, Any], required: list[str]) -> list[str]:
    """Which required fields came back missing or null. Empty list = complete."""
```

- Treat a key that's absent, `None`, or an empty string as "missing" — check with the person who owns product copy whether an empty string should count as missing for `string` fields (the plan doesn't specify this edge case; make a decision, document it in the docstring, and write a test for it either way).
- No I/O, no imports from `services`/`api`/`database` — this lives in `domain/` specifically so it stays testable without a database, matching `CLAUDE.md`'s own stated reason `triage.py` and `safety.py` are held up as the SRP exemplar.
- New test file `apps/api/tests/test_extraction.py`, mirroring `test_triage.py`'s style (plain `def test_...()` functions, no fixtures beyond plain dicts).

### P2-T2 — the extraction + completion-judgment LLM call

New file `apps/api/app/services/extraction_runner.py` (services/, not domain/, because this makes a real LLM call — I/O):

- Builds an extraction prompt from the campaign's **existing, unchanged** `result_schema` (the same JSONB column already produced by `build_result_schema()` — nothing about how a campaign declares fields changes) plus the full transcript.
- Calls the org's configured LLM. This goes through the **same per-org OpenRouter key** Part 1 provisions (ADR-7) — you are a *consumer* of that key, not a provisioner of it. Part 1's runbook commits to exposing `apps/api/app/integrations/openrouter/client.py::get_conversational_llm(voice_agent) -> ConversationalLLM` for exactly this purpose (their P1-T10) — use that, don't hardcode an OpenRouter SDK call directly in this file. This is a second real reason `VoiceProvider`-style protocol boundaries matter. If that function isn't ready yet when you reach this task, stub it behind the same signature yourself and swap to the real one once Part 1 lands it — don't block on this to keep writing the prompt logic and completeness check.
- Also asks for a holistic completion judgment — the direct replacement for CALL-E's `task_completed` field, which `triage.py`'s rule 4 (`outcome.task_completed is False`) already reads and which you are **not** removing (it's vendor-neutral in shape, only its producer changes). This is a real prompt-engineering deliverable: design and test the prompt like any other product surface, not as plumbing. Budget real iteration time here.
- **Extraction failure handling — do this deliberately, not as an afterthought (ADR-5 point 6, explicitly called out because an earlier draft of the plan got this wrong).** If the extraction LLM call times out, hits a rate limit, or returns malformed JSON: retry a bounded number of times (mirror `campaign_runner.py`'s own `_RETRYABLE_FAILURES` bounded-retry instinct for the dial itself — a couple of attempts for transient failures, not infinite). If it still fails, treat it as if **every** required field were missing, with a distinct reason text:
  ```python
  disposition_reason = "Structured extraction failed - review the transcript directly"
  ```
  rather than reusing the generic "fields missing" wording — a human reviewing the escalations worklist needs to tell "the agent had the conversation but didn't get the data" apart from "CallFlow's own extraction step broke," since those need different follow-up. **Do not let this fall through to a silent `AUTO_CLOSED`** — that is exactly the "success state for something that did not happen" `CLAUDE.md` non-negotiable #9 forbids, and the plan calls this out as a real bug an earlier draft actually had.
- Function signature (the recommended integration seam from §2 above): `resolve_and_triage(campaign: Campaign, result_schema: dict, transcript: str, *, escalate_on_negative: bool) -> CallOutcome`. Internally: build the base outcome, call the extraction LLM, run `check_extraction_completeness()`, populate `missing_required_fields`, call `triage()`, return.

### P2-T3 — `CallOutcome.missing_required_fields`

- `apps/api/app/domain/entities.py`: add `missing_required_fields: list[str] = Field(default_factory=list)` immediately after the existing `attempts: list[AttemptSummary] = Field(default_factory=list)` field (line 142) — same grouping as the other CALL-E-judgment-adjacent fields.
- New migration, following the **exact precedent** of `apps/api/alembic/versions/202608091600_call_outcome_completion_signals.py` (a plain `op.add_column`, no RLS changes needed since `call_outcomes`' RLS already applies to any new column on the same table):
  ```python
  op.add_column(
      "call_outcomes",
      sa.Column(
          "missing_required_fields",
          postgresql.ARRAY(sa.Text()),
          server_default="{}",
          nullable=False,
      ),
      schema="public",
  )
  ```
  Use a Postgres native `text[]`, not `jsonb` — decided explicitly in ADR-4: it's always a flat list of field names with no nesting, and `text[]` supports a plain `array_length(...) > 0` filter if you ever need one server-side.
- `apps/api/app/database/repositories/runs.py`'s `append_outcome()`: add `missing_required_fields` to the `INSERT`'s column list, the `values(...)` placeholder list (currently `$1`–`$20`, becomes `$1`–`$21`), the positional argument list, and the `on conflict ... do update set` clause (`missing_required_fields = excluded.missing_required_fields`). Also add it to `list_outcomes()`'s `SELECT` column list.
- `apps/api/app/api/v1/routes/runs.py`'s `get_run()`: add `"missing_required_fields": o["missing_required_fields"]` to the per-outcome dict it builds (alongside `task_completed`/`evidence`/`attempts`).
- `apps/web/lib/api.ts`'s `Outcome` interface: add `missing_required_fields: string[];`.

### P2-T4 — the new `triage.py` rule

Replace exactly `apps/api/app/domain/triage.py` lines 83–85 with:

```python
elif status == "completed" and outcome.missing_required_fields:
    updates["disposition"] = Disposition.ESCALATED
    updates["disposition_reason"] = (
        f"Missing required fields: {', '.join(outcome.missing_required_fields)}"
    )

elif status == "completed":
    updates["disposition"] = Disposition.AUTO_CLOSED
    updates["disposition_reason"] = "Conversation completed with no escalation signals."
```

Reasoning already settled by the plan and worth restating so you don't second-guess the placement: this pair only fires for a call that reached `status == "completed"` — rules 5–7 above it (negative-sentiment retry, busy/no-answer/voicemail, failed/canceled) all cover calls that never had a real chance to provide the data at all, and checking *those* for missing fields would override a more useful "worth retrying" signal with a less useful "fields missing" one. Do not move this check earlier in the chain.

- `apps/api/tests/test_triage.py`: add tests for (a) a completed call with `missing_required_fields` non-empty escalates with the right reason text, (b) a completed call with an empty list still auto-closes (regression test — this is `test_clean_call_auto_closes`, verify it still passes unmodified since your new `elif` only fires when the list is non-empty), (c) confirm rule ordering still holds — the existing `test_task_not_completed_beats_negative_sentiment_retry`-style precedence tests should not need to change.

---

## 4. Task list — `voice_agents` API and Agentic tab

### P2-T5 — `voice_agents` CRUD API

New file `apps/api/app/api/v1/routes/voice_agents.py` (CRUD only — connect-number endpoints live in Part 1's `routes/telephony.py`, see integration table in §7). Follow `routes/campaigns.py`'s exact shape (it's the closest existing precedent: built-in-vs-custom split doesn't apply here, but the `CampaignIn`/`CampaignOut`/list/create/update/delete/permission-dependency pattern does):

```python
class VoiceAgentIn(BaseModel):
    name: str
    kind: Literal["custom", "prebuilt"]
    stt_provider: str | None = None
    stt_credential_id: UUID | None = None
    tts_provider: str | None = None
    tts_credential_id: UUID | None = None
    llm_provider: str | None = None
    llm_credential_id: UUID | None = None
    llm_model: str | None = None
    prebuilt_persona: str | None = None
    system_prompt: str | None = None
    voice_id: str | None = None

class VoiceAgentOut(VoiceAgentIn):
    id: UUID
    org_id: UUID
    telephony_status: Literal["disconnected", "pending", "provisioning", "verified", "failed"]
    created_at: datetime
    created_by: UUID | None
```

- Validate `llm_model` is required when `llm_provider == "openrouter"` (ADR-4 point 3) — a 400 with a specific message, matching `CLAUDE.md`'s error-writing convention ("state what happened and what to do next"), e.g. `"llm_model is required when llm_provider is 'openrouter' - pick a model."`
- `telephony_status` is derived by joining against Part 1's `telephony_provisioning` table (latest row per `voice_agent_id`, or `"disconnected"` if none exists) — this is the one place your route touches Part 1's table, read-only.
- New repository `apps/api/app/database/repositories/voice_agents.py`, raw asyncpg, same shape as `repositories/campaigns.py`.
- New permissions in `apps/api/app/auth/permissions.py` (**you own this edit** — coordinate with Part 3, who also adds entries to this same file for chat, see §7): `Permission.AGENTS_READ` (every role — `_READ_ONLY` set), `Permission.AGENTS_WRITE` (operator and above — add to `_OPERATOR`), `Permission.AGENTS_DELETE` (admin/owner only — add to `_ADMIN`). Follow the existing enum-plus-role-set pattern exactly (see `CAMPAIGNS_READ`/`WRITE`/`DELETE`'s own placement for the template).
- **Deliberate breadth decision, already made by the plan — implement it as stated, don't narrow it:** everyone with `AGENTS_WRITE` sees every voice agent's configuration in the org, unlike campaigns' per-creator visibility silo. A voice agent's STT/TTS/LLM/telephony configuration is infrastructure, the same breadth logic that already makes `provider_credentials` org-wide rather than per-creator. Do not add an RLS-level per-creator narrowing to `voice_agents` — that would contradict this explicit decision.

### P2-T6 — Agentic tab frontend

- New route: `apps/web/app/(app)/app/agentic/page.tsx` (list) and likely `apps/web/app/(app)/app/agentic/[id]/page.tsx` (editor), mirroring the exact structure `campaigns/page.tsx` + `campaigns/[id]/page.tsx` + `campaign-editor.tsx` already use.
- Nav entry in `apps/web/components/layout/app-nav.tsx`'s `NAV_ITEMS` array (line 34–42) — **add it as a new top-level entry alongside Dashboard/Campaigns/Runs/Needs a person/Contacts**, not under Settings (per ADR-4: creating/connecting an agent is a first-run-blocking action once §9 lands, not an occasional configuration change). This edit is shared with Part 3, who also adds a nav entry for chat — see §7 for how to avoid stepping on each other.
- Two sections, per ADR-4: **"Your agents"** (list of org's `voice_agents`, opening an editor: name → STT provider+credential → TTS provider+credential → LLM provider+credential (+model when OpenRouter) → system prompt → voice selection → **Connect a number**), and **"Prebuilt"** (the CallFlow-operated agent, persona picker only — see P2-T9).
- The "Connect a number" step is where you integrate with Part 1's endpoints: `POST /api/v1/voice-agents/{id}/connect-number` (starts provisioning) and `GET .../connect-number` (poll status). Build your UI against the `ConnectNumberIn`/`ProvisioningStatusOut` shapes the plan already specifies in ADR-4, using `apps/web/app/(app)/app/settings/integrations/page.tsx`'s `ConnectDialog` component as your structural template (it already has the exact "paste credentials, save, show connected state" shape you need — you're building the same interaction one layer up, against a `voice_agent` instead of a bare `provider_credentials` row) — the state machine is `pending → provisioning → verified → failed`, each with distinct UI (a spinner for `provisioning`, `last_error` shown verbatim for `failed` per `CLAUDE.md`'s error-writing convention, never a generic message, with a "try again" action that starts a **new** attempt, not a retry of the stuck one).
- Poll for status the same way `use-run-poll.ts` polls a run (a `setInterval` + cancel-on-unmount pattern) — there's no Realtime hook available to you (Part 3 is building the only one, for chat, and it's not a shared utility as of when you'll need this).
- Permission-gated per P2-T5's new permissions: viewer sees the list read-only, operator+ can create/edit, admin/owner can delete. The nav item itself shows for every role (read access), matching how Campaigns/Runs already work.

### P2-T7 — §9 run-start rejection + A0.4 honest empty states

- `apps/web/app/(app)/app/runs/new/page.tsx`: the `blocker` `useMemo` (lines 82–105) already centralizes every reason "Start run" can be disabled, with a specific message, matching exactly the pattern §9 needs. Add a new check in this chain: if the selected campaign has no `voice_agent_id`, or its agent has no verified connected number, block with `"This campaign needs a voice agent with a connected phone number before it can start a run."` — this replaces (once Part 1's runtime is real) the current `!health?.api_key_configured` check, which is CALL-E-specific and should be removed once this lands, not kept alongside it.
- **Until Part 1's runtime is real, this same file needs the honest "calling unavailable" state (A0.4) as your very first task in this area** — don't wait for `voice_agents` to exist to say the true thing right now: calling is not available at all. Replace the current blocker chain's dependency on `health.api_key_configured` (which will always be false the moment Part 1 deletes `CALLE_API_KEY`) with a plain, always-true block during the gap: `"Calling isn't available right now — the voice platform migration is in progress."` Use the existing `NotWiredNotice` component (`@/components/app/settings-section`, already imported in this file) rather than inventing a new notice pattern.
- Same honest-state check applies to every other "Start a run" entry point — grep the codebase for `router.push('/app/runs/new'` and `?campaign=` query param usages (the dashboard's per-campaign "Run" shortcuts) and confirm each one either routes through this same composer (inheriting the fix for free) or needs its own equivalent notice.
- `apps/api/app/api/v1/routes/runs.py`'s `start_run()`: add the server-side version of the same check (never trust the frontend alone) — reject with `400` and the same message once a campaign has a `voice_agent_id` concept to check (this lands after P2-T5's schema exists; until then, the existing `if not config.api_key` check that already 400s is the honest gate — do not remove it prematurely, only replace it once the real voice-agent check is ready to take its place).

### P2-T8 — Needs-a-person: missing-fields badge (A4.1)

- `apps/web/components/app/escalation-card.tsx`: the reasoning `chain` (built in `buildChain()`, lines 184–202) already renders `disposition_reason` verbatim (line 190–192) — your new triage rule's reason text ("Missing required fields: ...") will already appear in the chain with **zero code change**. What's missing is a **visually distinct badge** so this reads as a different *kind* of escalation from a sentiment-driven one at a glance, not just different wording buried in the chain. Add a `Tag` (already imported, `@/components/ui/badge`) rendered when `outcome.missing_required_fields?.length` is non-zero, e.g. `<Tag tone="warning">Missing fields</Tag>` positioned near the existing lamp/name row (around line 56–64).
- `apps/web/app/(app)/app/escalations/page.tsx`: the existing `reasonFilter` (lines 29, 34–40, 108–120) is built from the **raw, free-text** `disposition_reason` string — your new rule's reason text embeds the specific missing field names per call, so it will never repeat exactly and won't group cleanly under this filter as-is. Add a second, purpose-built filter instead of trying to force it through the existing one: a toggle/select distinguishing "All reasons" / "Missing fields" / "Sentiment or frustration", computed from `outcome.missing_required_fields?.length > 0` rather than string-matching `disposition_reason`. Keep the existing campaign/reason filters unchanged alongside it.
- `apps/web/lib/api.ts`: confirm `missing_required_fields` (added in P2-T3) is present on the `Outcome` interface before wiring the UI against it.

### P2-T9 — Campaign editor: required-fields prominence (A4.2)

- `apps/web/components/app/campaign-editor.tsx` already has the `required` checkbox per field (confirmed at lines 572–577: `checked={field.required}` / `onCheckedChange={(v) => updateField(field.id, { required: v })}`). Your job is making the aggregate more visible, now that it's enforced rather than decorative: add a small summary near the field list (e.g. "3 of 6 fields required" or similar), and update the JSON-schema preview panel (`previewSchema()` in `apps/web/lib/campaign-fields.ts`, lines 126–173, already correctly builds a `required` array — no logic change needed there, just make sure the editor surfaces it prominently, not only in the raw JSON preview most users never open).

### P2-T10 — docs rewrite

`apps/web/app/(marketing)/docs/result-schemas/page.mdx`: the "Nothing is required except the two defaults" section (lines 48–55) states as product philosophy the *opposite* of what you just built — "If a field being missing means the call was not useful, that belongs in your triage reading of the results, not in forcing the agent." Rewrite this section to describe the real, current behavior: a field marked required is now enforced by a completeness check after the call, and a completed call missing one is escalated to "Needs a person" with the specific fields named, rather than silently trusted. Keep the rest of the page (the two-fields-you-always-get table, the types table, the extraction-happens-during-the-call section) — none of that changes; only this one section contradicts the shipped feature and needs rewriting, not the whole page.

### P2-T11 — A3.3: OpenRouter model picker UI

Once Part 1's OpenRouter provisioning (their P1-T10) exposes a way to list available models for an org's key, build the Agentic tab's LLM-provider step (P2-T6) to browse/pick from the real OpenRouter model list when `llm_provider == "openrouter"`, rather than a fixed curated dropdown — this is flagged in the plan (§10) as a real, evidence-backed differentiator nobody else in the market has built. Depends on Part 1 exposing the model list somehow (likely a thin passthrough of OpenRouter's own models endpoint) — coordinate the exact response shape with them when you reach this task; don't block earlier Agentic-tab work on it.

### P2-T12 — A4.3: prebuilt agent UI

The "Prebuilt" section of the Agentic tab (P2-T6): a persona picker only, no STT/TTS/LLM configuration exposed — the underlying credentials are CallFlow's own, wired by Part 1 (their P1-T11, alongside the second STT/TTS adapter). Your job is purely the UI: a card per available persona, "Use this agent" action that creates a `voice_agents` row with `kind = 'prebuilt'` and the chosen `prebuilt_persona`, no telephony connection step required (CallFlow's own number, not the org's).

---

## 5. Task list — CALL-E removal (your half)

Part 1 owns deleting the backend vendor code (their §3). Your half:
- Confirm no frontend code references CALL-E-specific concepts directly (a grep for `dry_run`, `CALLE`, `call-e` across `apps/web` should already return nothing per `CLAUDE.md`'s own claim that `dry_run` was fully removed in an earlier iteration — verify this claim rather than trusting it, since you're the one now depending on it being true).
- A0.4's honest empty states (P2-T7 above) are your actual deliverable here, not a separate task — do not schedule this twice.

---

## 6. Step-by-step implementation order

1. **P2-T1** (`check_extraction_completeness`) — zero dependencies, do this first, same day you start.
2. **P2-T3** (schema: `missing_required_fields` field + migration + repository/route plumbing) — small, mechanical, unlocks P2-T4's tests.
3. **P2-T4** (triage rule) — depends on P2-T3's field existing on `CallOutcome`.
4. **P2-T7's honest-empty-state half** (A0.4) — do this in parallel with 1–3; it only touches the frontend and has no backend dependency. Ship it early so the dashboard never lies about calling being available while the rest of this work is in flight.
5. **P2-T2** (extraction LLM call) — start the prompt-design work in parallel with 1–4 using a hand-supplied transcript fixture (no LiveKit dependency needed per the plan's own note); finalize the actual LLM-calling wiring once Part 1 exposes their per-org LLM client interface.
6. **P2-T5** (`voice_agents` CRUD API) — start your Pydantic models and a locally-stubbed repository the moment Part 1 gives you the column list (day one, per their commitment in §2); swap to the real migration once it merges.
7. **P2-T6** (Agentic tab UI) — build against P2-T5's API once it's real; the "Connect a number" step specifically depends on Part 1's `telephony.py` endpoints existing.
8. **P2-T8, P2-T9, P2-T10** (Needs-a-person badge, campaign editor prominence, docs rewrite) — all depend only on P2-T3/P2-T4 being merged; can run in parallel with 6–7.
9. **P2-T11, P2-T12** (model picker, prebuilt agent) — later, depend on Part 1's A3 work.
10. **Joint integration checkpoint with Part 1**: the end-to-end first real call (their A1.7) — your `extraction_runner.resolve_and_triage()` needs to be callable from wherever Part 1's completion callback lands by this point.

---

## 7. Integration points, shared files, and how to avoid conflicts

| Shared item | What you do | What Part 1 does | How to sequence it |
|---|---|---|---|
| `apps/api/app/services/campaign_runner.py` | Nothing, directly — your extraction/triage logic lives in the new `extraction_runner.py`, called from wherever Part 1's completion callback lands, not from inside `campaign_runner.py` itself | Stubs then rewires the dial call (their P1-T2/P1-T6) | You should not need to edit this file at all if the integration seam in §2 holds. If it turns out you do, coordinate with Part 1 first — this is their file. |
| `voice_agents`/`telephony_provisioning` migration | You consume the `voice_agents` columns for your CRUD API | Part 1 authors and lands the migration | Don't wait for the merge — build your Pydantic models and a stub repository against the column list Part 1 gives you on day one (see their runbook §6). |
| `apps/api/app/api/v1/routes/voice_agents.py` vs. `telephony.py` | You own `voice_agents.py` (CRUD: list/create/update/delete) | Part 1 owns `telephony.py` (connect-number/status, same URL prefix) | **Two files, not one** — this is the single highest-value conflict-avoidance move in the plan, and both runbooks agree on it. Don't let anyone talk you into merging them back into one file for "consistency with the plan's own draft." |
| `apps/api/app/auth/permissions.py` | You add `AGENTS_READ`/`AGENTS_WRITE`/`AGENTS_DELETE` | Part 3 adds `MESSAGES_READ`/`MESSAGES_SEND` (unrelated) | Purely additive enum entries in different logical groups. Rebase before you push if it's been a few days; a merge conflict here, if it happens, is a two-line resolve, not a design problem. |
| `apps/web/components/layout/app-nav.tsx` | You add the Agentic nav item | Part 3 adds a Chat nav item | Same additive-array situation. Check `git log` on this file before you start your edit if it's been a while since you last pulled — if Part 3 already landed their entry, add yours after it rather than reordering the array. |
| `apps/api/app/api/v1/routes/runs.py` | You add the §9 rejection logic inside `start_run()` | Part 1 deletes `get_call_events` and the engine imports | Different regions of the same file, and Part 1's deletion happens first (day one of their work). No real conflict if you don't start your edit until their CALL-E-removal PR has merged. |
| `apps/api/app/domain/entities.py` | You add `CallOutcome.missing_required_fields` | No edits expected from Part 1 | Low risk. |

---

## 8. Testing requirements

- `apps/api/tests/test_extraction.py` (new): `check_extraction_completeness()` against missing/null/present/empty-string cases, no I/O, no fixtures beyond plain dicts — mirror `test_triage.py`'s style exactly.
- `apps/api/tests/test_triage.py`: add the two new tests described in P2-T4; re-run the full file and confirm all 19 existing tests still pass unmodified (this is your regression guarantee that you didn't disturb rule ordering).
- `apps/api/app/services/extraction_runner.py`: test the retry-then-fail-safe path explicitly — a mocked LLM client that always errors should produce a `CallOutcome` with every required field in `missing_required_fields` and the distinct "Structured extraction failed" reason text, never a silent `AUTO_CLOSED`. This is the single most important test in this whole runbook per the plan's own adversarial-review callout — do not skip it.
- Cross-tenant RLS test for `voice_agents` reads through your CRUD API (even though Part 1 owns the migration's RLS policies, you own the route layer — confirm org B's session genuinely cannot list/edit org A's agents via your endpoints, not just that the SQL policy exists).
- Frontend: manually verify the Needs-a-person filter correctly separates a missing-fields escalation from a sentiment-driven one using two fixture outcomes (no test framework currently covers `apps/web` component behavior beyond `tsc`/`eslint` per the repo's existing conventions — don't introduce a new frontend test runner for this alone; a manual verification pass plus type-checking is proportionate here, matching how the rest of `apps/web` is verified today).
- `npm run lint`, `npm run type-check`, `npm run build` must stay clean (`CLAUDE.md` §7).
- `ruff check app tests` and `pytest -q` must stay clean in `apps/api`.

---

## 9. Validation checklist / Definition of Done

- [ ] `check_extraction_completeness()` exists in `app/domain/extraction.py`, pure, tested, no I/O.
- [ ] `CallOutcome.missing_required_fields` exists end-to-end: entity field → migration → repository INSERT/UPDATE/SELECT → API response → `lib/api.ts` type.
- [ ] `triage.py`'s new rule is in place at exactly the right position (after the retryable/unreachable rules, gated on `status == "completed"`), and all pre-existing `test_triage.py` tests still pass.
- [ ] An extraction failure (simulated via a mocked always-erroring LLM client) never produces `AUTO_CLOSED` — it produces an `ESCALATED` outcome with every required field listed as missing and the distinct "Structured extraction failed" reason.
- [ ] `voice_agents` CRUD API is fully permission-gated (`AGENTS_READ`/`WRITE`/`DELETE`) and has a passing cross-tenant isolation test.
- [ ] The Agentic tab exists at `/app/agentic`, is in the primary nav, lists/creates/edits agents, and its "Connect a number" step correctly polls Part 1's provisioning-status endpoint through all four states (`pending`/`provisioning`/`verified`/`failed`), showing `last_error` verbatim on failure.
- [ ] Every "Start a run" entry point shows an honest, specific "calling isn't available" message right now (before Part 1's runtime exists) and the real "needs a voice agent with a connected number" rejection once it does — never a silent failure or a stale CALL-E-era message.
- [ ] The Needs-a-person worklist visually distinguishes a missing-fields escalation from a sentiment-driven one, and its new filter works against real fixture data.
- [ ] The campaign editor visibly surfaces how many fields are marked required.
- [ ] `apps/web/app/(marketing)/docs/result-schemas/page.mdx`'s "nothing is required" section no longer contradicts the shipped feature.
- [ ] `npm run lint && npm run type-check && npm run build` and `ruff check app tests && pytest -q` are both clean.
- [ ] `SYSTEM.md`/`ISSUES.md` updated for everything in this runbook that changed the API, schema, or module layout.
