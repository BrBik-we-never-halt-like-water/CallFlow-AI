# Issues and bugs

A living log. Every audit or iteration appends findings here; nothing is deleted, only
re-statused, so we keep the history of what was wrong and when we knew.

**Related:** [`SYSTEM.md`](SYSTEM.md) (as-built reference) · `FEATURES.md` (target state —
**referenced by `F<n>` throughout this file and `SYSTEM.md`, but the file itself doesn't
exist in this repo**; `SYSTEM.md` §12 is the closest real gap map until it's written) ·
[`apps/web/DESIGN_NOTES.md`](apps/web/DESIGN_NOTES.md) (frontend decisions)

## Severity

| | Meaning |
|---|---|
| **S1** | Breaks a product guarantee, loses data, or exposes one tenant's data to another. Fix before shipping to a paying customer. |
| **S2** | A feature is broken or actively misleading in normal use. |
| **S3** | Wrong in an edge case, or misleads a developer rather than a user. |
| **S4** | Cosmetic, naming, or tidiness. |

## Status

`OPEN` · `IN PROGRESS` · `FIXED` (with the commit) · `WONTFIX` (with the reason) ·
`SUPERSEDED` (folded into a larger change)

---

## Open issues

| ID | Sev | Title | Area | Found | Status |
|---|---|---|---|---|---|
| [#1](#1--no-persistence-anywhere) | S1 | No persistence anywhere | backend | it-1 | **FIXED** |
| [#2](#2--user-campaigns-are-global-and-ephemeral) | S1 | User campaigns are global and ephemeral | backend | it-1 | **FIXED** |
| [#3](#3--suppression-list-is-never-enforced) | S1 | Suppression list is never enforced | backend + web | it-1 | **FIXED** |
| [#4](#4--calloutcomerun_id-holds-the-provider-call-id) | S1 | `CallOutcome.run_id` holds the provider call id | backend | it-1 | **FIXED** |
| [#5](#5--rate-limits-and-daily-budget-are-per-process-and-reset-on-restart) | S2 | Rate limits reset on restart, not shared | backend | it-1 | OPEN |
| [#6](#6--three-high-severity-npm-advisories) | S2 | Three high-severity npm advisories | web | it-1 | OPEN |
| [#7](#7--escalation-resolution-is-component-state) | S3 | Escalation resolution is component state | web | it-1 | OPEN |
| [#8](#8--stats-mixes-denominators) | S3 | `stats` mixes denominators | backend | it-1 | OPEN |
| [#9](#9--renderyaml-contradicts-the-real-deployment) | S3 | `render.yaml` contradicts the real deployment | infra | it-1 | **FIXED** |
| [#10](#10--no-frontend-tests) | S3 | No frontend tests | web | it-1 | OPEN |
| [#11](#11--escalate_on_negative-is-misnamed) | S4 | `escalate_on_negative` is misnamed | backend | it-1 | OPEN |
| [#12](#12--whatsapp-env-vars-are-read-but-unused) | S4 | WhatsApp env vars read but unused | backend | it-1 | OPEN |
| [#13](#13--the-last-owner-guard-blocked-every-cascading-delete) | S1 | Last-owner guard blocked every cascading delete | database | it-2 | **FIXED** |
| [#14](#14--orphaned-organisations-survive-account-deletion) | S3 | Orphaned organisations survive account deletion | database | it-2 | **FIXED** |
| [#15](#15--next-build-output-blocked-a-git-mv-of-the-web-app) | S4 | `.next` blocked a `git mv` of the web app | tooling | it-2 | **FIXED** |
| [#16](#16--token-verification-rejected-valid-tokens-under-clock-skew) | S1 | Token verification rejected valid tokens under clock skew | api | it-3 | **FIXED** |
| [#17](#17--orphaned-organisations-confirmed-in-practice) | S3 | Orphaned orgs consume slugs permanently | database | it-3 | **FIXED** |
| [#18](#18--supabase-rejects-email-domains-without-mx-records) | S4 | Supabase rejects domains without MX records | external | it-3 | WONTFIX |
| [#19](#19--built-in-email-sender-quota-is-exhausted-quickly) | S2 | Built-in email sender quota exhausted quickly | config | it-3 | **PARTLY FIXED** |
| [#20](#20--calling-windows-are-not-enforced-anywhere-in-the-backend) | S2 | Calling windows are not enforced anywhere in the backend | backend + web | it-4 | **PARTLY FIXED** |
| [#21](#21--organisationlogo_url-was-missing-from-the-orm-model) | S4 | `Organisation.logo_url` was missing from the ORM model | backend | it-4 | **FIXED** |
| [#22](#22--half-the-real-runtime-dependencies-were-undeclared-in-pyprojecttoml) | S2 | Half the real runtime dependencies were undeclared in `pyproject.toml` | backend | it-4 | **FIXED** |
| [#23](#23--root-envexample-still-had-callflow_dry_run-and-no-supabase-config-at-all) | S2 | Root `.env.example` still had `CALLFLOW_DRY_RUN` and no Supabase config at all | config | it-4 | **FIXED** |
| [#24](#24--featuresmd-does-not-exist) | S3 | `FEATURES.md` does not exist | docs | it-4 | OPEN |

---

## Iteration 1 — 2026-08-06 · full system audit

Findings from reading the whole codebase to write `SYSTEM.md`.

### #1 — No persistence anywhere
**S1 · FIXED · backend · migration `202608070900_campaigns_runs_and_call_outcomes`**

`callflow/store.py` was a `dict` behind a `threading.Lock`. Every run, outcome,
transcript, and user-created campaign lived in process memory.

**Impact.** All data was lost on restart or redeploy — and CI redeploys on every push to
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

### #2 — User campaigns are global and ephemeral
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

### #3 — Suppression list is never enforced
**S1 · FIXED · backend + web · `app/domain/safety.py`, `app/database/repositories/suppressions.py`, `app/api/v1/routes/suppressions.py`**

`web/lib/suppression.ts` used to keep the list in one browser's `localStorage`. The dial
path (`safety.check_dial_allowed`) never consulted it.

**Impact.** The product told users a suppressed number is "never dialled by any campaign,
ever" and showed a permanent `SUPPRESSED` tag. That guarantee did not hold — a run could
dial someone who had asked not to be called. This was the most serious gap after #1
because it was a stated promise with legal weight (DPDP, TCPA, TRAI), and the UI actively
asserted it was true.

**Read/enforcement side fixed first.** A `suppressions` table keyed on `(org_id,
phone_hash)` (SHA-256 with a per-deployment pepper, `PHONE_HASH_PEPPER`).
`check_dial_allowed()` now takes an `is_suppressed: bool` and denies the dial if true —
checked against a snapshot of suppressed hashes resolved once per run and consulted for
every contact in it (`FEATURES.md` F14). This shipped in the same change as dry_run
removal (see Iteration 4): once dry_run stopped being a de facto safety net, this became
the guard that actually has to hold. Verified by the orchestrator test suite (a suppressed
contact never reaches the gateway).

**Write side fixed in this iteration.** `app/database/repositories/suppressions.py`'s
`add_suppression()` and `remove_suppression()` had no caller anywhere in the app — no
`/api/v1/suppressions` route existed, so the table could only be populated by a direct
database write, and the frontend's "Contacts" page suppression toggle was a **separate,
disconnected** `localStorage` list that never touched it. Found by re-reading the dial
path against the frontend while investigating the calling-window claims in #20 — the same
"UI promises something the backend doesn't do" shape, on a legally-weighted guarantee.

Fixed by adding `app/api/v1/routes/suppressions.py`: `GET/POST /api/v1/suppressions` and
`DELETE /api/v1/suppressions/{id}`, gated by the `SUPPRESSIONS_READ`/`ADD`/`REMOVE`
permissions that already existed in the permission matrix (unused until now — this route
is the feature they were written for). Adding is `operator` role or above; removing
(making someone callable again) is owner-only, matching the table's existing RLS insert/
delete policies exactly. The "Contacts" page's suppression tab now calls this API
directly instead of `lib/suppression.ts`, which is deleted.

**Still open, separately:** a `do_not_call` disposition from triage does not yet
auto-insert a suppression row — today a person still has to add the number by hand after
noticing the call ended that way. Not blocking, since the manual path is now real; tracked
for a future iteration rather than reopening this issue.

**Depends on:** #1 (fixed).

---

### #4 — `CallOutcome.run_id` holds the provider call id
**S1 · FIXED · backend · `app/api/v1/routes/runs.py`**

The orchestrator sets `run_id=call_id` (the engine's call identifier) internally, in
three places: the in-flight update, `_poll_until_done`, and the resolved outcome —
this is still true of `app/services/campaign_runner.py` in isolation.

**Impact.** The frontend links to `/app/runs/{outcome.run_id}` from the overview lamp
strip and ⌘K search. On a live run those links pointed at a run id that did not exist →
404-ish empty state.

**Fixed** one layer up, at the persistence boundary rather than in the orchestrator:
`_run_and_persist()` in `app/api/v1/routes/runs.py` renames the field before it is ever
stored — `record["provider_call_id"] = record.pop("run_id", None)` — and passes the
actual run id in separately. The persisted `call_outcomes` row and every API response
carry the real `run_id`; `provider_call_id` holds the engine's call id as its own field.
Re-severitised from S2 to S1 on fix, since with dry_run gone every run is real and this
would otherwise have broken run navigation universally rather than only masking it.

**Verified.** `Outcome.provider_call_id` is now a distinct, typed field in
`apps/web/lib/api.ts`; `run_id` always resolves to the real run.

---

### #5 — Rate limits and daily budget are per-process and reset on restart
**S2 · OPEN · backend · `callflow/ratelimit.py`**

Counters are in-memory `deque`s using `time.monotonic()`.

**Impact.** The "shared daily budget" is neither shared (per process) nor durable (resets
on deploy). Since CI deploys on every push to `main`, the budget effectively resets
whenever anyone merges. `monotonic()` also means the 24h window is measured from process
start, not wall-clock midnight.

**Fix.** Upstash Redis sliding window (`FEATURES.md` F10), failing **closed** for
cost-bearing writes and open for reads.

**Depends on:** #1 for the org scoping.

---

### #6 — Three high-severity npm advisories
**S2 · OPEN · web**

`postcss` (4 advisories: XSS via unescaped `</style>`, arbitrary file read and path
traversal via `sourceMappingURL`) and `sharp` (inherited libvips CVEs), both transitive
through `next@16.2.12`.

**Impact.** No known exploit path in this app — `postcss` runs at build time on our own
CSS, and `sharp` is used by Next's image optimisation. Still fails `npm audit` and will
fail any security review.

**Fix.** Upgrade to `next@16.3.0`, which resolves all three. Deliberately not done during
the UI rebuild to avoid mixing a framework bump into a large diff.

---

### #7 — Escalation resolution is component state
**S3 · OPEN · web · `components/app/escalation-card.tsx`**

`Mark resolved` sets local `useState`. Navigating away loses it.

**Impact.** An operator marks five escalations resolved, changes page, and they are all
back. Actively worse than no button, because it implies work was saved.

**Fix.** `escalations` table with `status`, `assigned_to`, `resolved_by`, `resolved_at`
(`FEATURES.md` F23), plus claim-on-open so two people cannot resolve the same item.

**Depends on:** #1.

---

### #8 — `stats` mixes denominators
**S3 · OPEN · backend · `callflow/api.py`**

In `get_run`, `escalated` is counted over `resolved` outcomes, but `auto_closed` and
`needs_human_pct` are counted over **all** outcomes including `in_flight`.

**Impact.** Mid-run percentages are diluted by in-flight rows, so the escalation rate
reads lower than it is while a run is live. Settles correctly once the run finishes.

**Fix.** Compute every stat over `resolved`, and expose `in_flight` as its own count.

---

### #9 — `render.yaml` contradicts the real deployment
**S3 · OPEN · infra**

`render.yaml` describes a two-service Render deploy. The actual deploy is
`.github/workflows/ci-cd.yml` → SSH to a VM → `pm2 restart callflow-api|callflow-web`,
behind `callflow-ai.brbik.com`.

**Impact.** Misleads anyone new, and invites someone to "fix" deployment in the wrong file.

**Fix.** Delete it, or keep it with a header comment saying it is unused.

---

### #10 — No frontend tests
**S3 · OPEN · web**

84 backend tests; zero on the frontend.

**Impact.** The highest-risk frontend logic is untested: `lib/format/phone.ts` (the masking
guarantee), `lib/lamp.ts` (disposition → lamp mapping), `lib/contacts.ts` (row validation),
`lib/campaign-fields.ts` (the 5→4 type mapping).

**Fix.** Vitest on those four modules first. They are pure functions, so this is cheap.

---

### #11 — `escalate_on_negative` is misnamed
**S4 · OPEN · backend · `callflow/triage.py`**

The flag gates a branch that returns `Disposition.RETRY`, not an escalation. When `false`,
negative sentiment falls through to the status checks rather than being ignored.

**Impact.** Anyone reading the campaign editor's "Escalate frustrated calls to a person"
switch will expect it to control escalation. Frustration escalation is actually
unconditional; this only controls the negative-sentiment retry.

**Fix.** Rename to `retry_on_negative` and correct the UI label. Breaking change to the
campaign create payload, so best done alongside the schema migration.

---

### #12 — WhatsApp env vars are read but unused
**S4 · OPEN · backend · `callflow/config.py`**

`WHATSAPP_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` are loaded into config. No code reads them.

**Impact.** Implies a working integration. `.env.example` lists them as "optional".

**Fix.** Either remove until F30 is built, or comment them as reserved.

---

## Iteration 2 — 2026-08-06 · Supabase auth foundation

### #13 — The last-owner guard blocked every cascading delete
**S1 · FIXED · database · migration `..._fix_last_owner_cascade`**

Introduced by me in the first auth migration and caught by the verification script, not by
review.

`protect_last_owner` raised whenever the last owner's membership was removed. Correct for a
direct removal, but a membership row is *also* removed as a side effect of legitimate
deletions — `delete auth.users → cascade public.users → cascade memberships`, and
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

### #14 — Orphaned organisations survive account deletion
**S3 · OPEN · database**

Organisations are deliberately not cascade-deleted from users — they are soft-deleted via the
DSR flow. So deleting the only member of an org leaves the org row behind with no memberships,
which makes it invisible to every RLS policy and therefore unreachable.

**Impact.** Rows accumulate that nobody can see or administer. Harmless today, but it will
distort any org-count metric and confuse a future support tool.

**Fix.** Either a `pg_cron` sweep that soft-deletes member-less organisations after a grace
period, or fold it into the account-deletion path in F43. Needs the DSR flow to exist first.

---

### #15 — `.next` build output blocked a `git mv` of the web app
**S4 · FIXED · tooling**

Not a product bug, recorded because it will recur. A running `next dev` server plus a 395 MB
`.next` directory held Windows file handles, so `git mv web apps/web` failed with
"Permission denied" — with no indication of the cause.

**Fix / how to avoid.** Stop the dev server and delete `.next` before moving or renaming any
directory under `apps/web`. Both are disposable: `.next` is gitignored and regenerates.

---

## Iteration 3 — 2026-08-06 · backend auth chain

### #16 — Token verification rejected valid tokens under clock skew
**S1 · FIXED · api · `app/auth/tokens.py`**

`/api/v1/me` returned `401 ImmatureSignatureError` for a token Supabase had just
issued. The token's `iat` was marginally ahead of this host's clock, and PyJWT rejects
that with zero tolerance by default.

**Impact.** Would have rejected **every valid login** on any host not tightly
NTP-synced. Presents as "correct credentials refused", with nothing in the client to
suggest a clock problem — the worst class of auth bug to diagnose in production.

**Fix.** `leeway=timedelta(seconds=30)` on `jwt.decode`. Deliberately small: leeway
also extends `exp`, so a large value would keep expired tokens alive.

**Verified.** Real Supabase token now verifies; bogus/absent tokens still 401.

---

### #17 — Orphaned organisations confirmed in practice
**S3 · OPEN · database**

Predicted as #14, now observed. Four orphans accumulated across three test runs, and
the visible symptom was a *slug collision*: a new signup from `brbik.com` became
`brbik-2` because the dead org still held `brbik`.

**Impact.** Worse than the invisible-row problem #14 described. Organisation slugs are
globally unique, so orphans permanently consume names — a real customer re-signing up
after deleting their account would get `acme-2`.

**Fixed** in two revisions, because the first attempt was incomplete and the test caught it:

1. `release_slugs_and_retire_empty_orgs` — slug uniqueness became a partial unique index
   on `deleted_at IS NULL`, and an `AFTER DELETE` trigger soft-deletes an organisation
   once its last membership goes.
2. `reuse_freed_slugs_on_signup` — the signup trigger's collision loop was still counting
   *every* row, so it kept stepping past freed slugs and a repeat signup still got
   `acme-2`. The loop now ignores soft-deleted rows, matching the index that enforces
   uniqueness.

**Verified.** First signup gets `brbik`; after account deletion the org is soft-deleted;
a fresh signup from the same domain gets `brbik` again; two live organisations still
cannot share a slug.

This also closes #14 — a member-less organisation is no longer left behind at all.

---

### #18 — Supabase rejects email domains without MX records
**S4 · WONTFIX (documented) · external**

Signup with `@northgate-labs.com` and `@example.com` returns
`400 email_address_invalid`. Supabase validates deliverability, so invented domains
cannot be used for test fixtures.

**Consequence for testing.** Seed test users through the admin API
(`POST /auth/v1/admin/users` with the secret key and `email_confirm: true`). It skips
both the domain check and the email send, so it does not consume the sender quota.

---

### #19 — Built-in email sender quota is exhausted quickly
**S2 · OPEN · external config**

Signup attempts returned `429 email rate limit exceeded` on the third and later tries,
which indicates Supabase still attempts a send.

**Impact.** Password reset cannot work reliably, and if "Confirm email" is not in fact
disabled, signups will silently fail once the hourly quota is gone.

**Partly fixed.** "Confirm email" is now genuinely off, and public signup was
re-verified end to end: `POST /auth/v1/signup` returns `200` with an access token
immediately, `email_confirmed_at` is set, and `/api/v1/me` resolves the new
organisation. Signup no longer depends on email delivery at all.

**Still open:** password reset and team invitations *do* send mail, so they remain
subject to the built-in sender's few-per-hour quota. Configure **custom SMTP** (Resend)
before either flow is relied on. Not a blocker for sign-up or sign-in.

---

## Iteration 4 — 2026-08-07 · persistence, dry_run removal

Not a bug-finding pass — a deliberate, user-confirmed product change, recorded here
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
first run an organisation makes — see #3 (partly fixed: enforcement is real, but there
is still no way to add a number to the list through the product).

**What still stands as the safety model:** E.164 validation, allowlist, per-run ceiling,
rate limiting (still #5's known weakness — in-memory, per-process), the shared daily
budget, calling windows, phone masking, and the now-enforced suppression list. `CLAUDE.md`
non-negotiable #8 ("dry_run defaults to true, everywhere") is replaced accordingly — see
the file itself for the current wording.

---

### #20 — Calling windows are not enforced anywhere in the backend
**S2 · PARTLY FIXED · backend + web**

Found while fact-checking `README.md` against the real code for this iteration's docs
pass. `apps/api/app/domain/safety.py` has no window check at all — grepping the whole
backend for `window_start`/`window_end`/calling-window logic returns nothing.

**Impact.** This was a `CLAUDE.md` non-negotiable #9 violation ("never show a success
state for something that did not happen"), not just a missing feature — and a wider one
than first found. A follow-up sweep (prompted by a user report of a confusing dashboard)
turned up the same false claim in **eight** places, not the three originally listed:
`apps/web/components/app/safety-bar.tsx`'s `guardsFromHealth()` (the guard chip shown on
the *actual run composer*, hardcoding `"09:00–20:00 IST"` as if confirmed — the one guard
in that function that didn't follow its own "unconfirmed → null/OFF" rule),
`settings/safety/page.tsx`, `components/app/campaign-editor.tsx` (told users configuring
a real campaign "nothing is dialled outside this window," and the same panel's retry
"attempts"/"spacing" controls turned out to have an identical problem — the `RETRY`
disposition is real, but nothing acts on the attempt count or spacing automatically),
the marketing `safety-section.tsx` (both the demo guard bar and the explained-guards
list), `/docs/safety-configuration`, `lib/docs.ts`'s summary of that page, and — most
seriously — **`/trust`'s regional compliance notes**, which stated as fact that "India —
calling windows default to 09:00–20:00 IST and are enforced per campaign" and the
equivalent for US area codes. That's a false regulatory-compliance claim on the one page
a prospect reads specifically to assess compliance risk before signing.

**Fixed:** every surface above now either omits the claim or says plainly that calling
windows (and, in the campaign editor, automatic retry) aren't enforced yet — using the
existing `NotWiredNotice` pattern, and `guardsFromHealth()`'s window guard now reports
`null` (renders as `OFF`, consistent with how every other unconfirmed guard already
behaves) instead of a hardcoded fake value.

**Still open:** the underlying feature. Either wire real enforcement — a per-campaign or
per-org window column, checked in `check_dial_allowed()` (the same place suppression is
now checked, so the pattern already exists), with queued-for-retry semantics — or leave
it permanently out of the product. What's fixed is that nothing lies about it in the
meantime.

**Depends on:** #1 (fixed) for a place to persist a window per org/campaign.

---

### #21 — `Organisation.logo_url` was missing from the ORM model
**S4 · FIXED · backend · `app/database/models.py`**

`logo_url` was added to the real `organisations` table by the invitations/storage
migration, but the SQLAlchemy `Organisation` class was never updated to declare it.
Found by `alembic check` while adding the `onboarded_at` column for the org-onboarding
gate (this iteration) — it reported a phantom `remove_column` operation for `logo_url`,
which meant the model and the database had silently drifted.

**Impact.** Low on its own (the column still worked fine through raw asyncpg in the
repositories, which don't go through the ORM), but `alembic check`'s no-drift guarantee
was already broken before this iteration touched anything, and a future autogenerate
run would have proposed actually dropping a column that's in active use.

**Fixed.** Added `logo_url: Mapped[str | None] = mapped_column(Text)` to the model.
`alembic check` reports no drift again.

---

### #22 — Half the real runtime dependencies were undeclared in `pyproject.toml`
**S2 · FIXED · backend · `apps/api/pyproject.toml`**

`SQLAlchemy`, `asyncpg`, `alembic`, `psycopg[binary]`, and `PyJWT` are all imported
throughout `app/` and actively used — auth verification, every database query, every
migration — but none of them were listed in `dependencies`. Found while adding
`cryptography` for the Integrations feature and checking what else was missing.

**Impact.** `pip install -e ".[dev]"` — the README's own quick-start command — would
install a service that immediately fails at import time on a machine that didn't
already happen to have these packages from some earlier, undocumented `pip install`.

**Fixed.** Added all five, plus `cryptography` (already a transitive dependency, now
declared directly since `app/core/crypto.py` imports it).

---

### #23 — Root `.env.example` still had `CALLFLOW_DRY_RUN` and no Supabase config at all
**S2 · FIXED · config · `.env.example`**

The dry_run removal pass (iteration 4) updated every other reference to
`CALLFLOW_DRY_RUN` but missed the root `.env.example`, which still listed it as a
real, honored variable. Separately, `.env.example` predated the entire Supabase/auth
build-out — it had no `SUPABASE_*`, `DATABASE_URL`, `PHONE_HASH_PEPPER`,
`RESEND_*`, or `SITE_URL` entries, despite `config.py` reading all of them.

**Impact.** Anyone following the README's `cp .env.example .env` step would set a
variable that does nothing and skip every variable persistence and auth actually
require, then hit confusing failures with no clue why.

**Fixed.** Rewritten to match `config.py` field-for-field, with `CALLFLOW_DRY_RUN`
removed and `PROVIDER_CREDENTIALS_KEY` (new, this iteration) included.

---

### #24 — `FEATURES.md` does not exist
**S3 · OPEN · docs**

`CLAUDE.md`'s own document map describes it as "Target state, F1–F52, with build
order... read-only; it is the spec," and `SYSTEM.md`, `ISSUES.md`, and `CLAUDE.md`
itself reference specific `F<n>` numbers throughout (F2, F14, F17, F19, F47, and
dozens more) as though resolving them against a real document. Checked `git log --all
-- FEATURES.md`: it has never existed at any commit in this repository's history.

**Impact.** Every `F<n>` citation across three governing documents points at nothing.
Low severity because the numbers still function as stable, consistently-used labels —
`SYSTEM.md` §12's gap map is a real, accurate substitute in practice — but a new
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

## Template for the next iteration

```
## Iteration N — YYYY-MM-DD · <what prompted the audit>

### #N — <one-line title>
**S? · OPEN · area · file**

<What is wrong, factually.>

**Impact.** <Who is hurt and how. Say if it is currently masked and by what.>

**Fix.** <The intended fix, with the FEATURES.md reference if there is one.>

**Depends on / Blocks:** <ids>
```
