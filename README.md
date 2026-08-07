<div align="center">

# CallFlow AI

**An operations layer for outbound phone calls.**

Feed in contacts and a goal. CallFlow AI dials, holds real conversations,
extracts typed results, and escalates only what needs a person.

[![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js%2016-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![Tests](https://img.shields.io/badge/tests-85%20passing-3fb950)](#tests)
[![Live](https://img.shields.io/badge/live-callflow--ai.brbik.com-4f46e5)](https://callflow-ai.brbik.com)

</div>

---

## The problem

Outbound calling costs enormous manual effort and buys you no visibility.

In a normal call log, a delighted customer and a furious one look identical —
both just say `completed`. Teams burn hours dialing, repeating the same five
questions, and typing notes into a CRM afterwards. You find out a call went
badly when someone escalates, which is far too late.

**CallFlow AI turns every conversation into typed data the moment it ends**, so
the work that needs a human is visible immediately and the rest closes itself.

---

## What it does

| | |
|---|---|
| **Campaigns, not scripts** | Write a goal in plain English. The agent improvises the conversation and adapts when people go off-script. |
| **Typed results** | Every call returns schema-validated JSON via the engine's native `result_schema`. No transcript scraping. |
| **Sentiment triage** | Frustration and opt-outs escalate to a person. Bad timing is queued for a polite retry. Clean calls auto-close. |
| **Build your own** | Create unlimited campaigns from the dashboard with custom extraction fields. |
| **Safe by default** | Every dial passes an E.164 check, an allowlist, a per-run ceiling, rate limiting, a shared daily budget, and the suppression list — any guard that can't complete denies the call. |

---

## Architecture

```
  Next.js dashboard              FastAPI orchestrator         voice engine
  -----------------   -- HTTP ->  --------------------  -- SDK ->  ------
  campaigns                       safety gate                     dials
  contact table                     E.164 validation              speaks
  live results                      allowlist                     adapts
                                    rate limit                    listens
                                    call ceiling
                                          |
                                          v
                                    result_schema   -- typed JSON back
                                          |
                                          v
                                        triage
                                          |
                    +---------------------+---------------------+
                    |                     |                     |
                    v                     v                     v
               auto-close            retry later           needs human
```

**The voice engine is the calling agent.** It owns the phone number, dialer, speech
recognition, conversational model, turn-taking, voicemail detection, and IVR
handling. CallFlow AI is the operations layer around it.

---

## Quick start

**Backend** — Python 3.11+

```bash
cd apps/api
python -m venv .venv
.venv/Scripts/activate           # Windows  ·  source .venv/bin/activate on Unix
pip install -e ".[dev]"

cp ../../.env.example ../../.env # repo root — config.py reads it from there
uvicorn app.main:app --reload --port 8000   # → http://127.0.0.1:8000
```

**Frontend** — Node 20+

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev                      # → http://localhost:3000
```

Set `CALLE_API_KEY` to the Voice API key from your voice-engine provider — new
accounts include free calls.

Auth and persistence run on Supabase: a project gives you a Postgres database, a
JWKS URL, and publishable/secret keys. Set `SUPABASE_URL`, `SUPABASE_JWKS_URL`,
`DATABASE_URL`, and `SUPABASE_SECRET_KEY` for the API, and
`NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` for the frontend,
then run the Alembic migrations in `apps/api/alembic/versions/` against that
database. See `SUPABASE_SETUP.md` for the exact dashboard steps.

---

## Try it live

**→ [callflow-ai.brbik.com](https://callflow-ai.brbik.com)**

There is no more anonymous "enter your number and see what happens" demo —
the dashboard requires an account. Sign up, and you get an organisation of
your own with Supabase-backed auth and roles (owner, admin, operator,
viewer). From there you can create a campaign, load contacts, and start a
run, which **places real phone calls** — every run dials for real,
unconditionally, from the first one.

Only call a number you own or have permission to call. The run stays inside
the safety guards below regardless of who starts it: the allowlist, the
per-run ceiling, the rate limiter, the shared daily budget, and the
suppression list all still apply.

---

## Safety

> **CallFlow AI places real phone calls.** There is no dry-run mode — every run
> dials for real, unconditionally, from the first one. That is a deliberate
> product decision, not a gap: it means the guards below are what actually
> stands between "started a run" and "rang a real phone", so every one of them
> fails closed.

| Guard | Behaviour |
|---|---|
| E.164 validation | Malformed numbers are rejected before reaching the engine. |
| `CALLFLOW_ALLOWLIST` | When non-empty, only these E.164 numbers can be dialed. |
| `CALLFLOW_MAX_CALLS_PER_RUN` | Hard ceiling per run. Protects your credit balance. |
| `CALLFLOW_RATE_LIMIT_CALLS` | Calls allowed per IP per window (default 5/hour). |
| `CALLFLOW_DAILY_BUDGET` | Shared daily call ceiling across the whole deployment. |
| Suppression list | A contact who opted out is looked up by a peppered phone hash before every dial and denied, regardless of who starts the run. |

The allowlist and the rate limiter solve different problems. **Use the
allowlist for private development** — it makes dialing anyone but yourself
impossible. **Use the rate limiter in production** so no single run, or no
runaway retry loop, can drain the account.

Set `CALLFLOW_OWNER_KEY` and send it as an `X-CallFlow-Owner-Key` header to
lift the rate limiter for your own testing.

Phone numbers are masked (`+15******100`) in every log, API response, and UI
surface. All sample data uses reserved fictional numbers (`+1 555 0100–0199`)
that cannot connect to a real person.

**While developing, set an allowlist to your own number** — with no dry run,
that's the guard that keeps a bug from calling someone who isn't you.

Starting a run at all requires the `runs:start` permission (owner, admin, or
operator — not viewer), since every run now spends real credits.

---

## How a campaign works

A campaign is a **goal template** plus a **result schema**:

```python
Campaign(
    id="travel-discovery",
    name="Travel enquiry follow-up",
    goal_template=(
        "You are CallFlow AI, a friendly travel consultant calling {name} "
        "back about their holiday enquiry.\n\n"
        "Open by greeting them by name and confirming this is a good time. "
        "If it is not, apologise, ask when to call back, and end politely.\n\n"
        "Known context: {enquiry_note}\n\n"
        "If they sound annoyed, do not push. Offer a human colleague instead."
    ),
    region="IN",
    language="en",
)
```

The engine returns this, validated against the schema:

```json
{
  "outcome": "interested",
  "sentiment": "positive",
  "frustration_signals": false,
  "destination": "Dubai",
  "travel_date": "2026-12-18",
  "party_size": 4,
  "summary": "Wants a 4-person Dubai package in mid-December."
}
```

Triage reads those typed fields — never prose — to decide the disposition.

### Triage rules

| Signal | Disposition |
|---|---|
| Asked never to be called again | **Needs human** — suppress and log |
| Explicitly asked for a person | **Needs human** |
| Frustration detected | **Needs human** |
| Negative tone, no frustration | **Retry later** — a bad time isn't a bad mood |
| Busy / no answer / voicemail | **Retry later** |
| Completed, no escalation signals | **Auto-closed** |

---

## API

Every endpoint below except `/api/health` requires `Authorization: Bearer
<supabase-access-token>` and resolves to one organisation, so results are
always scoped to the caller's org — enforced again at the database by RLS.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Backend status and active safety settings — unauthenticated |
| `GET /api/v1/campaigns` | List built-in and org-created campaigns |
| `POST /api/v1/campaigns` | Create a campaign with custom extraction fields |
| `DELETE /api/v1/campaigns/{id}` | Remove a user-created campaign |
| `POST /api/v1/campaigns/preview` | Render goals without touching the voice engine |
| `POST /api/v1/runs` | Start a run — dials for real, in the background |
| `GET /api/v1/runs` | List the org's runs |
| `GET /api/v1/runs/{id}` | Poll a run's status, outcomes, and stats |

---

## Project layout

```
apps/api/app/                     FastAPI backend
├── main.py                       app assembly, lifespan, CORS
├── api/v1/routes/                HTTP endpoints — campaigns, runs, organisations, invitations, profile
├── core/                         config.py, rate_limit.py
├── auth/                         tokens.py, dependencies.py, permissions.py
├── database/                     models.py, session.py, privileged.py, repositories/
├── domain/                       entities, safety, triage, result_schemas, campaigns — pure, no I/O
├── services/campaign_runner.py   gate → dial → poll → triage
└── integrations/voice/engine.py  the one voice-SDK import

apps/api/alembic/                 migrations (psycopg; runtime uses asyncpg)
apps/api/tests/                   9 files, 85 tests

apps/web/                         Next.js 16 dashboard
├── app/(marketing) (auth) (app)  public site, login/signup, the dashboard
├── components/                   brand, ui, marketing, app, layout
└── lib/                          typed API client, Supabase clients, formatters
```

---

## Tests

```bash
cd apps/api && pytest -q     # 85 passed
```

Coverage focuses on what can cause harm: the safety gate fails closed for bad
numbers, an exhausted ceiling, and a suppressed contact; masking never leaks
more than half a number; triage precedence is correct; and 11 tests hit a real
Postgres database directly to prove one organisation's rows — campaigns,
members, suppressions — are invisible and unwritable from another tenant's
session.

---

## Notes from the build

**`language` is not a valid recipient field** — it's `locale`. The API
rejects the former with a `422 extra_forbidden`, which is only discoverable from
the error payload.

**The engine validates task substance.** A thin goal like `"Call and ask about their
trip"` is rejected with `call_not_ready`. The goal must state what to say, ask,
and do on success or failure — the dashboard enforces a 40-character minimum.

**The goal field is the entire product.** A one-line task produced a confusing
robocall; the same platform with a well-written goal produced a consultant. That
difference is what CallFlow AI's campaign templates exist to manage.

---

## Status

**Working** — accounts and organisations with role-based permissions and
RLS-enforced tenancy, campaigns (built-in and user-created, persisted per
org), safety gate with an enforced suppression list, engine integration,
typed extraction, sentiment triage, CSV import, dashboard with live polling.
Every run places real calls; there is no dry-run mode.

---

## Future enhancements

### WhatsApp delivery

Right now the call ends with the agent saying a consultant will follow up. The
natural next step is to **send the contact everything that was agreed, in
writing, on WhatsApp** — so they have a record and the team has a receipt.

The structured result already contains everything the message needs:

```json
{
  "destination": "Dubai",
  "travel_date": "2026-12-18",
  "party_size": 4,
  "service_interest": "package",
  "ready_for_quote": true
}
```

A post-call step would render that into a template message and send it through
the WhatsApp Cloud API, keyed off the contact who just spoke.

Two constraints shape the design:

- **Consent must come from the call.** The agent has to ask, and the answer has
  to land in the schema as a typed field, before anything is sent. A silent
  message to someone who didn't agree is worse than no message.
- **Business-initiated messages need pre-approved templates.** WhatsApp only
  allows free-form replies inside a 24-hour window the user opened. Outside it,
  messages must use an approved template and are billed per conversation — so
  this is a paid, approval-gated integration, not a free bolt-on.

The config hooks (`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`) already exist
and read as empty strings when unset.

### Beyond WhatsApp

| | |
|---|---|
| **Booking tools** | Let a campaign call MCP tools — flights, hotels, tours — driven by the extracted outcome, so a confirmed intent books itself. |
| **Scheduled campaigns** | Recurring runs with time-zone-aware calling windows, so nobody is dialed at 3am local time. |
| **Inbound calls** | Handle calls coming *in*, not just going out. |
| **CRM write-back** | Push outcomes to HubSpot or Salesforce so results land where the team already works. |
| **Retry orchestration** | Act on the `retry` disposition automatically instead of only surfacing it. |

---

<div align="center">

Created by [BrBik](https://brbik.com)

</div>
