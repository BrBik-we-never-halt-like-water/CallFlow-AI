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
│   │   │   └── integrations/voice/ protocol.py - no adapter implements it yet
│   │   ├── alembic/                env.py + 20 revisions
│   │   ├── tests/                  12 files, 202 tests
│   │   └── pyproject.toml
│   ├── voice-runtime/              LiveKit Agents worker - a third pm2 process
│   │   └── app/                    worker (lifecycle) · pipeline (plugin registry)
│   │                               · reporter (completion callback) · config
│   └── web/                        Next.js
│       ├── app/                    (marketing) · (auth) · (app)/app
│       ├── components/             brand · ui · marketing · app · layout
│       ├── lib/                    api client, supabase/, auth/, format/, hooks/
│       ├── middleware.ts           session refresh + /app/* gating
│       └── DESIGN_NOTES.md
├── packages/shared/                (empty - for generated TS types)
├── scripts/db.js                   npm db:migrate/generate/reset -> Alembic, apps/api
├── package.json                    repo-root only - just wraps the database commands
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
| **Escalations**                   | Filter by reason/campaign/age, sort oldest-first, open transcript, assign to a teammate (admin/owner), mark resolved - live-synced across teammates                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | `GET /api/v1/escalations`, `POST .../assign`, `POST .../resolve`                                                                  | ✅ org-scoped Postgres row (`escalations`), one per escalating call outcome; Realtime-pushed to every signed-in teammate                                                            |
| **Sharing** (Phase 4)              | Operator: browse a name-only, org-wide directory of teammates' campaigns/open escalations, request access/to help (with an optional message). Owner of a resource: approve (clones the campaign, or hands off the escalation) or reject, from the Organisation page's "Sharing" tab - live-synced across teammates                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `GET .../campaigns/directory`, `GET .../escalations/directory`, `GET/POST /api/v1/share-requests`, `POST .../{id}/approve\|reject` | ✅ org-scoped Postgres row (`share_requests`); Realtime-pushed to requester and owner                                                                                              |
| **Contacts list**                 | Search, view call history                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | none - derived from run outcomes                                                                                                  | ❌                                                                                                                                                                                  |
| **Suppression list**              | View, add, and remove (owner-only) - org-wide, checked before every dial                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | `GET/POST /api/v1/suppressions`, `DELETE /api/v1/suppressions/{id}`                                                               | ✅ org-scoped Postgres row; the same table `check_dial_allowed()` checks (see §7)                                                                                                   |
| **Calling window / retry policy** | Edit per campaign                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | none                                                                                                                              | ⚠️ `localStorage`, never sent to the API, not enforced                                                                                                                              |
| **Org setup gate**                | Mandatory, non-skippable name confirmation on a fresh organisation, then a skippable profile-details step                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | `POST /api/v1/organisations/me/complete-onboarding`, `PATCH /api/v1/me`                                                           | ✅ `organisations.onboarded_at`, server-verified - not `localStorage`                                                                                                               |
| **Onboarding**                    | 4-step walkthrough ending in a real, live call, reached only after the org-setup gate clears                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | `POST /api/v1/runs`                                                                                                               | ⚠️ step index in `localStorage`                                                                                                                                                     |
| **Status page**                   | Live health check with latency                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | `GET /api/health`                                                                                                                 | n/a                                                                                                                                                                                 |
| **Auth**                          | Sign up, sign in, sign out, password reset, `/app/*` gating, user menu with org + role                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Supabase Auth + `GET /api/v1/me`                                                                                                  | ✅ Postgres, RLS-scoped                                                                                                                                                             |
| **Organisation + membership**     | Auto-created at signup (owner role granted by the trigger). A second organisation is created from a dedicated two-step `/app/organisation/new` (name, then an optional logo - logo is a separate step because Storage RLS scopes uploads by `org_id`, which doesn't exist until the org does). Managed - name, logo, delete - from `/app/organisation`, a dedicated page, not a dialog or a Settings tab                                                                                                                                                                                                                                                                                                                                                                                                                                   | signup trigger; `POST /api/v1/organisations` via `public.create_organisation()`                                                   | ✅ Postgres                                                                                                                                                                         |
| **Team**                          | Invite by email (role chosen), list members + pending invites, change a member's role, remove a member - from `/app/organisation`'s Team pane. A caller may only grant a role strictly below their own rank (owner > admin > operator > viewer; Owner is the one exception, who may grant any role including owner itself), and may only act on - update or remove - a member whose _current_ role is strictly below their own. Enforced at both the API (`can_grant_role()`/`can_act_on_member()`) and RLS layers; self-targeting (e.g. an Admin stepping themselves down) is exempt from the second check. Accepting an invitation cannot be used to escalate - invitation `role` is not writable by `authenticated` past creation, and a valid invitation can only seat its own invitee, never an arbitrary `user_id` (`ISSUES.md` #43). `/accept-invite/[token]` shows the invited email read-only alongside the name/password fields for a new account; if opened while already signed in as a *different* email, it says so directly and offers Sign out, rather than letting the accept call fail with a generic error (`ISSUES.md` #65). **Removing someone else is not a membership delete** - `public.remove_member_and_reassign_data()` (`SECURITY DEFINER`, migration `202608092600`) reassigns whatever they created in this org (`campaigns.created_by`, `runs.started_by`) to whoever removed them, then deletes their account entirely (every org they belong to, not just this one) - a product decision, not the previous lightweight behavior. Leaving your own org is unchanged (membership-only). The Team tab's Remove action requires typing the person's name to confirm, matching the org-deletion dialog's own pattern. The sidebar org-switcher is admin/owner-only; an operator/viewer sees the current org's name as plain text, no switcher | `GET/POST/DELETE /api/v1/organisations/me/members`, `.../invitations`                                                              | ✅ Postgres, RLS-scoped                                                                                                                                                             |
| **API keys**                      | Create (full key shown once), list (name, prefix, last used, created), revoke                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `GET/POST /api/v1/api-keys`, `DELETE /api/v1/api-keys/{id}`                                                                       | ✅ org-scoped Postgres row; only a SHA-256 hash is ever stored. **The key itself authenticates** - see §5                                                                           |
| **Connect a number**              | Point an org's own Twilio/Plivo number at LiveKit and register the trunk CallFlow dials out through | `POST`/`GET /api/v1/voice-agents/{id}/connect-number` | ⚠️ The workflow and its HTTP surface are real and idempotent, and every step is recorded so a retry resumes rather than orphaning a trunk. **Not exercised against a live carrier account.** Creating the voice agent it attaches to is Part 2's |
| **Integrations**                  | Connect/update/disconnect org-owned Twilio or Plivo credentials                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | `GET/PUT/DELETE /api/v1/integrations/providers/{provider}`                                                                        | ✅ credential storage is real, encrypted at rest (Fernet). ⚠️ Actually placing a call over a connected number is separate, not-yet-built work - the UI says so via `NotWiredNotice` |
| **Billing**                       | View the current plan and today's real usage against the daily budget                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | `GET /api/v1/me` (`plan_id`), `GET /api/health` (`limits`)                                                                        | ✅ plan name and usage are real. ❌ No payment processor - upgrading/downgrading is not wired                                                                                       |
| **Per-teammate credits**          | Admin/owner set a daily call allocation per teammate (Team pane); anyone sees their own allocation + today's real usage (Settings → Billing's "My credits"). **1 credit = 1 connected call** - enforced per dial, layered on top of the org-wide daily budget                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `GET/PATCH .../members/{id}/credits`, `GET .../members/me/credits`, `GET .../team-performance`                                    | ✅ org-scoped Postgres row (`member_credit_allocations`); `used_today` is a real live query counting only connected calls, not the org-wide limiter's in-process counter. ✅ Enforced at dial time (`check_dial_allowed`'s `credits_remaining`) - a teammate with no allocation row set is ungated by this check entirely, per `ISSUES.md` iteration 30 |
| **Numbers, notifications**        | UI renders; actions explain they are not connected                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | none                                                                                                                              | ❌ not wired                                                                                                                                                                        |
| **Team chat**                     | Channels and DMs between teammates in one organisation - not contact-facing SMS/WhatsApp. Search organisation members, create a channel (named, any number of teammates) or a DM - `create_channel()` is idempotent for a DM (migration `b3f7d2a891c5`): the same pair of people always converges on the same channel, race-safe via a partial unique index on `channels(org_id, dm_pair)`, not just app-level dedup - list conversations with per-conversation unread counts plus a dedicated cheap `GET .../unread-count` for the nav badge, read (cursor-paginated, tie-broken by `before_id` so an exact-timestamp collision can't skip a message)/send/edit/soft-delete messages, view a conversation's members, add/remove members, rename a channel, mark read on open, live updates via Supabase Realtime (`channels`/`messages`/`channel_members`, each its own subscription - `ISSUES.md` #96, all three set `replica identity full` so a DELETE's `old` record carries the full row rather than primary-key columns only - `ISSUES.md` #106, same reasoning `202608101000_escalations_realtime.py` already set defensively). Each conversation has a real URL, `/app/chat?c={id}` - a query param rather than a `[id]` route segment, because the list pane, the open conversation, and the "start a DM" search all live in one always-mounted `ChatShell`: Next.js remounts a `[id]/page.tsx` on every change to its own dynamic segment, which wiped all of that state (and flashed a full reload of the list) on every single conversation switch. The frontend's own `useSearchParams()` read is isolated to a stateless leaf (`ChannelIdSync`) under a `<Suspense>` boundary - Next.js requires that boundary for `useSearchParams()`, and the boundary itself is what gets torn down and rebuilt on navigation, so keeping it around only that leaf (rather than `ChatShell` as a whole) is what keeps the rest of the page from remounting too. The list pane and the open conversation render side by side once one is open, rather than the previous full-screen modal that hid the list - each pane scrolls independently (`overflow-y-auto`, with the message pane auto-scrolled to its newest message on open/send/receive, anchored instead of jumped when paging in older history) inside a viewport-relative-height container, since nothing in the shared `AppShell` chrome bounds `<main>`'s height on its own. A brief per-switch load (the channel record, then its messages) shows a small animated waveform (`WavesLoader`, reusing the first-paint `SiteLoader`'s bar motif) held for at least 500ms even on a fast/cached fetch, rather than the flat `Skeleton` used elsewhere - a loader that flashes for under a second reads as a glitch, not as feedback. Starting a DM no longer requires the "New" dialog - a debounced organisation-member search sits directly on the list pane and opens (or reopens, `create_channel()`'s DM idempotency makes this safe) a conversation on click; the "New" dialog itself is unchanged and still offers both kinds. The composer recognises `@Name` while typing, scoped to the open conversation's own members (not the whole organisation), and highlights recognised `@Name` mentions in sent messages via a client-side regex built from the channel's live roster - stored as plain text in `messages.body`, no schema change. Visibility is `channel_members` membership (RLS) **and current organisation membership** - `channels_select`/`channel_members_select`/`messages_select`/`messages_insert` all require `is_org_member(...)` in addition to `is_channel_member(...)`, so a `channel_members` row left over from before someone left the organisation no longer keeps their access - or their visibility into who else is in the channel - alive on its own; `messages_insert` and `channel_members_insert` also both require the row's own `org_id` to actually equal `channel_org_id(channel_id)` - membership alone doesn't stop someone who belongs to two organisations from writing a row whose `org_id` disagrees with its own `channel_id` (`ISSUES.md` #107); rename/remove authorisation is the channel's creator or an org owner/admin, enforced in `channels_update`/`channel_members_delete`, not the route - the creator branch of both carries the identical live-membership requirement, so a departed former creator is no longer treated as an authorised one. `remove_member()` (leaving your own org) also clears the departing user's `channel_members` rows for that org in the same transaction, as a data-hygiene complement - not the security boundary, which is the RLS change (`ISSUES.md` #101/#102). Every rejection `create_channel()` itself can raise (a cross-org member id, a malformed DM) surfaces as a clean 400 (`ValueError` from the repository), not a 500 - `ISSUES.md` #98                                                                                                                                                                                                                                                                                                                                                                                        | `GET/POST /api/v1/channels`, `GET /api/v1/channels/unread-count`, `GET/PATCH /api/v1/channels/{id}`, `POST .../members`, `DELETE .../members/{user_id}`, `POST .../read`, `GET/POST .../messages`, `PATCH/DELETE .../messages/{id}` | ✅ org-scoped Postgres (`channels`, `channel_members`, `messages`), migration `b3f7d2a891c5`                                                                                        |

Legend: ✅ persists · ⚠️ persists locally/partially · ❌ lost on restart or never stored.

---

## 4. Backend modules

| Module                                          | Purpose                                                                                                                                                                                                                                                                                                                                              | Key exports                                                                                                   |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `main.py`                                       | FastAPI app assembly: CORS, lifespan (DB pool), router includes, `/` and `/api/health` only                                                                                                                                                                                                                                                          | `app`                                                                                                         |
| `core/config.py`                                | Frozen dataclass read once from the repo-root `.env`                                                                                                                                                                                                                                                                                                 | `config`                                                                                                      |
| `core/rate_limit.py`                            | In-process sliding windows, reserve-on-check, **keyed per organisation** (not IP - `ISSUES.md` #32), with per-key overrides for an org's own `org_safety_settings`                                                                                                                                                                                   | `limiter`                                                                                                     |
| `core/crypto.py`                                | Fernet symmetric encryption for org-owned provider credentials, keyed by `PROVIDER_CREDENTIALS_KEY`                                                                                                                                                                                                                                                  | `encrypt()`, `decrypt()`, `CredentialsNotConfigured`                                                          |
| `core/logging.py`                               | The one place logging is configured. A real global `RedactingFilter` (phone/token/transcript redaction - CLAUDE.md #5) on every handler, plus `CallContext` binding `run_id`/`call_id`/`org_id` to every record emitted inside it (contextvars, composes across nested blocks). Text or JSON output via `CALLFLOW_LOG_FORMAT`                     | `configure_logging()`, `CallContext`, `RedactingFilter`                                                       |
| `auth/tokens.py`                                | JWKS/HS256 verification with 30s clock-skew leeway                                                                                                                                                                                                                                                                                                   | `TokenVerifier`, `TokenClaims`, `InvalidToken`                                                                |
| `auth/dependencies.py`                          | Bearer token → `(user, org, role)`. **Two paths**: a Supabase access token, or a `cfk_…` CallFlow API key routed through `_resolve_api_key()`; both produce the same `CurrentUser`                                                                                                                                                                   | `CurrentUser`, `current_user`, `RequirePermission`                                                            |
| `auth/permissions.py`                           | The one role→permission matrix, plus the role-hierarchy checks for _which_ role a caller may grant and _whose_ row they may act on (owner > admin > operator > viewer)                                                                                                                                                                               | `Permission`, `ROLE_PERMISSIONS`, `role_has()`, `can_grant_role()`, `can_act_on_member()`                     |
| `database/models.py`                            | SQLAlchemy tables for identity/tenancy only - structure, no RLS. `campaigns`, `runs`, `call_outcomes` are **not** ORM classes; they're hand-authored in the migration and read only through raw asyncpg in the repositories below                                                                                                                    | `User`, `Organisation`, `Membership`, `Suppression`, `OrgRole`                                                |
| `database/session.py`                           | Pool + the RLS-scoped connection + jsonb codec registration                                                                                                                                                                                                                                                                                          | `Database`, `database`                                                                                        |
| `database/privileged.py`                        | The only RLS bypass. Demands a reason, logs every use                                                                                                                                                                                                                                                                                                | `PrivilegedAccess`, `privileged`                                                                              |
| `database/repositories/campaigns.py`            | Org-owned campaign CRUD, raw asyncpg. List/get join `users` for `created_by_name`/`created_by_avatar_url` - RLS does the actual visibility narrowing, this join is only for attribution                                                                                                                                                             | `list_org_campaigns()`, `get_org_campaign()`, `create_campaign()`, `delete_campaign()`                        |
| `database/repositories/runs.py`                 | Run + call-outcome persistence, raw asyncpg. `lookup_owner_for_webhook()` is the one exception - runs on an anonymous connection, via a SECURITY DEFINER function, for the webhook receiver. `summarize_by_member()` backs the admin/owner team-summary route and has no ownership filter of its own - it leans entirely on RLS                    | `create_run()`, `append_outcome()`, `finish_run()`, `get_run()`, `list_outcomes()`, `list_runs()`, `summarize_by_member()`, `lookup_owner_for_webhook()` |
| `database/repositories/suppressions.py`         | Do-not-call list, raw asyncpg                                                                                                                                                                                                                                                                                                                        | `is_suppressed()`, `list_suppressions()`, `add_suppression()`, `remove_suppression()`                         |
| `database/repositories/safety_settings.py`      | An org's own safety-guard overrides, raw asyncpg                                                                                                                                                                                                                                                                                                     | `get_for_org()`, `upsert()`                                                                                   |
| `database/repositories/api_keys.py`             | Org-scoped API key CRUD, raw asyncpg. RLS restricts every query to owner/admin                                                                                                                                                                                                                                                                       | `list_for_org()`, `create()`, `revoke()`                                                                      |
| `database/repositories/provider_credentials.py` | Org-owned Twilio/Plivo credential storage, raw asyncpg. Only ever sees ciphertext - encryption happens in the route layer                                                                                                                                                                                                                            | `list_for_org()`, `upsert()`, `remove()`                                                                      |
| `database/repositories/channels.py`             | Internal team chat: channel CRUD + group management, raw asyncpg. `create_channel()` calls the `SECURITY DEFINER` SQL function of the same name (migration `b3f7d2a891c5`) rather than a two-step insert, avoiding the `RETURNING`-before-membership-exists race `create_organisation()` already fixed once; for a `dm` it's also idempotent and race-safe (same migration - `channels.dm_pair` plus a partial unique index), and the repository wrapper converts every rejection the SQL function can raise (`RaiseError`) into a plain `ValueError`, so a bad request 400s instead of 500ing (`ISSUES.md` #98). Every `_CHANNEL_COLUMNS` read (`list_my_channels`/`get_channel`) carries a correlated `unread_count` subquery against the caller's own `channel_members.last_read_at`; `total_unread_count()` is a separate, cheaper single-join aggregate for the nav badge specifically, deliberately not `sum()` over the per-channel query - that one pays for every channel's full member list and was being re-run on every Realtime event for every open tab in the organisation (`ISSUES.md` #99). `add_member()`/`remove_member()` are plain insert/delete - safe without a definer function since neither asks for its own row back via `RETURNING`; `add_member()` still wraps its insert in a nested `SAVEPOINT`, since `channel_members.org_id` means the insert can fail its `WITH CHECK` the same way `send_message()` always could. `rename_channel()`/`mark_read()` are plain `UPDATE`s, authorised entirely by `channels_update`/`channel_members_update`                | `create_channel()`, `list_my_channels()`, `get_channel()`, `total_unread_count()`, `add_member()`, `remove_member()`, `rename_channel()`, `mark_read()` |
| `database/repositories/messages.py`             | Internal team chat: message list/send/edit/delete, raw asyncpg. RLS (`messages_select`/`messages_insert`/`messages_update`) does the actual per-channel-membership and per-sender narrowing. `list_messages()` takes a `before`/`before_id`/`limit` cursor against `messages_channel_created_idx`, always returning oldest-first regardless of pagination - `before_id` breaks a tie when two messages share the exact same `created_at` (transaction-start time, so two genuinely concurrent sends can collide), which a bare `created_at <` cursor would otherwise silently skip one side of (`ISSUES.md` #100). `send_message()` catches a `WITH CHECK` failure (non-member posting) inside a nested `SAVEPOINT`, returning `None` instead of letting it abort the outer request transaction - same pattern `invitations_repo.accept()` uses. `edit_message()`/`delete_message()` (soft delete, `deleted_at`) both scope their `UPDATE` to `sender_id = $2` as a first filter, with `messages_update`'s RLS policy as the actual guard | `list_messages()`, `send_message()`, `edit_message()`, `delete_message()`                                     |
| `database/repositories/telephony_provisioning.py` | One row per attempt to connect a number. `start_attempt()` is idempotent by (agent, key) and returns `(row, created)` so a replay carries back the trunk ids the first attempt recorded instead of making a second trunk. `set_status()` refuses an undeclared transition | `start_attempt()`, `get_attempt()`, `latest_for_agent()`, `record_livekit_ids()`, `set_status()` |
| `domain/entities.py`                            | Pydantic domain types and terminal-status sets. **No `dry_run` field anywhere**                                                                                                                                                                                                                                                                      | `Contact`, `Campaign`, `CallOutcome`, `Sentiment`, `Disposition`, `DialFailure`                               |
| `domain/safety.py`                              | Pre-dial gate and phone masking. No I/O                                                                                                                                                                                                                                                                                                              | `is_e164()`, `mask()`, `phone_hash()`, `check_dial_allowed()`, `EffectiveSafety`, `resolve_safety_settings()` |
| `domain/provisioning.py`                        | The provisioning status machine, pure. `pending -> provisioning -> verified \| failed`, one-way: no edge leaves a terminal state, so "try again" must start a new attempt rather than revive a half-built one | `ProvisioningStatus`, `check_transition()`, `InvalidTransition`, `TERMINAL` |
| `domain/triage.py`                              | Pure disposition decision from typed fields only                                                                                                                                                                                                                                                                                                     | `triage()`, `needs_human()`                                                                                   |
| `domain/result_schemas.py`                      | The shared result contract every campaign inherits                                                                                                                                                                                                                                                                                                   | `BASE_PROPERTIES`, `build_result_schema()`                                                                    |
| `domain/campaigns.py`                           | 2 built-in constants + `slugify()`. **No runtime registry anymore** - custom campaigns are real rows, resolved through the repository above                                                                                                                                                                                                          | `TRAVEL_DISCOVERY`, `APPOINTMENT_REMINDER`, `REGISTRY`, `SCHEMAS`, `BUILT_IN_IDS`, `FIELD_TYPES`, `slugify()` |
| `domain/api_keys.py`                            | Generating and hashing CallFlow API keys. Pure - no I/O, no database                                                                                                                                                                                                                                                                                 | `generate_api_key()`, `hash_api_key()`, `looks_like_api_key()`                                                |
| `services/number_provisioning.py`               | The connect-a-number workflow across two vendors: LiveKit inbound trunk → dispatch rule → carrier config → LiveKit outbound trunk, in that order because each step needs the one before. **Nothing is transactional**, so every step records what it created immediately and a retry of the same key skips what is already done - re-running blindly is what orphans a LiveKit trunk. A part-way failure stays `provisioning` (resumable) with `last_error`; `failed` means superseded by a newer attempt | `connect_number()`, `ProvisioningRefused`, `CARRIERS` |
| `services/campaign_runner.py`                   | Per-contact pipeline - **fully `async def`**, awaiting the aiohttp-based LiveKit gateway directly (no `to_thread`). `run()` dials up to `CALLFLOW_MAX_CONCURRENT_CALLS` contacts at once (`asyncio.Semaphore`); the per-run ceiling check-and-reserve is one atomic step under a lock, race-safe under that concurrency (`ISSUES.md` #54/#60). Needs **both** a `trunk_id` and a `voice_agent`, resolved by the caller from the same voice agent - the agent travels to the worker as the `voice_agent` metadata key, which is the only key `AgentSpec.from_metadata()` reads, and a runner holding one without the other refuses before dialling (`ISSUES.md` #109). `contact.context` is spread **first** into that metadata so an uploaded CSV column cannot overwrite the goal or misaddress the completion row (`ISSUES.md` #114) | `CampaignRunner`, `render_goal()`                                                                             |
| `api/v1/routes/campaigns.py`                    | `/api/v1/campaigns` - list/create/update/delete/preview, org-scoped                                                                                                                                                                                                                                                                                  | `router`, `resolve_campaign()`                                                                                |
| `api/v1/routes/internal.py`                     | `/internal/v1/runs/{run_id}/complete` - the voice runtime's callback. Not a public API: no session, trust is the `X-CallFlow-Internal-Key` shared secret compared in constant time, and a bad key and an unknown run both give 404 so the secret cannot be used to enumerate runs. Resolves identity via `database.anonymous()` + `lookup_run_owner_for_webhook`, triages, upserts the outcome, **raises the escalation if triage asks for a person**, then closes the run if that was the last contact. The escalation belongs here and nowhere else: `run_one()` returns while the call is in flight, so the only needs-a-person disposition the run's own progress write can ever see is a contact that failed to dial (`ISSUES.md` #111) | `router`, `CallCompletion` |
| `api/v1/routes/runs.py`                         | `/api/v1/runs` - start/list/get, org-scoped, background execution | `router`                                                                                                      |
| `api/v1/routes/suppressions.py`                 | `/api/v1/suppressions` - list/add/remove the org's do-not-call list. Add is operator+, remove is owner-only, matching the RLS policy                                                                                                                                                                                                                 | `router`                                                                                                      |
| `api/v1/routes/safety.py`                       | `/api/v1/safety` - get/patch this org's own safety-guard overrides, plus live `used_today` from the org-keyed limiter                                                                                                                                                                                                                                | `router`                                                                                                      |
| `api/v1/routes/api_keys.py`                     | `/api/v1/api-keys` - list/create/revoke, org-scoped, owner/admin only                                                                                                                                                                                                                                                                                | `router`                                                                                                      |
| `api/v1/routes/integrations.py`                 | `/api/v1/integrations/providers/{provider}` - connect (upsert)/list/disconnect, owner/admin only                                                                                                                                                                                                                                                     | `router`                                                                                                      |
| `api/v1/routes/messages.py`                     | Internal team chat - `/api/v1/channels` + 7 sub-routes (unread-count, get/rename one channel, add/remove a member, mark read, list/send/edit/delete messages). `MESSAGES_READ`/`MESSAGES_SEND` only gate breadth (can this role use chat, can it post); per-conversation visibility is `channel_members` membership via RLS, and who may rename/remove-someone-else is the channel's creator or an org owner/admin, enforced in `channels_update`/`channel_members_delete` - neither is a role check in this file (see §5). `create_channel` catches `ValueError` from the repository and turns it into a 400, rather than letting a cross-org member id or a malformed DM 500                                                                                                  | `router`                                                                                                      |
| `api/v1/routes/telephony.py`                    | `/api/v1/voice-agents/{id}/connect-number` - POST starts or resumes a provisioning attempt, GET polls the newest one. Gated on `integrations:write`/`integrations:read`, not an agent permission: what it actually does is reconfigure the org's own Twilio/Plivo account with credentials from the Integrations page, and Part 2 owns `permissions.py`. Decrypts that org's stored credentials itself - an endpoint accepting credentials in its body would be a way to make CallFlow configure an account nobody proved they own. A part-way failure returns 202 with `status`/`last_error` rather than a 500 (`ISSUES.md` #112/#113) | `router`, `ConnectNumberIn`, `ProvisioningOut` |
| `integrations/openrouter/client.py`             | **The only OpenRouter caller.** Two unrelated jobs sharing a vendor: issuing one metered key per organisation from CallFlow's management key, and `get_conversational_llm()` - the thin, keyword-only function Part 2's extraction step uses to hold a turn without importing an LLM SDK. Usage is read from the provisioning API, not accumulated from stream chunks, because no final-usage chunk is guaranteed. Keys are disabled, never deleted - the usage record settles billing disputes | `OpenRouterProvisioning`, `get_conversational_llm()`, `ConversationalLLM`, `OpenRouterError` |
| `integrations/telephony/twilio.py`              | **The only Twilio REST caller** - `httpx`, not the SDK, for four POSTs. Creates the trunk, points origination at LiveKit, stores outbound credentials, attaches the number, in that order so a part-way failure leaves a stray trunk rather than a number ringing into nowhere. Twilio **cannot** authenticate inbound, so `allowed_addresses()` supplies the signalling CIDRs the LiveKit trunk must be restricted to | `TwilioCarrier`, `TWILIO_SIGNALLING_CIDRS` |
| `integrations/telephony/plivo.py`               | **The only Plivo REST caller.** Same shape as the Twilio adapter on purpose. Sends an explicit `;transport=tls` (Plivo rejects a URI without one) and returns the Termination SIP Domain LiveKit dials out through - which Twilio has no analog for, hence `CarrierTrunk.termination_domain` being optional rather than callers branching on the provider | `PlivoCarrier`, `DEFAULT_TRANSPORT` |
| `integrations/livekit/client.py`                | **The only LiveKit SDK import**, aliased on the way in. Owns inbound/outbound trunk creation, dispatch rules, and `CreateSIPParticipant`. `classify_error()` maps a `TwirpError` onto `DialFailure`, preferring the upstream SIP status (486 -> busy) over the transport code and failing closed to `INTERNAL` for anything unmapped. Async - the SDK is aiohttp-based, so call sites must NOT wrap it in `asyncio.to_thread` the way CALL-E's blocking client needed | `LiveKitGateway`, `classify_error()`, `EngineError`, `SipTransport` |
| `integrations/voice/protocol.py`                | The `VoiceProvider` protocol and its `VoiceCapability` set. **Nothing implements it** - CALL-E was removed and `livekit/client.py` deliberately does not conform to it yet, because a protocol shaped around one deleted vendor is not evidence of the right shape. Settle it once a second carrier proves the real one | `VoiceProvider`, `VoiceCapability`, `NotImplementedForProvider` |

**Per-contact pipeline** (`CampaignRunner.run_one`, in `services/campaign_runner.py`):

```
build base outcome (masked phone)
  → render_goal(campaign, contact)        {name} / {context[key]}, missing keys → ""
  → check_dial_allowed(is_suppressed=…)   fails closed → SKIPPED. Suppression is checked
                                           here too now - the caller resolves the org's
                                           real suppressions table once per run and passes
                                           the verdict in (domain/ does no I/O, by design)
  → LiveKitGateway.start_call()           one shared session per batch; wait_until_answered,
                                           so a busy/unreachable number is distinguishable
  → return IN_FLIGHT                      the call is answered, NOT finished
  ... the worker holds the conversation, then POSTs the transcript back (P1-T4)
  → _extract_result() / triage()          run against that callback, not here
```

**A run no longer ends when `run()` returns.** CALL-E was request/response and could be
polled to completion; LiveKit is not. Origination puts the caller and an agent worker into
a room and returns once the call is *answered*, so `run_one()` reports `IN_FLIGHT` and the
worker POSTs the transcript and terminal status back when the conversation actually ends.
Anything reading a run's outcomes must expect rows that resolve later rather than every row
being terminal immediately.

A campaign whose voice agent has no connected number is refused per contact with that
reason - `run_one()` takes its `trunk_id` from the caller, the same way the allowlist and
suppression set are resolved once per run and passed in.

The failure taxonomy that survives is `DialFailure`, and `integrations/livekit/client.py`'s
`classify_error()` is what will populate it: a `TwirpError`'s upstream SIP status is
preferred over its transport code (486 → `busy`, not `internal`), and anything unmapped
fails closed to `INTERNAL`, which is deliberately *not* retryable. Only `rate_limited`,
`provider_unavailable`, `timed_out`, `busy` and `no_answer` become `Disposition.RETRY`;
everything else becomes `Disposition.UNREACHABLE` (`ISSUES.md` #37).

Unlike CALL-E's blocking client, the LiveKit SDK is aiohttp-based and must be awaited
directly - the `asyncio.to_thread` wrapping every old call site is gone and must not come
back.

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

**`POST /api/v1/voice-agents/{voice_agent_id}/connect-number`** - requires
`Permission.INTEGRATIONS_WRITE`. Body: `provider` (`twilio` | `plivo`), `phone_number`,
`number_ref` (Twilio's Phone Number SID, or the number itself for Plivo), `label`, and a
client-chosen `idempotency_key`. Returns **202** with the attempt row - `id`,
`voice_agent_id`, `status`, `last_error`, `created_at`, `updated_at` - and never a trunk id,
since those are LiveKit's internal handles and an operator can do nothing with them.

Reusing an `idempotency_key` **resumes** that attempt rather than starting a second one, so
a double-clicked button cannot create a second LiveKit trunk pair. A part-way failure still
returns 202: `status` stays `provisioning` and `last_error` carries the carrier's own
wording, because the steps that succeeded created real objects at the vendors and the record
of them has to survive the response (`ISSUES.md` #112). 400 for an unsupported carrier or one
with no stored credentials; 404 for an agent this organisation cannot see.

**`GET /api/v1/voice-agents/{voice_agent_id}/connect-number`** - requires
`Permission.INTEGRATIONS_READ`. The newest attempt for that agent, same shape. 404 when no
number has ever been connected to it.

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
  "calling_available": false,
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

`calling_available` is currently hard-coded `false`: CALL-E has been removed and the
LiveKit origination path is not built yet, so no deployment can place a call regardless
of configuration. It replaces the old `api_key_configured` field, which named a vendor
key that no longer exists.
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
this organisation's own rows (`campaigns_repo.list_org_campaigns`). **Role-based UI
roadmap, Phase 1:** an operator's connection only ever gets back campaigns they created -
`campaigns_select`'s RLS policy (migration `202608092000`) narrows the row set itself, not
this handler; owner/admin/viewer still see every campaign in the org.

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
    "built_in": true,
    "created_by": null,
    "created_by_name": null,
    "created_by_avatar_url": null
  },
  {
    "id": "holiday-enquiry-follow-up",
    "...": "…",
    "built_in": false,
    "created_by": "2c7e1a4b-...",
    "created_by_name": "Aditi Rao",
    "created_by_avatar_url": "https://.../avatar.png"
  }
]
```

All three are `null` for the two built-in templates (no owner). `created_by_name`/
`created_by_avatar_url` are joined to `public.users` so an admin/owner/viewer's org-wide
list can attribute each row; `POST`/`PATCH`'s own response still has a real `created_by`
(the actor's own id) but leaves the two name/avatar fields `null`, since the actor already
knows it's their own edit and those two calls skip the join.

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

### `GET /api/v1/campaigns/directory`

Any org member - no special permission beyond being signed in. Role-based UI roadmap,
**Phase 4 (peer-to-peer sharing)**: name + owner only, org-wide, so an operator whose
`campaigns_select` RLS narrows them to their own rows (Phase 1) can still see *what
exists* to request without seeing its goal template, extraction fields, or any content.
Backed by the `SECURITY DEFINER` SQL function `public.list_campaign_directory()`
(migration `202608101100`), which bypasses that same RLS narrowing on purpose - the whole
point of a directory is showing rows the caller's own `SELECT` policy would otherwise hide.

```json
[
  { "id": "holiday-enquiry-follow-up", "name": "Holiday enquiry follow-up", "owner_user_id": "2c7e1a4b-...", "owner_name": "Aditi Rao" }
]
```

_Used by:_ the Campaigns page's "Team campaigns" directory panel (operators only) - filters
out rows the caller already owns, then offers "Request access" per remaining row.

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

Org-scoped list (`runs_repo.list_runs`). **Role-based UI roadmap, Phase 1:** same silo as
campaigns - an operator's connection only gets back runs they started (`runs_select`,
migration `202608092000`); owner/admin/viewer see every run in the org.

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
    "completed": 3,
    "started_by": "2c7e1a4b-...",
    "started_by_name": "Aditi Rao",
    "started_by_avatar_url": "https://.../avatar.png"
  }
]
```

Newest first (`started_at` descending). `outcomes` is stripped; `completed` here is a
`count(*)` of outcome rows whose `disposition <> 'in_flight'` - a raw row count, **not**
the same as `stats.completed` below. `started_by*` is joined to `public.users`, `null` if
the starting member has since been removed from the org (`ON DELETE SET NULL`).

### `GET /api/v1/runs/team-summary`

Requires `Permission.RUNS_READ_TEAM` (owner, admin, viewer - **not** operator: their own
runs are already covered by `runs:read`, and `runs_select` would otherwise just silently
narrow this query to their own row anyway). Call volume grouped by teammate. Superseded
as the dashboard's actual data source by the richer `GET /api/v1/organisations/me/team-
performance` below (added for the role-based UI roadmap's Phase 5) - kept as-is, unused
by the frontend, rather than removed, since nothing about it is wrong.

```json
[
  {
    "user_id": "2c7e1a4b-...",
    "name": "Aditi Rao",
    "avatar_url": "https://.../avatar.png",
    "total_runs": 12,
    "total_calls": 34
  }
]
```

Ordered by `total_calls` descending. `runs_repo.summarize_by_member` has no ownership
filter of its own - it leans entirely on RLS, which is why the permission check on the
route, not the query, is what actually keeps an operator from calling this at all.

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
  "started_by": "2c7e1a4b-...",
  "started_by_name": "Aditi Rao",
  "started_by_avatar_url": "https://.../avatar.png",
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
transitions rather than a row per change. It now returns the row's `id` (previously
write-only), which is what lets a real `escalations` row (below) reference a specific
call outcome.

### `GET /api/v1/escalations`

Requires `Permission.ESCALATIONS_READ` (every role). Real, persisted "needs a person"
items - `public.escalations`, one row per call outcome whose disposition is `escalated`
or `unreachable` (`domain/entities.NEEDS_A_PERSON_DISPOSITIONS`), inserted by
`runs.py`'s/`webhooks.py`'s outcome-resolution call sites, not a trigger. RLS narrows the
result to what the caller's role and assignments actually allow - the response shape is a
superset of an `Outcome` (contact, transcript, disposition, sentiment, ...) plus:

```json
{
  "id": "b7e2...",
  "escalation_status": "open",
  "assigned_to": null,
  "assigned_to_name": null,
  "assigned_by": null,
  "assigned_by_name": null,
  "resolved_by": null,
  "resolved_by_name": null,
  "resolved_at": null
}
```

### `GET /api/v1/escalations/directory`

Requires `Permission.SHARING_REQUEST` (operator, admin, owner - not viewer). Stricter than
the campaign directory above, deliberately: this one surfaces which customers are
currently frustrated org-wide (contact name + campaign + owner), not just a resource name.
Only **open** escalations - a resolved one has nothing left to request. Backed by
`public.list_escalation_directory()` (`SECURITY DEFINER`, migration `202608101100`).

```json
[
  { "id": "b7e2...", "contact_name": "Rohan Mehta", "campaign_name": "Holiday enquiry follow-up", "owner_user_id": "2c7e1a4b-...", "owner_name": "Aditi Rao" }
]
```

_Used by:_ the Escalations page's "Team escalations" directory panel - "Request to help"
per row not already assigned to the caller.

### `POST /api/v1/escalations/{id}/assign`

Requires `Permission.ESCALATIONS_ASSIGN` (owner, admin only). Body `{"user_id": "..."}`.
→ `204`, or `400` if that user isn't a member of this organisation, or `404` if RLS
doesn't let this caller touch that row at all (not just "not found" - the same response
either way, by design: it doesn't reveal which case it was).

### `POST /api/v1/escalations/{id}/resolve`

Requires `Permission.ESCALATIONS_RESOLVE` (every role except viewer). → `204`, or `404`
if the escalation doesn't exist, is already resolved, or RLS doesn't let this caller
touch it (an operator can only resolve their own run's escalations or ones assigned to
them - enforced by RLS, not just the permission check).

### `GET /api/v1/share-requests`

Any org member - RLS (`share_requests_select`, migration `202608101100`) does the actual
narrowing: rows this caller sent, rows directed at them to decide, or every row if
admin/owner. Own sent requests and requests to decide come back in one list; the frontend
splits them into "Requests you've sent" / "Waiting on you" by comparing `requested_by`/
`owner_user_id` against the caller's own id.

```json
{
  "id": "9f3c...", "resource_type": "campaign", "resource_id": "holiday-enquiry-follow-up",
  "resource_name": "Holiday enquiry follow-up", "status": "pending", "message": "Can I take this over while Aditi's on leave?",
  "created_at": "2026-08-10T09:00:00Z", "decided_at": null,
  "requested_by": "7b1e...", "requested_by_name": "Rohan Mehta",
  "owner_user_id": "2c7e1a4b-...", "owner_name": "Aditi Rao"
}
```

`resource_name` is `null` whenever this connection's own RLS can't resolve the underlying
resource - always true for a requester's own *sent, still-pending* row (their
`campaigns_select`/escalation RLS can't see a campaign they don't own yet), non-null once
they're viewing it as the owner deciding on it, or after approval flips ownership.

### `POST /api/v1/share-requests`

Requires `Permission.SHARING_REQUEST` (operator, admin, owner - not viewer). Body
`{"resource_type": "campaign" | "escalation", "resource_id": "...", "message": "..." }`
(`message` optional, ≤280 chars). The owner is resolved **server-side** via
`public.resolve_resource_owner()` - never trusted from the client, since the whole reason
this flow exists is that the requester's own RLS scope can't see the resource (or its
owner) to check this themselves.

→ `201` the created request · `400` unknown `resource_type`, non-UUID escalation
`resource_id`, or requesting a resource the caller already owns · `404` no such resource
in this organisation · `409` a pending request for this exact resource already exists
(`share_requests_one_pending_idx`, a partial unique index - resolved requests don't block
a fresh one).

### `POST /api/v1/share-requests/{id}/approve` · `POST /api/v1/share-requests/{id}/reject`

No extra permission beyond being signed in - deciding is gated by actually owning the
resource (`share_requests_update`'s RLS: `owner_user_id = self`), re-checked explicitly in
the handler for a clear 403 instead of a bare RLS no-op. → `204` no body.

**Approving** re-resolves the resource's *current* owner before granting (ownership can
drift between request and decision - ISSUES.md #86); if it moved, the request is
auto-rejected with "Ownership of this changed since the request was made" instead of
silently overriding whoever holds it now. Otherwise the pending→approved transition
(`WHERE status = 'pending'`, race-safe against a second concurrent decision) commits
**before** the grant, not after, so two concurrent approvals can't both perform the grant:

- **campaign**: clones it - a new id, `created_by = requester`, independent from that
  point on (edits after this never write back to the original). Goes through the
  `SECURITY DEFINER` function `clone_campaign_for_share()` (migration `202608101200`), not
  a plain insert - see `ISSUES.md` #85 for why a plain insert fails under RLS for any
  non-admin/owner approver.
- **escalation**: reassigns it (`assigned_to = requester`, via `escalations_repo.assign()`)
  - a hand-off, not a clone, since there's only one real underlying event. → `404` if the
  escalation was resolved or deleted in the meantime.

→ `400` if already decided · `403` not the owner · `404` unknown request · `409` decided
by someone else in the same instant, or ownership drifted (see above).

_Used by:_ the Organisation page's "Sharing" tab, live-synced via Supabase Realtime
(`share_requests` is in the `supabase_realtime` publication, migration `202608101130`).

### `GET /api/v1/organisations/me/team-performance`

Requires `Permission.RUNS_READ_TEAM` (owner, admin, viewer). One row per teammate:
calls, run-status breakdown, open escalations, and credits - the dashboard's "Team
performance" panel's one data source.

```json
[
  {
    "user_id": "2c7e1a4b-...",
    "name": "Aditi Rao",
    "avatar_url": "https://.../avatar.png",
    "total_runs": 12,
    "runs_active": 1,
    "runs_completed": 10,
    "runs_failed": 1,
    "total_calls": 34,
    "calls_closed": 20,
    "open_escalations": 2,
    "daily_allocation": 50,
    "credits_used_today": 7
  }
]
```

`credits_used_today` is a real, live SQL count against `call_outcomes`/`runs` scoped to
that teammate and today - correct across restarts and replicas, unlike the org-wide
`used_today` in `GET /api/v1/safety` (§7's own documented limitation - an in-process
sliding window). `daily_allocation` of `0` means nobody has set one for that teammate yet.

### `GET /api/v1/organisations/me/members/me/credits`

No permission beyond being signed in - RLS on `member_credit_allocations` already scopes
this to the caller's own row. `{"daily_allocation": 50, "used_today": 7}` - `used_today`
counts only *connected* calls (`upper(status) = 'COMPLETED'`), the same number
`check_dial_allowed()` enforces against, not merely attempted ones. Backs Settings →
Billing's "My credits" view for anyone without `billing:read`.

### `PATCH /api/v1/organisations/me/members/{user_id}/credits`

Requires `Permission.CREDITS_WRITE` (owner, admin). Body `{"daily_allocation": 50}`
(`>= 0`). → `204`, or `404` if that user isn't a member. **Enforced at dial time** as of
`ISSUES.md` iteration 30: `POST /api/v1/runs` resolves the caller's own ceiling once per
run and `domain/safety.py::check_dial_allowed()`'s `credits_remaining` param denies a
dial once it's exhausted - layered *on top of* the org-wide `daily_budget`, which still
applies regardless of any individual allocation. A teammate with no row at all
(`credits_repo.get_enforced_ceiling()` returns `None`) is not gated by this check -
only an admin/owner explicitly setting one (including to `0`) turns it on for them.

### `GET /api/v1/channels`

Requires `Permission.MESSAGES_READ` (every role, including viewer). RLS
(`channels_select`) narrows the result to channels/DMs the caller is actually a
*current* member of - `is_channel_member(id) and is_org_member(org_id)`, not
`is_channel_member(id)` alone, since migration `b3f7d2a891c5` - **or** any
channel in their org if they're an owner/admin (moderation - migration
`b3f7d2a891c5`; `messages_select` has no matching branch, so this never
extends to reading a channel's messages).
`unread_count` is a correlated subquery against the caller's own
`channel_members.last_read_at` - it excludes the caller's own sends and
resets to 0 after `POST .../read`.

```json
[
  {
    "id": "e1c2...",
    "kind": "channel",
    "name": "launch-team",
    "created_by": "2c7e...",
    "member_ids": ["2c7e...", "9a1f..."],
    "unread_count": 3,
    "created_at": "2026-08-10T09:00:00Z"
  }
]
```

### `POST /api/v1/channels`

Requires `Permission.MESSAGES_SEND` (operator and above). Body: `kind`
(`"channel"`/`"dm"`), `name` (required for `channel`, ignored for `dm` - `400`
if a channel has no name), `member_ids` (the other initial members; the caller
is seated automatically - for a `dm`, `member_ids` must be exactly one id,
and not the caller's own). Goes through the `SECURITY DEFINER`
`create_channel()` function (migration `b3f7d2a891c5`), not a two-step insert -
see `database/repositories/channels.py`'s row above for why. → `201`, same
shape as the list above. For a `dm`, idempotent (migration `b3f7d2a891c5`):
calling this twice for the same two people returns the *same* channel,
race-safe against two simultaneous calls (a partial unique index on
`channels(org_id, dm_pair)` is the actual guard, not just an
exists-check-then-insert). → `400`, not `500`, for anything `create_channel()`
itself rejects - a `dm` with the wrong member count, a self-DM, or a member id
from another organisation (`ISSUES.md` #98).

### `GET /api/v1/channels/unread-count`

Requires `Permission.MESSAGES_READ`. `{"unread_count": 3}` - the total across
every conversation the caller is in. Deliberately not derived from `GET
/channels` (which the nav badge would otherwise have to call on every
Realtime event, for every open tab in the organisation, paying for that
endpoint's per-channel member-list aggregation just to sum one field back
out) - `channels_repo.total_unread_count()` is a single join with no per-row
fan-out (`ISSUES.md` #99).

### `GET /api/v1/channels/{id}`

Requires `Permission.MESSAGES_READ`. A single channel, same shape as one item
of the list above. → `404` if the id doesn't exist *or* RLS hides it - the two
are indistinguishable on purpose, so a channel id from another organisation
typed directly into the URL bar (`/app/chat?c={id}`) never confirms whether it
exists at all.

### `PATCH /api/v1/channels/{id}`

Requires `Permission.MESSAGES_SEND`. Body: `{"name": "..."}` (1-80 chars). →
`400` for a DM (only named channels can be renamed). → `403` if the caller is
neither a *current-org-member* creator nor an org owner/admin - a former
creator who has since left the organisation no longer qualifies, since
migration `b3f7d2a891c5` added `is_org_member(org_id)` to the creator branch
- `channels_update`'s RLS
enforces this, not the route; the permission dependency only gates that the
caller can use chat at all. → `200`, same shape as the list above.

### `POST /api/v1/channels/{id}/members`

Requires `Permission.MESSAGES_SEND`. Body: `{"user_id": "..."}`. → `204`. →
`403` if the caller isn't a member of `{id}`, or if `user_id` isn't a member
of the caller's own organisation - `channel_members_insert`'s RLS, not a route
check (adding someone from a different org is rejected here the same way
`create_channel()`'s own `member_ids` already is).

### `DELETE /api/v1/channels/{id}/members/{user_id}`

Requires `Permission.MESSAGES_READ` (every role) - leaving a channel has to
work for a viewer too. → `204`. → `403` unless the caller is removing
themself, or is the channel's creator or an org owner/admin removing someone
else - `channel_members_delete`'s RLS.

### `POST /api/v1/channels/{id}/read`

Requires `Permission.MESSAGES_READ`. No body. Bumps the caller's own
`channel_members.last_read_at` to now - `channel_members_update`'s
`user_id = current_user_id()` check is what keeps this from ever touching
someone else's row. → `204`. Called by the frontend whenever a conversation is
opened, and again on any Realtime `messages` event while it's still open.

### `GET /api/v1/channels/{id}/messages`

Requires `Permission.MESSAGES_READ`. RLS (`messages_select`) returns nothing
for a channel the caller isn't a member of, regardless of role - there is
**no** admin/owner branch on this policy (deliberately unlike `channels_select`
above: admins/owners can moderate a channel's existence and membership, never
its contents). Oldest-first, soft-deleted rows excluded. Cursor pagination:
`?before=<ISO 8601 timestamp>&before_id=<uuid>&limit=<1-200, default 50>` -
`before`/`before_id` are the `created_at`/`id` of the oldest message already
loaded; the response is always oldest-first regardless of whether a cursor
was supplied, on `messages_channel_created_idx` (`channel_id, created_at`).
`before_id` is optional but should always be sent alongside `before` - it
breaks a tie when two messages share the exact same `created_at`
(transaction-start time, so genuinely concurrent sends can collide), which a
bare `created_at <` comparison would otherwise resolve by silently dropping
whichever tied message doesn't make the earlier page (`ISSUES.md` #100).

```json
[
  {
    "id": "9f3a...",
    "channel_id": "e1c2...",
    "sender_id": "2c7e...",
    "sender_name": "Aditi Rao",
    "body": "call went well",
    "created_at": "2026-08-10T09:05:00Z",
    "edited_at": null
  }
]
```

### `POST /api/v1/channels/{id}/messages`

Requires `Permission.MESSAGES_SEND`. Body: `{"body": "..."}` (1-4000 chars). →
`201`, same shape as one item above. → `403` if the caller isn't a member of
`{id}` - `messages_insert`'s RLS check failing, caught in the repository (a
nested `SAVEPOINT`, not a bare `try`/`except` - see `messages.py`'s row above)
so it surfaces as a clean denial rather than an aborted-transaction `500`.

### `PATCH /api/v1/channels/{id}/messages/{message_id}`

Requires `Permission.MESSAGES_SEND`. Body: `{"body": "..."}`. → `200`, same
shape as one item above, with `edited_at` now set. → `403` unless the caller
is the message's own sender - `messages_update`'s RLS. Builds its response
from the caller's own `CurrentUser.name` rather than the updated row (which
has no `sender_name` - its `UPDATE ... RETURNING` has no join to `users`,
unlike the list endpoint above - `ISSUES.md` #97).

### `DELETE /api/v1/channels/{id}/messages/{message_id}`

Requires `Permission.MESSAGES_SEND`. Soft delete (`messages.deleted_at`, never
a real `DELETE`) - the row stops appearing in `GET .../messages` immediately
after, on every connection, since that query already filters
`deleted_at is null`. → `204`. → `403` unless the caller is the sender.

**Realtime.** `channels`/`channel_members`/`messages` are all in the
`supabase_realtime` Postgres publication (added by the migration itself, since
the migration role already owns that publication on this project - no
`SUPABASE_SETUP.md` manual step needed). The frontend's `useOrgRealtime()`
hook (`lib/hooks/use-org-realtime.ts`) subscribes per table, per call site
(each gets its own `useId()`-suffixed channel name - two callers sharing one
name broke each other, `ISSUES.md` #96); its `org_id` filter is a bandwidth
optimisation only - RLS on `channels_select`/`messages_select` is what
actually gates which Postgres Changes events a given caller receives at all.
`chat-shell.tsx` and `use-chat-unread.ts` (the nav badge) each hold their own
independent subscriptions to the same tables. The hook debounces its own
callback (300ms, trailing) so a burst of events coalesces into one refetch,
and passes the changed row's payload through rather than firing a bare
trigger - `chat-shell.tsx`'s message and `channel_members` subscriptions use
that to skip a refetch of the open conversation when the event was actually
about a *different* one, instead of re-fetching (and, for messages,
re-marking-read) on every send anywhere in the organisation the caller
happens to belong to (`ISSUES.md` #99).

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
| `region`   | `str \| None`    | `None`   | Overrides the campaign's own region. No deployment-wide fallback remains - it was a CALL-E setting |
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
| `task_completed`     | `bool \| None`   | `None`      | CALL-E's own holistic judgment of whether the task reached a clear resolution - task-level only, never per-recipient (confirmed against the live OpenAPI spec). Independent of `extracted`; `triage()` escalates on an explicit `False`                                                                                                                             |
| `completion_confidence_score` | `float \| None` | `None` | 0-1, confidence in `task_completed`. `None` until CALL-E has a terminal judgment                                                                                                                                                                                                                                                                                     |
| `completion_confidence_label` | `str \| None` | `None` | `low`/`medium`/`high`                                                                                                                                                                                                                                                                                                                                                 |
| `evidence`           | `list[str]`      | `[]`        | Short evidence items supporting CALL-E's `task_completed` judgment                                                                                                                                                                                                                                                                                                    |
| `attempts`           | `list[AttemptSummary]` | `[]`  | Every dial CALL-E made for this recipient (a recipient can be redialled) - `status`/`started_at`/`completed_at`/`had_transcript` per attempt, not just the one `_final_attempt()` picks for the transcript above                                                                                                                                                    |
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
| 4   | `task_completed is False`                         | `ESCALATED` - CALL-E's own judgment the call never reached a clear resolution |
| 5   | `escalate_on_negative` **and** sentiment negative | `RETRY` - "a bad time is not a bad mood" |
| 6   | status in `busy`, `no_answer`, `voicemail`        | `RETRY`                                  |
| 7   | status in `failed`, `canceled`                    | `UNREACHABLE`                            |
| 8   | status is `completed`                             | `AUTO_CLOSED`                            |
| 9   | anything else                                     | `SKIPPED`                                |

One subtlety: the badly-named `escalate_on_negative` flag gates rule 4, which produces a
**retry, not an escalation** - and when it is `false`, negative sentiment falls through to
the status checks. (There is no longer a `"preview"` status branch - dry runs don't exist,
so every outcome reaching this function came from a real call.)

### Enums

`Disposition`: `in_flight`, `auto_closed`, `escalated`, `retry`, `unreachable`, `skipped`
`Sentiment`: `positive`, `neutral`, `negative`, `unknown`
Run `status`: `running`, `completed`, `failed`
`DialFailure`: `invalid_number`, `rate_limited`, `insufficient_balance`, `policy_violation`,
`unauthorized`, `provider_unavailable`, `timed_out`, `busy`, `no_answer`, `internal` -
vendor-neutral, and the only vocabulary retry policy keys off. `busy`/`no_answer` were added
when SIP became the transport: a carrier reports 486 and 480 distinctly, and folding either
into `provider_unavailable` would tell an operator CallFlow broke when the person was simply
on another call. Stored as plain text, so extending it needs no migration.
`ProvisioningStatus` (`domain/provisioning.py`): `pending`, `provisioning`, `verified`,
`failed` - one-way, no edge out of a terminal state

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
| Per-teammate daily credits  | unset (no per-teammate ceiling; org-wide budget is the only gate) | `member_credit_allocations.daily_allocation`, editable admin/owner via `PATCH .../members/{id}/credits`. **1 credit = 1 connected call** - a dial that never rings through doesn't spend one (`ISSUES.md` iteration 30) |
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
- **`(app)/app`** - dashboard (`/app`), `campaigns` + `new` + `[id]`, `runs` + `new` + `[id]`, `escalations`, `contacts`, `chat` + `[id]` (internal team chat - channels/DMs, §3/§5; `chat-shell.tsx` is the shared component both the list-only and per-conversation routes render, parameterised by `channelId`, so a conversation has a real, shareable/refreshable URL), `profile`, `organisation` + `new`, `settings` + 4 panes (`safety`, `api-keys`, `integrations`, `billing`). Organisation and Team are their own route, `/app/organisation` (`Suspense`-wrapped for `useSearchParams()`, `?tab=team`/`?tab=sharing` select the Team/Sharing panes - Phase 4 added the third tab) - not a dialog and not a Settings pane; `/app/settings` and `/app/settings/team` both redirect to `/app/settings/safety` so pre-existing generic "Settings" links still resolve; "Organisation" lives in the account menu (`user-menu.tsx`'s dropdown) and, as of the dark-theme-pivot foundation task, also as a direct link in the sidebar's footer section (`app-shell.tsx`'s `AppSidebar`, below the six-item primary nav list) - it and Settings are lower-frequency than those six, so neither joins `PRIMARY_NAV_ITEMS` itself (Chat does - unlike Organisation/Settings, it's a working feature someone checks often); the footer is a second path to the same three destinations (Profile/Organisation/Settings), not a replacement for the account menu, since the sidebar disappears below `lg` and the account menu is mobile's only way to reach them (or to sign out). Creating a second organisation is a dedicated two-step page, `/app/organisation/new` (name, then an optional logo - logo upload has to be a second step because Storage RLS scopes the upload path by `org_id`, which doesn't exist until the create call returns). There is no `/app/welcome` - the mandatory org-setup step + its skippable profile follow-up are **not routes at all**; `OnboardingGate` renders them as a modal over whatever page is active (see §3/§12), specifically to avoid the two-independent-`useSession()`-instances bug a page-per-step version had (`ISSUES.md`)
- **Generated** - `icon.svg`, `apple-icon`, `opengraph-image`, `manifest.webmanifest`, `not-found` (`error.tsx` is a boundary, not a routed page)

### Design layer - `app/globals.css`

Light mode, product-wide, with one in-progress exception: `/app/*` is mid-pivot to a dark-
glassmorphism surface (round-3 dashboard-polish, dark theme). Marketing and auth stay light-
only, no toggle. Semantic tokens (`--surface*`, `--text*`, `--rule*`), five lamp colours plus
`-text` variants for contrast, a fluid type scale, a 4-step shadow scale, and motion tokens.

A parallel `--dark-*` token set (background/glow, glass surface, text tiers, a cyan accent, and
muted `--dark-lamp-*`/`-text` variants reusing the same lamp semantics, never a second status-
colour system) is declared inside `.app-font-scope` - the same `/app/*`-only scoping trick that
rule already used for the Ubuntu font swap - so it resolves only under the dashboard and is
inert everywhere else. `.dark-canvas`/`.dark-panel-glass` are the dark equivalents of
`.canvas-tint`/`.panel-glass`. As of this task, the tokens exist and the sidebar footer consumes
plain light-scoped classes; no page has opted into the dark classes yet - see
`.superpowers/sdd/round3-dashboard-polish/dark-theme-D1-report.md` for the full palette, the
contrast method, and what's still unstyled (the sidebar/top-bar chrome itself).

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
| `app-store.tsx`                            | `AppStoreProvider` - hydrates up to 10 recent runs (derives `outcomes`); fetches real `escalations` from `GET /api/v1/escalations`, kept live via Realtime                            |
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
| `hooks/use-org-realtime.ts`                | Generic `useOrgRealtime(table, orgId, onChange)` - Supabase Realtime (`postgres_changes`, filtered by org) for any table in the `supabase_realtime` publication. `onChange` receives every payload a 300ms debounce window coalesced, not just the last one - it used to hand back only the most recent, silently dropping any event a filtering caller (chat's own `payloadChannelId` checks) wasn't watching for (`ISSUES.md` #105). Replaces the earlier escalations-only hook; also backs the Sharing tab's live updates on `public.share_requests`                |
| `hooks/use-permission.ts`                  | `usePermission(permission)` / `useRole()` - thin wrappers over `useSession()`, the one place pages read `profile.permissions`/`profile.active.role` instead of inlining the check    |
| `hooks/use-external-store.ts`              | `useSyncExternalStore` over `localStorage` and `matchMedia`                                                                                                                          |
| `hooks/use-org-scoped-effect.ts`           | `useEffect`, structurally forced to re-run when the active organisation changes - the standard pattern for org-scoped data fetching, used by 9 fetch sites                           |
| `hooks/use-org-realtime.ts`                | `useOrgRealtime(table, orgId, onChange)` - generic Supabase Postgres Changes subscription, org-filtered. Fires `onChange()` (a refetch) on any event RLS lets through; the `org_id` filter is bandwidth-only, not the security boundary. Each call site gets its own `useId()`-suffixed channel name - `supabase-js` dedupes `.channel(name)` by name, so two callers watching the same table with the old deterministic name silently broke each other (`ISSUES.md` #96) |
| `hooks/use-chat-unread.ts`                 | `useChatUnreadCount()` - total unread messages across every conversation, for the "Chat" nav badge. Its own small fetch + three `useOrgRealtime` subscriptions rather than reading `AppStoreProvider`, so a mistake here can't regress the dashboard/runs/escalations that store already powers |
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

**`app/` (16)** - dashboard. **`dry-run-switch.tsx` is deleted** - there is nothing left to
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
| `escalation-card.tsx`      | Worklist item with typed reasoning chain; real assign (teammate picker, admin/owner)/resolve against `GET/POST /api/v1/escalations/*`                                                                                                                                                                                                                            |
| `transcript-view.tsx`      | Conversation left, typed result + triage chain right                                                                                                                                                                                                                                                                                                              |
| `masked-phone.tsx`         | Masked by default; **no prop to disable masking**                                                                                                                                                                                                                                                                                                                 |
| `connection-banner.tsx`    | Silent unless the service genuinely doesn't respond - no cold-start sequence to play                                                                                                                                                                                                                                                                              |
| `settings-section.tsx`     | `SettingsSection` (with `effect` line) + `NotWiredNotice`                                                                                                                                                                                                                                                                                                         |
| `onboarding-gate.tsx`      | `OnboardingGate` - renders a non-dismissible modal (org name, then a skippable profile step) over any `/app/*` page while `active.onboarded_at` is `null`; a server signal, not `localStorage`. Owns one `useSession()` instance for both steps deliberately - a separate-page-per-step version had each step reading its own independent, stale session snapshot |
| `session-gate.tsx`         | `SessionGate` - renders once the session resolves signed-in; a skeleton while loading, a retry panel otherwise, so pages stop each collapsing that into a silent blank render                                                                                                                                                                                     |
| `overview-org-section.tsx` | `TeamControls` - the dashboard's team summary popover. Its "Manage" link goes to `/app/organisation?tab=team`, not a dialog                                                                                                                                                                                                                                       |
| `invite-dialog.tsx`        | Email + role "invite a teammate" dialog, shared by `/app/organisation`'s Team pane and the dashboard's team popover                                                                                                                                                                                                                                               |
| `welcome-modal.tsx`        | `WelcomeModal` - one-time dismissible dialog naming the org + role, shown after a freshly-accepted invitation. Reads/clears a `localStorage` flag (`PENDING_WELCOME_KEY`) written by `accept-invite/[token]` right before it redirects to `/app`; mounted once, as a sibling of `AppShell`                                                                     |
| `share-request-dialog.tsx` | `ShareRequestDialog` - Phase 4. Title/copy vary by `resourceType` ("Request access" for a campaign, "Request to help" for an escalation), optional 280-char message, `POST /api/v1/share-requests`. Reused by both directory panels below                                                                                                                       |

**`layout/` (11)**

| File                              | Role                                                                                                                                                                               |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `site-header.tsx`                 | Hover mega-menus with a single-open coordinator that re-reads `:hover` on close                                                                                                    |
| `site-footer.tsx`                 | 4 columns, legal row, capability band, BrBik credit                                                                                                                                |
| `site-loader.tsx`                 | First-paint brand loader; CSS fade + JS unmount at 1700ms so it can never trap the page                                                                                            |
| `view-transitions.tsx`            | Intercepts internal links, drives `document.startViewTransition`, resolves on real route change with a timeout backstop                                                            |
| `app-shell.tsx`                   | Left sidebar (`AppSidebar`: brand, `SidebarOrgSwitcher`, primary nav list, collapsible, `ProfileFooterLink` at the bottom) fixed-width at `lg`+, no header - `AppTopBar` is gone - and a bottom `AppTabBar` (with `UserMenu` as a 5th slot) below `lg`                            |
| `app-nav.tsx`                     | Nav constants (`NAV_ITEMS`/`PRIMARY_NAV_ITEMS`), `OrgMark`, and `AppTabBar` (the mobile tab bar) - the sidebar itself is `AppShell`'s `AppSidebar`, not defined here                                                         |
| `user-menu.tsx`                   | `UserMenu` - avatar dropdown: profile, settings, sign out. No org switcher here - that's `SidebarOrgSwitcher` in `app-shell.tsx`, so the action doesn't exist in two places at once |
| `docs-shell.tsx`                  | Three-pane docs; TOC read from rendered DOM headings                                                                                                                               |
| `auth-card.tsx` `auth-notice.tsx` | Auth card shell; the honest "not connected" notice                                                                                                                                 |

Root layout mounts `NuqsAdapter` → `TooltipProvider` → `ToastProvider`, plus `SiteLoader`
and `ViewTransitions` as siblings.

### Actions available per dashboard page

| Page                                               | Actions                                                                                                                                                                                    | Hits                                                                                            |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| `/app` (Dashboard)                                 | View volume/disposition/outcome-distribution summaries, a "Needs a person" preview, "Team performance" (admin/owner/viewer), open a recent run, navigate                                   | `GET /api/v1/runs`, `GET /api/v1/runs/{id}`, `GET /api/v1/organisations/me/team-performance`     |
| Org-setup modal (any `/app/*` page, not a route)   | Confirm the org's real name - the one mandatory, non-skippable step - then a skippable name + avatar step                                                                                  | `POST /api/v1/organisations/me/complete-onboarding`, `PATCH /api/v1/me`                         |
| `/app/campaigns`                                   | Filter all/template/custom, duplicate, delete, run. Operators additionally see a "Team campaigns" directory (name + owner only) with a "Request access" action per row                    | `GET`/`DELETE /api/v1/campaigns`, `GET .../directory`, `POST /api/v1/share-requests`             |
| `/app/campaigns/new`, `/[id]`                      | Edit name/goal/fields/region/language/window/retry, preview with a different contact (rendered locally, not via the API), save                                                             | `POST /api/v1/campaigns`                                                                        |
| `/app/runs`                                        | Sort, paginate, change page size, export CSV, open run                                                                                                                                     | `GET /api/v1/runs`                                                                              |
| `/app/runs/new`                                    | Paste/import/edit contacts, remove invalid, pick campaign, preview the goal (rendered locally), start - **no dry-run toggle; Start run always dials**                                      | `POST /api/v1/runs`                                                                             |
| `/app/runs/[id]`                                   | Watch lamps settle, pause updates (browser polling only), cancel the run for real (stops the next contact from being dialled, not one already in conversation), open transcript in a centered dialog. No "Guards for this run" display and no visible run id anywhere on the page as of it-17 (`ISSUES.md`) - the run id is still the URL segment and still round-trips through the API | `GET /api/v1/runs/{id}` every 2.5s, `POST /api/v1/runs/{id}/cancel`                                                              |
| `/app/escalations`                                 | Filter reason/campaign, sort oldest/newest, open transcript in a centered dialog, call back myself, reassign (admin/owner), mark resolved - live-synced across teammates. Renders 20 at a time behind an `IntersectionObserver` sentinel (client-side only - the full list is already in memory, there is no server-side pagination API for this view). Operators/admins/owners with `sharing:request` additionally see a "Team escalations" directory with a "Request to help" action per open row not already theirs | `GET /api/v1/escalations`, `POST .../assign`, `POST .../resolve`, `GET .../directory`, `POST /api/v1/share-requests` |
| `/app/contacts`                                    | Search, sort, paginate, export CSV (via the shared `DataTable`, same component `/app/runs` uses), suppress a number, remove suppression. Suppression list is real-API-backed (`GET`/`POST`/`DELETE /api/v1/suppressions*`), not `localStorage` - the previous note here was stale | `GET /api/v1/runs`, `GET`/`POST /api/v1/suppressions`, `DELETE /api/v1/suppressions/{id}`        |
| `/app/settings` (Organisation), `/team`, `/safety` | Rename/re-logo the org, invite/remove/re-role teammates, read the safety guards                                                                                                            | `PATCH /api/v1/organisations/me`, `.../members`, `.../invitations`, `GET /api/health`           |
| `/app/organisation?tab=sharing`                    | "Waiting on you" (approve/reject requests directed at you) and "Requests you've sent" (status only) - live-synced across teammates                                                        | `GET /api/v1/share-requests`, `POST .../{id}/approve`, `POST .../{id}/reject`                    |
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
| `CALLFLOW_MAX_CALLS_PER_RUN`                 | `3`     | Hard per-run ceiling                                                                                                                                                                                                                           |
| `CALLFLOW_MAX_CONCURRENT_CALLS`              | `5`     | How many contacts in one run may be dialling/polling at once (`CampaignRunner.run()`). CALL-E publishes no rate-limit numbers, so this starts conservative                                                                                     |
| `CALLFLOW_ALLOWLIST`                         | empty   | Comma-separated E.164. Non-empty ⇒ only these dialable                                                                                                                                                                                         |
| `CALLFLOW_CORS_ORIGINS`                      | empty   | Extra browser origins; bare hostnames get `https://`                                                                                                                                                                                           |
| `CALLFLOW_LOG_FORMAT`                        | `text`  | `text` (human-readable, local dev) or `json` (one object per line, for a log aggregator) - see `core/logging.py`                                                                                                                               |
| `LIVEKIT_URL`                                | `""`    | CallFlow's own LiveKit Cloud project (ap-south). Empty ⇒ `LiveKitGateway` refuses to construct |
| `LIVEKIT_API_KEY`                            | `""`    | As above |
| `LIVEKIT_API_SECRET`                         | `""`    | As above |
| `LIVEKIT_SIP_HOST`                           | `""`    | The project's SIP host, given to every carrier as the origination target. Empty ⇒ provisioning refuses rather than configuring a carrier to send calls nowhere |
| `LIVEKIT_AGENT_NAME`                         | `callflow-voice` | Must match on the API and the worker. A mismatch means dispatches name a worker that never answers, and callers hear silence |
| `OPENROUTER_MANAGEMENT_KEY`                  | `""`    | Mints one metered key per org. A platform secret, never a `provider_credentials` row |
| `OPENROUTER_DEFAULT_LIMIT_USD`               | `25`    | Spend ceiling on a newly issued org key. `0` is unlimited |
| `CALLFLOW_ANSWER_TIMEOUT_SECONDS`            | `120`   | Voice runtime only. How long the worker waits for the contact to appear in the room. It is dispatched *before* the number is dialled, so this covers dial setup plus a full ring, not just the moment of answering |
| `CALLFLOW_MAX_CALL_SECONDS`                  | `900`   | Voice runtime only. The worker's own backstop for a conversation that connects and never ends. A job's `max_call_duration_seconds` metadata overrides it, so both halves agree on one number |
| `CALLFLOW_INTERNAL_API_SECRET`               | `""`    | Shared secret on `/internal/v1/*`, the voice runtime's callback. Empty ⇒ every completion is refused and calls never resolve past IN_FLIGHT |
| `CALLFLOW_PUBLIC_API_URL`                    | `""`    | This API's own publicly-reachable base URL. Read by nothing today; kept for the voice runtime's transcript callback (`RUNBOOK_HET_PART_1.md` P1-T4)                                                                                                                 |
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

**Tests** - 264 collected across 17 files (verified via `pytest --collect-only -q`).
`pytest -q`, `ruff check app tests`. The per-file table below reflects the files this and
the preceding few iterations touched most directly; some untouched files' counts may lag.

| File                           | Tests | Covers                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------ | ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_internal_completion.py`  | 17    | The worker callback against the real database: no key / wrong key / unset secret all refused (fails closed), an unknown run is the same 404 as a bad key, a completion resolves the in-flight row rather than adding a second, the result is triaged rather than stored raw, a non-terminal status is rejected, replaying is idempotent, and the run closes only when the *last* contact settles - with exactly one callback reporting it. Then the four this file grew after review: a call whose triage asks for a person raises an escalation and a clean one does not (the only place a real conversation can, `ISSUES.md` #111), a settled row is not dragged back to in-flight by a late origination write and still returns its id (#116), and a call whose worker died stops holding the run open while one still inside its ceiling is left alone (#117). Skipped when `DATABASE_URL` is unset |
| `voice-runtime/test_pipeline.py` | 12  | Which plugin a voice agent's stored providers resolve to, with the registries substituted - so it needs neither a LiveKit room nor any vendor package installed. Covers a second STT and TTS vendor swapping cleanly (P1-T11), mixing vendors across the pipeline, unknown/unset providers refusing rather than falling back to a default, per-provider credentials, and a check that `build_pipeline` names no vendor itself |
| `voice-runtime/test_worker.py` | 20    | The worker's decisions: unusable job metadata yields an empty mapping rather than killing a live call, the transcript reads as a conversation with non-conversational turns dropped, and the completion payload - a connected call with no turns is NO_ANSWER not COMPLETED, a crash still sends its partial transcript, and extraction is left empty rather than guessed. Plus how long a call is *held* (`ISSUES.md` #110), against a fake room: held until the contact hangs up, nobody joining is an unanswered call rather than an error, a call that ends before the handlers are armed still returns instead of waiting out the ceiling, a room that never reports is cut off at it, and a room-level disconnect ends the wait too |
| `voice-runtime/test_reporter.py` | 8   | Delivering the result: the secret is sent, transient failures retry, a 4xx does **not** retry (it will never succeed and would burn the budget a real outage needs), retries are bounded, and giving up says the conversation happened but was not recorded |
| `test_number_provisioning.py`  | 14    | The workflow against the real database with stub vendors. The one that matters: after a carrier failure, a retry with the same key creates **only** the outbound trunk - it does not make a second inbound one. Also that a part-way failure stays resumable rather than terminal, that the derived SIP credentials are identical across a resume (regenerating would leave LiveKit dialling a password the carrier no longer expects), that a superseded attempt refuses, that a verified replay is a no-op, and that an unknown carrier is refused before anything is created. A carrier failure must **not** propagate out of the workflow - raising would roll back the ledger the successful steps wrote and the retry would orphan a second trunk pair (`ISSUES.md` #112) |
| `test_openrouter.py`           | 15    | Provisioning and the conversational LLM against stubbed HTTP. The one that matters most: a create response carrying no key is treated as a **failed** issue, because OpenRouter returns the secret once and accepting it would leave an org with a hash it can meter but never authenticate with. Also no-limit vs zero-limit, exhausted keys reporting no remaining budget rather than a negative one, disable-not-delete, streaming token by token, the system prompt leading the history, and a malformed SSE chunk being skipped rather than ending a live call |
| `test_telephony_carriers.py`   | 17    | Both carrier adapters against stubbed HTTP - no account needed, since what is under test is the shaping, not the network. Call ordering (the number attached last), the transport parameter on the origination URI, outbound credential creation, the vendor's own error message surfacing into `last_error`, an unreachable carrier reported as such rather than raising a transport error, Twilio's IP allowlist being non-empty and Plivo's deliberately empty, and a check that both adapters still expose the same entry points |
| `test_livekit_client.py`       | 40    | The LiveKit boundary against a stub client - no account needed, and none should be: these assert the translation, not the network. Request shaping (numbers, allowed addresses, explicit SIP transport, individual dispatch rule, `wait_until_answered`), the aiohttp session closed on both the happy and raising paths, and the full error mapping including SIP-status-beats-transport-code, unmapped-fails-closed, junk metadata, and a check that every `DialFailure` member is reachable from some vendor error. Also that a failed dial cancels the agent dispatch it created, that a cleanup failure never replaces the dial's own classified error, and that nothing is cancelled when no agent was dispatched (`ISSUES.md` #115) |
| `test_dispatch_contract.py`    | 6     | The agent-dispatch metadata, built by the real `_originate()` and read by the worker's **real** `AgentSpec.from_metadata()`, loaded by path because both deployables name their package `app`. This is the test that would have caught `ISSUES.md` #109: every provider resolves, the model/voice/keys survive the trip, a missing `voice_agent` resolves to nothing (which is why the runner refuses to dial without one), the completion callback can address the row the dial created, an uploaded CSV column cannot overwrite the goal or the masked number (#114), and no phone number reaches the metadata at all |
| `test_telephony_routes.py`     | 10    | The connect-a-number endpoints against the real database with stub vendors: an attempt is recorded verified, the org's own stored credentials are what reach the carrier (decrypted server-side, never accepted in the body), **another tenant's agent is a 404**, replaying the same key does not create a second trunk, a carrier failure comes back as a readable 202 attempt rather than a 500, an unsupported carrier and a carrier with no stored credentials each say what to do, the status poll reports the newest attempt, and no LiveKit trunk id reaches the response. Skipped when `DATABASE_URL` is unset |
| `test_provisioning_state.py`   | 23    | The provisioning state machine, exhaustive over the whole 4x4 status grid - every declared move allowed, every other rejected, terminal states final, and the error message naming the legal alternatives. Pure, so this runs in CI |
| `test_telephony_provisioning_repo.py` | 12 | The repository against a real database: a replayed idempotency key returns the original attempt rather than a second row and carries back its recorded trunk ids, a new key starts a fresh attempt without disturbing the failed one's `last_error`, per-step writes don't blank earlier steps, an illegal transition raises instead of writing, another org's attempt is invisible to `set_status`, and `latest_for_agent` is stable across repeated polls. Skipped when `DATABASE_URL` is unset |
| `test_messages_routes.py`      | 3     | `edit_message`'s route, not its repository or RLS - pins `ISSUES.md` #97 (the route called `_message_json()`, written for `list_messages()`'s joined rows, on `edit_message()`'s un-joined `UPDATE ... RETURNING`, `KeyError`-ing on every real edit; no repo-level or RLS test touches the route at all, which is why nothing else caught it). **Deep-audit round:** `create_channel`'s route turns a repository `ValueError` into a clean `400`, not a `500`; `get_unread_count` returns the repository's value unmodified - `ISSUES.md` #98/#99 |
| `test_rls_isolation.py`        | 100   | Cross-tenant isolation against the real database - signup trigger, org/user/membership/suppression invisibility, forged-org-id insert rejected, anon sees nothing, `postgres` bypass, account-deletion cascade + slug reuse, API-key resolution (matches owning tenant, revoked, live-membership), provider credentials (invisible cross-tenant, owner/admin-only write). **Cross-role:** the admin-to-owner grant guard - granted-role and target-role checks on `memberships_update`/`_insert`/`_delete` and `invitations_insert`, the invitee-cannot-mutate-their-own-invitation-role and invitation-cannot-seat-someone-else guards, and real (non-mocked) invitation creation/refresh through `org_repo.create_invitation()` proving the `SECURITY DEFINER` upsert fix actually works end to end (15 tests) - `ISSUES.md` #43/#44. **Same-org, cross-member:** two operators in one org - neither sees the other's campaign, run, or call outcome; admin and viewer see both; `summarize_by_member()` reflects the caller's own RLS scope, not just whoever's logged in (4 tests) - `ISSUES.md` #64. **First-time acceptance:** a genuine brand-new signup (real `auth.users` insert, real trigger, their own auto-created org) accepting a real invitation end to end, and an expired invitation correctly rejected (2 tests) - the previously-nonexistent coverage that would have caught `ISSUES.md` #68. **Remove-and-reassign, new this phase:** an admin removing a teammate reassigns their in-org data and deletes their account while leaving their unrelated other-org data untouched, and a same-rank operator cannot call the removal function directly (2 tests). **Team chat, new this phase (8 tests):** cross-tenant channel/message invisibility; `create_channel()` seats the creator atomically and rejects a `member_ids` entry outside the organisation with no orphaned `channels` row; a same-org non-member sees a channel in neither the list nor its messages; an admin sees `channel_members` for a channel they aren't in but not its `messages` (no admin/owner branch on that policy, deliberately); `channel_members_insert` rejects a non-member adding anyone, allows an existing member to add another org member, and rejects seating a user id from a different organisation entirely - the cross-tenant seating hole `is_user_org_member()` closes (migration `b3f7d2a891c5`). **Also new this phase:** a caller whose email doesn't match a pending invitation's target still gets a clean `None` from `invitations_repo.accept()` on a *second* call in the same transaction, not `InFailedSqlTransactionError` - pins the `SAVEPOINT` fix for `ISSUES.md` #78 (checked directly against the pre-fix code, which fails this test); and a real, non-mocked `messages_repo.send_message()` call actually succeeds and persists the right `org_id` - pins the fix for `ISSUES.md` #79 (also checked directly against the pre-fix code). **Teams-parity round (11 tests):** member search never crosses organisations; `add_member()`/`get_channel()`/`list_messages()`/`send_message()` all reject a different organisation through the real repository functions, not just raw SQL; a full rename/remove authorisation matrix (creator yes, org admin/owner yes even for a channel they never joined, a plain member no) against both `channels_update` and `channel_members_delete`; `channels_update` cannot be used to move a channel to another org (column-level grant, not just the policy); only a message's sender can edit or soft-delete it; unread counts exclude the reader's own sends and reset on `mark_read()`; cursor pagination returns oldest-first pages with no gap or overlap - `ISSUES.md` #94/#95. **Deep-audit round (8 tests):** `create_channel()` is idempotent for a `dm` through the repository itself, not just the raw SQL function, and two genuinely concurrent calls (two physical connections, `asyncio.gather`) converge on one channel rather than each merely not erroring; a `dm` with the wrong member count or aimed at the caller's own id is rejected with no orphaned channel; a member id from another organisation now raises `ValueError` through the repository (not a raw `asyncpg` error); the `channels(org_id, dm_pair)` partial unique index rejects a duplicate as a direct insert too, proving it's a real constraint and not just application logic; `total_unread_count()` matches the sum of `list_my_channels()`'s per-row counts and is scoped to the caller's own organisation even if the wrong `org_id` is passed in (RLS, not the parameter, is the actual boundary); and forcing three messages onto one identical `created_at` proves `before_id` stops `list_messages()` from skipping or repeating one - `ISSUES.md` #98/#99/#100. **Org-departure round (4 tests):** an active member's full read/send/rename access is unaffected by the tightened policies; a departed member - identical identity, `channel_members` row deliberately left stale - loses `channels_select`/`messages_select`/`messages_insert`; a departed creator can no longer rename their old channel or remove another member from it via the creator branch; `org_repo.remove_member()` actually clears the stale `channel_members` rows it leaves behind - `ISSUES.md` #101. **Follow-up (1 test):** a departed member - identical identity, stale row left in place - can no longer read `channel_members` either, closing the one policy the previous round's own migration deliberately deferred - `ISSUES.md` #102. **Platform pivot, new this phase:** `voice_agents` and `telephony_provisioning` invisible cross-tenant, forged-org-id insert rejected on both, another tenant's agent not updatable, a provisioning row not deletable by anyone (the missing delete *grant*, which a future policy edit cannot undo), the same idempotency key rejected as a second attempt while a different key is allowed, a credential in use by an agent not deletable (ON DELETE RESTRICT), and the widened `provider_credentials` check accepting `openrouter` while still rejecting blank (10 tests). Skipped when `DATABASE_URL` is unset - see `tests/local_postgres/README.md` to run them |
| `test_safety.py`               | 22    | E.164, masking, gate decisions                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `test_orchestrator.py`         | 18    | Goal rendering, the async dial pipeline, ceiling + suppression gating, extraction shapes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `test_organisations_routes.py` | 18    | The admin-to-owner grant guard's API layer, called through the real route handlers directly - `ISSUES.md` #43                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `test_permissions.py`          | 20    | `can_grant_role()`/`can_act_on_member()` - pure, no database - `ISSUES.md` #43. Plus `role_has()` pins for `Permission.RUNS_READ_TEAM` (owner/admin/viewer yes, operator no)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `test_triage.py`               | 14    | Precedence rules - the most thoroughly tested module                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `test_ratelimit.py`            | 12    | Windows, budget, owner bypass, reserve/release                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `test_config.py`               | 5     | Env parsing and defaults                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `test_crypto.py`               | 4     | Round-trips, nonce uniqueness, missing-key and tampered-ciphertext both fail closed. Pure - no database                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `test_campaigns.py`            | 1     | `slugify()` only - org-owned campaign CRUD needs a live Postgres connection, so it isn't covered by this local suite                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |

`test_samples.py` and `app/domain/samples.py` are both gone - there is nothing left to
sample once every run dials for real. `run_store.py` is gone with them.

**No frontend tests exist.**

**CI** - `.github/workflows/ci-cd.yml`, on PR and push to `main` **and `dev`**. Five
jobs; the last three run on push only, in order, one per thing that can independently
go wrong - the machine, the schema, the code:

1. `api` - Python 3.11, `pip install -e ".[dev]"` in `apps/api`, ruff, **a single
   migration-head check**, pytest. `alembic heads` reads `alembic/versions` without
   executing `env.py` or opening a connection, so it catches the two-branches-two-heads
   merge - which would otherwise fail at deploy time against a real database - for free
2. `web` - Node 20, `npm ci`, lint, type-check, build in `apps/web`
3. `provision` - SSH: clone if absent, `checkout -B` the deployed branch, then
   `scripts/bootstrap.sh` (venv, `pip install -e ./apps/api`, `.env` and `apps/web/.env.local`
   from their secrets, nginx site, certbot, pm2 systemd unit). Idempotent
4. `migrate` - SSH: `alembic current` → `upgrade head` → `current`, run **from
   `apps/api`**; `alembic.ini` resolves `script_location` and `prepend_sys_path`
   against the CWD, so `-c` from the repo root finds no migrations and silently
   upgrades nothing
5. `deploy` - SSH: `pm2 startOrRestart` the API → `npm ci && npm run build` →
   `pm2 startOrRestart` the web app → `pm2 save`, then curls `/api/health` and `/`

Every deployment job resolves `environment: ${{ github.ref_name }}`, so `APP_DIR`,
`PUBLIC_URL`, `VM_HOST`, `VM_USER`, `VM_SSH_KEY`, `ENV_FILE_B64` and `WEB_ENV_FILE_B64` come from the
GitHub Environment of that name and no job holds an environment literal. `provision`
fails before connecting if `APP_DIR` or `PUBLIC_URL` is unset.

`cancel-in-progress` is scoped to pull requests. A push is never cancelled: killing a
run mid-`migrate` can leave the schema between two revisions.

**Deployment** - `main` → `/var/www/callflow-ai` at `callflow-ai.brbik.com`, `dev` →
`/var/www/callflow-ai-dev` at `dev.callflow-ai.brbik.com`, each with its own `.env`,
its own Supabase project, and its own pm2 pair. Process names and ports come from
`ecosystem.config.js` keyed on `CALLFLOW_ENV`: `callflow-api`/`callflow-web` on
8000/3000, `callflow-api-dev`/`callflow-web-dev` on 8001/3001; `scripts/bootstrap.sh`
reads the ports from that same file to render nginx, so the proxy cannot drift from
what pm2 binds. The API runs one worker deliberately - the rate limiter is a
per-process dict. The VM is provisioned by the pipeline, not by hand; the only manual
steps left are creating the Supabase project and giving the VM read access to this
repo. Full bring-up in `DEPLOYMENT.md`.

> `render.yaml` was deleted in the monorepo restructure. It described a two-service
> Render deploy with `healthCheckPath: /`, which was never how this shipped.

**Local pre-commit hook** (`.githooks/pre-commit`, opt-in) resolves ruff/pytest from
`.venv` first, falls back to PATH, and skips with a warning rather than blocking if
neither is present.

---

## 12. `FEATURES.md` gap map

| F       | Feature                                                 | Status     | Note                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ------- | ------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1      | Repo, envs, config                                      | ⚠️ Partial | Flat repo not monorepo; no `uv`/`pnpm`/mypy/Docker; config is a dataclass not `pydantic-settings`, and does not refuse to boot on a missing var                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| F2      | Database schema                                         | ⚠️ Partial | Core relational schema is real: `users`, `organisations`, `memberships`, `suppressions`, `campaigns`, `runs`, `call_outcomes`, `api_keys`, `provider_credentials`, `org_safety_settings`, `voice_agents`, `telephony_provisioning`, all RLS'd. No credit ledger, billing, or audit-log tables yet                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| F3      | Authentication                                          | ✅         | Real Supabase Auth: signup/signin/signout, password reset, JWT verification (JWKS, 30s clock-skew leeway), plus a second path - org-scoped API keys (`cfk_…`) resolved through a SECURITY DEFINER function for programmatic access. This row was stale (marked "UI stubs only") for several iterations after auth actually shipped - fixed here                                                                                                                                                                                                                                                                                                                                                                                                          |
| F4      | Organisations, membership                               | ✅         | Real, RLS-scoped Postgres: create/rename/delete an organisation, membership + roles, team invitations by email, and a mandatory server-verified onboarding gate (`organisations.onboarded_at`) that confirms the org's real name before the dashboard is reachable (`OnboardingGate`, `POST /api/v1/organisations/me/complete-onboarding`)                                                                                                                                                                                                                                                                                                                                                                                                               |
| F5      | Authorisation, RLS                                      | ✅         | RLS enabled and forced on every tenant-scoped table, `app/auth/permissions.py`'s one role→permission matrix, `RequirePermission` FastAPI dependency, 39 cross-tenant/cross-role isolation tests hitting the real database. Also stale as "❌" until this pass. Role-hierarchy grant guard (`can_grant_role()`/`can_act_on_member()`, API + RLS) closed a real admin-to-owner privilege-escalation hole, including a column-privilege gap on `invitations.role` and a missing target-role check that would have let an Admin still act on an existing Owner's row. The column-privilege fix itself regressed invitation creation entirely (fixed via a `SECURITY DEFINER` upsert function, `public.create_or_refresh_invitation()`) - `ISSUES.md` #43/#44. **Role-based UI roadmap, Phase 1** added a second isolation dimension - same-org, cross-member: `campaigns_select`/`runs_select`/`call_outcomes_select` (migration `202608092000`) narrow an operator's visibility to rows they created (or, for call outcomes, runs they started); owner/admin/viewer are unaffected. Caught and fixed a real bug in the process (`ISSUES.md` #64): `campaigns_write`'s `for all` policy was silently re-granting every operator full org-wide campaign visibility, since Postgres ORs permissive policies for the same command and that policy's role-only check had no ownership condition - `runs`/`call_outcomes` never had this problem because their write policies were already split per command. A follow-up Supabase-security-checklist pass (`ISSUES.md` #66) found `public.create_or_refresh_invitation()` trusted a caller-supplied `target_invited_by` argument instead of deriving it from `current_user_id()` - a real gap given it's a `SECURITY DEFINER` function in the exposed `public` schema with `EXECUTE` granted to `anon`/`authenticated` (Supabase's Data API exposes every public function as an RPC endpoint by default), even though the one real call site never exploited it. Migration `202608092300` dropped the parameter; the function now derives it itself, matching `create_organisation()`'s existing pattern. The rest of the audit came back clean: every UPDATE policy has a `WITH CHECK`, RLS is forced on every tenant table, no deprecated `auth.role()` usage, no unprotected views. **Critical fix, found by real-world testing (`ISSUES.md` #68):** no one could ever actually accept their first invitation - `invitations_repo.accept()`'s lookup joined `public.organisations`, whose `organisations_select` policy is plain `is_org_member(id)`; a brand-new invitee fails that by definition, so the join silently dropped the row and every real first-time acceptance returned the generic "invitation isn't valid" message. Fixed with the same narrowly-scoped `SECURITY DEFINER` pattern as `#66` (`public.lookup_invitation_for_accept()`, migrations `202608092400`/`202608092500`) - exposes nothing the already-anonymous `lookup_invitation()` preview doesn't; the membership `INSERT` itself is untouched, so `has_valid_invitation()` still independently guards it. Also now checks `expires_at` at accept time, which it never did before. This had no test coverage of any kind before this fix - two new tests exercise a genuine brand-new signup accepting a real invitation end to end. **Removing a teammate** (product decision, not a bug) now goes through `public.remove_member_and_reassign_data()` - same `SECURITY DEFINER` shape, same reasoning (deleting `auth.users` needs privileges `authenticated` never holds) - reassigning their in-org `created_by`/`started_by` to whoever removed them before deleting their account entirely, everywhere, not just this org |
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
| F17     | Voice provider abstraction                              | ❌ Superseded | The single CALL-E wrapper this described has been **deleted** (`RUNBOOK_HET_PART_1.md` P1-T1). `integrations/voice/protocol.py` survives with no implementation behind it. The BYO-telephony stack that replaces it - LiveKit as the media/SIP substrate, the org's own Twilio/Plivo as carrier - is Phase A1 work (P1-T4 … P1-T6). Org-owned Twilio/Plivo credential storage (Settings → Integrations, encrypted at rest) is the one piece already built                                                                                                                                                                                                                                                                                                                                                                                                             |
| F18     | Runs and orchestration                                  | ⚠️ Partial | **Runs and outcomes are now Postgres-backed**, updated as each call resolves. Still sequential and single-process within a run; no state machine beyond running/completed/failed, no pause/stop/cancel endpoint, no calling-window enforcement, no crash recovery if the process dies mid-run                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| F19     | Safety gate                                             | ⚠️ Partial | 6 of 9 guards (suppression now included; dry run no longer exists as a concept to count). Missing calling-window enforcement, credit-balance check, consent flag                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| F20     | Call execution                                          | ❌ Not built | **No call can be placed.** CALL-E's dial/poll loop and its webhook receiver are both deleted; `CampaignRunner.run_one()` returns an explicit `provider_unavailable` failure for every contact that clears the safety gate. LiveKit `CreateSIPParticipant` origination lands in P1-T6. No billable flag or provider cost recorded either way                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| F21     | Typed extraction                                        | ✅         | Native `result_schema`, no transcript scraping. Not validated against the schema on return                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| F22     | Triage engine                                           | ✅         | Pure, precedence-ordered, 14 tests. No custom org rules                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| F23     | Escalation queue                                        | ⚠️ Partial | Full worklist UI backed by a real, persisted `escalations` table - assign (admin/owner) and resolve both survive a reload, Realtime-pushed to every teammate. Peer-to-peer "request to help" (role-based UI roadmap Phase 4) layers on top. Still no SLA/ageing alerts                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| F24     | Retry orchestration                                     | ❌         | `RETRY` disposition is produced but nothing acts on it                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| F25     | Transcripts, recordings                                 | ❌         | Transcript held in memory on the outcome; no R2                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| F26     | Analytics                                               | ⚠️ Partial | Dashboard stats computed client-side; no rollups or campaign comparison                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| F27     | Realtime                                                | ⚠️ Partial | Runs/dashboard still 2.5s/4s polling. Escalations and share requests are the exception: Supabase Realtime (`postgres_changes`, `lib/hooks/use-org-realtime.ts` - now generic, any table in the `supabase_realtime` publication) - an assignment, resolution, or share decision reaches every signed-in teammate live                                                                                                                                                                                                                                                                                                                                                                                                                          |
| F28–F31 | Inbound, scheduling, WhatsApp, CRM                      | ❌         | WhatsApp env vars read but unused                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| F32     | Outbound webhooks                                       | ❌         | UI + docs describe them; no implementation                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| F33     | Public API, keys                                        | ⚠️ Partial | **API keys are now real** - `GET/POST /api/v1/api-keys`, `DELETE .../{id}`; only a SHA-256 hash is stored, and the key actually authenticates (`current_user()`'s `cfk_…` path). No published API docs beyond this reference, no per-key rate limits or scopes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| F34     | Exports                                                 | ⚠️ Partial | Client-side CSV from the visible table                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| F35–F41 | Plans, credits, payments, invoicing, dunning, referrals | ⚠️ Partial | `organisations.plan_id` (real, default `'free'`) and today's real usage are now surfaced honestly at Settings → Billing, ending in a `NotWiredNotice` about no payment processor. Per-teammate daily credits are real and **enforced** at dial time (§7, `ISSUES.md` iteration 30), not just displayed. `lib/pricing.ts` itself is still presentation only, all prices `null`. No credit ledger, payments, invoicing, dunning, or referrals                                                                                                                                                                                                                                                                                                                                                                                                                                    |
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

## 13b. Voice-agent and telephony schema (platform pivot)

Added by `202608151200_voice_agents_and_telephony_provisioning.py`
(`PLATFORM_PIVOT_PLAN.md` ADR-4). `telephony_provisioning` is read and written by
`services/number_provisioning.py` through `routes/telephony.py`; `voice_agents` is
only read (a visibility check, and Part 2 owns its CRUD), so nothing in the product
creates one yet.

### `voice_agents`

What a live conversation runs with. 18 columns: `id`, `org_id`, `name`,
`kind` (`custom` | `prebuilt`), the three provider/credential pairs
(`stt_*`, `tts_*`, `llm_*`), `llm_model`, `telephony_provider` +
`telephony_credential_id`, `prebuilt_persona`, `system_prompt`, `voice_id`,
`created_at`, `created_by`.

One number per agent for V1: an org with several agents connects a number per
agent rather than sharing a pool. Every provider/credential column is nullable
because an agent is built up incrementally in the Agentic tab - the check that
one is *complete enough to dial* belongs at run start, not in the schema.

The four credential foreign keys are `ON DELETE RESTRICT`, not `CASCADE`:
deleting a credential a live agent authenticates with fails loudly rather than
silently leaving an agent that cannot connect.

RLS: select for any org member; insert/update for owner/admin/operator; delete
for owner/admin only. Choosing which credentials a call authenticates with is
not a viewer's decision.

### `telephony_provisioning`

One row per *attempt* to connect a number, not per agent, so a failed attempt
keeps its `last_error` when a fresh one starts. Status machine:
`pending → provisioning → verified | failed`.

`unique (voice_agent_id, idempotency_key)` is the schema half of the guarantee
that a retry cannot orphan a second LiveKit trunk: a double-submitted request
cannot become two rows, which forces the retry path to look up what the first
attempt already created (`livekit_inbound_trunk_id` and friends) instead of
blindly re-running the step. "Try again" from the UI starts a **new** row with a
new key rather than retrying the stuck one in place.

Rows are re-statused, never deleted - there is **no delete policy and no delete
grant**, so the trail of what was tried survives. `updated_at` is maintained by a
`touch_updated_at()` trigger, matching every other table carrying that column.

### `provider_credentials`, widened

The `check (provider in ('twilio','plivo'))` constraint is replaced by
`check (provider <> '')`, and `provider` widens from `varchar(16)` to `text`.
`voice_agents` references this table for STT/TTS/LLM credentials, and those
vendors (sarvam, openrouter, deepgram, elevenlabs, …) were not in the old list.
The accepted set now lives in the Pydantic layer, so adding a vendor is an app
change rather than a migration - which a 16-character ceiling would have undone.

## 14. The rule that shapes the schema

Application code must never reference `auth.users.id`. Every table points at
`public.users.id`, which carries an `auth_user_id` column mapping to the provider -
so changing auth providers later is repopulating one column, not a rewrite. (This
section used to be "Immediate next step - auth," a plan for work that has since
fully shipped across several iterations - see `ISSUES.md` iterations 2 and 3. Only
the one fact worth keeping from it is retained here.)
