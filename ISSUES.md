# Issues — design audit, `het/design-polish-v2`

This branch was cut from `133bf2a` (pre-restructure) and then had the complete
frontend brought onto it, so it carries no `ISSUES.md` history from `main`. The
canonical numbered log (#1–#24) lives on `het/design-polish`.

To stay merge-safe, findings here are numbered **D1…** rather than continuing that
sequence. Anything below that duplicates an existing numbered issue says so.

Found during the full UI/UX audit of 2026-08-08, which read every file under
`web/app`, `web/components` and `web/lib`. Everything is cited to `file:line`.

**Status of this list: logged, not fixed.** The redesign in progress deliberately
does not touch these — that was a explicit call, so the visual work could land
without entangling it with correctness and copy changes.

---

## Severity

| | Meaning |
|---|---|
| **S1** | States something untrue to a user or regulator, or loses/corrupts data |
| **S2** | Breaks a documented product rule, or blocks a user with no way out |
| **S3** | Real defect, contained blast radius |
| **S4** | Inconsistency or polish |

---

## Index

| # | Sev | Title | Area |
|---|---|---|---|
| [D1](#d1--trust-claims-calling-windows-are-enforced) | S1 | `/trust` claims calling windows are enforced | marketing |
| [D2](#d2--trust-and-docs-claim-the-suppression-list-is-global-and-permanent) | S1 | Suppression list described as global + permanent | marketing + docs |
| [D3](#d3--the-webhooks-page-documents-a-feature-that-does-not-exist) | S1 | Webhooks page documents a non-existent feature | docs |
| [D4](#d4--forgot-password-reports-success-on-almost-every-failure) | S1 | Forgot-password reports success on nearly every failure | auth |
| [D5](#d5--verify-email-claims-an-email-was-sent-in-its-default-state) | S1 | `/verify-email` claims an email was sent | auth |
| [D6](#d6--signup-toasts-success-then-lands-the-user-on-the-login-screen) | S1 | Signup toasts success, then bounces to login | auth |
| [D7](#d7--editing-a-campaign-silently-creates-a-second-one) | S1 | Editing a campaign creates a duplicate | dashboard |
| [D8](#d8--mark-resolved-does-not-persist) | S1 | "Mark resolved" fakes success | dashboard |
| [D9](#d9--the-onboarding-modal-can-trap-a-new-user) | S2 | Onboarding modal can trap a new user | auth |
| [D10](#d10--accept-invite-can-join-as-the-wrong-account) | S2 | Accept-invite can join as the wrong account | auth |
| [D11](#d11--trust-is-linked-as-both-privacy-policy-and-terms-and-is-neither) | S2 | `/trust` linked as Privacy + Terms, is neither | marketing |
| [D12](#d12--lamp-colour-used-for-things-that-are-not-call-state) | S2 | Lamp colour used for non-call-state | auth + marketing |
| [D13](#d13--the-changelog-and-docs-still-describe-removed-features) | S2 | Docs still describe removed features | docs |
| [D14](#d14--desktop-table-rows-cannot-be-operated-from-the-keyboard) | S2 | Desktop table rows are keyboard-inaccessible | dashboard |
| [D15](#d15--two-of-six-dashboard-destinations-have-no-mobile-route) | S2 | Two nav destinations unreachable on mobile | dashboard |
| [D16](#d16--duplicate-docs-entry-breaks-the-mobile-menu) | S3 | Duplicate "Docs" entry breaks the mobile menu | marketing |
| [D17](#d17--the-pricing-sticky-header-never-engages) | S3 | Pricing sticky header never engages | marketing |
| [D18](#d18--safety-settings-asserts-enforcement-from-unsaved-input) | S3 | Safety settings asserts from unsaved input | dashboard |
| [D19](#d19--solutions-has-no-index-page) | S3 | `/solutions` 404s | marketing |
| [D20](#d20--the-404-sends-signed-out-visitors-to-a-login-redirect) | S3 | 404 sends signed-out visitors to login | marketing |
| [D21](#d21--vendor-name-leaks-into-integrations-copy) | S3 | Vendor name leaks into UI copy | dashboard |
| [D22](#d22--dead-css-and-five-competing-surface-treatments) | S4 | Dead CSS + five competing surfaces | design system |
| [D23](#d23--contradictory-authorship-credit) | S4 | Contradictory authorship credit | marketing |

---

## S1 — untrue to a user, or data loss

### D1 — `/trust` claims calling windows are enforced

`web/app/(marketing)/trust/page.tsx:90` states that for India "calling windows
default to 09:00–20:00 IST and **are enforced per campaign**"; `:92` makes the
equivalent claim for the US. `web/app/(marketing)/docs/safety-configuration/page.mdx:21`
lists the calling window as a guard that means "Nothing is dialled outside it",
under an opening line at `:9-11` promising "Every guard here fails closed."

Grepping the backend for window enforcement returns nothing. This is the same
gap as the canonical **#20** on `het/design-polish`, but the trust page raises the
stakes: it is written to be read by a compliance reviewer, so this is a
representation about product behaviour rather than marketing copy.

Also asserted in the dashboard at `web/app/(app)/app/settings/safety/page.tsx:130`,
`web/components/app/campaign-editor.tsx:267-270`, and
`web/components/app/safety-bar.tsx:130-137`.

**Fix.** Either implement the window check in `check_dial_allowed()`, or say
plainly on all six surfaces that it is not yet wired. `NotWiredNotice` is the
existing pattern.

---

### D2 — `/trust` and docs claim the suppression list is global and permanent

`web/app/(marketing)/trust/page.tsx:48-50` says an opt-out is added to a global,
permanent, org-wide suppression list "immediately".
`web/app/(marketing)/docs/triage-rules/page.mdx:54-62` says opt-outs apply to
"every campaign in your organisation, forever".
`web/app/(marketing)/docs/safety-configuration/page.mdx:23` repeats it.

`DESIGN_NOTES.md` §5 records the list as **browser-local** (`lib/suppression.ts`,
`localStorage`) and notes the suppression page itself says so. Two surfaces of
the same product disagree, and the one making the stronger claim is the legal one.

---

### D3 — The webhooks page documents a feature that does not exist

`web/app/(marketing)/docs/webhooks/page.mdx` documents four event types (`:16-21`),
a payload schema (`:28-44`), HMAC signature headers (`:54-57`), 24-hour
exponential-backoff retries (`:65`) and a replayable delivery log (`:69-71`), and
tells the reader at `:12` to configure endpoints in Settings → Integrations.

No outbound webhook system exists in the backend. There is no "not yet available"
marker anywhere on the page, unlike every other unbuilt surface in the product.

---

### D4 — Forgot-password reports success on almost every failure

`web/app/(auth)/forgot-password/page.tsx:35-42` returns early only when the error
message contains the substring `"emails have been sent"` — the rate-limit case.
Every other failure (SMTP unconfigured, provider down, network error) falls
through to `setSent(true)` and the "Reset link sent" toast at `:43-47`. The button
then locks to "Link sent" and the input disables (`:71`, `:75-76`), so there is no
retry path.

Two compounding problems: the match at `:35` is against the *user-facing* string
from `lib/auth/errors.ts:26`, so rewording that message silently disables the
branch; and if `/verify-email`'s claim that this deployment has no mail service is
correct, the whole screen is a fake success state.

---

### D5 — `/verify-email` claims an email was sent, in its default state

`web/app/(auth)/verify-email/page.tsx:15` opens with "We've sent a link to the
address you signed up with." `:30-32` adds expiry and spam advice. The honest
`AuthNotice` at `:35-38` — which says there is no mail service on this deployment
and nothing was sent — only renders *after* the user clicks "Send it again".

The page is also unreachable: grepping `app`, `components`, `lib` and
`middleware.ts` finds zero links to it.

---

### D6 — Signup toasts success, then lands the user on the login screen

`web/app/(auth)/signup/page.tsx:74` fires "Account created" and `:79` does
`router.replace("/app")`, on the assumption stated at `:76-78` that email
confirmation is disabled. When confirmation is on — Supabase's **default**, and a
state `web/lib/auth/errors.ts:18-19` explicitly has an error string for — no
session is returned, so `web/lib/supabase/middleware.ts:49-56` redirects to
`/login?next=/app`.

The user sees a success toast and arrives at a login form with no explanation.
There is no `SUPABASE_SETUP.md` on this branch telling a deployer to turn
confirmation off.

**Fix.** Branch on whether a session came back; route to `/verify-email` when it
did not.

---

### D7 — Editing a campaign silently creates a second one

`web/components/app/campaign-editor.tsx:167` always calls `api.createCampaign`,
and `web/lib/api.ts` exposes no update method — only `createCampaign` (`:308`) and
`deleteCampaign` (`:313`). Saving from `/app/campaigns/[id]` therefore POSTs a new
campaign, toasts "Campaign saved" (`campaign-editor.tsx:176`), and routes to the
list where the user now has two.

Fake success plus silent data duplication. The most damaging item in this list.

---

### D8 — "Mark resolved" does not persist

`web/components/app/escalation-card.tsx:133-138` sets local component state and
toasts "Marked resolved". Nothing is written; the nav badge fed by
`web/components/layout/app-shell.tsx:47` still counts it and a refresh restores it.

Notably the two neighbouring buttons are honest about being unwired
(`escalation-card.tsx:108`, `:121`) — this one is not.

---

## S2 — breaks a documented rule, or blocks the user

### D9 — The onboarding modal can trap a new user

`web/components/app/onboarding-gate.tsx:38` sets `onOpenChange={() => {}}` with
`dismissible={false}` at `:92`. If `api.completeOnboarding` (`:74`) fails, the
catch at `:80-88` toasts and the modal remains, with no close, no skip and no
sign-out. `needsOrgSetup` derives from server state (`:32`), so reloading does not
help. Step two correctly offers "Skip for now" (`:176`); step one offers nothing.

---

### D10 — Accept-invite can join as the wrong account

`web/app/(auth)/accept-invite/[token]/page.tsx:126` derives `alreadySignedIn` from
session presence alone and never compares `session.profile.email` against
`preview.email`. Someone signed in as one user, clicking an invite addressed to
another, is shown "Join {org}" (`:166-168`) and joins as the wrong account.

The invite preview already carries `email` (used at `:85`, `:89`), so the check is
available and simply not made. There is no "not you? sign out" affordance.

---

### D11 — `/trust` is linked as both privacy policy and terms, and is neither

`web/components/layout/site-footer.tsx:120-121`, `web/app/(auth)/layout.tsx:31-32`,
and `web/app/(auth)/signup/page.tsx:147,151` all link "Privacy" and "Terms" to
`/trust`. The signup links are the ones the user is asked to *agree* to. `/trust`
contains neither document.

`web/app/(marketing)/trust/page.tsx:40` and `:68` also route the reader to
"Settings → Compliance" for consent configuration and deletion requests; no such
screen exists (`web/app/(app)/app/settings/` has api-keys, billing, integrations,
safety, team).

---

### D12 — Lamp colour used for things that are not call state

`DESIGN_NOTES.md` §2 permits exactly three exceptions. Two more exist:

- `web/components/ui/password-strength.tsx:34` maps `flare`/`brass`/`brass`/`jade`
  to password strength, plus `text-lamp-jade-text` at `:80`. Renders on three auth
  pages.
- `web/components/layout/auth-card.tsx:26` renders `<Rule withLamps />` on every
  auth page, while `web/components/ui/rule.tsx:10-11` documents that prop as "not
  used on pages with no call state: if there is no call, there is no lamp." Two
  primitives in one system documenting opposite rules for the same prop.

Also `web/app/(marketing)/maintenance/page.tsx:14-18` repurposes `ice` as "Paused".
`ice` is documented as reserved and unassigned, and the lamp-state table at
`web/app/(marketing)/docs/triage-rules/page.mdx:43-49` was not updated — it also
lists a non-existent state name `"dim"` where the token is `off`.

---

### D13 — The changelog and docs still describe removed features

- `web/app/(marketing)/docs/triage-rules/page.mdx:11` — "It runs on every call,
  live or dry". `dry_run` was deliberately removed.
- `web/app/(marketing)/docs/changelog/page.mdx:29-31` — lists "simulated" as a
  current lamp state, in present tense.
- `:33-35` — "The dry-run switch confirms before going live" in present tense,
  describing a control deleted in the entry above it.
- `:41-42` — "Two surface modes… both available everywhere and switchable."
  `DESIGN_NOTES.md` §1 records `lib/surface.ts`, `SurfaceProvider` and
  `SurfaceToggle` as deleted; no removal entry was written.

---

### D14 — Desktop table rows cannot be operated from the keyboard

`web/components/app/data-table.tsx:330-341` puts `onClick` on a `<tr>` with
`cursor-pointer` and no `tabIndex`, `role` or key handler.
`web/app/(app)/app/runs/[id]/page.tsx:222-227` repeats it. The mobile path at
`data-table.tsx:419-427` already does it correctly with a real `<button>`.

Opening a transcript — the core action on the run detail page — is impossible from
the keyboard on desktop.

---

### D15 — Two of six dashboard destinations have no mobile route

`web/components/layout/app-nav.tsx:54` ships four tab-bar destinations; the sidebar
is `hidden md:flex` (`:80`). Settings survives via the user menu
(`web/components/layout/user-menu.tsx:82`). **Contacts has no mobile route at all**
— and the suppression list lives inside it as tab 2
(`web/app/(app)/app/contacts/page.tsx:109`).

---

## S3 — contained defects

### D16 — Duplicate "Docs" entry breaks the mobile menu

`web/components/layout/site-header.tsx:17` and `:46` both define
`{ label: "Docs", href: "/docs" }`. `MobileNav` concatenates the lists at `:261-265`
and keys them `` `${link.href}-${link.label}` `` at `:296`, so both produce
`"/docs-Docs"` — a React duplicate-key warning and "Docs" rendered twice.

The same flattening drops all grouping and hints (`:264` strips them explicitly,
`:300` renders only the label), so mobile gets twelve undifferentiated links where
desktop gets grouped menus with context.

---

### D17 — The pricing sticky header never engages

`web/components/marketing/pricing-table.tsx:232` sets `sticky top-0` on `<thead>`,
but `:226` wraps the table in `overflow-x-auto`, making that div the scroll
container. It has no `max-height` and never scrolls vertically, so the header
sticks to something that never moves. Both `:218` and `web/lib/pricing.ts:172`
advertise "sticky plan headers".

Related: `:227` sets `min-w-3xl`, and the `<th scope="row">` at `:264` is not
sticky — scrolling right to reach the Scale column loses the feature name across
22 rows.

---

### D18 — Safety settings asserts enforcement from unsaved input

All three footers in `web/app/(app)/app/settings/safety/page.tsx` call `notSaved()`
(`:67`, `:91`, `:132`), which toasts that values come from the environment
(`:39-45`). But the `effect` copy recomputes from local state: typing `999` into
the ceiling makes `:89` assert "A run stops after 999 real calls even if the list
is longer" — a claim about enforcement derived from a value the server never
received.

`web/app/(app)/app/settings/billing/page.tsx:78-82` handles the identical
situation honestly with `NotWiredNotice`.

---

### D19 — `/solutions` has no index page

`web/app/(marketing)/solutions/` contains only `[vertical]/`. The header mega-menu
(`site-header.tsx:21-42`) and footer column (`site-footer.tsx:16-24`) list the four
verticals individually, and the mega-menu trigger is a `<button>` with no `href`
(`:199-211`) — so there is no "all solutions" destination on any device, and the
obvious URL 404s.

---

### D20 — The 404 sends signed-out visitors to a login redirect

`web/app/not-found.tsx` makes "Open dashboard" (`/app`) the primary action. For a
signed-out marketing visitor — most 404s, including anyone trying `/solutions` —
middleware bounces that to `/login?next=/app`. "Back to home" should be primary.
The page also renders a bare logo instead of `SiteHeader`, and no footer.

---

### D21 — Vendor name leaks into integrations copy

`web/app/(app)/app/settings/integrations/page.tsx:105` — "instead of CALL-E's
shared numbers." `DESIGN_NOTES.md` §9 states no vendor is named in any UI copy;
this is the only occurrence in `web/` source.

---

## S4 — inconsistency

### D22 — Dead CSS and five competing surface treatments

`web/app/globals.css` defines five surface treatments. The dashboard uses exactly
one (`.panel-raised`, via `Panel`); `.surface-flow`, `.card-flow` and `.pool` are
marketing-only; `.plan-featured` (`:346`) is referenced only in a comment.
`.seam-x` (`:377`), `.seam-y` (`:384`) and `.wave-field` (`:423`) have **no source
usages anywhere**.

Meanwhile several dashboard components hand-roll their own panel rather than using
`Panel`, at a different radius and border opacity: `data-table.tsx:382,388,411,423`,
`safety-bar.tsx:36`, `contact-grid.tsx:184`, `field.tsx:134`,
`transcript-view.tsx:142`. There are four separate idioms for a hairline divider,
and `border-l-2` appears in four colours, two carrying state meaning and two
decorative.

*Partly addressed by the in-progress redesign, which collapses these to one Card
with three levels and deletes the unused classes.*

---

### D23 — Contradictory authorship credit

`web/components/layout/site-footer.tsx:141-151` credits **BrBik** on every page.
`web/app/(marketing)/about/page.tsx:60-68` credits **mohdcodes**, and that page's
docstring (`:13-20`) says the credit was moved out of the footer onto this page
precisely so it appears once. Both now exist, naming different parties.

---

## Also worth noting

- `web/lib/hooks/use-session.ts:76` calls `fetch()` directly, outside
  `lib/api.ts` — forbidden by `CLAUDE.md`'s "Where things must NOT go" table.
- `web/app/(marketing)/about/page.tsx:107,111,115` list three support addresses as
  plain text, none clickable; a fourth (`hello@callflow.ai`) appears only at
  `web/app/(marketing)/demo/demo-form.tsx:81`.
- `web/app/(marketing)/status/status-board.tsx:117-122` hard-codes the Dashboard
  row to `jade`/"Serving", so it reports healthy during a total API outage.
- `/maintenance` is orphaned (no links, no middleware) and renders inside the
  marketing layout, so a page announcing downtime ships with a "Start free" header.
- The pricing page renders roughly 17 TODO chips, including two on the **Free**
  plan whose commercial terms are settled. Deliberate per `DESIGN_NOTES.md` §10,
  noted here only because it gates shipping the page.
