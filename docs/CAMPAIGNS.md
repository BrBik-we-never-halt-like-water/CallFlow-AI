# Campaigns in CallFlow AI: Design to Development

This document explains the Campaign feature — the core concept CallFlow AI is built
around — first as it's designed, then as it's actually implemented, and finally
where the two have drifted apart. File references point at the exact source so
each claim can be checked.

## 1. What a Campaign is (the design)

A **Campaign is a reusable template**, not a live outreach effort. It bundles two
things:

- a **goal**: a natural-language instruction telling the voice engine what the
  call should accomplish (`goal_template`)
- a **result contract**: a typed JSON schema describing what should be extracted
  from the conversation (`outcome_fields`)

It deliberately has no contacts, no schedule, and no calls attached to it. The
idea is that you define a campaign once ("confirm this appointment", "follow up
on this travel enquiry") and then execute it repeatedly against different
batches of contacts.

That execution is a separate concept: a **Run**. A Run pairs one Campaign with a
batch of contacts and a dry-run flag, and produces one `CallOutcome` per contact.
This split matters for reading the rest of this doc — **"starting a campaign"
always means "starting a Run against a campaign."** There's no "start campaign"
button anywhere; there's only "start a run."

## 2. Design: the intended data model

The `Campaign` model (`callflow/models.py:68-79`):

```python
class Campaign(BaseModel):
    id: str
    name: str
    goal_template: str                    # supports {name}, {context[key]}
    outcome_fields: dict[str, str] = {}   # field -> extraction instruction
    region: str | None = None
    language: str | None = None
    escalate_on_negative: bool = True
```

Related entities:

| Entity | Purpose | Source |
|---|---|---|
| `Contact` | `name`, `phone` (E.164-validated), `region`, `language`, free-form `context` dict merged into the goal template | `callflow/models.py:52-65` |
| `CallOutcome` | One row per call: transcript, summary, sentiment, extracted fields, disposition, dry-run flag, duration | `callflow/models.py:82-110` |
| `Disposition` | `in_flight \| auto_closed \| escalated \| retry \| unreachable \| skipped` | `callflow/models.py:39-49` |
| `Run` | `id`, `campaign_id`, `total`, `dry_run`, `status`, `outcomes[]` | `callflow/store.py:22-36` |

Every campaign — built-in or custom — automatically inherits a shared set of
triage fields on top of its own `outcome_fields`: `sentiment`,
`frustration_signals`, `wants_human_callback`, `do_not_call`, `summary`
(`callflow/schemas.py:15-44`). This is what lets triage work identically across
every vertical, regardless of what custom data a campaign asks for.

**What the model does *not* have, despite the editor UI suggesting otherwise:**
a calling window, a retry policy, a status, an owner, or a linked contact list.
The `Campaign` object is exactly the six fields above — nothing else survives
past the editor. See §4 for what that means in practice.

## 3. Development: how a campaign actually runs, end to end

### Author

`CampaignEditor` (`web/components/app/campaign-editor.tsx`) → `POST
/api/campaigns` (`callflow/api.py:122-147`, validates goal length ≥ 40 chars and
field types) → `register_campaign()` (`callflow/campaigns.py:124-165`, slugifies
the name into an id, merges extraction fields into the shared schema) → added to
an in-memory `REGISTRY: dict[str, Campaign]` (`callflow/campaigns.py:80`). There
is no database — a backend restart wipes every custom campaign back down to the
two seeded built-ins, `travel-discovery` and `appointment-reminder`
(`callflow/campaigns.py:15-83`).

### Browse / edit

`GET /api/campaigns` lists everything in the registry, rendered as
`CampaignCard`s (`web/components/app/campaign-card.tsx`) with a goal preview,
extraction-field tags, and a last-run lamp strip. Built-ins are read-only in the
UI (`campaigns/page.tsx:44-65`) and nudge the user toward "Duplicate" instead of
edit. The backend's actual route surface is:

```
callflow/api.py:117   @app.get("/api/campaigns")
callflow/api.py:122   @app.post("/api/campaigns", status_code=201)
callflow/api.py:150   @app.delete("/api/campaigns/{campaign_id}", status_code=204)
```

No `PUT`/`PATCH` exists (verified directly against source). See §4 for what the
"Edit" screen does instead.

### Preview

`POST /api/preview` (`callflow/api.py:160-176`) renders the goal template
against a contact with no engine call and no cost — pure string templating via
`render_goal()`.

### Run it

`RunComposer` (`web/app/(app)/app/runs/new/page.tsx`) — paste/import contacts,
pick a campaign, review the safety guard bar, toggle dry-run, Start — calls
`POST /api/runs` (`callflow/api.py:211-254`). The server validates the campaign
exists, contacts are non-empty and E.164-valid, and (for live runs) an API key
is configured and rate limits pass. Execution is handed to FastAPI
`BackgroundTasks.add_task()` — an in-process background task, not a real job
queue (`callflow/api.py:253`).

Per contact, `CampaignRunner.run_one()` (`callflow/orchestrator.py:186-294`)
does:

1. **Safety gate** — `check_dial_allowed()` (`callflow/safety.py:51-70`): E.164
   format, per-run call ceiling, allowlist.
2. **Render the goal** — missing template variables render as empty rather than
   erroring (`_Safe` dict).
3. **Dry run**: stops here and generates a synthetic outcome from
   `callflow/samples.py`, run through the *real* triage logic so the preview's
   disposition matches what a live call would get.
   **Live run**: `EngineGateway.start_call()` (`callflow/engine_client.py:53-85`)
   calls the underlying voice engine with the goal, the result schema, and an
   idempotency key.
4. **Poll** every 2 seconds up to a 900-second timeout
   (`_poll_until_done`, `callflow/orchestrator.py:145-184`) until the call
   reaches a terminal state.
5. **Extract** the structured result and transcript from whatever shape the
   engine returned.
6. **Triage** (`callflow/triage.py:25-80`) assigns a `Disposition` by fixed
   priority: `do_not_call` → `wants_human_callback` → `frustration_signals` →
   negative sentiment (if `escalate_on_negative`, → `RETRY`) → busy/no-answer/
   voicemail (→ `RETRY`) → failed/canceled (→ `UNREACHABLE`) → completed (→
   `AUTO_CLOSED`) → else `SKIPPED`.
7. Stored via `store.append_outcome()` (`callflow/store.py:38-57`), which
   matches on contact name + masked phone so a call's queued→ringing→completed
   lifecycle collapses into a single updated row rather than duplicating it.

### Observe / act on results

- Run detail page polls `GET /api/runs/{id}` every 2.5s
  (`web/lib/hooks/use-run-poll.ts`) and shows a live lamp-strip, results table,
  and transcript drill-down.
- **Escalations** (`web/app/(app)/app/escalations/page.tsx`) — a manual worklist
  of calls that `triage()` marked `ESCALATED`.
- **Contacts** (`web/app/(app)/app/contacts/page.tsx`) — not a real contact
  store; it's derived by grouping past `CallOutcome` rows, since that's the only
  contact data the service retains.

### UI inventory

| Page / component | Path | Role |
|---|---|---|
| Campaign list | `web/app/(app)/app/campaigns/page.tsx` | Grid of cards, filter tabs, delete/duplicate |
| Campaign editor | `web/components/app/campaign-editor.tsx` | Compose goal, fields, region/language, calling window, retry policy |
| New/edit campaign | `campaigns/new/page.tsx`, `campaigns/[id]/page.tsx` | Wrap the editor |
| Run composer | `web/app/(app)/app/runs/new/page.tsx` | Contacts → campaign → safety guards → start |
| Runs list | `web/app/(app)/app/runs/page.tsx` | Sortable/paginated run history |
| Run detail | `web/app/(app)/app/runs/[id]/page.tsx` | Live progress, results, transcripts, Pause/Stop |
| Escalations | `web/app/(app)/app/escalations/page.tsx` | Calls needing a human |
| Contacts | `web/app/(app)/app/contacts/page.tsx` | Derived contact list + suppression tab |

## 4. Where design and development diverge

The UI (and in one case, the public docs) design for behaviors the backend does
not actually deliver. This is the most important section for anyone picking up
this feature next — each of these is a real user-facing promise that doesn't
hold up server-side.

**Editing a campaign silently creates a duplicate, not an update.**
The "Edit" screen (`campaigns/[id]/page.tsx`) reuses the same
`CampaignEditor.save()` path as creation, which calls `api.createCampaign()`
(`campaign-editor.tsx:163-187`). Since the backend has no `PUT`/`PATCH`
route, saving an edited custom campaign registers a brand-new one with a new
id rather than updating the original in place.
→ *Next step: add `PUT /api/campaigns/{id}` and point the editor's save path
at it when `existing` is set.*

**"Stop run" doesn't stop the run.** The Stop button
(`runs/[id]/page.tsx:269-297`) only pauses the frontend's polling; there is no
cancel endpoint on the backend (`callflow/api.py` has no `DELETE` or similar
route for `/api/runs/{id}`). The confirmation dialog's own copy admits
*"Updates stopped, run not cancelled... Remaining calls will still be placed."*
→ *Next step: add a cancel endpoint that flips a flag `CampaignRunner` checks
between contacts.*

**Retry policy is configured in the UI but never executed.** The editor's
"Attempts after the first" / "Wait between attempts" controls
(`campaign-editor.tsx:320-338`) are local UI state only — `Campaign` has no
such fields (§2), and while `triage()` does assign `Disposition.RETRY` to
bad-timing calls, nothing in the codebase re-queues or re-dials a
retry-flagged contact. There is no scheduler.
→ *Next step: either remove the controls until retry execution exists, or add
a scheduled job that re-dials `RETRY` outcomes after the configured spacing.*

**Calling window is a display string, not a guardrail.** The editor's
"Calling window" control saves to `localStorage` only
(`web/lib/campaign-draft.ts`) and is never sent to the API. Worse, the safety
guard chip that's supposed to reflect it hardcodes the value
`"09:00–20:00 IST"` unconditionally (`web/components/app/safety-bar.tsx:133`)
regardless of what's actually configured. No code anywhere checks time-of-day
before dialing (`callflow/orchestrator.py`, `callflow/safety.py`).
→ *Next step: add a `calling_window` field to `Campaign` (or to run config),
enforce it in `check_dial_allowed()`, and derive the guard chip's display value
from real config instead of a literal string.*

**Suppression ("do-not-call") is browser-local only, despite UI copy promising
otherwise.** The Contacts page's suppression list lives in `localStorage`
(`web/lib/suppression.ts`) and its copy claims a number is "never dialled by
any campaign, ever." But `check_dial_allowed()` (`callflow/safety.py:51-70`) —
the actual dial gate — only checks E.164 format, per-run ceiling, and an
allowlist; it has no concept of a suppression list. A suppressed number could
be redialed from another device, another browser session, or by a teammate.
→ *Next step: move suppression server-side and check it in
`check_dial_allowed()`.*

**Extraction field types are silently downgraded.** The editor offers five
field types — `string | number | boolean | date | enum`
(`web/lib/campaign-fields.ts:17`) — but the backend's `FIELD_TYPES` only
accepts four (`callflow/campaigns.py:100`: `string, boolean, integer,
number`). `date` and `enum` are folded into `string` with the constraint
described in prose instead (`campaign-fields.ts:83-99`). The result is that
nothing validates a malformed date or an out-of-set enum value; the "type"
system only nudges the engine's extraction via a text description.
→ *Next step: extend the backend schema builder to emit real JSON Schema
`format: date` / `enum: [...]` constraints for these two types.*

**CSV-imported contact context is hardcoded to one vertical.**
`toContactInputs()` (`web/lib/contacts.ts:109-120`) always injects
`context: { enquiry_note, appointment_time: "tomorrow at 4pm" }` on every
imported contact, regardless of which campaign is selected. This is correct
for `travel-discovery` but wrong for `appointment-reminder` or any custom
campaign — every contact would be told their appointment is literally
"tomorrow at 4pm."
→ *Next step: derive the injected context keys from the selected campaign's
`outcome_fields`/template variables instead of a fixed shape.*

**Webhooks are documented but don't exist.** The public docs page
(`web/app/(marketing)/docs/webhooks/page.mdx`) fully describes a webhook
system — event types, HMAC signatures, a delivery log, retries. In reality,
`EngineGateway.start_call()` and `CampaignRunner` accept a `webhook_url`
parameter that's plumbed through but never populated
(`callflow/api.py:180-181` omits the keyword entirely, so it defaults to
`None`), and there is no receiving
endpoint anywhere in `callflow/api.py`. All progress updates are pulled via
polling, never pushed.
→ *Next step: either build the documented webhook receiver, or pull the docs
page down until it exists — right now it actively misleads readers.*

**Everything is single-process, in-memory state.** Campaigns
(`callflow/campaigns.py:80`), runs (`callflow/store.py:20`), and the rate
limiter (`callflow/ratelimit.py:33-35`) are all plain dicts behind a
`threading.Lock`. A restart discards every custom campaign and every run ever
recorded; a horizontally-scaled deployment would let each instance enforce
its own independent rate ceiling, defeating the "shared daily budget"
guarantee described in the rate limiter's own docstring. This is
self-documented as a known limitation, not a surprise
(`callflow/store.py:1-5`: *"Swap for Postgres by reimplementing this
interface"*).
→ *Next step: implement a Postgres-backed store behind the same interface,
then move the rate limiter to something shared (e.g. Redis) if the deployment
becomes multi-instance.*

## 5. Quick reference

**Run it locally:**

```bash
# backend
python -m venv .venv && .venv/Scripts/activate
pip install -e .
cp .env.example .env      # set CALLE_API_KEY
python run_api.py          # http://127.0.0.1:8000

# frontend
cd web
npm install
npm run dev                # http://localhost:3000
```

**Relevant env vars:** `CALLE_API_KEY` (voice engine key — required for live
calls), `CALLFLOW_DRY_RUN`, `CALLFLOW_MAX_CALLS_PER_RUN`, `CALLFLOW_ALLOWLIST`.

**Also worth reading:** `web/DESIGN_NOTES.md` (§5, §6, §11) — the team's own
prior notes cover several of the gaps in §4 above from the frontend side; this
document folds those into the full design-to-development picture rather than
duplicating them.
