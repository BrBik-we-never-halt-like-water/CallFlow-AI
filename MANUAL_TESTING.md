# Manual testing guide — roles, sharing, and credits

A click-through script for verifying the three systems built in the role-based UI
roadmap: the four-role permission matrix, peer-to-peer campaign/escalation sharing, and
per-teammate credits. Everything below is checkable in a browser, with what to look at
in DevTools when a step doesn't match what's expected.

**Companion docs:** [`TEAM_COLLABORATION_ROADMAP.md`](TEAM_COLLABORATION_ROADMAP.md) (why
each phase is shaped the way it is) · [`SYSTEM.md`](SYSTEM.md) (exact API shapes) ·
[`ISSUES.md`](ISSUES.md) (known quirks - check there before reporting something as new).

---

## Before you start

**⚠️ Every run dials for real.** There is no dry-run mode anywhere in this product
(CLAUDE.md's own non-negotiable #8) - clicking "Start run" places an actual outbound
call through CALL-E to whatever number you typed in. For every step below that mentions
starting a run:

- Use one of the reserved fictional numbers, **`+1 555 0100`–`+1 555 0199`**, if you only
  want to see the guard behaviour (per-run ceiling, rate limit, allowlist, the "run
  started" UI) without a real phone ringing anywhere - these numbers can't reach a real
  person, so CALL-E will fail the dial itself, which is expected and fine for this
  purpose.
- Use your **own** phone number only if you specifically want to see a completed call,
  a transcript, and a real triage result end to end - and only your own number, never
  anyone else's, without their consent.

**You need at least two accounts in the same organisation** with different roles to test
anything in Part 2 or Part 3 - a single owner account can't observe what an operator
sees. Suggested minimum: one **owner** (whichever account you already have) plus one
**operator** invited into the same org. Add an **admin** and a **viewer** too if you want
full matrix coverage.

**Getting a second signed-in account without a second real email address:** if your
Postgres/Supabase project uses Resend for invitation email and the domain isn't verified
yet (`GET /api/health` or a failed invite will tell you - see `ISSUES.md` #51), Resend's
API will reject `@example.com` and most other made-up addresses outright. Resend's own
test address, `delivered@resend.dev`, always accepts mail and is safe to use for this -
and `delivered+operator@resend.dev` / `delivered+viewer@resend.dev` (the `+tag` is
ignored for delivery but makes each one a distinct account) let you create as many
distinct test identities as you need against the same real inbox.

**Two browser profiles, not two tabs.** Supabase's session lives in a cookie scoped to
the browser profile, so signing in as a second account in a second tab of the *same*
profile will sign the first one out. Use an Incognito/Private window for the second
account, or two different browser profiles side by side.

---

## Part 1 — Set up your test accounts

1. Sign up (or use your existing account) - this becomes the **owner** of a
   fresh organisation automatically.
2. Go to **Organisation → Team** (`/app/organisation?tab=team`, or the "Organisation"
   link in the sidebar footer / account menu → Team tab). Click **Invite**, enter a test
   address (see above) and pick a role - do this once each for **operator**, **admin**,
   and **viewer** if you want full coverage.
3. Open the invite email (or the accept link directly, if email isn't delivering in your
   environment yet) in an Incognito window, set a name and password, and accept.
   - **Known quirk, not a bug to report:** the very first `/api/v1/me` call right after
     accepting sometimes 403s with "You are not a member of that organisation." The
     page's own **"Join {org}"** retry button fixes this immediately - it's a timing
     race in how fast the new membership becomes visible, and clicking retry once always
     works. See `ISSUES.md` for the existing note on this.
4. Confirm each new account landed in the org-setup gate (a non-skippable modal
   confirming the org's name) before reaching `/app` - this is the mandatory first-login
   gate, and it should be impossible to reach any `/app/*` page without clearing it.

**What to check in DevTools if a step above misbehaves:** Network tab → find the
`/api/v1/me` request → Response tab. It returns `active.role` and `active.org_id` - if
the role isn't what you expect, the invite was accepted with the wrong role (a bug), not
a frontend display issue. Application tab → Cookies → `sb-<ref>-auth-token` confirms
which account is actually signed in, useful when "the UI looks like the wrong account" -
decode the base64 JSON's `access_token` (a JWT) at jwt.io if you need to check its claims
directly.

---

## Part 2 — Role system walkthrough

Sign in as each role in turn (use a separate Incognito window per account, or sign out/in
between checks) and confirm the table below. "Hidden" means the nav link/section doesn't
render at all, not just disabled.

| Where | Owner | Admin | Operator | Viewer |
|---|---|---|---|---|
| Sidebar footer: **Organisation** link | visible | visible | **hidden** | **hidden** |
| Sidebar footer: **Settings** link | visible | visible | visible (Safety/API keys/Integrations tabs hidden inside) | visible (same) |
| Account menu (mobile) | Organisation + Settings | same | **"My credits" instead of both** | same as operator |
| `/app` Dashboard | full org data + Team performance panel | same as owner | **own runs/calls only**, no Team performance panel | full org data, read-only (no Start-run buttons) |
| `/app/campaigns` | all campaigns, full actions | same | **own campaigns only** + a "Team campaigns" directory (see Part 3) | all campaigns, **no** New/Edit/Delete/Duplicate buttons |
| `/app/runs/new` | can start | can start | can start (own campaigns only) | **page/action unreachable** - `NotWiredNotice` if navigated to directly |
| `/app/escalations` | all, assign + resolve any | same | own + assigned to them + a "Team escalations" directory | all, read-only, **no** Assign/Resolve/Call-back buttons |
| `/app/settings/safety` | read + write | read + write | **hidden** | **hidden** |
| `/app/settings/api-keys`, `/integrations` | read + write | read + write | **hidden** | **hidden** |
| `/app/billing` | full org plan + usage | read-only org view | **"My credits" placeholder/real number**, no org totals | same as operator |
| Team pane: change a member's role / remove | can act on anyone ranked below them | same, one rank narrower | **hidden** | **hidden** |
| Team pane: "Credits/day" field per member | editable | editable | **read-only display, no input** | **read-only display, no input** |

**How to verify a "hidden" row is really enforced, not just hidden by CSS:** open
DevTools → Network tab, then try the underlying request directly - e.g. as an operator,
open `/app/settings/safety` by typing the URL directly rather than clicking a nav link.
The page should redirect or show nothing meaningful, **and** the underlying
`PATCH /api/v1/safety` should 403 if you try it via the Console:

```js
fetch('/api/v1/safety', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: '{}' })
  .then(r => console.log(r.status))
```

A `403` confirms the backend enforces it independently of the UI hiding the button - the
important guarantee. A `200` with the UI hidden would mean the restriction is
cosmetic only, which is the actual bug class to watch for here.

**Data-silo check (Phase 1 - the load-bearing one):** as an operator, create a campaign
and start a run. Sign in as a *second* operator in the same org and confirm they cannot
see the first operator's campaign in `/app/campaigns`'s main list, nor the run in
`/app/runs` - it should be completely absent, not shown-but-disabled. Then sign in as
the owner/admin/viewer and confirm they see **both** operators' campaigns and runs, each
correctly attributed ("by {name}").

---

## Part 3 — Sharing system walkthrough (Phase 4)

This needs two operator accounts (or one operator + the resource's actual owner, if you
used a different role) in the same org.

### 3a. Campaign sharing

1. As **Operator A**, create a campaign (`/app/campaigns/new`) - anything, e.g. a copy of
   a built-in template with a new name.
2. As **Operator B** (different account, same org), go to `/app/campaigns` and scroll to
   the **"Team campaigns"** section below your own list. Confirm Operator A's campaign
   appears there with **just its name and Operator A's name** - no goal template, no
   extraction fields, nothing else. Confirm your **own** campaigns never appear in this
   list (it's the rest of the org, not everything).
3. Click **"Request access"** on that row, optionally add a short message, submit.
4. Still as Operator B: the row should now say **"Requested"** instead of showing the
   button again. Refresh the page - it should still say "Requested" (this is a real
   pending row, not local UI state).
5. Sign back in as **Operator A**. Go to **Organisation → Sharing**
   (`/app/organisation?tab=sharing`). Under **"Waiting on you"**, you should see Operator
   B's request with **Approve** / **Reject** buttons.
6. Click **Approve**. It should disappear from "Waiting on you" immediately.
7. Sign back in as **Operator B**. Their own `/app/campaigns` list should now include a
   **new, independent copy** of the campaign (named "... (shared)" by default), owned by
   Operator B. Confirm editing this copy does **not** change Operator A's original -
   they're two separate rows from this point on.
8. Under **Organisation → Sharing → "Requests you've sent"**, Operator B's request should
   now show **status: approved**.

**Try rejecting too:** repeat from step 3 with a second campaign, but click **Reject**
instead. Confirm the campaign does *not* appear in Operator B's list afterward, and the
request shows **status: rejected** under "Requests you've sent."

**Try requesting twice:** click "Request access" on the same still-pending row a second
time (e.g. via two browser tabs) - the second attempt should fail with **"You already
have a pending request for this"** (a `409`), not create a duplicate. Once the first
request is decided (approved or rejected), requesting that same campaign again should
work fine - the block is "one *pending* request," not "one request ever."

### 3b. Escalation sharing

Needs an escalation to exist first - the fastest way is to run a campaign against a
number your safety guards will mark unreachable (or wait for a real call to escalate).
Alternatively, check `/app/escalations` for any existing open item from earlier testing.

1. As the escalation's owner (whoever started that run), leave it open/unassigned.
2. As a **different** operator, go to `/app/escalations` and find the **"Team
   escalations"** section. Confirm it shows contact name + campaign + owner, for **open**
   escalations only - resolve one first and confirm it disappears from this directory
   immediately.
3. Click **"Request to help"** on an open row, submit.
4. As the owner, approve it from **Organisation → Sharing**. Confirm the escalation is
   now **reassigned** to the requester (`assigned_to`) in `/app/escalations` - not
   cloned; there's still exactly one row, just a new owner.

### 3c. Live sync check

Open **Organisation → Sharing** in two browser windows as the same owner account (or
owner + admin). In one window, have a request submitted (from a third window/account) -
the "Waiting on you" list in **both** open windows should update within a second or two
**without a manual refresh**. This is Supabase Realtime, not polling - if it takes more
than a few seconds, check the DevTools Network tab's WS (WebSocket) filter for a
connection to `*.supabase.co/realtime/v1/websocket` and confirm it's open (status
`101 Switching Protocols`), not erroring.

**What to check in DevTools if a sharing step misbehaves:** Network tab → filter
`share-requests` → check the request/response for the exact step that failed. A `403` on
approve/reject means you're testing as someone who isn't the resource's real owner -
that's correct behaviour, not a bug. A `404` on approve typically means the `X-Org-Id`
request header doesn't match the organisation the request actually belongs to - check
Request Headers on the failing call if you belong to more than one organisation.

---

## Part 4 — Credits system walkthrough

1. As **owner or admin**, go to **Organisation → Team**. Each member row has a
   **"Credits/day"** field - set Operator A's to something small, e.g. `3`.
2. As **Operator A**, go to **Billing** in the sidebar. You should see **"My credits"**
   showing `0 of 3 calls used` (or whatever you set), with a progress bar - not the org's
   overall plan/usage, which stays hidden for this role.
3. **1 credit = 1 *connected* call, not 1 attempt** (`ISSUES.md` iteration 30) - `used`
   only goes up once the callee actually answers. Start a run as Operator A against 1–2
   numbers from the reserved range (`+1 555 0100`–`0199`, see the warning at the top) -
   these never connect to a real phone, by design. After the run finishes, refresh
   Billing and confirm **`used` is still `0`** - the attempt itself doesn't
   spend a credit, only a connected conversation does. This is the correct result, not a
   bug; it's also the safest way to test the "non-connect doesn't spend" half of the rule
   without risking a real dial.
4. As the **owner/admin**, open **Organisation** (dashboard, or the Team pane) and check
   the **Team performance** panel / member row - it should show the same
   `credits_used_today` number for Operator A that Operator A themselves saw (both `0`,
   per step 3), confirming both views read the same live, connected-only source.
5. **Confirm the ceiling actually blocks dialling** - set Operator A's allocation to `0`
   and have them start a run against any contact. The outcome should show as **Blocked**
   with a reason mentioning "daily credit limit reached", and it appears instantly - a
   ceiling of `0` denies before any real number is dialled at all, so this check is 100%
   safe to run regardless of what number you use.
6. **Fully confirming the positive path** - a *connected* call correctly counting toward
   the ceiling and eventually blocking the next one - needs a real, live-answered call,
   which this guide deliberately does not instruct you to place against an arbitrary
   number (CLAUDE.md's non-negotiable: every run dials for real, and sample data must
   stay within the reserved range). That path is already covered by the automated test
   suite instead - `test_orchestrator.py`'s `test_credit_ceiling_blocks_the_next_contact_
   once_a_call_connects` and `test_a_call_that_never_connects_does_not_spend_a_credit`.
7. As a **viewer**, confirm Billing shows the same "My credits" personal view
   as an operator (not the org-wide plan), and that nobody except owner/admin can edit
   any "Credits/day" field.

**What to check in DevTools if a number looks wrong:** Network tab → find
`/api/v1/organisations/me/members/me/credits` (self view) or
`/api/v1/organisations/me/team-performance` (admin/owner view) → Response tab. Compare
`used_today` in both - they're independent SQL queries against the same tables and
should always agree. If they disagree, note the exact numbers and timestamp; that's a
real inconsistency worth reporting, not a UI rendering issue (there's no client-side math
involved beyond formatting).

---

## Appendix — reading the Network tab for this app, in general

Every meaningful action in this product is one fetch call - there's no hidden client
state to reason about beyond what's in `lib/api.ts`. When something on screen looks
wrong:

1. Open DevTools → **Network** tab, filter by `Fetch/XHR`, reproduce the action.
2. Click the request. **Headers** tab: confirm `Authorization: Bearer …` is present, and
   if you belong to more than one organisation, confirm `X-Org-Id` matches the
   organisation you think you're testing - a stale or missing `X-Org-Id` silently
   targets the wrong org rather than erroring, which looks exactly like "the data isn't
   there" from the UI.
3. **Response** tab: the JSON is the actual source of truth for what the backend decided
   - compare it against the exact shapes in `SYSTEM.md` §5 if something looks off,
     rather than guessing from the rendered UI.
4. **Console** tab: any uncaught error here means a real frontend bug (a `TypeError`, a
   failed assertion) - these are always worth reporting, since this codebase has no
   error-swallowing `catch {}` blocks by convention.
5. For anything Realtime-related (Sharing tab, Escalations), the **Network → WS** filter
   shows the live Supabase websocket - a closed/erroring connection explains "it didn't
   update live" far better than assuming the feature is broken.

## Appendix — known quirks that are not bugs (check here before reporting)

- **First accept-invite attempt can 403; the "Join {org}" retry button fixes it
  immediately.** A pre-existing timing race, not something this round introduced or
  fixed - documented, low-severity, has a working mitigation already in the UI.
- **Per-teammate credits only count *connected* calls, not attempts** - a run against
  reserved-range numbers (they never connect) correctly leaves `used` at `0`, even after
  several calls. That's the rule working as designed, not a stuck counter. The org-wide
  daily budget (`GET/PATCH /api/v1/safety`) still applies on top regardless of any
  individual teammate's allocation.
- **Calling-window / retry-policy fields in the campaign editor are `localStorage` only**
  and not enforced anywhere server-side, despite looking like real settings.
- **`ice` (the fifth lamp colour) never appears anywhere** - it's reserved, not a bug.
- A `resource_name` of `null` on a **pending, self-sent** share request (under "Requests
  you've sent," before it's decided) is correct, not a missing-data bug - your own RLS
  scope genuinely can't see a resource you don't own yet. It fills in once the request
  is approved.

For anything not listed above that doesn't match this guide, check `ISSUES.md` first (it
may already be a known, tracked issue) before treating it as new.
