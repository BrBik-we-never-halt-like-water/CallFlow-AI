# Organisations, invites, profile — and cleaning up two dev-experience papercuts

## Context

Four asks came in together:

1. **The dashboard shows a fake "waking the service…" cold-start sequence** on every
   sign-in. That UX (`use-connection.ts`, `connection-banner.tsx`, `/api/wake`) was built
   for Render's free tier, which sleeps an idle service. The app now runs on a dedicated,
   always-on VM behind pm2 — there is no sleep state to wait out, so this is just a fake
   multi-second delay in front of every page load.
2. **Organisations are a database concept, not a product one yet.** The schema
   (`users` / `organisations` / `memberships`, RLS, the last-owner-guard trigger, a
   signup trigger that auto-creates one org per new user) is already solid — but there
   is no way for a user to create a _second_ organisation, switch between them, invite a
   teammate for real, remove one, delete an org, or edit their own profile. `settings/team`
   and `accept-invite/[token]` are fully decorative today (`NotWiredNotice`,
   "Invitations aren't connected yet").
3. **Auth screens should stay minimal**, with success states as a toast instead of a
   full paragraph (login/signup are already close to this; forgot/reset-password and
   verify-email carry more copy than they need).
4. **Local dev should start the API with `uvicorn` directly**, not `python run_api.py`.
   (Production already runs uvicorn under pm2 — confirmed in `SYSTEM.md` §11 — so this is
   purely a repo/docs cleanup, not a deploy change.)

Confirmed with you: invites will send **real email via Resend** (3,000/day free tier) —
you'll supply the API key + verified sending domain after the integration is built;
until then it reads from env vars and I'll use a placeholder from-address.

---

## Part 1 — Remove the fake cold-start UX

**Files:**

- Delete `apps/web/app/api/wake/route.ts` and `apps/web/components/app/prewarm.tsx`
  (remove its mount point in `apps/web/app/(marketing)/layout.tsx`).
- `apps/web/lib/hooks/use-connection.ts`: collapse `ConnectionPhase` to
  `"connecting" | "up" | "down"`. One request; on failure, 2 quick retries (short fixed
  delay) for a genuine transient blip, then `"down"`. Remove `wakeSeconds`, the
  `WAKE_ATTEMPTS`/`WAKE_INTERVAL_MS` loop, and the `/api/wake` ping.
- `apps/web/components/app/connection-banner.tsx`: drop the "waking" lamp-sequence
  branch and its copy ("The service sleeps when it isn't in use…"). Keep only the
  `"down"` panel ("The service didn't respond" / reload) — now a rare, honest error
  state instead of an expected multi-second wait.
- `AppStoreProvider` (`apps/web/lib/app-store.tsx`) and the 8 call sites of
  `<ConnectionBanner phase wakeSeconds>` (found via grep: `app/page.tsx`,
  `campaigns/page.tsx`, `campaigns/[id]/page.tsx`, `contacts/page.tsx`,
  `escalations/page.tsx`, `runs/page.tsx`, `runs/[id]/page.tsx`, `runs/new/page.tsx`)
  drop the now-unused `wakeSeconds` prop.
- Check `components/marketing/hero.tsx` and `web/DESIGN_NOTES.md` for cold-start
  references and trim only what's actually about waking a sleeping service (not the
  hero's own scripted-typing timing, which is unrelated).

## Part 2 — `uvicorn`, not `python run_api.py`

- Delete `apps/api/run_api.py`.
- `CLAUDE.md` §6: replace `python run_api.py` with
  `uvicorn app.main:app --reload --port 8000` (run from `apps/api`).
- `.github/workflows/ci-cd.yml`: drop `run_api.py` from the `ruff check app tests
run_api.py` line.
- Production is unaffected — `SYSTEM.md` already documents pm2 running uvicorn there.

## Part 3 — Database: org logo, invitations, and the RLS to make them real

