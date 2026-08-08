# Working in this codebase

CallFlow AI is an **operations layer for outbound phone calls**. You load contacts and
write a goal in plain English; the system dials, holds a real conversation, and returns
schema-validated structured data. Clean calls close themselves; frustration, opt-outs, and
requests for a human get escalated.

**Read this file before writing code.** It is the contract for how work lands here.

---

## 1. The document map

| File | What it is | When you touch it |
|---|---|---|
| `CLAUDE.md` | This file — structure and conventions | When you add a folder or change a convention |
| `SYSTEM.md` | **As-built** reference: every module, every endpoint, every field | After any change to the API, schema, or module layout |
| `FEATURES.md` | **Target** state, F1–F52, with build order | Referenced throughout this file, `SYSTEM.md`, and `ISSUES.md` by `F<n>` number — but **the file itself does not exist in this repo, at any commit.** Write it for real before trusting an `F<n>` reference as anything more than a stable label; until then `SYSTEM.md` §12 is the closest thing to a real gap map |
| `ISSUES.md` | Living bug log, severity-ranked, per iteration | Whenever you find or fix a bug |
| `apps/web/DESIGN_NOTES.md` | Frontend design decisions and deliberate deviations | When you make a free-axis design choice |
| `SUPABASE_SETUP.md` | Dashboard settings a human must click | When a new provider setting is required |

Keeping `SYSTEM.md` and `ISSUES.md` current is part of the work, not paperwork after it.
A PR that changes an endpoint and not `SYSTEM.md` is incomplete.

---

## 2. Folder structure

Layered by responsibility, and every folder name says what is inside it. Dependencies
point **inwards**: `api → services → domain`, and `domain` imports nothing outward.

```
CallFlow-AI/
├── apps/
│   ├── api/                        FastAPI service
│   │   ├── app/
│   │   │   ├── main.py             app assembly, lifespan, middleware
│   │   │   ├── api/v1/routes/      HTTP endpoints. Thin: validate, delegate, shape
│   │   │   ├── core/               cross-cutting concerns
│   │   │   │   ├── config.py       env → frozen dataclass, read once at import
│   │   │   │   └── rate_limit.py   sliding-window limiter
│   │   │   ├── auth/               identity
│   │   │   │   ├── tokens.py       access-token verification (JWKS / HS256)
│   │   │   │   ├── dependencies.py CurrentUser → (user_id, org_id, role)
│   │   │   │   └── permissions.py  the permission matrix — ONE file
│   │   │   ├── database/           persistence
│   │   │   │   ├── models.py       SQLAlchemy tables. Structure only
│   │   │   │   ├── session.py      pool + the RLS-scoped connection
│   │   │   │   ├── privileged.py   the ONLY RLS bypass. Every call logged
│   │   │   │   └── repositories/   one module per aggregate. SQL lives here
│   │   │   ├── domain/             business rules. Pure, no I/O, no vendors
│   │   │   │   ├── entities.py     Contact, Campaign, CallOutcome, enums
│   │   │   │   ├── safety.py       the dial gate
│   │   │   │   ├── triage.py       disposition rules, precedence-ordered
│   │   │   │   ├── result_schemas.py
│   │   │   │   └── campaigns.py
│   │   │   ├── services/           orchestration across domain + integrations
│   │   │   │   └── campaign_runner.py
│   │   │   └── integrations/       external vendors, one folder each
│   │   │       └── voice/engine.py the ONLY place the voice SDK is imported
│   │   ├── alembic/                migration environment + versions
│   │   ├── alembic.ini
│   │   ├── tests/                  mirrors the app/ layout
│   │   └── pyproject.toml
│   │
│   └── web/                        Next.js
│       ├── app/
│       │   ├── (marketing)/        public site
│       │   ├── (auth)/             login, signup, reset, invite
│       │   ├── (app)/app/          the dashboard
│       │   ├── api/                route handlers (thin proxies only)
│       │   └── globals.css         THE ENTIRE design token layer
│       ├── components/
│       │   ├── brand/              Lamp, LampStrip, Mark, Wordmark
│       │   ├── ui/                 generic primitives. No domain knowledge
│       │   ├── marketing/          public-site sections
│       │   ├── app/                dashboard components. Domain-aware
│       │   └── layout/             shells, nav, headers
│       └── lib/
│           ├── api.ts              the typed client. The only place fetch() is called
│           ├── supabase/           browser + server clients
│           ├── format/             shared formatters. phone.ts is load-bearing — §4
│           ├── hooks/              reusable hooks
│           └── *.ts                domain mapping (lamp, campaign-fields, pricing…)
│
├── packages/shared/                types shared between api and web
├── CLAUDE.md  SYSTEM.md  ISSUES.md  FEATURES.md
└── .github/workflows/ci-cd.yml     lint → test → build → deploy to VM
```

