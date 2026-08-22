# CallFlow AI — capabilities reference

Everything the product can actually do today, organised by capability rather than by
code layer: what it is, where it lives in the UI, which API endpoints back it, what a
correct result looks like, and - for every section - what to check in the browser's
DevTools when something doesn't match. Written after a full review/fix/test pass on the
role, sharing, and credits systems (2026-08-10) - nothing below describes a feature this
review found broken and left unfixed.

**How this differs from the other docs at the repo root:** [`SYSTEM.md`](SYSTEM.md) is
the exhaustive as-built architecture reference (every module, every field, every RLS
policy) for someone editing the code. [`TEAM_COLLABORATION_ROADMAP.md`](TEAM_COLLABORATION_ROADMAP.md)
is the phase-by-phase build history for the role/sharing/credits systems specifically.
[`MANUAL_TESTING.md`](MANUAL_TESTING.md) is a click-through test script. [`ISSUES.md`](ISSUES.md)
is the bug log. This document is the one to read to answer "what can this product do,
which endpoint does it, and how do I tell if it's actually working" - for every area,
not just the newest one.

**Every run dials a real phone number - there is no simulation mode anywhere in this
product.** Keep that in mind reading the Runs section below.

---

## Contents

1. [Quick reference — base URL, auth, headers](#1-quick-reference)
2. [Authentication & identity](#2-authentication--identity)
3. [Organisations, team & roles](#3-organisations-team--roles)
4. [Campaigns](#4-campaigns)
5. [Runs (placing calls)](#5-runs-placing-calls)
6. [Escalations ("needs a person")](#6-escalations-needs-a-person)
7. [Sharing (peer-to-peer requests)](#7-sharing-peer-to-peer-requests)
8. [Credits & billing](#8-credits--billing)
9. [Safety guards & suppression list](#9-safety-guards--suppression-list)
10. [API keys](#10-api-keys)
11. [Integrations (Twilio / Plivo)](#11-integrations-twilio--plivo)
12. [Contacts](#12-contacts)
13. [Realtime (live sync)](#13-realtime-live-sync)
14. [Full endpoint index](#14-full-endpoint-index)
15. [General debugging toolkit](#15-general-debugging-toolkit)
16. [What isn't built yet](#16-what-isnt-built-yet)

---

## 1. Quick reference

- **Base URL:** `NEXT_PUBLIC_API_URL` (frontend env var) - typically the same origin as
  the deployed API.
- **Auth:** every endpoint except `GET /`, `GET /api/health`, `GET /api/v1/invitations/{token}`,
  and `POST /api/v1/webhooks/calle/{secret}` requires
  `Authorization: Bearer <token>`. The token is either a Supabase access token (the web
  app, always) or a CallFlow API key (`cfk_…`, see [§10](#10-api-keys)) - both resolve to
  the same identity shape server-side.
- **`X-Org-Id`:** send this header if the signed-in user belongs to more than one
  organisation. Omitting it silently falls back to whichever organisation they joined
  *first* - not necessarily the one showing in the UI. This is the single most common
  cause of "I did the action but nothing happened" during testing - **always check this
  header first** when a request 404s or returns unexpectedly empty data for a
  multi-org account.
- **Errors:** FastAPI's plain `{"detail": "..."}` shape - no problem-details envelope,
  no error codes. The `detail` string is written to be read by a human, not parsed by
  code (CLAUDE.md's own convention: state what happened and what to do next).
- **Every write is scoped to one organisation** (`org_id`), enforced twice - once in the
  route/repository layer, once again by Postgres RLS on the same query. A bug that only
  breaks one of the two layers is still contained by the other; both showing the same
  data is the actual guarantee.

---

## 2. Authentication & identity

**What it is.** Sign up, sign in, sign out, password reset, and "who am I" - backed by
Supabase Auth, with CallFlow's own `public.users`/`public.memberships` tables mapping an
auth identity onto an organisation and role.

**Frontend.** `(auth)/login`, `/signup`, `/forgot-password`, `/reset-password`,
`/verify-email`, `/accept-invite/[token]`. `lib/supabase/` (browser + server clients).
Every `/app/*` page is wrapped by `SessionGate` (`components/app/session-gate.tsx`),
which shows a skeleton while the session resolves and a retry panel if it fails to load
at all - pages don't each reinvent that state.

**Backend.**

| Endpoint | Auth required | What it does |
|---|---|---|
| `GET /api/v1/me` | yes | The signed-in user, their **active** organisation (name, role, plan, `onboarded_at`), and their full permission list. Called once after sign-in to hydrate the whole session. |
| `PATCH /api/v1/me` | yes | Update your own name/avatar. |
| `GET /api/v1/invitations/{token}` | no (public) | Preview an invite before signing in - org name, role, the email it was sent to, and whether it's still valid. |
| `POST /api/v1/invitations/{token}/accept` | yes | Turns a pending invitation into a real membership. |

**What to expect.** `GET /api/v1/me`'s `permissions` array is what the frontend uses to
show/hide everything role-gated - it is **not** decorative; every one of those strings
maps 1:1 to a `Permission` the backend independently re-checks per request. `active.role`
is the role in the *currently active* organisation only - a user with different roles in
different organisations sees a different `permissions` array after switching orgs
(`X-Org-Id` changes, then `GET /api/v1/me` is refetched).

**Debugging this section.** DevTools → Network → find `/api/v1/me` → Response tab is the
single most useful request in the entire app when a permission-related bug is reported:
it shows exactly what role/permissions the backend thinks this session has, which is the
actual source of truth the whole UI renders from. If the UI shows something a role
shouldn't see, check this response before assuming a frontend bug - if `permissions`
already excludes it and the UI still shows it, that's a real frontend gating bug; if
`permissions` includes it, the backend granted more than expected, which is a much more
serious class of bug (check the `ROLE_PERMISSIONS` matrix in `app/auth/permissions.py`
and the RLS policy on whatever table is over-exposed).

---

## 3. Organisations, team & roles

**What it is.** Four roles - `owner > admin > operator > viewer` - and everything about
who's in the organisation: inviting, removing, re-roling, and the mandatory first-login
org-setup gate.

**Frontend.** `/app/organisation` (three tabs: Organisation, Team, Sharing - `?tab=`
selects one). The org-setup gate itself isn't a route - `OnboardingGate`
(`components/app/onboarding-gate.tsx`) renders as a non-dismissible modal over whatever
`/app/*` page is active, until `active.onboarded_at` is non-null. `lib/hooks/
use-permission.ts` (`usePermission()`/`useRole()`) is how every page reads the role/
permission data from `GET /api/v1/me` without re-deriving it inline.

**Backend.**

| Endpoint | Permission | What it does |
|---|---|---|
| `GET /api/v1/organisations` | signed in | Every org this user belongs to (for the org switcher). |
| `POST /api/v1/organisations` | signed in | Create a second organisation - caller becomes its owner. |
| `PATCH /api/v1/organisations/me` | `org:update` | Rename / re-logo the active org. |
| `POST /api/v1/organisations/me/complete-onboarding` | `org:update` | Confirms the org's real name, sets `onboarded_at` - clears the mandatory gate. Idempotent (`coalesce`). |
| `DELETE /api/v1/organisations/me` | `org:delete` | Delete the active org - blocked with a 400 if it's the caller's only one. |
| `GET /api/v1/organisations/me/members` | `team:read` | Members + pending invitations. |
| `POST /api/v1/organisations/me/invitations` | `team:invite` | Invite by email + role. Sends real email via Resend. |
| `DELETE /api/v1/organisations/me/invitations/{id}` | `team:invite` | Revoke a pending invite. |
| `PATCH /api/v1/organisations/me/members/{id}` | `team:set_role` | Change a member's role - see the rank rule below. |
| `DELETE /api/v1/organisations/me/members/{id}` | `team:remove` (or none, for your own row) | Remove someone else (reassigns their data to you, deletes their account entirely) or leave yourself (membership-only). |
| `GET /api/v1/organisations/me/team-performance` | `runs:read_team` | Per-teammate calls/runs/escalations/credits - the dashboard's Team performance panel. |

**The role-rank rule (important, and easy to test wrong):** holding `team:set_role` lets
you change *a* role, but **not any role** - you can only grant a role strictly below your
own, and only act on (update/remove) a member currently holding a role strictly below
your own. Owner is the sole exception: an owner may grant or act on anyone, including
another owner. This means an **admin cannot promote anyone to admin or owner**, cannot
demote another admin, and cannot remove another admin - even though `team:set_role`/
`team:remove` alone would otherwise allow it. This is enforced in **two independent
places** - `can_grant_role()`/`can_act_on_member()` in Python, and their SQL mirrors
(`public.can_grant_role()`/`public.can_act_on_member()`) - so it holds even for a write
that reaches the database some other way.

**What to expect.** Inviting someone sends real mail through Resend - if it never
arrives, check `GET /api/health` or the invite response for a `503`/`502` first (see
`ISSUES.md` #51 - a common cause is the sending domain not being verified in Resend,
which is a dashboard setting, not a code bug). Removing a *teammate* (not yourself) is
heavier than it sounds: `remove_member_and_reassign_data()` transfers everything they
created in this org to whoever removed them, then deletes their account **entirely**
(every org they're in, not just this one) - the Team pane's Remove action requires typing
their name to confirm, on purpose.

**Debugging this section.** A 403 on a team-management action almost always means one of
the two rank checks above tripped - the error message names which role the caller
actually has and what's missing, so read it before assuming a bug. To confirm the rank
rule is really enforced by the database and not just the route, try the same write via
the SQL functions directly if you have database access: `select public.can_grant_role('admin', 'owner')`
should return `false`. For the onboarding gate specifically, check `GET /api/v1/me`'s
`active.onboarded_at` - `null` means the gate should be showing; if the modal isn't
appearing despite `null`, that's a frontend bug in `OnboardingGate`, not a data problem.

---

## 4. Campaigns

**What it is.** A reusable "goal + extraction schema" template a run dials against - two
built-in templates (Python constants, can't be edited/deleted) plus an organisation's own
custom ones (real Postgres rows).

**Frontend.** `/app/campaigns` (list, filter all/template/custom, duplicate, delete);
`/app/campaigns/new`, `/app/campaigns/[id]` (two-pane editor with a live goal + schema
preview, rendered **locally**, not via the API). `components/app/campaign-editor.tsx`,
`campaign-card.tsx`. `lib/campaign-fields.ts` (editor field types ↔ JSON Schema).

**Backend.**

| Endpoint | Permission | What it does |
|---|---|---|
| `GET /api/v1/campaigns` | signed in | Built-ins + this org's own rows. An **operator only ever gets their own** rows back - enforced by RLS on the query itself, not a filter in the handler. |
| `POST /api/v1/campaigns` | `campaigns:write` | Create. Id is slugified from the name, deduplicated against built-ins and this org's existing ids. |
| `PATCH /api/v1/campaigns/{id}` | `campaigns:write` | Edit - id never changes, so existing runs keep pointing at the right campaign. |
| `DELETE /api/v1/campaigns/{id}` | `campaigns:delete` | Delete - 400 if built-in. |
| `POST /api/v1/campaigns/preview` | signed in | Render a goal server-side without dialling. **Not currently called by the frontend** - the editor renders the same logic locally. |
| `GET /api/v1/campaigns/directory` | signed in | Name + owner only, org-wide - lets an operator see what exists to request (see [§7](#7-sharing-peer-to-peer-requests)) without seeing its content. |

**What to expect.** An operator's `/app/campaigns` list is genuinely smaller than an
admin's for the same organisation - this is correct (per-creator data ownership, not a
bug), and it's why the directory endpoint above exists as a separate, deliberately
narrower read. Editing a built-in template (`travel-discovery`,
`appointment-reminder`) always 400s with "Built-in campaigns cannot be edited." - by
design, not a missing feature.

**Debugging this section.** If an operator "can't see a campaign they should own,"
check `created_by` in the `GET /api/v1/campaigns` response against their own `user_id`
from `GET /api/v1/me` - if it doesn't match, they don't own it (which is correct
behaviour, not a bug); if it does match and it's still missing, that's a real RLS/query
bug worth reporting with both response bodies attached. The campaign editor's live
preview never touches the network - if the preview looks wrong, the bug is in
`lib/campaign-fields.ts`'s local rendering, not an API call; Network tab will show
nothing relevant to check.

---

## 5. Runs (placing calls)

**What it is.** Starting a batch of real phone calls against a campaign, watching them
resolve live, and reading the transcript/extracted result/triage outcome of each.
**There is no dry-run mode** - every contact submitted here gets an actual dial attempt.

**Frontend.** `/app/runs` (list, sort, paginate, CSV export); `/app/runs/new` (paste/
CSV/manual contact entry, campaign picker, local goal preview, Start); `/app/runs/[id]`
(live-updating call list, transcript sheet). `lib/hooks/use-run-poll.ts` polls
**every 2.5 seconds** while a run is active - this is polling, not Realtime (see
[§13](#13-realtime-live-sync) for which parts of the product are which).

**Backend.**

| Endpoint | Permission | What it does |
|---|---|---|
| `POST /api/v1/runs` | `runs:start` | Starts a run. Validates contacts, checks the org's safety guards (allowlist, rate limit, daily budget - see [§9](#9-safety-guards--suppression-list)), resolves suppression per contact, creates the `runs` row, then dials **in a background task** - the HTTP response returns immediately with `{run_id, total}`, before any call has necessarily connected. |
| `GET /api/v1/runs` | signed in | List, org-scoped (and per-creator scoped for an operator, same as campaigns). |
| `GET /api/v1/runs/{id}` | signed in | Full detail: every call outcome (transcript, extracted fields, disposition, sentiment) plus aggregate stats. |
| `GET /api/v1/runs/{id}/calls/{call_id}/events` | signed in | CALL-E's own developer event log for one call, fetched on demand - richer than the 2.5s poll, since a fast state transition between two polls is otherwise invisible. |
| `GET /api/v1/runs/team-summary` | `runs:read_team` | Call volume per teammate (superseded for most UI purposes by `organisations/me/team-performance`, [§3](#3-organisations-team--roles), which has more detail - this one is a thinner, older shape still used in one place). |

**What to expect.** A `429` from `POST /api/v1/runs` means a safety guard rejected the
whole batch before dialling anything - the `detail` names which one (rate limit, daily
budget), and a rate-limit rejection includes a `Retry-After` header. A `400` means either
no contacts were submitted, a contact failed E.164 validation, or the deployment has no
voice API key configured at all (an environment problem, not a per-request one). Once a
run starts successfully, individual contacts can still fail per-contact (an invalid
number, no answer, provider error) - that's a normal `unreachable`/`skipped` disposition
on that one row, not a failure of the run as a whole.

**Debugging this section.** The single most useful check for "a run looks stuck": open
`GET /api/v1/runs/{id}` directly in the Network tab and read `status` and each outcome's
own `status`/`disposition` - the UI's lamps are a rendering of exactly this JSON, so if
the JSON already shows `completed`, a stuck-looking UI is a frontend rendering bug, and
if the JSON itself still shows `in_flight` long after you'd expect it to resolve, the
problem is upstream (the voice engine, or the background task) rather than in the
frontend at all - check `GET /{run_id}/calls/{provider_call_id}/events` for that specific
call next, since it often shows a warning/error the coarse status never surfaces.
Remember every dial is real - "the call never happened" is only a bug if the number was
genuinely reachable; the reserved test range (`+1 555 0100`–`0199`, see
`MANUAL_TESTING.md`) is *expected* to fail every time.

---

## 6. Escalations ("needs a person")

**What it is.** A real, persisted row created automatically whenever a call's
disposition lands on `escalated` or `unreachable` - the product's "this needs a human"
worklist. Assignable (admin/owner) and resolvable, and it survives a page reload (it did
not, before this round of work - see `TEAM_COLLABORATION_ROADMAP.md` Phase 2).

**Frontend.** `/app/escalations` - filter by reason/campaign, sort oldest/newest, open
the transcript, call back yourself, reassign (admin/owner - a real teammate picker), mark
resolved. Live-synced, not polled (see [§13](#13-realtime-live-sync)).
`components/app/escalation-card.tsx`.

**Backend.**

| Endpoint | Permission | What it does |
|---|---|---|
| `GET /api/v1/escalations` | `escalations:read` (every role) | RLS narrows this to what the caller's role/assignment actually allows - not a query filter in the handler. |
| `POST /api/v1/escalations/{id}/assign` | `escalations:assign` (admin/owner only) | Body `{"user_id": "..."}`. |
| `POST /api/v1/escalations/{id}/resolve` | `escalations:resolve` (everyone but viewer) | Only works on your own run's escalations, ones assigned to you, or (admin/owner) any of them. |
| `GET /api/v1/escalations/directory` | `sharing:request` | Open escalations org-wide, contact + campaign + owner only - see [§7](#7-sharing-peer-to-peer-requests). |

**What to expect.** A `404` on assign/resolve can mean either "this escalation doesn't
exist" or "it exists but RLS won't let you touch it" - **deliberately** the same response
either way, so a caller probing ids can't distinguish "not found" from "not yours."
Resolving an already-resolved escalation, or assigning on one that's already closed, both
404 with a message naming that specifically, rather than silently succeeding a second
time.

**Debugging this section.** If an assign/resolve action does nothing visible, check the
Network response status first: a `403` (permission) prints a name-the-required-
permission message; a `404` is the ambiguous "not found or not yours" case above. Live
updates (a teammate's assignment appearing on your screen without a refresh) depend on
the Supabase Realtime websocket - see [§13](#13-realtime-live-sync)'s debugging note if
that specifically is what's not working.

---

## 7. Sharing (peer-to-peer requests)

**What it is.** An operator can ask for a teammate's campaign, or ask to take over their
open escalation; only the resource's real owner (or an admin/owner, for viewing) can
grant it. Built in this round - see `TEAM_COLLABORATION_ROADMAP.md`'s Phase 4 writeup and
`ISSUES.md` iteration 29 for the two real bugs found and fixed while building it.

**Frontend.** `/app/campaigns`'s "Team campaigns" panel and `/app/escalations`'s "Team
escalations" panel (both operator-facing, "Request access"/"Request to help"); `/app/
organisation?tab=sharing`'s "Waiting on you" (Approve/Reject) and "Requests you've sent"
lists. `components/app/share-request-dialog.tsx`.

**Backend.**

| Endpoint | Permission | What it does |
|---|---|---|
| `GET /api/v1/campaigns/directory` | signed in | See [§4](#4-campaigns). |
| `GET /api/v1/escalations/directory` | `sharing:request` | See [§6](#6-escalations-needs-a-person). |
| `GET /api/v1/share-requests` | signed in | Own sent requests + requests directed at you to decide (RLS-narrowed). |
| `POST /api/v1/share-requests` | `sharing:request` | Body `{resource_type, resource_id, message?}`. The owner is resolved **server-side** - never trusted from the client. |
| `POST /api/v1/share-requests/{id}/approve` | none beyond being signed in - gated by actually owning the resource | Campaign: **clones** it (new independent id, `created_by` = requester). Escalation: **reassigns** it (`assigned_to` = requester) - one event, not a fork. |
| `POST /api/v1/share-requests/{id}/reject` | same as approve | Marks it rejected. |

**What to expect.**

- `resource_name` in a `GET /api/v1/share-requests` row is `null` on your own
  **pending, not-yet-decided** sent requests - that's correct, not missing data (your own
  RLS scope genuinely can't see a resource you don't own yet); it fills in once approved.
- Requesting the same resource twice while a request is still pending 409s with "You
  already have a pending request for this" - a real database constraint, not a
  client-side debounce. Once that request is decided (either way), requesting again
  works fine.
- Approving re-checks who *currently* owns the resource before granting - if ownership
  moved since the request was made, the request auto-rejects with "Ownership of this
  changed since the request was made," rather than silently overriding whoever holds it
  now.
- A campaign clone is fully independent from the moment it's created - editing either
  copy afterward never affects the other.

**Debugging this section.** This is the newest, most RLS-dependent part of the product,
so lean on the Network tab more than intuition here. `GET /api/v1/campaigns/directory`
and `GET /api/v1/escalations/directory` should show teammates' resources you don't own;
if either comes back empty when you know a teammate has something to show, check
`X-Org-Id` first (§1) - a mismatched org header is the most common cause. A `403` on
approve/reject means you're signed in as someone other than the resource's actual owner
- check the request's own `owner_user_id` field against your own `user_id` from
`GET /api/v1/me`. For "it should have updated live and didn't," see
[§13](#13-realtime-live-sync).

---

## 8. Credits & billing

**What it is.** Two related but distinct things: the organisation's overall plan/usage
(admin/owner), and an optional per-teammate slice of the org's existing daily call
budget that an admin/owner can set (everyone's own "My credits" view).

**Frontend.** `/app/settings/billing` - admin/owner see the real plan + org-wide usage;
everyone else sees "My credits" (their own allocation + today's usage, or a placeholder
if nobody's set one yet). Organisation → Team pane has a per-member "Credits/day" field,
editable by admin/owner only.

**Backend.**

| Endpoint | Permission | What it does |
|---|---|---|
| `GET /api/v1/me` (`active.plan_id`) | signed in | The org's plan name - part of the identity payload, not a separate call. |
| `GET /api/health` (`limits`) | none | The org-wide daily budget and today's real usage against it. |
| `GET /api/v1/organisations/me/members/me/credits` | signed in | Your own allocation + `used_today` - RLS scopes this to your own row automatically. |
| `PATCH /api/v1/organisations/me/members/{id}/credits` | `credits:write` (admin/owner) | Set a teammate's daily allocation (`>= 0`). `0` means "not set yet" in the UI's own display convention - but internally, a `0` row is enforced ("blocked entirely"), distinct from no row at all ("ungated") - see below. |
| `GET /api/v1/organisations/me/team-performance` | `runs:read_team` | Every teammate's allocation + usage in one call - the admin/owner dashboard view. |

**What to expect - the one thing worth stating explicitly:** **1 credit = 1 connected
call, and it's enforced** (`ISSUES.md` iteration 30) - layered on top of, never instead
of, the org-wide daily budget ([§9](#9-safety-guards--suppression-list)), which still
applies regardless of any individual allocation. Two things trip people up:

- **`used_today` counts connected calls only**, not every attempt - a call that never
  rings through (busy, no answer, an invalid number) does not spend a credit. Testing
  against the reserved fictional number range (`+1 555 0100`–`0199`) will therefore
  *never* increase `used_today`, since those numbers never connect - that's correct, not
  a stuck counter.
- **Setting someone's allocation to `0` blocks them immediately**, before any real
  number is dialled - but a teammate nobody has ever set an allocation for is **not**
  gated by this check at all (only the org-wide budget applies to them). The API
  distinguishes "no row" from "a row with `0`" internally
  (`credits_repo.get_enforced_ceiling()`); the "My credits" display's own `0`-means-
  unset convention is a UI simplification that doesn't apply to enforcement.

There's also no payment processor wired up at all - Billing's plan/usage view is real,
but there's no upgrade/downgrade flow behind it.

**Debugging this section.** `used_today` in both the "My credits" view and the admin
Team-performance panel are two independent live SQL queries against the same underlying
`call_outcomes`/`runs` data - they should always agree for the same person on the same
day. If they don't, that's a real bug worth reporting with both response bodies and a
timestamp (UTC day boundaries are the most likely explanation, not a calculation error).
This number is **not** the same as `GET /api/health`'s org-wide `used_today` - that one
is an in-process rate-limiter counter that resets on every deploy/restart (a known,
documented limitation, `SYSTEM.md` §7) and is correct only for "since the process last
restarted," never "since midnight."

---

## 9. Safety guards & suppression list

**What it is.** The guards that stand between "someone clicked Start run" and "a phone
actually rings," now that there's no dry-run mode to fall back on. Per-run ceiling,
allowlist, per-organisation rate limit, daily budget, phone masking, and the
do-not-call (suppression) list - all real, all overridable per organisation, all
enforced **per contact, immediately before dialling** inside `check_dial_allowed()`.

**Frontend.** `/app/settings/safety` (admin/owner read+write; operator/viewer read-only)
- shows and edits the org's own overrides, with live `used_today` from the actual rate
limiter. Contacts page's suppression tab.

**Backend.**

| Endpoint | Permission | What it does |
|---|---|---|
| `GET /api/v1/safety` | `safety:read` (every role) | This org's effective guard values (its own override merged onto deployment defaults) + live rate-limiter usage. |
| `PATCH /api/v1/safety` | `safety:write` (admin/owner) | Edit the org's own overrides. |
| `GET /api/v1/suppressions` | `suppressions:read` | This org's do-not-call list. |
| `POST /api/v1/suppressions` | `suppressions:add` (operator+) | Add a number. |
| `DELETE /api/v1/suppressions/{id}` | `suppressions:remove` (owner only) | Make a number callable again - deliberately the narrowest permission in the whole matrix. |

**What to expect.** Every one of these guards fails **closed** - if a check can't
complete for any reason, the dial is denied, never allowed by default. The suppression
list is checked **per contact inside the run**, not just displayed in the UI - a number
on the list will be silently skipped (marked `skipped`, not attempted) even mid-run.
**Calling-window enforcement does not exist server-side**, despite some UI surfaces
implying it does (`ISSUES.md` #20) - don't test for it expecting it to block a call
outside "business hours"; nothing currently checks that.

**Debugging this section.** `GET /api/v1/safety`'s `used_today` and `GET /api/health`'s
org-wide usage read the same underlying in-process counter and should always agree for
the same org - if you see two different numbers for the same organisation, that's a real
bug. Remember this counter is **process-local** - a redeploy or restart resets it to
zero, which looks exactly like "the daily budget mysteriously refreshed early" but is
actually a known, documented limitation (`SYSTEM.md` §7, `ISSUES.md` #10), not silent
data loss.

---

## 10. API keys

**What it is.** Org-scoped keys (`cfk_…`) for programmatic access to CallFlow's own API
- a second way into the same `current_user()` identity resolution the web app uses,
without a Supabase session at all.

**Frontend.** `/app/settings/api-keys` (admin/owner only) - create (full key shown
**exactly once**), list (name, prefix, last used, created), revoke.

**Backend.**

| Endpoint | Permission | What it does |
|---|---|---|
| `GET /api/v1/api-keys` | `api_keys:read` | List - never returns the full key, only its prefix. |
| `POST /api/v1/api-keys` | `api_keys:write` | Create - **the only response that ever contains the full key.** |
| `DELETE /api/v1/api-keys/{id}` | `api_keys:write` | Revoke. |

**What to expect.** Only a SHA-256 hash of the key is ever stored - if you navigate away
from the creation screen without copying it, it is genuinely gone; there's no "reveal"
action anywhere, by design. A key's effective *role* is re-read from the live membership
table on every request (not cached on the key itself) - removing someone from the org or
changing their role invalidates their keys' access immediately, not on their next sign-
in.

**Debugging this section.** To confirm a key actually works, try it directly:
```bash
curl -H "Authorization: Bearer cfk_..." https://<api-host>/api/v1/me
```
A `401 "That API key isn't valid. It may have been revoked."` means either it was
revoked, mistyped, or the prefix doesn't match what's on file - check the `key_prefix`
column shown in the UI against the start of the key you're using.

---

## 11. Integrations (Twilio / Plivo)

**What it is.** Org-owned credential storage for Twilio and Plivo, so an organisation can
eventually place calls from its own number instead of relying on the shared voice engine.
**Storing credentials is real and works today; actually placing a call through either
provider is separate, not-yet-built work** - the UI says so plainly rather than
pretending it's wired up.

**Frontend.** `/app/integrations` (admin/owner only, primary nav - the old
`/app/settings/integrations` path redirects here) - connect, update,
disconnect, with a `NotWiredNotice` explaining that dialling through these isn't live
yet.

**Backend.**

| Endpoint | Permission | What it does |
|---|---|---|
| `GET /api/v1/integrations/providers` | `integrations:read` | List connected providers (label, masked phone number, timestamps - never the credential itself). |
| `PUT /api/v1/integrations/providers/{provider}` | `integrations:write` | Connect or update any of the 57 providers. Each declares its own credential fields, so most authenticate with an identifier+secret pair rather than OAuth. **Checks the vendor first:** a rejection is a `400` and nothing is stored. |
| `POST /api/v1/integrations/providers/{provider}/verify` | `integrations:write` | Re-check a stored credential. Clears `verified_at` and returns `400` when the vendor no longer accepts it. Needs `write` despite reading nothing: it spends a request against the org's own vendor account. |
| `DELETE /api/v1/integrations/providers/{provider}` | `integrations:write` | Disconnect. |

**What to expect.** Credentials are encrypted at rest (Fernet, keyed by a server-side
secret) - a `503 "..."` on connect means that encryption key isn't configured in this
deployment at all, an environment problem, not a bad request.

**Credentials are checked with the vendor before they are stored, and the answer is
kept.** This paragraph used to say the opposite - "connecting succeeds as long as the
fields are non-empty; nothing calls out to either provider to check" - which is no
longer true on either half (`ISSUES.md` #160, #169, #179):

- The vendor **rejects** them -> `400` with its own refusal, and **nothing is
  stored**.
- The vendor **accepts** them -> stored with `verified_at` set. The only state
  reported as "Connected", and the only one the readiness line counts.
- CallFlow **cannot tell** -> stored with `verified_at` null and the reason shown.
  Covers an unreachable vendor, a key too narrowly scoped to check, and the 27
  of 57 providers with no probe. It deliberately does not fail the request: an
  outage must not stop someone saving a working key.

30 of the 57 declare a probe, carriers included. Sarvam deliberately does not - its
models endpoint returns 200 for an invalid key, so a probe there would manufacture the
exact false "Connected" this exists to prevent.

`POST .../verify` re-runs the check against a stored credential. It is the only
thing that notices a key revoked or rotated at the vendor's end, and the way out of
an unconfirmed save; a refusal clears `verified_at` rather than deleting the row.

**Debugging this section.** The response never contains the identifier or secret, even
right after connecting - if you need to confirm *which* credentials are stored, that's
only checkable against the encrypted ciphertext directly in the database (or not at all,
by design) - there's no API surface for it, and adding one would defeat the point of
encrypting them.

---

## 12. Contacts

**What it is.** The lightest capability in the product on purpose - contacts exist only
as an artifact of runs, not as a stored entity of their own.

**Frontend.** `/app/contacts` - search, view call history (derived entirely from past run
outcomes). `/app/runs/new`'s contact grid - paste, CSV drop, manual entry, per-row E.164
validation, "remove all invalid."

**Backend.** None. There is no `GET/POST /api/v1/contacts` - contacts are submitted
inline with `POST /api/v1/runs` and never persisted as their own row. The suppression
list ([§9](#9-safety-guards--suppression-list)) is the one contact-adjacent thing that
*is* real and server-backed.

**What to expect.** Nothing about a contact survives outside the context of the runs
that dialled them - there's no contact "profile," no saved list, no import history. This
is a known, current gap (`SYSTEM.md`'s own gap map, F13), not a bug - don't spend time
looking for a contacts API that doesn't exist.

**Debugging this section.** Any issue with contact data is either in the CSV/paste
parsing (`lib/contacts.ts`, entirely client-side - check the Console tab for a parse
exception, not the Network tab, since nothing round-trips to the server until Start Run
is clicked) or in the run's own outcome data once a run has actually started (see
[§5](#5-runs-placing-calls)).

---

## 13. Realtime (live sync)

**What it is.** Two tables push changes to every signed-in teammate immediately via
Supabase Realtime (Postgres logical replication over a websocket) rather than waiting for
a poll: `escalations` and `share_requests`. Everything else in the product (runs,
dashboard stats) is still interval polling.

**Frontend.** `lib/hooks/use-org-realtime.ts` - `useOrgRealtime(table, orgId, onChange)`,
a generic hook subscribing to `postgres_changes` on any table in the
`supabase_realtime` publication, filtered to the active organisation, calling `onChange`
(typically a refetch) on any insert/update. Used by `app-store.tsx` (escalations) and the
Sharing pane (`share_requests`).

**What to expect.** An event reaches a subscriber only if that subscriber's own RLS
`SELECT` policy would let them see the row via an ordinary query - Realtime does not
bypass RLS, it's scoped by the same policy a normal `SELECT` would use. This means an
operator who can't see a teammate's escalation directly also won't receive a live event
about it - which is correct, not a delivery bug.

**Debugging this section.** DevTools → Network → filter to **WS** (WebSocket) → look for
a connection to `<project-ref>.supabase.co/realtime/v1/websocket`. Status
`101 Switching Protocols` and no red/closed icon means the connection is healthy - if an
update isn't arriving live despite that, the more likely cause is the RLS-scoping
behaviour just described (the event genuinely wasn't sent to this subscriber) rather than
a broken connection. If the connection itself shows as closed/erroring, that's usually a
Supabase project-level issue (Realtime disabled for that table, or a network/proxy
blocking websockets) rather than an application bug - check whether the table is in the
`supabase_realtime` publication (`SYSTEM.md`'s migration references for the table in
question) before assuming the frontend hook is broken.

---

## 14. Full endpoint index

Every route in the API, grouped by router. `Any org member` means no permission beyond
being signed in (RLS still scopes the result). Full request/response JSON for each is in
`SYSTEM.md` §5.

| Method & path | Permission |
|---|---|
| `GET /` | none |
| `GET /api/health` | none |
| `GET /api/v1/me` | any org member |
| `PATCH /api/v1/me` | any org member |
| `GET /api/v1/invitations/{token}` | public |
| `POST /api/v1/invitations/{token}/accept` | any org member |
| `GET /api/v1/organisations` | any org member |
| `POST /api/v1/organisations` | any org member |
| `PATCH /api/v1/organisations/me` | `org:update` |
| `POST /api/v1/organisations/me/complete-onboarding` | `org:update` |
| `DELETE /api/v1/organisations/me` | `org:delete` |
| `GET /api/v1/organisations/me/members` | `team:read` |
| `POST /api/v1/organisations/me/invitations` | `team:invite` |
| `DELETE /api/v1/organisations/me/invitations/{id}` | `team:invite` |
| `PATCH /api/v1/organisations/me/members/{id}` | `team:set_role` |
| `DELETE /api/v1/organisations/me/members/{id}` | `team:remove` (or self) |
| `GET /api/v1/organisations/me/team-performance` | `runs:read_team` |
| `GET /api/v1/organisations/me/members/me/credits` | any org member |
| `PATCH /api/v1/organisations/me/members/{id}/credits` | `credits:write` |
| `GET /api/v1/campaigns` | any org member |
| `POST /api/v1/campaigns` | `campaigns:write` |
| `PATCH /api/v1/campaigns/{id}` | `campaigns:write` |
| `DELETE /api/v1/campaigns/{id}` | `campaigns:delete` |
| `POST /api/v1/campaigns/preview` | any org member |
| `GET /api/v1/campaigns/directory` | any org member |
| `POST /api/v1/runs` | `runs:start` |
| `GET /api/v1/runs` | any org member |
| `GET /api/v1/runs/team-summary` | `runs:read_team` |
| `GET /api/v1/runs/{id}` | any org member |
| `GET /api/v1/runs/{id}/calls/{call_id}/events` | any org member |
| `GET /api/v1/escalations` | `escalations:read` |
| `POST /api/v1/escalations/{id}/assign` | `escalations:assign` |
| `POST /api/v1/escalations/{id}/resolve` | `escalations:resolve` |
| `GET /api/v1/escalations/directory` | `sharing:request` |
| `GET /api/v1/share-requests` | any org member |
| `POST /api/v1/share-requests` | `sharing:request` |
| `POST /api/v1/share-requests/{id}/approve` | resource owner |
| `POST /api/v1/share-requests/{id}/reject` | resource owner |
| `GET /api/v1/safety` | `safety:read` |
| `PATCH /api/v1/safety` | `safety:write` |
| `GET /api/v1/suppressions` | `suppressions:read` |
| `POST /api/v1/suppressions` | `suppressions:add` |
| `DELETE /api/v1/suppressions/{id}` | `suppressions:remove` |
| `GET /api/v1/api-keys` | `api_keys:read` |
| `POST /api/v1/api-keys` | `api_keys:write` |
| `DELETE /api/v1/api-keys/{id}` | `api_keys:write` |
| `GET /api/v1/integrations/providers` | `integrations:read` |
| `PUT /api/v1/integrations/providers/{provider}` | `integrations:write` |
| `DELETE /api/v1/integrations/providers/{provider}` | `integrations:write` |
| `POST /api/v1/webhooks/calle/{secret}` | secret-in-path |

### Role → permission matrix

| Permission | Viewer | Operator | Admin | Owner |
|---|---|---|---|---|
| `*:read` (org/team/campaigns/runs/contacts/suppressions/escalations/safety) | ✅ | ✅ | ✅ | ✅ |
| `campaigns:write`, `campaigns:delete`, `runs:start`, `contacts:write`, `suppressions:add`, `escalations:resolve`, `sharing:request` | ❌ | ✅ | ✅ | ✅ |
| `runs:read_team` | ✅ (read-only breadth) | ❌ | ✅ | ✅ |
| `org:update`, `team:invite`, `team:remove`, `team:set_role`, `contacts:reveal`, `safety:write`, `api_keys:*`, `integrations:*`, `audit:read`, `billing:read`, `escalations:assign`, `credits:write` | ❌ | ❌ | ✅ | ✅ |
| `org:delete`, `billing:write`, `suppressions:remove` | ❌ | ❌ | ❌ | ✅ |

Approving/rejecting a share request needs **no permission from this table at all** - it's
gated purely by actually owning the resource in question (checked explicitly, backed by
RLS), so whichever role happens to own something can decide on it.

---

## 15. General debugging toolkit

Applies across every section above.

1. **Network tab, Fetch/XHR filter, every time.** This product has no hidden client-side
   business logic beyond `lib/api.ts` and local-only preview rendering (explicitly called
   out per-section above where it applies) - if something looks wrong, the request/
   response pair almost always shows you exactly what the backend decided.
2. **Check `X-Org-Id` first for any multi-org account.** Missing or stale, it silently
   targets the wrong organisation rather than erroring - this produces symptoms that look
   like almost any other bug ("my data disappeared," "the request 404s," "the count is
   wrong") and is the fastest thing to rule out.
3. **Compare the JSON to the role you're testing as.** `GET /api/v1/me`'s `permissions`
   array is the ground truth for what a session should be able to do - cross-check
   against it before concluding a 403 is unexpected.
4. **Console tab for uncaught errors.** This codebase doesn't swallow errors in empty
   `catch` blocks by convention - an error in the console is a real bug, not noise.
5. **WS filter for anything in [§13](#13-realtime-live-sync)'s scope** (Escalations,
   Sharing) - "it didn't update live" is a websocket/RLS-scoping question, not a general
   frontend question.
6. **`GET /api/health`** is the fastest single check for "is the backend even up, and
   what does it think the current org-wide safety/limiter state is" - no auth required.
7. When a response and the UI disagree, **trust the response** - the rendering logic is
   almost always the simpler of the two to have a bug in, and the JSON is what to quote
   when filing a report.

---

## 16. What isn't built yet

Named here explicitly, so a missing feature doesn't get mistaken for a bug during
testing. Full detail in `SYSTEM.md`'s gap map (§12) and `ISSUES.md`.

- **A general notification inbox.** Assignment, sharing decisions, and credit changes
  are all visible if you go looking (the relevant page, live-synced) but nothing pushes a
  "you have something new" indicator anywhere outside the pages that already show it.
- **Edit notifications.** If an admin edits someone else's campaign, the original creator
  is not told.
- **Calling-window enforcement does not exist server-side** despite some UI implying it
  does (§9).
- **Twilio/Plivo integrations store credentials but cannot yet place a call through
  either provider** (§11) - the shared voice engine is the only thing that actually
  dials, for every organisation, regardless of what's connected in Settings →
  Integrations.
- **No payment processor** - Billing shows real plan/usage, nothing behind an
  upgrade/downgrade action.
- **Contacts have no stored identity of their own** (§12) - by design for now, not a
  partial implementation of something bigger.
- **The org-wide safety/rate-limit counters are in-process** - they reset on every
  deploy/restart and don't agree across replicas. Per-teammate credit usage
  ([§8](#8-credits--billing)) does **not** have this limitation - it's a live SQL query,
  correct across restarts.