New Alembic revision (follows the exact pattern of
`apps/api/alembic/versions/202608060050_initial_schema.py`: raw SQL blocks for anything
autogenerate can't see).

**Schema**

- `organisations.logo_url text null` (mirrors `users.avatar_url`).
- New `invitations` table: `id uuid pk`, `org_id fk→organisations cascade`,
  `email citext`, `role org_role`, `token text unique`, `invited_by fk→users set null`,
  `expires_at timestamptz`, `accepted_at timestamptz null`, `created_at`. Partial unique
  index on `(org_id, lower(email))` where `accepted_at is null` (one live invite per
  address per org).

**New SECURITY DEFINER helpers** (same pinned-`search_path` pattern as
`is_org_member`/`has_org_role`):

- `public.unique_org_slug(base_name text) returns text` — extracts the
  slugify-then-dedupe loop that's currently inlined in the signup trigger, so both the
  trigger and the new "create organisation" endpoint call one implementation.
- `public.has_valid_invitation(target_org uuid, target_role org_role) returns boolean` —
  true if the current user's email has a matching, unexpired, unaccepted invitation.
- `public.lookup_invitation(token text) returns table(org_name text, role org_role,
email citext, valid boolean, reason text)` — for the **unauthenticated** accept-invite
  preview (see below).

**RLS changes**

- `memberships_insert` gains two more branches alongside the existing owner/admin one:
  `has_valid_invitation(org_id, role)` (accepting an invite) and
  `role = 'owner' and no existing membership row for this org_id` (bootstrapping the
  first owner of a brand-new organisation — today only the SECURITY DEFINER signup
  trigger can do this; a user-initiated "create another org" has nowhere to attach its
  first membership without this).
- `invitations`: `select`/`insert`/`delete` for org owner/admin
  (`has_org_role(org_id, ['owner','admin'])`); a narrow additional `select`/`update` for
  `lower(email) = own email` so an invitee can see/accept their own invite once signed in.
- Grants: `select, insert, update, delete` on `invitations` to `authenticated`
  (RLS does the real narrowing, per the existing convention in this migration file).

**Why not `privileged.acquire()` for the public token lookup:** CLAUDE.md is explicit —
`privileged` must never appear in a request handler. `database.anonymous()` already
exists for exactly this shape (a connection with no identity, calling a SECURITY
DEFINER function that internally bypasses RLS) — use that instead.

**Storage** — two buckets, created and policed via SQL in the same migration
(`insert into storage.buckets ...` + policies on `storage.objects`), not the dashboard:

- `org-logos` — public read; write restricted to path prefix `{org_id}/...` where the
  caller `has_org_role(org_id, ['owner','admin'])`.
- `avatars` — public read; write restricted to path prefix `{user_id}/...` where
  `user_id = current_user_id()`.

Both reuse the helper functions already defined for table RLS — no new logic, just new
policies referencing them.

## Part 4 — Backend: routes, repositories, email adapter

Introduces `app/api/v1/routes/` and `app/database/repositories/` for real (currently
empty per `CLAUDE.md`'s target layout) — scoped to the new surface only; the existing
inline endpoints in `main.py` are untouched.

- `app/integrations/email/resend.py` — mirrors `integrations/voice/engine.py`: the only
  file that imports the Resend HTTP client, aliased on the way in
  (`# from resend import ... as _VendorClient`-style), exposing one method like
  `send_invitation(to, org_name, role, accept_url)`. Reads `RESEND_API_KEY` and
  `RESEND_FROM_EMAIL` from `core/config.py` (new fields, same `field(default_factory=...)`
  pattern as the existing `whatsapp_token`). Empty key ⇒ raises a clear
  `EmailNotConfigured` the route layer turns into `503` with an honest message — same
  fail-closed spirit as the voice key check on `/api/runs`.
- `app/database/repositories/organisations.py`, `invitations.py` — the raw SQL for
  everything below, run through `database.as_user()` (or `database.anonymous()` for the
  one public lookup). No SQL in the route files themselves.
- `app/api/v1/routes/profile.py` — moves the existing `GET /api/v1/me` out of `main.py`
  here, adds `PATCH /api/v1/me` (name, avatar_url — self-service, no permission check
  beyond being signed in; `users_update_self` RLS already covers it).
- `app/api/v1/routes/organisations.py`:
  - `GET  /api/v1/organisations` — every org the caller belongs to (id, name, slug,
    logo_url, role) — feeds the org switcher.
  - `POST /api/v1/organisations` — create one; caller becomes owner via the new
    bootstrap RLS branch.
  - `PATCH  /api/v1/organisations/me` — update the _active_ org (from `X-Org-Id`/default,
    same resolution `current_user` already does) — name, logo_url. `[ORG_UPDATE]`.
  - `DELETE /api/v1/organisations/me` — soft delete (`deleted_at`, column already
    exists). `[ORG_DELETE]`, owner-only per the existing permission matrix. App-level
    guard: 400 if this is the caller's only active organisation.
  - `GET /api/v1/organisations/me/members` — members (with role) + pending invitations.
    `[TEAM_READ]`.
  - `POST /api/v1/organisations/me/invitations` — create-or-refresh a pending invite,
    send it via the Resend adapter. `[TEAM_INVITE]`.
  - `DELETE /api/v1/organisations/me/invitations/{id}` — revoke a pending invite.
    `[TEAM_INVITE]`.
  - `PATCH /api/v1/organisations/me/members/{user_id}` — change role. `[TEAM_SET_ROLE]`.
    Catches the last-owner-guard trigger's exception → `400` with its message.
  - `DELETE /api/v1/organisations/me/members/{user_id}` — remove a teammate. Self-removal
    ("leave organisation") is allowed for anyone (the `memberships_delete` RLS policy
    already permits `user_id = current_user_id()`); removing _someone else_ requires
    `[TEAM_REMOVE]`. Same last-owner-guard handling.
- `app/api/v1/routes/invitations.py`:
  - `GET  /api/v1/invitations/{token}` — **public**, `database.anonymous()` +
    `lookup_invitation()`. Powers the accept-invite preview panel that's currently
    hard-coded to "Couldn't be confirmed".
  - `POST /api/v1/invitations/{token}/accept` — authenticated; inserts the membership
    (via the invitation RLS branch), marks `accepted_at`. Returns the org so the client
    can switch to it.
- `main.py`: `app.include_router(...)` for the four new routers; remove the inline
  `MeOut`/`/api/v1/me` now that it lives in `profile.py`.

## Part 5 — Frontend: the client, the switcher, the settings pages

- **`lib/api.ts`** — the one place `fetch()` happens (per `CLAUDE.md`). Add an
  `authHeaders()` helper (reads the Supabase session the same way `use-session.ts`
  does, plus an active-org id from a small localStorage-backed value) and thread it
  through `req()` for the new authenticated calls; add typed methods:
  `listOrganisations`, `createOrganisation`, `updateActiveOrganisation`,
  `deleteActiveOrganisation`, `listMembers`, `inviteMember`, `revokeInvitation`,
  `setMemberRole`, `removeMember`, `previewInvitation(token)`, `acceptInvitation(token)`,
  `updateProfile`.
- **Active-org state** — a small `useActiveOrg()` hook (same
  `useSyncExternalStore`-over-`localStorage` pattern as
  `lib/hooks/use-external-store.ts`) holding the selected org id, defaulting to
  whatever `/api/v1/me` returns. The org switcher writes to it; `api.ts`'s
  `authHeaders()` reads it for `X-Org-Id`.
- **Org switcher** — extend `components/layout/user-menu.tsx`: replace the static
  "org name + role" line with a small submenu (reusing `dropdown-menu.tsx` primitives
  already imported there) listing every org from `listOrganisations()`, a "+ New
  organisation" item opening a small dialog (name + optional logo, reusing `Dialog`
  from `ui/dialog.tsx`), and add a "Profile" link alongside the existing "Settings" one.
- **Image upload** — one new `components/ui/image-upload.tsx`: preview + click/drag,
  client-side type/size check (jpg/png/webp, ≤2MB), uploads directly to Supabase
  Storage via `supabaseBrowser()` (`storage.from(bucket).upload(...)`, matching the
  RLS path-prefix scheme from Part 3), returns the public URL to the caller, who PATCHes
  it to the API. No cropping — out of scope.
- **`/app/settings` (Organisation tab)** — wire the existing form
  (`apps/web/app/(app)/app/settings/page.tsx`) to `updateActiveOrganisation`; replace the
  fake "not saved yet" toast with a real save + `toast({tone:"success", title:"Organisation updated"})`.
  Add logo upload. Add a "Delete organisation" section (typed-name confirmation, same
  UX pattern as the dry-run-off confirmation in `dry-run-switch.tsx`), owner-gated by
  `permissions.includes("org:delete")` from the session.
- **`/app/settings/team`** — replace the stub in `team/page.tsx`: real member list +
  pending-invite list from `listMembers()`, real invite dialog (`inviteMember`, success
  toast "Invitation sent"), remove/role-change actions gated by permission, delete the
  `NotWiredNotice` for this pane.
- **New `/app/settings/profile` tab** — name + avatar upload, `updateProfile()`, added
  to the `TABS` array in `settings/layout.tsx`.
- **Post-signup onboarding step** — new `apps/web/app/(app)/app/onboarding/organisation/page.tsx`:
  confirm/rename the auto-created org and optionally add a logo, skippable, one-time
  (same `useStoredString` pattern `welcome/page.tsx` already uses for its own step
  tracking). Change the signup redirect in `apps/web/app/(auth)/signup/page.tsx`
  (`router.replace("/app/welcome")`) to point here first; this page's "Continue"
  forwards to `/app/welcome`. No middleware changes needed — this is a client redirect
  hop, same as the existing flow.
- **`accept-invite/[token]/page.tsx`** — replace the hard-coded `organisation`/`role`
  nulls with a real `previewInvitation(token)` call on mount. If already signed in, skip
  the name/password form and show a single "Join {org}" button calling
  `acceptInvitation(token)`; otherwise keep the existing name/password form, call
  `signUpWithPassword` (email fixed to the invite's, not user-editable) then
  `acceptInvitation(token)`, then redirect to `/app`.
- **Auth screens, minimal + toast** — `forgot-password/page.tsx`: replace the full-page
  "Check your email" success panel with `router` staying put but showing a toast
  (`tone:"success", title:"Reset link sent"`) plus collapsing the form to a disabled/sent
  state, dropping the extra explanatory panel. `reset-password/page.tsx`: add a success
  toast at its existing `router.replace("/app")` (currently silent). Leave
  `reset-password`'s expired-link state and `verify-email`'s "not connected" notice as
  pages, not toasts — those are errors/blockers a person needs to actually read, not a
  fire-and-forget confirmation.

## Part 6 — Docs

- `SYSTEM.md`: update the API reference (§5) with the new endpoints, the feature matrix
  (§3, org/team rows move from "not wired" to real), and §12's F4 gap-map row.
- `ISSUES.md`: log anything found while wiring this up.
- `SUPABASE_SETUP.md`: add the Resend SMTP note is already there (line ~44) — add a new
  short section for `RESEND_API_KEY`/`RESEND_FROM_EMAIL` env vars and a one-line mention
  that Storage buckets are created by migration, not the dashboard.

---

## Verification

- `pytest -q` in `apps/api` — extend `tests/` with the RLS/permission-relevant cases:
  bootstrap-owner insert, invitation-branch insert, last-owner-guard still fires,
  cross-tenant isolation for the new `invitations` table (a cross-org read must return
  nothing) — matching the existing cross-tenant test style.
- `ruff check app tests` (no more `run_api.py` in the list).
- `npm run lint && npm run type-check && npm run build` in `apps/web`.
- Manual pass: sign up fresh → land on the org-onboarding step → set a logo → continue
  to `/app/welcome` → invite a teammate (real email arrives via Resend once the key is
  set) → open the accept link in a private window → join → switch between the two orgs
  from the switcher → rename/delete the second org → confirm the "waking the service"
  banner never appears on any `/app/*` page load.