**The dependency rule.** `domain/` is the core and imports nothing from `services/`,
`api/`, `database/`, or `integrations/`. That is what keeps `safety.py` and `triage.py`
testable without a database, a mock, or a network. If you find yourself importing a
repository into `domain/`, the logic belongs in `services/` instead.

### Where things must NOT go

| Never | Why | Instead |
|---|---|---|
| A vendor SDK import outside `app/integrations/{vendor}/` | One import leaks vendor types through the whole app | Extend the adapter's protocol |
| Raw SQL outside `app/database/repositories/` | Untestable, and bypasses the repository boundary | Add a repository method |
| An import from `services/`, `api/`, or `database/` inside `domain/` | Breaks the dependency rule and makes the core untestable | Move the logic to `services/` |
| RLS bypass outside `app/database/privileged.py` | `postgres` holds BYPASSRLS. Unrestricted use makes RLS decorative | `privileged.acquire(reason=…)`; it logs every call |
| `fetch()` outside `apps/web/lib/api.ts` | Types drift, error handling forks | Add a method to the client |
| A hex colour anywhere but `globals.css` | Breaks the token layer silently | Add or use a token |
| Domain knowledge in `components/ui/` | `ui/` must be reusable in any project | Put it in `components/app/` |
| A second phone formatter | Masking is a guarantee; a second impl is how it gets bypassed | `lib/format/phone.ts` |
| Business logic in a React component | Untestable | `lib/` as a pure function |

---

## 3. SOLID, as it actually applies here

Not textbook definitions — the specific shape each principle takes in this codebase.

### S — Single responsibility

The clearest wins in the current code, and the standard to hold:

- `safety.py` decides whether a dial is allowed. It performs **no I/O**, which is why it is
  fully unit-testable and why 9 tests cover it properly.
- `triage.py` is a pure function from a typed result to a disposition. It has **no access to
  the transcript** — structurally, not by convention — so it cannot start guessing from prose.
- `lib/format/phone.ts` is the only place a number is masked.

If a module needs a mock to test, it is probably doing two jobs. Split the decision from
the I/O: a pure function that returns a decision, and a thin caller that acts on it.

### O — Open for extension, closed for modification

The product's core extension point: **a new vertical is a goal template plus a result
schema, nothing else.** Adding one must not touch the orchestrator. Same shape elsewhere —
a new campaign field type extends the map in `lib/campaign-fields.ts`; a new lamp state
extends `lib/lamp.ts`. If adding a case means editing a `switch` in five files, the
abstraction is in the wrong place.

### L — Substitutability

This is the one that keeps us from being a hostage, and it is mostly **not yet done**
(`ISSUES.md`, `FEATURES.md` F17).

A `VoiceProvider` implementation must be substitutable for any other: swapping in a stub
must exercise the entire run pipeline with no code path outside `voice/` noticing. That
requires two things people usually skip:

1. **Normalise errors into an internal taxonomy** (`invalid_number`, `no_answer`, `busy`,
   `voicemail`, `provider_unavailable`, …). Retry policy keys off the internal name, never
   a vendor string.
2. **Declare capabilities rather than assume them.** `supports('recording')` — and a
   feature that needs it degrades with an explanation instead of throwing.

An abstraction with one implementation is not an abstraction. Write the second adapter,
even if it is only a stub for tests.

### I — Interface segregation

- Every API response is a **declared Pydantic model**. No bare dicts, no `Any`.
- Components take the props they need. `components/ui/` knows nothing about calls,
  campaigns, or orgs — that is what makes it reusable and what keeps `components/app/`
  honest about being domain-specific.
- Prefer `supports(capability)` over one fat interface every adapter must implement fully.

### D — Dependency inversion

Application code depends on **protocols we own**, never on a vendor.

`app/integrations/voice/engine.py` is the working example: it is the only file that
imports the vendor SDK, and it aliases the names on the way in —

```python
from calle import CalleClient as _VendorClient
from calle.errors import CalleAPIError as EngineAPIError
```

— so nothing above it speaks the vendor's vocabulary. Every vendor gets this treatment:
voice, payments, email, storage.

