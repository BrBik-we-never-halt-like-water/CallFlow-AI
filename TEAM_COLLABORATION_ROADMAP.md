# Role-based UI + teammate collaboration — roadmap

Target state and build order for making the product's four roles
(`owner > admin > operator > viewer`) actually mean something in the UI, plus a set of
new collaboration features on top: per-teammate visibility, real escalation assignment,
enforced per-teammate credits, live sync, peer-to-peer resource sharing, and (not yet
started) an in-app notification inbox.

**Status as of 2026-08-10.** Phases 0, 1, 2, 4, and 5 (including enforcement) are shipped
and tested (backend: `pytest`, `ruff` clean; frontend: `type-check`, `lint`, `build`
clean). Phases 3 and 6 are designed below but not built - each depends on the in-app
notification inbox, which is Phase 3 itself. This file is the durable, checked-in version
of the working plan - it replaces re-deriving "what's next" from scratch each session.

**Related:** [`CLAUDE.md`](CLAUDE.md) (conventions this roadmap follows - RLS shape, repo
layout, permission matrix) · [`SYSTEM.md`](SYSTEM.md) (as-built reference, §5/§8 for the
routes and pages this roadmap added) · [`ISSUES.md`](ISSUES.md) (iteration 21 for Phase 1,
iteration 22 for the Phase 0 follow-through, iteration 28 for Phase 2/5's initial slice,
iteration 29 for Phase 4, iteration 30 for Phase 5's enforcement - the actual bug-and-fix
narrative lives there, not duplicated here. Renumbered on merge with `dev` - iterations
23-27 there belong to unrelated work done independently on that branch)

---

## Role capability matrix (target state)

| Screen / action | Owner | Admin | Operator | Viewer |
|---|---|---|---|---|
| Dashboard | all org data | all org data + per-teammate breakdown | own data only | all org data, read-only |
| Campaigns - view | all | all | own only + a name/owner-only directory of the rest, with "Request access" | all, read-only |
| Campaigns - create/edit/delete | yes | yes, any | own only | no |
| Runs - view | all | all | own only | all, read-only |
| Runs - start | yes | yes | own campaigns | no |
| Needs a person - view | all | all | own runs + assigned to them + a directory of other open ones, with "Request to help" | all, read-only |
| Needs a person - resolve | yes | yes, any | own/assigned only | no |
| Needs a person - assign to teammate | yes | yes | no | no |
| Request access to a teammate's campaign/escalation | n/a (sees all already) | n/a | yes | no |
| Approve/reject a request for a resource they own | n/a | n/a | yes | n/a |
| Organisation (team, org settings) | full | full except org delete | hidden | hidden |
| Settings - Safety | read+write | read+write | read-only | read-only |
| Settings - API keys / Integrations | read+write | read+write | hidden | hidden |
| Settings - Billing | full | read-only | replaced with "My credits" | replaced with "My credits" |
| Team - set a teammate's daily credits | yes | yes | no | no |
| Contacts | all | all | own only | all, read-only |

Everything above is now enforced except a general notification inbox (Phase 3) - approving
or rejecting a share request today only surfaces live in the Organisation page's Sharing
tab, not as a push notification the way Phase 3 would eventually deliver it.

---

## Phase 0 — Frontend role/route gating — ✅ shipped

Nav-level gating (`AppSidebar`'s footer links, `UserMenu`'s "My credits" swap for
operator/viewer), read-only field-level gating on every settings page, and per-action-
button permission checks across every remaining page (campaigns, runs, contacts,
dashboard, escalations, the organisation logo upload). `settings/layout.tsx`'s tab bar
now filters per-tab by that tab's own read permission. `ISSUES.md` #71, #74.

## Phase 1 — Per-user data ownership (the data silo) — ✅ shipped

`campaigns_select`/`runs_select`/`call_outcomes_select` RLS policies carry an
owner-or-admin-or-viewer-OR-created_by branch; an operator's plain org-scoped query
returns only what they made. `GET /api/v1/runs/team-summary` (now consumed by the
dashboard's Volume chart is *not* where the fuller breakdown lives any more - see Phase
2/5 below, which superseded it with `GET /api/v1/organisations/me/team-performance`).
`ISSUES.md` iteration 21, `#64`.

## Phase 2 — Real, assignable, live-synced escalations — ✅ shipped

**Goal met:** "needs a person" is a real, durable row now, not a computed label that
forgets itself on reload - and assigning one reaches every other signed-in teammate
immediately, not on their next poll.

