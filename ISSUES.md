# Issues and bugs

A living log. Every audit or iteration appends findings here; nothing is deleted, only
re-statused, so we keep the history of what was wrong and when we knew.

**Related:** [`SYSTEM.md`](SYSTEM.md) (as-built reference) · `FEATURES.md` (target state -
**referenced by `F<n>` throughout this file and `SYSTEM.md`, but the file itself doesn't
exist in this repo**; `SYSTEM.md` §12 is the closest real gap map until it's written) ·
[`apps/web/DESIGN_NOTES.md`](apps/web/DESIGN_NOTES.md) (frontend decisions)

## Severity

|        | Meaning                                                                                                                    |
| ------ | -------------------------------------------------------------------------------------------------------------------------- |
| **S1** | Breaks a product guarantee, loses data, or exposes one tenant's data to another. Fix before shipping to a paying customer. |
| **S2** | A feature is broken or actively misleading in normal use.                                                                  |
| **S3** | Wrong in an edge case, or misleads a developer rather than a user.                                                         |
| **S4** | Cosmetic, naming, or tidiness.                                                                                             |

## Status

`OPEN` · `IN PROGRESS` · `FIXED` (with the commit) · `WONTFIX` (with the reason) ·
`SUPERSEDED` (folded into a larger change)

---

## Open issues

| ID                                                                                                                                | Sev | Title                                                                                                                 | Area           | Found | Status           |
| --------------------------------------------------------------------------------------------------------------------------------- | --- | --------------------------------------------------------------------------------------------------------------------- | -------------- | ----- | ---------------- |
| [#1](#1--no-persistence-anywhere)                                                                                                 | S1  | No persistence anywhere                                                                                               | backend        | it-1  | **FIXED**        |
| [#2](#2--user-campaigns-are-global-and-ephemeral)                                                                                 | S1  | User campaigns are global and ephemeral                                                                               | backend        | it-1  | **FIXED**        |
| [#3](#3--suppression-list-is-never-enforced)                                                                                      | S1  | Suppression list is never enforced                                                                                    | backend + web  | it-1  | **FIXED**        |
| [#4](#4--calloutcomerun_id-holds-the-provider-call-id)                                                                            | S1  | `CallOutcome.run_id` holds the provider call id                                                                       | backend        | it-1  | **FIXED**        |
| [#5](#5--rate-limits-and-daily-budget-are-per-process-and-reset-on-restart)                                                       | S2  | Rate limits reset on restart, not shared                                                                              | backend        | it-1  | **PARTLY FIXED** |
| [#6](#6--three-high-severity-npm-advisories)                                                                                      | S2  | Three high-severity npm advisories                                                                                    | web            | it-1  | OPEN             |
| [#7](#7--escalation-resolution-is-component-state)                                                                                | S3  | Escalation resolution is component state                                                                              | web            | it-1  | **PARTLY FIXED** |
| [#8](#8--stats-mixes-denominators)                                                                                                | S3  | `stats` mixes denominators                                                                                            | backend        | it-1  | OPEN             |
| [#9](#9--renderyaml-contradicts-the-real-deployment)                                                                              | S3  | `render.yaml` contradicts the real deployment                                                                         | infra          | it-1  | **FIXED**        |
| [#10](#10--no-frontend-tests)                                                                                                     | S3  | No frontend tests                                                                                                     | web            | it-1  | OPEN             |
| [#11](#11--escalate_on_negative-is-misnamed)                                                                                      | S4  | `escalate_on_negative` is misnamed                                                                                    | backend        | it-1  | OPEN             |
| [#12](#12--whatsapp-env-vars-are-read-but-unused)                                                                                 | S4  | WhatsApp env vars read but unused                                                                                     | backend        | it-1  | OPEN             |
| [#13](#13--the-last-owner-guard-blocked-every-cascading-delete)                                                                   | S1  | Last-owner guard blocked every cascading delete                                                                       | database       | it-2  | **FIXED**        |
| [#14](#14--orphaned-organisations-survive-account-deletion)                                                                       | S3  | Orphaned organisations survive account deletion                                                                       | database       | it-2  | **FIXED**        |
| [#15](#15--next-build-output-blocked-a-git-mv-of-the-web-app)                                                                     | S4  | `.next` blocked a `git mv` of the web app                                                                             | tooling        | it-2  | **FIXED**        |
| [#16](#16--token-verification-rejected-valid-tokens-under-clock-skew)                                                             | S1  | Token verification rejected valid tokens under clock skew                                                             | api            | it-3  | **FIXED**        |
| [#17](#17--orphaned-organisations-confirmed-in-practice)                                                                          | S3  | Orphaned orgs consume slugs permanently                                                                               | database       | it-3  | **FIXED**        |
| [#18](#18--supabase-rejects-email-domains-without-mx-records)                                                                     | S4  | Supabase rejects domains without MX records                                                                           | external       | it-3  | WONTFIX          |
| [#19](#19--built-in-email-sender-quota-is-exhausted-quickly)                                                                      | S2  | Built-in email sender quota exhausted quickly                                                                         | config         | it-3  | **PARTLY FIXED** |
| [#20](#20--calling-windows-are-not-enforced-anywhere-in-the-backend)                                                              | S2  | Calling windows are not enforced anywhere in the backend                                                              | backend + web  | it-4  | **PARTLY FIXED** |
| [#21](#21--organisationlogo_url-was-missing-from-the-orm-model)                                                                   | S4  | `Organisation.logo_url` was missing from the ORM model                                                                | backend        | it-4  | **FIXED**        |
| [#22](#22--half-the-real-runtime-dependencies-were-undeclared-in-pyprojecttoml)                                                   | S2  | Half the real runtime dependencies were undeclared in `pyproject.toml`                                                | backend        | it-4  | **FIXED**        |
| [#23](#23--root-envexample-still-had-callflow_dry_run-and-no-supabase-config-at-all)                                              | S2  | Root `.env.example` still had `CALLFLOW_DRY_RUN` and no Supabase config at all                                        | config         | it-4  | **FIXED**        |
| [#24](#24--featuresmd-does-not-exist)                                                                                             | S3  | `FEATURES.md` does not exist                                                                                          | docs           | it-4  | OPEN             |
| [#25](#25--editing-a-campaign-silently-created-a-duplicate)                                                                       | S1  | Editing a campaign silently created a duplicate                                                                       | backend + web  | it-5  | **FIXED**        |
| [#26](#26--the-run-composers-window-guard-chip-reintroduced-an-already-fixed-false-claim)                                         | S2  | The run composer's Window guard chip reintroduced an already-fixed false claim                                        | web            | it-5  | **FIXED**        |
| [#27](#27--the-required-field-checkbox-had-no-effect-on-the-schema-sent-to-the-engine)                                            | S3  | The "Required" field checkbox had no effect on the schema sent to the engine                                          | backend + web  | it-5  | **FIXED**        |
| [#28](#28--creating-a-second-organisation-always-failed-with-an-rls-error)                                                        | S1  | Creating a second organisation always failed with an RLS error                                                        | backend        | it-6  | **FIXED**        |
| [#29](#29--an-error-inside-asuser-masked-itself-with-a-connection-cleanup-crash)                                                  | S1  | An error inside `as_user()` masked itself with a connection-cleanup crash                                             | backend        | it-6  | **FIXED**        |
| [#30](#30--the-needs-a-person-queue-and-the-dashboards-own-disposition-count-disagreed)                                           | S2  | The "Needs a person" queue and the dashboard's own disposition count disagreed                                        | web            | it-6  | **FIXED**        |
| [#31](#31--switching-organisations-never-actually-took-effect)                                                                    | S1  | Switching organisations never actually took effect                                                                    | web            | it-6  | **FIXED**        |
| [#32](#32--the-rate-limiter-and-daily-budget-were-shared-across-every-organisation)                                               | S1  | The rate limiter and daily budget were shared across every organisation                                               | backend        | it-7  | **FIXED**        |
| [#33](#33--safety-settings-had-no-real-persistence-behind-them)                                                                   | S2  | Safety settings had no real persistence behind them                                                                   | backend + web  | it-7  | **FIXED**        |
| [#34](#34--the-invitation-email-interpolated-org-name-and-role-into-html-unescaped)                                               | S2  | The invitation email interpolated org name and role into HTML unescaped                                               | backend        | it-7  | **FIXED**        |
| [#35](#35--a-stale-pinned-organisation-produced-an-unrecoverable-403-and-a-fake-service-down-error)                               | S2  | A stale pinned organisation produced an unrecoverable 403 and a fake service-down error                               | web            | it-7  | **FIXED**        |
| [#36](#36--contact-grids-error-was-shown-on-the-wrong-column-and-on-untouched-blank-rows)                                         | S3  | Contact grid's error was shown on the wrong column and on untouched blank rows                                        | web            | it-7  | **FIXED**        |
| [#37](#37--voice-engine-errors-were-not-normalised-into-an-internal-taxonomy)                                                     | S3  | Voice engine errors were not normalised into an internal taxonomy                                                     | backend        | it-7  | **FIXED**        |
| [#38](#38--the-runs-list-and-dashboard-never-updated-while-a-run-was-in-flight)                                                   | S3  | The runs list and dashboard never updated while a run was in flight                                                   | web            | it-7  | **FIXED**        |
| [#39](#39--stop-run-contradicted-itself-and-was-a-dead-duplicate-of-pause-run)                                                    | S2  | "Stop run" contradicted itself and was a dead duplicate of "Pause run"                                                | web            | it-8  | **FIXED**        |
| [#40](#40--the-dashboards-recent-runs-panel-showed-the-raw-campaign-slug-instead-of-its-name)                                     | S3  | The dashboard's "Recent runs" panel showed the raw campaign slug instead of its name                                  | web            | it-8  | **FIXED**        |
| [#41](#41--the-run-composer-showed-a-credits-estimate-with-no-backing-credit-system)                                              | S3  | The run composer showed a "Credits" estimate with no backing credit system                                            | web            | it-8  | **FIXED**        |
| [#42](#42--a-css-comment-containing-a-literal--silently-broke-the-production-build)                                               | S2  | A CSS comment containing a literal `*/` silently broke the production build                                           | web            | it-8  | **FIXED**        |
| [#43](#43--admin-could-self-promote-to-owner-and-take-over-the-account)                                                           | S1  | Admin could self-promote to Owner and take over the account                                                           | backend        | it-9  | **FIXED**        |
| [#44](#44--re-inviting-an-already-invited-email-fails-under-rls)                                                                  | S3  | Re-inviting an already-invited email fails under RLS                                                                  | backend        | it-9  | **FIXED**        |
| [#45](#45--43s-own-invitation-column-lock-fix-broke-inviting-anyone-at-all)                                                       | S1  | `#43`'s own invitation-column-lock fix broke inviting anyone at all                                                   | backend        | it-9  | **FIXED**        |
| [#46](#46--resolving-an-escalation-updated-nothing-outside-its-own-card)                                                          | S3  | Resolving an escalation updated nothing outside its own card                                                          | web            | it-10 | **FIXED**        |
| [#47](#47----text-mute-fell-short-of-wcag-aa-body-text-contrast-almost-everywhere-its-used)                                       | S3  | `--text-mute` fell short of WCAG AA body-text contrast almost everywhere it's used                                    | web            | it-10 | **FIXED**        |
| [#48](#48--the-dashboards-ambient-glow-widened-the-page-past-the-viewport-and-caused-a-global-horizontal-scroll)                  | S2  | The dashboard's ambient glow widened the page past the viewport and caused a global horizontal scroll                 | web            | it-10 | **FIXED**        |
| [#49](#49--radix-overlays-and-the-toast-provider-portal-outside-app-font-scope-and-lose-the-new-typeface)                         | S3  | Radix overlays and the toast provider portal outside `.app-font-scope` and lose the new typeface                      | web            | it-11 | OPEN             |
| [#50](#50--admins-role-picker-offers-admin-a-role-admin-cant-grant-guaranteeing-a-403)                                            | S3  | Admin's role picker offers "Admin," a role Admin can't grant, guaranteeing a 403                                      | web            | it-11 | OPEN             |
| [#51](#51--team-invitations-failed-outright--the-from-domain-was-never-verified-in-resend-and-the-error-leaked-a-raw-httpx-dump)  | S2  | Team invitations failed outright - the from-domain was never verified in Resend                                       | backend + docs | it-12 | **PARTLY FIXED** |
| [#52](#52--transcript-extraction-read-a-top-level-key-that-doesnt-exist-anywhere-in-call-es-real-response)                        | S2  | Transcript extraction read a top-level key that doesn't exist anywhere in CALL-E's real response                      | backend        | it-13 | **FIXED**        |
| [#53](#53--one-flaky-status-poll-could-mark-an-entire-successfully-completed-call-as-failed)                                      | S2  | One flaky status poll could mark an entire, successfully-completed call as failed                                     | backend        | it-13 | **FIXED**        |
| [#54](#54--a-retried-call-after-a-connection-error-classification-could-double-dial-without-counting-against-the-per-run-ceiling) | S3  | A retried call after a connection-error classification could double-dial without counting against the per-run ceiling | backend        | it-13 | OPEN             |

---

## Iteration 1 - 2026-08-06 · full system audit

Findings from reading the whole codebase to write `SYSTEM.md`.

### #1 - No persistence anywhere

**S1 · FIXED · backend · migration `202608070900_campaigns_runs_and_call_outcomes`**

`callflow/store.py` was a `dict` behind a `threading.Lock`. Every run, outcome,
transcript, and user-created campaign lived in process memory.

**Impact.** All data was lost on restart or redeploy - and CI redeploys on every push to
`main`. With more than one worker, requests hit different stores, so a run started on
worker A returned 404 from worker B.

**Fixed.** `campaigns`, `runs`, and `call_outcomes` tables in Postgres, each `org_id
NOT NULL` with RLS, per `FEATURES.md` F2. `app/database/run_store.py` and the module-global
registry in `app/domain/campaigns.py` are deleted; `app/database/repositories/{campaigns,runs}.py`
hold the org-scoped SQL. Transcript/recording offload to object storage is not part of this
change and remains future work.

**Verified.** 76 backend tests pass, including the persistence and RLS paths.

**Blocked:** #2, #3, #5, #7, and every feature from F13 onward. #2, #3 are now also fixed;
#5 and #7 remain open.

---

### #2 - User campaigns are global and ephemeral

**S1 · FIXED · backend · `app/database/repositories/campaigns.py`**

`register_campaign()` used to mutate a module-level `REGISTRY`/`SCHEMAS` dict.

**Impact.** On the shared deployment every visitor could see, edit, and delete every other
visitor's campaigns. This was a cross-tenant data exposure, not a future risk. They also
vanished on restart.

**Fixed.** User-created campaigns now live in the `campaigns` table, scoped by `org_id`
with RLS. Built-ins stay in code (`app/domain/campaigns.py`) as read-only templates,
never written to the database, and are resolved at the application layer alongside the
persisted ones.

**Depends on:** #1 (fixed).

---

### #3 - Suppression list is never enforced

**S1 · FIXED · backend + web · `app/domain/safety.py`, `app/database/repositories/suppressions.py`, `app/api/v1/routes/suppressions.py`**

`web/lib/suppression.ts` used to keep the list in one browser's `localStorage`. The dial
path (`safety.check_dial_allowed`) never consulted it.

**Impact.** The product told users a suppressed number is "never dialled by any campaign,
ever" and showed a permanent `SUPPRESSED` tag. That guarantee did not hold - a run could
dial someone who had asked not to be called. This was the most serious gap after #1
because it was a stated promise with legal weight (DPDP, TCPA, TRAI), and the UI actively
asserted it was true.

**Read/enforcement side fixed first.** A `suppressions` table keyed on `(org_id,
phone_hash)` (SHA-256 with a per-deployment pepper, `PHONE_HASH_PEPPER`).
`check_dial_allowed()` now takes an `is_suppressed: bool` and denies the dial if true -
checked against a snapshot of suppressed hashes resolved once per run and consulted for
every contact in it (`FEATURES.md` F14). This shipped in the same change as dry_run
removal (see Iteration 4): once dry_run stopped being a de facto safety net, this became
the guard that actually has to hold. Verified by the orchestrator test suite (a suppressed
contact never reaches the gateway).

**Write side fixed in this iteration.** `app/database/repositories/suppressions.py`'s
`add_suppression()` and `remove_suppression()` had no caller anywhere in the app - no
`/api/v1/suppressions` route existed, so the table could only be populated by a direct
database write, and the frontend's "Contacts" page suppression toggle was a **separate,
disconnected** `localStorage` list that never touched it. Found by re-reading the dial
path against the frontend while investigating the calling-window claims in #20 - the same
"UI promises something the backend doesn't do" shape, on a legally-weighted guarantee.

Fixed by adding `app/api/v1/routes/suppressions.py`: `GET/POST /api/v1/suppressions` and
`DELETE /api/v1/suppressions/{id}`, gated by the `SUPPRESSIONS_READ`/`ADD`/`REMOVE`
permissions that already existed in the permission matrix (unused until now - this route
is the feature they were written for). Adding is `operator` role or above; removing
(making someone callable again) is owner-only, matching the table's existing RLS insert/
delete policies exactly. The "Contacts" page's suppression tab now calls this API
directly instead of `lib/suppression.ts`, which is deleted.

**Still open, separately:** a `do_not_call` disposition from triage does not yet
auto-insert a suppression row - today a person still has to add the number by hand after
noticing the call ended that way. Not blocking, since the manual path is now real; tracked
for a future iteration rather than reopening this issue.

**Depends on:** #1 (fixed).

---

### #4 - `CallOutcome.run_id` holds the provider call id

**S1 · FIXED · backend · `app/api/v1/routes/runs.py`**

The orchestrator sets `run_id=call_id` (the engine's call identifier) internally, in
three places: the in-flight update, `_poll_until_done`, and the resolved outcome -
this is still true of `app/services/campaign_runner.py` in isolation.

**Impact.** The frontend links to `/app/runs/{outcome.run_id}` from the overview lamp
strip and ⌘K search. On a live run those links pointed at a run id that did not exist →
404-ish empty state.

**Fixed** one layer up, at the persistence boundary rather than in the orchestrator:
`_run_and_persist()` in `app/api/v1/routes/runs.py` renames the field before it is ever
stored - `record["provider_call_id"] = record.pop("run_id", None)` - and passes the
actual run id in separately. The persisted `call_outcomes` row and every API response
carry the real `run_id`; `provider_call_id` holds the engine's call id as its own field.
Re-severitised from S2 to S1 on fix, since with dry_run gone every run is real and this
would otherwise have broken run navigation universally rather than only masking it.

**Verified.** `Outcome.provider_call_id` is now a distinct, typed field in
`apps/web/lib/api.ts`; `run_id` always resolves to the real run.

---

### #5 - Rate limits and daily budget are per-process and reset on restart

**S2 · PARTLY FIXED · backend · `app/core/rate_limit.py`**

Counters are in-memory `deque`s using `time.monotonic()`.

**Impact.** The "shared daily budget" is neither shared (per process) nor durable (resets
on deploy). Since CI deploys on every push to `main`, the budget effectively resets
whenever anyone merges. `monotonic()` also means the 24h window is measured from process
start, not wall-clock midnight.

**Partly fixed in it-7 (see #32):** the limiter is now keyed per organisation instead of
one shared/global bucket, which closes the cross-tenant part of this issue. **Still open:**
the counters are still in-process `deque`s - durability across a restart/redeploy is
unchanged. Fix remains Upstash Redis sliding window (`FEATURES.md` F10), failing
**closed** for cost-bearing writes and open for reads.

**Depends on:** #1 for the org scoping (fixed, this iteration).

---

### #6 - Three high-severity npm advisories

**S2 · OPEN · web**

`postcss` (4 advisories: XSS via unescaped `</style>`, arbitrary file read and path
traversal via `sourceMappingURL`) and `sharp` (inherited libvips CVEs), both transitive
through `next@16.2.12`.

**Impact.** No known exploit path in this app - `postcss` runs at build time on our own
CSS, and `sharp` is used by Next's image optimisation. Still fails `npm audit` and will
fail any security review.

**Fix.** Upgrade to `next@16.3.0`, which resolves all three. Deliberately not done during
the UI rebuild to avoid mixing a framework bump into a large diff.

---

### #7 - Escalation resolution is component state

**S3 · PARTLY FIXED · web · `apps/web/components/app/escalation-card.tsx`**

`Mark resolved` sets local `useState`. Navigating away loses it.

**Partly fixed in it-10 (see #46):** resolving now drops the item from the shared
`useAppStore().escalations` list itself, so the worklist, the dashboard panel, and the
nav badge all update in the same render - the within-session "nothing visibly updates"
symptom is gone. **Still open:** nothing is written to a database. A reload, a second
tab, or a second person still sees the item as unresolved - the fix below is unchanged.

**Impact.** An operator marks five escalations resolved, changes page, and they are all
back. Actively worse than no button, because it implies work was saved.

**Fix.** `escalations` table with `status`, `assigned_to`, `resolved_by`, `resolved_at`
(`FEATURES.md` F23), plus claim-on-open so two people cannot resolve the same item.

**Depends on:** #1.

---

### #8 - `stats` mixes denominators

**S3 · OPEN · backend · `callflow/api.py`**

In `get_run`, `escalated` is counted over `resolved` outcomes, but `auto_closed` and
`needs_human_pct` are counted over **all** outcomes including `in_flight`.

**Impact.** Mid-run percentages are diluted by in-flight rows, so the escalation rate
reads lower than it is while a run is live. Settles correctly once the run finishes.

**Fix.** Compute every stat over `resolved`, and expose `in_flight` as its own count.

---

### #9 - `render.yaml` contradicts the real deployment

**S3 · OPEN · infra**

`render.yaml` describes a two-service Render deploy. The actual deploy is
`.github/workflows/ci-cd.yml` → SSH to a VM → `pm2 restart callflow-api|callflow-web`,
behind `callflow-ai.brbik.com`.

**Impact.** Misleads anyone new, and invites someone to "fix" deployment in the wrong file.

**Fix.** Delete it, or keep it with a header comment saying it is unused.

---

### #10 - No frontend tests

**S3 · OPEN · web**

84 backend tests; zero on the frontend.

**Impact.** The highest-risk frontend logic is untested: `lib/format/phone.ts` (the masking
guarantee), `lib/lamp.ts` (disposition → lamp mapping), `lib/contacts.ts` (row validation),
`lib/campaign-fields.ts` (the 5→4 type mapping).

**Fix.** Vitest on those four modules first. They are pure functions, so this is cheap.

---

### #11 - `escalate_on_negative` is misnamed

**S4 · OPEN · backend · `callflow/triage.py`**

The flag gates a branch that returns `Disposition.RETRY`, not an escalation. When `false`,
negative sentiment falls through to the status checks rather than being ignored.

**Impact.** Anyone reading the campaign editor's "Escalate frustrated calls to a person"
switch will expect it to control escalation. Frustration escalation is actually
unconditional; this only controls the negative-sentiment retry.

**Fix.** Rename to `retry_on_negative` and correct the UI label. Breaking change to the
campaign create payload, so best done alongside the schema migration.

---

### #12 - WhatsApp env vars are read but unused

**S4 · OPEN · backend · `callflow/config.py`**

`WHATSAPP_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` are loaded into config. No code reads them.

**Impact.** Implies a working integration. `.env.example` lists them as "optional".

**Fix.** Either remove until F30 is built, or comment them as reserved.

---

## Iteration 2 - 2026-08-06 · Supabase auth foundation

### #13 - The last-owner guard blocked every cascading delete

**S1 · FIXED · database · migration `..._fix_last_owner_cascade`**

Introduced by me in the first auth migration and caught by the verification script, not by
review.

`protect_last_owner` raised whenever the last owner's membership was removed. Correct for a
direct removal, but a membership row is _also_ removed as a side effect of legitimate
deletions - `delete auth.users → cascade public.users → cascade memberships`, and
`delete organisation → cascade memberships`.

**Impact.** No user or organisation could ever be deleted. That breaks Supabase's own user
management and the data-subject erasure flow (F43), and it fails precisely on the most
common case: deleting the account that owns its org.

**Fix.** The guard now skips when the parent organisation or user is already gone. Postgres
applies the parent delete before firing the referential action, so mid-cascade absence is a
reliable discriminator between "someone is revoking this membership" and "this row is being
cleaned up".

**Verified.** Direct removal of a sole owner is still refused; deleting the account now
cascades cleanly.

---

### #14 - Orphaned organisations survive account deletion

**S3 · OPEN · database**

Organisations are deliberately not cascade-deleted from users - they are soft-deleted via the
DSR flow. So deleting the only member of an org leaves the org row behind with no memberships,
which makes it invisible to every RLS policy and therefore unreachable.

**Impact.** Rows accumulate that nobody can see or administer. Harmless today, but it will
distort any org-count metric and confuse a future support tool.

**Fix.** Either a `pg_cron` sweep that soft-deletes member-less organisations after a grace
period, or fold it into the account-deletion path in F43. Needs the DSR flow to exist first.

---

### #15 - `.next` build output blocked a `git mv` of the web app

**S4 · FIXED · tooling**

Not a product bug, recorded because it will recur. A running `next dev` server plus a 395 MB
`.next` directory held Windows file handles, so `git mv web apps/web` failed with
"Permission denied" - with no indication of the cause.

**Fix / how to avoid.** Stop the dev server and delete `.next` before moving or renaming any
directory under `apps/web`. Both are disposable: `.next` is gitignored and regenerates.

---

## Iteration 3 - 2026-08-06 · backend auth chain

### #16 - Token verification rejected valid tokens under clock skew

**S1 · FIXED · api · `app/auth/tokens.py`**

`/api/v1/me` returned `401 ImmatureSignatureError` for a token Supabase had just
issued. The token's `iat` was marginally ahead of this host's clock, and PyJWT rejects
that with zero tolerance by default.

**Impact.** Would have rejected **every valid login** on any host not tightly
NTP-synced. Presents as "correct credentials refused", with nothing in the client to
suggest a clock problem - the worst class of auth bug to diagnose in production.

**Fix.** `leeway=timedelta(seconds=30)` on `jwt.decode`. Deliberately small: leeway
also extends `exp`, so a large value would keep expired tokens alive.

**Verified.** Real Supabase token now verifies; bogus/absent tokens still 401.

---

### #17 - Orphaned organisations confirmed in practice

**S3 · OPEN · database**

Predicted as #14, now observed. Four orphans accumulated across three test runs, and
the visible symptom was a _slug collision_: a new signup from `brbik.com` became
`brbik-2` because the dead org still held `brbik`.

**Impact.** Worse than the invisible-row problem #14 described. Organisation slugs are
globally unique, so orphans permanently consume names - a real customer re-signing up
after deleting their account would get `acme-2`.

**Fixed** in two revisions, because the first attempt was incomplete and the test caught it:

1. `release_slugs_and_retire_empty_orgs` - slug uniqueness became a partial unique index
   on `deleted_at IS NULL`, and an `AFTER DELETE` trigger soft-deletes an organisation
   once its last membership goes.
2. `reuse_freed_slugs_on_signup` - the signup trigger's collision loop was still counting
   _every_ row, so it kept stepping past freed slugs and a repeat signup still got
   `acme-2`. The loop now ignores soft-deleted rows, matching the index that enforces
   uniqueness.

**Verified.** First signup gets `brbik`; after account deletion the org is soft-deleted;
a fresh signup from the same domain gets `brbik` again; two live organisations still
cannot share a slug.

This also closes #14 - a member-less organisation is no longer left behind at all.

---

### #18 - Supabase rejects email domains without MX records

**S4 · WONTFIX (documented) · external**

Signup with `@northgate-labs.com` and `@example.com` returns
`400 email_address_invalid`. Supabase validates deliverability, so invented domains
cannot be used for test fixtures.

**Consequence for testing.** Seed test users through the admin API
(`POST /auth/v1/admin/users` with the secret key and `email_confirm: true`). It skips
both the domain check and the email send, so it does not consume the sender quota.

---

### #19 - Built-in email sender quota is exhausted quickly

**S2 · OPEN · external config**

Signup attempts returned `429 email rate limit exceeded` on the third and later tries,
which indicates Supabase still attempts a send.

**Impact.** Password reset cannot work reliably, and if "Confirm email" is not in fact
disabled, signups will silently fail once the hourly quota is gone.

**Partly fixed.** "Confirm email" is now genuinely off, and public signup was
re-verified end to end: `POST /auth/v1/signup` returns `200` with an access token
immediately, `email_confirmed_at` is set, and `/api/v1/me` resolves the new
organisation. Signup no longer depends on email delivery at all.

**Still open:** password reset and team invitations _do_ send mail, so they remain
subject to the built-in sender's few-per-hour quota. Configure **custom SMTP** (Resend)
before either flow is relied on. Not a blocker for sign-up or sign-in.

---

## Iteration 4 - 2026-08-07 · persistence, dry_run removal

Not a bug-finding pass - a deliberate, user-confirmed product change, recorded here
because it closes #1–#4 above and changes the safety model CLAUDE.md documents as
non-negotiable.

**Persistence.** Campaigns, runs, and call outcomes moved from process memory to
org-scoped Postgres tables with RLS (`202608070900_campaigns_runs_and_call_outcomes`).
This closes #1, #2, and #4. `app/services/campaign_runner.py` is now `async def`
throughout, using `asyncio.to_thread()` for the still-synchronous voice SDK calls, so it
can write to Postgres as a run progresses instead of only holding state in memory.

**`dry_run` removed entirely.** Confirmed explicitly by the product owner as a deliberate
removal of the safety gate, not a cosmetic UI change: `dry_run` no longer exists on
`Config`, `CallOutcome`, the run-start request, or anywhere in the frontend. Every run
dials for real, unconditionally, from the first one. `app/domain/samples.py` (dry-run
sample results) is deleted; `Permission.RUNS_GO_LIVE` is removed in favour of a single
`RUNS_START` (starting any run at all is now the consequential action).

**Suppression enforcement shipped in the same change**, not separately, because with
dry_run gone the suppression list is the guard that actually has to hold on the very
first run an organisation makes - see #3 (partly fixed: enforcement is real, but there
is still no way to add a number to the list through the product).

**What still stands as the safety model:** E.164 validation, allowlist, per-run ceiling,
rate limiting (still #5's known weakness - in-memory, per-process), the shared daily
budget, calling windows, phone masking, and the now-enforced suppression list. `CLAUDE.md`
non-negotiable #8 ("dry_run defaults to true, everywhere") is replaced accordingly - see
the file itself for the current wording.

---

### #20 - Calling windows are not enforced anywhere in the backend

**S2 · PARTLY FIXED · backend + web**

Found while fact-checking `README.md` against the real code for this iteration's docs
pass. `apps/api/app/domain/safety.py` has no window check at all - grepping the whole
backend for `window_start`/`window_end`/calling-window logic returns nothing.

**Impact.** This was a `CLAUDE.md` non-negotiable #9 violation ("never show a success
state for something that did not happen"), not just a missing feature - and a wider one
than first found. A follow-up sweep (prompted by a user report of a confusing dashboard)
turned up the same false claim in **eight** places, not the three originally listed:
`apps/web/components/app/safety-bar.tsx`'s `guardsFromHealth()` (the guard chip shown on
the _actual run composer_, hardcoding `"09:00–20:00 IST"` as if confirmed - the one guard
in that function that didn't follow its own "unconfirmed → null/OFF" rule),
`settings/safety/page.tsx`, `components/app/campaign-editor.tsx` (told users configuring
a real campaign "nothing is dialled outside this window," and the same panel's retry
"attempts"/"spacing" controls turned out to have an identical problem - the `RETRY`
disposition is real, but nothing acts on the attempt count or spacing automatically),
the marketing `safety-section.tsx` (both the demo guard bar and the explained-guards
list), `/docs/safety-configuration`, `lib/docs.ts`'s summary of that page, and - most
seriously - **`/trust`'s regional compliance notes**, which stated as fact that "India -
calling windows default to 09:00–20:00 IST and are enforced per campaign" and the
equivalent for US area codes. That's a false regulatory-compliance claim on the one page
a prospect reads specifically to assess compliance risk before signing.

**Fixed:** every surface above now either omits the claim or says plainly that calling
windows (and, in the campaign editor, automatic retry) aren't enforced yet - using the
existing `NotWiredNotice` pattern, and `guardsFromHealth()`'s window guard now reports
`null` (renders as `OFF`, consistent with how every other unconfirmed guard already
behaves) instead of a hardcoded fake value.

**Still open:** the underlying feature. Either wire real enforcement - a per-campaign or
per-org window column, checked in `check_dial_allowed()` (the same place suppression is
now checked, so the pattern already exists), with queued-for-retry semantics - or leave
it permanently out of the product. What's fixed is that nothing lies about it in the
meantime.

**Depends on:** #1 (fixed) for a place to persist a window per org/campaign.

---

### #21 - `Organisation.logo_url` was missing from the ORM model

**S4 · FIXED · backend · `app/database/models.py`**

`logo_url` was added to the real `organisations` table by the invitations/storage
migration, but the SQLAlchemy `Organisation` class was never updated to declare it.
Found by `alembic check` while adding the `onboarded_at` column for the org-onboarding
gate (this iteration) - it reported a phantom `remove_column` operation for `logo_url`,
which meant the model and the database had silently drifted.

**Impact.** Low on its own (the column still worked fine through raw asyncpg in the
repositories, which don't go through the ORM), but `alembic check`'s no-drift guarantee
was already broken before this iteration touched anything, and a future autogenerate
run would have proposed actually dropping a column that's in active use.

**Fixed.** Added `logo_url: Mapped[str | None] = mapped_column(Text)` to the model.
`alembic check` reports no drift again.

---

### #22 - Half the real runtime dependencies were undeclared in `pyproject.toml`

**S2 · FIXED · backend · `apps/api/pyproject.toml`**

`SQLAlchemy`, `asyncpg`, `alembic`, `psycopg[binary]`, and `PyJWT` are all imported
throughout `app/` and actively used - auth verification, every database query, every
migration - but none of them were listed in `dependencies`. Found while adding
`cryptography` for the Integrations feature and checking what else was missing.

**Impact.** `pip install -e ".[dev]"` - the README's own quick-start command - would
install a service that immediately fails at import time on a machine that didn't
already happen to have these packages from some earlier, undocumented `pip install`.

**Fixed.** Added all five, plus `cryptography` (already a transitive dependency, now
declared directly since `app/core/crypto.py` imports it).

---

### #23 - Root `.env.example` still had `CALLFLOW_DRY_RUN` and no Supabase config at all

**S2 · FIXED · config · `.env.example`**

The dry*run removal pass (iteration 4) updated every other reference to
`CALLFLOW_DRY_RUN` but missed the root `.env.example`, which still listed it as a
real, honored variable. Separately, `.env.example` predated the entire Supabase/auth
build-out - it had no `SUPABASE*_`, `DATABASE*URL`, `PHONE_HASH_PEPPER`,
`RESEND*_`, or `SITE_URL`entries, despite`config.py` reading all of them.

**Impact.** Anyone following the README's `cp .env.example .env` step would set a
variable that does nothing and skip every variable persistence and auth actually
require, then hit confusing failures with no clue why.

**Fixed.** Rewritten to match `config.py` field-for-field, with `CALLFLOW_DRY_RUN`
removed and `PROVIDER_CREDENTIALS_KEY` (new, this iteration) included.

---

### #24 - `FEATURES.md` does not exist

**S3 · OPEN · docs**

`CLAUDE.md`'s own document map describes it as "Target state, F1–F52, with build
order... read-only; it is the spec," and `SYSTEM.md`, `ISSUES.md`, and `CLAUDE.md`
itself reference specific `F<n>` numbers throughout (F2, F14, F17, F19, F47, and
dozens more) as though resolving them against a real document. Checked `git log --all
-- FEATURES.md`: it has never existed at any commit in this repository's history.

**Impact.** Every `F<n>` citation across three governing documents points at nothing.
Low severity because the numbers still function as stable, consistently-used labels -
`SYSTEM.md` §12's gap map is a real, accurate substitute in practice - but a new
contributor told to "check FEATURES.md, it's read-only, it's the spec" will find no
such file, and the phased build order CLAUDE.md and old planning notes refer to
(e.g. "the dependency order in B") was never written down anywhere real.

**Fix.** Either write `FEATURES.md` for real (F1–F52, with the build-order sections
`SYSTEM.md`/`CLAUDE.md` already reference by letter), or stop citing a spec that
doesn't exist and fold §12's gap map into being the canonical target-state document
instead. Noted at the top of `SYSTEM.md`, in `CLAUDE.md`'s document map, and in this
file's own header so nobody trusts an `F<n>` reference as pointing to a real file
until one of these happens.

---

## Iteration 5 - 2026-08-07 · dashboard revamp: honesty and wiring sweep

Findings from a systematic pass over the remaining `/app/*` pages, tracing every button
to what it actually calls, prompted by user feedback that the dashboard needed to "look
good" and be trustworthy before launch. Two more instances of the calling-window shape
turned up (#20, #3) plus one genuine data-integrity bug.

### #25 - Editing a campaign silently created a duplicate

**S1 · FIXED · backend + web · `app/api/v1/routes/campaigns.py`, `web/components/app/campaign-editor.tsx`**

The campaigns list's "Edit" menu item opened `/app/campaigns/{id}` with the full editor
unlocked for any non-template campaign (`campaign-editor.tsx`, `readOnly =
existing?.built_in`). Its `save()` unconditionally called `api.createCampaign(...)`
regardless of whether an existing campaign was being edited. No `PATCH`/`PUT` route
existed on the backend at all - `create_campaign` always slugifies the name into a new
id and inserts a new row.

**Impact.** Opening a real campaign via "Edit," changing something, and clicking "Save
campaign" created a second, independent campaign with a new id and left the original
completely unchanged - while the toast said "Campaign saved," implying the edit had
taken effect. A person who edited a goal template to fix a mistake would keep running
the old, broken campaign without realising it, since the run composer's campaign picker
now shows both and nothing distinguishes "the one you just edited" from "the original."

**Fix.** Added `PATCH /api/v1/campaigns/{campaign_id}` (`Permission.CAMPAIGNS_WRITE`,
same validation as `POST`, id/slug never changes so existing runs keep pointing at the
right campaign) and `campaigns_repo.update_campaign()`. No migration needed - the
`campaigns_write` RLS policy was already `for all` (insert/update/delete), so the
database side of this was ready and unused, same shape as #3's suppression permissions.
`campaign-editor.tsx`'s `save()` now branches: `PATCH` when editing an existing,
non-built-in campaign, `POST` otherwise.

### #26 - The run composer's Window guard chip reintroduced an already-fixed false claim

**S2 · FIXED · web · `web/app/(app)/app/runs/new/page.tsx`, `web/components/app/safety-bar.tsx`**

`safety-bar.tsx`'s `guardsFromHealth()` was fixed earlier this iteration (see #20) to
report the "Window" guard as `null`/OFF, since calling-hour enforcement doesn't exist in
`check_dial_allowed()`. `runs/new/page.tsx` built its `guards` list by taking that
honest result and then unconditionally overwriting the window guard's `value` with the
selected campaign's locally-stored window (`loadLocalSettings`), rendering it in the
normal "active" chip style with a concrete time range and a popover claiming "Calls are
only placed inside this window... queued for the next opening rather than dialled."

**Impact.** The exact false claim #20 fixed in one file was still live in the one place
an operator looks immediately before starting a real run - the safety bar on the run
composer itself.

**Fix.** Removed the override; the composer now renders `guardsFromHealth(health)`
directly, same as everywhere else. Also fixed `safety-bar.tsx`'s own `explanation` text
for the window guard, which I'd missed when fixing #20 - the value had been changed to
`null` but the explanation still asserted the window was enforced, contradicting the
"this guard is off" caveat rendered directly below it in the same popover.

**Depends on:** #20 (fixed).

### #27 - The "Required" field checkbox had no effect on the schema sent to the engine

**S3 · FIXED · backend + web · `app/domain/result_schemas.py`, `app/api/v1/routes/campaigns.py`, `web/lib/campaign-fields.ts`**

The campaign editor's per-field "Required" checkbox is labelled "the call isn't complete
without it," and the live schema preview shown beside the form added the field to a
`required` array to match. `toWireFields()` never sent that flag, `FieldIn` had no
`required` property, and `build_result_schema()` always used a hardcoded
`BASE_REQUIRED` - so the checkbox's only real effect was a wording change in the
description text sent to the engine ("Leave it null if the contact didn't say."), not
the structural schema constraint the UI implied.

**Fix.** Threaded `required` end to end: `CampaignField.required` (wire type) →
`FieldIn.required` → collected into a list in `_validate_and_build_fields()` →
`build_result_schema(properties, extra_required)`, appended to `BASE_REQUIRED` rather
than replacing it, so a campaign can never make triage's own fields optional. Both
`POST` and the new `PATCH` (#25) pass it through.

**Known remaining gap, not blocking:** the editor reloads an existing campaign's fields
from `outcome_fields: dict[str, str]` (description only) - type, `required`, and enum
options are not persisted per-field today, so re-opening a saved campaign shows every
field as a generic, optional string regardless of how it was configured. Fixing that
needs `outcome_fields` (or a new column) to carry structured per-field metadata, not
just descriptions - a real gap, but pre-existing and separate from this fix, which is
about what a _new_ save sends going forward.

---

## Iteration 6 - 2026-08-07 · reported from real use: org creation, dashboard data, IA

Found from the product actually being used for the first time end to end, not from
code review - a real signup, a real second-organisation attempt, a real run with
escalations. Screenshots and a server traceback made two of these unambiguous;
the third was found by reproducing the traceback directly against the database.

### #28 - Creating a second organisation always failed with an RLS error

**S1 · FIXED · backend · `app/database/repositories/organisations.py`, migration `a7c2e5f9b184`**

`POST /api/v1/organisations` returned 500 for every attempt, with
`asyncpg.exceptions.InsufficientPrivilegeError: new row violates row-level security
policy for table "organisations"` - even though `current_user_id()` resolved
correctly and the table's own `organisations_insert` check
(`current_user_id() is not null`) was satisfied. Confirmed by reproducing the exact
call against the real database outside the API: the same insert with `RETURNING`
removed succeeded immediately.

**Root cause.** `org_repo.create()` inserted into `organisations` _with `RETURNING`_
before the follow-up insert into `memberships` that makes the caller an actual
member. Postgres re-checks a `RETURNING` row against the table's `SELECT` policy
(`organisations_select`, `is_org_member(id)`) before handing it back - and at that
moment no membership row exists yet for the brand-new org, so the check fails and
Postgres raises rather than just returning nothing. This is the exact chicken-and-egg
case the signup trigger already solves by being `SECURITY DEFINER` and owned by a
role with `BYPASSRLS`, so its own inserts never hit a policy check at all - the
dashboard's "create organisation" button just didn't go through that escape hatch.

**Impact.** Every organisation-creation attempt from the product failed, with no
working path - S1 because it's a total block on a core, advertised action, not a
degraded one.

**Fix.** Added `public.create_organisation(org_name text)` - `SECURITY DEFINER`,
does both inserts and returns the row itself, matching the signup trigger's own
pattern instead of duplicating the two-step version under a regular RLS-scoped
connection. `org_repo.create()` is now a single call to it. Verified against the
real database: the happy path succeeds, and a second, unrelated deliberate error
afterward confirmed the connection pool stays healthy (see #29).

### #29 - An error inside `as_user()` masked itself with a connection-cleanup crash

**S1 · FIXED · backend · `app/database/session.py`**

While reproducing #28, the API's logs showed _two_ chained tracebacks: the real
`InsufficientPrivilegeError`, immediately followed by
`asyncpg.exceptions.InFailedSQLTransactionError: current transaction is aborted,
commands ignored until end of transaction block` - raised from inside
`Database._release()`'s own cleanup call.

**Root cause.** `as_user()` and `anonymous()` ran their body in a `try/finally`,
unconditionally calling `_release()` (a `SET LOCAL role = 'postgres'` reset) even
when the body raised. Once any statement inside the transaction fails, Postgres
puts the whole transaction into "aborted" state and refuses to run anything else in
it except `ROLLBACK` - so the cleanup's own `SET LOCAL` command always failed too,
on _every_ error from _any_ route using `as_user()`, not just this one.

**Impact.** Any failure inside an `as_user()`-scoped block - not just RLS
violations, any exception - got a second, unrelated `InFailedSQLTransactionError`
chained onto it in the logs, obscuring the actual cause. Severity is S1 rather than
cosmetic because the transaction's own `ROLLBACK` (triggered by
`connection.transaction()`'s exit) already discards the `SET LOCAL` role safely on
its own - the explicit cleanup call was not just redundant on the error path, it was
actively the thing crashing.

**Fix.** Skip the explicit `_release()` call on the error path - it only runs after
`yield` returns normally now, not in a `finally`. Verified the connection pool stays
usable immediately after a real error is raised through `as_user()`.

**Depends on:** discovered while fixing #28.

### #30 - The "Needs a person" queue and the dashboard's own disposition count disagreed

**S2 · FIXED · web · `web/lib/app-store.tsx`**

The dashboard's own outcome-distribution donut showed "3 need a person," but the
"Needs a person" panel on the same page - and the dedicated `/app/escalations`
page - both said "Nothing needs you," for the exact same data.

**Root cause.** `lib/lamp.ts` (the single documented source of truth for "what does
each disposition mean visually") maps _both_ `escalated` and `unreachable` to the
flare ("Needs a person") lamp state - deliberately, since a contact who couldn't be
reached also needs a human to decide what happens next. But `app-store.tsx`'s
`escalations` list - which both the dashboard panel and the dedicated page render
from - filtered for `disposition === "escalated"` only, silently excluding
`unreachable`. Two definitions of the same phrase, drifting apart.

**Fix.** `escalations` now filters by `lampForOutcome(outcome).state === "flare"`,
deriving from the one module that's supposed to own this mapping instead of
duplicating its logic.

**Also fixed alongside this investigation (found via the browser console, not code
review):** `components/ui/area-chart.tsx` keyed its SVG groups by the narrow weekday
label (`"S"`, `"T"`, …), which repeats within any 7-day window and triggered a React
duplicate-key warning - keyed by index instead.

### #31 - Switching organisations never actually took effect

**S1 · FIXED · web · `web/lib/hooks/use-session.ts`**

Found by real browser verification (Playwright, now available in this environment,
against a throwaway seeded account) - not by code review, which had read this file
earlier in the same session and missed it. Creating a second organisation and
clicking it in the sidebar switcher updated the switcher's own `localStorage` pin
correctly and even re-fetched `/api/v1/me` - but the profile that came back kept
reporting the _original_ organisation as `active`, every time, including across a
full page reload.

**Root cause.** Every other authenticated call in the app goes through
`lib/api.ts`'s `authReq()`, which attaches both the bearer token and an `X-Org-Id`
header read from `localStorage`. `useSession()` - the one hook that actually drives
what "the active organisation" means everywhere in the UI - never went through that
chokepoint: it built its own `fetch("/api/v1/me")` call with only an `Authorization`
header, a violation of `CLAUDE.md`'s "`fetch()` outside `lib/api.ts`" rule that had
gone unnoticed because it doesn't error, it just silently never sends the header the
backend needs to resolve anything but the caller's default (earliest-joined)
organisation.

**Impact.** The org switcher looked and behaved like it worked - the dropdown
closed, a toast could fire, the sidebar re-rendered - but `active.org_id` server-side
never changed, so every page that reads `profile.active` (which is most of them)
silently kept acting on the wrong organisation after a switch. This is likely a real
contributor to the earlier, separately-reported confusion about "which dropdown am I
even on" - switching plainly not doing anything is worse than a confusing label.

**Fix.** `useSession()`'s fetch now reads `ACTIVE_ORG_KEY` from `localStorage` and
attaches `X-Org-Id` itself, matching `authHeaders()`'s behaviour. Verified end to end
against the real API and database: created a second organisation, switched to it,
confirmed via the network tab that `/api/v1/me` now returns the new `active.org_id`,
and confirmed it survives a full reload.

**Note on verification method:** a Playwright MCP server became available partway
through this session (previously reported as unavailable). This bug was found and
confirmed fixed using it, seeded against a throwaway test account created via the
Supabase admin API (per `SUPABASE_SETUP.md` §7's documented pattern) and deleted
afterward, along with the organisations it created. No pre-existing data was touched.

### IA change - Organisation and Team moved out of Settings, into the sidebar switcher

Not a bug: a requested restructuring. "Organisation" and "Team" were two of six
Settings tabs; both are about _which workspace_ you're in, not the product's own
configuration (Safety, API keys, Integrations, Billing), and the sidebar org
switcher already existed one click away. They're now a dialog
(`components/app/org-settings-dialog.tsx`) opened from "Organisation settings" in
that switcher, and from "Manage" in the dashboard's team popover. `/app/settings`
and `/app/settings/team` redirect to `/app/settings/safety` so existing links (the
nav item, the user menu's "Settings" entry) still resolve to something real instead
of a route that no longer has a matching tab.

Also fixed in this pass: the sidebar switcher always rendered an organisation's
initial letter even when a logo had been uploaded (`org_logo_url` was resolved but
never rendered) - added an `OrgMark` that shows the real logo when one exists.
Dialog overlays across the app now blur the content behind them
(`backdrop-blur-[3px]`), and the empty dashboard no longer shows a separate
"Getting Started" checklist screen - it renders the normal dashboard layout, whose
panels already had honest per-section empty states.

---

## Iteration 7 - 2026-08-07 · settings persistence, safety multi-tenancy, live-browser sweep

Prompted by user reports that Settings → Safety pointed at an API that didn't exist,
that the org/team screen and org-switcher UX needed reworking, and a general request to
verify wiring end to end. Two of these (#32, #34) were found while building the safety
persistence feature, not from a report - reading `rate_limit.py` and the old inline email
HTML to wire real persistence surfaced a live cross-tenant bug and an injection bug that
predated this iteration. #35 was found by live Playwright verification against a real
seeded account, the same method that caught #31 last iteration.

### #32 - The rate limiter and daily budget were shared across every organisation

**S1 · FIXED · backend · `app/core/rate_limit.py`, `app/api/v1/routes/runs.py`**

`RateLimiter` keyed its per-window bucket by client IP and kept exactly one
process-global `deque` for the daily budget (`self._today`) - a design left over from
when the dashboard was an unauthenticated public demo with one shared budget. Once every
caller became a signed-in member of a real organisation, this stopped being a quirky demo
limit and became a multi-tenancy bug: `CLAUDE.md` non-negotiable #1 requires every
org-scoped resource to be scoped by org, and a shared daily call budget across every
tenant on the deployment is exactly the kind of resource that has to be.

**Impact.** Any organisation could exhaust another's ability to place calls just by
running its own campaigns - the busier organisation would trip the "shared daily demo
budget is used up" message for a completely unrelated tenant with calls left in its own
plan. Two organisations behind the same NAT/office IP also shared the per-window burst
limit, throttling each other for an unrelated reason.

**Fix.** `RateLimiter.check()`/`release()`/`snapshot()` are now keyed by an arbitrary
`key` string - callers pass `str(org_id)`, not an IP - with separate `_windowed` and
`_daily` dicts per key instead of one shared `_today` deque. `check()` also accepts
per-call overrides (`rate_limit_calls`, `rate_limit_window_seconds`, `daily_call_budget`)
so an organisation's own `org_safety_settings` row can raise or lower its own limits
without affecting anyone else's. `start_run()` resolves the effective settings once via
`resolve_safety_settings()` (see #33) and passes both the org-keyed lookup and the
override values through.

**Verified.** `test_ratelimit.py` rewritten around per-key isolation:
`test_daily_budget_is_not_shared_across_keys` and `test_snapshot_is_per_key` both assert
two organisations' buckets never observe each other's calls.

**Depends on:** #1 (fixed) for `org_id` to key against. Partly closes #5 - see that
entry for what's still open (in-process, not durable across a restart).

### #33 - Safety settings had no real persistence behind them

**S2 · FIXED · backend + web · `app/database/repositories/safety_settings.py`, `app/api/v1/routes/safety.py`, `apps/web/app/(app)/app/settings/safety/page.tsx`**

Settings → Safety rendered the deployment's env-var config (`CALLFLOW_MAX_CALLS_PER_RUN`,
`CALLFLOW_ALLOWLIST`, etc.) read-only, with a "Save" action that only showed a toast - no
`PATCH` route existed, and nothing about an organisation's safety configuration could
actually be written anywhere. The page pointed at `/api/v1/safety`, which returned 404.

**Impact.** Violates `CLAUDE.md` non-negotiable #9 - the settings screen implied a
working save action that did nothing. An owner who raised their per-run ceiling or added
a number to the allowlist through the UI would find it silently reverted (because it was
never persisted) the next time they loaded the page.

**Fix.** New `org_safety_settings` table (migration `202608072200_org_safety_settings`,
`b9d4f1a6c832`) - one row per org, every column nullable so "not set" means "use the
deployment default," RLS scoped the same way as every other tenant table (select: any
member; insert/update: owner/admin only, matching `has_org_role`). New
`GET/PATCH /api/v1/safety` route, and `EffectiveSafety`/`resolve_safety_settings()` in
`app/domain/safety.py` - one pure-merge function so display and enforcement (#32) can
never resolve two different answers for the same org. `check_dial_allowed()` gained
optional `max_calls_per_run`/`allowlist` params (defaulting to `config.*` for backward
compatibility) so the merged values flow all the way to the actual dial gate, not just
the rate limiter.

**Verified.** `npm run type-check`/lint/build clean; backend tests updated for the new
`check_dial_allowed()` signature; manual save/reload round-trip confirmed the value
persists across a page reload.

### #34 - The invitation email interpolated org name and role into HTML unescaped

**S2 · FIXED · backend · `app/integrations/email/resend.py`, `app/integrations/email/templates.py`**

`EmailGateway.send_invitation()` built the email body with an f-string:
`f"<p>You've been invited to join <strong>{org_name}</strong> ..."`. `org_name` is a
user-controlled value - any org owner/admin can set it via `PATCH
/api/v1/organisations/me` - with no escaping before it reached a raw HTML email body sent
to a third party's inbox.

**Impact.** An organisation's own display name is attacker-controlled input reaching an
uninvolved invitee's email client as raw HTML: at minimum, arbitrary styling/link
injection (e.g. a fake "urgent" banner, or an `<a href>` visually overlapping the real
accept link) and, depending on the recipient's mail client's HTML sanitisation, worse.
This is exactly the class of bug CLAUDE.md's "no PII/no unescaped user content across a
trust boundary" spirit exists to prevent, just not one the file list had previously
called out.

**Fix.** Extracted into `app/integrations/email/templates.py`'s `invitation_email()`,
which runs `html.escape()` on every interpolated value (`org_name`, `role`) before
building the table-based HTML body. `resend.py` now calls it instead of building HTML
inline.

**Verified.** No test previously existed for this path; the fix is structural (escaping
happens once, in the one function that builds the HTML) rather than something to unit
test per call site.

### #35 - A stale pinned organisation produced an unrecoverable 403 and a fake service-down error

**S2 · FIXED · web · `apps/web/lib/hooks/use-session.ts`**

Found live: signing in as a second, unrelated test account in the same browser context
as a since-deleted first account. `localStorage['callflow.active_org_id']` still held the
first account's org id from an earlier session. `useSession()` sent that dead id as
`X-Org-Id` on every `/api/v1/me` call, which correctly 403'd ("not a member of that
organisation") - but nothing on the client ever cleared the stale pin or retried without
it, so the failure was permanent for that browser until someone manually cleared storage.
The resulting UI showed "The service didn't respond," which is doubly wrong: the service
responded correctly, and the org switcher - the only UI that could fix this - never
renders, because loading the profile had already failed.

**Impact.** Anyone reusing a browser profile across a deleted/left organisation (a very
normal thing to do in dev, QA, or after leaving a team) got permanently locked out with a
message that pointed at the wrong cause and offered no recovery path other than knowing
to open dev tools and clear `localStorage` by hand.

**Fix.** `load()` in `use-session.ts` now retries once, with no `X-Org-Id` header, if the
first attempt 403's while a pinned org id was sent - clearing the dead pin from
`localStorage` first so the retry (and every subsequent load) falls back cleanly to the
server's own default organisation for that user.

**Verified.** Live Playwright reproduction: seeded a second throwaway account via the
Supabase admin API in a context that still held the first (deleted) account's org pin,
confirmed the bug reproduced exactly as described, applied the fix, and confirmed the
same session now lands on a normal dashboard with the onboarding flow for the new
account's own org. Test account and its org deleted afterward (`SUPABASE_SETUP.md` §7).

**Related, not duplicate:** #31 (last iteration) was the org _switcher_ not taking
effect because `useSession()` didn't attach `X-Org-Id` at all. This bug is a different
failure mode in the same function, introduced by that very fix - once `useSession()`
started attaching the pinned org id, a _stale_ pin became newly capable of producing a
hard failure with no fallback.

### #36 - Contact grid's error was shown on the wrong column and on untouched blank rows

**S3 · FIXED · web · `apps/web/lib/contacts.ts`, `apps/web/components/app/contact-grid.tsx`**

`ParsedRow` carried a single `error` string with no indication of which field it
described. `ContactGrid` rendered every row's error under the **phone** column
unconditionally, regardless of whether the actual problem was a missing name, a missing
phone, or an invalid phone. Separately, a freshly-added blank row (all three fields
empty) was `valid: false` from the moment it existed, so it rendered in the flagged/error
style before a person had typed anything.

**Impact.** Someone who left the _name_ blank saw a red-bordered phone field and "Add a
name for this row" printed underneath the phone input - attributing the error to the
wrong cell - while every new blank row appeared broken on sight, before there was
anything to fix.

**Fix.** `validateRow()` now returns an `errorField: "name" | "phone"` alongside the
message; `ContactGrid` routes the `invalid`/`error` props to whichever column actually
owns the problem. Row-level flagging now requires `touched` (any of name/phone/note
non-empty) in addition to `!valid`, so a blank row added via "Add a row" renders neutrally
until someone starts typing into it.

**Verified.** `npm run type-check`/lint pass; manually traced both complaint screenshots
against the new logic - a name-only-missing row now flags the name cell, and a freshly
added blank row no longer shows error styling.

### #37 - Voice engine errors were not normalised into an internal taxonomy

**S3 · FIXED · backend · `app/domain/entities.py`, `app/integrations/voice/engine.py`, `app/services/campaign_runner.py`**

`CampaignRunner._dial()`'s failure handling was one bare `except Exception as exc`,
storing `f"{type(exc).__name__}: {exc}"` as the outcome's `error` field and always
setting `Disposition.UNREACHABLE` - an auth failure, an invalid number, a rate limit, and
a network timeout all produced the exact same disposition and a Python exception string
as the user-facing reason. This is the gap `CLAUDE.md`'s Substitutability section
describes directly: "retry policy keys off the internal name, never a vendor error
string" - there was no internal name at all.

**Impact.** No way to distinguish "this number will never work, stop retrying" from
"this is transient, try again" anywhere downstream of a failed call - every failure read
identically to an operator. The raw exception string could also leak vendor-internal
detail into a stored outcome with no normalisation.

**Fix.** New `DialFailure` enum (`invalid_number`, `rate_limited`,
`insufficient_balance`, `policy_violation`, `unauthorized`, `provider_unavailable`,
`timed_out`, `internal`) in `app/domain/entities.py`. `engine.py`'s new
`classify_error()` maps CALL-E's own documented error codes (CALLE.md §4) onto it,
falling through to `internal` for anything unmapped rather than raising - fail-closed,
per `CLAUDE.md` #2, so an unrecognised code is never treated as a known-safe-to-retry
one. `campaign_runner.py` now catches `(EngineAPIError, EngineTimeoutError)` specifically,
classifies, and sets `Disposition.RETRY` for the three genuinely transient failures
(`rate_limited`, `provider_unavailable`, `timed_out`) and `Disposition.UNREACHABLE` for
the rest; a separate fallback `except Exception` (unclassified/network errors) stores
`DialFailure.INTERNAL` instead of the raw exception string.

**Verified.** `test_orchestrator.py` extended with a `FailingGateway` fixture and 4 new
tests covering the retryable/non-retryable split and the fallback path.

### #38 - The runs list and dashboard never updated while a run was in flight

**S3 · FIXED · web · `apps/web/lib/app-store.tsx`**

Nothing outside the dedicated run-detail page polled for run status. The dashboard's
"Recent runs" panel and `/app/runs` both rendered from the same store slice, fetched once
on load - so a run that was still dialling when the page opened showed "running"
indefinitely until a manual refresh, even after it had actually finished.

**Impact.** Matches a user report of the dashboard looking "stuck" after a run - not a
data bug (the backend had the right status the whole time), but a staleness bug that
looked like one, on the page most likely to be left open while a run is live.

**Fix.** Self-rescheduling `setTimeout` poll (`LIVE_POLL_MS = 4000`) that re-fetches the
run summary list only while at least one run in it has `status === "running"`, and stops
rescheduling once nothing is non-terminal - so it doesn't poll forever on an idle
dashboard.

**Verified.** `npm run type-check`/lint pass; traced the effect's cleanup to confirm the
timeout is cleared on unmount and doesn't leak across navigation.

### IA change - Organisation and Team moved back out to a dedicated page

Reverses the iteration-6 IA change (org/team as a dialog opened from the switcher) at
explicit user request: `/app/organisation` is now a real route (`Suspense`-wrapped for
`useSearchParams()`), holding the same organisation-details/danger-zone and team panels
that previously lived in `org-settings-dialog.tsx` (now deleted). The sidebar gained an
"Organisation" nav item; `/app/settings` and `/app/settings/team`'s redirects, and the
overview page's "Manage" link, all point at the new route instead of opening the dialog.
"New organisation" is also a two-step page (`/app/organisation/new`) rather than a small
popup - name first, then an optional logo upload, which has to be two steps because
Supabase Storage's RLS path-prefix scoping (`{org_id}/...`) makes uploading a logo
architecturally impossible before the organisation (and its id) exists.

---

## Iteration 8 - 2026-08-07 · dashboard flow/copy/wiring audit

A product-manager-style pass over `/app/campaigns`, `/app/runs`, `/app/escalations`,
`/app/contacts`, and the dashboard: tracing every button to what it actually calls,
reading empty-state and toast copy for anything generic or misleading. Scoped to flow,
copy, and wiring only - colour, typography, and badges are a separate, concurrent pass.

### #39 - "Stop run" contradicted itself and was a dead duplicate of "Pause run"

**S2 · FIXED · web · `apps/web/app/(app)/app/runs/[id]/page.tsx`**

The live run page had two controls: "Pause run" (`setPaused(true)`, which only stops
this screen's polling - `useRunPoll`'s effect returns early while `paused`) and a
separate red "Stop run" button that opened a confirmation dialog. That dialog's own
description read "Contacts not yet reached will not be called" - but confirming it ran
`setPaused(true)` (the _exact same_ state change as "Pause run") and then fired a toast
titled "Updates stopped, run not cancelled" whose body said the opposite: "Remaining
calls will still be placed."

**Impact.** Two contradictory claims about the same action, one right after the other,
in the one screen an operator watches while real people are being called. The dialog
promised a stop; the toast fired a second later admitted nothing had stopped. The button
also did nothing "Pause run" didn't already do - there is no cancel-run endpoint
anywhere in the backend (confirmed: no `stop`/`cancel` route or `api.ts` method exists),
so "Stop run" was a second, more alarming-looking way to trigger the same pause, dressed
up with false confirmation copy.

**Fix.** Removed the "Stop run" button and its dialog entirely. "Pause run"/"Resume
updates" - already honest, already labelled correctly, already the only thing either
control actually did - is now the only control. A comment at the call site notes there
is no way to cancel an in-flight run yet, so a future real cancel endpoint doesn't get
silently absorbed back into "pause."

### #40 - The dashboard's "Recent runs" panel showed the raw campaign slug instead of its name

**S3 · FIXED · web · `apps/web/app/(app)/app/page.tsx`**

`/app/runs` resolves each run's `campaign_id` to the campaign's actual name via a
`campaignName()` helper backed by the `campaigns` list. The dashboard's own "Recent
runs" panel, built from the same `RunSummary` data, rendered `run.campaign_id` - the
slugified id (`create_campaign` slugifies the name server-side, e.g.
`holiday-enquiry-followup`) - directly, because the component never pulled `campaigns`
out of `useAppStore()` in the first place.

**Impact.** The same run showed its readable name on `/app/runs` and a cryptic slug on
the dashboard one click away - confusing on its own, and actively misleading for any
campaign name that doesn't slugify predictably.

**Fix.** Dashboard now destructures `campaigns` from the store and resolves the name the
same way, falling back to the id if the campaign was since deleted (matching the
existing fallback pattern on `/app/runs`).

### #41 - The run composer showed a "Credits" estimate with no backing credit system

**S3 · FIXED · web · `apps/web/app/(app)/app/runs/new/page.tsx`**

Step 3 of the run composer showed two `Estimate` chips side by side: "Contacts" and
"Credits," both rendering the identical value (`validRows.length`). There is no credit
deduction, no credit balance check, and no low-balance warning anywhere in the
run-start path (`app/api/v1/routes/runs.py` has no reference to credits at all) - the
only real per-org monetary field, `credit_balance_paise`, is described in its own model
comment as "a derived cache of credit_ledger once F36 lands." No settings or billing
page in the dashboard shows a balance to compare this number against either.

**Impact.** A specific-looking number labelled "Credits" right before the button that
places real calls implies this run will consume that many credits from a real balance -
a claim about cost and consumption the product does not yet back with anything. Smaller
in impact than the other two findings this iteration because it never blocks or
misleads about whether the run itself succeeds, but it is the same shape as the
calling-window false claims (#20): a specific number presented as fact where nothing
behind it is real yet.

**Fix.** Removed the "Credits" chip. "Contacts" already shows the same number honestly,
as what it actually is - how many contacts this run will dial.

### Not re-reported (already logged)

`#7` (escalation resolution is component state, `web/components/app/escalation-card.tsx`)
is confirmed still open - no persistence endpoint exists for it. Left the underlying
bug as-is (a real fix needs an `escalations` table, out of scope for a copy pass) but
fixed the one part that was actively dishonest: "Mark resolved" fired a `tone: "success"`
toast reading "Marked resolved," indistinguishable from a toast confirming a real save,
while its sibling buttons in the same card ("Call back myself," "Reassign") already use
`tone: "info"` with an explicit "isn't wired up yet" disclosure for the same kind of gap.
"Mark resolved" now matches them: `tone: "info"`, "Hidden for now, not saved," with a
body stating it reappears on reload.

### #42 - A CSS comment containing a literal `*/` silently broke the production build

**S2 · FIXED · web · `apps/web/app/globals.css`**

The monochrome-glass treatment (below) added a comment block documenting the new
`.panel-glass*` utilities. Its prose read `Built only from --surface*/--rule* tokens` -
which contains the two-character sequence `*/` in the middle of a sentence, and CSS
comments have no escape for that: the parser reads the first `*/` it finds as the
comment's end, regardless of intent. Everything from that point to the block's real
closing `*/` (nine more lines of prose) was parsed as CSS, which failed with
`CssSyntaxError: Unknown word tokens`.

**Impact.** `npm run lint` and `npm run type-check` both passed - neither parses CSS -
so this shipped past both gates invisibly. Only `npm run build` (Turbopack's real
PostCSS pass) caught it, with a build-breaking error that would have blocked any
deploy. Found by running the full verification suite, including the build, rather than
stopping at lint/type-check green.

**Fix.** Reworded the comment to drop the literal `*/` substring (spelled out "surface
and rule tokens" instead of the shorthand). Re-ran `npm run build`: compiles clean, all
47 routes generate.

**Also found in the same review pass:** `apps/web/DESIGN_NOTES.md` still described the
now-removed "Stop run" button (#39) as current, present-tense behavior - exactly the
doc-drift `DESIGN_NOTES.md` §5 itself warns against ("update the row the moment a
surface moves... the same turn as the code change"). Updated to describe the removal
and point at #39 instead of narrating dead UI.

## Visual and architecture work landed this round (not bugs)

Three frontend passes plus one backend refactor, run as four parallel sub-agents plus
the orchestrating session, per explicit user request to parallelise independent phases
of the voice-agent-platform roadmap (`VOICE_AGENT_PLATFORM.md`) and the still-open
visual-polish backlog:

- **Monochrome-glass panels.** `Panel` and the runs `DataTable` now render via new
  `.panel-glass`/`.panel-glass-sunken`/`-flat`/`-interactive` utilities in
  `globals.css` - frosted translucency (`color-mix` + `backdrop-filter: blur`) built
  only from existing greyscale surface/rule tokens, reaching every `Panel` call site
  (campaigns, escalations, contacts, settings, safety, campaign editor) for free. Per
  the user's earlier explicit choice of "monochrome glass" over vibrant glassmorphism -
  the five lamp colours remain the only colour in the product.
- **Status badges.** New `RunStatus`/`lampForRunStatus()` in `lib/lamp.ts` replaces raw
  lowercase status strings (`"running"`, `"failed"`) with humanised labels and a pulsing
  lamp for in-progress runs, on both `/app/runs` and `/app/runs/{id}`. `LampBadge` itself
  gained more padding/depth so it reads as a designed pill rather than a bare dot.
  Deliberately did **not** add pulse to the `in_flight` disposition lamp, since
  `countLamps()`/strip summaries key "pulsing + brass" specifically to mean "queued for
  retry" - confirmed this holds against the real code in the code-review pass below.
- **Profile page chrome.** `/app/profile` no longer renders the full sidebar/topbar -
  `AppShell` gained a route-gated minimal mode (a `MinimalTopBar` with just a close
  button, `router.back()` with a history-length-aware fallback to `/app`) for the one
  page in the product meant to be a focused, closeable task rather than a permanent
  destination.
- **Header/copy pass.** Every `/app/*` page gained a concrete one-line description
  under its heading (dashboard, campaigns, runs, contacts, organisation, settings,
  profile), replacing bare or duplicated headings with specific, non-generic copy.
- **`VoiceProvider` protocol (P1 of `VOICE_AGENT_PLATFORM.md`).** New
  `app/integrations/voice/protocol.py`: a structural `VoiceProvider` Protocol,
  `VoiceCapability` enum, and `NotImplementedForProvider`. `EngineGateway` (CALL-E) now
  conforms - `supports()` declares `STRUCTURED_EXTRACTION`/`LIVE_EVENTS` true,
  `RECORDING`/`CUSTOM_AGENT` false; `cancel_call()` raises rather than faking one,
  confirmed against the real `calle` SDK (`create`, `create_and_wait`, `get`,
  `list_events`, `wait_for_result` - no cancel method exists). Deliberately scoped as a
  true no-behavior-change refactor: no async conversion, no normalised return type - see
  `VOICE_AGENT_PLATFORM.md` §1 for why both are explicitly deferred rather than guessed
  from a single (CALL-E-only) data point.

**Verification for the whole batch:** backend 93 tests pass, `ruff check` clean;
frontend `type-check`/`lint`/`build` all clean (one pre-existing, unrelated `<img>`
lint warning in `app-nav.tsx`). An independent code-review pass over this round's diff
found one issue (#42's `DESIGN_NOTES.md` drift) and confirmed the rest - the
`AppShell` route-matching, the lamp/pulse interaction, the glass CSS at its real call
sites, and `cancel_call()`'s lack of any existing caller - by reading the actual code
paths rather than trusting the sub-agents' own descriptions.

## Iteration 9 - 2026-08-08 · critical privilege-escalation fix (R5 audit)

### #43 - Admin could self-promote to Owner and take over the account

**S1 · FIXED · backend · `app/api/v1/routes/organisations.py`, `app/auth/permissions.py`,
`app/database/repositories/organisations.py`, migrations `c2f7a9d15e63` and
`d94b2c8f1a67`**

`PATCH /api/v1/organisations/me/members/{member_user_id}` and
`POST /api/v1/organisations/me/invitations` were guarded only by
`Permission.TEAM_SET_ROLE`/`TEAM_INVITE` - which Admin already holds, same as Owner.
Neither endpoint checked _which_ role was being granted: `set_member_role` accepted any
role in `VALID_ROLES` (including `"owner"`) and ran an unconditional
`update ... set role = $3`; `invite` would happily create a pending invitation straight
into `"owner"`. RLS mirrored the same gap - `memberships_update`/`memberships_insert`/
`invitations_insert` all allowed `owner`/`admin` equally, with no restriction on the
_target_ role.

**Impact.** Combined with the existing last-owner guard (which only blocks removing the
organisation's _last_ owner, not demoting or removing a non-last one, `#13`/`protect_last_owner`),
an Admin could: `PATCH .../members/{self}` with `{"role": "owner"}` → now a second owner →
demote or remove the original owner → full, unilateral account takeover from an Admin
seat, with no Owner action required at any step. Confirmed directly against the real
route handlers and the real database rather than inferred from reading the permission
matrix - reading the matrix alone would have said this was fine, since Admin legitimately
holds both permissions involved; the missing check was on the value, not the permission.

**Fix, part 1 - the granted-role check** (migration `c2f7a9d15e63`). Two layers, per
CLAUDE.md §4b's stated model of an API check _and_ an RLS check, neither alone:

- **API.** `app/auth/permissions.py` gains `can_grant_role(caller_role, target_role)`:
  Owner may grant any role, including owner itself (that's how ownership transfers);
  every other role may only grant a role _strictly_ below its own - Admin gets
  operator/viewer, never admin or owner, not even to itself.
  `app/api/v1/routes/organisations.py`'s `_ensure_can_grant()` calls it in both
  `set_member_role` and `invite`, before either reaches the database, raising `403`.
- **RLS (defense-in-depth).** `public.can_grant_role()` (SQL mirror) and
  `public.current_org_role()` (a new `SECURITY DEFINER` helper returning the caller's own
  role, alongside `has_org_role`), added to `memberships_update`, `memberships_insert`'s
  owner/admin branch, and `invitations_insert`.

**A security-review pass over that fix found three more gaps in the same policy family,
one of them Critical on its own** - closed together in migration `d94b2c8f1a67`:

- **Critical - the invitee could still self-escalate a pending invite's role.**
  `invitations_update_own` (pre-existing, migration `202608061530`) lets the invitee
  update _any column_ of their own pending invitation, including `role`, checking only
  that the email matches; the table grant was column-unrestricted. An invitee legitimately
  invited as `viewer` could run `update invitations set role = 'owner' where token = …`
  directly against their own row - no Admin or Owner action required at all - and then
  `accept()` would seat them as `owner`. **Column-level `GRANT` is the actual fix:**
  `authenticated` can now only ever write `accepted_at` on `invitations`
  (`revoke update ...; grant update (accepted_at) ...`); every other column requires the
  already role-gated `invitations_insert`/`_delete` paths instead.
- **`memberships_insert`'s invitation branch didn't pin `user_id`.**
  `has_valid_invitation(org_id, role)` only checked that _the caller_ held a matching
  pending invitation - never that the `user_id` being inserted was the caller's own. A
  caller with any valid invitation could seat an arbitrary other `user_id`. Added
  `user_id = current_user_id()` to that branch.
- **`can_grant_role` alone never checked the target member's _current_ role.** In an org
  with two Owners, an Admin could still demote or remove one of them -
  `memberships_update`/`memberships_delete` looked only at the _new_ value being written,
  never the existing row. New `can_act_on_member()` (API: `app/auth/permissions.py`,
  called from both routes via `_ensure_can_act_on()`, using a new
  `org_repo.get_member_role()` lookup; RLS: `public.can_act_on_member()`, same rank rule,
  added to both policies' `USING` clause) closes this. Self-targeting is explicitly
  exempted in both layers - an Admin can still step themselves down.

**What "closed" means precisely, so this doesn't overstate itself:** reusing
`can_grant_role`'s exact rank rule for `can_act_on_member` is a deliberate, symmetric
choice, and it is _broader_ than the two-Owner scenario above - an Admin can now only
update or remove a member whose current role is operator or viewer, which also means an
Admin can no longer act on _another Admin's_ row, not only an Owner's. Disclosed here
rather than left implicit. No residual gap is known open in this policy family as of this
fix; the one thing found but _not_ fixed here, because it's an unrelated pre-existing
bug rather than a security gap, is logged separately as `#44`.

**Verification.** Every layer proven by calling the real code path, not the permission
matrix: `tests/test_organisations_routes.py` (18 tests) calls the actual
`set_member_role`/`invite`/`remove_member` route functions directly and asserts
`HTTPException(403)` for every denial (granted-role _and_ target-role), plus
non-regression cases for Admin's real grants/actions and Owner's full range.
`tests/test_rls_isolation.py` (28 tests, up from 16 before this fix) proves the same at
the RLS layer against the real database. Confirmed denial tests actually depend on the
fix by reverting the relevant check(s), re-running (failures confirmed - either a raised
exception disappearing, or an update/delete silently affecting zero rows instead of being
blocked), then restoring - done for both migrations independently (`c2f7a9d15e63`'s and
`d94b2c8f1a67`'s checks), not just once. `pytest -q`: 144 passed. `ruff check app tests`:
clean. One test (`test_admin_cannot_promote_a_member_to_owner_via_direct_update`) was
retargeted from an owner→owner no-op to a genuine operator→owner promotion attempt after
the target-role fix changed its failure mode from a raised exception to a silent
zero-row update - it was never testing what its name claimed.

**Also found in the same review pass, not a bug:** the `alembic_version` bookkeeping on
the dev database used for verification was stale (several already-applied migrations
unrecorded), and several ad-hoc verification runs against a deliberately-downgraded
schema left stray test fixture rows behind (rows whose manual, non-fixture cleanup lines
never ran because the test's own assertion failed first) - both cleaned up; no product
code was involved in either.

### #44 - Re-inviting an already-invited email fails under RLS

**S3 · FIXED (as a side effect of `#45`) · backend ·
`app/database/repositories/organisations.py` (`create_invitation`), migration
`202608061530`, closed by migration `e15f3d9a2c78`**

Found while verifying `#43`'s invitation-column-lock fix, unrelated to it.
`create_invitation()`'s `insert ... on conflict (org_id, lower(email)) where accepted_at
is null do update set role = excluded.role, ...` is meant to let re-inviting the same
pending address refresh the existing invitation instead of erroring. Postgres applies a
table's **UPDATE** row-security policies (not its INSERT policies) to the `DO UPDATE`
branch of an upsert. The only UPDATE policy on `invitations` is `invitations_update_own`,
scoped to the invitee's own email - so when the _inviter_ (an Owner/Admin, a different
email) is the one re-inviting, the conflict path fails RLS outright. Confirmed directly:
a real Owner re-inviting the same pending email raised
`asyncpg.exceptions.InsufficientPrivilegeError: new row violates row-level security
policy (USING expression) for table "invitations"`.

**This entry's original stated fix direction - "needs an Owner/Admin-scoped UPDATE
policy" - turned out to be insufficient on its own once `#43`'s finding 1 landed**: a
plain UPDATE policy does nothing to satisfy the _column-level_ `GRANT` that finding 1
correctly locked down to `accepted_at` only (a policy is evaluated only after a
column-privilege check already passes). Fixing `#45` - moving the whole upsert into a
`SECURITY DEFINER` function that enforces `has_org_role`/`can_grant_role` itself rather
than relying on a table policy at all - fixed this at the same time, since the function
runs with the definer's own privileges and never touches the RLS-scoped UPDATE path in
the first place. Confirmed with a real re-invite through `org_repo.create_invitation()`
(`test_owner_can_refresh_a_pending_invitation_through_the_repository`,
`tests/test_rls_isolation.py`) and end-to-end through the actual `invite()` route
function against a real, unmocked database connection.

### #45 - `#43`'s own invitation-column-lock fix broke inviting anyone at all

**S1 · FIXED · backend · `app/database/repositories/organisations.py` (`create_invitation`),
migration `e15f3d9a2c78`**

`#43` finding 1's fix (`revoke update on invitations from authenticated; grant update
(accepted_at) ...`, migration `d94b2c8f1a67`) closed the invitee-role-mutation hole
correctly, but `create_invitation()`'s `insert ... on conflict (...) do update set
role = excluded.role, token = ..., invited_by = ..., expires_at = ..., created_at = ...`
needs UPDATE privilege on every column in that `do update set` list for the _entire
statement_ to plan - checked once at executor start, regardless of whether a conflict
actually occurs at runtime. A first-time invite (no conflict possible) failed identically
to a re-invite. Caught by a second-pass security review, which reproduced it live against
the dev database with a fresh, non-conflicting email:
`InsufficientPrivilegeError: permission denied for table invitations`.

**Impact.** `POST /api/v1/organisations/me/invitations` - the only way to add a teammate
who doesn't already have an account - bare-500'd for every single call, reachable from
the UI via `api.inviteMember`. S1 because it is a total, silent block on a core,
advertised action (same severity class as `#28`), introduced by a fix for a _different_
S1, on the very next round.

**Fix.** Re-granting broader UPDATE was not an option - that reopens finding 1 verbatim.
Moved the upsert into `public.create_or_refresh_invitation()`, a new `SECURITY DEFINER`
function (same shape as `create_organisation()`, migration `a7c2e5f9b184`): it does the
write with the function owner's privileges rather than the caller's, and - because that
means it bypasses both RLS and the column grant - enforces the equivalent checks itself
first: `has_org_role(target_org, ['owner','admin'])` and
`can_grant_role(current_org_role(target_org), target_role)`. `authenticated` keeps its
`accepted_at`-only grant on the table; nothing about finding 1 changes.
`org_repo.create_invitation()` now calls this function instead of the raw upsert.

**Also fixed `#44`** as a consequence - see that entry.

**Verification.** Reproduced the regression live _before_ fixing it (a fresh, non-
conflicting email failed with the exact error above), confirmed the fix live after
(first-time invite succeeds, re-invite/refresh succeeds, an Admin inviting as `owner`
still correctly fails). New tests hit the real, unmocked code path - the exact coverage
gap that let this regression through undetected in the first place, since
`test_admin_can_still_invite_as_operator_or_viewer` mocks `create_invitation()` entirely:
`test_owner_can_create_a_real_invitation_through_the_repository`,
`test_owner_can_refresh_a_pending_invitation_through_the_repository`, and
`test_admin_cannot_create_an_owner_invitation_through_the_repository`
(`tests/test_rls_isolation.py`), all calling `org_repo.create_invitation()` directly
against the real database. Confirmed dependence on the fix: all three failed against the
pre-fix schema (`alembic downgrade d94b2c8f1a67`) with `UndefinedFunctionError`; passed
after `alembic upgrade head`. Additionally verified end-to-end by calling the actual
`organisations.invite()` route function (not the repository function directly) against a
real, unmocked database connection pool, with only the outbound email call stubbed -
first-time invite and re-invite both succeeded. `pytest -q`: 147 passed.
`ruff check app tests`: clean.

## Iteration 10 - 2026-08-08 · dashboard polish round 3 (escalations worklist)

### #46 - Resolving an escalation updated nothing outside its own card

**S3 · FIXED · web · `apps/web/components/app/escalation-card.tsx`,
`apps/web/lib/app-store.tsx`**

Clicking "Mark resolved" only ever flipped a `useState` local to the one
`EscalationCard` that was clicked (`#7`). The "N waiting" heading on
`/app/escalations`, the same count on the dashboard's "Needs a person" panel, and the
nav bar's escalation badge all read `useAppStore().escalations` - none of them knew
the click happened, so resolving five items in a row left every one of those numbers
unchanged, and the resolved cards themselves stayed in whichever list rendered them.

**Impact.** Worse than `#7`'s original framing ("navigating away loses it") suggests:
the count and list not updating is visible _immediately_, without ever leaving the
page - clicking the button looked like it did nothing at all, in the same view where
it was clicked.

**Fix.** Moved resolution ownership from the card to `useAppStore()`. A new
`resolveEscalation(outcome)` action records the outcome's key in a session-only
`Set` - there is no per-outcome id from the API yet, so the key is content-derived
(`run_id` + `provider_call_id` + `contact_name` + `created_at`), good enough to dedupe
within one loaded session and no more - and the store's own `escalations` list
excludes anything in that set. Every consumer of `escalations` (the worklist, the
dashboard panel, the nav badge) therefore drops the item and its count in the same
render, with no per-page wiring needed. `EscalationCard` now calls
`resolveEscalation()` and keeps the existing honest toast ("Hidden for now, not
saved... comes back if you reload"); its own local `resolved`/grayed-out visual state
was removed as dead code, since the card unmounts in the same render pass that would
have shown it.

**Still open - this is `#7`, not a new gap:** nothing above writes to a database.
The `Set` lives in a React context, so a reload, a second tab, or a second person all
still see the item as unresolved. The real fix is still the `escalations` table
`#7` already calls for (`FEATURES.md` F23); this entry only closes the
within-session visibility half of it.

**Verification.** `npm run type-check` and `npm run lint` (from `apps/web`) both pass.
No backend changes.

**Depends on:** #7 (this closes its visible-symptom half only).

### #47 - `--text-mute` fell short of WCAG AA body-text contrast almost everywhere it's used

**S3 · FIXED · web · `apps/web/app/globals.css`**

`--text-mute` (`#6b7280`) measured 4.39:1 against `--surface` and 4.46:1 against the new
`--glass-surface`-over-`.canvas-tint` composite (round 3 Task 1's glass tokens) - both
below the 4.5:1 WCAG AA minimum for normal-weight body text, despite a code comment
next to the declaration claiming "4.6:1 on --surface" that was apparently never
accurate. This was caught during Task 1's own contrast-verification work (which checked
`--text`/`--text-mute` against the new glass tokens per that task's brief) - the
verification correctly computed ~4.46:1 for the glass case, but the report accompanying
that task paired it against the 3:1 large-text threshold instead of 4.5:1. A
review pass grepped roughly 100 real `text-text-mute` usage sites across the app and
found it used almost exclusively as small, regular/medium-weight text -
`text-small` hint paragraphs, `text-data` (13px mono) IDs/timestamps, `.eyebrow` (11px)
labels, placeholder text - none of which is large enough (≥24px normal or ≥18.66px bold)
to qualify for the 3:1 exception, so 4.5:1 is the bar that actually applies almost
everywhere this token is used.

**Pre-existing, not introduced by round 3.** Traced back: the _old_ `--text-mute`
(`#6b787e`) against the _old_ `--surface` (`#f4f6f5`, both from before this round's other
token tweaks) was already only 4.19:1 by the same method - the stale "4.6:1" comment
looks like it was never re-verified after either value was last hand-picked. Round 3's
glass treatment is contrast-neutral-to-slightly-positive for this token (a white glass
fill lightens the effective backdrop slightly versus the flat surface), not the cause.

**Impact.** Borderline-low contrast on most secondary/tertiary text across the product -
hint copy, timestamps, IDs, placeholders. The shortfall was small (0.1–0.3 below the
4.5:1 line, not a drastic failure), so unlikely to have been reported as a visible
readability complaint, but it is a real, measurable AA non-conformance on a very common
usage pattern, not an edge case.

**Fix.** Darkened `--text-mute` from `#6b7280` to `#666d7b` (roughly −5% per channel,
same hue direction). Recomputed against both real backdrops: **4.73:1 against plain
`--surface`**, **4.80:1 against `--glass-surface` composited over `.canvas-tint`'s
worst-case (`--accent-wash`) point** - both clear 4.5:1 with margin. Corrected the stale
comment next to the declaration to state the real numbers and point here.

**Verification.** `npm run type-check` and `npm run lint` (from `apps/web`) both pass.
No component changes needed - `--text-mute` is consumed everywhere through the token,
with no hardcoded duplicate of the old hex found anywhere else in `apps/web`.

**Depends on / Blocks:** none. Not part of round 3 Task 1's stated brief, but fixed in
place rather than deferred, since this token lives in the exact file every later
round-3 task builds on.

### #48 - The dashboard's ambient glow widened the page past the viewport and caused a global horizontal scroll

**S2 · FIXED · web · `apps/web/app/globals.css`**

User-reported: "the whole UI is scrolling to left." `.signal-field` (the wrapper
`page.tsx` puts around the dashboard's "Outcome distribution" panel, its only caller)
gives the panel an ambient three-colour glow via a `::before` pseudo-element sized
`inset: -20% -10%` - deliberately larger than `.signal-field` itself, so `blur(40px)`
has room to soften the gradient's edge instead of visibly cutting it off. That's a
real box in layout, not paint (unlike `.canvas-tint`'s plain `background` gradient,
which was checked and ruled out - background images never affect scrollable
overflow regardless of sizing). Nothing between `.signal-field` and `<body>` clipped
overflow, so the oversized pseudo-element widened `.signal-field`'s own scrollable
area, which bubbled straight up to the document: loading `/app` picked up a
horizontal scrollbar (and matching vertical bleed) the moment the page's initial
fetch finished - with or without any call history in the account.

`page.tsx`'s only use of `hasAnything` (`settled.length > 0 || runs.length > 0`) is
in the loading-skeleton's early return - `if ((phase !== "up" || loadingRuns) &&
!hasAnything) return <LoadingSkeleton />` - which is skipped once `phase === "up"`
and `loadingRuns` is false, regardless of `hasAnything`. Past that early return,
`.signal-field`'s wrapper div is unconditional: `recent.length === 0` only swaps in
an `EmptyState` _inside_ it, the wrapper itself always renders. So a brand-new
organisation with zero runs still hits this codepath the moment its first fetch
resolves.

**Why it looked intermittent / pre-existing rather than tied to round 3's own new
wrapper divs (Task 1's `.app-font-scope`, Task 2's 3-column header grid - both
checked directly against the live rendered DOM at 1024–1920px with long/worst-case
content and found clean):** the only thing that ever skips this codepath is the
connection still being down or the initial fetch not having resolved yet - not the
account having no data - so it only failed to reproduce during exactly that narrow
loading/offline window, and reproduced on essentially every other load.

**Impact.** Every visit to `/app` that got past the initial connect/load - which is
effectively every real visit, including a brand-new organisation with zero runs -
scrolled and looked broken, on desktop, for every organisation. The most-visited
page in the product, broken far more broadly than "accounts with call history."

**Fix.** Added `overflow: hidden` to `.signal-field` itself (the element that already
establishes `position: relative` for the pseudo-element), clipping the glow's bleed
to the card it decorates instead of letting it expand the page. The gradients already
fade to `transparent` at 70% of their own radius and the blur only needs on the order
of 60–80px of margin to avoid a hard edge - both well inside `.signal-field`'s own
box even without the extra overshoot - so the clip produces no visible hard cutoff
(checked visually). One accepted, minor trade-off: `Panel`'s own `--shadow-card`
bleed (~20–28px) is now clipped at the same boundary rather than fading past it,
since the wrapper and the panel share a box; not worth a DOM restructure for this
round. Grepped the rest of `globals.css` for the same pattern (`position: absolute`

- negative `inset`) - no other instance exists; `.btn-pulse::after` uses `inset: 0`
  and is safe.

**Verification.** Reproduced directly in a real browser against the live component
markup (`document.documentElement.scrollWidth` went `1440→1544` at a 1440px viewport
with the exact `signal-field`/`panel-glass` class combination present, `1544→1440`
after the fix) rather than inferred from reading the CSS alone. `npm run type-check`
and `npm run lint` (from `apps/web`) both pass - 0 errors; the lint run's one warning
is pre-existing and unrelated (`components/layout/app-nav.tsx`, an `<img>` vs
`next/image` suggestion). No backend changes. No blanket `overflow-x: hidden` added
to `<body>` - the fix is scoped to the one component that produced the oversized box.

**Depends on / Blocks:** none.

## Iteration 11 - 2026-08-08 · round 3 close-out: final review sweep

Nine independent fixes from a whole-round final review (accessibility, permission
gating, stale docs, dead code), plus two findings the review confirmed as real but
judged too broad to land in the same pass - logged here, open, rather than silently
deferred.

### #49 - Radix overlays and the toast provider portal outside `.app-font-scope` and lose the new typeface

**S3 · OPEN · web · `apps/web/components/ui/dialog.tsx`, `dropdown-menu.tsx`,
`tooltip.tsx`, `select.tsx`, `disclosure.tsx`, the toast provider**

`.app-font-scope` (`apps/web/app/(app)/app/layout.tsx`) is the wrapper div this
round's Ubuntu-font switch scopes to - both the `.app-font-scope` class itself and
the `--font-ubuntu` CSS variable (from `next/font`'s `.variable`) are declared only
on that one div. Every Radix-based overlay - `dialog.tsx`, `dropdown-menu.tsx`,
`tooltip.tsx`, `select.tsx`, `disclosure.tsx` - and the toast provider all portal
their content to `document.body` by default, which sits outside that wrapper
entirely.

**Impact.** Every dropdown, dialog, tooltip, select, and toast under `/app/*` still
renders in the old Inter Tight font instead of Ubuntu, even though the page around
it - and the trigger that opened it - is Ubuntu. Visible on essentially every
interactive surface in the dashboard: the org switcher, the user menu, every form
select, every toast, every confirmation dialog.

**Why the obvious quick fix doesn't work.** Adding `.app-font-scope`'s class name to
the portalled content does **not** fix this, and makes it worse: the class alone
does nothing without `--font-ubuntu` in scope, and that variable isn't available at
`document.body` either (it's set inline on the wrapper div by `next/font`, not
globally). Applying the class without the variable falls through to a generic
sans-serif fallback with _neither_ font loaded - worse than the current Inter Tight
mismatch, not better.

**Fix.** Thread a `container` prop through each Radix primitive (`Portal`
already accepts one) so overlay content portals inside `.app-font-scope`'s wrapper
div instead of `document.body`. Touches five `ui/` primitives plus the toast
provider - real, scoped follow-up work, not a one-line patch.

**Depends on / Blocks:** none.

### #50 - Admin's role picker offers "Admin," a role Admin can't grant, guaranteeing a 403

**S3 · OPEN · web · `apps/web/components/app/invite-dialog.tsx`,
`apps/web/app/(app)/app/organisation/page.tsx`**

`#43`'s fix (iteration 9) correctly taught the backend that an Admin may only grant
a role strictly below their own - `can_grant_role()` in
`apps/api/app/auth/permissions.py` rejects an Admin granting `admin` or `owner`.
Nothing on the frontend knows this rule: `ROLES` (`invite-dialog.tsx`) is a flat,
unconditional list including `"admin"`, and it feeds both the invite dialog itself
and the one interactive role-change dropdown in `organisation/page.tsx`'s "Manage"
menu. (`organisation/page.tsx` also renders `ROLES` a second time as a static
"Roles" reference legend - name plus a one-line description of what each role can
do - which isn't a picker at all: no `onClick`/`onSelect`, nothing to submit, so it
can never trigger this bug.)

**Impact.** An Admin can select "Admin" in either the invite dialog or the
role-change dropdown and submit - the request always comes back `403`. Not a false
success (`CLAUDE.md` non-negotiable #9): the error is real and correctly worded, the
UI doesn't claim the invite/change went through. But offering a choice that is
_never_ valid for the caller making it, with no indication in the picker itself, is
a confusing dead end an Admin has no way to anticipate before clicking "Send" or
"Save."

**Fix.** A `rolesGrantableBy(callerRole)` helper (mirroring `can_grant_role()`'s
rank rule) threaded through `invite-dialog.tsx`'s `ROLES` and the one interactive
role-change dropdown in `organisation/page.tsx`, so the picker itself never lists a
role the caller cannot actually grant. Touches two call sites across two files -
real follow-up work, not landed in this pass. (The static "Roles" legend needs no
change - it isn't a picker.)

**Depends on / Blocks:** none.

## Iteration 12 - 2026-08-08 · team invitation send failure, user-reported

### #51 - Team invitations failed outright - the from-domain was never verified in Resend, and the error leaked a raw httpx dump

**S2 · PARTLY FIXED · backend + docs · `apps/api/app/integrations/email/resend.py`,
`SUPABASE_SETUP.md`**

Sending any team invitation failed with `Could not send the invitation email: Client
error '403 Forbidden' for url 'https://api.resend.com/emails'` - a bare
`httpx.HTTPStatusError` string, actionable by no one.

Root cause confirmed directly against Resend's API, not just inferred: `RESEND_API_KEY`
is a valid, real key (a restricted send-only key, which is expected and not itself the
bug), but `RESEND_FROM_EMAIL` (`CallFlow AI <noreply@callflow-ai.brbik.com>`) sits on
`callflow-ai.brbik.com`, a domain never added to or verified in this Resend account.
Reproduced with a request Resend never delivers (`to: ["delivered@resend.dev"]`, its own
non-delivering simulation address - no real email was sent):

```
{"statusCode":403,"name":"validation_error","message":"The callflow-ai.brbik.com domain
is not verified. Please, add and verify your domain on https://resend.com/domains"}
```

**Correction to `#19`:** that entry describes team invitations as sent through
Supabase's built-in mailer / **custom SMTP**, same as password reset. That was never
accurate. `POST /api/v1/organisations/me/invitations`
(`apps/api/app/api/v1/routes/organisations.py`) never touches Supabase Auth's mailer -
it calls `EmailGateway.send_invitation()` (`apps/api/app/integrations/email/resend.py`),
which POSTs to `https://api.resend.com/emails` directly using `RESEND_API_KEY` /
`RESEND_FROM_EMAIL` from `.env`. Supabase's Auth → SMTP Settings governs password reset
(and signup confirmation, if that's ever re-enabled) only - it has no effect on team
invitations either way. Left `#19`'s original text as the historical record and corrected
the description here rather than rewriting it.

**Impact.** Every invitation, to every recipient, has always failed in this environment -
the team feature's core write path has never worked. Nothing in application code could
have fixed this: Resend requires DNS records proving domain ownership before it will
relay mail from that domain, and only the domain's owner can add them.

**Partly fixed.**

- `resend.py` now inspects a rejected send's response body. When it matches Resend's
  domain-verification shape (`statusCode 403`, `name: "validation_error"`, message
  containing "domain is not verified"), it raises a message naming the actual unverified
  domain and pointing at Resend's dashboard → Domains - not Resend's raw sentence, not an
  `httpx` dump. Other rejection reasons (e.g. a malformed `from` field, a network failure)
  still surface distinctly, so a future different failure doesn't get mislabeled as a
  verification problem. This message reaches the invite dialog's error toast unchanged -
  `organisations.py`'s `invite()` already passed `EmailAPIError`'s text through as the
  HTTP exception detail, and `apps/web/lib/api.ts` already surfaces `detail` verbatim, so
  no frontend change was needed. Covered by `apps/api/tests/test_email.py` (new file):
  the request shape sent to Resend, the domain-verification message, a non-domain 403/422
  staying generic, and a network-level failure all have a test.
- `SUPABASE_SETUP.md` §3 now separates the two email paths explicitly and states plainly
  that `RESEND_FROM_EMAIL`'s domain must be verified in Resend's dashboard before any
  invitation can go out; §4's env var table now lists `RESEND_API_KEY` /
  `RESEND_FROM_EMAIL` alongside the Supabase variables.
- **Not fixed, and not fixable in code:** `callflow-ai.brbik.com` is still unverified.
  Invitations will keep failing - now with a clear, correct reason - until a human adds
  real DNS records for a real domain (or repoints `RESEND_FROM_EMAIL` at one already
  verified in this account) in Resend's dashboard.
- **Documented stopgap, for local testing only, not wired into any default:**
  `onboarding@resend.dev` is Resend's pre-verified sandbox sender and needs no domain of
  its own. Confirmed this account can send from it at all - a request to
  `delivered@resend.dev` returned `200`. Per Resend's current documentation, before a
  domain is verified it can only deliver to the email address the account itself was
  signed up with, not to arbitrary invitees; this specific restriction was not tested
  live, to avoid spending send quota or emailing anyone without a clear reason. Left out
  of `config.py`'s default on purpose - a silent fallback would restrict who can be
  invited without anyone noticing (`CLAUDE.md` non-negotiable #9).

**Depends on / Blocks:** corrects `#19`'s description of the invitation path. Blocked on
a human verifying a real sending domain in Resend's dashboard before this can move past
PARTLY FIXED.

---

## Iteration 13 - 2026-08-08 · CALL-E integration research follow-up: transcript extraction and poll resilience

Findings from acting on `CALLE_INTEGRATION_STATUS.md`'s research pass (which cross-checked
CALL-E's real response shape against the installed SDK's generated models, the public
OpenAPI spec, and `CALLE.md`), then a review pass that ran the resulting fix against
realistic failure scenarios and found two gaps in the first version of it.

### #52 - Transcript extraction read a top-level key that doesn't exist anywhere in CALL-E's real response

**S2 · FIXED · backend · `apps/api/app/services/campaign_runner.py`, `apps/web/components/app/transcript-view.tsx`**

`_extract_transcript()` checked `transcript`/`transcript_text`/`asr_transcript` at the top
level of the call payload. Confirmed independently against the installed SDK's generated
models (`calle/generated/models/call_task_attempt.py`, `call_transcript_turn.py`),
`calle/calls.py` (proves `get_call()` returns the raw, unreshaped API JSON - no reshaping
happens in the SDK layer), and the public OpenAPI spec (`CALLE.md`): none of these keys
exist anywhere in the real shape. The real location is nested two levels down,
`recipients[N].attempts[M].transcript_turns[]`, each turn
`{offset_seconds, speaker: "bot"|"user"|"unknown", text}`.

**Impact.** `CallOutcome.transcript` was `None` for every real call CallFlow ever placed.
`transcript-view.tsx` renders "No transcript was recorded for this call." whenever
`outcome.transcript` is falsy, so every completed call showed that message regardless of
what was actually said. Not independently confirmed against a live CALL-E call (no API
access in this environment), but every documented source agreed on the nested shape and
none supported the flat one the old code checked.

**Fixed.** `_extract_transcript()` now reads `recipients[0].attempts[...].transcript_turns[]`,
following `_extract_result()`'s existing `recipients[0]` convention for the batch case. A
new `_final_attempt()` helper decides which attempt to surface when a recipient was
redialled - not by status alone (a `completed` attempt can still have empty
`transcript_turns`, and a `failed` one can carry a real partial conversation, per the
model's own documented behaviour), but by whichever attempt actually has turns, most
recent first by `started_at` rather than array position (the model doesn't document
`attempts` as chronologically ordered). A turn with `"text": null` (a real, permitted
value) is skipped rather than rendered as the literal string "None". `_extract_result()`
was checked for the same class of bug and found _not_ buggy: `CampaignRunner` always
passes a task-level `result_schema`, never `recipient_result_schema`, so the real API
genuinely populates the top-level `structured_result` key it already reads - confirmed via
the SDK model's own docstring, replacing that function's previously-unsourced "a few
different keys across versions" comment with the actual citation.

Frontend: `transcript-view.tsx`'s `parseTranscript` previously folded CALL-E's real
`"unknown"` speaker value into "contact" - unreachable before this fix (transcript was
always `None`), so newly real rather than pre-existing. Fixed to render `"unknown"` as its
own, visually distinct, unattributed turn ("Unknown speaker") instead of silently
attributing it to the contact.

**Verified.** New tests in `apps/api/tests/test_orchestrator.py` cover the nested shape,
multi-attempt selection - including two scenarios a review pass specifically found broken
in the first version of this fix: an empty `completed` final attempt with an earlier
attempt carrying the real transcript, and attempts ordered by `started_at` rather than
array position - multi-recipient batches, and the null-text case. `pytest -q` and
`ruff check app tests` pass; `npx tsc --noEmit` and `eslint` pass on the frontend change.

**Depends on / Blocks:** none.

### #53 - One flaky status poll could mark an entire, successfully-completed call as failed

**S2 · FIXED · backend · `apps/api/app/services/campaign_runner.py`, `apps/api/app/integrations/voice/engine.py`**

`_poll_until_done()` had no error handling around its per-iteration `GET /v1/calls/{id}`.
At a 2s interval and up to `poll_timeout_seconds` (900s default), a single call could make
on the order of 450 requests just to watch it finish; any one of them raising propagated
straight out and marked the whole call FAILED - even though the phone conversation itself
keeps running at CALL-E regardless of whether CallFlow can currently poll it, and could
complete successfully moments later with a real result nobody came back to collect.

**Impact.** A transient network blip or a momentary `provider_unavailable` mid-poll could
misreport a call someone actually answered and completed as unreachable/failed, with no
automatic way to recover the real result.

**Fixed.** Per-iteration poll failures are now caught and classified via the engine's
existing `classify_error()` taxonomy. A new `_POLL_RETRYABLE_FAILURES` set is used for this
decision instead of the dial-time `_RETRYABLE_FAILURES` - a `GET` is an idempotent read,
not a safety/credit/permission decision, so CLAUDE.md's fail-closed rule doesn't apply to
it the way it does to a dial decision, and it gets a deliberately wider retry net:
everything is retried except an outright auth failure (`unauthorized`/`forbidden`), which
polling can never recover from regardless of how long it waits.

A review pass that ran the first version of this fix against realistic failure codes found
it too narrow: `internal_error`, `not_found` (the classic read-after-write race right after
a call is created - polling before it's indexed yet), and `call_not_ready` (literally
"not ready yet, check again") all fall through `classify_error`'s unmapped-code default to
`DialFailure.INTERNAL`, which the dial-time set deliberately excludes - so under the first
version of this fix, all three still failed an otherwise-completing call. They're covered
now by `_POLL_RETRYABLE_FAILURES`'s wider net.

Also added while fixing this: `CalleConnectionError` (raised by the SDK when a request
fails before any response arrives - DNS failure, connection refused, TLS error) was a
distinct exception type `engine.py` never imported or classified, so it fell into the same
"propagates and fails the call" path this issue describes, both during polling and during
`start_call` itself. `engine.py` now imports it (aliased `EngineConnectionError`, per
CLAUDE.md's dependency-inversion rule - never imported directly into `campaign_runner.py`)
and `classify_error()` maps it to `PROVIDER_UNAVAILABLE`.

Retryable poll failures are bounded by the existing overall `poll_timeout_seconds` deadline
(900s) rather than a separate consecutive-failure counter - if every poll keeps failing
until the deadline, the loop's existing `TimeoutError` fires exactly as it already did for
a slow-but-healthy call, landing on `Disposition.RETRY`, a coherent, already-tested outcome
rather than a new failure mode.

**Known limitation, not separately tracked.** Retries use a flat 2s interval with no
backoff - a sustained `rate_limit_exceeded` mid-poll would be retried at the same cadence
for up to 900s, which can extend rather than help clear a rate limit. Left as-is rather
than added here: real backoff needs a policy decision (cap, jitter, per-failure-type
tuning) that's more than this fix's scope.

**Verified.** New tests in `apps/api/tests/test_orchestrator.py`: one transient failure
followed by success does not fail the call; each of `internal_error`/`not_found`/
`call_not_ready` followed by success does not fail the call; an always-failing connection
eventually times out (bounded, not infinite) into `Disposition.RETRY`; a genuinely
non-retryable failure (`unauthorized`) fails the call immediately rather than exhausting
the timeout. New tests in `apps/api/tests/test_engine.py` for the `classify_error`
addition. `pytest -q` and `ruff check app tests` pass.

**Depends on / Blocks:** none.

### #54 - A retried call after a connection-error classification could double-dial without counting against the per-run ceiling

**S3 · OPEN · backend · `apps/api/app/services/campaign_runner.py`**

Flagged by the same review pass that found the gaps in `#53`, as a narrow follow-up risk
rather than an active bug - no code change accompanies this entry. Since `#53`'s fix, a
connection error during `start_call()` is now classified `PROVIDER_UNAVAILABLE` /
`Disposition.RETRY` (previously it fell through to `DialFailure.INTERNAL` /
`Disposition.UNREACHABLE`, non-retryable). `Disposition.RETRY` is advisory only - nothing
in this codebase automatically retries a call today, so this is not a live double-dial bug.

But if something ever does act on that `RETRY` disposition (a future auto-retry feature, or
a person manually re-running the same contact): the idempotency key is regenerated per
attempt (`f"{campaign.id}-{contact.phone}-{uuid.uuid4().hex[:8]}"`, already flagged
separately in `CALLE_INTEGRATION_STATUS.md` §3.5 - CALL-E has no way to recognise a retry
as a duplicate of a request that actually reached it before the connection dropped), and
`_calls_made` is only incremented after `start_call` returns successfully, not on a path
that raised `EngineConnectionError` - so a retry after this specific classification
wouldn't count against `max_calls_per_run` either. The narrow window: the create-call
request reaches CALL-E and a call actually gets placed, but the connection drops before the
response reaches CallFlow. A subsequent retry in that window would be a genuine second
phone call to the same contact, uncounted by the per-run ceiling.

**Impact.** Narrow - requires the specific timing where CALL-E received and acted on a
request whose response CallFlow never saw, combined with something acting on the advisory
`RETRY` disposition. Not reachable today since nothing auto-retries.

**Fix.** Not fixed here. Would need either a stable (non-regenerated) idempotency key per
contact-attempt, or `_calls_made` incremented before the request is sent rather than after
it returns successfully, to close - either changes retry semantics enough to deserve its
own deliberate pass rather than a drive-by fix.

**Depends on / Blocks:** related to `CALLE_INTEGRATION_STATUS.md` §3.5 (idempotency key
regenerated per attempt) and `#53` (introduced the reclassification that makes this
reachable).

## Template for the next iteration

```
## Iteration N - YYYY-MM-DD · <what prompted the audit>

### #N - <one-line title>
**S? · OPEN · area · file**

<What is wrong, factually.>

**Impact.** <Who is hurt and how. Say if it is currently masked and by what.>

**Fix.** <The intended fix, with the FEATURES.md reference if there is one.>

**Depends on / Blocks:** <ids>
```
