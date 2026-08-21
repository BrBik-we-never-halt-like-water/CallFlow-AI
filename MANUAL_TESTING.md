# Manual testing guide — roles, sharing, credits, and billing

A click-through script for verifying what is built: the four-role permission matrix,
peer-to-peer campaign/escalation sharing, per-teammate usage-credit shares, and the
plan/entitlement/usage-credit layer. Parts 1–5 are all checkable in a browser, with what
to look at in DevTools when a step doesn't match what's expected. **Part 6 is the
exception** — it covers placing a real call end to end, which cannot be done through the
product today, and it lists exactly what blocks it so nobody books an afternoon for it
first.

**Part 4** is a teammate's own *share* of the organisation's usage credit (money, set in
Organisation → Team's "₹/month" field); **Part 5** is the organisation-wide usage credit
itself (the same money, spent per connected second). They are the same rail, checked at
two different scopes - a naming collision used to exist here between this and a separate,
now-retired daily call-count allowance (`ISSUES.md` #146); it no longer does.

**Companion docs:** [`TEAM_COLLABORATION_ROADMAP.md`](TEAM_COLLABORATION_ROADMAP.md) (why
each phase is shaped the way it is) · [`SYSTEM.md`](SYSTEM.md) (exact API shapes) ·
[`docs/BILLING.md`](docs/BILLING.md) and
[`docs/PRICING_DECISIONS.md`](docs/PRICING_DECISIONS.md) (what the plans mean and why the
rates are what they are) · [`ISSUES.md`](ISSUES.md) (known quirks - check there before
reporting something as new).

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

## Part 4 — Per-teammate usage-credit share walkthrough

**Superseded, kept as a marker:** this part used to walk through a per-teammate *daily
call allowance* ("Credits/day," a count of connected calls). That concept is retired
(`ISSUES.md` #146) - the org-wide daily budget is now a uniform runaway safety rail on
every plan rather than a packaging number, and a plan's real flow limit is its usage
credit. The one per-teammate ceiling left is a share of that usage credit, in money -
this walkthrough now covers that instead.

1. As **owner or admin**, go to **Organisation → Team**. Each member row has a
   **"₹/month"** field - set Operator A's to something small, e.g. `50`.
2. **Try setting it above the plan's own grant** - e.g. `9999` on a Starter org (₹850 a
   period). Expect a **400**, surfaced as a toast naming the actual ceiling ("Starter
   grants only ₹850 of usage credit a period..."), not a silent clamp or a generic
   validation error (`ISSUES.md` #147).
3. As **Operator A**, go to **Billing** in the sidebar. You should see **"My credits"**
   showing `₹0 / ₹50` (or whatever you set) - not the org's overall plan/usage, which
   stays hidden for this role.
4. As the **owner/admin**, open the **dashboard**'s per-teammate table and check it shows
   the same `₹0 / ₹50` for Operator A that Operator A themselves saw, confirming both
   views read the same `credit_service.member_credit_cap_status` call.
5. **Confirm the cap actually blocks a run** - set Operator A's share to `0` and have them
   start a run. It should refuse with a reason naming their usage-credit share, before any
   number is dialled - safe to test regardless of which number you use, since the run
   never starts.
6. **Confirm it's independent of the org-wide balance** - a teammate with no share set at
   all is not gated by this check; only the organisation-wide balance applies to them
   (see Part 5 for exercising that balance directly).
7. As a **viewer**, confirm Billing shows the same "My credits" personal view as an
   operator, and that nobody except owner/admin can edit the "₹/month" field.

**What to check in DevTools if a number looks wrong:** Network tab → find
`/api/v1/organisations/me/members/me/credits` (self view) or
`/api/v1/organisations/me/team-performance` (admin/owner view) → Response tab. Compare
`credit_cap_paise`/`credit_spent_paise` in both - they should always agree. If they
disagree, note the exact numbers and timestamp; that's a real inconsistency worth
reporting, not a UI rendering issue (there's no client-side math involved beyond
formatting).

---

## Part 5 — Billing, entitlements and usage credit

**All of this works today.** Nothing here needs a phone call, a carrier, or the
voice worker — which is what makes it the part worth doing first.

### 5.1 A plan gate you can see before it bites

1. On **Free**, go to **Agents**. With one agent created, the Create button is
   *replaced* by **Upgrade plan**, reading "Free includes 1 agent." A greyed-out
   button would say the product is broken; naming the plan's own number says what
   actually happened.
2. Check the other three surfaces refuse the same way, with a reason and no dead
   button: the **org switcher** ("Upgrade to create another"), **New
   organisation**, and the **invite dialog**.
3. Repeat as a **non-owner**. Expect the reason and *no* button — only an owner
   holds `billing:write`, and a button that 403s is worse than none.
4. Now bypass the interface and `POST /api/v1/voice-agents` directly. It answers
   **402 Payment Required**, not 403. That distinction is why the interface can
   offer an upgrade instead of a dead end.

### 5.2 Locked agents — the downgrade case

Needs an organisation over its limit. Quickest route: create 3 agents on a paid
plan, then set the org back to `free` in the database.

1. **Agents** shows two cards blurred behind a padlock, "Locked by your plan", and
   **Make active** / **Upgrade**.
2. Press **Make active** on a locked one. It activates and the previously active
   one locks — the toast says so, because on a one-agent plan that swap is
   unavoidable and discovering it later is worse.
3. **Tab through the page.** A locked card must be entirely unreachable: it is
   `inert`, not merely blurred. If tabbing lands on a link inside a blurred card
   that is a bug — blur is a visual effect and does not stop a keyboard.
4. Confirm nothing was destroyed: the agent count is unchanged and every agent is
   still editable.

### 5.3 Credit: grant, spend, replay

1. On Free with an empty ledger, open **Billing**. Expect **₹100 left of ₹100**,
   0 used, and "about 66 minutes at your current rate of ₹1.50 a minute". The grant
   is lazy and lands on first read, so needing one reload is expected rather than a
   sign of failure.
2. **See statement** lists one `Credit added` row and nothing else.
3. Drive a settle by hand — the only way to exercise spending until calls work.
   You need a **real** `run_id`: start a run (every contact is skipped, but the run
   row is created and the response returns its id), then

       curl -X POST "http://127.0.0.1:8002/internal/v1/runs/$RUN_ID/complete" \
         -H "x-callflow-internal-key: $CALLFLOW_INTERNAL_API_SECRET" \
         -H "content-type: application/json" \
         -d '{"contact_name":"Asha","phone_masked":"+1 555 0142","status":"COMPLETED","duration_seconds":245}'

   The balance drops **₹6.13** — 245 seconds at ₹1.50/min, prorated by the second
   rather than rounded up to a whole minute. A 404 here means either the internal
   secret is unset/wrong or the run id does not resolve; both answer 404 on purpose,
   so a caller without the secret learns nothing about which runs exist.
4. **Send that request again, unchanged.** The balance must not move. `call_key` is
   `run_id:contact_name:phone_masked`, so keep all three identical — that is the
   `dedupe_key` guarantee, and it is what makes a retrying worker safe.
5. Spend to zero, then start a run. Refused before anything dials, with *"Free's
   usage credit is spent. Top up in Billing, or wait for the next period to
   start."* Then press **Top up** — it 404s until `DODO_PRODUCT_CREDIT_PACK` is set,
   which is honest rather than a button that cannot work.
6. Set the balance unreadable (stop Postgres mid-request, or revoke the grant) and
   start a run. It must **refuse**, not proceed. A credit check that cannot complete
   has to deny — otherwise an outage is free calling.

### 5.4 Subscription, through the real gateway

Needs `DODO_API_KEY` and `DODO_WEBHOOK_KEY` (both already set) plus a public tunnel:
`cloudflared tunnel --url http://127.0.0.1:8002`, then point Dodo's webhook at
`<tunnel>/api/v1/webhooks/dodo`.

1. **Billing → Upgrade to Starter**, complete the Dodo test checkout.
2. In the API log expect `subscription.active` applied, then `payment.succeeded`
   recorded. In the database: `org_subscriptions.status = 'active'`,
   `organisations.plan_id = 'starter'`, one `payments` row, and a `credit_ledger`
   grant of **85000** paise.
3. **Replay the same delivery** from Dodo's dashboard. No second payment row and no
   second grant — the payment is keyed on the gateway's id, the grant on the
   subscription period.
4. Kill the tunnel, buy again, restore it, then press **Sync with provider**. Plan
   and credit catch up. That path exists because a webhook can be missed, and it is
   the difference between a recoverable gap and a support ticket.
5. **Receipt**: a settled payment offers a **Receipt** button that opens the
   gateway's own invoice PDF. A failed one shows `-`, not a link that 404s.

---

## Part 6 — A real call, end to end

**Read this before booking time for it.** A call cannot currently be placed through
the product, and the reason is a code gap rather than configuration.

### 6.1 What blocks it today

| # | blocker | what it needs |
|---|---|---|
| 1 | **`POST /api/v1/runs` never passes `trunk_id` or `voice_agent`** to `CampaignRunner`, so every contact is skipped with "no connected number to call from" (`campaign_runner.py:297`). It is the only `CampaignRunner(...)` construction in the app. | a code fix |
| 2 | `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` are empty | a LiveKit project |
| 3 | no carrier credentials and no provisioned number — `provider_credentials` and `telephony_provisioning` are both empty | a Twilio/Plivo account and a number |
| 4 | `livekit-agents` is not installed, so the worker cannot start | `pip install -e "apps/voice-runtime[deepgram,elevenlabs,openai,silero]"` |
| 5 | `CALLFLOW_INTERNAL_API_SECRET` is empty, so the worker's completion callback is refused with 404 — deliberately fails closed | set it in `.env` |

Only #1 is engineering work; the rest is accounts and setup.

**The one path that dials today** is `scripts/telephony_check.py`, a manual
one-contact CLI check that supplies the trunk and agent itself — which is exactly
what the run route omits.

### 6.2 Once unblocked, the walkthrough

1. **Integrations** → connect a carrier, provision a number, confirm
   `telephony_provisioning` reaches a verified state.
2. Connect **STT / LLM / TTS** keys. There is no CallFlow-owned fallback, so a call
   cannot run without the organisation's own keys.
3. **Agents** → build one on those three legs plus the connected number. The
   builder's cost bar shows what a minute will cost before you commit to it.
4. Start the worker: `python -m app.worker` from `apps/voice-runtime`.
5. **Campaigns** → write a goal and a result schema. **Runs → New** → add exactly
   *one* contact: your own phone.
   - Keep `CALLFLOW_ALLOWLIST` set to that number. It is the guard that stops a test
     reaching a stranger, and it is checked per dial rather than once per run.
6. Answer, talk, hang up.
7. Then check, in order:
   - `call_outcomes` has one row with a real `duration_seconds`
   - `credit_ledger` has a **spend** for that call, at the platform-fee rate
   - the spend equals `duration × rate`, prorated by the second
   - the run closed — `runs.finished_at` is set
   - **Billing** shows the reduced balance and the call in the statement

   **Expect no `hold` row.** `reserve_for_call` is written and tested but has no
   caller, so nothing reserves credit before dialling — the settle resolves the rate
   itself and charges correctly either way. It shares a root cause with blocker #1:
   the dial path that would place the hold is the one that cannot dial. Until it is
   wired, a run can overspend its balance within a single batch, because the balance
   is only checked once at run start.

### 6.3 Refusals worth doing deliberately

Each of these is a guard that must hold on the very first call an organisation ever
makes, which is exactly when nobody is watching.

- a number **not on the allowlist** → refused, and the reason names the allowlist
- a **suppressed** number → refused per dial, not merely hidden in the interface
- **credit at zero** → refused before dialling
- a **locked agent** → should refuse. *Not yet wired*: `check_agent_usable` is
  written and tested but has no caller, because nothing resolves a campaign's
  agent. Expect this to pass wrongly until blocker #1 is fixed.
- **kill the worker mid-call** → the call's in-flight row is swept and the run does
  not hang. The credit half of that sweep (`sweep_stale_holds`) has nothing to
  release yet, for the reason in 6.2 step 7 — so verify the run closes, not that
  credit came back.

### 6.4 What to watch in the logs

The worker POSTs to `/internal/v1/runs/{run_id}/complete`. If a call happens and
nothing appears in `call_outcomes`, check that callback first: a 404 there means the
internal secret is unset or mismatched, and it fails closed on purpose rather than
accepting an anonymous write.

Also worth knowing: an unhandled 500 now reaches the browser as a JSON 500 with CORS
headers. Before this iteration it arrived as `TypeError: Failed to fetch`, which is
indistinguishable from the API being down — one real bug was misdiagnosed as a
network fault because of it.

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
- **The per-teammate usage-credit share is independent of the org-wide daily budget** -
  a teammate can be well under their own share and still have a run refused by the
  organisation-wide balance, or the reverse. The org-wide daily budget
  (`GET/PATCH /api/v1/safety`) is a separate, uniform runaway safety rail, unrelated to
  either.
- **Calling-window / retry-policy fields in the campaign editor are `localStorage` only**
  and not enforced anywhere server-side, despite looking like real settings.
- **`ice` (the fifth lamp colour) never appears anywhere** - it's reserved, not a bug.
- A `resource_name` of `null` on a **pending, self-sent** share request (under "Requests
  you've sent," before it's decided) is correct, not a missing-data bug - your own RLS
  scope genuinely can't see a resource you don't own yet. It fills in once the request
  is approved.

- **The usage-credit meter is absent, not zeroed, before the first grant lands.** The
  grant for an unsubscribed plan is lazy — it is written on the first read of Billing or
  the first run — so a brand-new org may need one reload before the meter appears. A
  meter reading "0 of 0" would be a bug; no meter at all is the intended state.
- **`credit_ledger` contains no `hold` rows.** Nothing reserves credit before dialling
  yet; the settle resolves the rate and charges the real duration. See Part 6.2.
- **Every rate is the platform fee alone (₹1.50/min).** The nine per-leg tier add-ons are
  seeded and tested but unreachable: every key a call uses comes from the organisation's
  own `ai_provider_credentials`, so every pipeline is bring-your-own by necessity. A
  builder cost bar showing only the platform fee is correct.
- **"Calls per day" is no longer a plan difference.** All four plans carry the same 500,
  which is a runaway-run safety rail rather than a packaging lever — the plan's real flow
  limit is its usage credit.

For anything not listed above that doesn't match this guide, check `ISSUES.md` first (it
may already be a known, tracked issue) before treating it as new.
