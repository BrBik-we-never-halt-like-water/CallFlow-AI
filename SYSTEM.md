# CallFlow AI - system reference (as built)

What exists **today**, verified against the running system on 2026-08-07. Not a plan.

- **`FEATURES.md`** is referenced throughout this document (and `CLAUDE.md`, `ISSUES.md`)
  as the target-state spec behind every `F<n>` number below - **but the file does not
  exist in this repo, at any commit.** Every `F<n>` reference is load-bearing only as a
  stable label this document itself has used consistently; treat §12 as the actual spec
  until `FEATURES.md` is written for real.
- **`apps/web/DESIGN_NOTES.md`** is the frontend design rationale.
- **`CLAUDE.md`** holds the conventions and the non-obvious auth/database facts.
- **`SUPABASE_SETUP.md`** is the dashboard checklist and environment reference.
- **`ISSUES.md`** is the running bug log.

> **State of play.** Identity, tenancy, and the calling domain are now all real:
> Supabase Postgres, RLS on every tenant-scoped table, working signup/sign-in, and
> campaigns/runs/call outcomes persisted per-organisation (`ISSUES.md` #1, #2 closed -
> `app/database/run_store.py` and the module-global campaign registry are both gone).
> **`dry_run` no longer exists anywhere in the product** - every run dials for real,
> unconditionally, from an org's very first run (CLAUDE.md, ADR-3). The guards that
> now matter are E.164 validation, the allowlist, the per-run ceiling, rate limiting, the
> shared/daily budget, calling windows (UI only), and the suppression list, which is
> checked before every dial for the first time (`ISSUES.md` #3 partially closed - see §7).
>
> **Two more slices shipped since.** Every organisation now passes through a mandatory,
> server-verified onboarding gate (`organisations.onboarded_at`, not `localStorage`)
> before the dashboard is reachable - see the `OnboardingGate` component and §12 F4/F47.
> And Settings grew three real panes: **API keys** (create/list/revoke, and the keys
> actually authenticate - `current_user()` now accepts a Supabase session _or_ a
> `cfk_…` key, see §5), **Integrations** (Twilio/Plivo credentials, encrypted at rest -
> actually placing a call over them is explicit, honest, not-yet-built work), and
> **Billing** (real plan name and real usage, no payment processor).

---

## 1. Snapshot

|             |                                                                                                                                                                           |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Repo layout | `apps/api` + `apps/web` + `packages/shared`, per `FEATURES.md` F1                                                                                                         |
| Backend     | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, asyncpg                                                                                                        |
| Frontend    | Next.js 16.2.12 (App Router, Turbopack), React 19, TypeScript strict, Tailwind v4                                                                                         |
| UI deps     | Radix primitives, Phosphor icons, framer-motion, nuqs, clsx + tailwind-merge, MDX                                                                                         |
| Persistence | Supabase Postgres 17. Identity, tenancy, campaigns, runs, and call outcomes are all org-scoped Postgres rows under RLS - **nothing calling-related is in-memory anymore** |
| Auth        | Supabase Auth, email + password. Cookie sessions, RLS-enforced tenancy                                                                                                    |
| Deployment  | Single VM, nginx + pm2, at `callflow-ai.brbik.com`. `render.yaml` is stale                                                                                                |
| CI          | GitHub Actions `ci-cd.yml` - 3 jobs, deploys on push to `main`                                                                                                            |
| Verified    | 29 API endpoints (all but 3 authenticated) · 50 built routes · **147 backend tests** (31 cross-tenant/cross-role RLS) · eslint + `tsc` clean · `alembic check` no drift   |

---

## 2. Repository layout

```
CallFlow-AI/
├── apps/
│   ├── api/                        FastAPI service
│   │   ├── app/
│   │   │   ├── main.py             app assembly, lifespan, CORS, router includes
│   │   │   ├── api/v1/routes/      campaigns, runs, organisations, invitations, profile,
│   │   │   │                       api_keys, integrations, suppressions, safety
│   │   │   ├── core/               config, rate_limit, crypto
│   │   │   ├── auth/               tokens, dependencies, permissions
│   │   │   ├── database/           models, session, privileged, repositories/
│   │   │   ├── domain/             entities, safety, triage, result_schemas,
│   │   │   │                       campaigns, api_keys  - pure, no I/O
│   │   │   ├── services/           campaign_runner (async)
│   │   │   └── integrations/voice/ engine.py - the only vendor SDK import
│   │   ├── alembic/                env.py + 13 revisions
│   │   ├── tests/                  12 files, 147 tests
│   │   └── pyproject.toml
│   └── web/                        Next.js
│       ├── app/                    (marketing) · (auth) · (app)/app
│       ├── components/             brand · ui · marketing · app · layout
│       ├── lib/                    api client, supabase/, auth/, format/, hooks/
│       ├── middleware.ts           session refresh + /app/* gating
│       └── DESIGN_NOTES.md
├── packages/shared/                (empty - for generated TS types)
├── CLAUDE.md  SYSTEM.md  ISSUES.md  FEATURES.md  SUPABASE_SETUP.md
└── .github/workflows/ci-cd.yml
```

**Layering rule.** Dependencies point inwards: `main → services → domain`, and `domain`
imports nothing from `services`, `api`, `database`, or `integrations`. That is what keeps
`safety.py` and `triage.py` testable without a database or a mock.

**Remaining divergences from `FEATURES.md` F1:** no `uv`/`pnpm`, no `mypy`, no Docker
Compose, and `packages/shared` is a placeholder - the frontend still hand-maintains its
types in `apps/web/lib/api.ts`.

---

## 3. Feature capability matrix

What a user can actually do, which endpoint it hits, and what survives a restart.

| Feature area                      | User actions available                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Endpoint(s)                                                                                                                       | Persists?                                                                                                                                                                           |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Campaigns**                     | List, create, edit in place (name + goal + extraction fields, id/slug never changes), duplicate, delete, live goal/schema preview                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | `GET/POST /api/v1/campaigns`, `PATCH/DELETE /api/v1/campaigns/{id}`                                                               | ✅ org-scoped Postgres row (built-ins stay Python constants)                                                                                                                        |
| **Goal preview**                  | Render the goal per contact - free, no dialling                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | `POST /api/v1/campaigns/preview` (authenticated; currently unused by any UI - the editor and run composer render locally, see §5) | n/a (stateless)                                                                                                                                                                     |
| **Contacts (in a run)**           | Paste, CSV drop, manual grid entry, per-row E.164 validation, remove-all-invalid                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | none - client-side only, sent inline with the run                                                                                 | ❌ never stored                                                                                                                                                                     |
| **Runs**                          | Start (always live), watch live, open a call's transcript, export CSV                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | `POST /api/v1/runs`, `GET /api/v1/runs`, `GET /api/v1/runs/{id}`                                                                  | ✅ org-scoped Postgres, updated as each call resolves                                                                                                                               |
| **Safety guards**                 | View and edit this org's own overrides (per-run ceiling, rate limit, daily budget, allowlist); enforced server-side per dial                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | `GET/PATCH /api/v1/safety`                                                                                                        | ✅ org-scoped Postgres row (`org_safety_settings`), falls back to deployment env vars when unset                                                                                    |
| **Escalations**                   | Filter by reason/campaign/age, sort oldest-first, open transcript, mark resolved                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | none - derived client-side from `GET /api/v1/runs/{id}`                                                                           | ❌ resolution is component state, lost on navigate                                                                                                                                  |
| **Contacts list**                 | Search, view call history                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | none - derived from run outcomes                                                                                                  | ❌                                                                                                                                                                                  |
| **Suppression list**              | View, add, and remove (owner-only) - org-wide, checked before every dial                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | `GET/POST /api/v1/suppressions`, `DELETE /api/v1/suppressions/{id}`                                                               | ✅ org-scoped Postgres row; the same table `check_dial_allowed()` checks (see §7)                                                                                                   |
| **Calling window / retry policy** | Edit per campaign                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | none                                                                                                                              | ⚠️ `localStorage`, never sent to the API, not enforced                                                                                                                              |
| **Org setup gate**                | Mandatory, non-skippable name confirmation on a fresh organisation, then a skippable profile-details step                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | `POST /api/v1/organisations/me/complete-onboarding`, `PATCH /api/v1/me`                                                           | ✅ `organisations.onboarded_at`, server-verified - not `localStorage`                                                                                                               |
| **Onboarding**                    | 4-step walkthrough ending in a real, live call, reached only after the org-setup gate clears                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | `POST /api/v1/runs`                                                                                                               | ⚠️ step index in `localStorage`                                                                                                                                                     |
| **Status page**                   | Live health check with latency                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | `GET /api/health`                                                                                                                 | n/a                                                                                                                                                                                 |
| **Auth**                          | Sign up, sign in, sign out, password reset, `/app/*` gating, user menu with org + role                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Supabase Auth + `GET /api/v1/me`                                                                                                  | ✅ Postgres, RLS-scoped                                                                                                                                                             |
| **Organisation + membership**     | Auto-created at signup (owner role granted by the trigger). A second organisation is created from a dedicated two-step `/app/organisation/new` (name, then an optional logo - logo is a separate step because Storage RLS scopes uploads by `org_id`, which doesn't exist until the org does). Managed - name, logo, delete - from `/app/organisation`, a dedicated page, not a dialog or a Settings tab                                                                                                                                                                                                                                                                                                                                                                                                                                   | signup trigger; `POST /api/v1/organisations` via `public.create_organisation()`                                                   | ✅ Postgres                                                                                                                                                                         |
| **Team**                          | Invite by email (role chosen), list members + pending invites, change a member's role, remove a member - from `/app/organisation`'s Team pane. A caller may only grant a role strictly below their own rank (owner > admin > operator > viewer; Owner is the one exception, who may grant any role including owner itself), and may only act on - update or remove - a member whose _current_ role is strictly below their own. Enforced at both the API (`can_grant_role()`/`can_act_on_member()`) and RLS layers; self-targeting (e.g. an Admin stepping themselves down) is exempt from the second check. Accepting an invitation cannot be used to escalate - invitation `role` is not writable by `authenticated` past creation, and a valid invitation can only seat its own invitee, never an arbitrary `user_id` (`ISSUES.md` #43) | `GET/POST /api/v1/organisations/me/members`, `.../invitations`                                                                    | ✅ Postgres, RLS-scoped                                                                                                                                                             |
| **API keys**                      | Create (full key shown once), list (name, prefix, last used, created), revoke                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `GET/POST /api/v1/api-keys`, `DELETE /api/v1/api-keys/{id}`                                                                       | ✅ org-scoped Postgres row; only a SHA-256 hash is ever stored. **The key itself authenticates** - see §5                                                                           |
| **Integrations**                  | Connect/update/disconnect org-owned Twilio or Plivo credentials                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | `GET/PUT/DELETE /api/v1/integrations/providers/{provider}`                                                                        | ✅ credential storage is real, encrypted at rest (Fernet). ⚠️ Actually placing a call over a connected number is separate, not-yet-built work - the UI says so via `NotWiredNotice` |
| **Billing**                       | View the current plan and today's real usage against the daily budget                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | `GET /api/v1/me` (`plan_id`), `GET /api/health` (`limits`)                                                                        | ✅ plan name and usage are real. ❌ No payment processor - upgrading/downgrading is not wired                                                                                       |
| **Numbers, notifications**        | UI renders; actions explain they are not connected                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | none                                                                                                                              | ❌ not wired                                                                                                                                                                        |

Legend: ✅ persists · ⚠️ persists locally/partially · ❌ lost on restart or never stored.

---

## 4. Backend modules

| Module                                          | Purpose                                                                                                                                                                                                                                                                                                                                              | Key exports                                                                                                   |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `main.py`                                       | FastAPI app assembly: CORS, lifespan (DB pool), router includes, `/` and `/api/health` only                                                                                                                                                                                                                                                          | `app`                                                                                                         |
| `core/config.py`                                | Frozen dataclass read once from the repo-root `.env`                                                                                                                                                                                                                                                                                                 | `config`                                                                                                      |
| `core/rate_limit.py`                            | In-process sliding windows, reserve-on-check, **keyed per organisation** (not IP - `ISSUES.md` #32), with per-key overrides for an org's own `org_safety_settings`                                                                                                                                                                                   | `limiter`                                                                                                     |
| `core/crypto.py`                                | Fernet symmetric encryption for org-owned provider credentials, keyed by `PROVIDER_CREDENTIALS_KEY`                                                                                                                                                                                                                                                  | `encrypt()`, `decrypt()`, `CredentialsNotConfigured`                                                          |
| `auth/tokens.py`                                | JWKS/HS256 verification with 30s clock-skew leeway                                                                                                                                                                                                                                                                                                   | `TokenVerifier`, `TokenClaims`, `InvalidToken`                                                                |
| `auth/dependencies.py`                          | Bearer token → `(user, org, role)`. **Two paths**: a Supabase access token, or a `cfk_…` CallFlow API key routed through `_resolve_api_key()`; both produce the same `CurrentUser`                                                                                                                                                                   | `CurrentUser`, `current_user`, `RequirePermission`                                                            |
| `auth/permissions.py`                           | The one role→permission matrix, plus the role-hierarchy checks for _which_ role a caller may grant and _whose_ row they may act on (owner > admin > operator > viewer)                                                                                                                                                                               | `Permission`, `ROLE_PERMISSIONS`, `role_has()`, `can_grant_role()`, `can_act_on_member()`                     |
| `database/models.py`                            | SQLAlchemy tables for identity/tenancy only - structure, no RLS. `campaigns`, `runs`, `call_outcomes` are **not** ORM classes; they're hand-authored in the migration and read only through raw asyncpg in the repositories below                                                                                                                    | `User`, `Organisation`, `Membership`, `Suppression`, `OrgRole`                                                |
| `database/session.py`                           | Pool + the RLS-scoped connection + jsonb codec registration                                                                                                                                                                                                                                                                                          | `Database`, `database`                                                                                        |
| `database/privileged.py`                        | The only RLS bypass. Demands a reason, logs every use                                                                                                                                                                                                                                                                                                | `PrivilegedAccess`, `privileged`                                                                              |
| `database/repositories/campaigns.py`            | Org-owned campaign CRUD, raw asyncpg                                                                                                                                                                                                                                                                                                                 | `list_org_campaigns()`, `get_org_campaign()`, `create_campaign()`, `delete_campaign()`                        |
| `database/repositories/runs.py`                 | Run + call-outcome persistence, raw asyncpg                                                                                                                                                                                                                                                                                                          | `create_run()`, `append_outcome()`, `finish_run()`, `get_run()`, `list_outcomes()`, `list_runs()`             |
| `database/repositories/suppressions.py`         | Do-not-call list, raw asyncpg                                                                                                                                                                                                                                                                                                                        | `is_suppressed()`, `list_suppressions()`, `add_suppression()`, `remove_suppression()`                         |
| `database/repositories/safety_settings.py`      | An org's own safety-guard overrides, raw asyncpg                                                                                                                                                                                                                                                                                                     | `get_for_org()`, `upsert()`                                                                                   |
| `database/repositories/api_keys.py`             | Org-scoped API key CRUD, raw asyncpg. RLS restricts every query to owner/admin                                                                                                                                                                                                                                                                       | `list_for_org()`, `create()`, `revoke()`                                                                      |
| `database/repositories/provider_credentials.py` | Org-owned Twilio/Plivo credential storage, raw asyncpg. Only ever sees ciphertext - encryption happens in the route layer                                                                                                                                                                                                                            | `list_for_org()`, `upsert()`, `remove()`                                                                      |
| `domain/entities.py`                            | Pydantic domain types and terminal-status sets. **No `dry_run` field anywhere**                                                                                                                                                                                                                                                                      | `Contact`, `Campaign`, `CallOutcome`, `Sentiment`, `Disposition`, `DialFailure`                               |
| `domain/safety.py`                              | Pre-dial gate and phone masking. No I/O                                                                                                                                                                                                                                                                                                              | `is_e164()`, `mask()`, `phone_hash()`, `check_dial_allowed()`, `EffectiveSafety`, `resolve_safety_settings()` |
| `domain/triage.py`                              | Pure disposition decision from typed fields only                                                                                                                                                                                                                                                                                                     | `triage()`, `needs_human()`                                                                                   |
| `domain/result_schemas.py`                      | The shared result contract every campaign inherits                                                                                                                                                                                                                                                                                                   | `BASE_PROPERTIES`, `build_result_schema()`                                                                    |
| `domain/campaigns.py`                           | 2 built-in constants + `slugify()`. **No runtime registry anymore** - custom campaigns are real rows, resolved through the repository above                                                                                                                                                                                                          | `TRAVEL_DISCOVERY`, `APPOINTMENT_REMINDER`, `REGISTRY`, `SCHEMAS`, `BUILT_IN_IDS`, `FIELD_TYPES`, `slugify()` |
| `domain/api_keys.py`                            | Generating and hashing CallFlow API keys. Pure - no I/O, no database                                                                                                                                                                                                                                                                                 | `generate_api_key()`, `hash_api_key()`, `looks_like_api_key()`                                                |
| `services/campaign_runner.py`                   | Per-contact pipeline - **fully `async def`**, using `asyncio.to_thread()` for the still-synchronous voice SDK                                                                                                                                                                                                                                        | `CampaignRunner`, `render_goal()`                                                                             |
| `api/v1/routes/campaigns.py`                    | `/api/v1/campaigns` - list/create/update/delete/preview, org-scoped                                                                                                                                                                                                                                                                                  | `router`, `resolve_campaign()`                                                                                |
| `api/v1/routes/runs.py`                         | `/api/v1/runs` - start/list/get, org-scoped, background execution                                                                                                                                                                                                                                                                                    | `router`                                                                                                      |
| `api/v1/routes/suppressions.py`                 | `/api/v1/suppressions` - list/add/remove the org's do-not-call list. Add is operator+, remove is owner-only, matching the RLS policy                                                                                                                                                                                                                 | `router`                                                                                                      |
| `api/v1/routes/safety.py`                       | `/api/v1/safety` - get/patch this org's own safety-guard overrides, plus live `used_today` from the org-keyed limiter                                                                                                                                                                                                                                | `router`                                                                                                      |
| `api/v1/routes/api_keys.py`                     | `/api/v1/api-keys` - list/create/revoke, org-scoped, owner/admin only                                                                                                                                                                                                                                                                                | `router`                                                                                                      |
| `api/v1/routes/integrations.py`                 | `/api/v1/integrations/providers/{provider}` - connect (upsert)/list/disconnect, owner/admin only                                                                                                                                                                                                                                                     | `router`                                                                                                      |
| `integrations/voice/protocol.py`                | The `VoiceProvider` structural protocol every voice adapter conforms to - CALL-E is still the only one (`VOICE_AGENT_PLATFORM.md` P1)                                                                                                                                                                                                                | `VoiceProvider`, `VoiceCapability`, `NotImplementedForProvider`                                               |
| `integrations/voice/engine.py`                  | **The only vendor-SDK boundary**, aliased on import. Conforms to `VoiceProvider`: `supports()` declares structured-extraction/live-events only, `cancel_call()` raises (the SDK has none). `classify_error()` maps the engine's own error codes onto the internal `DialFailure` taxonomy (`ISSUES.md` #37), unmapped codes fail closed to `INTERNAL` | `EngineGateway`, `EngineAPIError`, `TERMINAL`, `classify_error`                                               |

**Per-contact pipeline** (`CampaignRunner.run_one`, in `services/campaign_runner.py`):

```
build base outcome (masked phone)
  → render_goal(campaign, contact)        {name} / {context[key]}, missing keys → ""
  → check_dial_allowed(is_suppressed=…)   fails closed → SKIPPED. Suppression is checked
                                           here too now - the caller resolves the org's
                                           real suppressions table once per run and passes
                                           the verdict in (domain/ does no I/O, by design)
  → gateway.start_call()   [asyncio.to_thread]   idempotency key per attempt
  → on_status(IN_FLIGHT)                  row appears immediately, persisted via append_outcome
  → _poll_until_done()     [asyncio.to_thread per poll]   2s interval, reports each status change
  → _extract_result() / _extract_transcript()
  → triage() → return
```

A failed `EngineAPIError`/`EngineTimeoutError` doesn't fall through to a generic catch -
`classify_error()` maps it onto `DialFailure` first, and only `rate_limited`,
`provider_unavailable`, and `timed_out` become `Disposition.RETRY`; everything else
(`invalid_number`, `insufficient_balance`, `policy_violation`, `unauthorized`, and any
unmapped engine code) becomes `Disposition.UNREACHABLE` (`ISSUES.md` #37). An
unclassified exception (network error, anything outside the engine's own error types)
still falls through to a final `except Exception`, storing `DialFailure.INTERNAL` rather
than the raw exception string.

Every run dials for real - there is no branch that skips the network call. The SDK's own
client is blocking, so every call into it runs in a worker thread; otherwise one in-flight
call would stall the event loop for every other request.

`_extract_result` tries `result`, `structured_result`, `results`, `output`, `data`, then
`recipients[0].result` - the payload shape has moved across engine versions, so it probes
known candidates rather than assuming one.

---

## 5. API reference

Base URL from `NEXT_PUBLIC_API_URL`. **Authenticated by default.** Every endpoint except
`GET /`, `GET /api/health`, and `GET /api/v1/invitations/{token}` requires a bearer token
(`Authorization: Bearer <token>`), resolved to `(user, org, role)` by
`current_user`/`RequirePermission` (`auth/dependencies.py`). Two kinds of token are
accepted, and everything downstream - permissions, RLS, routes - is identical either way:

- a **Supabase access token** (the web client, always), verified by `auth/tokens.py`;
- a **CallFlow API key** (`cfk_…`, programmatic access - Settings → API keys), detected by
  its prefix and resolved through `database.anonymous()` calling the SECURITY DEFINER
  function `public.resolve_api_key()` - there is no Supabase session at all on this path.
  The key's _role_ is re-read from `memberships` fresh on every call rather than cached on
  the key row, so removing someone from an organisation or changing their role invalidates
  their API keys immediately, not on their next sign-in.

A caller who belongs to more than one organisation sends `X-Org-Id` (Supabase-token path
only); omitting it falls back to the earliest-joined membership. Organisation, team,
profile, API-key, suppression-list, and integration-credential management
(`/api/v1/organisations/*`, `/api/v1/me`, `/api/v1/invitations/*`, `/api/v1/api-keys/*`,
`/api/v1/suppressions/*`, `/api/v1/integrations/*`) are their own routers and aren't
detailed below - one exception follows, since it's
new and load-bearing for the mandatory onboarding gate described in §3/§12. All bodies JSON.

**`POST /api/v1/organisations/me/complete-onboarding`** - requires `Permission.ORG_UPDATE`.
Sets the active organisation's name and `onboarded_at` in one update
(`coalesce(onboarded_at, now())`, so calling it twice is harmless). This is the only write
that clears `active.onboarded_at` on `GET /api/v1/me` from `null` to a timestamp, which is
what lets `OnboardingGate` (frontend) stop showing the mandatory org-setup modal.

### `GET /`

Liveness probe. Touches no locks and no config, so it can never be the slow thing.
→ `200 {"service": "callflow-api", "status": "ok"}`
_Used by:_ nginx/pm2 health check, CI post-deploy check.

### `GET /api/health`

The deployment's own default guards. Unauthenticated - since the rate limiter is now
keyed per organisation (§7, `ISSUES.md` #32), this endpoint has no org to report live
usage for and no longer tries to.

```json
{
  "ok": true,
  "api_key_configured": false,
  "max_calls_per_run": 3,
  "allowlist_active": false,
  "limits": {
    "daily_budget": 20,
    "per_window": 5,
    "window_minutes": 60
  }
}
```

`limits` is omitted only if `config` fails to load. No `used_today` field - that moved to
`GET /api/v1/safety` (below), the one place it can be resolved against a real `org_id`.
There is no `dry_run` concept left to report - every run dials for real.
_Used by:_ `SafetyBar` (deployment defaults only), `/status`.

### `GET /api/v1/safety`

Requires `Permission.SAFETY_READ` (any member). This organisation's effective guards -
its own `org_safety_settings` override merged onto the deployment defaults
(`resolve_safety_settings()`, domain/safety.py) - plus this organisation's real, live
`used_today` from the now org-keyed rate limiter.

```json
{
  "allowlist": ["+919876543210"],
  "max_calls_per_run": 3,
  "calls_per_window": 5,
  "window_minutes": 60,
  "daily_budget": 20,
  "used_today": 4
}
```

### `PATCH /api/v1/safety`

Requires `Permission.SAFETY_WRITE` (owner/admin). Upserts this organisation's
`org_safety_settings` row and returns the same shape as the `GET`. Every field is
required in the body (unlike the nullable-by-default database row) - a partial save
isn't offered; the settings page always submits the full effective set it's already
displaying. `allowlist` entries are validated E.164 (`400` listing which ones failed).
_Used by:_ Settings → Safety (`apps/web/app/(app)/app/settings/safety/page.tsx`), the run
composer's guard bar (`guardsFromSafety()`).

### `GET /api/v1/campaigns`

Any org member. Returns the 2 built-in constants (`app/domain/campaigns.py`) followed by
this organisation's own rows (`campaigns_repo.list_org_campaigns`).

```json
[
  {
    "id": "travel-discovery",
    "name": "Travel enquiry follow-up",
    "region": "IN",
    "language": "en",
    "outcome_fields": {
      "service_interest": "flight | hotel | tour | package | none",
      "destination": "destination city or country"
    },
    "goal_template": "You are CallFlow AI, a friendly travel consultant…",
    "goal_preview": "You are CallFlow AI, a friendly travel consultant…",
    "built_in": true
  }
]
```

`goal_preview` is `goal_template[:280]`. `outcome_fields` is a flat
`{field_name: human description}` map - _not_ JSON Schema; the real schema lives
server-side (`SCHEMAS[campaign_id]` or the row's `result_schema` jsonb column) and is
never exposed over the API.
_Used by:_ campaigns index, run composer, campaign editor.

### `POST /api/v1/campaigns`

Requires `Permission.CAMPAIGNS_WRITE` (operator role or above).

```json
{
  "name": "Holiday enquiry follow-up",
  "goal_template": "You are calling {name} about their enquiry…",
  "extra_fields": [
    {
      "key": "party_size",
      "type": "integer",
      "description": "Number of travellers."
    }
  ],
  "region": "IN",
  "language": "en",
  "escalate_on_negative": true
}
```

| Constraint                                                   | Enforced by                                                                                                                                                                                                                 |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name` 2–80 chars                                            | Pydantic `Field(min_length=2, max_length=80)`                                                                                                                                                                               |
| `goal_template` ≥ 40 chars                                   | Pydantic **and** an explicit re-check with a friendlier message                                                                                                                                                             |
| `extra_fields[].key` 1–40 chars                              | Pydantic                                                                                                                                                                                                                    |
| `extra_fields[].type` ∈ `{string, boolean, integer, number}` | Handler, 400 listing the valid set                                                                                                                                                                                          |
| `extra_fields[].required`                                    | Appended to the schema's `required` array alongside `BASE_REQUIRED` (`domain/result_schemas.py`) - a field marked required in the editor is actually required in the schema sent to the engine, not just a description hint |

→ `201` the created campaign (same shape as the list) · `400` bad field type · `400` goal too short

**Side effects:** inserts a real row into `public.campaigns` (`org_id`, `created_by`).
The id is slugified from the name with a numeric suffix on collision, checked against both
`BUILT_IN_IDS` and this organisation's existing rows - so two organisations can each have
a campaign called "Holiday enquiry follow-up" with the same id, and neither collides with
the other (`org_id` scopes everything). Keys are slugified to `snake_case`; a key that
slugifies to empty is silently dropped.

### `PATCH /api/v1/campaigns/{campaign_id}`

Requires `Permission.CAMPAIGNS_WRITE`. Same body and validation as `POST`. The id/slug
never changes on update, only the row's content - so existing runs that reference this
`campaign_id` keep pointing at the right campaign after an edit.

→ `200` the updated campaign · `400` if built-in ("Built-in campaigns cannot be edited.")
· `404` unknown or belongs to another organisation

Before this route existed, the campaign editor's "Edit" entry point called the same
`createCampaign` the "New campaign" button used - so editing a real campaign silently
created a second, independent one and left the original untouched, while the toast said
"Campaign saved." Fixed by adding this route and branching the frontend's `save()` on
whether `existing` is set.

### `DELETE /api/v1/campaigns/{campaign_id}`

Requires `Permission.CAMPAIGNS_DELETE`.
→ `204` no body · `400` if built-in ("Built-in campaigns cannot be deleted.") · `404` unknown
or belongs to another organisation (RLS plus an explicit `org_id` filter in the delete).

### `POST /api/v1/campaigns/preview`

Any org member. Renders goals without touching the voice engine - free, instant, no
dialling, no rate limit.

```json
{
  "campaign_id": "travel-discovery",
  "contacts": [
    {
      "name": "Aditi",
      "phone": "+15555550100",
      "context": { "enquiry_note": "Bali in December" }
    }
  ]
}
```

```json
{
  "campaign_id": "travel-discovery",
  "previews": [
    { "name": "Aditi", "goal": "You are CallFlow AI… calling Aditi back…" },
    {
      "name": "Bad Row",
      "error": "phone must be E.164 (e.g. +15555550100), got '98765'"
    }
  ]
}
```

An invalid contact yields a per-entry `error` instead of failing the whole request.
→ `404` unknown campaign. **Currently unused by the frontend** - the campaign editor and
the run composer both render the goal preview locally via `renderGoalPreview` in
`lib/campaign-fields.ts` rather than calling this endpoint; `api.preview` exists in
`lib/api.ts` with no caller.

### `POST /api/v1/runs`

Requires `Permission.RUNS_START`. **Every run dials for real - there is no `dry_run`
field, and no way to simulate a run through this endpoint.**

```json
{
  "campaign_id": "travel-discovery",
  "contacts": [
    {
      "name": "Aditi",
      "phone": "+15555550100",
      "region": null,
      "language": null,
      "context": { "enquiry_note": "Bali in December" }
    }
  ]
}
```

```json
{ "run_id": "8f2a1c4d9e7b", "total": 1 }
```

| Status | Cause                                                                       |
| ------ | --------------------------------------------------------------------------- |
| `200`  | Accepted. `run_id` is a 12-char hex; work continues in `BackgroundTasks`    |
| `400`  | `"At least one contact is required."`                                       |
| `400`  | A contact fails E.164 validation (Pydantic message)                         |
| `400`  | No Voice API key configured                                                 |
| `404`  | Unknown `campaign_id`                                                       |
| `429`  | Per-IP window or shared daily budget exceeded; `Retry-After` set when known |

Rate limiting now applies to **every** run, since there is no non-dialling mode left to
exempt. Client IP is taken from the first entry of `X-Forwarded-For`, falling back to the
socket peer. `X-CallFlow-Owner-Key` is compared with `secrets.compare_digest` and lifts
the rate limits (not the allowlist or ceiling).

**Suppression, resolved once per run.** Before creating the run, the handler hashes every
contact's phone with `phone_hash()` and checks each against the org's real
`public.suppressions` table (`suppressions_repo.is_suppressed`). The set of matching
hashes is handed to `CampaignRunner` as `suppressed_hashes`, and `check_dial_allowed`
skips any contact whose hash is in that set - one query for the whole run rather than one
per contact.

Returns immediately - nothing holds the connection open while calls run. The background
task (`_run_and_persist`) drives the async `CampaignRunner`, and on every progress callback
re-acquires an `as_user` connection and calls `runs_repo.append_outcome` - so a browser
polling `GET /api/v1/runs/{id}` sees rows update as calls resolve, not only once the run
ends. `finish_run` marks the run `completed` or `failed` when the loop exits.

### `GET /api/v1/runs`

Org-scoped list (`runs_repo.list_runs`).

```json
[
  {
    "id": "8f2a1c4d9e7b",
    "campaign_id": "travel-discovery",
    "total": 3,
    "status": "completed",
    "started_at": "2026-08-05T09:12:04.221Z",
    "finished_at": "2026-08-05T09:12:05.108Z",
    "error": null,
    "completed": 3
  }
]
```

Newest first (`started_at` descending). `outcomes` is stripped; `completed` here is a
`count(*)` of outcome rows whose `disposition <> 'in_flight'` - a raw row count, **not**
the same as `stats.completed` below.

### `GET /api/v1/runs/{run_id}`

Org-scoped. Full run, plus `outcomes[]` (see §6 for every field), plus computed `stats`:

```json
{
  "id": "8f2a1c4d9e7b",
  "campaign_id": "travel-discovery",
  "total": 3,
  "status": "completed",
  "started_at": "2026-08-05T09:12:04.221Z",
  "finished_at": "2026-08-05T09:12:05.108Z",
  "error": null,
  "outcomes": [
    /* CallOutcome objects, each with both run_id and provider_call_id */
  ],
  "stats": {
    "completed": 3,
    "total": 3,
    "escalated": 1,
    "auto_closed": 1,
    "needs_human_pct": 33
  }
}
```

→ `404` `"Run not found"`.

Two subtleties in `stats`, both deliberate:

- `completed` counts only outcomes whose `disposition != "in_flight"` - an in-flight call
  is not progress yet, which is what stops the progress indicator going backwards.
- `escalated` is counted over **resolved** outcomes, but `auto_closed` and
  `needs_human_pct` are computed over **all** outcomes. So mid-run the percentage is
  diluted by in-flight rows. Cosmetic, but worth knowing before trusting it in a report.

`runs_repo.append_outcome` upserts on `(run_id, contact_name, phone_masked)` - a real
Postgres `on conflict … do update`, so one call produces one row across all its status
transitions rather than a row per change.

### What the API does **not** have

No `Idempotency-Key` header · no cursor pagination · no RFC 9457 problem details (errors
are FastAPI's `{"detail": "..."}`) · **no run cancel endpoint** (which is why the UI's
Stop button honestly says "updates stopped, run not cancelled") · no webhooks in or out ·
**no dry-run or simulate mode of any kind** - every run dials for real from the first
request an org ever makes. It now **does** have an `/api/v1` prefix throughout, Bearer-
token auth, and per-org scoping (RLS-enforced) on everything except the three endpoints
listed at the top of this section.

---

## 6. Domain model and lifecycles

### Every field, by type (`domain/entities.py`)

**`Contact`** - the input unit.

| Field      | Type             | Default  | Notes                                                                               |
| ---------- | ---------------- | -------- | ----------------------------------------------------------------------------------- |
| `name`     | `str`            | required | Substituted as `{name}` in the goal                                                 |
| `phone`    | `str`            | required | **Validated E.164 at construction** - a bad number raises before anything is queued |
| `region`   | `str \| None`    | `None`   | Overrides the campaign, then `CALLE_DEFAULT_REGION`                                 |
| `language` | `str \| None`    | `None`   | Sent to the engine as `locale`, not `language`                                      |
| `context`  | `dict[str, Any]` | `{}`     | Arbitrary business data; merged into the goal and engine metadata                   |

**`Campaign`** - the goal plus its result contract.

| Field                  | Type             | Default  | Notes                                                                     |
| ---------------------- | ---------------- | -------- | ------------------------------------------------------------------------- |
| `id`                   | `str`            | required | Slugified from the name, numeric suffix on collision                      |
| `name`                 | `str`            | required |                                                                           |
| `goal_template`        | `str`            | required | Supports `{name}` and `{context[key]}`                                    |
| `outcome_fields`       | `dict[str, str]` | `{}`     | `field → human description`. What the UI lists and goal previews populate |
| `region`               | `str \| None`    | `None`   |                                                                           |
| `language`             | `str \| None`    | `None`   |                                                                           |
| `escalate_on_negative` | `bool`           | `True`   | Misnamed - gates the _retry_ branch of triage, not an escalation          |

**`CallOutcome`** - everything known after one call resolves. This is what the frontend renders.

| Field                | Type             | Default     | Notes                                                                                                                                                                                                                                                                                                                                                                 |
| -------------------- | ---------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `contact_name`       | `str`            | required    |                                                                                                                                                                                                                                                                                                                                                                       |
| `phone_masked`       | `str`            | required    | **Already masked** - the raw number never leaves `CampaignRunner`                                                                                                                                                                                                                                                                                                     |
| `campaign_id`        | `str`            | required    |                                                                                                                                                                                                                                                                                                                                                                       |
| `status`             | `str`            | `"UNKNOWN"` | Engine status, uppercased. `"BLOCKED"` when a safety guard skips the contact                                                                                                                                                                                                                                                                                          |
| `plan_id`            | `str \| None`    | `None`      | **Unused** - set nowhere, read nowhere                                                                                                                                                                                                                                                                                                                                |
| `run_id`             | `str \| None`    | `None`      | Set by `campaign_runner.py` to the **provider's own call id** while a call is in flight - this domain object never held the run id. `routes/runs.py` fixes this at the persistence boundary: it remaps this field to `provider_call_id` before writing, and the API always serves the real run id in its place (see §13, ISSUES.md #1, now closed at the API surface) |
| `transcript`         | `str \| None`    | `None`      | The conversation transcript, when the engine returns one                                                                                                                                                                                                                                                                                                              |
| `summary`            | `str \| None`    | `None`      | From the extracted result, falling back to the engine payload                                                                                                                                                                                                                                                                                                         |
| `sentiment`          | `Sentiment`      | `unknown`   | Parsed from the extraction, unparseable → `unknown`                                                                                                                                                                                                                                                                                                                   |
| `sentiment_reason`   | `str \| None`    | `None`      | Currently always set equal to `disposition_reason`                                                                                                                                                                                                                                                                                                                    |
| `extracted`          | `dict[str, Any]` | `{}`        | The typed result, as returned by the voice engine                                                                                                                                                                                                                                                                                                                     |
| `disposition`        | `Disposition`    | `skipped`   | Set by `triage()`                                                                                                                                                                                                                                                                                                                                                     |
| `disposition_reason` | `str \| None`    | `None`      | Human sentence - what the UI's reasoning chain displays                                                                                                                                                                                                                                                                                                               |
| `error`              | `str \| None`    | `None`      | `"ExcType: message"` on failure                                                                                                                                                                                                                                                                                                                                       |
| `duration_seconds`   | `float \| None`  | `None`      | From the engine payload                                                                                                                                                                                                                                                                                                                                               |
| `created_at`         | `datetime`       | now (UTC)   |                                                                                                                                                                                                                                                                                                                                                                       |
| `answered`           | property         | -           | `status.upper() in {"COMPLETED"}`                                                                                                                                                                                                                                                                                                                                     |

**Terminal engine statuses** (`TERMINAL_STATUSES`): `BUSY`, `CANCELED`, `CANCELLED`,
`COMPLETED`, `DECLINED`, `EXPIRED`, `FAILED`, `NO_ANSWER`, `VOICEMAIL`. Both US and UK
spellings of "cancelled" are included because the engine has used each.
`ANSWERED_STATUSES` is just `{COMPLETED}`.

Note `integrations/voice/engine.TERMINAL` is a _separate_, lowercase set (`completed`,
`failed`, `canceled`) used for poll termination - the two are not the same constant.

### The shared result contract (`domain/result_schemas.py`)

Every campaign inherits these six, so triage is uniform regardless of the vertical:

| Field                  | Type                                                                      | Drives                                 |
| ---------------------- | ------------------------------------------------------------------------- | -------------------------------------- |
| `outcome`              | enum: `interested`, `not_interested`, `callback_requested`, `no_decision` | reporting                              |
| `sentiment`            | enum: `positive`, `neutral`, `negative`                                   | triage                                 |
| `frustration_signals`  | boolean                                                                   | triage → escalate                      |
| `wants_human_callback` | boolean                                                                   | triage → escalate                      |
| `do_not_call`          | boolean                                                                   | triage → escalate (highest precedence) |
| `summary`              | string                                                                    | UI                                     |

Required: `outcome`, `sentiment`, `frustration_signals`, `summary`.
Campaign-specific fields are merged on top by `build_result_schema()`.

### Triage precedence (`triage.py`) - exact order

| #   | Condition                                         | Disposition                              |
| --- | ------------------------------------------------- | ---------------------------------------- |
| 1   | `do_not_call`                                     | `ESCALATED` - suppress and log           |
| 2   | `wants_human_callback`                            | `ESCALATED`                              |
| 3   | `frustration_signals`                             | `ESCALATED`                              |
| 4   | `escalate_on_negative` **and** sentiment negative | `RETRY` - "a bad time is not a bad mood" |
| 5   | status in `busy`, `no_answer`, `voicemail`        | `RETRY`                                  |
| 6   | status in `failed`, `canceled`                    | `UNREACHABLE`                            |
| 7   | status is `completed`                             | `AUTO_CLOSED`                            |
| 8   | anything else                                     | `SKIPPED`                                |

One subtlety: the badly-named `escalate_on_negative` flag gates rule 4, which produces a
**retry, not an escalation** - and when it is `false`, negative sentiment falls through to
the status checks. (There is no longer a `"preview"` status branch - dry runs don't exist,
so every outcome reaching this function came from a real call.)

### Enums

`Disposition`: `in_flight`, `auto_closed`, `escalated`, `retry`, `unreachable`, `skipped`
`Sentiment`: `positive`, `neutral`, `negative`, `unknown`
Run `status`: `running`, `completed`, `failed`

### Disposition → lamp (`web/lib/lamp.ts`)

The frontend's whole visual language.

| Disposition   | Lamp           | Meaning             |
| ------------- | -------------- | ------------------- |
| `in_flight`   | brass          | in conversation     |
| `auto_closed` | jade           | clean outcome       |
| `retry`       | brass, pulsing | queued for retry    |
| `escalated`   | flare          | needs a person      |
| `unreachable` | flare          | couldn't be reached |
| `skipped`     | off            | blocked by a guard  |

`LampState` also declares `ice`, currently **unassigned** - no disposition maps to it.
Before dry_run removal it meant "simulated, nothing dialled"; `lamp.ts`'s own comment
now reserves it for a possible future "scheduled, not yet dialling" state rather than
retiring the colour outright.

---

## 7. Safety model

Guards run inside `check_dial_allowed()`, called **once per contact immediately before
dialling** - never once per batch. All fail closed. There is no dry-run mode to fall back
on if a guard is misconfigured - every one of these is the real thing standing between a
started run and a ringing phone.

**Implemented**

| Guard                       | Default                                                    | Where                                                                                         |
| --------------------------- | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Suppression list            | on, always checked                                         | `is_suppressed` param, resolved once per run against `public.suppressions`                    |
| E.164 validation            | always                                                     | `safety.is_e164`                                                                              |
| Per-run ceiling             | 3, or an org's own `org_safety_settings.max_calls_per_run` | `CALLFLOW_MAX_CALLS_PER_RUN`, editable per org via `PATCH /api/v1/safety`                     |
| Allowlist                   | empty (inactive), or an org's own override                 | `CALLFLOW_ALLOWLIST`, editable per org via `PATCH /api/v1/safety`                             |
| Per-organisation rate limit | 5 per 3600s, or an org's own override                      | `rate_limit.py`, keyed by `org_id` - **not** IP (`ISSUES.md` #32)                             |
| Daily budget                | 20, or an org's own override                               | `CALLFLOW_DAILY_BUDGET`, keyed by `org_id` - one organisation can no longer exhaust another's |
| Owner bypass                | off                                                        | `X-CallFlow-Owner-Key` header lifts rate limits only                                          |
| Phone masking               | always                                                     | `safety.mask` + `lib/format/phone.ts`                                                         |

`resolve_safety_settings()` (`domain/safety.py`) is the one place an org's
`org_safety_settings` row is merged onto the deployment defaults - `GET/PATCH
/api/v1/safety`, the rate limiter, and `check_dial_allowed()` all resolve through it, so
display and enforcement can never disagree about what an organisation's guards actually
are (`ISSUES.md` #33). The rate limiter **reserves slots at check time** so concurrent
requests cannot both pass, and exposes `release()` for a run that fails before dialling.

**Suppression is checked and has a real write path.** `check_dial_allowed` takes
`is_suppressed` as a plain boolean and denies the dial if true - `POST /api/v1/runs`
resolves it against the org's actual `public.suppressions` table before every run.
`GET/POST /api/v1/suppressions` and `DELETE /api/v1/suppressions/{id}` (`ISSUES.md` #3,
now fixed) let a person actually populate that table: the "Contacts" page's suppression
tab calls these directly, replacing the old disconnected `localStorage` list. Adding
requires `operator` or above; removing (making someone callable again) is owner-only,
matching the table's RLS policy. Still missing: a `do_not_call` triage disposition does
not yet auto-insert a row - today someone has to add the number by hand after the call.

**Required by `FEATURES.md` F19 but missing:** calling-window enforcement · credit-balance
check · consent flag.

---

## 8. Frontend

### Routes (40 page files → 48 built routes, verified via `next build`)

- **`(marketing)`** - `/`, `/pricing`, `/solutions/[vertical]` (4 static), `/trust`, `/about`, `/demo`, `/status`, `/maintenance`, `/docs` + 8 MDX pages
- **`(auth)`** - `/login`, `/signup`, `/forgot-password`, `/reset-password`, `/verify-email`, `/accept-invite/[token]`
- **`(app)/app`** - dashboard (`/app`), `campaigns` + `new` + `[id]`, `runs` + `new` + `[id]`, `escalations`, `contacts`, `profile`, `organisation` + `new`, `settings` + 4 panes (`safety`, `api-keys`, `integrations`, `billing`). Organisation and Team are their own route, `/app/organisation` (`Suspense`-wrapped for `useSearchParams()`, `?tab=team` selects the Team pane) - not a dialog and not a Settings pane; `/app/settings` and `/app/settings/team` both redirect to `/app/settings/safety` so pre-existing generic "Settings" links still resolve; "Organisation" lives in the account menu (`user-menu.tsx`/`app-nav.tsx`'s dropdown), not a sidebar item, since there is no sidebar. Creating a second organisation is a dedicated two-step page, `/app/organisation/new` (name, then an optional logo - logo upload has to be a second step because Storage RLS scopes the upload path by `org_id`, which doesn't exist until the create call returns). There is no `/app/welcome` - the mandatory org-setup step + its skippable profile follow-up are **not routes at all**; `OnboardingGate` renders them as a modal over whatever page is active (see §3/§12), specifically to avoid the two-independent-`useSession()`-instances bug a page-per-step version had (`ISSUES.md`)
- **Generated** - `icon.svg`, `apple-icon`, `opengraph-image`, `manifest.webmanifest`, `not-found` (`error.tsx` is a boundary, not a routed page)

### Design layer - `app/globals.css`, 714 lines

Light mode only; no dark theme, no surface toggle. Semantic tokens (`--surface*`,
`--text*`, `--rule*`), five lamp colours plus `-text` variants for contrast, a fluid type
scale, a 4-step shadow scale, and motion tokens.

The "flow" surface language (added after the initial build):

| Utility               | What it does                                                             |
| --------------------- | ------------------------------------------------------------------------ |
| `.pool`               | Shallow gradient-lit basin, no rectangular edge                          |
| `.surface-flow`       | Borderless gradient card - the stand-in for `border + bg-surface-raised` |
| `.card-flow`          | The hero readout: 32px radius, wide soft glow, edges melt into the page  |
| `.seam-x` / `.seam-y` | Hairlines that fade at both ends instead of hard rules                   |
| `.flow-seam-l`        | Desktop-only fading left border between columns                          |
| `.grid-field`         | Masked draughtsman's grid behind the hero                                |

Named animations: `relay-settle` (the signature lamp flicker), `relay-glow`, `lamp-pulse`,
`loader-bar`, `loader-out`, `wave-active`, `menu-in`, `sheet-in`, `page-enter`, `row-enter`, `caret`.

### `lib/` (18 files)

| File                                       | Role                                                                                                                                                                                 |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `api.ts`                                   | Typed fetch client + all response types. Rejects unreachable internal hosts                                                                                                          |
| `lamp.ts`                                  | Disposition → lamp mapping, `countLamps`, `describeStrip` (the a11y summary)                                                                                                         |
| `app-store.tsx`                            | `AppStoreProvider` - hydrates up to 10 recent runs, derives escalations/outcomes                                                                                                     |
| `format/phone.ts`                          | **The single masking implementation.** `maskPhone`, `isE164`, `normalisePhone`                                                                                                       |
| `format/index.ts`                          | Duration, currency, percent, timestamp, age, `humaniseKey`                                                                                                                           |
| `campaign-fields.ts`                       | 5 editor field types → 4 wire types; JSON Schema preview; goal rendering                                                                                                             |
| `campaign-draft.ts`                        | Calling window / retry policy in `localStorage`; preview contacts                                                                                                                    |
| `contacts.ts`                              | CSV/TSV parse, row validation, sample CSV                                                                                                                                            |
| `pricing.ts`                               | Plans, feature matrix, FAQ. **All prices are `null` → render as `TODO`**                                                                                                             |
| `verticals.ts`                             | The 4 solution pages' goal templates and schemas, shown in full                                                                                                                      |
| `docs.ts`                                  | Docs nav tree and neighbours                                                                                                                                                         |
| `cn.ts`                                    | `clsx` + `tailwind-merge`                                                                                                                                                            |
| `hooks/use-connection.ts`                  | Loads health + campaigns on mount; 2 quick retries at 1.5s absorb a blip. No cold-start wake logic - the VM deploy is always on, so a failure here means something is actually wrong |
| `hooks/use-run-poll.ts`                    | 2.5s run polling + debounced `aria-live` announcement                                                                                                                                |
| `hooks/use-external-store.ts`              | `useSyncExternalStore` over `localStorage` and `matchMedia`                                                                                                                          |
| `hooks/use-org-scoped-effect.ts`           | `useEffect`, structurally forced to re-run when the active organisation changes - the standard pattern for org-scoped data fetching, used by 9 fetch sites                           |
| `hooks/use-reveal.ts`, `use-typewriter.ts` | Scroll reveal, hero typing                                                                                                                                                           |

### `components/` - all 66 files

**`brand/` (4)** - the visual identity.

| File             | Role                                                                                                     |
| ---------------- | -------------------------------------------------------------------------------------------------------- |
| `lamp.tsx`       | One status lamp. Replays `relay-settle` on state change via a remount key. Never animates when `off`     |
| `lamp-strip.tsx` | A row of lamps + optional counts line. Carries **one** summarising `aria-label`; lamps are `aria-hidden` |
| `mark.tsx`       | Inline SVG: three lamps in a capsule. Capsule inherits `currentColor`                                    |
| `wordmark.tsx`   | `CallFlow` + mono `AI`, as live text. Also exports `BrandLockup`                                         |

**`ui/` (23)** - primitives, Radix-backed where focus or ARIA is involved.

| File                                     | Notes                                                                                                                                                            |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `button.tsx`                             | 4 variants, 3 sizes, `asChild`, loading state that locks width                                                                                                   |
| `input.tsx`                              | `Input`, `Textarea`, `SearchInput`, `MinLengthCounter`. Phone variant normalises on blur                                                                         |
| `field.tsx`                              | Label/hint/error wiring + `aria-describedby`; also `ErrorSummary`                                                                                                |
| `select.tsx` `switch.tsx` `checkbox.tsx` | Radix Select / Switch / Checkbox + `RadioGroup`                                                                                                                  |
| `dialog.tsx`                             | `Dialog` and `Sheet`, shared overlay, focus trap                                                                                                                 |
| `disclosure.tsx`                         | `Tabs`, `TabPanel`, `Accordion`, `Popover`                                                                                                                       |
| `dropdown-menu.tsx`                      | Menu, checkbox items, destructive item                                                                                                                           |
| `toast.tsx`                              | Provider + `useToast`, 4 tones, stack max 3, ref-counter ids                                                                                                     |
| `tooltip.tsx`                            | 400ms delay; `wrapTrigger` for disabled controls                                                                                                                 |
| `badge.tsx`                              | `LampBadge` (colour-mix surface + `-text` colour) and neutral `Tag`                                                                                              |
| `panel.tsx`                              | `Panel`, `Eyebrow`, `SectionHeading`                                                                                                                             |
| `code-block.tsx`                         | Mono block, monochrome JSON tokeniser, `bare` mode, `CopyButton`                                                                                                 |
| `stat.tsx`                               | `Stat` + axis-free `Sparkline`                                                                                                                                   |
| `rule.tsx`                               | Hairline, `withLamps` variant, `VRule`                                                                                                                           |
| `reveal.tsx`                             | `Reveal`, `RevealGroup`, `RevealItem` on framer-motion                                                                                                           |
| `empty-state.tsx` `skeleton.tsx`         | Icon + title + body + action; shimmer-free skeletons                                                                                                             |
| `password-strength.tsx`                  | 4-segment lamp meter + upfront rule checklist                                                                                                                    |
| `area-chart.tsx`                         | `AreaChart` - monochrome trend line; deliberately carries none of the five lamp colours                                                                          |
| `donut-chart.tsx`                        | `DonutChart` - the one chart allowed to fill segments with lamp colours, since a disposition breakdown genuinely is call-state meaning                           |
| `image-upload.tsx`                       | `ImageUpload` - uploads straight to Supabase Storage (`avatars`/`org-logos` buckets) from the browser; used by profile and organisation-logo onboarding/settings |

**`marketing/` (13)** - home and solution page sections.

| File                                      | Role                                                                                                                                                                                                                                                        |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hero.tsx`                                | A fully scripted example call - two typewriter beats (the line heard, then the typed JSON result) synced to a voice waveform, parallax grid behind. Makes **no API call at all**; never shows an error, because the scripted sequence is all there ever was |
| `voice-wave.tsx`                          | Waveform whose envelope is derived from the spoken text - deterministic, no randomness                                                                                                                                                                      |
| `problem-compare.tsx`                     | Two identical call-log rows vs. the same rows with lamps                                                                                                                                                                                                    |
| `steps.tsx`                               | Four steps, each with a live mini-UI panel rather than a screenshot                                                                                                                                                                                         |
| `capability-grid.tsx`                     | Six capability cards, `surface-flow` + hover lift                                                                                                                                                                                                           |
| `vertical-strip.tsx`                      | The four solutions as rows, not cards                                                                                                                                                                                                                       |
| `safety-section.tsx`                      | Live `SafetyBar` with one guard shown **off**                                                                                                                                                                                                               |
| `pricing-preview.tsx` `pricing-table.tsx` | 3-plan preview; full plan cards, `SegmentedToggle`, `FeatureMatrix`                                                                                                                                                                                         |
| `price-value.tsx`                         | `PriceValue`, `RateValue`, `VolumeValue`, `TodoChip` for unset numbers                                                                                                                                                                                      |
| `cost-comparison.tsx`                     | Tele-caller vs CallFlow, with editable assumptions                                                                                                                                                                                                          |
| `roi-calculator.tsx`                      | Leads with **hours**, not money                                                                                                                                                                                                                             |
| `final-cta.tsx`                           | Closing card with grid backdrop                                                                                                                                                                                                                             |

**`app/` (15)** - dashboard. **`dry-run-switch.tsx` is deleted** - there is nothing left to
switch; every run composer and the welcome flow start a real run directly.
**`prewarm.tsx` is also deleted**, along with the `/api/wake` route handler it fired - the
deployment is a single always-on VM, not a cold-starting free tier, so there is nothing
left to pre-warm (`hooks/use-connection.ts` below no longer has wake/retry logic either).

| File                       | Role                                                                                                                                                                                                                                                                                                                                                              |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data-table.tsx`           | Sticky header, sort, selection bar, column visibility, CSV export, pagination, mobile card fallback                                                                                                                                                                                                                                                               |
| `campaign-editor.tsx`      | Two-pane composer with sticky live goal + schema preview                                                                                                                                                                                                                                                                                                          |
| `campaign-card.tsx`        | Card with field tags and last-run mini strip                                                                                                                                                                                                                                                                                                                      |
| `contact-grid.tsx`         | Spreadsheet grid, paste, CSV drop, per-row inline errors                                                                                                                                                                                                                                                                                                          |
| `safety-bar.tsx`           | Guard chips with popovers; `guardsFromSafety()`, reading this org's real `GET /api/v1/safety` values, not just the deployment defaults                                                                                                                                                                                                                            |
| `escalation-card.tsx`      | Worklist item with typed reasoning chain                                                                                                                                                                                                                                                                                                                          |
| `transcript-view.tsx`      | Conversation left, typed result + triage chain right                                                                                                                                                                                                                                                                                                              |
| `masked-phone.tsx`         | Masked by default; **no prop to disable masking**                                                                                                                                                                                                                                                                                                                 |
| `connection-banner.tsx`    | Silent unless the service genuinely doesn't respond - no cold-start sequence to play                                                                                                                                                                                                                                                                              |
| `settings-section.tsx`     | `SettingsSection` (with `effect` line) + `NotWiredNotice`                                                                                                                                                                                                                                                                                                         |
| `onboarding-gate.tsx`      | `OnboardingGate` - renders a non-dismissible modal (org name, then a skippable profile step) over any `/app/*` page while `active.onboarded_at` is `null`; a server signal, not `localStorage`. Owns one `useSession()` instance for both steps deliberately - a separate-page-per-step version had each step reading its own independent, stale session snapshot |
| `session-gate.tsx`         | `SessionGate` - renders once the session resolves signed-in; a skeleton while loading, a retry panel otherwise, so pages stop each collapsing that into a silent blank render                                                                                                                                                                                     |
| `overview-org-section.tsx` | `TeamControls` - the dashboard's team summary popover. Its "Manage" link goes to `/app/organisation?tab=team`, not a dialog                                                                                                                                                                                                                                       |
| `invite-dialog.tsx`        | Email + role "invite a teammate" dialog, shared by `/app/organisation`'s Team pane and the dashboard's team popover                                                                                                                                                                                                                                               |

**`layout/` (11)**

| File                              | Role                                                                                                                                                                               |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `site-header.tsx`                 | Hover mega-menus with a single-open coordinator that re-reads `:hover` on close                                                                                                    |
| `site-footer.tsx`                 | 4 columns, legal row, capability band, BrBik credit                                                                                                                                |
| `site-loader.tsx`                 | First-paint brand loader; CSS fade + JS unmount at 1700ms so it can never trap the page                                                                                            |
| `view-transitions.tsx`            | Intercepts internal links, drives `document.startViewTransition`, resolves on real route change with a timeout backstop                                                            |
| `app-shell.tsx`                   | No sidebar: a `grid-cols-[1fr_auto_1fr]` header (brand, primary nav, credit balance + org switcher + account menu) plus a bottom `AppTabBar` below `lg`                            |
| `app-nav.tsx`                     | Nav constants (`NAV_ITEMS`/`PRIMARY_NAV_ITEMS`), `OrgMark`, and `AppTabBar` (the mobile tab bar) - not a sidebar component                                                         |
| `user-menu.tsx`                   | `UserMenu` - avatar dropdown: profile, settings, sign out. No org switcher here - that's `HeaderOrgSwitcher` in `app-shell.tsx`, so the action doesn't exist in two places at once |
| `docs-shell.tsx`                  | Three-pane docs; TOC read from rendered DOM headings                                                                                                                               |
| `auth-card.tsx` `auth-notice.tsx` | Auth card shell; the honest "not connected" notice                                                                                                                                 |

Root layout mounts `NuqsAdapter` → `TooltipProvider` → `ToastProvider`, plus `SiteLoader`
and `ViewTransitions` as siblings.

### Actions available per dashboard page

| Page                                               | Actions                                                                                                                                                                                    | Hits                                                                                            |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| `/app` (Dashboard)                                 | View volume/disposition/outcome-distribution summaries, open a recent run, resolve an escalation inline (local, unpersisted - reassignment is a stub toast, not wired up at all), navigate | `GET /api/v1/runs`, `GET /api/v1/runs/{id}`                                                     |
| Org-setup modal (any `/app/*` page, not a route)   | Confirm the org's real name - the one mandatory, non-skippable step - then a skippable name + avatar step                                                                                  | `POST /api/v1/organisations/me/complete-onboarding`, `PATCH /api/v1/me`                         |
| `/app/campaigns`                                   | Filter all/template/custom, duplicate, delete, run                                                                                                                                         | `GET`/`DELETE /api/v1/campaigns`                                                                |
| `/app/campaigns/new`, `/[id]`                      | Edit name/goal/fields/region/language/window/retry, preview with a different contact (rendered locally, not via the API), save                                                             | `POST /api/v1/campaigns`                                                                        |
| `/app/runs`                                        | Sort, paginate, change page size, export CSV, open run                                                                                                                                     | `GET /api/v1/runs`                                                                              |
| `/app/runs/new`                                    | Paste/import/edit contacts, remove invalid, pick campaign, preview the goal (rendered locally), start - **no dry-run toggle; Start run always dials**                                      | `POST /api/v1/runs`                                                                             |
| `/app/runs/[id]`                                   | Watch lamps settle, pause updates, stop (updates only), open transcript sheet                                                                                                              | `GET /api/v1/runs/{id}` every 2.5s                                                              |
| `/app/escalations`                                 | Filter reason/campaign, sort oldest/newest, open transcript, call back / reassign / mark resolved                                                                                          | derived; no endpoint                                                                            |
| `/app/contacts`                                    | Search, view call counts, suppress a number, remove suppression                                                                                                                            | `localStorage` only - disconnected from the real `suppressions` table the dial path checks (§7) |
| `/app/settings` (Organisation), `/team`, `/safety` | Rename/re-logo the org, invite/remove/re-role teammates, read the safety guards                                                                                                            | `PATCH /api/v1/organisations/me`, `.../members`, `.../invitations`, `GET /api/health`           |
| `/app/settings/api-keys`                           | Create (full key shown exactly once), list (prefix, last used, created), revoke                                                                                                            | `GET`/`POST /api/v1/api-keys`, `DELETE /api/v1/api-keys/{id}`                                   |
| `/app/settings/integrations`                       | Connect, update, or disconnect Twilio/Plivo credentials                                                                                                                                    | `GET`/`PUT`/`DELETE /api/v1/integrations/providers/{provider}`                                  |
| `/app/settings/billing`                            | View the current plan and today's real usage - no upgrade flow                                                                                                                             | `GET /api/v1/me`, `GET /api/health`                                                             |
| `/app/welcome`                                     | 4-step onboarding ending in a real, live call - the copy is explicit ("This places a real call to each contact above")                                                                     | `POST /api/v1/runs`                                                                             |

---

## 9. Where the UI is ahead of the API

Consistent with `web/DESIGN_NOTES.md` §5.

| Surface                                                                                                              | Reality                                                                                                            |
| -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Dashboard, runs, escalations, contacts                                                                               | **Real** - derived from hydrated runs                                                                              |
| Safety pane (editable, org-scoped)                                                                                   | **Real** - from `GET/PATCH /api/v1/safety`                                                                         |
| Voice-API-key status, status page, credit balance                                                                    | **Real** - from `/api/health` (deployment defaults only, no per-org usage - see §5)                                |
| Campaign editor (name, goal, fields, region, language)                                                               | **Real**                                                                                                           |
| Organisation setup gate, team, API keys, Integrations (credential storage), Billing (plan + usage), Suppression list | **Real** - see §3. Integrations doesn't yet place a call over a connected number; Billing has no payment processor |
| Calling window, retry policy, onboarding progress                                                                    | **Local only** - `localStorage`                                                                                    |
| Numbers, notifications, webhooks                                                                                     | **Not wired** - validate then say so                                                                               |

The governing rule, applied throughout: **never show a success state for something that
did not happen.** Every unwired action reports honestly via `AuthNotice` / `NotWiredNotice`.

---

## 10. Configuration

### Backend - `app/core/config.py`

Env vars covering the calling domain's safety limits are below; `config.py` also holds the
Supabase/database/email settings that back auth and persistence (`SUPABASE_URL`,
`DATABASE_URL`, `PHONE_HASH_PEPPER`, `RESEND_API_KEY`, …) - see `SUPABASE_SETUP.md`.

| Variable                                     | Default | Purpose                                                                                                                                                                                                                                        |
| -------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CALLE_API_KEY`                              | `""`    | Voice API key. Empty ⇒ every run is refused with 400                                                                                                                                                                                           |
| `CALLE_DEFAULT_REGION`                       | `IN`    | Fallback calling region                                                                                                                                                                                                                        |
| `CALLE_DEFAULT_LANGUAGE`                     | `en`    | Fallback locale                                                                                                                                                                                                                                |
| `CALLFLOW_MAX_CALLS_PER_RUN`                 | `3`     | Hard per-run ceiling                                                                                                                                                                                                                           |
| `CALLFLOW_ALLOWLIST`                         | empty   | Comma-separated E.164. Non-empty ⇒ only these dialable                                                                                                                                                                                         |
| `CALLFLOW_CORS_ORIGINS`                      | empty   | Extra browser origins; bare hostnames get `https://`                                                                                                                                                                                           |
| `CALLFLOW_RATE_LIMIT_CALLS`                  | `5`     | Live calls per IP per window                                                                                                                                                                                                                   |
| `CALLFLOW_RATE_LIMIT_WINDOW`                 | `3600`  | Window, seconds                                                                                                                                                                                                                                |
| `CALLFLOW_DAILY_BUDGET`                      | `20`    | Shared daily live-call ceiling                                                                                                                                                                                                                 |
| `CALLFLOW_OWNER_KEY`                         | `""`    | Lifts rate limits via `X-CallFlow-Owner-Key`                                                                                                                                                                                                   |
| `PROVIDER_CREDENTIALS_KEY`                   | `""`    | Fernet key encrypting Settings → Integrations credentials at rest. Same sensitivity class as `SUPABASE_SECRET_KEY` - never enters the database. Unset ⇒ `core/crypto.py` raises `CredentialsNotConfigured` (503) rather than storing plaintext |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | `""`    | Read but **unused** - no WhatsApp code path exists                                                                                                                                                                                             |

Not settable: `poll_interval_seconds` (10.0), `poll_timeout_seconds` (900.0) are hard-coded.
CORS also always allows `localhost:3000` plus a regex for `*.onrender.com` / `*.vercel.app`.

### Frontend - `web/.env.example`

| Variable                                                    | Purpose                                                                                                                          |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `NEXT_PUBLIC_API_URL`                                       | Where the browser reaches the API. Rejected at runtime and falls back to a public URL if it resolves to an internal-only address |
| `NEXT_PUBLIC_SITE_URL`                                      | Canonical + social-card base                                                                                                     |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public - safe for the browser, RLS still applies. Used by `lib/supabase/`                                                        |

`web/.env.local` holds working dummy values and is gitignored.

---

## 11. Testing, CI, deployment

**Tests** - 147 collected across 12 files (verified via `pytest --collect-only -q`).
`pytest -q`, `ruff check app tests`.

| File                           | Tests | Covers                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------ | ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_rls_isolation.py`        | 31    | Cross-tenant isolation against the real database - signup trigger, org/user/membership/suppression invisibility, forged-org-id insert rejected, anon sees nothing, `postgres` bypass, account-deletion cascade + slug reuse, API-key resolution (matches owning tenant, revoked, live-membership), provider credentials (invisible cross-tenant, owner/admin-only write). **Cross-role, new this phase:** the admin-to-owner grant guard - granted-role and target-role checks on `memberships_update`/`_insert`/`_delete` and `invitations_insert`, the invitee-cannot-mutate-their-own-invitation-role and invitation-cannot-seat-someone-else guards, and real (non-mocked) invitation creation/refresh through `org_repo.create_invitation()` proving the `SECURITY DEFINER` upsert fix actually works end to end (15 tests) - `ISSUES.md` #43/#44. Skipped when `DATABASE_URL` is unset |
| `test_safety.py`               | 22    | E.164, masking, gate decisions                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `test_orchestrator.py`         | 18    | Goal rendering, the async dial pipeline, ceiling + suppression gating, extraction shapes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `test_organisations_routes.py` | 18    | The admin-to-owner grant guard's API layer, called through the real route handlers directly - `ISSUES.md` #43                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `test_permissions.py`          | 16    | `can_grant_role()`/`can_act_on_member()` - pure, no database - `ISSUES.md` #43                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `test_triage.py`               | 14    | Precedence rules - the most thoroughly tested module                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `test_ratelimit.py`            | 12    | Windows, budget, owner bypass, reserve/release                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `test_config.py`               | 5     | Env parsing and defaults                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `test_crypto.py`               | 4     | Round-trips, nonce uniqueness, missing-key and tampered-ciphertext both fail closed. Pure - no database                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `test_engine.py`               | 3     | `EngineGateway`'s conformance to the `VoiceProvider` protocol, against a second stub implementation                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `test_live_progress.py`        | 3     | In-flight status callbacks                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `test_campaigns.py`            | 1     | `slugify()` only - org-owned campaign CRUD needs a live Postgres connection, so it isn't covered by this local suite                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |

`test_samples.py` and `app/domain/samples.py` are both gone - there is nothing left to
sample once every run dials for real. `run_store.py` is gone with them.

**No frontend tests exist.**

**CI** - `.github/workflows/ci-cd.yml`, on PR and push to `main`, `cancel-in-progress`:

1. `backend` - Python 3.11, `pip install -e ".[dev]"`, ruff, pytest
2. `frontend` - Node 20, `npm ci`, lint, type-check, build
3. `deploy` - push to `main` only, needs both, SSH to VM: `git pull` → `pip install -e .` →
   `pm2 restart callflow-api` → `npm ci && npm run build` → `pm2 restart callflow-web`,
   then curls `/api/health` and `/`

**Deployment** - one VM, pm2 processes `callflow-api` (uvicorn) and `callflow-web` (next
start), both behind `callflow-ai.brbik.com`. Secrets via GitHub Actions `vars`/`secrets`.

> ⚠️ **`render.yaml` is stale.** It describes a two-service Render deploy with
> `healthCheckPath: /`, which is not how this ships. Delete it or mark it unused.

**Local pre-commit hook** (`.githooks/pre-commit`, opt-in) resolves ruff/pytest from
`.venv` first, falls back to PATH, and skips with a warning rather than blocking if
neither is present.

---

## 12. `FEATURES.md` gap map

| F       | Feature                                                 | Status     | Note                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ------- | ------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1      | Repo, envs, config                                      | ⚠️ Partial | Flat repo not monorepo; no `uv`/`pnpm`/mypy/Docker; config is a dataclass not `pydantic-settings`, and does not refuse to boot on a missing var                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| F2      | Database schema                                         | ⚠️ Partial | Core relational schema is real: `users`, `organisations`, `memberships`, `suppressions`, `campaigns`, `runs`, `call_outcomes`, `api_keys`, `provider_credentials`, `org_safety_settings`, all RLS'd. No credit ledger, billing, or audit-log tables yet                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| F3      | Authentication                                          | ✅         | Real Supabase Auth: signup/signin/signout, password reset, JWT verification (JWKS, 30s clock-skew leeway), plus a second path - org-scoped API keys (`cfk_…`) resolved through a SECURITY DEFINER function for programmatic access. This row was stale (marked "UI stubs only") for several iterations after auth actually shipped - fixed here                                                                                                                                                                                                                                                                                                                                                                                                          |
| F4      | Organisations, membership                               | ✅         | Real, RLS-scoped Postgres: create/rename/delete an organisation, membership + roles, team invitations by email, and a mandatory server-verified onboarding gate (`organisations.onboarded_at`) that confirms the org's real name before the dashboard is reachable (`OnboardingGate`, `POST /api/v1/organisations/me/complete-onboarding`)                                                                                                                                                                                                                                                                                                                                                                                                               |
| F5      | Authorisation, RLS                                      | ✅         | RLS enabled and forced on every tenant-scoped table, `app/auth/permissions.py`'s one role→permission matrix, `RequirePermission` FastAPI dependency, 31 cross-tenant/cross-role isolation tests hitting the real database. Also stale as "❌" until this pass. Role-hierarchy grant guard (`can_grant_role()`/`can_act_on_member()`, API + RLS) closed a real admin-to-owner privilege-escalation hole, including a column-privilege gap on `invitations.role` and a missing target-role check that would have let an Admin still act on an existing Owner's row. The column-privilege fix itself regressed invitation creation entirely (fixed via a `SECURITY DEFINER` upsert function, `public.create_or_refresh_invitation()`) - `ISSUES.md` #43/#44 |
| F6      | Audit log                                               | ❌         |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| F7      | API conventions                                         | ⚠️ Partial | FastAPI + Pydantic models ✅; **now under `/api/v1` throughout** - campaigns and runs joined organisations/invitations/profile there in this change. Still no idempotency, cursor pagination, or problem details                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| F8      | Background jobs                                         | ⚠️ Partial | `BackgroundTasks` only; single-process, no claim/retry/heartbeat                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| F9      | Observability                                           | ⚠️ Partial | stdlib logging + `/` health; no Sentry, structured JSON, or `/health/deep`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| F10     | Rate limiting                                           | ⚠️ Partial | Now correctly keyed per organisation, with a real per-org override (`ISSUES.md` #32, #33) - the cross-tenant sharing bug is fixed. Still in-process - resets on restart, wrong across replicas. Not Redis                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| F11     | Secrets management                                      | ⚠️ Partial | GH secrets + gitignore; no gitleaks, no rotation drill                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| F12     | Email                                                   | ⚠️ Partial | Team invitations are wired end to end (`EmailGateway`/`apps/api/app/integrations/email/resend.py` → Resend's HTTP API) and password reset goes through Supabase Auth's own mailer - but invitations have never actually delivered in this environment: `RESEND_FROM_EMAIL`'s domain was never verified in Resend, so every send is rejected 403 (`ISSUES.md` #51, PARTLY FIXED - the error is now specific and actionable, but verifying a real domain is a human dashboard step, not something code can do). This row was stale as "❌" - the integration exists, it's the domain that isn't ready                                                                                                                                                      |
| F13     | Contacts and lists                                      | ⚠️ Partial | Parse + validate + dedupe-in-file ✅; no storage, no `phonenumbers`, no import history                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| F14     | Suppression list                                        | ⚠️ Partial | **Now checked before every dial**, against the org's real `suppressions` table - the "never dialled again" guarantee holds for rows already in that table. But nothing writes to it yet: no CRUD route, `add_suppression()` has no caller, and a `do_not_call` disposition doesn't auto-add the number. The UI's own suppression list is still a disconnected `localStorage` list                                                                                                                                                                                                                                                                                                                                                                        |
| F15     | Campaigns                                               | ⚠️ Partial | Create/edit/preview ✅; **now persisted** as org-scoped Postgres rows. Still no versioning, 2 built-ins not 6                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| F16     | Result schema builder                                   | ⚠️ Partial | Visual builder ✅; 4 wire types, `date`/`enum` mapped onto `string`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| F17     | Voice provider abstraction                              | ⚠️ Partial | One wrapper, vendor contained. **No protocol, no capabilities, no error taxonomy, no second adapter.** Org-owned Twilio/Plivo credential storage now exists (Settings → Integrations, encrypted at rest) as groundwork, but nothing yet routes a call through either - that's separate, explicitly not-yet-built "voice-agent platform" work                                                                                                                                                                                                                                                                                                                                                                                                             |
| F18     | Runs and orchestration                                  | ⚠️ Partial | **Runs and outcomes are now Postgres-backed**, updated as each call resolves. Still sequential and single-process within a run; no state machine beyond running/completed/failed, no pause/stop/cancel endpoint, no calling-window enforcement, no crash recovery if the process dies mid-run                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| F19     | Safety gate                                             | ⚠️ Partial | 6 of 9 guards (suppression now included; dry run no longer exists as a concept to count). Missing calling-window enforcement, credit-balance check, consent flag                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| F20     | Call execution                                          | ⚠️ Partial | Polling only, no webhooks; no billable flag or provider cost recorded                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| F21     | Typed extraction                                        | ✅         | Native `result_schema`, no transcript scraping. Not validated against the schema on return                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| F22     | Triage engine                                           | ✅         | Pure, precedence-ordered, 14 tests. No custom org rules                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| F23     | Escalation queue                                        | ⚠️ Partial | Full worklist UI; resolution is not persisted, no assignment or SLA                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| F24     | Retry orchestration                                     | ❌         | `RETRY` disposition is produced but nothing acts on it                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| F25     | Transcripts, recordings                                 | ❌         | Transcript held in memory on the outcome; no R2                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| F26     | Analytics                                               | ⚠️ Partial | Dashboard stats computed client-side; no rollups or campaign comparison                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| F27     | Realtime                                                | ⚠️ Partial | 2.5s polling with debounced announcements; no Supabase Realtime                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| F28–F31 | Inbound, scheduling, WhatsApp, CRM                      | ❌         | WhatsApp env vars read but unused                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| F32     | Outbound webhooks                                       | ❌         | UI + docs describe them; no implementation                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| F33     | Public API, keys                                        | ⚠️ Partial | **API keys are now real** - `GET/POST /api/v1/api-keys`, `DELETE .../{id}`; only a SHA-256 hash is stored, and the key actually authenticates (`current_user()`'s `cfk_…` path). No published API docs beyond this reference, no per-key rate limits or scopes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| F34     | Exports                                                 | ⚠️ Partial | Client-side CSV from the visible table                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| F35–F41 | Plans, credits, payments, invoicing, dunning, referrals | ⚠️ Partial | `organisations.plan_id` (real, default `'free'`) and today's real usage are now surfaced honestly at Settings → Billing, ending in a `NotWiredNotice` about no payment processor. `lib/pricing.ts` itself is still presentation only, all prices `null`. No credit ledger, payments, invoicing, dunning, or referrals                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| F42     | AI disclosure, consent                                  | ⚠️ Partial | Disclosure is _copy_ in built-in goals and settings UI. **Not enforced in a compiler** - a goal can be saved without one                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| F43     | Retention, subject rights                               | ❌         |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| F44     | Regional compliance                                     | ⚠️ Partial | Region/language fields exist; no per-region rules                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| F45     | Phone masking                                           | ✅         | One implementation per side, used everywhere. No reveal permission or log-filter backstop                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| F46     | Security hardening                                      | ⚠️ Partial | Pydantic validation; SQL is now real but parameterised throughout (asyncpg placeholders, never string interpolation) - no injection surface introduced by persistence. No CSP/HSTS, CSRF, or dependency scanning                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| F47     | Onboarding                                              | ⚠️ Partial | Org-name confirmation is now a real, server-verified, non-skippable gate (`organisations.onboarded_at`) ✅ - not `localStorage`, cannot be bypassed by clearing storage. Followed by a skippable profile-details step, then the existing 4-step walkthrough ending in a real, live call; walkthrough progress is still `localStorage`, no PostHog                                                                                                                                                                                                                                                                                                                                                                                                        |
| F48     | Marketing, docs, blog                                   | ✅         | 20 marketing routes, 8 MDX docs, OG images, sitemap-ready. No blog                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| F49     | Product analytics                                       | ❌         |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| F50–F52 | Support, status page, admin console                     | ⚠️ Partial | `/status` and `/maintenance` pages exist and check health live; no external monitor or admin console                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |

**Totals:** 7 built · 34 partial · 11 not built.

---

## 13. Known issues found while auditing

Ordered by how much they'd hurt.

1. **CLOSED - `CallOutcome.run_id` used to hold the _provider's_ call id, not the run id.**
   Migration `202608070900_campaigns_runs_and_call_outcomes` plus the accompanying
   `routes/runs.py` change fixed this at the API boundary: the vendor's id now has its own
   `provider_call_id` column and field, and the API's `run_id` is always the real run id.
   One internal wart remains - `CampaignRunner`/`CallOutcome` still uses the `run_id`
   field as scratch space for the vendor's call id while a call is in flight
   (`services/campaign_runner.py`); only `routes/runs.py` remaps it before persisting.
2. **CLOSED - user campaigns were global and ephemeral.** `app/domain/campaigns.py`'s
   module-global registry is gone. Custom campaigns are real, org-scoped Postgres rows
   (`public.campaigns`, RLS-enforced) via `database/repositories/campaigns.py`.
3. **PARTIALLY CLOSED - suppression is now enforced in the dial path.**
   `check_dial_allowed` denies a dial when `is_suppressed` is true, and
   `POST /api/v1/runs` resolves that flag against the org's real `public.suppressions`
   table before a run starts - the check the product's "never dialled again" promise
   depended on is real for the first time. What's still open: there is no route to add a
   number to that table (`add_suppression()` has no caller), and a `do_not_call`
   disposition doesn't add one automatically - see §7.
4. **Rate limits and the daily budget reset on restart** and are per-process, so the
   "shared daily budget" is neither shared nor durable.
5. **Escalation resolution is component state.** Marking resolved survives until navigation.
6. **`render.yaml` contradicts the real deploy** and will mislead the next person.
7. **Three high-severity npm advisories** in Next 16.2.12's `postcss`/`sharp`. Fixed by
   16.3.0; deliberately not bumped.
8. **`escalate_on_negative` is misnamed** - it gates a _retry_, not an escalation.
9. **`POST /api/v1/campaigns/preview` has no caller.** Both the campaign editor and the
   run composer render the goal preview locally (`lib/campaign-fields.ts`'s
   `renderGoalPreview`) instead of calling it. Not wrong, but the endpoint and the
   `api.preview` client method are currently dead code from the product's point of view.

---

## 14. The rule that shapes the schema

Application code must never reference `auth.users.id`. Every table points at
`public.users.id`, which carries an `auth_user_id` column mapping to the provider -
so changing auth providers later is repopulating one column, not a rewrite. (This
section used to be "Immediate next step - auth," a plan for work that has since
fully shipped across several iterations - see `ISSUES.md` iterations 2 and 3. Only
the one fact worth keeping from it is retained here.)