- New `public.escalations` table (migration `43a7b26f6038`): one row per `call_outcomes`
  id, inserted by `runs.py`'s/`webhooks.py`'s outcome-resolution call sites whenever a
  call lands on `Disposition.ESCALATED` or `Disposition.UNREACHABLE` (the same pair
  `lib/lamp.ts`'s `flare` state already groups as "needs a person" everywhere in the
  product - kept as one shared constant, `domain/entities.py`'s
  `NEEDS_A_PERSON_DISPOSITIONS`, so the two can't drift apart again).
- `append_outcome()` now returns the call outcome's id (`RETURNING id`) instead of being
  write-only - the stable id `escalations.call_outcome_id` needed to exist at all.
- RLS: select = org role in (owner, admin, viewer) OR `assigned_to` = self OR the
  underlying run's `started_by` = self. A follow-up migration (`3ea00413701c`) had to fix
  an **infinite recursion** the first attempt caused - `runs_select` querying
  `escalations` while `escalations_select` queries `runs` back is exactly the "a policy
  that queries its own table recursively" trap `initial_schema`'s own comment already
  warned about, just across two tables. Fixed with `SECURITY DEFINER` helper functions
  (`is_assigned_to_run_escalation`, `is_assigned_to_call_outcome_escalation`), the same
  pattern `has_org_role`/`current_user_id` already use for the same reason. Caught by the
  new RLS test suite before it ever reached the frontend.
- New `Permission.ESCALATIONS_ASSIGN` (admin + owner only).
- New route `app/api/v1/routes/escalations.py`: `GET /api/v1/escalations`,
  `POST /{id}/assign {user_id}`, `POST /{id}/resolve`.
- **Live sync:** `escalations` is now in Supabase's `supabase_realtime` publication
  (migration `aebc05c817cf`, `REPLICA IDENTITY FULL`). The frontend
  (`lib/hooks/use-escalations-realtime.ts`) subscribes to Postgres Changes filtered to
  the active org and refetches on any insert/update - RLS is what actually scopes which
  events a given subscriber receives, the same way it scopes a normal query. This is the
  first table in the product to use Realtime at all (previously 2.5s/4s polling only).
- Frontend: `escalation-card.tsx` calls the real endpoints (`Escalation` type, a
  superset of `Outcome` so the transcript sheet needs no adapter); "Reassign" is a real
  teammate picker (admin/owner only); `app-store.tsx`'s escalation list is a real fetch,
  not derived from `outcomes` + local-only "resolved" state.
- Tests: 5 new cross-member RLS tests (`test_rls_isolation.py`) - an unassigned
  operator can't see a teammate's escalation, an assignee can regardless of who started
  the run, an operator can't assign/resolve a teammate's escalation directly (RLS, not
  just the permission check, is what actually blocks it).

## Phase 5 — Per-teammate credits + team-performance dashboard — ✅ shipped, including enforcement

**Goal met in full as of `ISSUES.md` iteration 30.** Shipped in two passes: a minimal
slice first (`Iteration 28`) - admin/owner can allocate a slice of the org's existing
daily budget per teammate, and see calls/run-status/open-escalations/credits for the
whole team in one dashboard panel, display-only, honestly labelled as such - then
enforcement (`Iteration 30`): **1 credit = 1 connected call**, checked per dial the same
way every other safety guard is, layered on top of (never instead of) the org-wide daily
budget. `used_today` was redefined from "resolved call attempts" to "calls the callee
actually answered" for both passes at once, since enforcement and display must never be
able to disagree about what "used" means.

- New `public.member_credit_allocations` table (same migration as Phase 2,
  `43a7b26f6038`): `daily_allocation` per `(org_id, user_id)`. `used_today` is
  **derived live** from `call_outcomes`/`runs` (correct across restarts and replicas,
  unlike the org-wide `used_today`, which is `RateLimiter`'s in-process sliding window -
  `SYSTEM.md`'s own documented limitation, cited explicitly in `credits.py` so the two
  aren't mistaken for the same guarantee).
- New `Permission.CREDITS_WRITE` (admin + owner).
- New endpoints (`organisations.py`): `GET /me/team-performance` (calls, run-status
  breakdown, open escalations, credits - per teammate, gated on the existing
  `RUNS_READ_TEAM`), `GET /me/members/me/credits` (self, no permission beyond being
  signed in - RLS already scopes the row), `PATCH /me/members/{id}/credits`
  (`CREDITS_WRITE`).
- Frontend: dashboard's new **Team performance** panel (full-width, below the existing
  grid rather than crowding the Volume card) - one row per teammate: calls made, calls
  closed, runs active/completed/failed, open "needs a person" count, credits used/
  allocated. Organisation → Team pane gained a per-member "Credits/day" field
  (admin/owner only, hidden for owner rows). Settings → Billing's "My credits" view
  (previously an honest placeholder) now shows real numbers once an admin has set an
  allocation.
- **Enforcement (`Iteration 30`):** `credits_repo.get_enforced_ceiling()` - `None` when
  no row exists at all (only the org-wide budget applies), the real int otherwise
  (including `0`, distinct from "unset" - `get_allocation()`'s display convention
  can't be reused here). `domain/safety.py::check_dial_allowed()` gained a
  `credits_remaining` param. `CampaignRunner` reserves a credit before dialling and
  releases it if that call doesn't connect - the same "reserve at check time, release
  on no-dial" shape `core/rate_limit.py`'s own limiter already uses, so a burst of
  concurrent contacts near the last credit can't all slip through, and a call that
  never rings through never actually spends anything. `POST /api/v1/runs` resolves the
  caller's own ceiling once per run, same as suppression/allowlist already do.
- Tests: 2 new cross-member RLS tests for `member_credit_allocations` (an operator can't
  see or set a teammate's allocation directly) + 4 new permission-matrix tests for the
  two new `Permission` members.

## Phase 4 — Peer-to-peer campaign/escalation sharing — ✅ shipped

**Goal met:** an operator can request a teammate's campaign, or ask to take over their
escalation, and only that teammate (or an admin/owner) can grant it. Built without Phase
3's notification inbox underneath it - the "Sharing" tab's own live Realtime feed and its
"Waiting on you" / "Requests you've sent" split cover the same need for this one resource
type, without waiting on a general inbox. A future Phase 3 can still add a push
notification on top; it isn't required for this to work end to end.

- New `public.share_requests` table (migration `202608101100`, `4cbc5103657f`): who
  asked, who owns it, pending/approved/rejected, an optional 280-char message. A partial
  unique index (`share_requests_one_pending_idx`, `where status = 'pending'`) enforces
  "one pending request per resource per requester" without blocking a fresh request once
  the first is resolved.
- Three `SECURITY DEFINER` functions, same shape as `create_organisation()`/
  `remove_member_and_reassign_data()`: `resolve_resource_owner()` (never trusts the
  client - the requester's own RLS can't see the resource or its owner to check this
  themselves), `list_campaign_directory()`, `list_escalation_directory()` (name/contact +
  owner only, org-wide, deliberately bypassing Phase 1's per-creator RLS narrowing for
  this one read).
- RLS on `share_requests` itself stays ordinary (no `SECURITY DEFINER` needed): select =
  requester or owner or admin/owner; insert = `requested_by = self`; update (decide) =
  `owner_user_id = self` only, never broadened to admin/owner.
- New `Permission.SHARING_REQUEST` (operator, admin, owner - not viewer). Deciding needs
  no separate permission - it's gated by actually owning the resource.
- New endpoints: `GET /api/v1/campaigns/directory`, `GET /api/v1/escalations/directory`,
  `GET/POST /api/v1/share-requests`, `POST /{id}/approve` / `/reject`. Full request/
  response shapes in `SYSTEM.md` §5.
- **Approving a campaign clones it** (`created_by = requester`, a new independent id -
  edits after that point never write back to the original) through a fourth `SECURITY
  DEFINER` function, `clone_campaign_for_share()` (migration `202608101200`) - a plain
  `INSERT ... RETURNING` fails under RLS for any non-admin/owner approver, since
  Postgres also checks the table's `SELECT` policy against a `RETURNING` row and an
  operator's own select policy is `created_by = self` (`ISSUES.md` #85, S1, found by
  manual testing, not static review).
- **Approving an escalation reassigns it** (`assigned_to = requester`, via the existing
  `escalations_repo.assign()`) - one real event, not a fork, unlike a campaign template.
- The atomic pending→approved/rejected transition runs **before** the grant, not after,
  closing a double-grant race two concurrent approvals could otherwise hit (`ISSUES.md`
  #86, S2, found by code review). Ownership is re-resolved at decide-time and a stale
  request (owner changed since it was made) auto-rejects instead of overriding whoever
  holds it now.
- Live sync: `share_requests` joined the `supabase_realtime` publication (migration
  `202608101130`). Frontend generalised the escalations-only Realtime hook into
  `lib/hooks/use-org-realtime.ts(table, orgId, onChange)`, reused by both `escalations`
  and `share_requests`.
- Frontend: `ShareRequestDialog` (shared by both directory panels, copy varies "Request
  access"/"Request to help"); `/app/campaigns`'s "Team campaigns" directory; `/app/
  escalations`'s "Team escalations" directory; `/app/organisation`'s third tab,
  "Sharing" (`?tab=sharing`), split into "Waiting on you" (Approve/Reject) and "Requests
  you've sent" (status only).
- Tests: 8 new cross-member/security RLS tests (`test_rls_isolation.py`) - the directory
  functions and `resolve_resource_owner()` correctly bypass Phase 1's narrowing while
  still refusing non-members; a forged `owner_user_id` on an insert still can't grant
  access to the real resource; only the named owner can decide; deciding twice is a
  no-op; the operator-clones-operator case that `#85` regressed. 2 new permission-matrix
  tests for `SHARING_REQUEST`.
- Verification: this is the first phase this round verified through a real, running
  browser session with two genuinely separate signed-up accounts and a real invite -
  `#85` existed despite a fully green automated test run, because no automated test had
  ever exercised the authorized happy path's actual write, only the security boundary
  around it. See `ISSUES.md` iteration 29 for the full narrative.

---

## Phase 3 — Notifications — not started

**Goal:** the in-app inbox every later phase (assignment, sharing, edit-notices, credit
changes) needs before those phases can actually notify anyone about anything.

```sql
create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organisations(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,   -- recipient
  type text not null,        -- escalation_assigned | campaign_edited | share_requested |
                              -- share_approved | share_rejected | credits_adjusted
  title text not null,
  body text,
  actor_user_id uuid references public.users(id) on delete set null,     -- who caused it
  resource_type text,        -- campaign | escalation | run
  resource_id text,
  read_at timestamptz,
  created_at timestamptz not null default now()
);
-- select/update(mark read): user_id = current_user_id() only.
-- insert: with check (is_org_member(org_id)).
```

`GET /api/v1/notifications` (own, unread-first), `POST /{id}/read`. Frontend: a bell in
the sidebar footer, unread badge, a panel linking to the relevant resource. Worth
building on the same Realtime pattern Phase 2 just proved out (`postgres_changes` on
`notifications`, filtered by `user_id`) rather than polling - notifications are exactly
the kind of low-frequency, "the user should see this the moment it happens" event that
pattern fits.

## Phase 6 — Edit notifications — not started, depends on Phase 3

**Goal:** "if the admin alters anything it should be notified to that user" - a teammate
finds out when someone else edits something they created.

Add `campaigns.updated_by`. After a successful `update_campaign`, if
`updated_by != created_by` (and `created_by` isn't null), insert a `campaign_edited`
notification naming the editor. No new frontend surface beyond the Phase 3 inbox.

---

## What's explicitly out of scope unless asked

- A general audit log (`Permission.AUDIT_READ` exists, unused) - Phase 6 is targeted
  edit-notices, not a full "who changed what, ever" history view.
- Email delivery for notifications - Phase 3 is in-app only, matching how invites are the
  only thing that currently sends real email.
- Contacts silo - Campaigns/Runs got the per-creator restriction (Phase 1); Contacts
  wasn't named explicitly and stays org-wide unless asked.

## Verification approach (every phase, followed for 0/1/2/4/5)

- Every new/changed RLS policy gets a same-org, cross-member test alongside the existing
  cross-tenant suite (`test_rls_isolation.py`) - not just a permission-matrix unit test,
  since a policy that looks right and permits a same-org cross-member read is exactly the
  class of bug this codebase treats as most expensive.
- `pytest -q`, `ruff check app tests`, `npm run lint && npm run type-check && npm run
  build` clean before considering a phase done - not just type-check, since a broken
  runtime import (e.g. an unused permission dependency) type-checks fine but fails at
  request time.
- Phase 4 added a third check worth keeping for anything RLS-heavy: a real manual pass
  through a running browser with two genuinely separate accounts, not just the automated
  suite. `#85` shipped past a fully green `pytest` run because no automated test ever
  exercised the authorized happy path's actual write (a non-admin/owner approver cloning
  a campaign) - only the security boundary around it. Automated RLS tests prove
  unauthorized access is blocked; they don't by themselves prove authorized access works.