---

## 4. Non-negotiables

These override style preference, convenience, and personal taste.

1. **Multi-tenancy.** Every tenant-scoped table has `org_id NOT NULL`, a foreign key, an
   index, and RLS. Every query is scoped by org at the API *and* enforced again by the
   database. Cross-tenant access is the most severe bug class this product can ship.
2. **Fail closed.** Any safety, credit, or permission check that cannot complete **denies**.
   A rate-limiter outage must never let a bug drain a customer's credits.
3. **Money is integers.** Paise, `BIGINT`. No floats anywhere in the credit or payment path.
4. **Phone numbers are masked by default,** through the one shared formatter. Revealing a
   full number is a separate permissioned, audit-logged action.
5. **No PII in logs.** Numbers, tokens, keys, and transcript bodies are redacted by a global
   filter — and the redaction is tested.
6. **Idempotency.** Every mutating endpoint and every background job is safe to run twice.
7. **Explicit state machines.** Runs, calls, subscriptions, escalations: enum states with
   declared transitions. An invalid transition raises rather than quietly succeeding.
8. **Every run dials for real — there is no dry-run gate.** That was a deliberate,
   confirmed removal (`ISSUES.md` iteration 4), not a cosmetic UI change: `dry_run` does
   not exist on `Config`, `CallOutcome`, the run-start request, or anywhere in the
   frontend. The guards that must hold on the very first call an organisation ever makes
   are the allowlist, the per-run ceiling, rate limiting, the daily budget, E.164
   validation, and the suppression list — the last of these is checked **per dial**,
   inside `check_dial_allowed()`, not just shown in the interface (`ISSUES.md` #3 —
   enforcement is real, though nothing yet writes to the list from the product itself;
   don't describe it as fully closed). Calling windows are **not** currently enforced
   anywhere server-side despite several surfaces implying they are (`ISSUES.md` #20) —
   do not add a new guard to this list, or claim one is real, without verifying it's
   actually checked in `check_dial_allowed()`, not just displayed. Weakening any real
   guard requires the same scrutiny as removing dry_run did.
9. **Never show a success state for something that did not happen.** If an action is not
   wired up, say so plainly. A fake "check your inbox" leaves someone waiting for an email
   that will never arrive, and they blame the product rather than the gap. Existing pattern:
   `AuthNotice` / `NotWiredNotice`.
10. **Colour with meaning is reserved for meaning.** The five lamp colours communicate call
    state and nothing else — never buttons, links, headings, or decoration. See
    `apps/web/DESIGN_NOTES.md` §2 for the three documented exceptions. With dry_run gone,
    `ice` (previously "simulated") is reserved and currently unassigned — do not repurpose
    it without updating the lamp-state table everywhere it's documented (`SYSTEM.md`,
    the docs site's triage-rules page). Separately, `--accent` (an indigo, `globals.css`)
    exists as the product's one **decorative-only** colour — dashboard chart markers, one
    CTA card, a tinted page canvas. The line between it and the lamps is absolute: `--accent`
    must never appear inside anything that represents call/run/escalation state (`Lamp`,
    `LampBadge`, `DonutChart`, or any future component like them) — see
    `apps/web/DESIGN_NOTES.md` §2 for where it's used today.

---

## 4b. Auth and the database — how it actually works

Four facts that are not obvious from reading the code, and that you will get wrong
without them.

**`postgres` holds BYPASSRLS.** A plain connection sees *every* organisation's rows,
and `FORCE ROW LEVEL SECURITY` does not change that — the attribute always wins. RLS
is therefore only real because `database.as_user()` drops to the `authenticated` role
and installs the JWT claims per request. If you add a code path that queries without
going through `as_user`, tenancy silently stops applying.

**Two ways into the database, and only two.**

```python
async with database.as_user(claims.auth_user_id) as conn:   # RLS applies
async with privileged.acquire("nightly purge") as conn:      # RLS bypassed, logged
```

`privileged` requires a reason string and refuses an empty one. It must never appear in
a request handler.

**Migrations use psycopg; runtime uses asyncpg.** asyncpg prepares every statement and
so rejects the multi-statement DDL that RLS policies and plpgsql functions are written
as. Do not "simplify" `alembic/env.py` back to the async driver.

**Autogenerate cannot see the security layer.** RLS, policies, triggers, functions and
grants are hand-written inside the revision. Two guards exist in `alembic/env.py` and
both matter: Supabase-owned schemas are excluded, and so are foreign keys *into* them —
without the second, autogenerate proposes dropping the `users → auth.users` link and
breaks signup.

**Adding a tenant-scoped table** means all four of these, in the same revision:
`org_id NOT NULL` + FK + index · `enable`/`force row level security` · a policy per
operation · a `grant` for `authenticated`. Then a cross-tenant test. A table with three
of the four is a data leak.

**Permissions live in one file.** `app/auth/permissions.py` maps role → permission set;
endpoints declare `Depends(RequirePermission(Permission.X))`. Never inline a role
comparison in a handler.

**Never reference `auth.users.id` in application code.** Everything joins on
`public.users.id`; `auth_user_id` is the single mapping column, used only by the
database layer to satisfy `auth.uid()`.

---

## 5. Conventions

**Python.** 3.11+. `from __future__ import annotations`. Full type hints. `ruff` clean.
Pydantic v2 for anything crossing a boundary; frozen dataclasses for config. Timestamps
`TIMESTAMPTZ`, UTC, named `*_at`.

**TypeScript.** `strict`. No `any` — use `unknown` and narrow. Components typed, accepting
`className`, forwarding refs. Prefer deriving state during render over syncing it in an
effect (`react-hooks/set-state-in-effect` is an error; see `lib/hooks/use-external-store.ts`
for the `useSyncExternalStore` pattern used for `localStorage` and `matchMedia`).

**SQL.** Timestamped migrations in `supabase/migrations/`. **Never** edit the schema through
the Supabase dashboard — it is read-only in this project. Every FK declares `ON DELETE`.
Every tenant table gets `enable row level security` **and** `force row level security`.
RLS helper functions are `SECURITY DEFINER` with a pinned `search_path`.

**Comments — write few.** The structure and the names carry the meaning. Aim for code a
developer understands without prose, and reserve comments for the small number of things
code genuinely cannot say:

- a constraint imposed from outside (`postgres` holds BYPASSRLS, so RLS needs a role switch)
- a decision whose obvious alternative is wrong (direct connection, not the pooler, because
  `SET LOCAL ROLE` is unreliable under transaction pooling)
- a non-obvious ordering or precedence requirement

Do **not** comment what the next line does. If a block needs a comment to be followed,
extract it into a named function instead — the name is the comment, and it cannot go stale.
Prefer a well-named class over a module of loose functions with a header explaining how they
relate.

Docstrings: one line on modules and public classes/functions saying what they are *for*.
Skip them entirely on anything self-evident.

**Errors.** State what happened and what to do next. Never "something went wrong", never
"oops", never apologise. Existing examples: `"Not a valid E.164 number — try
+919876543210."`, `"This run hit the per-run ceiling of 3 calls and stopped."`

**Naming.** Name things by what the user controls, not by how the system is built.
`"Escalated to a person"`, not `"triage disposition NEEDS_HUMAN"`. A button's verb survives
the whole flow: `Start run` → toast `Run started`.

---

## 6. Commands

```bash
# Backend  (from apps/api/)
pip install -e ".[dev]"
pytest -q
ruff check app tests
uvicorn app.main:app --reload --port 8000

# Frontend  (from apps/web/)
npm ci
npm run dev                            # :3000
npm run lint
npm run type-check
npm run build

# Database
supabase link --project-ref <ref>
supabase db push                       # apply migrations
supabase db reset                      # local: rebuild from migrations + seed
```

---

## 7. Before you commit

- [ ] `ruff check` and `pytest -q` pass
- [ ] `npm run lint`, `npm run type-check`, `npm run build` pass
- [ ] New tenant table has `org_id`, an index, RLS, and a **cross-tenant test that hits the
      database directly** — a policy that looks right and permits a cross-tenant read is the
      most expensive bug available here
- [ ] `SYSTEM.md` updated if the API, schema, or module layout changed
- [ ] `ISSUES.md` updated if you found or fixed a bug
- [ ] No secret, phone number, or token in a log line, a fixture, or the diff
- [ ] Sample data uses reserved fictional numbers only (`+1 555 0100–0199`), which cannot
      reach a real person

**Commit style.** Conventional prefixes (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`).
Subject in the imperative. Body explains *why* for anything non-obvious.

The opt-in pre-commit hook (`.githooks/pre-commit`) runs the backend and frontend checks.
Enable it with `git config core.hooksPath .githooks`. It resolves `ruff`/`pytest` from
`.venv` first and skips with a warning rather than blocking if the toolchain is missing.
