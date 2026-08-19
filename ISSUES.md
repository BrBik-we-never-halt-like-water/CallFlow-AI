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
| [#7](#7--escalation-resolution-is-component-state)                                                                                | S3  | Escalation resolution is component state                                                                              | web            | it-1  | **FIXED**        |
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
| [#54](#54--a-retried-call-after-a-connection-error-classification-could-double-dial-without-counting-against-the-per-run-ceiling) | S3  | A retried call after a connection-error classification could double-dial without counting against the per-run ceiling | backend        | it-13 | **FIXED**        |
| [#55](#55--7-of-call-es-reachable-error-codes-fell-through-to-a-generic-internal-error)                                          | S3  | 7 of CALL-E's reachable error codes fell through to a generic internal error                                          | backend        | it-14 | **FIXED**        |
| [#56](#56--a-vendor-specific-key-leaked-above-the-integration-boundary)                                                          | S4  | A vendor-specific key leaked above the integration boundary                                                           | backend        | it-14 | **FIXED**        |
| [#57](#57--list_events-dropped-cursor-pagination)                                                                                | S4  | `list_events()` dropped cursor pagination                                                                             | backend        | it-14 | **FIXED**        |
| [#58](#58--claude-mds-no-pii-in-logs-guarantee-had-no-actual-filter-behind-it)                                                    | S2  | CLAUDE.md's "No PII in logs" guarantee had no actual filter behind it                                                 | backend        | it-14 | **FIXED**        |
| [#59](#59--idempotency-key-is-now-stable-per-run-and-contact-half-of-54)                                                          | S3  | Idempotency key is now stable per run and contact (half of #54)                                                       | backend        | it-16 | **FIXED**        |
| [#60](#60--campaigns-dialled-contacts-strictly-one-at-a-time)                                                                     | S2  | Campaigns dialled contacts strictly one at a time                                                                     | backend        | it-17 | **FIXED**        |
| [#61](#61--no-webhook-receiver--every-call-outcome-only-ever-arrived-via-polling)                                                 | S3  | No webhook receiver - every call outcome only ever arrived via polling                                                | backend        | it-18 | **FIXED**        |
| [#62](#62--call-es-own-task_completedcompletion_confidenceevidence-and-full-retry-history-were-discarded)                        | S3  | CALL-E's own `task_completed`/`completion_confidence`/`evidence` and full retry history were discarded                | backend        | it-19 | **FIXED**        |
| [#63](#63--live-per-call-events-were-declared-and-plumbed-but-had-no-consumer)                                                    | S4  | Live per-call events were declared and plumbed but had no consumer                                                    | backend        | it-20 | **FIXED**        |
| [#64](#64--campaigns_writes-for-all-policy-silently-re-granted-every-operator-full-org-wide-campaign-visibility)                  | S1  | `campaigns_write`'s `for all` policy silently re-granted every operator full org-wide campaign visibility             | backend        | it-21 | **FIXED**        |
| [#65](#65--the-invite-accept-page-showed-this-invitation-isnt-valid-when-the-real-problem-was-being-signed-in-as-the-wrong-account) | S3  | Invite-accept page showed "invitation isn't valid" when the real problem was the wrong signed-in account              | web            | it-21 | **FIXED**        |
| [#66](#66--create_or_refresh_invitation-trusted-a-caller-supplied-identity-instead-of-deriving-it)                                | S2  | `create_or_refresh_invitation()` trusted a caller-supplied identity instead of deriving it                            | backend        | it-21 | **FIXED**        |
| [#67](#67--a-second-orphaned-migration-on-the-shared-database-same-failure-mode-as-before)                                        | S1  | A second orphaned migration on the shared database, same failure mode as before                                      | backend        | it-21 | **FIXED**        |
| [#68](#68--no-one-could-ever-actually-accept-their-first-invitation)                                                              | S1  | No one could ever actually accept their first invitation - RLS blocked the lookup                                    | backend        | it-21 | **FIXED**        |
| [#69](#69--dropdownmenu-popover-and-dialog-rendered-light---then-invisible---on-an-otherwise-all-dark-app-shell)                  | S2  | DropdownMenu/Popover/Dialog rendered light, then invisible after the first fix attempt                                | web            | it-21 | **FIXED**        |
| [#70](#70--appprofile-never-had-dark-canvas-applied-and-toasts-viewport-was-never-portaled-anywhere)                              | S3  | `/app/profile` never had `.dark-canvas` applied; Toast's viewport was never portaled anywhere                         | web            | it-21 | **FIXED**        |
| [#71](#71--viewer-role-had-a-correct-backend-and-a-completely-unenforced-frontend)                                                | S2  | Viewer role had a correct backend and a completely unenforced frontend                                               | web            | it-22 | **FIXED**        |
| [#72](#72--pending-invitations-showed-no-pending-status-in-the-team-list)                                                          | S3  | Pending invitations showed no pending status in the Team list                                                        | web            | it-22 | **FIXED**        |
| [#73](#73--toasts-18-fix-depended-on-an-element-that-doesnt-exist-on-every-page)                                                  | S3  | Toast's §18 fix depended on an element that doesn't exist on every page                                              | web            | it-22 | **FIXED**        |
| [#74](#74--postruns-had-no-idempotency-key-a-retried-request-could-start-a-second-real-run)                                       | S2  | `POST /runs` had no idempotency key - a retried request could start a second real run                                 | backend + web  | it-23 | **FIXED**        |
| [#75](#75--a-run-in-progress-when-the-api-restarted-stayed-running-forever)                                                       | S2  | A run in progress when the API restarted stayed "running" forever                                                     | backend        | it-23 | **FIXED**        |
| [#76](#76--there-was-no-way-to-actually-stop-a-run-once-started)                                                                  | S2  | There was no way to actually stop a run once started                                                                  | backend + web  | it-23 | **FIXED**        |
| [#77](#77--a-suppressed-contact-still-reserved-rate-limit-and-daily-budget-it-would-never-use)                                    | S3  | A suppressed contact still reserved rate-limit and daily-budget it would never use                                    | backend        | it-23 | **FIXED**        |
| [#78](#78--a-hand-typed-phone-number-could-show-valid-in-the-grid-while-failing-e164-at-submission)                               | S2  | A hand-typed phone number could show valid in the grid while failing E.164 at submission                              | web            | it-24 | **FIXED**        |
| [#79](#79--a-runs-actual-guards-were-never-recorded-so-past-runs-became-unauditable-once-settings-changed)                        | S2  | A run's actual guards were never recorded, so past runs became unauditable once settings changed                      | backend + web  | it-25 | **FIXED**        |
| [#80](#80--call-duration-was-never-visible-anywhere-because-the-field-it-was-read-from-doesnt-exist-in-call-es-response)          | S2  | Call duration was never visible anywhere, because the field it was read from doesn't exist in CALL-E's response       | backend        | it-26 | **FIXED**        |
| [#81](#81--a-long-filter-value-overflowed-the-select-trigger-and-broke-the-escalations-filter-row-layout)                         | S2  | A long filter value overflowed the Select trigger and broke the escalations filter-row layout                        | web            | it-26 | **FIXED** (it-27) |
| [#82](#82--a-calls-own-top-level-status-can-go-terminal-before-its-nested-attempts-completed_at-does-permanently-freezing-duration_seconds-at-none)  | S2  | A call's own top-level `status` can go terminal before its nested attempt's `completed_at` does, freezing duration at `None` | backend        | it-27 | **FIXED**        |
| [#83](#83--settingsbillingpagetsx-had-no-permission-check-and-the-settings-tab-bar-showed-every-tab-to-every-role)             | S2  | `settings/billing/page.tsx` had no permission check; the settings tab bar showed every tab to every role (renumbered from #74 on merge) | web            | it-22 | **FIXED**        |
| [#84](#84--runs_select-and-escalations_select-recursed-infinitely-once-each-queried-the-other)                                    | S1  | `runs_select` and `escalations_select` recursed infinitely once each queried the other (renumbered from #75 on merge) | backend        | it-28 | **FIXED**        |
| [#85](#85--cloning-a-teammates-campaign-on-share-approval-failed-under-rls-for-every-non-adminowner-approver)                     | S1  | Cloning a teammate's campaign on share approval failed under RLS for every non-admin/owner approver (renumbered from #76 on merge) | backend        | it-29 | **FIXED**        |
| [#86](#86--the-share-request-approval-flow-performed-the-grant-before-the-atomic-decision-a-double-clone-race)                    | S2  | The share-request approval flow performed the grant before the atomic decision - a double-clone race (renumbered from #77 on merge) | backend        | it-29 | **FIXED**        |
| [#87](#87--every-theme-switch-flashed-white-because-chrome-adds-the-two-view-transition-frames-together)                          | S3  | Every theme switch flashed white, because Chrome adds the two view-transition frames together (renumbered from #74 on merge) | web            | it-31 | **FIXED**        |
| [#88](#88--87s-fix-was-scoped-to-an-attribute-that-comes-off-before-the-transition-ends)                                          | S3  | `#87`'s fix was scoped to an attribute that comes off before the transition ends (renumbered from #75 on merge) | web            | it-31 | **FIXED**        |
| [#89](#89--canvases-kept-painting-the-previous-themes-ink-until-something-remounted-them)                                         | S3  | Canvases kept painting the previous theme's ink until something remounted them (renumbered from #76 on merge) | web            | it-31 | **FIXED**        |
| [#90](#90--channel_members_insert-s-rls-check-verified-the-inserter-never-the-person-being-added)                                  | S1  | `channel_members_insert`'s RLS check verified the inserter, never the person being added                             | database       | it-32 | **FIXED**        |
| [#91](#91--invitations_repoaccept-could-abort-its-own-transaction-on-a-wrong-email-or-racing-accept)                              | S2  | `invitations_repo.accept()` could abort its own transaction on a wrong-email or racing accept                        | backend        | it-32 | **FIXED**        |
| [#92](#92--messages_repo-send_message-never-inserted-org_id-so-every-real-send-500d)                                              | S1  | `messages_repo.send_message()` never inserted `org_id`, so every real send 500'd                                     | backend        | it-32 | **FIXED**        |
| [#93](#93--test_anonymous_sees_nothing-assumed-anon-s-access-is-always-denied-via-rls-never-via-a-missing-grant)                  | S4  | `test_anonymous_sees_nothing` assumed `anon`'s access is always denied via RLS, never via a missing grant             | backend        | it-32 | **FIXED**        |
| [#94](#94--channel_members-had-a-delete-policy-but-no-delete-grant)                                                                | S2  | `channel_members` had a `DELETE` policy but no `DELETE` grant                                                          | database       | it-33 | **FIXED**        |
| [#95](#95--an-org-admin-renaming-a-channel-they-hadnt-joined-got-back-nothing-even-though-the-rename-worked)                       | S2  | An org admin renaming a channel they hadn't joined got back nothing, even though the rename worked                     | database       | it-33 | **FIXED**        |
| [#96](#96--useorgrealtime-broke-entirely-the-moment-a-second-component-watched-the-same-table)                                    | S1  | `useOrgRealtime` broke entirely the moment a second component watched the same table                                   | web            | it-33 | **FIXED**        |
| [#97](#97--patch-messagesid-edit-500d-on-every-real-edit)                                                                          | S1  | `PATCH .../messages/{id}` (edit) 500'd on every real edit                                                              | backend        | it-33 | **FIXED**        |
| [#98](#98--starting-a-dm-with-the-same-teammate-twice-created-two-separate-conversations)                                          | S2  | Starting a DM with the same teammate twice created two separate conversations                                          | database       | it-34 | **FIXED**        |
| [#99](#99--the-chat-unread-badge-hook-re-ran-chats-heaviest-query-on-every-message-sent-anywhere-in-the-organisation-for-every-open-tab) | S2  | The chat unread-badge hook re-ran chat's heaviest query on every message sent anywhere in the org, for every open tab | web + backend  | it-34 | **FIXED**        |
| [#100](#100--cursor-pagination-could-silently-skip-or-repeat-a-message-under-an-exact-timestamp-tie)                               | S3  | Cursor pagination could silently skip or repeat a message under an exact-timestamp tie                                | backend        | it-34 | **FIXED**        |
| [#101](#101--chat-rls-treated-channel_memberscreated_by-as-permanent-never-re-checking-current-organisation-membership)            | S1  | Chat RLS treated `channel_members`/`created_by` as permanent, never re-checking current organisation membership       | database       | it-35 | **FIXED**        |
| [#102](#102--channel_members_select-s-member-branch-had-no-live-organisation-membership-check)                                     | S2  | `channel_members_select`'s member branch had no live organisation-membership check                                    | database       | it-36 | **FIXED**        |
| [#103](#103--opening-a-different-conversation-remounted-the-whole-chat-page)                                                       | S2  | Opening a different conversation remounted the whole chat page                                                        | web            | it-37 | **FIXED**        |
| [#104](#104--the-message-pane-never-auto-scrolled-to-the-newest-message)                                                           | S3  | The message pane never auto-scrolled to the newest message                                                            | web            | it-37 | **FIXED**        |
| [#105](#105--the-realtime-debounce-coalesced-a-burst-down-to-only-its-last-payload)                                                | S2  | The Realtime debounce coalesced a burst down to only its last payload                                                 | web            | it-38 | **FIXED**        |
| [#106](#106--no-replica-identity-full-on-the-three-chat-tables)                                                                    | S2  | No `replica identity full` on the three chat tables                                                                   | database       | it-38 | **FIXED**        |
| [#107](#107--messages_insert-had-no-org_id-check-channel_members_insert-already-had)                                               | S2  | `messages_insert` had no `org_id` check `channel_members_insert` already had                                          | database       | it-38 | **FIXED**        |
| [#108](#108--gitignores-supabase-entry-was-un-anchored)                                                                            | S3  | `.gitignore`'s `supabase` entry was un-anchored                                                                       | web            | it-38 | **FIXED**        |
| [#109](#109--appchat-served-a-cached-frozen-shell-to-every-visitor---opening-any-conversation-hung-on-the-loader-permanently)      | S1  | `/app/chat` served a cached, frozen shell to every visitor - opening any conversation hung forever                    | web            | it-39 | **FIXED**        |
| [#118](#118--resend_api_key-set-in-the-repo-root-env-never-reached-the-api-container-so-every-local-invitation-failed)            | S3  | `RESEND_API_KEY` never reached the API container - every local invitation failed                                      | infra + backend | it-40 | **FIXED**        |
| [#119](#119--password-reset-silently-sent-nothing-gotrue-had-no-smtp-transport-and-its-links-pointed-at-a-path-kong-does-not-route) | S2  | Password reset silently sent nothing - no SMTP transport, and emailed links 404 at the gateway                        | infra          | it-40 | **FIXED**        |
| [#120](#120--chat-never-updated-live---supabase-realtime-was-broken-at-three-separate-layers-each-hidden-behind-the-one-in-front-of-it) | S2  | Chat never updated live - Realtime broken at three layers (Kong keys, tenant host, missing `realtime` schema)         | infra          | it-41 | **FIXED**        |
| [#121](#121--some-realtime-joins-are-rejected-with-invalid-column-for-filter-org_id-during-a-page-load-burst---not-reproduced-not-fixed) | S3  | Some Realtime joins rejected during page-load burst - unreproduced                                                    | infra + web    | it-41 | OPEN             |
| [#122](#122--a-stalled-request-rendered-as-a-permanent-loader-because-nothing-on-the-path-from-fetch-to-poolacquire-had-a-timeout) | S2  | A stalled request rendered as a permanent loader - no timeout anywhere from `fetch()` to `pool.acquire()`             | web + backend  | it-42 | **FIXED**        |
| [#123](#123--every-deploy-to-dev-has-failed-for-20-hours-its-database-is-stamped-at-an-alembic-revision-that-exists-nowhere-in-this-repository) | S1  | Every deploy to dev fails - dev's database is stamped at a revision that exists nowhere in the repo                   | infra          | it-42 | **FIXED**        |
| [#124](#124--a-conversation-stuck-on-its-loader-forever-after-both-of-its-requests-returned-200) | S2  | Conversation stuck on its loader forever, after both its requests returned 200                                        | web            | it-42 | **FIXED**        |
| [#125](#125--a-500ms-anti-flicker-floor-could-stay-raised-forever-and-it-gated-the-entire-conversation-panel) | S2  | A 500ms anti-flicker floor could stay raised forever, and it gated the whole conversation panel                       | web            | it-42 | **FIXED**        |
| [#126](#126--accepting-an-invitation-offered-a-signup-form-to-people-who-already-have-an-account) | S2  | Accepting an invitation offered a signup form to people who already have an account                                   | web + backend  | it-43 | **FIXED**        |
| [#127](#127--your-role-in-one-organisation-decided-whether-you-could-leave-it) | S2  | Your role in one organisation decided whether you could leave it - mixed-role members got stranded                    | web            | it-43 | **FIXED**        |
| [#128](#128--agent-drafts-followed-you-into-the-next-organisation) | S2  | Agent drafts followed you into the next organisation and prefilled a new agent there                                  | web            | it-43 | **FIXED**        |
| [#129](#129--an-operator-could-build-an-agent-and-then-had-no-way-to-remove-it) | S2  | An operator could build an agent and then had no way to remove it, their own included                                 | backend + web  | it-43 | **FIXED**        |
| [#130](#130--the-canvas-loop-measured-and-reallocated-itself-every-frame) | S3  | Every animated canvas forced a layout and reallocated its backing store 60x a second                                  | web            | it-44 | **FIXED**        |
| [#131](#131--the-wheel-picker-read-scrolltop-back-after-writing-it-forcing-a-layout-every-frame) | S3  | The wheel picker read `scrollTop` back after writing it - layout thrash on preset selection                            | web            | it-44 | **FIXED**        |
| [#132](#132--voice-agents-were-visible-to-every-member-missing-the-per-creator-silo-the-rest-of-the-product-already-had) | S2  | Voice agents were visible to every member - missing the per-creator silo campaigns and runs already had                | backend        | it-44 | **FIXED**        |
| [#133](#133--nine-icon-only-controls-had-hit-areas-below-44x44-and-no-control-moved-when-pressed) | S3  | Nine icon-only controls had hit areas below 44x44, and no control moved when pressed                                  | web            | it-45 | **FIXED**        |
| [#134](#134--settings-listed-an-integrations-tab-that-threw-you-out-of-settings) | S4  | Settings listed an Integrations tab that threw you out of Settings                                                     | web            | it-45 | **FIXED**        |

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

**S3 · FIXED (it-23) · backend + web · `app/database/repositories/escalations.py`, `app/api/v1/routes/escalations.py`, `components/app/escalation-card.tsx`, `lib/app-store.tsx`**

`Mark resolved` used to set local `useState`. Navigating away, reloading, or a second
person looking at the same item all lost it.

**Partly fixed in it-10 (see #46):** resolving dropped the item from the shared
`useAppStore().escalations` list, so the worklist/dashboard/nav badge updated together
within a session - the "nothing visibly updates" symptom went away, but nothing was
persisted.

**Actually fixed in it-23**, as part of the role-based UI roadmap's Phase 2
(`TEAM_COLLABORATION_ROADMAP.md`): a real `public.escalations` table (`status`,
`assigned_to`, `assigned_by`, `resolved_by`, `resolved_at`), one row per escalating call
outcome, inserted by application code the moment `campaign_runner.py`'s (or the webhook
path's) outcome resolution lands on `Disposition.ESCALATED`/`UNREACHABLE`. `POST
/api/v1/escalations/{id}/resolve` writes it for real; RLS (not just the app's permission
check) is what stops a second person from resolving someone else's escalation, and a
reload or a different signed-in teammate now sees the same, correct state - reached
live, via Supabase Realtime, not just on next page load.

**Impact (historical).** An operator marking five escalations resolved and changing
page used to see them all come back. That's fixed - see above.

**Depends on:** #1 (fixed, it-1).

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

**Fix.** **Fixed in two parts.** Iteration 16 (module 3): the idempotency key is now
stable per `(run_id, contact)` (`CampaignRunner._idempotency_key()`) instead of a fresh
random suffix every attempt, so a retry is recognisable to CALL-E as a duplicate. Iteration
17 (module 4, concurrent dialling): `_calls_made` is now incremented as part of the same
locked check-and-reserve that admits a contact past the ceiling, *before* the dial is
attempted rather than after it returns successfully - a failed or lost-response attempt
still spent a real slot at CALL-E and now still counts, closing the other half of this
issue as a direct side effect of making the ceiling check race-safe under concurrency
(see `#60`).

**Depends on / Blocks:** related to `CALLE_INTEGRATION_STATUS.md` §3.5 (idempotency key
regenerated per attempt) and `#53` (introduced the reclassification that makes this
reachable).

## Iteration 14 - 2026-08-09 · CALL-E integration rebuild, module 1: error taxonomy completeness

First of a planned seven-module pass rebuilding the CALL-E integration for real - not
speculative feature work, each module targets a specific gap already documented in
`CALLE.md`/`CALLE_INTEGRATION_STATUS.md`/this file's own #37/#52/#53/#54. Module 1 closes
the three smallest, most mechanical gaps before the riskier concurrency/idempotency work
(modules 2-4) builds on top of a complete, correctly-classified failure taxonomy.

### #55 - 7 of CALL-E's reachable error codes fell through to a generic internal error

**S3 · FIXED · backend · `apps/api/app/integrations/voice/engine.py`**

`_ERROR_CODE_MAP` mapped 12 of the 19 error codes actually reachable from `/v1/calls`
(the other 5 of CALL-E's 24 documented codes are Goals-only, correctly excluded since
Goals aren't integrated). The other 7 - `call_not_ready`, `not_found`, `invalid_request`,
`idempotency_conflict`, `result_schema_invalid`, `recipient_result_schema_invalid`,
`internal_error` - fell through to the unmapped-code default. Fail-closed to `INTERNAL`
either way, so no behaviour actually changed for most of them, but a future reader
couldn't tell "considered and mapped to INTERNAL" apart from "never looked at."

**Fix.** All 7 now map explicitly: `call_not_ready`/`not_found` (poll-only, transient read-
after-write races) join `provider_unavailable` in the retryable bucket; the rest map to
`INTERNAL` as configuration/request-shape problems, explicitly rather than by omission.

### #56 - A vendor-specific key leaked above the integration boundary

**S4 · FIXED · backend · `apps/api/app/services/campaign_runner.py`**

`campaign_runner.py` (in `services/`, above `integrations/voice/`) built
`metadata = {"call-e/customerMetadata": {...}}` - a vendor-flavoured key living outside the
one file CLAUDE.md's dependency-inversion rule says should ever speak CALL-E's name. Not a
functional bug (`metadata` is a fully free-form bag on CALL-E's side, confirmed against the
generated SDK model - no required shape or namespacing), just a boundary breach.

**Fix.** Metadata is now built as a plain, vendor-neutral dict; the vendor-named wrapper is
gone entirely rather than moved, since nothing ever required it.

### #57 - `list_events()` dropped cursor pagination

**S4 · FIXED · backend · `apps/api/app/integrations/voice/engine.py`, `protocol.py`**

`EngineGateway.list_events()` forwarded `limit` to the SDK but never `cursor`, even though
the endpoint is documented as cursor-paginated and the SDK's own `list_events()` accepts
one. Moot today - nothing calls this method yet (module 7 of this same rebuild plans to) -
but would have silently truncated every long call's events to page one the moment
something did.

**Fix.** `cursor` now threads through `EngineGateway.list_events()` and the `VoiceProvider`
protocol signature it conforms to.

## Iteration 15 - 2026-08-09 · CALL-E integration rebuild, module 2: structured logging + a real redaction filter

### #58 - CLAUDE.md's "No PII in logs" guarantee had no actual filter behind it

**S2 · FIXED · backend · `apps/api/app/core/logging.py` (new), `main.py`, `campaign_runner.py`, `api/v1/routes/runs.py`**

CLAUDE.md's non-negotiable #5 stated, as fact, that "Numbers, tokens, keys, and transcript
bodies are redacted by a global filter - and the redaction is tested." No such filter
existed anywhere in the codebase - `logging.basicConfig(level=logging.INFO)` was the entire
logging setup (`main.py`). Redaction was real but 100% dependent on every call site
remembering to call `mask()` (`domain/safety.py`) before logging a phone number; a stated
safety guarantee resting entirely on discipline, with no backstop, is exactly the kind of
gap that stays invisible until the one call site that forgot.

Separately: no log line carried enough context to trace one call's whole lifecycle (dial →
poll → resolve) as a single unit - each line stood alone, correlated only by eye.

**Fix.** `app/core/logging.py`: `RedactingFilter`, attached to every handler by the new
`configure_logging()`, redacts E.164-shaped numbers and bearer/key-style tokens found in a
rendered message, and fully redacts known-sensitive `extra=` field values by name
(`transcript`, `phone`, `api_key`, `token`, `authorization`, `password`, `secret`) -
regardless of content, since a transcript is free text and not pattern-matchable the way a
phone number is. `mask()` stays the primary defence; this is the safety net for whatever a
call site misses. Also added `CallContext` (contextvars-based, composes across nesting):
`api/v1/routes/runs.py`'s background run task binds `run_id`/`org_id` for the run's whole
lifetime; `campaign_runner.py` binds `call_id` once a dial is placed, so every log line
touching one call - in this module and in `engine.py` - can be grepped together. Output is
text (human-readable, unchanged default) or one-JSON-object-per-line via
`CALLFLOW_LOG_FORMAT=json`, for a deployment that ships to a log aggregator.

**Tests.** `tests/test_logging.py` - redaction of raw numbers, format-arg numbers, and
several token shapes; sensitive-field-by-name redaction; context binding, nesting, and
leak-after-exit; both formatters. 16 new tests, 198/198 passing overall.

## Iteration 16 - 2026-08-09 · CALL-E integration rebuild, module 3: idempotency key correctness

### #59 - Idempotency key is now stable per run and contact (half of #54)

**S3 · FIXED · backend · `apps/api/app/services/campaign_runner.py`, `api/v1/routes/runs.py`**

Closes the idempotency-key half of `#54` and the previously-open item 5 in
`CALLE_INTEGRATION_STATUS.md` §3. `campaign_runner.py` built `Idempotency-Key` as
`f"{campaign.id}-{contact.phone}-{uuid.uuid4().hex[:8]}"` - a fresh random suffix on every
single dial, including a retry of the exact same logical attempt. `Idempotency-Key` exists
to protect exactly one scenario - a create-call request reaches CALL-E and a call gets
placed, but the response is lost before CallFlow sees it - and a random suffix defeats that
protection entirely: a retry with a new key cannot be recognised as a duplicate of anything.

**Fix.** `CampaignRunner` now takes an optional `run_id` (threaded from
`api/v1/routes/runs.py`, the persisted run's own id). `_idempotency_key()` builds
`f"{run_id}:{phone_hash(contact.phone)}"` when a run_id is present - stable across any
retry of this exact (run, contact) pair, since the rendered goal text for a given
(campaign, contact) is deterministic within one run, and distinct across two different runs
dialling the same contact, so an old run's key can never be replayed against a new one. Uses
`phone_hash()` rather than the raw number, in case the header value ever surfaces in a trace
or log outside CallFlow's own control. Without a `run_id` (ad hoc use, tests, no stable job
identity to key off of) it falls back to a fresh key every call, same as before this fix -
not idempotent, but no worse than the prior default either.

Does **not** close `#54` fully: `_calls_made` is still only incremented after `start_call`
returns successfully, so a retry after a connection-error classification still wouldn't
count against `max_calls_per_run`. Left for module 4, which has to redesign how
`_calls_made` is guarded anyway to be race-safe under concurrent dialling.

**Tests.** `tests/test_orchestrator.py` - same key across two calls for the same
(run_id, contact); different keys across two different run_ids for the same contact; raw
phone never appears in the key; falls back to a fresh key with no run_id. 4 new tests,
202/202 passing overall.

## Iteration 17 - 2026-08-09 · CALL-E integration rebuild, module 4: concurrent dialling

### #60 - Campaigns dialled contacts strictly one at a time

**S2 · FIXED · backend · `apps/api/app/services/campaign_runner.py`, `core/config.py`**

`CampaignRunner.run()` was `for contact in contacts: await self.run_one(...)` - every
contact dialled, polled to a terminal status (up to 900s), and resolved before the next
contact was even attempted. For a run of N contacts at roughly a minute or two per real
call, that's N times the wall-clock time the run actually needed. This is very likely the
real cause behind a user report that "calls placed take a little bit of time" - not
per-call dial latency (CALL-E's own infrastructure, outside this codebase's control - and,
per a live research pass, not a figure CALL-E publishes anywhere), but the *whole run*
taking N times longer than necessary because contacts were never allowed to overlap.

**Fix.** `run()` now dials up to `CALLFLOW_MAX_CONCURRENT_CALLS` (default 5 - CALL-E
publishes no rate-limit numbers, so this starts conservative) contacts at once via an
`asyncio.Semaphore`, using `asyncio.gather(..., return_exceptions=True)` so one contact's
own bug can't cancel every other contact's real, already-in-flight phone call - a failure
mode with no sequential analog, since a one-at-a-time loop never has more than one contact
in flight to abandon. `run()`'s returned list still matches the input contact order
regardless of which contact's call actually finishes first (`gather`'s own ordering
guarantee) - confirmed by test, not assumed.

Concurrency exposed a real, load-bearing race that a sequential loop could never trigger:
`run_one()` read `self._calls_made` (the per-run ceiling counter) and incremented it only
*after* a successful dial, so two contacts dialled at the same moment could both read the
same under-the-ceiling count before either incremented, admitting more calls than
`max_calls_per_run` allows. Fixed by making the check-and-reserve one atomic step under a
new `asyncio.Lock`, held only for that brief moment (never around the dial/poll itself, so
concurrency is preserved) - and the reservation now happens *before* the dial is attempted,
not after it succeeds, which is also the second half of `#54`'s fix (a failed or
lost-response attempt still spent a real slot at CALL-E and must still count, per
CLAUDE.md's fail-closed rule).

**Tests.** `tests/test_orchestrator.py` - `ConcurrencyTrackingGateway` proves contacts
genuinely overlap in wall-clock time (a real `time.sleep()` inside the worker thread, not
the mocked event-loop sleep) and never exceed the configured limit; the ceiling holds
under real concurrent dialling (5 contacts, ceiling 2 → exactly 2 admitted); output order
survives concurrency. `test_progress_hook_fires_per_contact` updated - concurrent dialling
means two contacts' progress events can now interleave with each other, so it checks each
contact's own event order (dialing, then resolved) rather than a fixed global sequence.
6 new/changed tests, 206/206 passing overall.

## Iteration 18 - 2026-08-09 · CALL-E integration rebuild, module 5: webhook receiver

### #61 - No webhook receiver - every call outcome only ever arrived via polling

**S3 · FIXED · backend · `api/v1/routes/webhooks.py` (new), `services/campaign_runner.py`, `database/repositories/runs.py`, migration `202608091200`**

CALL-E supports a per-request `webhook_url` on `POST /v1/calls`, delivering terminal events
(`call.completed`, `call.failed`, `call.result_validation_failed`) with a full `CallTask`
snapshot - and even ships an SDK module for it - but this codebase never populated
`webhook_url`, and no receiver endpoint existed. Every outcome, always, arrived via
`_poll_until_done`'s 2-second polling loop - a self-imposed floor on how fast a completed
call is *noticed*, on top of module 4's fix for how fast contacts are *dialled*.

The real complication, not just missing plumbing: a webhook has no signed-in user behind
it, and CLAUDE.md is explicit that `privileged.acquire()` must never appear in a request
handler. Raised to the user as a genuine architectural fork rather than worked around
silently; the chosen approach (below) follows the exact precedent
`GET /api/v1/invitations/{token}` already set for the same shape of problem.

**Fix.**
- New migration `202608091200_calle_webhook_run_lookup.py`: one narrow SECURITY DEFINER
  function, `lookup_run_owner_for_webhook(run_id)`, resolving a run's `org_id`,
  `campaign_id`, and starter's `auth_user_id` - a lookup only, no write, matching
  `lookup_invitation`'s own shape and requiring no new grant (function EXECUTE defaults to
  PUBLIC in Postgres, confirmed by that same precedent having none either).
- New route `POST /api/v1/webhooks/calle/{secret}`: `database.anonymous()` calls the lookup
  function to resolve identity, then the actual write goes through the *ordinary*,
  already-RLS-correct `database.as_user()` path - as the run's own starter, who already
  held sufficient permission to start it in the first place. No new RLS-bypassing write
  path was needed at all. Unsigned by CALL-E (confirmed: its SDK's HMAC helpers are
  deprecated, "must not be used to parse current deliveries"), so `secret` - compared in
  constant time - is the entire trust boundary; a wrong secret gets 404, not 401/403.
- `CampaignRunner`'s metadata now includes `run_id` (omitted when there isn't one) so the
  receiver can attribute an event back to a run once CALL-E echoes it. The outcome-
  resolution logic (`_extract_result`/`_extract_transcript`/`triage`) that used to live
  only in `run_one()`'s tail is now `_resolve_outcome()`, a shared function both the
  polling path and the webhook call identically - one triage implementation, not two.
- `CALLFLOW_PUBLIC_API_URL` + `CALLFLOW_WEBHOOK_SECRET` (both empty by default) gate
  whether `webhook_url` is ever sent at all - unset either and this deployment falls back
  to polling only, unchanged from before this fix.
- Polling is **not** removed - it stays the backstop for a dropped delivery or a
  deployment with no webhook configured. Whichever path notices a call's terminal state
  first writes it; the other's eventual write is a harmless no-op update of the same data.

**Tests.** `tests/test_webhooks.py` - against the real database (skipped without
`DATABASE_URL`), following `test_rls_isolation.py`'s own precedent for exactly this reason:
a SECURITY DEFINER function or an RLS policy that looks right on paper is the expensive bug
to ship. Wrong/unconfigured secret → 404; unknown run → acked without error; missing
`run_id` in metadata → acked without error; a real tenant + real run → the persisted
outcome matches what polling would have produced (contact name, masked phone, disposition,
extracted fields, transcript); a second real tenant cannot see the first tenant's outcome
through this path. 6 new tests, 212/212 passing overall.

## Iteration 19 - 2026-08-09 · CALL-E integration rebuild, module 6: richer outcome data

### #62 - CALL-E's own `task_completed`/`completion_confidence`/`evidence` and full retry history were discarded

**S3 · FIXED · backend · `domain/entities.py`, `domain/triage.py`, `services/campaign_runner.py`, `database/repositories/runs.py`, `api/v1/routes/runs.py`, migration `202608091600`**

CALL-E computes a holistic judgment of whether each call actually accomplished its task -
`task_completed` (bool), `completion_confidence` (`{score, label}`), `evidence[]` (short
supporting strings) - on every terminal call, independent of whatever a campaign's own
`result_schema` extracts. None of the three had a field on `CallOutcome`; all three were
silently dropped on arrival. Separately, CALL-E tracks every dial attempt at a recipient in
`recipients[0].attempts[]`, but `campaign_runner.py` kept only whichever one
`_final_attempt()` picked for its transcript - a redialled contact's earlier attempts (a
`no_answer` before the one that connected, say) left no trace at all.

Re-confirmed against the *live* OpenAPI spec before writing any code against it (not just
this doc's Aug-8 research pass) - the installed SDK doesn't type these fields at all
(`get_call()`'s success response is untyped `dict[str, Any]`, confirmed by reading
`calle/generated/api/calls/get_call.py` directly), so the SDK alone could neither confirm
nor deny they exist. The live spec confirms both: task-level only, never per-recipient.

**Fix.**
- New migration `202608091600_call_outcome_completion_signals.py`: five new columns on
  `call_outcomes` (`task_completed`, `completion_confidence_score`,
  `completion_confidence_label`, `evidence` jsonb, `attempts` jsonb). Kept separate from
  the existing `extracted` jsonb column deliberately - `extracted` is what a *campaign's*
  schema asked for; these are CALL-E's own meta-judgment, a different concern that could
  collide in field name with a campaign-defined one if merged together.
- `CallOutcome` gains the four scalar/list fields plus `attempts: list[AttemptSummary]`
  (a new small model: `status`/`started_at`/`completed_at`/`had_transcript` per attempt).
- `campaign_runner._resolve_outcome()` (shared by both the polling path and the module-5
  webhook receiver, so both extract and persist identically) now pulls all of these from
  the terminal payload; a new `_extract_attempts()` walks the full `attempts[]` list
  instead of `_final_attempt()`'s single pick.
- `triage()`: a new precedence rule - `task_completed is False` escalates, ranked below
  the explicit human-said-so signals (do_not_call/wants_human/frustration, which are more
  specific and more actionable) and above the plain status-based buckets (which have no
  signal at all to work with otherwise). `completion_confidence`/`evidence` are persisted
  and exposed but deliberately *not* weighted in `triage()` - a softer, fuzzier signal
  than a boolean judgment; left as data for now rather than another precedence branch.
- `GET /api/v1/runs/{id}` now serves all five new fields per outcome.

**Tests.** `test_triage.py` - `task_completed is False` escalates, beats negative-sentiment
retry, loses to `do_not_call`, and `None`/`True` are correctly *not* treated as `False`.
`test_orchestrator.py` - `_extract_attempts()` preserves every attempt (not just the
final one) and each attempt's `had_transcript` flag, empty-list fallbacks for malformed
input; `_resolve_outcome()` extraction of the three task-level fields, and correct
defaults when absent. `test_webhooks.py`'s real-database happy path extended to assert
all five new fields round-trip correctly end to end, including a two-attempt retry
history. 12 new tests, 224/224 passing overall.

## Iteration 20 - 2026-08-09 · CALL-E integration rebuild, module 7 (final): live per-call events

### #63 - Live per-call events were declared and plumbed but had no consumer

**S4 · FIXED (backend) · `api/v1/routes/runs.py`, `integrations/voice/engine.py` (cursor fix already in `#57`)**

`EngineGateway.list_events()` existed and `VoiceCapability.LIVE_EVENTS` was declared
`supported=True`, but nothing in `campaign_runner.py` or any route ever called it -
dashboard progress came entirely from polling `get_call()`'s coarse `status` field, unable
to see any transition faster than the 2-second poll interval, or any warning/error-level
diagnostic CALL-E logged mid-call.

Checked the actual response shape before building against it, since the SDK doesn't type
this endpoint's success response either (same `dict[str, Any]` pattern as `#62`'s
finding): it's a **developer/ops event log** (`debug`/`info`/`warning`/`error` levels, a
human-readable `message`, the `status` at that moment), not a turn-by-turn *conversation*
stream - a correction to this doc's and `CALLE_INTEGRATION_STATUS.md`'s original framing
of what this capability actually is.

**Fix.** New `GET /api/v1/runs/{run_id}/calls/{provider_call_id}/events`, on demand rather
than fetched automatically for every call - most calls never need this level of detail, and
fetching it unconditionally would double the request volume against CALL-E for data most
calls don't need inspected. Confirms the requested `provider_call_id` actually belongs to a
contact in the caller's own run (itself org-scoped via RLS) before proxying, so a caller
cannot probe an arbitrary CALL-E call id through their session. A real engine error (rate
limited, provider down) becomes a `502` with the classified `DialFailure`, not an unhandled
exception.

**Explicitly out of scope.** No frontend consumption of this endpoint was built - this
whole rebuild (modules 1-7) was scoped to the backend integration itself; an actual
dashboard control to view a call's event log is a real, separate decision, flagged back to
the user rather than built silently as scope creep.

**Tests.** `test_run_events.py` - against the real database, following this suite's own
precedent for anything RLS-adjacent: unknown run and call-id-not-in-this-run both 404;
missing API key 400; a classified engine error 502, not an unhandled exception; the happy
path returns events in order with `details` intact; `cursor` forwards to the engine. 6 new
tests, 230/230 passing overall.

---

**This closes the CALL-E integration rebuild** (modules 1-7, iterations 14-20). Every item
`CALLE_INTEGRATION_STATUS.md` tracked as open is now fixed; that doc's own status line has
been updated to say so rather than left to go stale again.

## Iteration 21 - 2026-08-09 · role-based UI roadmap, Phase 1: per-creator visibility silo

### #64 - `campaigns_write`'s `for all` policy silently re-granted every operator full org-wide campaign visibility

**S1 · FIXED · `alembic/versions/202608092100_split_campaigns_write_policy.py`**

Phase 1 narrowed `campaigns_select`/`runs_select`/`call_outcomes_select` so an operator sees
only what they created (migration `202608092000`) - but `campaigns_write` was declared
`for all` (one policy covering select/insert/update/delete). Postgres combines multiple
permissive policies for the same command with OR, so that policy's role-only check - true
for any operator in the org - was also being consulted for SELECT, silently re-granting
every operator full org-wide campaign visibility regardless of who created what. `runs` and
`call_outcomes` never had this problem: their write policies were already split per command
from their original migration (`202608070900`) - `campaigns_write` was the one table using
`for all`.

**Impact.** Every operator could see every teammate's campaign for as long as `d4bcc27a2b70`
was live, defeating the entire point of the silo for that one table. `runs`/`call_outcomes`
were never affected.

**Caught by** the new cross-member RLS test added in the same iteration
(`test_operator_cannot_see_a_teammates_campaign`, `tests/test_rls_isolation.py`) - it failed
against the real database on first run, which is what surfaced this before it shipped.

**Fix.** Split `campaigns_write` into `campaigns_insert`/`campaigns_update`/`campaigns_delete`,
each scoped to its own command - same role check as before, so no behavioural change on
paper. Confirmed against the live database (a throwaway, rolled-back probe) that for UPDATE
and DELETE specifically, Postgres also intersects the command's own `USING` clause with any
applicable SELECT policy's `USING` clause, so an operator's update/delete reach now
automatically narrows to campaigns they created too - matching the actual product spec
("no other teammate's campaign, nothing" for an operator), not just SELECT. INSERT is
unaffected by that intersection (no existing row to combine against); forging `created_by`
on insert is a pre-existing, unrelated gap this migration does not widen.

### Per-creator visibility silo, shipped

`campaigns.created_by` and `runs.started_by` existed since `202608070900` but were
write-only - no policy read them, no query selected them, no API response returned them.
`campaigns_select`/`runs_select`/`call_outcomes_select` (migration `202608092000`) now add
an owner-or-admin-or-viewer branch alongside the org-member check, so an operator's plain
org-scoped query returns only their own rows; owner/admin/viewer are unaffected. `GET
/api/v1/campaigns`, `GET/PATCH .../campaigns/{id}`, `GET /api/v1/runs`, and `GET
/api/v1/runs/{id}` now return `created_by`/`started_by` plus the creator's name/avatar
(joined to `users`), so an admin/owner/viewer's org-wide view can attribute each row to
whoever made it. New `GET /api/v1/runs/team-summary` (gated on the new
`Permission.RUNS_READ_TEAM`, granted to owner/admin/viewer, not operator) returns call
volume grouped by teammate, for the admin/owner dashboard's per-teammate breakdown chart
(no frontend consumer yet - backend-only, by design, per this iteration's scope).

**Tests.** 5 new cross-member RLS tests in `tests/test_rls_isolation.py` (two operators in
one org: neither sees the other's campaign/run/call-outcome; admin and viewer see both;
`summarize_by_member` reflects the caller's own RLS scope) plus 5 new permission-matrix
tests in `tests/test_permissions.py`. 238/238 passing overall.

**Depends on / Blocks:** signup → invite → role enforcement was verified (not rebuilt) as
part of the same phase - already correct, covered by the existing RLS/permission suites
this iteration extends.

### #65 - The invite-accept page showed "this invitation isn't valid" when the real problem was being signed in as the wrong account

**S3 · FIXED · web · `app/(auth)/accept-invite/[token]/page.tsx`**

Opening a valid invite link while already signed in as a *different* account (e.g. the
owner who sent the invite, opening their own link to check it) showed a "Join {org}"
button unconditionally. Clicking it tried to accept the invitation as whoever was
currently signed in, which the backend correctly rejects - but with a generic message
("...may have expired, already been used, or been sent to a different email address")
that reads as the invitation being broken, when the actual problem is which browser
session is active.

**Fix.** The page now compares the signed-in session's email to the invitation's target
email. On a mismatch it says so directly ("You're signed in as X, but this invitation was
sent to Y") with a **Sign out** button - `useSession()`'s existing auth-state-change
listener re-renders the page into the real signup form once signed out, no manual
redirect needed. Separately, the not-yet-signed-in signup form now shows the target email
as a read-only field alongside Name and Password, so it's never ambiguous which address
is being used.

### #66 - `create_or_refresh_invitation()` trusted a caller-supplied identity instead of deriving it

**S2 · FIXED · database · migration `202608092300_invitation_invited_by_from_caller_identity`**

Found via a Supabase Postgres security-checklist pass, prompted by testing the new
`npm run db:migrate` scripts turning up an unrelated orphaned migration (below) and
prompting a fuller audit of the role/RLS flow. `public.create_or_refresh_invitation()`
(migration `e15f3d9a2c78`) correctly anchors its *authorisation* checks
(`has_org_role`/`can_grant_role`) to the caller's own identity via `current_user_id()` -
but took `target_invited_by` as a plain argument and wrote it verbatim into
`invitations.invited_by`, never checking it matched the caller.

**Impact.** This function is `SECURITY DEFINER` in the exposed `public` schema with
`EXECUTE` granted to `anon`/`authenticated` (confirmed live, `has_function_privilege`) -
Supabase's Data API exposes every public function as an RPC endpoint by default. The
one real call site (`org_repo.create_invitation()`) always passed the authenticated
caller's own id, so the application itself was never affected - but nothing stopped a
caller reaching the function directly (e.g. via Supabase's REST RPC surface, entirely
outside this backend) from forging who an invitation credits.

**Fix.** Dropped `target_invited_by` as a parameter; the function now derives it from
`public.current_user_id()` itself, the same anchor already used for the authorisation
checks - the exact pattern `create_organisation()` already used correctly. The one call
site is unaffected since it always passed its own id.

**Also found in the same audit, clean:** every UPDATE policy has a `WITH CHECK`, RLS is
enabled *and* forced on every tenant table, no deprecated `auth.role()` usage anywhere,
no unprotected views. Every other `SECURITY DEFINER` function either takes no caller
identity as an argument at all or (like `create_organisation()`) already derives it
itself - `create_or_refresh_invitation()` was the one exception.

### #67 - A second orphaned migration on the shared database, same failure mode as before

**S1 · FIXED · database · migration `202608092200_reconcile_orphaned_run_safety_columns`**

While verifying the new `npm run db:migrate` script, `alembic_version` on the shared
database had advanced to `a3f7c9e2b6d8` - a revision with no file anywhere in this
repo's git history, checked across every local and remote branch. Same root cause as the
first occurrence (`202608091800_reconcile_orphaned_run_columns`, iteration 19/20 window):
almost certainly another uncommitted/discarded worktree or branch applying a migration
directly against the shared Supabase instance.

**Found:** five orphaned, all-`null`, unreferenced columns on `public.runs` mirroring
`public.org_safety_settings`'s own columns (`max_calls_per_run`, `allowlist`,
`calls_per_window`, `window_minutes`, `daily_budget`) - reads as an in-progress "snapshot
the org's safety settings onto the run at start time" feature, schema-only, nothing wired
to it yet. Confirmed none of Phase 1's RLS policies were touched by inspecting the live
policy definitions directly rather than assuming.

**Fix.** Same approach as the first occurrence: a new idempotent migration formally
adopts the columns (`add column if not exists`) rather than silently re-stamping past
them, so a fresh database can still reach the same schema. `alembic_version` was restamped
back to the last known-good revision by the user directly against the database (the
raw `UPDATE` on a system table was correctly blocked by this session's own permission
classifier as a hard-to-reverse action), then `alembic upgrade head` replayed both this
migration and `#66`'s fix. Recommend investigating what's producing these - twice in one
session against a shared database is a pattern, not a fluke.

**Verification.** `npm run db:migrate` (no-op, already at head) · `npm run db:generate`
(produces an empty no-op migration - confirms no undeclared ORM drift, file discarded) ·
`npm run db:reset` (confirmed it refuses without `--yes`, not actually run) ·
`pytest -q` 238/238 · `ruff check app tests` clean · `alembic history` shows a clean
linear chain from `b9d4f1a6c832` through `d7f3a8c2e951` (head).

### #68 - No one could ever actually accept their first invitation

**S1 · FIXED · database · migrations `202608092400`, `202608092500`**

Found by the user's own manual testing (five real invite attempts across five real
temp-mail addresses, all failing identically), after which every one of them turned out
to still have zero membership in the org they'd been invited to, despite each one having
signed up successfully. `invitations_repo.accept()`'s lookup was:

```sql
select ... from public.invitations i
join public.organisations o on o.id = i.org_id
where i.token = $1
```

run on the RLS-scoped `authenticated` connection. `invitations_select`'s policy correctly
lets an invitee see their own pending invitation by email match - but `organisations_select`
is plain `is_org_member(id)`, and a brand-new invitee is by definition not yet a member of
the org they're being invited to. The `join` silently dropped the row the instant it
reached `organisations`, so the whole query returned nothing, `accept()` returned `None`,
and the route reported the generic "this invitation isn't valid" message - for every
single real first-time acceptance, indistinguishable from an actually-invalid invitation.
A chicken-and-egg RLS problem: you need to already be a member to see the org row, but
seeing the org row was a precondition (via this join) for becoming one.

**Impact.** This has almost certainly never worked, for anyone, since the tables were
created - masked because no test exercised a genuine brand-new-user acceptance end to
end; existing coverage only ever exercised invitation *creation* and the RLS *write*
guards on `memberships_insert`, never a real first-time accept. The frontend fix from
`#65` (showing a clear "sign out, wrong account" message) made the underlying bug more
visible rather than less, since it eliminated the one other plausible explanation
(being signed in as the wrong person) and left only this.

**Fix.** Same pattern already established for `create_organisation()` and
`create_or_refresh_invitation()` (`#66`) - a narrowly-scoped `SECURITY DEFINER` function,
`public.lookup_invitation_for_accept()`, resolves token → invitation + org name/slug,
bypassing only this one read. It exposes nothing the existing *anonymous*
`lookup_invitation()` preview function doesn't already expose to anyone holding the
token, unauthenticated - so this is strictly less exposure, not more. The actual
state-mutating operations (the membership `INSERT`, the invitation `UPDATE`) are
deliberately left as plain RLS-scoped queries, unchanged - `memberships_insert`'s
`has_valid_invitation()` check still independently guards the one operation that
actually grants access, preserving defense-in-depth. A same-session follow-up migration
(`202608092500`) fixed a `citext`/`text` column-type mismatch in the first version,
caught immediately by re-running the reproduction script before it reached a real user.

**Also closed in the same fix:** `accept()` never checked `expires_at`, only
`accepted_at` - an expired-but-never-accepted invitation could still be accepted. The
new lookup function computes `expired` server-side to avoid any app/DB clock-skew
comparison (the lesson from `#16`).

**Tests.** Two new tests in `tests/test_rls_isolation.py`, the exact gap that let this
ship: a genuine brand-new signup (real `auth.users` insert, firing the real trigger,
giving them their own auto-created org exactly like a real signup) accepting a real
invitation end to end, and an expired invitation correctly rejected. 240/240 passing
overall. Reproduced and verified against the live database with a standalone script
before and after each fix, not just via the test suite.

### #69 - DropdownMenu, Popover, and Dialog rendered light - then invisible - on an otherwise all-dark `/app` shell

**S2 · FIXED (two attempts) · web · `app/globals.css`, `dropdown-menu.tsx`, `disclosure.tsx`, `dialog.tsx`, `(app)/app/layout.tsx`, new `lib/hooks/use-portal-container.ts`**

The sidebar org-switcher dropdown and the dashboard's Team popover both rendered with a
white/light surface, reported by the user as visually broken against the dark `/app`
shell around them. First diagnosis: `.dark-chrome`/`.dark-canvas`/`.dark-panel-glass`
re-scope the generic surface/rule/text tokens to their dark equivalents only as CSS
custom properties on those specific elements, and `DropdownMenuContent`,
`PopoverContent`, and `Dialog`/`Sheet`'s content all render through a Radix `Portal`,
which mounts straight to `<body>` by default - outside the DOM subtree those classes
scope. First fix attempt: a `.dark-overlay` class re-scoping the same tokens
`.dark-chrome` does, applied directly to the three portaled components.

**That fix was itself broken** - caught by the user immediately after, from a screenshot
showing the invite dialog with no visible background, border, or text at all (only the
footer buttons, which carry their own styling, were visible). `.dark-overlay` referenced
`var(--dark-text)`, `var(--dark-surface)`, etc. - but those raw palette values are
themselves declared inside `.app-font-scope` (the `/app` layout's own wrapper `<div>`),
**not** at `:root`. A Radix portal mounts as a sibling of that div, not a descendant of
it, so it never inherited those tokens either - the exact same architectural gap
`ISSUES.md` #49 already documented for the *font*, now biting the *color* fix for the
same underlying reason. Setting `--text: var(--dark-text)` when `--dark-text` itself
resolves to nothing collapses every property built on it to its own initial value -
`transparent` for a background, effectively invisible for text.

**Real fix.** New `usePortalContainer()` hook (`useSyncExternalStore`, not an effect +
`setState` - `react-hooks/set-state-in-effect` is an error here exactly as it is for
`localStorage`/`matchMedia`, see `lib/hooks/use-external-store.ts`) that resolves
`document.getElementById('app-font-scope')`, falling back to `document.body` outside
`/app`. Passed as the `container` prop to all three components' Radix `Portal`, so the
portaled content becomes a genuine descendant of `.app-font-scope` and correctly
inherits both the font class (partially closing `#49`, for these three components only)
and the raw `--dark-*` tokens `.dark-overlay` depends on. `.dark-overlay` itself is
unchanged and correct - it was never the broken half.

Confirmed exclusively `/app`-only before applying any of this: `(auth)`/`(marketing)`
never import `DropdownMenu`, `Popover`, or `Dialog` - grepped every import site to be
sure, since forcing this on a component also used from a light-themed page (as
`Tooltip` and `Select` both are - `pricing-table.tsx` and `demo-form.tsx` respectively -
which is why those two were deliberately **not** touched) would have broken it there
instead of fixing anything.

**Follow-up (design, not a bug):** the user asked for these surfaces to carry the same
purple radial-gradient background as the main content canvas, not a flat dark fill, and
for `Select` (the role picker inside the invite dialog) to match too - `Select` had been
correctly left alone in the first pass since it's also used on a light marketing page.
`.dark-overlay` now applies `.dark-canvas`'s exact gradient formula, and `Select` applies
`.dark-overlay` conditionally (only when its portal actually resolves to `/app`'s scope,
via `isAppScopeContainer()`), leaving the marketing form untouched. Full narrative -
including exactly why the first `.dark-overlay` attempt shipped broken - lives in
`apps/web/DESIGN_NOTES.md` §17, not duplicated here.

### Remove a teammate: reassigns their org data, deletes their account (product decision)

Not a bug fix - a product decision, confirmed with the user while reviewing the Team
management screen. Removing a teammate used to be a one-line membership delete
(`org_repo.remove_member()`). Now, removing *someone else* (not leaving your own org,
which is unchanged):

1. Reassigns whatever they created in this organisation - `campaigns.created_by`,
   `runs.started_by` - to whichever admin/owner performed the removal, so their work
   survives them leaving instead of falling back to `null` the moment their account
   goes away.
2. Deletes their CallFlow account entirely, not just their membership in this one org -
   a full account removal, not a per-org one (the user's explicit choice over the
   narrower, initially-recommended "just this org" option). Any *other* organisation
   they belong to is unaffected by step 1 - this admin has no relationship to that
   org's data - and behaves exactly like a self-deleted account already does
   (`ISSUES.md` #13/#14/#17's cascade/retirement triggers, unchanged).

Implemented as `public.remove_member_and_reassign_data()` (migration `202608092600`), a
`SECURITY DEFINER` function following the same shape as `create_organisation()`/
`create_or_refresh_invitation()` - deleting `auth.users` needs privileges the
`authenticated` role never holds, and CLAUDE.md §4b is explicit that `privileged.acquire()`
must never appear in a request handler. Authorisation (`has_org_role`, `can_act_on_member`)
is re-checked inside the function itself as defense-in-depth, same reasoning as those two
functions - the route's own Python-side checks are still the primary gate.

The "Remove" action in the Team tab now requires typing the person's name to confirm
(mirroring the existing "delete this organisation" dialog's pattern) and states plainly
what's about to happen, rather than the previous single-click destructive menu item -
CLAUDE.md's own bar for a hard-to-reverse action.

Separately, the sidebar org-switcher (the dropdown listing every org the signed-in user
belongs to) is now admin/owner-only - an operator or viewer sees the current
organisation's name as a plain, non-interactive label instead, since switching between
orgs is a multi-org-management concern only admin/owner ever need.

**Tests.** Two new tests in `test_rls_isolation.py`: an admin removing an operator
reassigns their in-org campaign to the admin while leaving the operator's own
(unrelated) organisation's data untouched, and deletes their account entirely; a
same-rank operator cannot call the function directly, bypassing the API's own
`Permission.TEAM_REMOVE` check. 242/242 passing overall.

### #70 - `/app/profile` never had `.dark-canvas` applied, and Toast's viewport was never portaled anywhere

**S3 · FIXED · web · `components/layout/app-shell.tsx`, `components/ui/toast.tsx`**

Two more instances of the same family of bug as `#69`, found the same way - direct use, direct
screenshot. `/app/profile` is `AppShell`'s one "minimal chrome" route (its own layout branch,
single column, no sidebar) - a genuinely different code path from the normal route's content
column, and that branch's wrapper `<div>` simply never carried the `.dark-canvas` class the
normal branch has always applied. Every component on the page was already written correctly
against generic tokens (`Panel`, `Button`, `Input`); the whole page rendering light was a single
missing class, not a component-by-component gap.

Separately, `ToastProvider` (mounted at the true root layout, shared by every route) rendered
its `Viewport` in place - not portaled anywhere, since `@radix-ui/react-toast` has no `Portal`
export at all (confirmed against its own type declarations), unlike every other Radix primitive
touched in `#69`. A toast fired from `/app` picked up the light `:root` defaults regardless of
the page around it, for the same underlying reason as `#69`'s components, just via a different
mechanism (in-place rendering, not an escaping default portal) and needing a different fix
(`createPortal` by hand, not a `container` prop).

Full narrative for both, plus three related non-bug design changes shipped alongside them
(`.dark-chrome`'s background, sidebar divider visibility, the toast success icon) - all product
asks, not defects - lives in `apps/web/DESIGN_NOTES.md` §18, not duplicated here.

## Iteration 22 - 2026-08-09 · viewer role UI enforcement + invite/toast follow-ups

### #71 - Viewer role had a correct backend and a completely unenforced frontend

**S2 · FIXED · web · `campaign-editor.tsx`, `campaigns/page.tsx`, `campaign-card.tsx`, `runs/page.tsx`, `runs/new/page.tsx`, `contacts/page.tsx`, `app/page.tsx`, `escalation-card.tsx`, `organisation/page.tsx`, `settings/safety/page.tsx`**

`app/auth/permissions.py` has always correctly restricted the viewer role to read-only
permissions (`_READ_ONLY | runs:read_team`), and every mutating route correctly rejects a
viewer's request with a 403 - but no page in `/app` checked a permission before rendering
its action controls. A viewer could open the campaign editor and type into every field,
click "Start run," "Delete," "Save," "Invite," "Revoke," or "Mark resolved" anywhere in the
product, and only discover the action was blocked when the request came back rejected.

**Impact.** Actively misleading, not a security hole - the backend never let a write
through. But CLAUDE.md §4 #9 ("never show a success state for something that did not
happen") applies just as much to *showing an action as available* when it structurally
cannot succeed. `settings/safety/page.tsx` had the least coverage of any page in the app:
zero permission checks of any kind before this fix - anyone could see live Save buttons
and every field editable regardless of role.

**Fix.** The existing inline `profile.permissions.includes('permission:string')`
convention (already used correctly on the Contacts page, Organisation's Team pane, and the
dashboard's Team preview) was extended to every remaining page and action component rather
than introducing the unused `hasPermission`/`usePermission` helpers in
`lib/hooks/use-permission.ts`. `campaign-editor.tsx`'s pre-existing `readOnly`/`blocker`
pair (previously only accounting for built-in templates) was extended rather than
duplicated: `readOnly = isBuiltIn || !canWrite`, and `blocker` now names the actual reason
("Your role can view campaigns but not edit them") ahead of the built-in check.
`runs/new/page.tsx`'s composer is blocked entirely behind a `NotWiredNotice` for anyone
without `runs:start`, rather than just disabling the final Start button - contact-grid
interactions (CSV import, paste, add rows) don't persist server-side until Start is
clicked, but still read as actions a pure viewer shouldn't be invited to take.
`escalation-card.tsx`'s three actions ("Call back myself," "Reassign," "Mark resolved")
are gated on `escalations:resolve`; the dashboard's own condensed escalation preview uses a
separate, already non-interactive row component and needed no change.
`components/ui/image-upload.tsx` had no `disabled` prop at all - added one, wired to
`!canUpdate` (`org:update`) on the Organisation page's logo control, matching the org-name
field beside it that was already correctly gated.

**Verification.** `npm run type-check`, `npm run lint`, and `npm run build` all clean after
the full sweep. No backend changes - the permission matrix was already correct.

**Depends on / Blocks:** the role-based UI roadmap's Phase 0 (`.superpowers` plan
`moonlit-orbiting-blum.md`) names this exact gap for campaigns/runs/settings; this closes
Phase 0's nav-and-page-level piece for the viewer role specifically. Admin/operator-specific
UI restrictions from that same roadmap (per-teammate data silo, org/Settings nav hiding for
operator) remain separate, not-yet-started work.

### #72 - Pending invitations showed no pending status in the Team list

**S3 · FIXED · web · `app/(app)/app/organisation/page.tsx`**

`PendingRow` rendered a role tag and a Revoke button for an invited-but-not-yet-accepted
teammate with nothing marking the row as pending - visually indistinguishable at a glance
from an active member, aside from the row's position in a separate list the user had to
already know to look for.

**Fix.** A plain, neutral `<Tag>Pending</Tag>` now renders ahead of the role tag on every
pending row. Deliberately not a lamp colour - an earlier draft of this fix used
`--lamp-brass`, caught and reverted before landing, since lamp colours are reserved for
call state and nothing else (CLAUDE.md §4 #10) and "pending" is an invitation-lifecycle
label, the same class of thing `Tag` already exists for elsewhere in this table (role tags)
and on campaign cards (`Template`/`Custom`).

Revoke was checked against the backend as part of the same pass and already fully
invalidates the invitation - `invitations_repo`'s revoke path deletes the row outright, and
a revoked token's accept page correctly shows the standard invalid-invitation state. No
backend change was needed.

### #73 - Toast's §18 fix depended on an element that doesn't exist on every page

**S3 · FIXED · web · `app/globals.css`, `components/ui/toast.tsx` - supersedes half of `#70`/`apps/web/DESIGN_NOTES.md` §18**

`#70`'s Toast fix portaled `Viewport` to `.app-font-scope` (falling back to `document.body`)
and applied `.dark-overlay` only when `isAppScopeContainer()` confirmed the portal landed
inside that scope. The "Joined" toast fired from `/accept-invite/[token]` still rendered
light, because that route is in the `(auth)` group, which never renders `.app-font-scope`
at all - it's exclusively rendered by `(app)/app/layout.tsx`. There was no element for the
fallback to detect, so the dark-styling condition was never true on that page, regardless
of the portal fix working correctly everywhere it actually applied.

**Fix.** New `.toast-dark-overlay` class, applied unconditionally in `ToastItem` regardless
of the page that fired it. Unlike `.dark-overlay`, it does not reference `var(--dark-*)` -
those tokens are deliberately declared only inside `.app-font-scope` (see `#69`'s own note
on why setting a property to an unresolved custom property collapses it to its initial
value), so a class that must also work where that scope doesn't exist cannot depend on
them. `.toast-dark-overlay` hardcodes the literal colour values instead - the one
deliberate exception in this codebase to "reference the token, never the hex," commented
as such at the declaration site. With theming no longer dependent on DOM position, the
`createPortal` machinery `#70` added to `ToastProvider` was removed as unneeded complexity;
`Viewport` renders in place again (unaffected for positioning purposes, since `position:
fixed` doesn't care about DOM nesting).

**Depends on:** `#70` (this issue corrects that fix's Toast half; the `/app/profile`
`.dark-canvas` half of `#70` is unaffected and unchanged).

**Merge note (arbaaz/role-handling ⨯ dev/jatin-config-resend, 2026-08-11):** the two
branches independently used issue numbers `#74`-`#77` for entirely different findings.
Dev's numbering (below) is kept as-is since it's the larger set; the three colliding
entries from `arbaaz/role-handling` are renumbered `#83`-`#86` and ordered by their
original iteration's date, not by their new number - so `#83` (from `it-22`,
2026-08-09) appears before `#74` (from `it-23`, also 2026-08-09) is not guaranteed here,
but every renumbered entry is annotated inline. Nothing was deleted or rewritten beyond
the number itself and the cross-references to it.

### #83 - `settings/billing/page.tsx` had no permission check, and the settings tab bar showed every tab to every role

*(renumbered from `#74` on merge - collided with the idempotency-key finding below)*

**S2 · FIXED · web · `app/(app)/app/settings/billing/page.tsx`, `app/(app)/app/settings/layout.tsx`, `app/(app)/app/page.tsx`, `lib/api.ts`**

Found while closing out the Phase 0/Phase 1 gaps from the role-based UI roadmap
(`.superpowers` plan `moonlit-orbiting-blum.md`). Two related gaps, same root cause -
nothing in Settings ever checked a permission before this session's viewer-lockdown pass:

1. `billing/page.tsx` had no permission check of any kind - `SessionGate` only confirms
   *someone* is signed in. Any role, including operator/viewer, saw the organisation's
   real plan name and real live daily-usage numbers. `user-menu.tsx` already links
   operator/viewer to this exact route under a "My credits" label, implying a
   per-teammate view that didn't exist - they landed on the full org view instead.
2. `settings/layout.tsx`'s tab bar rendered all 4 tabs (Safety, API keys, Integrations,
   Billing) unconditionally, regardless of role - so anyone reaching any one settings
   page (via the "My credits" link, or by typing the URL - no route in this app has
   server-level redirects, confirmed during the viewer-lockdown audit) saw a tab bar
   implying access to all four, even though each page's own content was separately
   gated.

**Fix.** `billing/page.tsx` now branches on `billing:read` (admin/owner only,
`app/auth/permissions.py`): with it, the real plan + usage render as before; without it,
an honest `NotWiredNotice` placeholder explains that per-teammate credit allocation
(`Phase 5` of the roadmap) isn't built yet and that everyone currently draws from the
same organisation-wide daily budget - not a fabricated number, per CLAUDE.md §4 #9.
`settings/layout.tsx`'s tab bar now filters each tab by that tab's own read permission,
falling back to showing all 4 while the session is still resolving (avoids a
narrow-then-widen flash) - Billing itself always shows, since the placeholder above is
what actually renders there for anyone without `billing:read`.

**Also shipped in the same pass:** `GET /api/v1/runs/team-summary` (added in `Iteration
21`'s per-creator visibility silo work) had zero frontend consumers until now. New
`TeamVolumeBreakdown` on the dashboard (`app/(app)/app/page.tsx`), gated on
`runs:read_team`, calls a newly-added `api.teamSummary()` client method
(`lib/api.ts`) and renders a ranked "by teammate" list under the Volume chart. Built as a
ranked list rather than the roadmap's originally-imagined stacked chart series, because
the endpoint returns lifetime totals per member, not a daily breakdown - there is no
per-day series to stack.

**Depends on / Blocks:** closes the two remaining Phase 0 gaps and the one incomplete
piece of Phase 1 from the role-based UI roadmap. Phases 2-6 (persisted escalations,
notifications, peer sharing, per-teammate credits, edit notifications) remain
not-started as of this entry - since fixed, see `it-28`/`it-29`/`it-30` below.

---

## Iteration 23 - 2026-08-09 · runs-feature audit follow-through: idempotency, cancel, crash recovery

Implementing the P0/P1 findings from a systematic audit of the Runs feature (backend
orchestration, safety gate, and frontend run pages), requested and implemented in the
same session. Closes #8 and #54 above; four new findings from the same audit follow.

**Merge note (arbaaz/role-handling → jatin/config-resend):** this iteration's #74 fixed
the same idempotency/`_calls_made` gap as #54 independently of it-16/it-17's module 3/4
work above, with the same key formula. See `campaign_runner.py`'s own merge commentary for
which implementation the merged code actually keeps.

### #74 - `POST /runs` had no idempotency key - a retried request could start a second real run

**S2 · FIXED · backend + web · `app/api/v1/routes/runs.py`, `app/database/repositories/runs.py`, `apps/web/lib/api.ts`, `apps/web/app/(app)/app/runs/new/page.tsx`**

`POST /api/v1/runs` is a mutating endpoint that dials real phones, with no
`Idempotency-Key` support - a network-level retry, a double-submit, or a programmatic
`cfk_…` caller retrying after a timeout had no way to avoid starting a second, independent
batch of real calls against the same contacts. Direct violation of `CLAUDE.md`
non-negotiable #6 ("every mutating endpoint... safe to run twice").

**Impact.** Low-probability from the web client (the Start button disables itself while
the request is in flight, and the fetch client makes no automatic retries) but real for
any programmatic caller, and the consequence of it firing is a second real phone call to
a real person, not just a duplicate row.

**Fix.** `public.runs` gained a nullable `idempotency_key` column and a partial unique
index on `(org_id, idempotency_key) where idempotency_key is not null` (migration
`f2a8c6e1d9b4`). `start_run()` checks for an existing run under the caller's
`Idempotency-Key` header before doing anything else - a replay returns the original run
untouched, with no new dial, no rate-limit charge, no second row. A race between two
identically-keyed concurrent requests is resolved by `create_run()`'s `on conflict ...
do nothing returning id`: the loser detects `created = False`, releases the rate-limit
slots it had reserved, and returns the winner's run instead. The web client now generates
a UUID once per submit attempt and keeps it across a failed retry, clearing it only on
success.

**Verified.** `tests/test_run_stats.py` n/a here; verified directly against the real
database with a standalone script exercising `create_run`/`get_run_by_idempotency_key`
under a repeated key, a fresh key, and a `None` key - see #75-#77 for the same
verification pass. `npm run type-check`/lint/build clean.

### #75 - A run in progress when the API restarted stayed "running" forever

**S2 · FIXED · backend · `app/database/repositories/runs.py`, `app/main.py`**

A run's dial loop lives entirely inside one `BackgroundTasks` coroutine in one process
(`SYSTEM.md` F18) - there is no queue or worker that could keep it going across a
restart, and CI deploys on every push to `main`. A run interrupted by a routine deploy
had no path to ever leave `running`.

**Impact.** A run stuck on `running` indefinitely looks identical, from the dashboard's
point of view, to one that's still genuinely in progress - nothing ever tells the
operator it died.

**Fix.** `reap_orphaned_runs()` runs once, cross-org, in `main.py`'s startup `lifespan`
hook via `privileged.acquire()` (the whole point of this call needing to run before any
request lands and across every organisation, not one). The reasoning is structural, not
a timeout guess: any row still `running`/`canceling` the moment this process boots was
being driven by the *previous* process, which is now gone - it is orphaned by definition.
Failed with an honest message: "The service restarted before this run finished."

**Verified.** Ran the real `lifespan()` context manager directly against a stale
`running` row inserted by hand (not via a real dial - no calling budget spent): confirmed
the log line `"reaped 1 run(s) left running by a previous process"` and the row landing on
`status='failed'` with the expected error text.

### #76 - There was no way to actually stop a run once started

**S2 · FIXED · backend + web · `app/api/v1/routes/runs.py`, `app/services/campaign_runner.py`, `apps/web/app/(app)/app/runs/[id]/page.tsx`**

"Pause run" (the only control on the live run page) only stopped the browser from
polling for updates - it never stopped a call, and there was no cancel endpoint anywhere
in the backend (this gap was already known and honestly labelled after `#39`, but never
closed).

**Impact.** Starting a run against the wrong contact list had no way to be stopped once
under way.

**Fix.** New `POST /api/v1/runs/{run_id}/cancel` (reuses `Permission.RUNS_START` -
whoever may spend the organisation's money starting a run may stop one early). Sets
`runs.status = 'canceling'` and `cancel_requested_at` immediately, visible right away.
`CampaignRunner.run()` takes an optional `should_cancel` hook, checked **between**
contacts only - there is no way to interrupt a call already in conversation (the voice
engine has no cancel operation, confirmed in `VOICE_AGENT_PLATFORM.md`), so the honest
guarantee is "no further contacts are dialled," not "stops instantly." The run then lands
on a new terminal `canceled` status, distinct from `completed`/`failed`. Frontend: a real
"Cancel run" button with a confirm dialog next to "Pause run," `canceling`/`canceled`
added to `RunStatus` and `lampForRunStatus` (rendered in the neutral `off` lamp colour,
not a new one - the five lamp colours stay reserved for call-state meaning), and the
run-detail/dashboard poll loops extended to keep polling through `canceling` instead of
stopping the instant status leaves `running`.

**Verified.** `tests/test_orchestrator.py`: `run()` stops after the contact in progress
when `should_cancel` flips, contacts already dialled keep their outcomes, contacts never
reached get no outcome row at all. Verified `request_cancel`/`is_cancel_requested`
directly against the real database: idempotent on a second call, rejects a different
org, rejects a run that's already finished. `npm run type-check`/lint/build clean.

### #77 - A suppressed contact still reserved rate-limit and daily-budget it would never use

**S3 · FIXED · backend · `app/api/v1/routes/runs.py`**

`start_run()` called `limiter.check(calls=len(contacts), ...)` before resolving which
contacts were suppressed - `check_dial_allowed()` skips a suppressed contact regardless,
so a run half full of suppressed numbers still burned that many slots from the daily
budget and rate window for calls that were never going to be placed.

**Impact.** Wasted a safety-critical, finite resource (the daily call budget) on
contacts guaranteed not to be dialled - in the worst case, an organisation's own
suppression list could exhaust its budget for the day without a single real call going
out.

**Fix.** Suppression is now resolved before the rate-limit check, and `limiter.check()`
is called with `calls = len(contacts) - len(suppressed)` instead of the raw contact
count.

**Verified.** Existing suppression-gating coverage in `tests/test_orchestrator.py`
(`test_suppressed_number_is_blocked`) already proves a suppressed contact never reaches
the gateway; this fix is the route-layer arithmetic feeding the rate limiter the right
count, confirmed by reading and by `test_ratelimit.py`'s existing coverage of the `calls`
parameter's behaviour.

---

## Iteration 24 - 2026-08-09 · run composer rebuild: contacts UX, phone validation, per-run guards

Requested directly: replace the contact grid's Paste/Use-sample buttons with a downloadable
sample CSV, add real input-level phone validation, audit the "Remove all invalid" button's
underlying logic, redesign the whole run-composer page, and add per-run safety overrides on top
of the organisation's own settings.

### #78 - A hand-typed phone number could show valid in the grid while failing E.164 at submission

**S2 · FIXED · web · `apps/web/components/app/contact-grid.tsx`, `apps/web/lib/contacts.ts`**

Found while auditing "Remove all invalid" per a user report - the button's own filter logic
(`rows.filter(r => r.valid)`) was correct; the bug was upstream, in what `valid` actually meant.
`ContactGrid`'s `updateCell` computed a normalised phone (`normalisePhone(merged.phone)`) purely
to check validity, then returned `{...merged, ...validateRow(...)}` - `validateRow` returns only
`{valid, error, errorField}`, never `phone`, so the row's stored `phone` stayed whatever the
person had typed. A bare 10-digit number (`9876543210`) normalises to a valid E.164 number
(`+919876543210`) for the check, so the row showed green/ready - but `toContactInputs` sent
`r.phone`, the un-normalised original, to the API. The backend's `Contact` model validates E.164
strictly with no normalisation, and `POST /api/v1/runs` fails the *entire* request - not just
that one row - the moment any contact fails Pydantic validation.

**Impact.** A single hand-typed row using a bare national number (an extremely ordinary way to
type a phone number) could make "Start run" fail outright with an opaque 400, for a request the
composer had just shown as fully ready - and would have blocked every other, genuinely valid
contact in the same batch along with it. CSV import was unaffected: `parseSheet` already stored
the normalised value correctly, so this only reached hand-edited or hand-added rows.

**Fix.** Two layers: `ContactGrid`'s phone cell now normalises on blur (`normaliseCellOnBlur`),
matching `ui/input.tsx`'s existing phone-variant "normalise on blur, not on every keystroke"
convention elsewhere in the app - so the grid's own displayed/stored value is honest, not just
the validity flag. `toContactInputs` (`lib/contacts.ts`) also normalises again at the point it
builds the API payload, regardless of what the grid's state holds - a defensive boundary fix, so
this is correct even if the UI-side fix is ever bypassed.

**Verified.** Traced by reading, since this repo has no frontend test suite (`ISSUES.md` #10) -
confirmed `updateCell`'s original return shape never included `phone`, confirmed `parseSheet`'s
did, confirmed `toContactInputs` used `r.phone` directly pre-fix. `npm run type-check`/lint/build
all clean after the fix.

### Contact grid: Paste and Use-sample replaced with a downloadable sample CSV

Not a bug - a requested UX change. `navigator.clipboard.readText()` ("Paste") and the
instant-populate three-row demo list ("Use sample") are both removed; `SAMPLE_CSV`
(`lib/contacts.ts`) is trimmed to one header row plus one example row and downloaded as a real
`.csv` file via a `Blob`/`<a download>` - no new dependency. A single grid cell still accepts a
normal OS paste (it's a plain `<input>`); what's gone is the bulk clipboard-read shortcut.

### Phone input: keystroke filtering plus a stricter national-length rule, scoped to the run composer

Not a bug - a requested tightening. `sanitizePhoneInput` restricts typed input to a leading `+`
and digits only; `hasValidNationalLength` additionally requires a 1-3 digit country code plus an
exactly-10-digit national number. Both new, both in `lib/format/phone.ts`, and deliberately
**not** folded into `isE164` - that stays the general check used for allowlist/suppression
entries elsewhere, where a 10-digit national number isn't a safe assumption for every country.
The stricter rule only applies inside `lib/contacts.ts`'s `validateRow`, matching this product's
two default regions (+91, +1) without a full number-metadata library.

### Run composer redesign: single-section layout, per-run guard overrides

Not a bug - a requested redesign plus a new capability. `runs/new/page.tsx`'s three numbered
`Step` panels (01 Contacts, 02 Campaign, 03 Run) are replaced with two plainly-titled panels
(Campaign, Contacts) in a main column and a `lg:sticky` right-hand rail holding the guard bar,
this run's own overrides, the contact-count readout, and Start/Cancel - dropping the numbering
that made a single continuous page read as a wizard.

New: a per-run override of `max_calls_per_run` and `allowlist`, **tighten-only** - a run may ask
for less than the organisation's Settings → Safety configuration, never more.
`apply_run_override()` (`app/domain/safety.py`) is a pure function: a requested ceiling above the
organisation's own is silently capped, not honoured; a requested allowlist intersects with a
non-empty organisation allowlist (can only narrow it) and stands alone only when the organisation
has none set. `calls_per_window`/`window_minutes`/`daily_budget` are deliberately not
per-run-overridable - those are whole-organisation resources shared across every run today, not
one run's own limit, unlike `max_calls_per_run` (already named as exactly that).

This is a considered reading of an ambiguous request ("apply settings run-wise"), made without
asking, against `CLAUDE.md`'s fail-closed non-negotiable: `Permission.RUNS_START` (operator and
above) must never be able to use a per-run control to reach a guard value that
`Permission.SAFETY_WRITE` (admin/owner) hasn't already permitted - the entire point of an
org-configured ceiling is that starting the next run can't quietly raise it. `POST /api/v1/runs`
accepts optional `max_calls_per_run`/`allowlist` fields; the frontend clamps to the organisation's
own ceiling client-side before ever submitting, so the backend's cap is a correctness backstop
for a race (the organisation's settings changing between page load and submit), not the normal
path.

**Verified.** New tests in `tests/test_safety.py`: a lower per-run ceiling wins, a higher one is
capped at the organisation's own, omitting the override keeps the organisation's value, a
non-empty organisation allowlist only ever narrows via intersection, an empty one lets the
run-level list stand alone, and `calls_per_window`/`window_minutes`/`daily_budget` pass through
untouched regardless of what's overridden. 189 backend tests pass (7 new), `ruff` clean, frontend
`type-check`/lint/build all clean.

---

## Iteration 25 - 2026-08-09 · per-run guard audit trail

Raised directly, following on from it-23's per-run overrides: nothing recorded what guards
actually governed a given run, so once an organisation's Settings → Safety changed, no past
run's real ceiling/allowlist/rate/budget could be reconstructed - not even for a run that
never used a per-run override at all.

### #79 - A run's actual guards were never recorded, so past runs became unauditable once settings changed

**S2 · FIXED · backend + web · `app/database/repositories/runs.py`, `app/api/v1/routes/runs.py`, `apps/web/components/app/safety-bar.tsx`, `apps/web/app/(app)/app/runs/[id]/page.tsx`**

`resolve_safety_settings()` merges an organisation's `org_safety_settings` row onto the
deployment defaults fresh on every read - there was never a point where the *result* of
that merge, for a specific run, was written down anywhere. For a product whose whole
premise is that the guards are real and enforced, that is a genuine audit gap: nothing
could answer "what ceiling actually governed this run" after the fact, for any run, not
just ones with a per-run override (it-23, #74-#77).

**Impact.** If a run's behaviour was ever questioned - "why did this only dial 3 people,"
"prove it respected the allowlist you'd set" - there was no way to answer from the data
itself, only from memory or a support ticket, and that answer became permanently
unavailable the moment the organisation's Settings → Safety changed again.

**Fix.** Five nullable columns on `public.runs` - `max_calls_per_run`, `allowlist`,
`calls_per_window`, `window_minutes`, `daily_budget` (migration `a3f7c9e2b6d8`, same names
and types as `org_safety_settings`'s own columns). `create_run()` now takes and stores the
exact `EffectiveSafety` object `start_run()` already resolved for that run's own dial gate
and rate-limit check - not a fresh read of current settings, so what's recorded can never
drift from what was actually enforced. Nullable, not backfilled: a run created before this
migration has no snapshot and reports one honestly (`null`), rather than a fabricated
default computed from today's settings. `GET /api/v1/runs/{id}` returns it as
`safety_snapshot`; the run-detail page renders it through the existing `SafetyBar`
component via a new `guardsFromSnapshot()` builder (`components/app/safety-bar.tsx`) -
same chip rendering a live guard bar uses, sourced from the run's own permanent record
instead of the organisation's current settings.

**Verified.** Direct database round-trip (no real call placed): a snapshot with values
round-trips exactly; an empty ("unrestricted") allowlist round-trips as `[]`, distinct from
`null` ("not captured"); a row inserted the old way (no snapshot columns) reads back with
every snapshot field `null`, not a fabricated default. 189 backend tests pass, `ruff`
clean, frontend `type-check`/lint/build all clean.

**Depends on / Blocks:** builds on #74-#77 (it-23, the per-run override this now makes
permanently auditable).

---

## Iteration 26 - 2026-08-09 · dashboard/runs/contacts/escalations UI pass, call-duration bug

Nine UI/UX changes requested directly against the dashboard, run detail page, contacts
page, and the "Needs a person" (escalations) worklist. Two of the nine surfaced real bugs
in the course of implementation rather than being pure preference; both are numbered below.
The rest were requested UX changes, not bugs, and are logged as a narrative batch afterward
per the existing pattern (`## Visual and architecture work landed this round`, it-11).

### #80 - Call duration was never visible anywhere, because the field it was read from doesn't exist in CALL-E's response

**S2 · FIXED · backend · `app/services/campaign_runner.py`, `apps/api/tests/test_orchestrator.py`**

Reported as "duration of call data is not visible." The resolved outcome read
`final.get("duration_seconds")` - a key that has never existed anywhere in CALL-E's real
API response. Confirmed by reading the installed SDK's `CallTaskAttempt` model directly:
its fields are `id, phone, status, started_at, completed_at, summary, transcript_turns,
provider_call_id, failure_code, failure_message` - no duration field at all, only the two
timestamps. Every call's `duration_seconds` has been `None` since the column existed, on
every page that shows it (dashboard, run detail, contacts). Same bug class as #52
(transcript read from a top-level key that doesn't exist), just never cross-checked for
this sibling field.

**Impact.** Nobody could tell from any table in the product how long a call actually
lasted - not a display bug, a data bug: the value was never computed, so no amount of
frontend formatting would have shown it.

**Fix.** New `_extract_duration()` computes `(completed_at - started_at)` in seconds from
the same "final" attempt `_extract_transcript()` already selects (the most representative
attempt among possibly-multiple redial attempts) - reusing that selection keeps duration
and transcript consistent about which attempt they describe. Returns `None`, not `0`, when
either timestamp is missing, since a rendered "0s" reads as an instant call rather than an
unmeasured one. Surfaced with a new "Call time" column (absolute timestamp, alongside the
now-working "Duration" column) on both the run detail page and the contacts page, per the
same request.

**Verified.** 3 new tests (5 cases) in `test_orchestrator.py`: computed from real
timestamps, uses the same attempt as the transcript, returns `None` when timestamps are
unavailable. 49/49 orchestrator tests pass; full backend suite 193 passed, `ruff` clean.
Three unrelated failures in `test_rls_isolation.py` (`create_or_refresh_invitation`
missing on the shared dev database) are pre-existing migration drift on that database, not
touched by anything in this iteration.

**Depends on / Blocks:** same bug class as #52 (it-13).

---

### #81 - A long filter value overflowed the Select trigger and broke the escalations filter-row layout

**S2 · FIXED · web · `components/ui/select.tsx`, `app/(app)/app/escalations/page.tsx`**

Reported as "filter UI is breaking when I select the value from filter dropdown." Root
cause: `RadixSelect.Value` had no `className` at all, so a long selected label - the
escalations "Reason" filter's options are full sentences from `disposition_reason`, not
short tags - overflowed the trigger's fixed width instead of clipping, visibly breaking
the row instead of just showing a wide box. A second, compounding cause in the same row:
the "Clear filters" button was only mounted once a filter was active, so picking a filter
value also reflowed every other control next to it via `flex-wrap` - which reads as the
row "breaking" a second time, immediately after the first.

**Impact.** The one interaction the page exists for - filtering the escalation queue - was
the one thing visibly broken by using it.

**Fix, attempt 1 (incomplete).** `min-w-0 flex-1 truncate` on `RadixSelect.Value` -
`min-w-0` is required for `truncate` to take effect at all on a flex child. This alone
turned out not to be enough: the user reproduced the identical wrapping/overflow a second
time after this landed. "Clear filters" was also switched to always-mounted with
`invisible`/`aria-hidden`/`tabIndex={-1}` when there's nothing to clear, reserving its
layout space either way instead of popping in and shifting its neighbours - this part of
the fix held.

**Fix, attempt 2 (the actual root cause).** Reading the installed `@radix-ui/react-select`
source directly (`node_modules/@radix-ui/react-select/dist/index.mjs`) explains why attempt
1 didn't hold: left without explicit children, `Select.Value` doesn't just display a copy
of the selected label - it mirrors the selected `Select.Item`'s own `ItemText` span into
itself via `ReactDOM.createPortal`, and that `ItemText` span (rendered a second time,
unstyled, because it's also what the dropdown *row* itself renders) has no `nowrap` of its
own. `min-w-0 truncate` on `Select.Value` was landing on the right outer node the whole
time; it just wasn't the node holding the actual text. Fix: pass the label directly as
`Select.Value`'s own children (`{options.find((o) => o.value === value)?.label}`), which
bypasses the mirroring entirely so `truncate` lands on a plain text node instead of a
second unstyled span. `overflow-hidden` was also added to the trigger itself as a backstop,
so any future case that still slips past `truncate` clips instead of visibly growing the
box into the content below it.

**Verified.** `type-check`/`lint`/`build` all clean (it-27).

**Depends on / Blocks:** none. Superseded its own first fix - see attempt 2 above.

---

## Also landed this round (not bugs)

The remaining seven requested changes, none of which were bugs:

- **Dashboard "Needs a person" preview capped at 3.** Was showing 5; now shows the 3
  oldest-first, with the existing "See all N" link to the full `/app/escalations` worklist
  doing the rest - no new component needed.
- **Run ID no longer shown anywhere on the run detail page.** It's still the URL segment
  (functional, unavoidable) and still round-trips through the API; only the visible
  `font-mono` display in the page header was removed.
- **"Guards for this run" panel removed from the run detail page**, per explicit request.
  This reverses only the *display* added in it-25 (#79) - the underlying
  `safety_snapshot` columns are untouched, still written by `create_run()`, and still
  returned by `GET /api/v1/runs/{id}`; the data just isn't rendered on this page anymore.
  Nothing about dial-time enforcement changed: the allowlist, per-run ceiling, rate limit,
  daily budget, E.164 validation, and suppression-list checks in `check_dial_allowed()`
  are exactly as they were. The "Live · Real calls" progress panel was restructured
  alongside this removal - a large settled-count stat leads, with the lamp strip (still
  the only progress indicator, per this page's own standing design note) in its own
  labelled sub-section below, rather than competing with the header for space.
- **Contacts page converted from a `<Panel>` list to a real table**, via the existing
  (previously unused anywhere) `DataTable` component - same sortable/paginated/CSV-export
  component now backing `/app/runs`. Picked up a real, if minor, correctness fix in
  passing: each contact's `calls` array is now sorted newest-first before use, since the
  status badge, duration, and new call-time columns all read `calls[0]` as "the latest
  call" and it was previously just whatever arrival order the outcomes list happened to be
  in.
- **Infinite scroll on the escalations worklist.** All escalations are already loaded into
  memory (`useAppStore`'s hydrated runs - there's no server-side pagination API for this
  list), so this bounds rendered DOM node count via a native `IntersectionObserver`
  sentinel rather than reducing network calls. Fixed a related `react-hooks/set-state-in-
  effect` lint error along the way: resetting the visible-count window on a filter change
  is now done during render (React's documented pattern for adjusting state from a
  prop-like change) instead of inside a `useEffect`, which would have committed one stale
  frame before a second render corrected it - CLAUDE.md already calls this pattern out as
  a hard lint error, not a style preference.
- **Transcript viewer changed from a right-side sliding sheet to a centered dialog**, on
  both the run detail page and the escalations page. The shared `Dialog` component gained
  an `xl` size and a `contentClassName` prop (default unchanged) so `TranscriptView`, which
  manages its own internal padding, isn't padded twice.
- **Escalation detail card redesigned for readability**: the reasoning chain now sits in
  its own labelled "Why it's here" block instead of floating loose under the header; the
  transcript excerpt and summary each got an explicit label ("Last thing they said,"
  "Summary") instead of relying on formatting alone to distinguish them; the campaign name
  now shows as a tag next to the contact's name; the age/duration figures in the header
  gained explicit units ("Waiting Xh," "Xm call") instead of two bare numbers.

**Verification for the whole batch:** frontend `type-check`/`lint`/`build` all clean (the
`set-state-in-effect` error above and one unescaped-apostrophe lint error were both
introduced and fixed within this same round, not pre-existing). Backend: 193 passed, 3
pre-existing/unrelated failures (see #80), `ruff` clean.

---

## Iteration 27 - 2026-08-09 · duration still missing after #80, filter dropdown still breaking after #81

User-reported follow-up, same day as it-26: duration was still showing "-" in the contacts
table after #80 shipped, and the escalations filter dropdown was still visibly breaking
after #81 shipped. Both turned out to be real, distinct problems the first fix didn't
reach - not the same bug recurring, and not user error. Investigated by querying the
production database directly (read-only) for the actual stored rows, then re-fetching each
call's real, current state straight from CALL-E using its own `provider_call_id` (a status
re-read, not a new call) to compare against what got persisted at the time.

### #82 - A call's own top-level `status` can go terminal before its nested attempt's `completed_at` does, permanently freezing `duration_seconds` at `None`

**S2 · FIXED · backend · `app/services/campaign_runner.py`, `apps/api/tests/test_orchestrator.py`**

#80 fixed the extraction *formula* - and it is correct: re-running `_extract_duration()`
by hand against a real, freshly-re-fetched call (`call_rNS2f5FQn-Py0ElQx0UxeQ`, processed
*after* #80's fix was already live) returned `0.0`, the right answer for that call's
same-second decline. The database, though, still had `duration_seconds = None` for that
exact row. The only place a snapshot of the same call could disagree with itself is the
moment `_poll_until_done()` first accepted a terminal response: it returns the instant the
top-level `status` reaches `completed`/`failed`/`canceled`, with no check that the same
response's `recipients[0].attempts[].completed_at` has actually been written yet. CALL-E
does not write the two fields atomically, so the exact response that ends the poll can have
a terminal `status` and a still-null nested `completed_at` at the same time - the same
class of eventual-consistency gap already fixed for `status` itself in #53, just on a
different field.

**Impact.** Any call whose terminal poll happened to land in that gap has its
`duration_seconds` permanently frozen at `None` - nothing re-polls after the loop exits, so
there is no second chance to pick up the real value once CALL-E finishes writing it.

**Fix.** New `_await_settled_duration()`: once `_poll_until_done` sees a terminal `status`,
it checks whether `_extract_duration()` can already compute a value from that response: if
not, it waits 1.5s and re-fetches, up to 3 times, before giving up and returning whatever
it has. Bounded, not unconditional - a call that genuinely never gets a duration (cancelled
before dialing) costs a few extra seconds once, not a hang.

**Verified.** 2 new tests: one fake gateway whose first terminal response has a null
`completed_at` and whose second has the real one, confirming `run_one` waits for the
settled value; one whose duration never settles at all, confirming the call still resolves
(with `duration_seconds` left `None`) rather than hanging. 51/51 orchestrator tests pass;
full suite 195 passed, `ruff` clean. Same 3 pre-existing `test_rls_isolation.py` failures
as it-26 (`create_or_refresh_invitation` missing on the shared dev database) - unrelated,
not touched here.

**Depends on / Blocks:** follow-up to #80 (it-26); same underlying eventual-consistency
class as #53 (it-13).

---

## Also landed this round (not bugs)

- **Escalation card's "Why it's here" section un-boxed.** The `bg-surface-sunken` panel
  background added around the reasoning chain in it-26 read as heavier chrome than the
  "Last thing they said"/"Summary" sections next to it, rather than a matching third
  section - removed so all three share the same plain label-then-content rhythm.
- **Runs page search bar collapsed to match `/app/campaigns`.** `/app/runs` rendered its
  search input fully expanded at all times (`w-full sm:w-64`); `/app/campaigns` instead
  shows a compact icon-only button that expands into the same input on click (or whenever
  there's already a query). `/app/runs` now follows the same pattern for consistency across
  the two list pages.

**Verification for the whole batch:** frontend `type-check`/`lint`/`build` all clean.

---

## Iteration 28 - 2026-08-10 · role-based UI roadmap, Phase 2 (real escalations) + Phase 5 slice (per-teammate credits)

*(this iteration was originally numbered "Iteration 23" on `arbaaz/role-handling`;
renamed on merge to avoid colliding with dev's own Iteration 23 above - the finding
inside is renumbered `#84`, see its own note)*

### #84 - `runs_select` and `escalations_select` recursed infinitely once each queried the other

*(renumbered from `#75` on merge - collided with the run-restart finding above)*

**S1 · FIXED · backend · migration `3ea00413701c`**

Building Phase 2's "an escalation's assignee can see it even if they didn't start the
underlying run" requirement, the natural first attempt added a branch to `runs_select`/
`call_outcomes_select` that queried `public.escalations` directly. `escalations_select`
already queried `public.runs` right back (its own "or the run's starter" branch, added
in the same migration). Evaluating either policy now required evaluating the other,
which required evaluating the first again - `asyncpg.exceptions.InvalidObjectDefinitionError:
infinite recursion detected in policy for relation "runs"` on every second read.

**Impact.** Would have broken every run/call-outcome read in the product the moment the
migration reached a real database - caught immediately by running the full test suite
before moving on to the frontend, not by inspecting the SQL and reasoning it through.
14 tests failed on the first run, cleanly reproducing the bug.

**Fix.** The exact lesson `initial_schema`'s own migration already documented for
`has_org_role`/`is_org_member` ("a policy on memberships that queried memberships
directly would recurse infinitely... running inside a [`SECURITY DEFINER`] function
bypasses RLS and breaks the cycle") applies identically across two tables, not just one.
Two new `SECURITY DEFINER` helper functions (`is_assigned_to_run_escalation`,
`is_assigned_to_call_outcome_escalation`) replace the plain correlated subqueries in
`runs_select`/`call_outcomes_select` - evaluating them never re-triggers the calling
policy, since they bypass RLS internally the same way the existing helpers do.

**Depends on:** none - self-contained within the same iteration's own new tables.

---

### Real, persisted, assignable escalations + a per-teammate credits/performance view, shipped

Not itself a bug fix - the role-based UI roadmap's Phase 2 (escalations) and a working
slice of Phase 5 (per-teammate credits), landed together because the dashboard's "needs
a person status per teammate" ask needed Phase 2's real data to be accurate. Full design
and phase-by-phase status lives in the new, checked-in
[`TEAM_COLLABORATION_ROADMAP.md`](TEAM_COLLABORATION_ROADMAP.md) - not duplicated here.
Summary:

- **Escalations are real rows now** (`public.escalations`), not a computed label -
  closes `#7` above. Assignable (admin/owner, new `Permission.ESCALATIONS_ASSIGN`) and
  resolvable for real, with RLS - not just the app's permission check - enforcing who
  can touch which row.
- **Live sync.** `escalations` is the first table in this product wired to Supabase
  Realtime (`SYSTEM.md` F27 was previously "2.5s polling only, no Realtime anywhere") -
  an assignment or resolution reaches every other signed-in teammate immediately.
- **Per-teammate credits** (`public.member_credit_allocations`) - a subdivision of the
  org's existing daily budget, not a second enforced limit at first (enforcement landed
  later - see `it-30`/the credit-enforcement entry below). Admin/owner set a daily
  number per teammate from the Team pane; a teammate's own "My credits" view (Settings →
  Billing, previously an honest placeholder) now shows it for real.
- **New dashboard panel**, "Team performance": one row per teammate - calls made, calls
  closed, run status breakdown, open "needs a person" count, credits used/allocated -
  visible to admin/owner/viewer (`runs:read_team`), placed as its own full-width section
  below the existing grid rather than crowding the Volume card.

**Tests.** 255 backend tests passing (13 new: 8 permission-matrix, 5 cross-member RLS -
unassigned operator can't see a teammate's escalation; an assignee can regardless of who
started the run; an operator can't assign/resolve/allocate-credits for a teammate
directly, RLS-enforced not just permission-checked). `npm run lint && type-check &&
build` clean.

## Iteration 29 - 2026-08-10 · role-based UI roadmap, Phase 4 (peer-to-peer campaign/escalation sharing)

*(originally "Iteration 24" on `arbaaz/role-handling`; renamed on merge - see `it-28`'s
own note. Both findings inside are renumbered, `#85` and `#86`)*

### #85 - Cloning a teammate's campaign on share approval failed under RLS for every non-admin/owner approver

*(renumbered from `#76` on merge - collided with the "stop a run" finding above)*

**S1 · FIXED · backend · migration `b938fa82e54d`, `app/database/repositories/campaigns.py`, `app/api/v1/routes/sharing.py`**

Found by manually walking the approve-a-share-request flow end to end in a
real browser (two real signed-up test accounts, a real invite, a real
request) - not by static review, and not caught by the automated test suite
either, which is its own finding (see the "shipped" note below). Every
automated RLS test for sharing exercised `sharing_repo.decide()` or
read-only checks; none exercised the actual campaign-clone `INSERT`.

Approving a campaign share request as an **operator** (the ordinary case -
admin/owner rarely need to request anything, since they already see
everything) failed with:

```
asyncpg.exceptions.InsufficientPrivilegeError: new row violates row-level
security policy for table "campaigns"
```

**Root cause.** `campaigns_insert`'s `WITH CHECK` is role-only
(`has_org_role(org_id, [owner,admin,operator])`) and correctly allows an
operator to insert the cloned row. But the insert used `RETURNING`, and
Postgres also evaluates the table's `SELECT` policy against any row
returned via `RETURNING` - raising the identical "violates row-level
security policy" error if that check fails, indistinguishable from a
`WITH CHECK` failure without reading the actual policy definitions.
`campaigns_select` for an operator is `created_by = self`, with no broader
role branch (Phase 1's own design - `ISSUES.md` iteration 21) - and the
clone's `created_by` is the *requester*, not the operator running the
insert. An operator can insert a row on a teammate's behalf but can never
legally see it back, and `RETURNING` demands both.

**Impact.** The single most common path through the entire sharing feature
- operator approves operator - was completely broken. Admin/owner approving
would have worked by coincidence (their `campaigns_select` branch is
role-based, not `created_by`-based), which is exactly why this could have
shipped without anyone noticing in an admin-only smoke test.

**Fix.** Same shape as `create_organisation()`/`remove_member_and_
reassign_data()` (migrations `a7c2e5f9b184`, `202608092600`): a narrowly-
scoped `SECURITY DEFINER` function, `clone_campaign_for_share()`, performs
the actual privileged insert, bypassing RLS for this one operation the way
every other "write a row on someone else's behalf" case in this codebase
already does. The unique-slug dedup logic stays in Python
(`sharing.py::_clone_campaign`) - only the write itself moved.

**Verified.** Reproduced the failure directly (a Python script calling the
real route function with a real `CurrentUser`, not just curl - curl alone
surfaced a *different*, correct 404 first, from missing the `X-Org-Id`
header the real frontend always sends), confirmed the fix with the same
script, then confirmed again through the actual browser UI: the clone now
lands, with the correct new owner, as an independent campaign. New
regression test `test_operator_can_clone_a_teammates_campaign_via_share_
approval` (`test_rls_isolation.py`) pins the previously-broken case
directly - not just the security boundary around it.

**Depends on:** Phase 1 (`created_by = self` for operators is exactly the
policy this collided with, and is correct - the fix is in how the clone is
written, not in loosening that policy).

### #86 - The share-request approval flow performed the grant before the atomic decision - a double-clone race

*(renumbered from `#77` on merge - collided with the suppression/rate-limit finding above)*

**S2 · FIXED · backend · `app/api/v1/routes/sharing.py`**

Caught by independent code review (`superpowers:requesting-code-review`),
not manual testing. `_decide()`'s original order: check the request is
still `pending` (a plain read), perform the grant (clone the campaign /
reassign the escalation), *then* atomically transition the row to
`approved`/`rejected` (`UPDATE ... WHERE status = 'pending'`). Two
concurrent `POST /approve` calls (two browser tabs, a client retry after a
slow response) could both pass the initial read-only pending check and both
perform the grant - producing two independent cloned campaigns - before the
atomic transition correctly let only one of the two calls "win" and 409'd
the other. The loser's transaction still committed its already-completed
clone; only the *decision* lost the race, not the side effect that should
have been gated by it.

**Impact.** Violates CLAUDE.md §4 non-negotiable #6 ("every mutating
endpoint... is safe to run twice"). Low likelihood in practice (both calls
need to be genuinely concurrent, not just close in time), but the failure
mode - a silent duplicate campaign with no error surfaced to either caller
- is the kind of bug that's expensive precisely because nothing looks
wrong when it happens.

**Fix.** Reordered: the atomic `decide()` transition (the actual
concurrency-safe linearisation point, backed by `WHERE status = 'pending'`
and Postgres's row-level locking) now runs *before* the grant, and the
grant is skipped entirely if `decide()` didn't return a row. Both live in
the same `database.as_user()` transaction, so if the grant step still fails
afterward (e.g. the campaign was deleted in between), the whole transaction
- including the `decide()` - rolls back, leaving the request genuinely
still pending rather than "approved" with nothing behind it. Also added:
re-resolving the resource's *current* owner at decide-time (not just
trusting the value stamped in at request-creation time) - if ownership
moved in between (a different admin reassigned the escalation elsewhere),
the stale request is auto-closed with a clear reason rather than silently
overriding the more recent change.

**Depends on:** none.

### Peer-to-peer campaign/escalation sharing, shipped

Not itself a bug fix - the role-based UI roadmap's Phase 4, the last of the
three phases planned this round (Phase 2 and a Phase 5 slice shipped in
`Iteration 28`). Full design lives in
[`TEAM_COLLABORATION_ROADMAP.md`](TEAM_COLLABORATION_ROADMAP.md), updated
in place rather than duplicated here. Summary:

- **`public.share_requests`** - a request/decision record: who asked, who
  owns it, pending/approved/rejected, an optional message. RLS: visible to
  the requester, the owner, or admin/owner; only the owner can decide.
- **Directory endpoints** (`GET /api/v1/campaigns/directory`, `GET
  /api/v1/escalations/directory`) - name/contact + owner only, via two new
  `SECURITY DEFINER` functions, so an operator can see *what exists* to
  request without the content their own Phase 1 RLS narrowing correctly
  hides.
- **`resolve_resource_owner()`** - a third `SECURITY DEFINER` function that
  resolves who really owns a campaign or escalation, called server-side
  and never trusted from the client - the whole reason it exists is that
  the requester's own RLS scope can't see the resource (or its owner) to
  begin with.
- **Approving** a campaign request clones it (new id, `created_by` =
  requester, independent from that point on); approving an escalation
  request reassigns it (`assigned_to` = requester) - a hand-off, not a
  fork, since there's only one real underlying event.
- **New "Sharing" tab** (Organisation page) - requests waiting on you
  (Approve/Reject), and requests you've sent, both live via the same
  Supabase Realtime mechanism Phase 2 introduced (`share_requests` is now
  the second table in the publication).
- **New permission**: `Permission.SHARING_REQUEST` (operator, admin, owner
  - not viewer). Deciding needs no separate permission - it's gated by
  actually owning the resource (RLS + an explicit check), available to
  whichever role that happens to be.

**Tests.** 268 backend tests passing (10 new since `Iteration 28`: 2
permission-matrix, 8 cross-member/security RLS - directory functions and
`resolve_resource_owner()` correctly bypass Phase 1's narrowing while still
refusing non-members; a forged `owner_user_id` can update the request row
but still can't read the real resource to grant it; only the named owner
can decide; deciding twice is a no-op; the actual operator-clones-operator
case, `#85`'s regression test). `ruff check`, `npm run lint`, `type-check`,
and `build` all clean.

**Verification method, worth naming explicitly:** this phase is the first
one this round verified through a real browser against the real running
app - two genuine signed-up test accounts (via Resend's own test recipient
address, not fabricated), a real invite accepted, a real campaign created,
a real share request sent and approved - rather than trusting automated
tests alone. It is also the phase where a real, ship-blocking bug (`#85`)
existed *despite* a clean automated test run - the tests proved the
security boundary (an unauthorized party can't grant access) but never
exercised the authorized happy path's own write. Both kinds of coverage
matter; neither substitutes for the other.

## Iteration 30 - 2026-08-10 · role-based UI roadmap, Phase 5 completed (per-teammate credit enforcement)

*(originally "Iteration 25" on `arbaaz/role-handling`; renamed on merge - see `it-28`'s
own note)*

### Per-teammate daily credits, now actually enforced at dial time

Not a bug fix - Phase 5 shipped in `Iteration 28` as a deliberate **minimal
slice**: a real, live-derived `used_today`/`daily_allocation` display, with
an explicit, documented caveat that nothing stopped a teammate from dialing
past their number (`TEAM_COLLABORATION_ROADMAP.md`'s own Phase 5 note). This
closes that gap: **1 credit = 1 connected call**, enforced the same way
every other safety guard is - fail closed, checked per contact, immediately
before the dial.

- **`used_today()`/`used_today_by_member()` redefined.** Previously counted
  every *resolved call attempt* (`disposition <> 'in_flight'`) - a busy
  signal or an invalid number spent a credit exactly like a real
  conversation did. Now counts only calls where the callee actually
  answered (`upper(status) = 'COMPLETED'` - the same predicate as
  `CallOutcome.answered`). This is the same number both displayed (Settings
  → Billing's "My credits", the Team-performance panel) and now enforced -
  deliberately, so what a teammate sees can never disagree with what
  actually blocked them.
- **New `credits_repo.get_enforced_ceiling()`.** `get_allocation()` (used
  for display) returns `0` for both "explicitly set to zero" and "never
  set" - the existing, correct UI convention (Settings → Billing's "hasn't
  been set yet" placeholder). Enforcement cannot conflate those two: a row
  that doesn't exist must never restrict anyone, while a row explicitly
  zeroed by an admin must actually block. The new function returns `None`
  for "no row" and the real int (including `0`) otherwise.
- **`domain/safety.py::check_dial_allowed()`** gained a `credits_remaining:
  int | None` parameter - `None` skips the check entirely (no per-teammate
  ceiling set, only the org-wide daily budget governs); otherwise denies
  once it reaches `0`. Stays pure and I/O-free, consistent with every other
  parameter this function already takes.
- **`CampaignRunner` reserves before dialling, releases if the call doesn't
  connect.** A per-run in-process counter (`_credits_reserved`, guarded by
  the same lock the per-run ceiling's own check-and-reserve already uses)
  is incremented before a contact is dialled and decremented back if that
  particular call resolves without connecting - mirroring the org-wide rate
  limiter's own established "reserve at check time, `release()` on
  no-dial" pattern (`core/rate_limit.py`). Without this, two contacts
  dialled concurrently near the last credit could both pass the check
  before either resolved, overshooting the ceiling; without the *release*
  half, a dial that never connects would burn a credit it never actually
  spent, contradicting "1 credit = 1 connected call."
- **`/api/v1/runs`** resolves the caller's own ceiling and today's
  already-connected count once per run (same place suppression/allowlist
  already resolve once, not once per contact) and threads both into the
  `CampaignRunner`.
- **Found while writing the test fixtures, not a bug in the shipped code:**
  a fake gateway simulating "nobody answered" via `status: "no_answer"`
  made `_poll_until_done` spin for the full 900-second poll timeout before
  giving up - because CALL-E's real, documented task-level `CallStatus`
  enum (`CALLE.md`) is only `queued/in_progress/completed/failed/canceled`;
  there is no `no_answer` at that level, so `engine.py`'s `TERMINAL` set
  correctly doesn't recognise it, and a fixture using it isn't a realistic
  payload. `triage.py`'s own `RETRYABLE_STATUSES = {"busy", "no_answer",
  "voicemail"}` branch is consequently unreachable for CALL-E today - not
  dead code to delete, since Twilio/Plivo (CLAUDE.md's Substitutability
  section, `FEATURES.md` F17, not yet built) do use exactly these terms,
  but worth knowing before assuming a "no answer" call takes that branch
  under the current, sole voice provider. A real unanswered call resolves
  `status: "failed"` and falls through to the `UNREACHABLE` branch instead.
  Fixed in the test fixtures (`test_orchestrator.py`); nothing in
  application code changed.
- **Tests:** 10 new - 3 pure `check_dial_allowed` cases (`test_safety.py`),
  6 `CampaignRunner` cases covering ceiling-blocks-after-connect,
  already-used-today counts toward it, a non-connected call's reservation
  is released and reusable by the next contact, an unanswered call isn't
  credited, and the reserve/release holds under real concurrency
  (`test_orchestrator.py`), 1 cross-member RLS/repo test proving
  `used_today` ignores non-connected calls and `get_enforced_ceiling`
  correctly tells "unset" apart from "explicitly zero"
  (`test_rls_isolation.py`). 278 backend tests passing, `ruff check` clean.

**Depends on:** Phase 5's minimal slice (`Iteration 28`) for the schema and
display; the org-wide daily budget (`domain/safety.py`, unchanged) remains
the hard outer bound regardless of what any individual teammate's
allocation says.

## Iteration 31 - 2026-08-14 · theme-switch review pass

*(originally "Iteration 23" on `dev`; renamed on merge - collided with this
document's own `Iteration 23` above (`it-23`'s runs-feature audit
follow-through), which was already established and cross-referenced from
`Iteration 28`/`29`/`30`. The three findings below are renumbered `#87`-`#89`
for the same reason - `#74`-`#76` were already in use above. Nothing was
deleted or rewritten beyond the numbers themselves and the cross-references
to them.)*

### #87 - Every theme switch flashed white, because Chrome adds the two view-transition frames together

*(renumbered from `#74` on merge - collided with the idempotency-key finding above)*

**S3 · FIXED · web · `apps/web/app/globals.css`**

The light/dark toggle animates with the View Transitions API: Chrome snapshots the old
page and the new one and cross-fades `::view-transition-old(root)` over
`::view-transition-new(root)`. Its UA stylesheet gives both pseudo-elements
`mix-blend-mode: plus-lighter`, which is *additive*, not a normal composite. That is
correct for a fade between two frames of the same page - the two opacities sum to 1 and
plus-lighter keeps the result from dipping - but here the two frames are a light page and
a dark page. Mid-transition their luminances add, and any region where the light frame is
already near white blows past it. The switch read as a white flash in both directions.

**Impact.** Cosmetic, but on the one interaction whose entire purpose is to look smooth,
and unpleasant for anyone switching to dark in a dark room.

**Fix.** Override both pseudo-elements to `mix-blend-mode: normal` while
`data-theme-transition` is set, and give them an explicit z-order so the new frame
composites over the old one rather than being summed with it. `html` also gets
`background: var(--surface)` so the frame behind the snapshots is never the browser's
default white. Verified by screencasting both directions at ~55fps and measuring mean
frame luminance: zero frames now fall outside the two endpoint luminances by more than
6/255, where before the mid-transition frames overshot the lighter endpoint.

### #88 - `#87`'s fix was scoped to an attribute that comes off before the transition ends

*(renumbered from `#75` on merge - collided with the run-restart finding above)*

**S3 · FIXED · web · `apps/web/app/globals.css`, `apps/web/components/ui/theme-toggle.tsx`**

`#87` put `mix-blend-mode: normal` behind `html[data-theme-transition]`, and the toggle
removed that attribute when its clip-path animation finished. The animation finishing and
the browser tearing down the view-transition pseudo-elements are not the same instant. In
the frames between them the override had stopped applying while the snapshots were still on
screen - and by then the reveal circle covers the whole viewport, so plus-lighter was adding
the *entire* old frame to the entire new one. One white frame, at the end. The reviewer's
report was precise: "after the switch there is a flash".

**Impact.** Same as `#87`, and worse-placed: a flash at the end reads as the page breaking
rather than as part of the animation.

**Fix.** Two independent closes, because the first one alone is a race and the second alone
depends on a browser timing guarantee that is not written down anywhere.

1. `mix-blend-mode: normal` is no longer gated. It applies to `::view-transition-old(root)`
   and `::view-transition-new(root)` for both transition kinds. Blend mode is not something
   this app ever wants inconsistent, and the route cross-dissolve is unaffected in practice
   now that `html` paints `--surface` (the midpoint dips toward the page's own colour).
2. The marker is tied to `transition.finished` instead of the clip-path animation's, so the
   rules that *are* still scoped to it - `animation: none` and the z-order - stay in force
   for the whole transition.

**Method note, because the first pass got a false negative.** The check that cleared `#87`
screencast the switch and found no luminance overshoot, and the flash was still there. Two
things were wrong with it: it sampled at 1x speed, where a one-or-two-frame artefact can
fall between captured frames, and it had no positive control, so "no flash detected" and
"cannot detect a flash" were indistinguishable. The current check runs all animations at 1/8
speed and measures the same switch twice - once as shipped and once with `plus-lighter`
forced back on. The control reports 130-180 frames above the brighter endpoint, peaking near
white; as shipped, zero, in both directions. A verification without a positive control is a
guess.

**Depends on:** `#87` (this corrects that fix's scope).

### #89 - Canvases kept painting the previous theme's ink until something remounted them

*(renumbered from `#76` on merge - collided with there being no way to stop a run above)*

**S3 · FIXED · web · `apps/web/lib/hooks/use-canvas-animation.ts`, `apps/web/components/brand/wave-canvas.tsx`, `apps/web/components/marketing/step-flow.tsx`**

Switching theme left the closing CTA card's waveform invisible - dark ink on a dark card -
until a hard reload. Same in the other direction, and the same on the step-flow rail.

A canvas cannot read a CSS variable, so every canvas here resolves its tokens through
`getComputedStyle` and paints the resulting literal. `voice-field.tsx` and `listening.tsx`
resolve inside the draw callback, so they follow the theme for free. `wave-canvas.tsx` and
`step-flow.tsx` resolve once at the top of a `useEffect` whose dependency lists were
`[tone, seed, pitch]` and `[reduced, count]` - neither of which changes when the theme does.
The effect never re-ran, the resolved colour was never re-read, and the animation loop
carried on drawing the old palette. A reload remounted the component, which is why the
reviewer found reloading fixed it.

The same shape has a second, quieter case: `useCanvasAnimation` paints exactly one frame
under `prefers-reduced-motion` and then stops. Even a draw function that resolves its tokens
per frame is stale the moment it stops being called, so *every* consumer of that hook was
exposed, not just the two components above.

**Impact.** A section of the marketing page rendered invisible after an interaction the
product itself offers, with no error and no way to guess that reloading would fix it.

**Fix.** The resolved theme becomes a redraw trigger. `useCanvasAnimation` takes
`useTheme().resolved` into its effect dependencies, which repaints the static frame for
every current and future consumer; `wave-canvas.tsx` and `step-flow.tsx` each take the same
value into theirs. Pixels a canvas has already drawn do not restyle themselves - the theme
has to be a reason to draw.

**Verified** by reading the ink straight out of each canvas's backing store (mean RGB of
pixels above 80 alpha, so an animated waveform's per-frame jitter does not matter) at three
points: the starting theme, after a switch with no reload, and a fresh load in the target
theme. Before: two canvases sat at distance 0 from the *starting* ink and 390 from the
target. After: every canvas on the page matches a reload in the new theme exactly, in both
directions.

One methodological trap worth recording. The first probe scrolled the whole page to find
every canvas, and that scrolling was itself remounting the CTA card - so the one canvas the
reviewer actually reported came back clean while genuinely broken. The check that counts
reproduces the user's sequence (sit at the bottom, switch, do not scroll, do not reload),
not the sequence that is convenient to automate.

**Depends on:** the theme system (`#87`, `#88` are the same feature's other two defects).

## Iteration 24 - 2026-08-15 · platform pivot, phase A0 (CALL-E removal)

### #77 - CALL-E removed outright; nothing can place a call until LiveKit origination lands

**S2 · DELIBERATE · api + web · `apps/api/app/integrations/voice/engine.py`, `apps/api/app/api/v1/routes/webhooks.py`, `apps/api/app/services/campaign_runner.py`, `apps/api/app/core/config.py`, `apps/api/app/main.py`, `apps/web/lib/api.ts`**

Not a bug - a planned, breaking removal, recorded here because it changes behaviour a user
can see and because the next person to read `SYSTEM.md` needs to know why calling is dark.

`PLATFORM_PIVOT_PLAN.md` replaces the single managed CALL-E vendor with a BYO-telephony
stack (LiveKit as the media/SIP substrate, the org's own Twilio/Plivo as carrier,
OpenRouter as the metered LLM marketplace). Step one is deleting CALL-E for real rather
than wrapping it, so the codebase never carries two half-live providers at once. Deleted:
`engine.py` (the vendor SDK boundary), `webhooks.py` (its terminal-event receiver), the
`calle-ai` dependency, the `CALLE_*`/`CALLFLOW_WEBHOOK_SECRET` settings, the
`GET /api/v1/runs/{run_id}/calls/{provider_call_id}/events` proxy, and four test files
totalling ~680 lines (`test_engine.py`, `test_webhooks.py`, `test_run_events.py`,
`test_live_progress.py`).

**Impact.** No call can be placed. `CampaignRunner.run_one()` returns
`status=FAILED, error=provider_unavailable, disposition=SKIPPED` for every contact that
clears the safety gate, with the reason "Calling is not available yet - the voice platform
migration is in progress." A run therefore still starts, still consumes this
organisation's rate-limit window, and still writes one honest failure row per contact.
Rejecting the run up front instead belongs with the "this campaign needs a voice agent
with a connected number" check that `RUNBOOK_ARBAAZ_PART_2.md` owns, and is deliberately
not done here.

The safety gate itself is untouched and still runs first, so the allowlist, per-run
ceiling, suppression check and rate limiter all keep behaving exactly as they will once
dialling is back - the guards were never CALL-E's.

**Fix.** Origination returns in `RUNBOOK_HET_PART_1.md` P1-T6 (LiveKit
`CreateSIPParticipant`), with the trunk provisioning that precedes it in P1-T5. The
retry-classification vocabulary is deliberately preserved: `DialFailure` and
`_RETRYABLE_FAILURES` stay, and P1-T6 maps LiveKit/Twilio/Plivo errors onto that same
enum rather than inventing a second failure taxonomy.

Two collateral changes worth naming, since neither is in the runbook's own task list:

- `GET /api/health` reported `api_key_configured`, a field named after a vendor key that
  no longer exists. It is now `calling_available`, hard-coded `false`. The three frontend
  readers (`lib/api.ts`, the run-start blocker, the `/status` board) follow it, so both
  surfaces say "unavailable" rather than silently reading `undefined` as falsy and
  happening to be right by accident.
- `routes/campaigns.py` imported `render_goal` *through* `campaign_runner.py`, which only
  re-exported it. That indirection died with the stub, so it now imports from
  `app/domain/goal_rendering.py` directly.

**Verified.** `ruff check app tests` clean; `pytest -q` 163 passed / 0 failed / 39 skipped
(was 28 failed / 150 passed before the test rewrite); `app.main` imports and serves 25
endpoints with no `webhooks`/`events` route in the OpenAPI schema; `pip install -e .[dev]`
resolves with no `calle-ai`; web `type-check` and `lint` clean.

Of the 28 broken tests, the vendor-agnostic ones were **repointed, not skipped** - the
check-and-reserve ceiling, the suppression block, the concurrency semaphore, run ordering,
the progress hook, and all four idempotency-key tests are still green. The idempotency
tests now assert against `_idempotency_key()` directly instead of observing a fake
gateway, and the concurrency tests patch `run_one` rather than faking a provider, so both
now test our own logic without a vendor in the loop at all. Only the genuine dial/poll
tests were removed; `RUNBOOK_HET_PART_1.md` P1-T7 rewrites them against the LiveKit client.

**Blocks:** every other CallFlow feature that needs a live call. **Depends on:** nothing.

### #78 - A run reported itself completed while its calls were still happening

**S2 · FIXED · api · `apps/api/app/api/v1/routes/runs.py`, `apps/api/app/database/repositories/runs.py`**

Introduced and fixed inside the same phase, recorded because the shape of it will recur
anywhere else this codebase swaps a request/response vendor for an event-driven one.

CALL-E could be polled to completion, so `CampaignRunner.run()` returning meant every call
had finished, and `_run_and_persist` correctly called `finish_run()` immediately after.
LiveKit is not that: origination returns when a call is **answered**, and the conversation
then continues in a room this process is not in. The same line therefore started marking
runs `completed` while their own `call_outcomes` rows still read "In conversation…".

**Impact.** A finished-looking run alongside live, unresolved rows - the exact fake success
state CLAUDE.md non-negotiable #9 exists to prevent. Nothing errored; the dashboard simply
lied, and the real outcomes would have landed afterwards against a run already closed.

**Fix.** `finish_run()` is replaced on that path by `finish_if_all_settled()`, which closes
a run only once no outcome is still in flight. Whichever worker callback settles the last
contact is the one that closes it. Idempotent by a `finished_at is null` guard inside a
single statement, so the concurrent callbacks a multi-contact run produces cannot both
close it - asserted directly, along with the all-blocked case still closing immediately
because those contacts settle on the spot.

**Depends on:** `#77`. **Blocks:** nothing.

### #79 - A provisioning retry could never resume, because every failure was terminal

**S2 · FIXED · api · `apps/api/app/services/number_provisioning.py`, `apps/api/app/database/repositories/telephony_provisioning.py`**

`telephony_provisioning` exists to stop a retried "connect number" attempt creating a
second LiveKit trunk that nobody will ever clean up. The first implementation of the
workflow marked **any** step failure as `failed`, and `failed` is terminal in the status
machine (`domain/provisioning.py`) - so a retry with the same idempotency key was refused,
and the resume logic the whole module was built around could not execute at all.

Found by its own tests: the resume test had to perform an illegal `failed → provisioning`
transition to set itself up, which is what exposed that the production path could never
reach the state it was testing.

**Impact.** Latent rather than shipped - no provisioning has run against a live account
yet. Had it shipped: every carrier hiccup would have forced a fresh attempt, and each
fresh attempt would have created another orphaned LiveKit inbound trunk and dispatch rule,
silently, with nothing in the product ever mentioning them.

**Fix.** `record_error()` notes why a step failed **without** ending the attempt, so the
row stays `provisioning` and remains resumable - which is what `PLATFORM_PIVOT_PLAN.md`
ADR-4 specified in the first place ("the row stays provisioning with last_error set"), and
which the first implementation quietly contradicted. `failed` now means superseded, set by
`supersede_unfinished()` when a newer attempt starts, so an agent cannot accumulate rows
that look live forever. The superseded row keeps its own `last_error` rather than having it
overwritten with "superseded" - that message is the only useful diagnostic on the row.

A related trap avoided in the same pass: the SIP username and password LiveKit and the
carrier must agree on are derived by HMAC from the attempt's idempotency key rather than
generated randomly, so a resumed attempt reproduces them exactly. Regenerating would leave
LiveKit dialling with a password the carrier no longer expects - a failure that surfaces
only as outbound calls being silently rejected, with both systems reporting themselves
healthy.

**Depends on:** `#77`.

## Iteration 25 - 2026-08-16 · platform pivot, phase A1 review pass (PR #23)

Nine defects found by review of the LiveKit/telephony PR before it merged. Numbered #109-#117 after the merge with dev: these were written as #90-#98 on a branch, and team chat had already merged those ids into the shared log. Eight of the
nine sit in a **seam between two modules that each mocked the other's half** - the dispatch
contract, the run/worker completion race, the escalation hand-off, the transaction boundary
between a service and its caller. None was a design error; every one was wiring, and every
one had a green test suite on both sides of it.

The pattern is worth naming, because it will recur for the rest of this pivot: a stub proves
a module honours the contract it was *told*, never that two modules were told the same one.
Where both halves live in this repo, test them against each other -
`apps/api/tests/test_dispatch_contract.py` loads the worker's real parser by path and feeds
it metadata the real orchestrator built.

### #109 - The two halves of the agent-dispatch contract disagreed, so no call could ever start

**S1 · FIXED · api + voice-runtime · `apps/api/app/services/campaign_runner.py`, `apps/voice-runtime/app/pipeline.py`**

`_originate()` built job metadata with `goal`, `campaign_id`, `contact_name`, `phone_masked`,
`result_schema`, `language` and `run_id` - and no `voice_agent` key. `AgentSpec.from_metadata()`
reads `metadata.get("voice_agent") or {}` and nothing else, so all three provider names
resolved to the empty string and `build_pipeline()` raised `UnknownProvider` on the first
lookup.

**Impact.** Every dispatched job died before its pipeline existed. The contact would have
heard the call connect into silence while the API recorded IN_FLIGHT, and the row would have
stayed there - the worker crashes before it can report anything. This was the phase's entire
deliverable, and it did not work.

**Fix.** `CampaignRunner` takes `voice_agent` beside `trunk_id` (both resolved from the same
voice agent) and sends it under the key the worker actually reads. A runner with a trunk but
no agent now refuses *before* dialling rather than letting the worker discover it after the
phone has rung. `test_dispatch_contract.py` builds metadata through the real `_originate()`
and feeds it to the real `AgentSpec.from_metadata()`, so the two can no longer drift apart
silently.

### #110 - The worker closed the session the instant it opened it, so every call reported empty

**S1 · FIXED · voice-runtime · `apps/voice-runtime/app/worker.py`**

`run_call()` ran `session.start(...)`, then `ctx.connect()`, then `session.aclose()` with
nothing awaiting the call's end. The ordering was also inverted - `connect()` has to precede
`start(room=...)`.

**Impact.** `aclose()` ran while the phone was still ringing. `transcript_from_history()`
returned the empty string, so `completion_payload()` picked `NO_ANSWER`, and
`duration_seconds` was a hardcoded `0` regardless. Every call - answered or not - would have
been reported as unanswered with no transcript.

**Fix.** `wait_for_call_end()` waits for the contact to join (an answer timeout), then for
them to leave, with a hard ceiling for a room that reports neither. Duration is measured from
`time.monotonic()`. The function is written against a duck-typed context specifically so it
*is* testable without a live room - it had been excluded from tests as "needs a live room",
and it was the one block that was wrong.

### #111 - Triage ran on every finished call and its result went nowhere

**S1 · FIXED · api · `apps/api/app/api/v1/routes/internal.py`**

`escalations_repo.create_for_outcome()` was called in exactly one place: inside
`_run_and_persist`'s `on_progress`, gated on a needs-a-person disposition. With LiveKit,
`run_one()` returns when the call is *answered*, so the outcome it reports is always
`IN_FLIGHT` - never a needs-a-person disposition. The real disposition arrives later through
the completion callback, which triaged it, wrote it, closed the run, and created nothing.

**Impact.** The "Needs a person" worklist was dead for every real call. Someone asking for a
human callback, or opting out, produced a correct `escalated` row that nobody was ever shown.
The check that remained could only fire for a contact that failed to dial.

**Fix.** The escalation is created in the completion callback, where the terminal disposition
actually exists.

### #112 - The provisioning error handler rolled back the ledger it had just written

**S1 · FIXED · api · `apps/api/app/services/number_provisioning.py`**

`connect_number()` caught a failed step, called `record_error()`, and re-raised. `as_user()`
wraps a request in a single transaction (`database/session.py`), so the raise discarded that
note *and* every `record_livekit_ids()` write the steps that had succeeded made.

**Impact.** Exactly the orphan ADR-4 exists to prevent, reintroduced by its own error path. A
carrier failure at step 3 leaves a real LiveKit inbound trunk and dispatch rule behind, but
the committed row records neither - so `_run_steps`' "skipped when the row already records its
result" has nothing to skip, and the retry creates a second trunk pair nobody will clean up.
The unit tests passed because they mock the connection, so no rollback ever happened.

**Fix.** Failure is *returned*, not raised: `connect_number()` hands back the attempt row
whichever way it goes, and `status` plus `last_error` are the result. The ledger now outlives
the failure, because the failure no longer unwinds the transaction carrying it.

### #113 - The connect-number workflow had no HTTP caller, so no number could be connected

**S1 · FIXED · api · `apps/api/app/api/v1/routes/telephony.py`**

The service (325 lines) and repository (235 lines) were complete and tested, but
`connect_number` was imported only by its own test file. Nothing in the running application
could start a provisioning attempt - which is also why `CampaignRunner._trunk_id` could only
ever be `None`.

**Impact.** The feature was unreachable from the product. It had been deferred on the grounds
that the runbook specified `Permission.AGENTS_WRITE`, which Part 2 owns.

**Fix.** `routes/telephony.py`, gated on `Permission.INTEGRATIONS_WRITE`/`INTEGRATIONS_READ`.
That is the honest permission rather than a placeholder: the endpoint reconfigures the
organisation's own Twilio or Plivo account using credentials stored on the Integrations page.
No new enum member, and no collision with Part 2's `permissions.py`.

### #114 - An uploaded CSV column could overwrite the agent's own instructions

**S2 · FIXED · api · `apps/api/app/services/campaign_runner.py`**

`**contact.context` was spread *last* into the dispatch metadata, after the deliberate keys.
The comment directly above it explained that the phone number is excluded because metadata
reaches LiveKit's logs and webhooks - and then let customer data overwrite everything beside
it.

**Impact.** A CSV column named `goal` rewrote what the agent was told to do. One named
`phone_masked` misaddressed the completion callback's row, so the call's result would insert a
second row rather than resolving the in-flight one. Uploaded data is context for a
conversation; it was in a position to control it.

**Fix.** The spread moved to the front, so CallFlow's own keys win. Asserted directly with a
contact whose context tries to overwrite `goal`, `phone_masked`, `run_id` and `voice_agent`.

### #115 - A failed dial left its agent dispatch behind, and the orphan overwrote the real outcome

**S2 · FIXED · api · `apps/api/app/integrations/livekit/client.py`**

The dispatch is created before the SIP participant, deliberately and correctly - an answered
call with no agent in the room is a person saying "hello?" into silence. But when
`create_sip_participant` then raised busy or unreachable, the dispatch survived.

**Impact.** The orphaned worker joins a room nobody will ever enter, waits out its answer
timeout, and POSTs `NO_ANSWER` - overwriting the accurate `busy`/`RETRY` outcome
`classify_error()` had just produced from the carrier's own SIP status. The operator is told
the wrong thing about a real call, and a retryable failure reads as unretryable.

**Fix.** The dial is wrapped and the dispatch deleted on failure. Cleanup is best-effort and
never replaces the dial's own classified error - letting it surface would turn "486 Busy Here"
into an internal error, which is strictly worse information.

### #116 - A settled call outcome could be dragged back to in-flight, losing its transcript

**S2 · FIXED · api · `apps/api/app/database/repositories/runs.py`**

Two writers upsert the same `(run_id, contact_name, phone_masked)` key: origination writes
IN_FLIGHT once a call is answered, and the completion callback writes the terminal row when it
ends. `append_outcome`'s `do update` set every column unconditionally, so whichever landed
last won.

**Impact.** A short call completes before origination's own progress write lands. The
in-flight write then overwrites the terminal row - discarding the transcript, the disposition
and the extracted result - and leaves `finish_if_all_settled` permanently unable to close the
run. Separately, `on_status` was declared on `run_one()`, threaded through from `run()`, and
never called; it is removed rather than left as an unwired hook.

**Fix.** The upsert refuses to downgrade a settled row, and falls back to reading the id when
its update is suppressed, since the caller still needs it to link an escalation.

### #117 - A run could stay "running" forever, from two independent causes

**S3 · PARTLY FIXED · api · `apps/api/app/database/repositories/runs.py`, `apps/api/app/api/v1/routes/runs.py`**

`finish_if_all_settled` requires `count(settled) >= runs.total`. Two things made that
unreachable: a contact list containing the same `(name, phone)` twice collapsed under the
upsert key, so the count could never reach `total`; and a worker that died before its callback
left a row in flight indefinitely (`ReportFailed` is logged and swallowed). `finish_run` used
to be unconditional, so neither could happen before this phase.

**Impact.** The run reads "running" for good and its progress never completes. The duplicate
case also silently discarded one real call's transcript.

**Fix.** Contacts are deduplicated at run start - a run should not dial the same person twice,
and the row being overwritten was a real call. `expire_stale_in_flight` settles rows older than
the carrier-enforced call ceiling as `unreachable`/`timed_out`, recorded as a real failure
rather than quietly closed, because nobody knows what was said (non-negotiable #9).

**Still open.** The sweep only runs when a callback or a run-completion check asks. A run whose
*every* worker dies has nobody left to ask, and stays open until something else touches it. A
scheduled reaper is the real fix and needs a scheduler this deployment does not have yet.

## Iteration 32 - 2026-08-16 · the Agentic tab (voice-agent builder)

### #90 - Voice agents can be built and previewed for real, but none can place a live call yet

**S2 · DELIBERATE · api + web · `apps/api/app/api/v1/routes/voice_agents.py`, `apps/api/app/services/voice_preview.py`, `apps/web/app/(app)/app/agentic/`**

Not a bug - a planned, sequenced gap, recorded here for the same reason `#77` is: the next
person to read `SYSTEM.md` needs to know this feature is real but not yet load-bearing.

The Agentic tab ships the full BYO voice-agent stack the platform pivot calls for: two new
tables (`voice_agents`, `ai_provider_credentials`), a CRUD API gated by three new
permissions (`AGENTS_READ`/`WRITE`/`DELETE`), a provider catalog (STT: Sarvam, Deepgram;
TTS: Sarvam, ElevenLabs; LLM: four curated OpenRouter models), a working `SarvamAdapter`
(Saarika STT + Bulbul TTS, real REST calls against `api.sarvam.ai`), and a full builder UI
- pick providers, connect a vendor key inline, preview a real TTS voice, assign one of the
org's already-connected Twilio/Plivo numbers.

**Impact.** An organisation can fully configure and preview an agent today. What it cannot
do is have that agent actually answer or place a phone call - that depends entirely on the
separate LiveKit voice runtime tracked in `RUNBOOK_HET_PART_1.md`, which does not exist yet
(`#77`). Two narrower gaps within the feature itself, both handled honestly rather than
faked: only Sarvam has a real preview adapter (Deepgram/ElevenLabs/OpenRouter models are
selectable for later use, but their "Preview" button says plainly that it isn't wired up
yet, via `app/services/voice_preview.py`'s `preview_available` check - never a fake result);
and the "Prebuilt" agents section is a placeholder notice, not a working picker, since
CallFlow has no hosted AI-vendor credentials or persona catalog of its own yet.

**Fix.** No fix needed until the LiveKit runtime lands - at that point, `voice_agents`'
`telephony_provider` field and the org's connected `provider_credentials` row are what a
real dial needs to originate from, and nothing about this feature's data model should need
to change to support it. Wiring OpenRouter's own preview and Deepgram/ElevenLabs adapters
are separate, smaller follow-ups (flip `preview_available` to `true` in
`app/integrations/ai_providers/catalog.py` once each adapter exists - no other code changes
needed).

**Verified.** `ruff check app tests` clean; `pytest -q` 258 passed (up from 235 before this
iteration; 59 of those in `test_rls_isolation.py`, including new cross-tenant and
same-org-role coverage for both new tables); `npm run lint`, `type-check`, and `build` all
clean, with `/app/agentic`, `/app/agentic/new`, and `/app/agentic/[id]` all present in the
build's route table.

**Blocks:** nothing (an org can build and preview agents right now). **Depends on:** the
LiveKit voice runtime (`#77`) for any of this to originate a real call.

## Iteration 32 - 2026-08-15 · internal team chat (RUNBOOK_JATIN_PART_3.md)

### #90 - `channel_members_insert`'s RLS check verified the inserter, never the person being added

**S1 · FIXED · database · `apps/api/alembic/versions/202608100000_team_chat_channels_and_messages.py`**

Found and fixed before ever shipping, while implementing the internal team chat feature's
RLS from the source plan's own specified SQL: `channel_members_insert`'s `WITH CHECK` read
`is_channel_member(channel_id) and is_org_member(channel_org_id(channel_id))` - both halves
resolve against `current_user_id()`, since that's what `is_org_member()` always checks. It
verifies the *caller* is already seated and still belongs to the organisation. Nothing in
the check touches the new row's own `user_id` - the actual person being added, who is not
necessarily the caller. An existing member could seat **any real user id in the system**,
including someone from a completely different organisation, into their channel. That row
would then satisfy `is_channel_member()` for the outsider, and with it, `channels_select`/
`messages_select` access to this organisation's channel and every message in it - the same
`create_channel()`-bypasses-RLS reasoning applied in reverse, and exactly the class of bug
CLAUDE.md calls the most expensive one this product can ship.

**Impact.** Cross-tenant data exposure: a teammate in Org A could hand a user from Org B
read access to Org A's channel and its message history, with no admin action and no audit
trail beyond the insert itself.

**Fix.** Added `public.is_user_org_member(target_org, target_user)`, the two-argument,
`SECURITY DEFINER` sibling of `is_org_member()` that checks an arbitrary target user rather
than always `current_user_id()`. `channel_members_insert` now also requires
`is_user_org_member(channel_org_id(channel_id), user_id)` on the row being inserted.
`create_channel()` needed the identical fix independently - it's `SECURITY DEFINER` and so
bypasses this policy entirely for its own body, meaning an outsider's id in its `member_ids`
argument would otherwise seat them with no RLS check at all; it now validates every id
against `is_user_org_member()` itself before either insert runs, raising rather than
seating. Verified by `test_channel_members_insert_rejects_seating_a_non_org_member` and
`test_create_channel_rejects_a_member_id_outside_the_organisation_and_leaves_no_orphaned_channel`
(`apps/api/tests/test_rls_isolation.py`), both against the real database.

### #91 - `invitations_repo.accept()` could abort its own transaction on a wrong-email or racing accept

**S2 · FIXED · backend · `apps/api/app/database/repositories/invitations.py`**

Found while fixing `#90` - the exact same shape of bug, in code this phase didn't touch
until now. `accept()` catches `InsufficientPrivilegeError`/`UniqueViolationError` from the
membership `INSERT` (a caller whose email doesn't match the invitation, or two concurrent
accepts of the same invitation racing each other) and returns `None`. But the `INSERT` ran
as a bare statement, not inside a nested transaction - so once Postgres aborted it, the
connection's transaction stayed aborted, and the very next statement (the `invitations`
`UPDATE`, or, under `database.as_user()`, that context manager's own cleanup on the way out)
raised `InFailedSqlTransactionError` instead of ever reaching `accept()`'s intended clean
`None`. `organisations_repo.set_member_role()` already documents this exact Postgres
behaviour and already uses the fix; `accept()` and this phase's own new
`messages_repo.send_message()` both needed it independently.

**Impact.** A real, reachable path: anyone signed in with a different email than an
invitation's target, or a double-clicked/retried accept, would surface as an unhandled 500
instead of the honest "couldn't accept" outcome the route is supposed to report.

**Fix.** Wrapped the `INSERT` in `async with conn.transaction():` (asyncpg issues a
`SAVEPOINT`), so the caught error rolls back only that statement - the outer request
transaction stays usable. Verified by
`test_accept_by_the_wrong_email_returns_none_without_aborting_the_transaction`
(`apps/api/tests/test_rls_isolation.py`), which fails with `InFailedSqlTransactionError` on
the pre-fix code (checked directly) and passes with the fix.

### #92 - `messages_repo.send_message()` never inserted `org_id`, so every real send 500'd

**S1 · FIXED · backend · `apps/api/app/database/repositories/messages.py`, `apps/api/app/api/v1/routes/messages.py`**

Found by driving the chat feature end to end for real - the first time anything in this
phase called `POST /api/v1/channels/{id}/messages` through the actual HTTP API rather than
inserting `messages` directly via SQL. `messages.org_id` is `NOT NULL` (deliberately
denormalised - this migration's own docstring), but `send_message()`'s `INSERT` only ever
listed `channel_id, sender_id, body`. Every real send failed with
`asyncpg.exceptions.NotNullViolationError: null value in column "org_id"`, surfaced to the
caller as an unhandled `500`. Every one of this phase's other chat tests supplies `org_id`
by hand in a raw SQL `INSERT` (to seed a message for an RLS check), which is exactly why
none of them exercised the repository's own `INSERT` and none caught this - a real, and
instructive, gap: RLS-focused tests proved the *policies* were right without ever proving
the *repository code* those policies sit in front of actually ran successfully.

**Impact.** The one write operation the whole feature exists to support - sending a
message - was completely broken. `GET` endpoints, `create_channel()`, and every RLS
guarantee were all fine in isolation; nothing before this exercised the write path for
real.

**Fix.** `send_message()` takes `org_id` and includes it in the `INSERT`; the route passes
`user.org_id`. Verified two ways: `test_owner_can_send_a_real_message_through_the_repository`
(`apps/api/tests/test_rls_isolation.py`), checked directly against the pre-fix code (fails
with the same `NotNullViolationError`); and manually, end to end, against a real local
Supabase stack (`supabase start`) - real signup, real signed JWT, real
`POST /api/v1/channels` and `POST .../messages` calls, both succeeding and the message
readable back via `GET .../messages`.

**Method note.** This is the reason a fresh local Postgres (rather than only the shared
cloud dev project) was worth setting up mid-phase: cross-tenant/RLS correctness was already
proven against the cloud database, but nothing had yet driven the write path through the
real API surface end to end. A local stack made that cheap enough (a few `curl` calls,
seconds each) to actually do rather than defer.

### #93 - `test_anonymous_sees_nothing` assumed `anon`'s access is always denied via RLS, never via a missing grant

**S4 · FIXED · backend (test only) · `apps/api/tests/test_rls_isolation.py`**

Found spinning up a second, independent Postgres instance for local development
(`supabase start`) and running the full suite against it. This migration's own `GRANTS`
block never grants `anon` anything on `organisations`/`users`/`memberships`/`suppressions`
("anon gets nothing: every read here requires a signed-in user") - so a bare Postgres
provisioned purely from these migrations denies an `anon` query with `permission denied`,
before RLS is ever consulted. The Supabase-hosted dev project apparently carries its own
platform-default grants underneath (a provisioning detail outside this repo's own
migrations), so the identical query there returns zero rows via RLS instead. The test
asserted the second outcome specifically (`count == 0`) and had never been run anywhere
that would exercise the first.

**Impact.** None to the product - both outcomes equally prove `anon` cannot read a row,
and this is the only test in the suite that would have told them apart. Impact is entirely
to whether this suite runs clean on a second, independently-provisioned Postgres.

**Fix.** Accepts either a successful zero-row result or a caught `InsufficientPrivilegeError`
per table (a nested transaction/`SAVEPOINT`, so one table failing doesn't stop the loop from
reaching the next). Confirmed this suite now passes unmodified against both the shared
cloud dev project and a fresh local stack.

## Iteration 33 - 2026-08-15 · Teams-parity chat: search, group management, read state, message edit/delete, pagination

Bringing chat toward Microsoft-Teams-level parity (member search, 1:1/group management,
add/remove/rename with real authorisation, read/unread, message edit/delete, cursor
pagination, `/app/chat/[id]` URLs, `channel_members` Realtime) - the gap analysis this
iteration closes is its own artifact, not repeated here. Four real bugs found and fixed
along the way, two caught by the new tests before anything ever ran for real, two that
passed every existing test and only broke against the actual running app - the same
pattern iteration 24's #92 already established, repeating here because the fix for it
(build a local dev stack, drive the feature over real HTTP and a real browser) is exactly
what caught these too.

### #94 - `channel_members` had a `DELETE` **policy** but no `DELETE` **grant**

**S2 · FIXED · database · `apps/api/alembic/versions/202608100000_team_chat_channels_and_messages.py (now folded into the single consolidated chat migration)`**

Caught by `test_channel_members_delete_leave_creator_remove_and_admin_moderate` before this
migration ever left this machine - every "remove a member" call failed with
`InsufficientPrivilegeError: permission denied for table channel_members`, not because the
policy was wrong, but because RLS and grants are two separate, both-required layers
(`initial_schema.py`'s own framing: "grants decide which tables are reachable at all") and
this migration wrote the policy without the matching `grant delete`.

**Fix.** Added `grant delete on public.channel_members to authenticated;` alongside the
policy.

### #95 - An org admin renaming a channel they hadn't joined got back nothing, even though the rename worked

**S2 · FIXED · database · `apps/api/alembic/versions/202608100000_team_chat_channels_and_messages.py (now folded into the single consolidated chat migration)`**

`channels_select` (`b3f7d2a891c5`) was `is_channel_member(id)` only. `channels_update`'s new
policy correctly lets an org owner/admin rename *any* channel in their org, including one
they never joined - but `UPDATE ... RETURNING` re-checks the updated row against the
table's own `SELECT` policy before handing it back, the identical mechanism
`create_organisation()`'s docstring describes for `INSERT ... RETURNING`, here showing up
on `UPDATE` instead. An admin who wasn't a member failed `is_channel_member(id)`, so the
rename silently applied while `rename_channel()` returned `None` - a real update the caller
could never see confirmed.

**Impact.** Not a security hole (the admin was authorised to make the change) - a
correctness bug that would have read as "renaming isn't working" with no error to explain
why, for the one moderation case the feature exists to support.

**Fix.** `channels_select` gained the same owner/admin branch `channel_members_select`
already has. Deliberately scoped to `channels` only - `messages_select` keeps no such
branch, so this does not let an admin read a channel's contents, only see that it exists
and rename it. Verified by `test_channels_update_rename_matrix`.

### #96 - `useOrgRealtime` broke entirely the moment a second component watched the same table

**S1 · FIXED · web · `apps/web/lib/hooks/use-org-realtime.ts`**

Found live, not by any test - the chat page loaded to a hard `500` the moment the new
"Chat" nav unread badge (`use-chat-unread.ts`) started also subscribing to the `channels`
table. `supabase-js` deduplicates `.channel(name)` calls by name within one client; this
hook named its channel deterministically from `table` + `orgId` alone
(`realtime:channels:{orgId}`), which was fine when exactly one caller ever watched a given
table (true for all of Part 3) and broke the instant a second one did: the second `.channel()`
call got handed back the *first* caller's already-`.subscribe()`d channel object, and
calling `.on()` on an already-subscribed channel throws
`cannot add postgres_changes callbacks ... after subscribe()` - which the console reported,
but the rendered page just showed the site's generic 500 boundary, with nothing pointing at
Realtime at all.

**Impact.** Total, silent breakage of the entire chat page (and, by the same mechanism,
would have hit any two features that ever watched the same org-scoped table) - and the
error message named a Supabase internal, not this hook, which is exactly the kind of
regression a written spec or a mocked test would not have caught; only actually loading the
page did.

**Fix.** The channel name now includes `useId()`, so every call site - regardless of how
many others watch the same table - gets its own channel. Verified two ways: a live
Playwright session confirmed the page loads and a `channel_members` change (a real add,
issued from outside the browser) appears in an already-open members panel with no reload;
and, before settling on that result, a first pass at this same check used an unscoped text
match and produced a false pass (it matched a *different* channel's "2 members" text in the
list behind the open sheet) - corrected to assert against the open sheet specifically,
which is the version that actually caught this bug.

### #97 - `PATCH .../messages/{id}` (edit) 500'd on every real edit

**S1 · FIXED · backend · `apps/api/app/api/v1/routes/messages.py`**

Same shape as `#92`: `messages_repo.edit_message()`'s `UPDATE ... RETURNING` has no join to
`users` (unlike `list_messages()`), so its Record never carries `sender_name` - but the
route built its response with `_message_json()`, written for `list_messages()`'s joined
rows. Every real edit raised `KeyError: 'sender_name'`. `send_message()`'s route had
already solved this exact mismatch for the same reason (its own insert has no join either)
by building `MessageOut` from `user.name` directly instead of calling `_message_json()`;
`edit_message()` just hadn't followed that precedent.

**Impact.** The entire edit feature was unusable - caught only by driving a real edit
through the live API, not by `test_messages_update_only_the_sender_can_edit_or_delete`
(which calls the repository directly and never touches the route or `_message_json()` at
all).

**Fix.** `edit_message()`'s route now builds `MessageOut` the same way `send_message()`'s
does. Verified by a new route-level test,
`test_edit_message_route_does_not_need_sender_name_from_the_repo`
(`apps/api/tests/test_messages_routes.py` - the first route-level test file for chat),
checked directly against the pre-fix code (reproduces the identical `KeyError`); and again
live, end to end, against the running local stack.

## Iteration 34 - 2026-08-16 · deep technical audit of chat: correctness, scalability, concurrency

A system-design-level audit of chat only (frontend, API, repositories, schema, RLS,
Realtime, tests), not a re-run of Iteration 33's feature checklist. Three real, verified
gaps, all confirmed against the actual code and - where practical - the live running stack
and the real dev database, not assumed from reading. No security boundary was ever actually
open; every fix here is either a correctness bug (duplicate DMs, a pagination edge case) or
a scalability bug (a hot path re-fetching far more than it needs), plus the error-handling
gap that made one of the correctness bugs' own guard rails surface as a `500` instead of a
clean rejection.

### #98 - Starting a DM with the same teammate twice created two separate conversations

**S2 · FIXED · database · `apps/api/alembic/versions/202608100000_team_chat_channels_and_messages.py (now folded into the single consolidated chat migration)`, `channels.py`**

`create_channel()` never checked for an existing DM between the same two people - every
"message this person" click made a brand-new `channels` row and a brand-new pair of
`channel_members` rows. This is a direct violation of `CLAUDE.md`'s idempotency
non-negotiable ("every mutating endpoint... safe to run twice"), not merely an inconvenience:
a relationship's message history silently scattered across N channels, with no way for
either person to find the "real" one. Confirmed against this codebase's own local dev
database, not hypothetically - applying the migration's backfill found three separate
pre-existing DM channels for the same pair of test users, left over from earlier manual
testing sessions in this project.

**Impact.** Every DM in the product before this fix. Not a cross-tenant or security issue -
both users were always in the same organisation - but a real, user-visible correctness bug
central to "1:1 chat" working at all.

**Fix.** `channels.dm_pair` (a sorted 2-element `uuid[]` of the two members, set only for
`kind = 'dm'`) plus a partial unique index on `(org_id, dm_pair)`. `create_channel()` now
checks for an existing row first (no contention, the common case) and falls back to
re-selecting the winner if a concurrent call raced it into the unique index instead (an
implicit savepoint from the function's own `exception` block, not a new Python-side
transaction dance). A `dm` is also now validated as actually 1:1 - exactly one other member,
never the caller's own id - which was previously unenforced at any layer. Pre-existing
duplicate DMs from before this migration are not merged (that is a data decision, not a
schema one); one representative per pair becomes the discoverable channel going forward,
and any other duplicate keeps working exactly as before, just outside the new dedup index.
Verified by `test_create_channel_dm_is_idempotent_and_reuses_the_existing_channel`,
`test_create_channel_dm_rejects_wrong_member_count_and_self_dm`,
`test_channels_dm_pair_unique_index_rejects_a_duplicate_at_the_database_level`, and a real
concurrency test across two independent physical connections
(`test_concurrent_dm_creation_from_two_connections_converges_on_one_channel`); also checked
live against the running API with real signed JWTs (two `POST /channels` calls for the same
pair returned the identical channel id).

While in this function: `create_channel()`'s own pre-existing guards ("not a member of this
organisation", "one or more member_ids are not members of this organisation") were never
caught anywhere between the database and the HTTP response - a member id from another
organisation submitted through `POST /channels` raised a bare `asyncpg.exceptions.RaiseError`
that FastAPI's default handler turned into a generic `500`. The rejection itself already
worked correctly (no channel was ever created; this was never a cross-tenant leak), only its
shape was wrong. `channels_repo.create_channel()` now catches `RaiseError` and re-raises
`ValueError`, which the route turns into a clean `400`. Verified by
`test_create_channel_repo_turns_a_cross_org_member_into_a_value_error` and, live, by
submitting a real user id from a genuinely different organisation through the running API
and confirming a `400` with the plain-English rejection message, not a `500`.

### #99 - The chat unread-badge hook re-ran chat's heaviest query on every message sent anywhere in the organisation, for every open tab

**S2 · FIXED · web + backend · `use-chat-unread.ts`, `channels.py`, `messages.py` route**

`useChatUnreadCount()` is mounted in `AppShell` - every `/app/*` page, for every signed-in
user, not just the chat page - and until this fix, every one of its three Realtime
subscriptions (`channels`/`messages`/`channel_members`) called `api.listChannels()` on every
event. That endpoint's query (`_CHANNEL_COLUMNS`) does an `array_agg` of every member of
every channel the caller is in, plus two correlated subqueries per channel row, just so the
badge could sum one field back out of the response and discard the rest. At the scale this
audit was asked to evaluate against - thousands of users per organisation, high-volume
concurrent messaging - one message sent anywhere in an organisation that a hundred people
had open in a browser tab meant a hundred full channel-list queries landing on the database
at once, member arrays and all, to compute a single integer. This is the kind of bottleneck
that doesn't show up in any single-user test or in normal development traffic, and would
have been the first thing to fall over under real concurrent load.

A second, related gap in the same area: `useOrgRealtime()`'s callback discarded the Postgres
Changes payload entirely, so every subscriber re-fetched on every org-wide event on a table
regardless of whether the changed row had anything to do with what was currently open. In
`chat-shell.tsx`, a message sent in channel A re-fetched and re-marked-read whatever
different channel (B) happened to be open in that tab, on every send.

**Fix.** A dedicated `GET /api/v1/channels/unread-count` endpoint backed by
`channels_repo.total_unread_count()` - one join between `messages` and the caller's own
`channel_members` rows, no per-channel fan-out, no member-list aggregation - replaces
`listChannels()` in the badge hook. `useOrgRealtime()` now passes the changed row's payload
through to its caller instead of a bare trigger, and debounces its own callback (300ms,
trailing) so a burst of events coalesces into one refetch rather than one per event;
`chat-shell.tsx`'s message and `channel_members` subscriptions use the payload to skip a
refetch of the open conversation when the change was actually about a different one, while
the channel list itself still refetches unconditionally (a membership change can add or
remove a channel from the caller's list regardless of which one was open). Verified by
`test_total_unread_count_matches_the_sum_of_per_channel_counts` and
`test_total_unread_count_is_scoped_to_the_callers_own_organisation` (RLS, not the `org_id`
parameter, is what actually confines the new endpoint - passing the wrong organisation's id
returns 0, not a leak), plus route-level and live-HTTP checks; frontend type-check, lint, and
build all pass with the payload-typed hook signature.

### #100 - Cursor pagination could silently skip or repeat a message under an exact-timestamp tie

**S3 · FIXED · backend · `apps/api/app/database/repositories/messages.py`**

`created_at` is Postgres's transaction-start time, not per-statement wall-clock, so two
messages committed by genuinely concurrent requests can land on the exact same timestamp.
`list_messages()`'s cursor was a bare `created_at < $before` - if the boundary message and
the next one down were tied, a strict `<` comparison would resolve the tie by silently
dropping whichever one didn't make the earlier page, a message that would then never appear
in the conversation's history again on that client. Rare at today's traffic (a single
channel needs two sends to genuinely overlap at transaction-start-time resolution), but
"millions of messages, high concurrent writes" - the scale this audit was asked to evaluate
against - is exactly where rare-per-request becomes routine-per-day.

**Fix.** `list_messages()` accepts an optional `before_id` alongside `before`; when both are
given, ties on `created_at` are broken by `id` (`order by created_at desc, id desc`, `where
... or (created_at = $before and id < $before_id)`). Additive and backward compatible - a
caller that only sends `before` keeps the prior behaviour. `chat-shell.tsx`'s
`loadOlderMessages()` now sends both. Verified by
`test_pagination_with_identical_timestamps_uses_id_as_a_tiebreaker`, which forces three
messages onto one identical timestamp directly (not relying on real concurrency to
reproduce the tie) and pages through them one at a time, asserting none is skipped or
repeated.

## Iteration 35 - 2026-08-17 · chat RLS: org departure did not revoke Realtime/PostgREST access

Follow-up to Iteration 34's #98 discussion of organisation isolation. That round's own re-evaluation
(requested before any fix, to confirm the finding against a real already-active session rather than
assume a stale row is automatically exploitable) precisely scoped what was and wasn't true: the
FastAPI application was already safe - `current_user()` re-checks live `memberships` on every
request, for an existing session exactly as much as a fresh one - but Supabase Realtime and direct
PostgREST access, which authorise purely off RLS with no FastAPI dependency at all, were not.

### #101 - Chat RLS treated `channel_members`/`created_by` as permanent, never re-checking current organisation membership

**S1 · FIXED · database · `apps/api/alembic/versions/202608100000_team_chat_channels_and_messages.py (now folded into the single consolidated chat migration)`**

`is_channel_member()` and `channel_created_by()` only ever queried `channel_members`/`channels`
directly - neither joined back to `memberships`. `channel_members_insert` (migration `b3f7d2a891c5`)
already required the inserter's *live* org membership via `is_org_member(channel_org_id(...))`; that
check was never applied to `channels_select`, `messages_select`, `messages_insert`, or the
creator-branch of `channels_update`/`channel_members_delete`.

**Impact, precisely confirmed live, not assumed.** A user who left an organisation through the real,
unprivileged `DELETE /api/v1/organisations/me/members/{self}` endpoint - using the exact same
already-active browser session, never reloaded - could not reach any chat data through the CallFlow
application itself (confirmed both for that pre-existing session and a freshly-issued one afterward:
identical `403` either way). But the same session's already-open Realtime subscription kept receiving
the full websocket frame (message body included) for new events in the organisation they'd left, and
the same session's token, used directly against Supabase's own PostgREST endpoint with no CallFlow
backend involved, could both read and insert messages in that organisation. A second, independent
instance of the same root cause: a departed user who had created a channel was still recognised as
its creator and could still rename it or remove other members from it via the identical RLS path.

**Fix.** Added `and public.is_org_member(...)` to `channels_select`, `messages_select`,
`messages_insert`, and the creator-branch of `channels_update`/`channel_members_delete` - additive to
each existing `USING`/`WITH CHECK` clause, not a replacement, so nothing previously correct (a live
member's own access, an org owner/admin's moderation) changed. `channel_members_delete`'s
self-removal branch (`user_id = current_user_id()`) deliberately keeps no org-membership requirement,
since leaving a channel yourself must keep working even for an already-stale row. `channel_members_select`
has the identical shape and was not changed - it wasn't part of what this round tested and confirmed,
so it stays out of scope rather than being bundled in on assumption.

Complementary, not a substitute: `organisations_repo.remove_member()` (the self-leave path) now also
deletes the departed user's `channel_members` rows for that organisation, in the same transaction as
the `memberships` delete - data hygiene (an honest member list/count for whoever remains), not the
security boundary itself. The regression tests below (`test_departed_org_member_loses_chat_rls_access_even_with_a_stale_channel_members_row`)
deliberately leave a stale row in place and confirm the *policies* reject it regardless, so the fix
does not depend on every future code path remembering this cleanup.

**Verified:**
- 4 new tests in `test_rls_isolation.py` (278 total, all passing; full existing suite unaffected,
  including every pre-existing cross-org isolation test): an active member's full chat access
  (read/send/rename) is unaffected by the tightened policies; a departed member - identical identity,
  stale `channel_members` row deliberately left in place - loses `channels_select`/`messages_select`/
  `messages_insert`; a departed creator can no longer rename or remove another member via the
  creator-branch; `remove_member()` actually clears the stale rows.
- Live, post-fix, against the real running API, a real browser, and Supabase's own endpoints directly,
  using one continuous already-active session throughout: FastAPI blocked before and after leaving
  (unchanged, as expected); direct PostgREST `GET /rest/v1/messages` returned `200` with zero rows
  (previously returned message content) and `POST` returned `403` "new row violates row-level
  security policy" (previously `201`, a successful insert); the same already-open Realtime
  subscription received no websocket frame at all for a new message sent after the user left
  (previously the full frame, message body included, was delivered).

**Depends on / Blocks:** Iteration 34 #98.

## Iteration 36 - 2026-08-18 · chat RLS: `channel_members_select` was the one policy #101's fix didn't cover

Direct follow-up to #101. That fix's own migration deliberately left `channel_members_select`
untouched, flagging it for confirmation rather than assuming it shared the same gap. A dedicated
audit pass confirmed it did, live.

### #102 - `channel_members_select`'s member branch had no live organisation-membership check

**S2 · FIXED · database · `apps/api/alembic/versions/202608100000_team_chat_channels_and_messages.py (now folded into the single consolidated chat migration)`**

`is_channel_member(channel_id) or has_org_role(...)` - the first branch, like every other one #101
fixed, never re-checked `memberships`. A departed member's stale `channel_members` row kept them
visible to this policy indefinitely.

**Impact, confirmed live.** A user who left an organisation (a plain `memberships` delete, their
`channel_members` row deliberately left in place to isolate the policy from the cleanup #101 also
added) could still read the full membership list of a channel they used to belong to - who else was
in it, `org_id`, `joined_at` - directly via PostgREST, no CallFlow backend involved: `GET
/rest/v1/channel_members?channel_id=eq...` returned `200` with the full member list both before and
after the test, until the fix. No message content and no write path were exposed by this one - lower
severity than #101, but the same root cause and the same reachable path.

**Fix.** One line, the identical pattern: `is_channel_member(channel_id) and
is_org_member(channel_org_id(channel_id))` for the member branch. The organisation admin/owner branch
(`has_org_role(...)`) was already correct - it queries live `memberships` by construction - and is
unchanged, so an admin/owner's ability to see membership of any channel in their org for moderation
purposes (`test_admin_can_see_channel_membership_but_not_messages_for_a_channel_they_are_not_in`) is
untouched.

**Verified**, following the same before/after discipline as #101:
- The new regression test (`test_departed_member_can_no_longer_read_channel_membership_via_a_stale_row`)
  was written and confirmed to **fail** against the pre-fix policy, then confirmed to **pass** after
  the migration - 279 backend tests total, full suite green, `ruff` clean.
- Live, post-fix: the identical PostgREST call that returned the full member list before the fix now
  returns `200` with zero rows, stale row and all.
- Live Realtime, with clear before/after markers: an active member's already-open `channel_members`
  subscription received the row's `UPDATE` event normally (10 delivered frames, matching known
  pre-departure activity); the identical `UPDATE` issued immediately after simulating departure -
  same stale row, same subscription, never reloaded - produced zero delivered frames.

**Depends on / Blocks:** Iteration 35 #101.

## Iteration 37 - 2026-08-16 · chat page: search-to-DM, a persistent list pane, and @mentions

Landed three requested features on `/app/chat` (inline organisation-member search to start a DM
directly from the list, the channel list and an open conversation visible side by side instead of
the conversation as a full-screen modal, and Teams-style `@mention` autocomplete/highlighting scoped
to a conversation's own members) - the group-creation dialog was left untouched by request. Restructuring
the page to a persistent two-pane layout surfaced both bugs below, live, before either shipped.

### #103 - Opening a different conversation remounted the whole chat page

**S2 · FIXED · web · `apps/web/app/(app)/app/chat/`**

The two-pane layout's whole point is that the channel list, its search box, and an open conversation
stay on screen together so a person can switch between conversations directly. The first shape of
this (a `chat/[id]/page.tsx` dynamic route, `channelId` passed down as a prop) defeated that on its
own: Next.js remounts a `[id]/page.tsx` on every change to its own dynamic segment - by design, not a
framework bug, since a detail page is often meant to treat a new param as a fresh identity - which
wiped the channel list, the search box, and every other bit of `ChatShell`'s state on every single
click between conversations.

**Impact, confirmed live** by the person testing it, mid-session: switching conversations visibly
re-rendered the entire section - list, header, composer - rather than only the conversation content,
which is the opposite of what a persistent list pane is for.

**Fix.** The open conversation now lives in a query param (`/app/chat?c={id}`) on one stable page
rather than a route segment, so there is no dynamic-segment identity for Next to remount on. Reading
that query param still requires `useSearchParams()`, which Next.js requires to sit under a
`<Suspense>` boundary - and a Suspense boundary is itself torn down and rebuilt on navigation, which
would have reintroduced the identical remount if `ChatShell` read it directly. It's isolated instead
in a small stateless leaf (`ChannelIdSync`) that does nothing but report the current id upward via an
effect; that leaf remounting on every navigation is harmless, since it holds no state of its own.

**Verified live**, end to end (Playwright against the local dev stack): a `window`-level marker set
before switching conversations was confirmed to survive the switch (proving the navigation itself is
a soft client transition, not a full reload) together with a mount/unmount instrumentation effect on
`ChatShell` confirming it mounts exactly once across an arbitrary number of conversation switches -
list state (an in-progress search box value) and the rendered channel buttons were confirmed intact
after switching conversations twice. `npm run build` (which prerenders and would fail immediately if
`useSearchParams()` were not correctly boundaried) passes.

### #104 - The message pane never auto-scrolled to the newest message

**S3 · FIXED · web · `apps/web/app/(app)/app/chat/chat-shell.tsx`**

The previous full-screen-modal conversation view had no fixed height, so the page (and, incidentally,
whatever was newest) was usually already in view. Giving the conversation its own bounded,
independently-scrollable pane - required for the list and the conversation to be visible together,
`#103`'s whole point - removed that incidental behaviour without replacing it: nothing set `scrollTop`
on open, on send, or on a live message arriving, so the newest content could sit below the fold with
no indication anything had changed.

**Impact, confirmed live** via a screenshot taken immediately after sending a message in a conversation
with enough history to overflow the pane: the composer cleared (confirming the send succeeded) but the
just-sent message was not visible without the reader scrolling down manually.

**Fix.** A `useLayoutEffect` keyed on the open conversation and its message list sets the pane's
`scrollTop` to its `scrollHeight` after every render, except when the render was triggered by
`loadOlderMessages()` paging in history - that one case anchors the scroll position to what was
already on screen instead, or paging in older messages would otherwise yank the reader back down to
the bottom they were trying to scroll away from. Ship order mattered here: a later change gave the
loading state a minimum-visible floor (`useMinVisible`, so a fast/cached fetch doesn't flash a loader
for under a second) which decoupled *when data arrives* from *when it actually reaches the DOM* -
the auto-scroll effect's dependency list has to include that loader's own visibility, or it fires
too early, against content that has not been rendered yet.

**Verified live**, in a viewport short enough to force real overflow (confirmed via `scrollHeight >
clientHeight` on the actual message-pane element, not assumed): before the fix, `scrollTop` sat at `0`
after opening a conversation with overflowing history; after the fix, `scrollTop` reads exactly
`scrollHeight - clientHeight` (bottom) both on opening a conversation and immediately after sending a
new message into it.

**Depends on / Blocks:** Iteration 37 #103 (same restructure exposed both).

## Iteration 38 - 2026-08-16 · team chat code review: four must-fix findings

A full review of the chat feature against `RUNBOOK_JATIN_PART_3.md` (26 files, +5538/-56)
found four issues serious enough to block the PR - "careful work... but #1 and #2 mean live
chat doesn't reliably deliver, which is the feature." All four are fixed below. The review's
"should fix" and "nit" findings (edit-then-403 ordering in `edit_message`, the admin-branch
product question on `channels_select`/`list_my_channels`, non-idempotent DELETE endpoints,
`supabase/config.toml`'s overlap with `DEV_SETUP.md`'s own local-database path, a migration
filename that sorts out of apply order, a stale `Revises:` docstring, a dead grant on
`channels`) are deliberately not addressed here - several want an explicit product decision
(the admin-branch scope, whether to keep the Supabase CLI path at all) rather than a
unilateral fix.

### #105 - The Realtime debounce coalesced a burst down to only its last payload

**S2 · FIXED · web · `apps/web/lib/hooks/use-org-realtime.ts`**

`useOrgRealtime`'s debounce reset a single timeout on every event and, when it fired, handed
the callback only the payload from whichever event arrived last. Two call sites filter on
that payload (`chat-shell.tsx`'s `messages`/`channel_members` subscriptions): a message
landing in channel A and one in channel B within the same 300ms window meant only B's payload
survived, so A's message was never refetched until a channel switch or reload. Debouncing the
refetch and filtering by payload are each fine in isolation; combined, the filter silently
discarded whichever event didn't win the race - the normal case, not an edge case, in a busy
organisation.

**Fix.** The debounce now accumulates every payload it coalesces into an array and clears it
only when the timer actually fires, so the callback receives the whole burst rather than its
last member - still one refetch per burst, but zero events dropped. Both consuming call sites
in `chat-shell.tsx` (`channel_members`, `messages`) were updated to check the whole batch
(`payloads.some(...)`) rather than a single payload; the three call sites that ignore the
payload entirely (`use-chat-unread.ts`, `app-store.tsx`, `organisation/page.tsx`) needed no
change - a `() => void` callback is assignable wherever the array-typed one is expected.

**Verified.** `tsc --noEmit` clean across all six call sites. Not covered by an automated
test - simulating a genuine sub-300ms two-channel Realtime burst deterministically wasn't
attempted; the fix was verified by inspection of the corrected coalescing logic instead.

### #106 - No `replica identity full` on the three chat tables

**S2 · FIXED · database · `apps/api/alembic/versions/202608100000_team_chat_channels_and_messages.py`**

The migration adds `channels`/`channel_members`/`messages` to `supabase_realtime` but never
sets replica identity - the one line `202608101000_escalations_realtime.py` already sets
defensively, and that migration's own docstring says why: Supabase's docs note RLS cannot be
applied to a DELETE event at all without it. Escalations set it for a delete path that
doesn't exist; chat has one - `channel_members` rows are deleted on leave/removal and
subscribed with `event: '*'`. Without the full row, a DELETE's `old` record ships primary-key
columns only (`org_id` isn't part of any of these three tables' primary key), so being
removed from a channel - or leaving in another tab - never propagated live, and the
`org_id=eq.<org>` Realtime filter couldn't match the delete's old record either.

**Fix.** `replica identity full` for all three tables, executed right before they're added to
the publication (mirroring escalations' order), with the reverse in `downgrade()`. Edited into
this migration directly rather than shipped as a follow-up - this table set is brand new to
every environment beyond this developer's own local one, so there is nothing anywhere to
migrate *through*, only the corrected end state to ship, the same reasoning the migration's
own docstring already gives for consolidating five earlier migrations into it in the first
place.

**Verified.** New regression test `test_chat_tables_have_full_replica_identity` asserts
`pg_class.relreplident = 'f'` for all three tables directly - confirmed to fail before the
migration change, pass after. Applied directly to the local dev database (`alter table ...
replica identity full`) rather than a destructive downgrade/upgrade cycle, so existing seeded
conversations were preserved. Full backend suite: 274 passed (272 + this + #107's test),
`ruff` clean, single alembic head.

### #107 - `messages_insert` had no `org_id` check `channel_members_insert` already had

**S2 · FIXED · database · `apps/api/alembic/versions/202608100000_team_chat_channels_and_messages.py`**

`channel_members_insert` ends with `and org_id = public.channel_org_id(channel_id)`;
`messages_insert` never constrained `messages.org_id` at all. Reachable without PostgREST: a
user who belongs to both organisation A and organisation B, seated in a channel that belongs
to A, sends with an active-org header of B. `sender_id`/`is_channel_member`/`is_org_member`
all pass - none of them look at the `org_id` column being written - and the row lands with
`org_id = B`. No read leak (`messages_select` keys off membership, not `org_id`), but the row
becomes invisible to every recipient's own `org_id=eq.A` Realtime filter - the message goes
undelivered live for the whole channel - and `messages.org_id` stops being trustworthy for
anything downstream that assumes it agrees with its own `channel_id`.

**Fix.** Added the identical clause - `and org_id = public.channel_org_id(channel_id)` - to
`messages_insert`'s `WITH CHECK`, in the same migration (see `#106`'s note on why editing it
directly is correct here, unlike a migration that has already shipped elsewhere).

**Verified.** New regression test `test_messages_insert_rejects_a_mismatched_org_id_from_a_multi_org_member`
seats one tenant in both organisations, confirms the exact scenario above (`send_message`
called with the channel's own org and a different, mismatched `org_id`) is rejected and
leaves no row - confirmed to fail against the pre-fix policy, pass after. Full backend suite:
274 passed, `ruff` clean.

### #108 - `.gitignore`'s `supabase` entry was un-anchored

**S3 · FIXED · web · `.gitignore`**

An un-anchored `supabase` line matched any path segment named `supabase` anywhere in the
repository, confirmed with `git check-ignore` against `apps/web/lib/supabase/newfile.ts`. The
four files already there stayed tracked (an ignore rule doesn't retroactively untrack
anything), so nothing broke today - but the next file added to the browser/server Supabase
clients would have been silently ignored. It also lacked a trailing newline and duplicated,
imprecisely, what `supabase/.gitignore` (this same PR's own addition) already excludes
precisely: `.branches` and `.temp`, relative to that nested file.

**Fix.** Removed the redundant, incorrectly-scoped root-level line entirely rather than
re-anchoring it to `/supabase/` - the nested `supabase/.gitignore` already handles the actual
exclusion correctly, and a root-level `/supabase/` would additionally ignore any future
top-level file added under `supabase/` (a seed file, say), which is a product decision (see
`ISSUES.md` #106's neighbour, the "should fix" note on `supabase/config.toml` itself) rather
than something this fix should decide unilaterally.

**Verified.** `git check-ignore -v apps/web/lib/supabase/newfile.ts` no longer matches;
`git check-ignore -v supabase/.branches/_current_branch` and `.../temp/...` still correctly
match via the nested `supabase/.gitignore`, confirming no loss of the intended exclusion.
Trailing newline confirmed via a byte-level check of the file's tail.

**Depends on / Blocks:** none - independent of #105-#107, filed together as the same review's
findings.

## Iteration 39 - 2026-08-16 · chat unusable on dev: a cached static shell froze `channelId` forever

### #109 - `/app/chat` served a cached, frozen shell to every visitor - opening any conversation hung on the loader permanently

**S1 · FIXED · web · `apps/web/app/(app)/app/chat/page.tsx`**

Reported live: after deploying to `dev`, every conversation opened into the `WavesLoader` (`#105`-`#108`'s own iteration) and never resolved - confirmed stuck past 20 seconds against the real deployment (Playwright, `jatinorg@yopmail.com`), even though the network log showed `GET /api/v1/channels/{id}` and `GET .../messages` both returning `200` with well-formed bodies and zero console errors. A local production build (`next build && next start`, not `next dev`) of the identical code resolved in under a second - so the bug wasn't in the React logic, the API, or "dev vs prod build" as such.

The actual difference: `curl`/Playwright response headers on `/app/chat` itself showed `x-nextjs-cache: HIT`, `x-nextjs-prerender: 1`, `x-nextjs-stale-time: 300`, and `x-nextjs-postponed: 2` on the streamed RSC payload. `ChatShell` reads the open conversation via a `useSearchParams()` call (isolated in a stateless `ChannelIdSync` leaf per `#103`'s fix, under its own `<Suspense>` boundary, which Next.js requires for `useSearchParams()`). That exact shape - a `Suspense` boundary around a `useSearchParams()` read, on an otherwise-static page (`○` in the build output, true of every `/app/*` page since none does server-side data fetching) - is what Next.js treats as one static, cacheable "shell" with a dynamic "hole" to resume per request. On `dev`'s deployed pm2 process, that shell got cached once - `channelId` frozen at whatever it read on the very first request that built it (effectively `null`, before `ChannelIdSync`'s effect ever ran) - and served to every subsequent visitor for the page's 300s stale window, regardless of the real URL each of them actually requested. `cf-cache-status: DYNAMIC` on the same response rules out Cloudflare's edge cache as a second layer to purge - this was entirely Next.js's own server-side route cache, on the origin.

**Impact.** Every conversation, for every user, on `dev`, hung on the loading state permanently - not an edge case, the whole feature.

**Fix.** `export const dynamic = 'force-dynamic'` on `chat/page.tsx`, which required first turning it back into a Server Component (dropping `'use client'`, since route segment config isn't available from a Client Component file) that renders `ChatShell` as a child - matching the split `#103` already introduced for the same reason. Forces this route to render fresh every request; costs nothing in practice, since the entire page's real content is a client component with no server-rendered data to reuse anyway. Confirmed in the build output: `/app/chat` moved from `○` (Static) to `ƒ` (Dynamic).

**The same shape exists in three other pages already in this codebase, pre-existing, not introduced by this work**: `app/(app)/app/organisation/page.tsx`, `app/(app)/app/runs/new/page.tsx`, and `app/(auth)/login/page.tsx` all wrap a `useSearchParams()` read in `Suspense` on a page the build marks `○` Static, with no `force-dynamic`. None is fixed here - each reads a narrower value (a redirect target, an invite token, a prefilled campaign id) than chat's does, so a frozen shell there likely misroutes or drops a prefill rather than hanging the whole page, but the mechanism is identical and worth a deliberate look rather than a silent fix bundled into this one.

**Verified.** Reproduced live against the real `dev` deployment (stuck past 20s, `.loader-bar` present, composer never rendered). Reproduced the *absence* of the bug locally under `next build && next start` (resolved in ~1s) before the fix, confirming it wasn't a build-mode difference. After the fix: `npm run build` shows `ƒ /app/chat`; `tsc --noEmit` and `eslint` both clean. Not re-verified against the live `dev` deployment after the fix - that requires an actual redeploy, which is the user's next step, not something done from here.

## Iteration 40 - 2026-08-17 · no email works locally: invitations never had the key, password reset never had a transport

### #118 - `RESEND_API_KEY` set in the repo-root `.env` never reached the API container, so every local invitation failed

**S3 · FIXED · infra + backend · `docker/docker-compose.yml`, `docker/.env.example`, `apps/api/app/core/config.py`**

Reported live: inviting a teammate on the local stack returned *"No Resend API key is set - RESEND_API_KEY must be configured before invitations can be sent."* The key was in fact configured - `RESEND_API_KEY` and `RESEND_FROM_EMAIL` were both set in the **repo-root** `.env`, which is the file a developer naturally opens.

Two independent gaps, either one sufficient to break it:

1. **Compose never reads the repo-root `.env`.** `scripts/local.js` runs `docker compose` against `docker/docker-compose.yml`, so variable interpolation resolves from `docker/.env` (created from `docker/.env.example` on first run). Neither file mentioned `RESEND_*` at all. The repo-root `.env` is read by Alembic and the `npm run db:*` scripts, not by compose - the two files look interchangeable and are not.
2. **The `api` service declares an explicit `environment:` map with no `env_file:`.** Even with the variables present in `docker/.env`, nothing forwarded them into the container - the list ends at `CALLFLOW_ALLOWLIST` / `CALLFLOW_LOG_FORMAT`.

The error message itself was correct and honest throughout (non-negotiable #9 - `EmailGateway` refuses rather than pretending to send); it named a real missing value. It just could not say *which* of two `.env` files it wanted.

**Impact.** Developer-facing, local stack only. Invitations are the one feature that depends on Resend, and they were unreachable on every fresh local checkout. Deployed environments are unaffected: pm2 inherits the shell environment, which is populated from the repo-root `.env`.

**Fix.** `RESEND_API_KEY` / `RESEND_FROM_EMAIL` added to the `api` service's `environment:` map and to `docker/.env.example`, the latter documented in the same "optional, blank still works" shape LiveKit already uses, with an explicit note that this file - not the repo-root one - is what compose reads.

Adding them surfaced a third, wider problem worth fixing at the source rather than in compose: `config.resend_from_email` used `os.getenv("RESEND_FROM_EMAIL", "<default>")`, and a `getenv` default only applies when the variable is **absent**. Compose (and pm2, and CI) pass a declared-but-unset variable through as an empty string, which would have beaten the default and sent `from: ""` to Resend. Changed to `os.getenv(...) or "<default>"`, which fixes it for every caller at once instead of duplicating the default string into `docker-compose.yml`.

**Verified.** `docker compose exec api python -c "from app.core.config import config; ..."` reports `resend_api_key` length 36 (`re_` prefix) and the expected `resend_from_email` inside the running container. `ruff check app tests --ignore EXE002` clean; `pytest tests/test_email.py tests/test_config.py` 10 passed. **Not verified end to end** - confirming an invitation actually arrives means sending real mail to a real address, which was left to the reporter rather than done from here.

**Note on running the checks in-container:** `ruff check app tests` reports `EXE002` on all 101 files, and `pytest` fails with `ModuleNotFoundError: No module named 'app'`. Both are artifacts of the Windows bind mount, not the code - every file appears mode 755 to Linux, and `app` resolves via the working directory rather than an installed package, which `python` honours and `pytest` does not. Use `--ignore EXE002` and `-e PYTHONPATH=/app/apps/api` respectively. Neither is fixed here.

### #119 - password reset silently sent nothing: GoTrue had no SMTP transport, and its links pointed at a path Kong does not route

**S2 · FIXED · infra · `docker/docker-compose.yml`, `docker/.env.example`**

Reported live: no password-reset email ever arrives on the local stack. The frontend is genuinely wired - `requestPasswordReset()` really calls `supabase.auth.resetPasswordForEmail` (`apps/web/lib/auth/actions.ts:56`) - and the failure is invisible from every surface a developer would check.

Two defects, stacked, the second hidden behind the first:

1. **No mail transport.** The `auth` service declared no `GOTRUE_SMTP_*` at all and the stack had no mail catcher. GoTrue with an empty SMTP host does not refuse and does not warn - it mints the recovery token, writes `recovery_sent_at`, returns `200 {}`, and discards the message. Verified directly: `POST /auth/v1/recover` returned `200`, `select count(*) from auth.users where recovery_sent_at > now() - interval '5 minutes'` returned `2`, and `docker compose logs auth` contained not one mail-related line. Every layer reports success; the mail simply never exists.
2. **The emailed link 404s.** GoTrue defaults `GOTRUE_MAILER_URLPATHS_*` to `/verify` and builds links as `API_EXTERNAL_URL + path` - but it sits behind Kong, which routes it at `/auth/v1/*`. Verified against the running gateway: `/verify` → `404` (no Kong route), `/auth/v1/verify` → `400` (reached GoTrue, rejected the empty token). So even once mail flowed, every link in it was dead. This one was only reachable *after* fixing #1, which is why it had never been observed.

**Impact.** Password reset was completely non-functional locally, in the way that costs the most time: the UI shows the correct "check your inbox" state, the API returns 200, the database records that a mail was sent, and nothing is wrong anywhere you would look. Deployed environments configure SMTP on the Supabase project and are unaffected by #1; **#2 is worth checking there**, since the same `MAILER_URLPATHS` default applies to any self-hosted GoTrue behind a gateway - not verified from here.

**Fix.** A `mailpit` container (`axllent/mailpit:v1.21`, UI on `${MAILPIT_PORT:-54324}`) now catches every auth email locally, and the `auth` service reads `GOTRUE_SMTP_*` from a `SMTP_*` block in `docker/.env` that defaults to it. Defaults live in the compose file as `${SMTP_HOST:-mailpit}` and friends, so an existing `docker/.env` from before this change works untouched; pointing the block at `smtp.resend.com` sends for real without a second code path. `GOTRUE_SMTP_ADMIN_EMAIL` is deliberately a bare address rather than `RESEND_FROM_EMAIL`, which carries a `Name <addr>` form GoTrue rejects. All four `GOTRUE_MAILER_URLPATHS_*` are set to `/auth/v1/verify`, not just recovery - they share the endpoint and each would have broken identically.

`GOTRUE_MAILER_AUTOCONFIRM` stays `true`: it governs signup confirmation, not recovery, and dropping it would cost the "one command to a working login" property for no gain here.

**Verified.** Full round trip against the running stack: `POST /auth/v1/recover?redirect_to=http://localhost:3000/reset-password` → `200`; mailpit holds one message, subject *"Reset Your Password"*, from `noreply@callflow-ai.local`; following the link in it → `303` to `http://localhost:3000/reset-password` with `access_token`, `refresh_token`, `expires_at`, `token_type` and `type` in the fragment - which is what the browser client consumes to establish the session `updatePassword()` needs. The final in-browser password change was not driven from here.

## Iteration 41 - 2026-08-17 · Realtime has never worked locally: three independent breaks between the browser and the WAL

### #120 - chat never updated live - Supabase Realtime was broken at three separate layers, each hidden behind the one in front of it

**S2 · FIXED · infra · `docker/docker-compose.yml`, `docker/volumes/kong.yml`, `docker/volumes/db/02-schemas.sql`**

Reported live: messages don't arrive and the history doesn't refresh while the chat stays open - you have to reload. The frontend is not at fault and was not changed: `chat-shell.tsx` and `use-chat-unread.ts` already subscribe through `useOrgRealtime`, which is a correct `postgres_changes` subscription. Nothing on the path from Postgres to that hook worked, and it appears **no Realtime feature has ever worked in this stack** - escalations and share requests (`SYSTEM.md` F27) ride the same hook and were equally dead, they just have no second-by-second expectation attached to notice it.

Three defects in series. Each had to be fixed before the next became visible, which is why none had been diagnosed:

1. **Kong rejected every API key on the Realtime route (401).** `kong.yml` declares its consumers with `key: $SUPABASE_ANON_KEY`, but Kong 2.8 does **not** interpolate environment variables in a declarative config, and the kong service had neither those variables nor the templating entrypoint upstream Supabase uses. So the stored credential was the literal 18-character string `$SUPABASE_ANON_KEY`. Proven rather than inferred: authenticating with the literal placeholder as the apikey moved the response from `401` to `403`, i.e. Kong accepted it and proxied. `/rest/v1/` (PostgREST) shares the same key-auth and was broken identically; nothing in the product calls it today, which is why only chat surfaced this.
2. **Realtime rejected the tenant (403).** Realtime is multi-tenant even self-hosted and takes the tenant's `external_id` from the first label of the Host header. `SEED_SELF_HOST` seeds exactly one tenant, `realtime-dev`, but `kong.yml` pointed at `http://realtime:4000`, so Kong forwarded `Host: realtime:4000` and Realtime looked up a tenant named `realtime`: `TenantNotFound`. Upstream Supabase avoids this by naming the container `realtime-dev.supabase-realtime`; this stack names it `callflow-realtime`.
3. **The `realtime` schema did not exist, so no subscription could be registered.** `02-schemas.sql` created `_realtime` (tenant metadata) but not `realtime` (the per-tenant CDC tables). Realtime's own tenant migrations create `realtime.subscription` and the `realtime.messages` partitions but **not the schema that holds them**, so they died on "Could not create schema migrations table" and every subscribe returned `RealtimeSubscriptionError: relation "realtime.subscription" does not exist`. Upstream creates the schema in a `realtime.sql` init script this stack does not use. The tell was that `pg_replication_slots` was empty even with a socket open and `SUBSCRIBED` reported to the client - the WAL was never being read at all.

**Impact.** Every live-updating surface in the product was silently static locally: team chat, the chat unread badge, escalations, share requests. The failure is entirely invisible from the app - `subscribe()` reports `SUBSCRIBED`, the socket stays open, and no error reaches the UI - so it reads as "chat is a bit slow" rather than as a broken subsystem. **Deployed environments use hosted Supabase, where all three of these are the provider's concern, so this is local-only** - but it also means no deployed environment has ever exercised the local path.

**Fix.** (1) `SUPABASE_ANON_KEY`/`SUPABASE_SERVICE_KEY` added to the kong service, with an entrypoint that `sed`s exactly those two placeholders into `kong.yml` before Kong starts. Deliberately not upstream's `eval "echo \"$(cat …)\""`: this `kong.yml` carries prose comments containing backticks, which `eval` would execute as command substitution. Keys stay a template, so `npm run local:keys` needs no edit here. (2) A `realtime-dev` network alias on the realtime service, with `kong.yml` pointing at it, so the forwarded Host resolves to the seeded tenant. (3) `create schema if not exists realtime authorization supabase_admin` in `02-schemas.sql`.

**Existing databases need one manual step.** `02-schemas.sql` runs only on an empty data directory, so a stack created before this change still has no `realtime` schema after pulling. Either `npm run local:reset -- --yes` (drops the volume, replays init) or create the schema in place and restart the realtime container - both spelled out in `DEV_SETUP.md`'s troubleshooting table. Fixes (1) and (2) need only a container recreate.

**Verified.** End to end against the running stack, with a probe subscribing exactly as the app does - authenticated user JWT, `postgres_changes` on `messages`, `filter: org_id=eq.<org>`. Before: `CHANNEL_ERROR - transport failure`. After all three: `STATUS SUBSCRIBED`, then a row inserted straight into `messages` via psql produced `EVENT INSERT` at the subscriber, with `supabase_realtime_replication_slot_` and `supabase_realtime_messages_replication_slot_` both present and `active=true`. Probe script and its two test rows were removed afterwards. Not driven through an actual browser - the two open-tab checks are the reporter's to make.

### #121 - some Realtime joins are rejected with `invalid column for filter org_id` during a page-load burst - not reproduced, not fixed

**S3 · OPEN · infra + web · `apps/web/lib/hooks/use-org-realtime.ts`, Realtime's `realtime.subscription_check_filters()`**

Found while verifying #120. With all three of that issue's fixes in place and live updates demonstrably working, Realtime still rejects a minority of subscription attempts:

```
RealtimeSubscriptionError: [event: *, filter: org_id=eq.<org>, schema: public, table: messages].
Exception: ERROR P0001 (raise_exception) invalid column for filter org_id
```

It is **partial and transient, not a steady failure**. One browser reload produced 18 accepted subscriptions and 14 rejections interleaved within the same nine seconds, then isolated single rejections 8 and 3 minutes later. The affected user still sees live messages, because enough of the duplicate channels survive.

`invalid column` is raised by Realtime's own `subscription_check_filters()` trigger when its `col_names` array comes back empty - it builds that from `information_schema.columns`, which is privilege-filtered per role (`authenticated` sees all 8 columns of `public.messages`; `anon` sees 0).

**Hypotheses tested and falsified**, all from a Node client using the same client library, filter and table as the app:

- *Caller role* - subscribing with an explicit `role: anon` token succeeds, so Realtime is not applying the subscriber's role when it inserts the subscription; the trigger always sees all 8 columns. Rules out the privilege-filtering explanation despite it fitting the error text.
- *Concurrency* - 12 simultaneous joins across three tables from one client: 12/12 accepted.
- *Per-user / per-table* - tokens for a user with no existing subscriptions, and each of the affected tables individually, all succeed.

Every controlled attempt succeeds, so the trigger condition is still unknown and is likely specific to what the browser sends or to the join/leave churn around it.

**A likely contributing factor, worth fixing regardless.** A signed-in user on `/app/chat` opens **seven** subscriptions: `chat-shell.tsx` takes `channels`, `channel_members` and `messages`, `use-chat-unread.ts` takes *the same three again* for the nav badge, and `app-store.tsx` adds `escalations`. `useOrgRealtime` deliberately gives each call site its own channel via `useId()` (see its own docstring - sharing one throws on the second `.on()`), so the duplication is by design. Under `next dev`'s StrictMode double-mount that becomes ~14 join attempts per page load, which is the burst the rejections cluster in. Collapsing the three duplicated tables to one subscription each, fanned out to both consumers, would roughly halve the churn - and is worth doing on its own merits.

**Impact.** Currently cosmetic: enough channels survive that live updates work, and a rejected channel is retried. It matters because it is unexplained, it makes the Realtime logs noisy enough to hide a real fault, and a future page that subscribes to only one table has no spare channel to fall back on.

**Not attempted.** Reading what the failing browser actually sends over the websocket, which is the obvious next step and needs its devtools rather than server-side logs.

## Iteration 42 - 2026-08-17 · dev stuck on a loader: nothing between the browser and the pool had a timeout, and no deploy had landed in 20 hours

### #122 - a stalled request rendered as a permanent loader, because nothing on the path from `fetch()` to `pool.acquire()` had a timeout

**S2 · FIXED · web + backend · `apps/web/lib/api.ts`, `apps/api/app/database/session.py`, `apps/api/app/main.py`**

Reported live on **deployed dev**: opening a conversation sits on the loader indefinitely. Whatever the underlying stall is, the reason it presents as an unkillable spinner rather than an error is that there were **two** places with no time bound, in series:

1. `lib/api.ts`'s `req()` - the single choke point every call in the app goes through - called `fetch()` with no `signal`. `fetch()` has no default timeout, so a server that accepts a connection and then never replies leaves the promise pending forever. Every loader in the product is driven by one of these promises.
2. `Database.as_user()`/`anonymous()` called `pool.acquire()` with no `timeout`. **asyncpg does not time out an acquire unless asked**, so once all `db_pool_max` (10) connections are checked out, every further request waits forever. `command_timeout=30` bounds a *query* but cannot bound the wait for a connection to run it on.

So a saturated pool produced requests that never answered, never errored, never logged, and never showed a status code - invisible from every angle, and indistinguishable from "the page is a bit slow".

**Impact.** Any transient backend stall became a permanent, silent, un-retryable UI state. Also the reason "it's the connection pool" was a plausible-but-unverifiable theory rather than something anyone could read off a dashboard - there was no measurement to confirm or refute it.

**Fix.** Three parts, all about making the failure *visible* rather than guessing at its cause:

- `req()` now passes `AbortSignal.timeout(45s)`, and distinguishes a timeout from a connection failure - "accepted the request but never answered" is different advice from "check your connection". 45s sits well above the API's own 30s query ceiling, so a genuinely slow query still returns its real error instead of being cut off by the client.
- `Database._acquire()` wraps every borrow with `config.db_acquire_timeout` (10s, `DB_ACQUIRE_TIMEOUT_SECONDS`) and raises `DatabasePoolBusy`, which `main.py` answers as a 503 with `Retry-After`. Fails closed and says which limit was hit, per non-negotiable #2.
- Observability, which is the part that actually settles the argument: `Database.stats()` reports size/free/max, `/api/health` exposes it, an acquire slower than 1s logs a warning, and exhaustion logs an error with occupancy attached. `pool_free: 0` under load is now a thing you can read rather than infer.

**Deliberately not done: halving the two pool acquisitions per request.** Every authenticated request takes two sequentially - `dependencies.py`'s auth lookup, then the handler's own - so a pool of 10 serves ~5 concurrent requests. Folding them into one request-scoped connection is a real optimisation, but it restructures the RLS-critical path for a bottleneck **nobody has yet measured**, and `DB_POOL_MAX` is already an environment variable. The observability above is precisely what tells us whether it is needed; the order should be measure, then raise the cheap lever, then restructure only if that is not enough.

**Verified.** Six tests in `tests/test_pool_timeout.py` cover the bounded wait, the timeout actually being handed to the pool (the regression that matters), release on both the success and the exception path, and empty stats before startup. The stub honours asyncpg's `timeout=` contract by raising rather than sleeping past it - an earlier version slept instead and tested nothing, which the tests caught. Backend suite 363 passed against a 357 baseline (+6, same 1 pre-existing failure and 141 pre-existing errors); `ruff` clean; `tsc` clean outside generated `.next` output; `eslint` clean on the changed file.

**This does not explain the dev stall itself** - only why it was invisible. Diagnosing the stall needs dev's own logs and `/api/health` occupancy once #123 lets a deploy land.

### #123 - every deploy to dev has failed for 20 hours: its database is stamped at an Alembic revision that exists nowhere in this repository

**S1 · OPEN · infra · CI/CD `Migrate dev`**

`Migrate dev` fails, which fails the whole pipeline, so **no deploy has reached dev since 2026-08-16 12:39**:

```
FAILED: Can't locate revision identified by 'e5b9c4d26f31'
```

Dev's `alembic_version` points at `e5b9c4d26f31`. That revision **has never existed in this repository** - `git log --all -S 'e5b9c4d26f31'` finds it in no branch, no commit, and no deleted file, after a full `git fetch --all`. The repo's own chain is healthy: linear, single head `c8e1f4a29b76`.

**Cause.** A developer pointed their local checkout at the shared dev database and ran `alembic upgrade head` from a branch that was never pushed. The database advanced; the repository did not.

**Impact.** S1 not because of what it breaks in the product but because of what it hides: dev silently serves 20-hour-old code while everyone assumes their merges are live. Every fix appears not to work, which is how an afternoon disappears - and it is the reason the chat stall could not be investigated on the environment reporting it.

**Fix.** Merging the branch that owns that revision restores it, provided its `down_revision` chains onto `c8e1f4a29b76`. If it was cut before that revision, the merge produces two heads and `upgrade head` fails differently but just as fatally - `alembic heads` must print exactly one before merging.

**The process gap is the real issue and is not fixed here.** Nothing stops a local machine migrating the shared dev database, so this recurs the moment someone else tests that way. Worth either a guard in `scripts/db.js` that refuses a non-local `DATABASE_URL` without an explicit override, or a dev database per developer.

### #124 - a conversation stuck on its loader forever, after both of its requests returned 200

**S2 · FIXED · web · `apps/web/app/(app)/app/chat/chat-shell.tsx`**

Reported on deployed dev: opening a conversation shows the loader and never resolves. The network tab settled it - **nothing failed**. `GET /channels/{id}` returned `200` in 722ms, `GET /channels/{id}/messages?limit=50` returned `200` in 661ms, `channels`, `members`, `unread-count` and `organisations` all `200`, the Realtime websocket reached `101`, and `read` returned `204`. No 5xx, no timeout, no pending request. The data arrived; the component never rendered it.

Both effects that load the open conversation guarded their responses with an effect-scoped `cancelled` flag:

```ts
const rows = await api.listMessages(id, { limit: MESSAGE_PAGE_SIZE });
if (cancelled) return;              // <- discards a good 200
setView({ channelId: id, messages: rows, loading: false, ... });
```

`loading` is set to `true` during render whenever the open channel changes, and **only the resolve and reject paths ever set it back**. So a cleanup running between request and response - which is what a re-render does - threw away a successful result and left `loading: true` with no path back to false. Same shape in the channel-detail effect and its `status: 'loading'`, which is why the header and composer were missing too, not just the message list.

Silent by construction: no error, no toast, no console output, and a green network tab. The `cancelled` guard is an *effect-lifecycle* signal being used to protect *data correctness*, and the two are not the same thing.

**Impact.** Chat unusable on dev whenever a re-render landed inside that ~700ms window. It presented as "the API is slow" or "the connection pool is exhausted" - both false, and both expensive to chase, because every measurement of the backend came back healthy.

**Fix.** Guard by value, not by lifecycle: `setView(current => current.channelId === id ? … : current)`, which is what the error path already did. That keeps the protection that actually mattered - a slow response for a channel the reader has navigated away from is still ignored - while making it impossible for effect lifecycle to strand the flag. `markChannelRead` and the error toast stay behind an effect-scoped flag, since those are side effects rather than state and genuinely should not fire for an abandoned conversation.

**Not fixed here, and a likely reason the window was hit so often:** `/api/v1/me` is requested **15+ times per page load** on dev, alongside repeats of `organisations`, `members` and `campaigns` - 128-140 requests taking 32.9s to settle. `useSession()` is called independently by several components, each with its own effect and its own `supabase.auth.onAuthStateChange` subscription, so a single auth event multiplies into one `me` request per consumer. It belongs in one shared context rather than per-consumer state. Worth its own change: it is wasteful on its own terms, and it is the churn that made this race fire reliably.

**Verified.** `tsc` clean on the changed file, `eslint` clean. Not reproduced end-to-end from here: the failure needs a production build under that re-render load, and the fix removes the state in which it can occur rather than depending on the timing.

### #125 - a 500ms anti-flicker floor could stay raised forever, and it gated the entire conversation panel

**S2 · FIXED · web · `apps/web/app/(app)/app/chat/chat-shell.tsx`**

Follow-up to #124, which fixed a real bug but not the one on screen. The loader visible on dev is the **fallback branch** - a bare `<Panel><WavesLoader/></Panel>` with no header and no composer - reached when this fails:

```tsx
) : selectedChannel && !showChannelLoader ? (
```

`#124` had targeted `view.loading`, which drives a *different* loader nested **inside** a panel that was never rendering. Fixing it changed nothing visible, which is the cost of fixing a mechanism instead of the one on the screen.

Two defects here, and either alone is enough:

1. **`useMinVisible` could never lift its floor.** It set `holding` during render whenever `active && !holding`, and cleared it from a timer keyed on `holding`. While `active` stayed true those fought each other indefinitely: the timer cleared the flag, the next render set it straight back, the effect re-ran and armed another timer. So the component re-rendered every `minMs` for as long as anything was loading, and `showChannelLoader` never went false. That perpetual re-render is also a strong candidate for the request storm seen alongside it - `/api/v1/me` fetched 15+ times per page load, 128-140 requests, 32.9s to settle.
2. **A cosmetic timer decided whether content existed.** `!showChannelLoader` gated the whole conversation - header, message list, composer. An anti-flicker floor is presentation; letting it decide whether the panel renders turns any way of holding it up into "the conversation never opens".

**Impact.** A conversation that never opens, with every request returning 200. The failure looks like a backend fault from every angle a developer would check - which is exactly how it consumed a day and had the API, the connection pool and Supabase each blamed and cleared in turn.

**Fix.** Three parts, in order of how much they matter:

- The panel is gated on `selectedChannel` alone. A loading floor may delay content *inside* a panel; it must never decide whether the panel renders.
- `useMinVisible` winds down only once `active` is false, so nothing changes while it is still true and the oscillation is gone. `Date.now()` moved out of the render body, where it was impure.
- A conversation still loading after 20s now renders "This conversation didn't open" with a **Try again**, via a new `useStalled`. A loader says "wait"; it cannot say "this is not going to finish", and after twenty seconds that is the more honest thing to say. This is the backstop that makes an indefinite spinner impossible regardless of cause.

**Honesty about what is proven.** The oscillation and the gating are both real and demonstrable by reading the code. Whether one of them is *the* trigger for the reported symptom is **not** proven - reproducing it needs a production build under load, and it was not reproduced from here. Four hypotheses were falsified before this one (an `anon`-role token, a join burst, an unstable `toast` identity, and #124's `cancelled` guard), so this is deliberately written as "remove the class of failure" rather than "found the culprit". The 20s backstop is what guarantees the user is never stranded even if the trigger is something else again.

**Verified.** `eslint` clean (including `react-hooks/set-state-in-effect` and `react-hooks/purity`, both of which caught real problems in the first drafts of this fix), `tsc` clean.

## Iteration 43 - 2026-08-17 · an invitee who already had an account was shown a signup form that could not succeed

### #126 - accepting an invitation offered a signup form to people who already have an account

**S2 · FIXED · web + backend · `apps/web/app/(auth)/accept-invite/[token]/page.tsx`, `public.lookup_invitation()`**

Reported live. Someone with an existing CallFlow account, signed out, opens an invitation link:

1. The page offers **"Set a password and you'll join the team"** - a signup form.
2. They fill in name and password and submit.
3. Supabase rejects it: a user with that email already exists, sign in or reset instead.
4. The only way through is to leave the page, sign in by the normal route, and open the link a second time - at which point it works, because the signed-in branch just asks them to accept.

The page branched on **whether the visitor was signed in**, and nothing else. Signed out meant "new person, collect a password", which is wrong for every invitee who already has an account - and inviting an existing user into a second organisation is a completely ordinary thing to do, not an edge case.

**Impact.** Every existing user invited to another organisation hit a dead end that blamed them ("a user with this email already exists") for following the link they were sent. Recoverable only by knowing to sign in first and re-open the link, which nothing on the page said.

**Fix.** `public.lookup_invitation()` gains `account_exists`, so the page can branch on *who the invitee is* rather than only on whether they happen to be signed in already. Signed out now has two branches: an address with an account gets a sign-in form (read-only email, password, "Sign in and join", and a **Forgot your password?** link); an address without one gets the signup form as before. Both accept the invitation immediately after authenticating, so the link works on the first click either way.

The card's own copy follows the branch - "Sign in to join the team" rather than "Set a password" - since promising a password step and then not offering one is its own small lie.

**Not an enumeration surface.** `account_exists` is reachable only through a valid invitation token, which is a secret delivered to that mailbox, and the same response already returns the invited address. There is no way to ask this question about an arbitrary email.

**Verified.** Migration `f4b2c9e17a35` applied locally, single head. The function was exercised directly against the real schema with two invitations - one to an address that has an account, one to an address that does not - asserting `account_exists` is `true` and `false` respectively, with the probe rows deleted afterwards. `ruff` clean, backend suite 381 passed against the same baseline, `eslint` and `tsc` clean.

**No regression test.** The DB-backed tests cannot run locally (`gen_salt` is unavailable - `pgcrypto` sits in `extensions`, off the tests' `search_path`, the same cause behind the 146 pre-existing errors) and CI's API job completes in ~20s, which is too fast to be running them either. Until that environment works, a test here would be written and never executed, so the direct database probe above is the verification of record. Worth fixing the test environment before this area changes again.

### #127 - your role in one organisation decided whether you could leave it

**S2 · FIXED · web · `apps/web/components/layout/app-shell.tsx`, `apps/web/app/(app)/app/chat/chat-shell.tsx`**

Two defects found while auditing whether one organisation's data can reach another.

**1. The org switcher was gated on role, and the gate read the *current* org.**

```tsx
// Switching between organisations ... is an admin/owner concern.
if (!hasRole(profile, 'owner', 'admin')) {  // <- static label, no switcher
```

The reasoning reads sensibly and is wrong in a way that only shows up with mixed roles: someone who owns organisation A and is a *viewer* in B loses the switcher the moment they arrive in B - the control that would take them back is the one being hidden. **They are stranded there**, with no route out short of clearing site data, because the pinned org lives in `localStorage`.

The API never agreed with the gate: `GET /organisations` (`list_mine`) takes a plain `Depends(current_user)` with no permission requirement and has always returned every membership to every member. This was a UI-only restriction, so lifting it needed no backend change.

Membership is what entitles someone to move between organisations; role governs what they can do *inside* one. The condition is now `list.length > 1 || hasRole(profile, 'owner', 'admin')` - the admin half stays only because this menu is also where **New organisation** lives, and a single-org owner still needs it.

**2. An open conversation survived an org switch.**

Chat's channel list and member list both key on `orgId` and refetch on a switch, but the open conversation lives in the `?c=` query param, which does not change - so the right-hand pane went on showing the **previous organisation's conversation and its already-fetched messages** beside a list that had moved on. RLS blocks any new read of that channel, but nothing un-renders what is already on screen. Now the conversation closes when the active org changes: a channel id from another organisation has no meaning in this one, so no selection is the honest result.

**3. The previous organisation's data stayed on screen during the switch.**

Re-fetching on switch is not the same as isolating, and every org-scoped surface got this wrong in the same way. `app-store` and each page replace their state only when the *new* response arrives, so for the length of a request the dashboard showed organisation A's runs, escalations and safety numbers while the switcher already said B. The `catch` branches make it worse: keeping stale data on a failed refresh is right for a refresh of the same organisation and wrong across a switch, where it leaves A's rows up **indefinitely** while you are in B.

Fixed in two places, because they sit either side of the provider boundary:

- `AppStoreProvider` clears runs, escalations and safety settings during render the moment the org changes, before anything can render them.
- `AppShell` keys the page subtree on the active org (`<Fragment key={activeOrgId}>`), so **every page remounts** on a switch and every `useState` in it returns to its initial value. Auditing ten pages would have fixed ten pages; keying the subtree fixes the class, including pages nobody has written yet.

Both key on `useActiveOrg()` rather than `session.profile.active.org_id`, deliberately. That is the same value `useOrgScopedEffect` and the API client's `X-Org-Id` read, so the clear and the re-fetch are driven by one signal in the right order. The session's copy only updates once `/me` returns - *after* the re-fetch - so resetting on it would wipe the new organisation's freshly-loaded data and leave nothing to trigger another load.

Losing scroll position and in-page state on a switch is the correct outcome: you are looking at a different tenant.

**What was checked and found already correct.** Worth recording so the next audit is shorter:

- Every other org-scoped page refetches on switch, via `useOrgScopedEffect` or `useAppStore` (which uses it). `runs/new` and `settings/safety` looked exposed but read through the store; `profile` and `organisation/new` are not org-scoped.
- Locally persisted state is keyed by entity id (`callflow.campaign.settings.<campaignId>`, `callflow.agent.draft.<agentId>`), and a campaign or agent belongs to exactly one organisation, so those cannot bleed. `callflow.campaign.draft` is a one-shot `sessionStorage` handoff, read and removed immediately.
- **Server-side isolation verified directly**, not assumed: with `request.jwt.claims` and `role` set exactly as `database.as_user()` installs them, a user belonging to 2 of the 8 organisations in the database saw 2 organisations, 3 memberships, and **zero rows belonging to an organisation they are not a member of**. RLS is doing its job.

**Impact.** Anyone with different roles across organisations could be trapped in one of them - which for a multi-tenant product is the switch feature not working at all for exactly the people who need it most. The chat leak is narrower but is literally one organisation's content displayed while inside another.

**Verified.** `eslint` 0 errors on both changed files (one pre-existing `<img>` warning elsewhere in `app-shell.tsx`), `tsc` clean, cross-tenant probe above.

### #128 - agent drafts followed you into the next organisation

**S2 · FIXED · web · `apps/web/lib/agent-draft.ts`, `apps/web/lib/hooks/use-active-org.ts`**

Reported live, and a hole in #127's own audit. That entry recorded locally-persisted state as safe because it is "keyed by entity id, and a campaign or agent belongs to exactly one organisation". True only once the entity exists. **A new agent has no id yet**, and every draft key was `callflow.agent.draft.<agentId|new>[.<fingerprint>]` - no organisation anywhere in it.

Two consequences, both reported:

- `listUnsavedAgentDrafts()` scanned a prefix shared by every organisation, so the Drafts tab in organisation B listed work started in A - including the draft of an agent that had already been created in A, whose real card had correctly disappeared on the switch.
- `loadAgentDraft(null)` returned "the newest unsaved draft in this browser" with no organisation filter, so opening **Create agent** in B prefilled the name, prompt, providers and voice last used in A.

**Impact.** One organisation's configuration presented as the starting point for another's, in the one part of the product where a wrong provider or prompt is invisible until a call is placed. It also made #127's isolation guarantee untrue in a place it claimed to have checked.

**Fix.** The organisation is now part of the key: `callflow.agent.draft.v2.<orgId>.<agentId|new>[.<fingerprint>]`. Every read, write, clear and eviction is scoped to one organisation and no-ops when no organisation has resolved yet, rather than guessing.

The `v2` segment exists to make the old keys identifiable: `<orgId>` and `<agentId>` are both UUIDs in the same position, so the two shapes are otherwise indistinguishable. `purgeLegacyAgentDrafts()` deletes everything under the old prefix on the next read - without it those drafts are merely *unreachable* rather than gone, which would leave the reporter's current bleeding drafts sitting in storage forever, and still on screen until a reload.

**Which organisation id.** A new `useScopedOrgId()` prefers the switcher's value (`useActiveOrg()`) and falls back to the session's. Neither alone works: the switcher's is empty until someone switches for the first time, so early drafts would land under a key that becomes unreachable the moment they do; the session's lags a switch, because it only updates once `/me` returns - long enough to read the previous organisation's drafts into a freshly-opened editor. Together they give a real id at all times that moves when the rest of the app moves.

**Checked at the same time:** `campaign-draft.ts` has the same `?? 'default'` shape (`settingsKey(existing?.id ?? '')`) but is **not** affected - `.default` is only ever read, never written, because every save goes through `saveLocalSettings(saved.id, …)` with a real id. So the key never exists and the read falls through to `DEFAULT_SETTINGS`. Left alone rather than changed for symmetry.

**Verified.** `eslint` clean - it caught a real missing `scopedOrgId` dependency on the editor's persist effect - and `tsc` clean.

### #129 - an operator could build an agent and then had no way to remove it

**S2 · FIXED · backend + web · `app/auth/permissions.py`, `voice_agents_delete`, `apps/web/app/(app)/app/agentic/page.tsx`**

Reported live. An operator creates a voice agent and cannot delete it - not someone else's, their own. The only way to remove it was to ask an owner or admin.

Wrong in two independent layers, which is why it was total rather than partial:

| Layer | Before |
| --- | --- |
| `app/auth/permissions.py` | `AGENTS_DELETE` sat in `_ADMIN` only, so the route rejected an operator before RLS was ever consulted |
| `voice_agents_delete` | `has_org_role(org_id, ['owner','admin'])` - no creator branch at all |

Meanwhile `voice_agents_insert` has always allowed an operator. A role that can create something and can never remove it accumulates its own mess and needs someone senior to clean it up.

**Fix.** The two layers now answer two different questions, which is the division the rest of the schema already uses (`channels_update`, `messages_update`):

- `AGENTS_DELETE` moves to `_OPERATOR`, and means "may delete agents **at all**". Viewer still cannot.
- `voice_agents_delete` becomes `has_org_role(org_id, ['owner','admin']) or created_by = public.current_user_id()` - owner or admin may remove any agent in the organisation, everyone else only what they created.

`created_by` has been on the table since `202608151200`, so no backfill: rows written before it existed have `created_by is null` and stay owner/admin-only, which is the safe side.

**The route no longer lies about why.** A delete that removes nothing had one message - `404 Unknown voice agent` - for two very different causes. Since `voice_agents_select` is plain org membership, the caller is usually *looking at* the agent they were just told does not exist. The route now re-reads it: still visible means `403` naming the actual rule ("This agent was created by someone else. You can delete agents you created; an owner or admin can delete any of them"), genuinely absent still means `404`.

**UI.** The Delete control now appears only where it would succeed - `agents:delete` **and** (owner/admin **or** you created it) - rather than on every card for a role that mostly could not use it. The agents list also splits into **Built by you** and **Built by your team** when there is something on both sides, so the agents you can edit and remove are findable without reading every card's "by" line. One group on its own stays ungrouped: a heading over the only section you have is a label, not information.

**Verified at the database level**, not just in the UI. Two real members of one organisation, an agent created by each, acting with `request.jwt.claims` set exactly as `database.as_user()` installs them:

```
operator deletes OWN agent       -> rows deleted: 1
operator deletes ANOTHER's agent -> rows deleted: 0
operator can still SEE that agent -> visible: 1
```

That third line is the one that justifies the 403: the row is readable and undeletable, so "unknown" would have been false. Probe ran inside a transaction and was rolled back.

`test_permissions.py` caught the change, as it should have - the old test asserted an operator *cannot* delete agents. Rewritten to state the new rule and why the two questions are separate, rather than deleted. Backend suite back to its baseline exactly (1 pre-existing failure, 381 passed, 146 pre-existing errors), `ruff`, `eslint` and `tsc` clean.

**Left alone deliberately: `voice_agents_update`.** Any operator may still edit any agent in the organisation, so you can edit a colleague's agent but not delete it. That asymmetry is real and worth a decision, but tightening it would silently break teams who share agents on purpose - it should not ride along inside a delete fix.

## Iteration 44 - 2026-08-17 · scrolling was jittery because every canvas forced a layout sixty times a second

### #130 - the canvas loop measured and reallocated itself every frame

**S3 · FIXED · web · `apps/web/lib/hooks/use-canvas-animation.ts`, `apps/web/components/brand/voice-field.tsx`**

Reported as "scrolling on the Agents page is very jittery". The cause is in the shared canvas driver, so it applied to every animated canvas in the product - the Agents hero, the brand wave, and four marketing sections.

`useCanvasAnimation`'s frame loop opened with `const s = size()`, and `size()` did two of the most expensive things available, sixty times a second:

- `getBoundingClientRect()` - a **forced synchronous layout**. During a scroll, when the browser is already mid-layout, this is the textbook way to produce jank.
- `cv.width = …; cv.height = …` - assigning either **discards the canvas backing store and allocates a new one**, even when the value is unchanged. Plus a `getContext` and a `setTransform` behind it.

None of it was needed per frame. The size only changes when the element changes size, and a `ResizeObserver` was already watching for exactly that - the per-frame call was redundant work, not a safeguard.

On top of that, `VoiceField` called `getComputedStyle(document.documentElement)` once per frame to read `--field-ink` and `--field-gain` - a forced **style** resolution to go with the forced layout.

**Fix.** `size()` now runs on mount and from the `ResizeObserver`, caches the context and dimensions, and only touches `width`/`height` when they actually differ. The frame loop reads the cache and draws. `VoiceField` samples its two tokens at 4Hz instead of 60Hz - neither is animated; the accent follows the theme and the gain dims a whole surface.

**One trap in that sampling, worth recording.** The first version keyed the cache on the frame's own `t`, which restarts at zero for every canvas instance - a second field mounting would have sat on a cache stamped in the first one's future and never resampled. It also would have broken the reduced-motion path, which paints **exactly one frame and never again**: a stale sample there is not a quarter-second of the wrong accent, it is the wrong accent until a reload - precisely the bug the hook's `theme` dependency was added to prevent. Now keyed on `performance.now()`, and forced whenever `reduced` is set.

**Impact.** Two forced layout/style passes per frame per canvas, removed. This was jitter rather than breakage, which is why it survived: nothing errors, the page just never feels settled.

**Verified.** `eslint` 0 errors, `tsc` clean on source. **Not measured** - a before/after frame profile needs a browser, and the reasoning here is structural rather than empirical: forced layout and backing-store reallocation per frame are wrong regardless of what a profile would say. Worth a devtools performance trace on the Agents page to confirm the felt improvement.

### #131 - the wheel picker read `scrollTop` back after writing it, forcing a layout every frame

**S3 · FIXED · web · `apps/web/components/ui/wheel-picker.tsx`**

Reported as "this section is very jittery when I select presets" - the Transcriber / Model / Voice wheels on the agent editor. The "when I select presets" part is the clue: a preset spins **several wheels at once**, each with its own animation loop.

`scrollTop` is a layout property. Writing it invalidates layout; reading it again in the same frame forces the browser to flush that layout synchronously before it can answer. The eased spin did exactly that, twice:

```ts
element.scrollTop = from + distance * eased;                 // write
… (element.scrollTop / ITEM_HEIGHT).toFixed(3)              // read  -> forced layout
const row = Math.round(element.scrollTop / ITEM_HEIGHT);    // read  -> again
```

One wheel is survivable. Four wheels, each running that loop, interleaving writes and reads across the same frame, is layout thrashing - and the value being read back is the value that was just assigned, so none of it bought anything.

The gesture path had a milder version: `recentre()` may write `scrollTop`, and `paintOffset()` plus the index calculation then each read it back.

**Fix.** The animation loop computes the position once into a local and uses it for all three writes. `recentre()` returns where the wheel ended up and `paintOffset()` takes an optional position, so a gesture frame reads `scrollTop` exactly once. The remaining reads are all one-per-animation setup rather than per-frame.

Nothing about the animation's design changed - the hand-driven `scrollTop` write per frame is still right, and the comment explaining why (`snap-mandatory` re-snapping a native smooth scroll) still stands. What changed is that the loop no longer asks the DOM to re-measure what it just set.

**Impact.** Jitter, not breakage, on the one interaction where the product shows off - picking a voice stack. It got worse the more wheels a preset touched, which is why it read as "presets are janky" rather than "the wheel is janky".

**Verified.** `eslint` clean, `tsc` clean on source, page serves. **Not measured** - same caveat as #130: confirming the felt improvement needs a devtools frame profile while selecting a preset, which needs a browser.

### #132 - voice agents were visible to every member, missing the per-creator silo the rest of the product already had

**S2 · FIXED · backend · `voice_agents_select` / `_update` / `_delete` (migration `c9f47a1e6b28`)**

Requested: an operator should have access to their own agents and nobody else's; an admin should see everyone's.

Campaigns, runs and call outcomes were narrowed to exactly that in `202608092000` - "operators see only what they created; owner, admin and viewer keep seeing everything". Voice agents were built afterwards and kept the older flat `is_org_member(org_id)`, so every operator could see every colleague's agent. This is that migration's rule, applied to the table that missed it.

Viewer follows the precedent and keeps seeing everything, which is what makes it the read-only oversight role rather than a weaker operator.

**Three policies moved, not one.** Visibility alone would have been a half-measure:

| Policy | Before | After |
| --- | --- | --- |
| `select` | `is_org_member(org_id)` | owner/admin/viewer see all, everyone else their own |
| `update` | **any** operator, **any** agent in the org | owner/admin any; operator their own |
| `delete` | owner/admin, or `created_by` (from `b6d1e93af472`) | same, plus the role check below |

`update` is the one that mattered. Left as it was, an operator would have been unable to *see* a colleague's agent while still being permitted to overwrite one whose id they happened to hold - visibility narrowed, write surface not. `202608092000` could leave its write policies alone because they were already creator-scoped; this table's were not. It also settles the asymmetry `#129` deliberately left open ("you may edit a colleague's agent but not delete it") - the requirement here decides it rather than a guess.

**Each non-owner branch also requires the `operator` role**, not just a `created_by` match. Without it, someone demoted from operator to viewer would keep write access to agents they had created, because `created_by` does not change when a role does. The API blocks that anyway - viewer holds neither `AGENTS_WRITE` nor `AGENTS_DELETE` - but RLS has to be right on its own (CLAUDE.md §4b). `insert` is unchanged: who may create an agent is a role question and it already answers it.

**Checked before narrowing.** `telephony_provisioning`'s agent existence check reads `voice_agents` through the caller's own RLS connection, and its docstring already leans on `voice_agents_select` for security ("an agent id from another org simply is not there"). Narrowing makes that check stricter, not broken: an operator can now only provision a number for an agent they own, which is the same rule. It is the only other reader; nothing else joins to the table.

**Verified at the database level.** Two real members of one organisation, an agent created by each, claims installed exactly as `database.as_user()` does:

```
OPERATOR sees: silo-mine                      (their own only)
OPERATOR edits another's agent -> rows: 0     (blocked)
OWNER sees:    silo-mine, silo-theirs         (everything)
```

Both probes ran in transactions and were rolled back. `ruff` clean; backend suite at its baseline exactly (1 pre-existing failure, 381 passed, 146 pre-existing errors).

**No frontend change was needed**, which is worth stating rather than assuming: for an operator the "Built by your team" group is now always empty, so `#129`'s split collapses to a single grid on its own, and Delete correctly appears on everything an operator can see.

**Open question, deliberately not answered here.** Nothing tells an operator their view is scoped - they see their own agents and cannot tell whether others exist. Campaigns and runs have behaved this way since `202608092000` with no such copy either, so this follows the precedent rather than inventing a one-off. If it should be said, it should be said on all three surfaces at once.

**Still no regression test**, for the third time in this area: the DB-backed tests cannot run locally (`gen_salt`, `pgcrypto` off the tests' `search_path`) and CI's API job finishes too fast to be running them. A per-creator RLS rule is exactly what a cross-tenant test exists to protect, so the database probe above is the verification of record. **Fixing that test environment should come before the next change here.**

## Iteration 45 - 2026-08-18 · a run could never place a call, and two concepts described one thing

### #133 - the dial path was fully built and never connected

**S1 · FIXED · api · `app/api/v1/routes/runs.py`, `app/services/run_dialer.py`**

`CampaignRunner` accepted `trunk_id` and `voice_agent`, and its own docstrings
said both were "resolved by the caller from the campaign's voice agent". Nothing
resolved them. Grepping the whole of `apps/api` found those kwargs passed in
tests and nowhere else, so every contact hit the guards at `campaign_runner.py`
lines 297 and 316 and was refused with "no connected number" / "no speech or
language providers set" before the phone rang.

**Impact.** Total: no organisation could place a call through the product, and the
failure read as a configuration problem the operator was expected to fix rather
than a missing wire. `telephony_provisioning` had been producing verified LiveKit
outbound trunks the whole time and nothing ever read one back out.

**Fix.** `services/run_dispatch.py` resolves an agent plus the numbers a run
picked into the trunks and decrypted keys the dialer already knew how to use,
failing closed with a message naming what to connect. The dialer itself needed no
new dialling machinery - only a pool where a single trunk used to be.

**Depends on / Blocks:** unblocks every call the product places.

### #134 - a run's numbers had nowhere to live

**S2 · FIXED · db · `alembic/versions/202608180900_agent_driven_runs_replace_campaigns.py`**

`provider_credentials` is uniquely keyed `(org_id, provider)` with a single
`phone_number` column, so an organisation with five Twilio numbers had nowhere to
put four of them. `telephony_provisioning.voice_agent_id` was `NOT NULL`, making
provisioning per-agent - the opposite of "any agent through any carrier".

**Impact.** "Pick one, several, or all of our numbers" was unrepresentable, and an
agent was bound to one number at build time.

**Fix.** ADR-8. `telephony_numbers` is the aggregate, `run_numbers` binds a run to
its lines, and provisioning targets a number. The first draft of the plan stored
the numbers as `runs.from_numbers jsonb`, which was wrong: a number's trunk id and
status are per-number state with their own lifecycle, and denormalising them into
each run means a number verified *after* a run started stays recorded unverified.

### #135 - `required` on a collect field was written and never read

**S2 · FIXED · api · `app/domain/collection.py`, `app/domain/triage.py`**

A field could be marked required, and that value was used exactly once - to build
the schema the model was asked to satisfy. Nothing re-checked the answer against
it, so a call could come back with none of the required fields and still be
recorded `auto_closed` because the status said `completed`.

**Impact.** Silent data loss: the product claimed a call was clean while the thing
it was sent to find out was missing, and nobody was told.

**Fix.** ADR-5's design, followed rather than reinvented - including the placement
its own review corrected. The new triage rule is gated on `status == "completed"`,
so a busy or no-answer call keeps its more actionable "worth retrying" signal
instead of being escalated for fields it never had a chance to collect. The
implementation plan had this rule ranked above `task_completed`, which is the bug
ADR-5 was written to prevent.

`is_present()` treats `False` and `0` as answers: a yes/no field answered "no" was
collected, and a bare falsiness check would send a person to ask something the
contact had already answered.

### #136 - a hostile spreadsheet column stopped colliding, so it stopped being blocked

**S2 · FIXED · api · `app/services/run_dialer.py`, `app/domain/prompt_assembly.py`**

`contact.context` was spread first into the dispatch metadata so a CSV column
named `goal` lost to CallFlow's own `goal` key - a defence that worked by
collision. Renaming that key to `prompt` removed the collision, and a hostile
`goal` column began riding along untouched. Inert today; live again the moment a
future reader adds a `goal` key back.

**Impact.** None yet, which is the point - it was a defence that had quietly
stopped defending, and nothing would have failed to say so.

**Fix.** Reserved keys are stripped from the metadata *and* the prompt, against
one shared list (`prompt_assembly.RESERVED_CONTEXT_KEYS`) so the two cannot
drift. Dropped column *names* are logged, never their values - a discarded column
may hold exactly the PII that must not reach a log line. Pinned by
`test_dispatch_contract.py`, and verified by mutation.

### #137 - four bugs the migration rehearsal caught before dev saw them

**S2 · FIXED · db · same revision**

Running the migration inside a rolled-back transaction against the real schema
found four faults, two of which would have failed silently:

1. `create or replace` cannot change a function's return type, and two of these
   change theirs - including `lookup_run_owner_for_webhook`, on the completion
   hot path. The migration would have aborted mid-flight.
2. The new functions read `runs.voice_agent_id` but name `public.campaigns`, so
   there is exactly one window they can be created in. The first version had them
   first and failed on a column that did not exist yet.
3. The member-removal rewrite silently left `update public.campaigns` in place. A
   `search_path`-pinned `SECURITY DEFINER` function, so it fails when someone
   removes a teammate, not when the migration runs.
4. Supabase's default ACL on `public` grants DELETE to `authenticated` on every
   new table, so granting select/insert/update still left both new tables
   deletable - the same miss `202608161700` already had to correct once.

**Impact.** Prevented. Worth recording because the rehearsal is what found them,
and three of the four would not have shown up in any test.

**Fix.** Applied. The rehearsal pattern - run the real migration in a transaction
against the real schema, assert the end state, roll back - is worth repeating for
anything that touches a `SECURITY DEFINER` function or adds a tenant table.

**Depends on / Blocks:** nothing.

## Iteration 46 - 2026-08-18 · finishing the agent-driven run: collection, upload, and the surfaces that read them

### #138 - every real call was told the appointment was "tomorrow at 4pm"

**S1 · FIXED · web · `apps/web/lib/contacts.ts`**

`toContactInputs()` built each contact's context as a literal:

```ts
context: {
  enquiry_note: r.note || 'no note on file',
  appointment_time: 'tomorrow at 4pm',
}
```

Every contact in every run, live ones included. A fixture written for a demo,
left in the one function that turns uploaded rows into dial payloads. Any agent
prompt referencing `{context[appointment_time]}` stated a time nobody had agreed
to, to a real person, on a real phone call - and the spreadsheet columns someone
actually uploaded were discarded, because only these two keys were ever built.

**Impact.** Real. Not a crash, which is why it survived: the call connected, the
agent spoke fluently, and the sentence it said was false. This is the worst shape
a bug can take in this product - confident, plausible, and wrong to a customer.

**Fix.** Every non-reserved column passes through under its own name, and the
note becomes `detail`, the key `render_call_prompt` reads for "what this call is
about". Nothing is invented. Pinned by `test_spreadsheet.py`'s note/detail tests
and by the composer's context-column summary, which shows the builder exactly
which columns each contact carries before the run starts.

**Depends on / Blocks:** the per-contact context requirement this whole iteration
exists to serve.

### #139 - the escalation directory 500'd on a column the migration had renamed

**S2 · FIXED · api · `app/api/v1/routes/escalations.py`**

`list_escalation_directory()` was rewritten in `202608180900` to return
`agent_name` instead of `campaign_name`. The route still read
`r["campaign_name"]`, so `GET /api/v1/escalations/directory` raised `KeyError`
for every caller - the "Team escalations" panel on the Needs a person page,
which is how an operator offers to help with someone else's frustrated customer.

Notably the *frontend* was already correct: `EscalationDirectoryEntry` declared
`agent_name`. Only the route sat between two halves that agreed with each other.

**Impact.** Real, and invisible to the test suite - the endpoint has no coverage,
and a `KeyError` on an asyncpg `Record` is a runtime failure, not an import one.

**Fix.** The route reads `agent_name`. Found the same way #134-#136 were: by
checking every SQL function's declared return type against the code that reads
it, directly against the live schema rather than against the migration file.

**Depends on / Blocks:** nothing.

### #140 - a valid sheet row was told to add the phone number it already had

**S3 · FIXED · api · `app/domain/spreadsheet.py`**

`validate()` decided between "Add a phone number for this row." and "Not a valid
E.164 number" by looking at the *normalised* number. A cell holding `not a
number` normalises to the empty string exactly as an empty cell does, so a row
where someone had typed something wrong was told to fill in a field they had
already filled in.

Caught by a test written before the code was, which is why it is recorded here
rather than shipping: the message was wrong in the direction that wastes the most
of someone's time, on a row they are looking straight at.

**Impact.** Prevented. The frontend CSV parser never had this bug - it checks the
raw cell - so the two validators would have disagreed about the same row, which
is its own class of problem (a row the browser accepts and the server rejects, or
here, describes differently).

**Fix.** `validate()` takes the raw cell alongside the normalised number and
distinguishes the two cases. The two parsers now produce the same verdict and the
same sentence for the same row.

**Depends on / Blocks:** nothing.

### #141 - a multipart upload cannot be sent with a Content-Type the client sets

**S2 · FIXED · web · `apps/web/lib/api.ts`**

`req()` set `'Content-Type': 'application/json'` on every request unconditionally.
A `FormData` body needs the browser to set its own header, because the multipart
boundary is generated per request and is part of the value - naming the type
without one produces a body the server cannot parse, and the failure surfaces as
a validation error about a missing field rather than as anything about encoding.

**Impact.** Prevented. The `.xlsx` upload would have failed on its first use with
a message pointing at the wrong thing entirely.

**Fix.** The JSON header is omitted when the body is `FormData`. One place, in
the single function every API call goes through, so a future upload cannot
reintroduce it.

**Depends on / Blocks:** #142.

### #142 - "please stop calling me" did not stop the call

**S1 · FIXED · voice-runtime · `app/worker.py`, `app/collection.py`**

The runtime had no tool-calling at all. The agent could say a warm goodbye and
then keep listening, because nothing gave it a way to *act* - `wait_for_call_end`
returned only when the contact disconnected or the ceiling ran out. A person who
asked to be let go stayed on a call they had already ended, until they hung up
themselves.

Three things were missing together, which is why this reads as one entry: no
`end_call` tool, no `record_field` tool, and no way for either to reach the loop
holding the call open.

**Impact.** Real, and the requirement most directly about respecting someone.
Also the reason `collected` was always empty: the worker did not send that key
at all, so the API defaulted it to `{}` regardless of how well the conversation
went, and every call with required fields escalated to a person even when the
agent had heard every answer.

**Fix.** `collection.py` holds the pure half - the field list off metadata, type
coercion, and the `Collector` that records answers and carries a hangup reason.
`worker.py`'s `build_tools()` wraps it as two LLM tools, and `wait_for_call_end`
polls a `should_end` predicate once a second while the call is up, so ending is
immediate rather than deferred to the next turn. Verified by mutation: removing
the poll makes the hangup test hang and fail rather than pass.

An `end_call` reason is first-wins - the thing that made the agent hang up is the
first thing it decided, and a second call while the room is closing would
otherwise rewrite it.

**Depends on / Blocks:** #143.

### #143 - a field the agent invented would have landed on a customer's record

**S2 · FIXED · voice-runtime · `app/collection.py`**

`record_field` accepts a key and a value from the model. Storing whatever arrived
would mean a hallucinated field name - or a real one the organisation never asked
for - persisted onto a call record as though it had been collected deliberately.

**Impact.** Prevented. Recorded because the permissive version is the obvious one
to write, and the failure would look like data rather than like a bug.

**Fix.** An undeclared key is refused and the agent is told so in the tool's
reply, which is also the more useful behaviour mid-call: the model corrects itself
and asks for what was actually declared. Pinned in both suites -
`test_collection.py` for the rule, and `test_dispatch_contract.py` for the
contract, so the API's declared fields and the worker's accepted keys cannot
drift apart.

**Depends on / Blocks:** nothing.

### #144 - transcript recovery must never overwrite what the agent heard

**S3 · FIXED · voice-runtime · `app/collection.py`, `app/worker.py`**

A model that holds a perfect conversation and forgets to call `record_field`
produces an empty result and escalates a call that did not need a person. So
`recover_missing()` reads absent fields back out of the transcript - which
immediately raises the opposite risk: a guess that *looks* like an answer means
the person who should have been asked never is.

**Impact.** Prevented, by two deliberate choices rather than one. The merge order
puts recorded values last (`{**recovered, **recorded}`), so an answer always beats
a guess. And the scan is narrow on purpose: it matches the field's own name
followed by a value on a **contact** turn, so the agent's own question ("so your
budget is what exactly?") is not read back as the reply. No inference pass - a
second LLM call to interpret the conversation is a real option, and it is not
this.

**Fix.** As described, plus a scan ceiling: a transcript past 40,000 characters is
truncated rather than regex-scanned whole, and the field is then reported missing.
That is the safe direction - a person gets asked.

**Depends on / Blocks:** nothing.

### #145 - three docs pages described behaviour that was never built

**S2 · FIXED · web · `app/(marketing)/docs/`**

Found while updating the docs site off campaigns, and unrelated to that change:

1. `writing-a-good-goal` documented a `call_not_ready` state and a 40-character
   minimum on a goal. `grep -rn call_not_ready apps/` hits the docs page and
   nothing else; `agent-editor.tsx`'s validation checks a name of two characters
   and a chosen model, and has no prompt-length check of any kind.
2. The same page told the reader to "preview it on a real name before you run".
   There is no prompt preview anywhere in the frontend, and the rebuilt run
   composer has no preview pane.
3. `getting-started` told people to start from a built-in goal template.
   `agent-presets.tsx` offers model and cost tiers, not goal templates.

**Impact.** Real, in the way CLAUDE.md non-negotiable #9 is about: someone
follows the documented step, cannot find the control, and concludes the product
is broken rather than the sentence. Also the api-reference page still documented
four `/api/v1/campaigns` endpoints and a `/campaigns/preview` that returned 404.

**Fix.** All three claims removed and replaced with what the page can honestly
say. Every endpoint in api-reference re-verified against the route files rather
than against SYSTEM.md, which was itself stale.

**Depends on / Blocks:** nothing.

### #146 - dead permissions outlived the feature they guarded

**S4 · FIXED · api · `app/auth/permissions.py`**

`CAMPAIGNS_READ`, `CAMPAIGNS_WRITE` and `CAMPAIGNS_DELETE` remained in the
permission enum and in the viewer/operator role sets after every endpoint they
guarded was deleted. Nothing read them - not a route, not a test, not the
frontend, which receives the permission list in its profile payload.

**Impact.** Cosmetic today. Recorded because the permission matrix is meant to be
readable as the authoritative answer to "who can do what", and entries for
features that do not exist make it answer a question nobody asked.

**Fix.** Removed, along with the `RequirePermission` docstring example that used
one.

**Depends on / Blocks:** nothing.

### #147 - the share-request list labelled an escalation "Campaign"

**S3 · FIXED · web · `app/(app)/app/organisation/page.tsx`**

```tsx
{request.resource_type === 'escalation' ? 'Campaign' : 'Escalation'}
```

The two branches were the wrong way round, so every request in the "Sent by you"
list was labelled with the name of the *other* resource type. Escalation is the
only shareable resource since ADR-8, so the ternary had no second branch to be
right about either.

**Impact.** Real, and the kind that survives review: the list rendered, the words
were product vocabulary, and the label was simply wrong about what you had asked
for.

**Fix.** The label is `Escalation`, with no branch.

**Depends on / Blocks:** nothing.

### #148 - three pricing claims describe features that do not exist

**S2 · OPEN · web · `apps/web/lib/pricing.ts`**

Found while sweeping campaign vocabulary out of the marketing copy, and
deliberately **not** renamed - converting these to agent vocabulary would have
turned a false claim about campaigns into a false claim about agents.

1. `"All starter campaign templates"` (line 80), and the related
   `free: "Templates only"` grading of custom extraction fields (line 245).
   There is no goal-template picker in the product. `agent-presets.tsx` offers
   model and cost tiers - a pipeline choice, not a goal. `verticals.ts`'s
   `goalTemplate` is read only by the public solutions pages.
2. `"Scheduled runs and calling windows per campaign"` (line 121). No scheduler
   exists anywhere in the web app.
3. `label: "Calling windows per campaign"` (line 231), marked
   `growth: true, scale: true` - i.e. sold as a paid entitlement. Calling windows
   are not enforced server-side at all (#20), and `run-settings.ts` says so in
   its own docstring: they live in `localStorage` because no API field exists.

**Impact.** Real, and commercially the most serious kind: (3) is a billed
entitlement for a guard that does not run, which is a stronger claim than the
product-tour copy CLAUDE.md non-negotiable #9 is usually about. Someone could buy
a tier for calling windows and dial outside them.

**Fix.** Not a copy edit - each line needs either the feature built or the claim
withdrawn, and that is a product decision. Recorded here rather than quietly
reworded. Kept open on purpose.

**Depends on / Blocks:** #20 (calling windows unenforced).

## Iteration 24 - 2026-08-19 - the local stack would not start, and no number could ever dial

### #149 - provisioning never wrote back to the number a run dials from

**S1 · FIXED · api · `apps/api/app/services/number_provisioning.py`, `apps/api/app/database/repositories/telephony_numbers.py`**

Two tables record connecting a number, and they answer different questions.
`telephony_provisioning` is the ledger of one attempt - what it created, in what
order, what failed - keyed by voice agent. `telephony_numbers` is the number
itself, and `GET /telephony/numbers` resolves `diallable` from *that* row:
`is_diallable(status) and bool(livekit_outbound_trunk_id)`.

`connect_number()` wrote its whole lifecycle - `PROVISIONING`, `VERIFIED`, every
trunk id - to the attempt ledger and **never touched the number row**. It did not
even import `telephony_numbers`. So a fully provisioned number stayed
`discovered` with a null trunk, and `numbers_repo.set_status(..., VERIFIED)` had
no caller anywhere in the product.

**Impact.** No number could ever become diallable, in any organisation, by any
route. The run composer's `diallable.length === 0` branch was therefore permanent:
it told the user to "connect a carrier in Integrations", they connected one
successfully, came back, and read the same sentence again. `discovered -> verified`
is also an illegal transition (`domain/numbers.py`), so the manual
`PATCH /telephony/numbers/{id}` could not repair it either - it 409s.

**Fix.** `_mirror_to_number()` carries the attempt's outcome onto the number row
at each state change, and `by_e164()` resolves the row from the E.164 the
workflow is given. It never raises: LiveKit and the carrier are really configured
by then, so a bookkeeping failure must not roll back the ledger of what exists. A
`disabled` number is explicitly left alone - `disabled -> verified` is legal, so
the transition table would not have stopped provisioning from quietly putting a
deliberately-retired line back into service. Five tests in
`test_number_provisioning.py` cover it; the disabled case caught that gap.

### #150 - the connect-a-number endpoint had no caller, and could not have had one

**S1 · FIXED · web · `apps/web/lib/api.ts`, `apps/web/components/app/carrier-numbers.tsx`, `apps/api/app/api/v1/routes/telephony.py`**

`POST /voice-agents/{id}/connect-number` is the only endpoint that provisions a
number. Nothing in `apps/web` called it - `api.ts` had no method for it - and
nothing could have: `ConnectNumberIn` required `phone_number`, but every number
the API returns is masked (non-negotiable #4), so no screen held the value to
send. The only screen listing numbers at all was the run composer, which could
merely link to Integrations; Integrations did not show numbers.

**Impact.** With #149, the second half of why connecting a carrier appeared to do
nothing. Even after #149 the fix would have been unreachable from the product.

**Fix.** `ConnectNumberIn` now accepts `number_id` and resolves the E.164
server-side where it is already permitted, rather than unmasking for the client;
`phone_number` stays for API callers, with a validator requiring one of the two.
`api.connectNumber` was added, and a `CarrierNumbers` section on Integrations
lists each number with its state and a "Make diallable" action. It sits directly
under the readiness line, because that line counts *credentials* and a credential
is not a diallable line.

### #151 - the run composer sent people to fix something that page could not fix

**S2 · FIXED · web · `apps/web/app/(app)/app/runs/new/page.tsx`**

`calling_available` is a property of the *deployment* - LiveKit keys in the
server environment - and was checked last, below the carrier and number gates.
With it false, no carrier connection can produce a diallable number, so the
composer led with "Connect a carrier in Integrations" for a condition Integrations
has no power over.

**Fix.** The deployment check runs first and names the missing variables. The
number branch now distinguishes nothing-synced from synced-but-not-connected, so
the sentence changes as the user makes progress instead of repeating.

### #152 - credit enforcement left the dial path in an uncommitted refactor

**S1 · OPEN · api · `apps/api/app/services/run_dialer.py`**

`RunDialer.__init__` took `credit_ceiling` at `HEAD` and used it to reserve and
release credits per dial. The working tree removes it, and no replacement exists:
`credit_ceiling` appears nowhere in `app/`, and `run_dispatch.py` has no reserve
logic. The nine `test_orchestrator.py` failures are that removal - the tests still
pass the argument, and they are currently the only trace of the guarantee.

**Impact.** Against non-negotiable #2 (fail closed): with no ceiling, a bug in a
run cannot be stopped from draining an organisation's credits. Not introduced by
this iteration's work and left for the author of the refactor - where credits
should now be enforced is a design decision, not a mechanical repair.

### #153 - the local stack could not start at all

**S1 · FIXED · infra · `docker/volumes/db/01-roles.sql`, `02-schemas.sql`, `03-post-init.sql`, `docker/docker-compose.yml`**

`npm run local` failed with `container callflow-db is unhealthy`, and the cause
was three deep. The entrypoint globs `/docker-entrypoint-initdb.d/*` - an ASCII
sort - so `01`/`02` ran *before* the image's own `migrate.sh`, which runs the
`init-scripts/` the entrypoint skips as a directory. Those scripts create `anon`,
`authenticated`, `service_role`, `authenticator`, `supabase_auth_admin` and
`supabase_storage_admin` unguarded, so `01` creating them aborted `migrate.sh` on
"role already exists". ON_ERROR_STOP then skipped everything after it: `auth.users`
was never built, GoTrue crash-looped, and no filename could fix it because every
digit sorts before `m`.

Two more surfaced behind it. The image seeds a 2017 GoTrue baseline that v2 cannot
migrate over (`relation "schema_migrations" already exists`), and its
`00000000000003-post-setup.sql` demotes `postgres` to NOSUPERUSER with only USAGE
on `public`, so Alembic could not create `alembic_version`.

**Fix.** `01-roles.sql` creates only `postgres` - the one role the image never
makes with BYPASSRLS, which §4b depends on. Everything needing the image's roles
moved to `03-post-init.sql`, mounted at `/etc/postgresql.schema.sql`, the hook
`migrate.sh` runs last: passwords, grants, search_paths, an empty `auth` schema
handed back to GoTrue, and `postgres`'s privileges restored. Verified end to end -
signup fires `on_auth_user_created` and lands a real organisation and membership.

### #154 - the internal callback disclosed its schema to anyone who could reach it

**S2 · FIXED · api · `apps/api/app/api/v1/routes/internal.py`**

`_require_internal_key()` was called in the first line of `complete_call`, but
FastAPI validates the request body *before* the handler runs. So a caller with
no secret got a 422 naming the field that was wrong - and by iterating, the
whole `CallCompletion` schema of an internal, unauthenticated-by-design endpoint.
The 404-for-everything the docstring describes only applied once the body
already parsed.

**Fix.** `_require_internal_key` is a route dependency, so it resolves before
validation and an unauthenticated caller gets a bare 404 whatever it sends.
`_complete()` in the tests now calls the dependency then the handler, in the
order FastAPI does - calling the handler alone skipped the check entirely, which
is why the trust-boundary tests passed while the boundary leaked.

### #155 - everything the agent collected was thrown away

**S1 · FIXED · api · `apps/api/app/database/repositories/runs.py`, `apps/api/app/api/v1/routes/runs.py`**

`append_outcome` wrote 20 columns. Four that the worker reports and the schema
already has were not among them: `collected` (the org's own business fields),
`missing_required_fields`, `handoff_questions`, and `from_number_masked`.

The whole chain around them was built. The worker computes `collected` and POSTs
it; `internal.py` derives `missing_required` and `handoff_questions` from it and
feeds triage, which is how escalations get raised; `entities.py` declares all
four; `api.ts` types them; `TranscriptView` renders "Called from", "What we
asked for" and "Ask on the callback" from them. Only the INSERT, the SELECT in
`list_outcomes`, and the serialisation in `get_run` were missing - so the data
was computed, used for the escalation decision, and then dropped.

**Impact.** The product's actual output. A run completed, the transcript and
disposition displayed correctly, and the structured fields the agent was sent to
establish were invisible on every run. `repositories/escalations.py` already
selected these columns, so the escalation queue read `{}` and `[]` on every row.

**Fix.** All four are written (with `from_number_masked` coalesced, since the
dialler knows the line and the worker does not - the terminal write must not
blank it), selected, and serialised. Four tests assert on the **stored row**
rather than on the triage decision, which is the gap that let this ship: a test
passed `collected` in and asserted only that no escalation was raised.

### #156 - a run whose dispatcher died stayed "running" for good

**S2 · FIXED · api · `apps/api/app/database/repositories/runs.py`**

`finish_if_all_settled` closes a run once settled outcomes reach `runs.total`,
and `expire_stale_in_flight` rescues a call that started and never reported. But
a run is dispatched into `BackgroundTasks` on the uvicorn worker that served the
request, so an API restart mid-run kills it - and every contact not yet reached
has *no `call_outcomes` row at all*. Nothing settles them, `count(*) >= total`
is unreachable, and the run reads "running" forever while the detail page polls
it forever.

**Fix.** `abandon_undialled()` records the unaccounted contacts as real failures
(`error = 'never_dialled'`, disposition `unreachable`) once the run is past the
same stale window, rather than reducing `total` - nobody called those people, and
a run that quietly shrinks its own target is a success state for something that
did not happen.

### #157 - one test file failed collection instead of skipping

**S3 · FIXED · api · `apps/api/tests/test_dispatch_contract.py`**

`_load_worker_module` is written to `pytest.skip` when voice-runtime is absent,
but it checked `spec is None` - and `spec_from_file_location` returns a perfectly
good spec for a path that does not exist. The failure surfaced at `exec_module`
as a `FileNotFoundError`, which pytest reports as a **collection error for the
whole file**, aborting the run. The `api` container mounts only `apps/api`, so
this was the normal case there: the suite could not be run without
`--ignore=tests/test_dispatch_contract.py`.

**Fix.** Check `path.is_file()` before building the spec, and skip at module
level. The file runs where voice-runtime is mounted and skips where it is not.

### #158 - a synced number was never pointed at LiveKit, so the chain stopped one step short

**S1 · FIXED · api · `apps/api/app/api/v1/routes/telephony_numbers.py`**

`POST /telephony/numbers/sync` discovered what a carrier holds and stored each
number `discovered` with no trunk - which `is_diallable` refuses. Provisioning
was a separate endpoint nothing called (#150), and after that was wired it was
still a separate button. So the honest sequence was: connect a carrier, sync,
read "no number is ready to dial from", and have no way to tell that a third
step existed at all.

**Fix.** Sync provisions every number it discovers, so connecting a carrier and
syncing leaves numbers ready to dial. Failures are per number and never raise -
the carrier and LiveKit are separate systems and either can refuse one number
for a reason that says nothing about the next, so a sync that 502'd on the third
would hide the two that worked. Each failure lands on its own row's
`last_error`, which the Integrations list and the run composer both now show
instead of a generic sentence. With no agent built yet the numbers are left
`discovered` with that as the reason, because the dispatch rule has to name one.

### #159 - making a number diallable took over its inbound routing

**S2 · FIXED · api · `apps/api/app/services/number_provisioning.py`, `integrations/telephony/*.py`**

`configure_number` has an `attach_number` flag that stops before associating the
number with the trunk - everything created is new, the number keeps whatever was
already answering it, and CallFlow can still dial *out* from it because Twilio
validates an outbound caller ID against the account. `connect_number` never
passed it, so every provisioning run took the destructive branch.

**Impact.** Sharper now that sync provisions automatically (#158): a number that
is someone's support line or IVR would have been silently redirected by pressing
"Sync". Placing outbound calls never needed that.

**Fix.** `attach_number` is threaded through `connect_number` and defaults to
**False**. Claiming inbound is still possible and has to be asked for. The flag
is declared on the `Carrier` protocol rather than special-cased for Twilio;
Plivo, Telnyx and Vonage accept it and document that their APIs bind the number
in the same call, so inbound is always claimed there (CLAUDE.md §3, capabilities
declared rather than assumed).

### #160 - credentials were never checked, so "Connected" meant "typed"

**S2 · FIXED · api · `apps/api/app/domain/providers.py`, `apps/api/app/services/credential_check.py`, `apps/api/app/api/v1/routes/integrations.py`**

`PUT /integrations/providers/{provider}` validated that the declared fields were
*present* and stored whatever they held. `_validated_fields` rejects an unknown
key and a blank required one; nothing ever asked the vendor whether the value
worked. The card then read "Connected" either way, so a mistyped key surfaced
much later as a sync that found nothing or a call that reached silence - a long
way from the form that caused it, which is the failure mode non-negotiable #9
exists to prevent.

**Fix.** `CredentialProbe` on `ProviderSpec` declares one **read-only** request
that proves a credential - data, not code, for the same reason the credential
fields are data: 57 providers would otherwise mean 57 functions to keep in step
with a declarative catalogue. `services/credential_check.py` performs it and
`connect_provider` refuses to store a credential the vendor rejects.

**The three-way answer is the point.** Rejected blocks the save. *Unreachable*
does not - an outage at the vendor must not stop someone configuring a working
account. And a key the vendor authenticates but refuses for **scope** is real,
so it is stored with that distinction kept: ElevenLabs keys are scoped per
operation, and a key that cannot read `/voices` may still synthesise speech,
which is all CallFlow asks of it. Rejecting it would block a working key.

Probes are declared for Twilio, OpenRouter, Groq, xAI, Google, Sarvam and
ElevenLabs. A provider with no probe returns `ok=None` and is stored unverified
rather than claimed to be checked.

**Found immediately on real data:** of seven credentials stored in the author's
own organisation, three were bad - Groq and xAI outright rejected, ElevenLabs
scoped too narrowly to confirm. All three had been showing "Connected".

### #161 - two credential probes pointed at public endpoints, so they accepted any key

**S2 · FIXED · api · `apps/api/app/domain/providers.py`, `apps/api/app/services/credential_check.py`**

Found by auditing #160's own work rather than trusting it: every probe was
replayed with **no credential at all**, on the principle that a probe which
cannot fail proves nothing.

Two of seven answered 200 unauthenticated. Sarvam's `/v1/models` and ElevenLabs'
`/v1/voices` are public listings, so `check_credentials` returned `ok=True` for
any string - `{"api_key": "fake-sarvam-key"}` verified clean. Sarvam was the
worse of the two: it silently accepted garbage. ElevenLabs only looked correct
because the key it was tested against happened to be scope-refused for an
unrelated reason.

**Fix.** Sarvam has no read endpoint that authenticates, so `CredentialProbe`
gained `method` and `accept_statuses`: its probe POSTs an **empty body** to
`/text-to-speech`, which checks the key before the body - a good key is refused
for the body (400, "text must be provided"), a bad one for the key (403), and
nothing is synthesised or charged either way. ElevenLabs moved to `/v1/history`,
which requires a key and distinguishes "Invalid API key" from "missing the
permission" in its own message, so a narrowly-scoped real key is still kept
rather than rejected.

**Also fixed: an empty secret read as a vendor outage.** `Bearer ` is an illegal
header value, so httpx raised before sending and the handler classified it as
unreachable - which does not block a save. A blank required field is now
rejected outright.

**Verified after the fix.** All seven probes answer 4xx unauthenticated; ten
deliberately-invalid credentials across six vendors were rejected with no false
accepts; the four genuinely-valid stored credentials still verify. Two tests
lock the flaw shut - one naming the known-public endpoints, one proving a bare
400 is still a rejection where `accept_statuses` was not declared.

### #162 - changing a TTS provider kept the old vendor's voice, and the call died on it

**S1 · FIXED · web + voice-runtime · `apps/web/components/app/agentic/agent-editor.tsx`, `provider-wheel.tsx`, `apps/voice-runtime/app/pipeline.py`**

`voice_id` is one column shared by every TTS vendor, and the names do not carry
across - ElevenLabs' "Rachel" is not a speaker Sarvam's bulbul model has.
Switching the provider on the Agents screen did not clear it: the preset path
(`onApply`) reset the voice, but selecting a provider directly on the wheel
called `setTtsProvider` alone.

**The screen then hid it.** `ProviderWheel` displayed `selectedVoiceId ??
voiceOptions[0]`, so after the switch it showed a perfectly valid Sarvam voice
while state still held `Rachel` - the operator picked correctly, saw the right
thing, and saved the wrong one. A success state for something that did not
happen (non-negotiable #9).

**Impact.** The worst placement possible: Sarvam validates the speaker in its
*constructor*, so `build_pipeline` raised after the contact's phone was already
ringing. They answered to silence, the call was billed, and the run row stuck at
`in_flight` because the failure path could not report either (#163).

**Fix.** Three layers, because one was not enough. The wheel's `onSelect` now
moves the voice with the provider; its display no longer falls back for a value
this provider does not have, so what is shown is what will save; and
`_sarvam_speaker()` drops a name the vendor's *current model* does not list
rather than passing it to a constructor that raises. That last check asks the
plugin's own `MODEL_SPEAKER_COMPATIBILITY` for the model it will actually build
with - `anushka` is a real speaker for bulbul:v2 and rejected by v3, so the
union of every model's list would still have let a call fail.

### #163 - the worker's callback could not reach the API on Windows

**S2 · FIXED · config · repo-root `.env`**

`CALLFLOW_PUBLIC_API_URL` was `http://localhost:8000`. On Windows `localhost`
resolves to IPv6 `::1` first, and `[::1]:8000` was held by Docker Desktop's
`wslrelay` while uvicorn listened only on `127.0.0.1`. Every completion report
hit the relay, which speaks no HTTP, and retried to exhaustion with
`RemoteProtocolError`.

**Impact.** Compounds every call failure: the outcome is never recorded, so the
row stays `in_flight` and the run never closes - which is what made #162 look
like a hang rather than an error.

**Fix.** `http://127.0.0.1:8000`. Worth knowing generally: on a Windows host with
Docker Desktop running, `localhost` is not a safe default for a service that
binds IPv4 only.

### #164 - the collect fields were listed to the agent but never asked for

**S2 · FIXED · api · `apps/api/app/domain/prompt_assembly.py`**

An operator adds fields on the Agents screen because those are the answers the
call exists to get. The prompt listed them under *"Record each one as soon as you
learn it"* - which says what to do with an answer that happened to arrive, not
that obtaining them is the purpose of the call. A capable model inferred the
intent; a small one talked about whatever it liked and collected nothing.

**Fix.** The block now opens with "This is what the call is for. Ask for each of
these, in this order, until you have them all", and closes by telling the agent
to ask one at a time, wait for each answer, and end the call once it has them.
The fields drive the conversation, so an agent's own prompt no longer has to
restate them - it carries identity and manner, which is what an operator should
be writing.

**Also fixed: a blank `{note}` left a dangling sentence.** `_Safe` renders a
missing placeholder as empty, which is right for a bare value and wrong for the
one an agent narrates around: "got in touch about: {note}" with nothing behind it
reads as "about: " and invites the model to fill the gap with something it
invented. `note` and `detail` now fall back to "no specific detail was recorded";
every other placeholder still renders empty. An empty-but-present column is
treated the same as an absent one - to the agent they are identical.

### #165 - nothing on the Agents screen said a prompt could carry placeholders

**S3 · FIXED · web · `apps/web/components/app/agentic/prompt-placeholders.tsx`, `agent-editor.tsx`**

`_identity_block` substitutes `{name}` and every context column into an agent's
prompt per contact, which is the feature that lets one agent call a whole sheet.
The editor was a bare textarea, so there was no way to learn this existed short
of reading `domain/prompt_assembly.py`.

**Impact.** Quiet and easy to miss in testing: a prompt gets written as "You are
calling Arbaaz about his Dubai trip", reads perfectly against the one contact it
was tried on, and then greets every other row in the run by the wrong name. The
prompt on this repo's own test agent had exactly that shape.

**Fix.** The tokens sit above the textarea as buttons: hovering explains what
each fills in, clicking inserts at the caret rather than appending, since anyone
reaching for `{name}` is mid-sentence. Only `{name}` and `{note}` get a button -
every column works, but listing a sheet's own headers would make the panel
change per run, and these two exist on every contact by definition.

### #166 - every Sarvam voice offered was one the runtime could not use

**S2 · FIXED · api · `apps/api/app/integrations/ai_providers/catalog.py`, `apps/api/tests/test_dispatch_contract.py`**

`ProviderCatalogEntry.voice_options` drives the Voice wheel, so every entry is a
promise: pick this and you will hear it. Sarvam ties its speaker list to the TTS
model and **replaced the entire set between bulbul v2 and v3**. The catalogue
listed seven v2 speakers - `anushka`, `abhilash`, `manisha`, `vidya`, `arya`,
`karun`, `hitesh` - and the plugin constructs with v3, which rejects all seven.

Compounded by #162's own fix: `_sarvam_speaker()` drops an unrecognised name to
`None` rather than letting the constructor raise, and `None` resolves to the
model default - `shubh`, who is **male**. So an operator picked "Anushka", the
agent was called Riya, and a man's voice answered. No error anywhere.

**Fix.** The catalogue lists bulbul:v3 speakers, female first because the default
is male. `voice_model` names the model the list belongs to, and
`test_dispatch_contract.py` checks every offered voice against the *plugin's own*
`MODEL_SPEAKER_COMPATIBILITY` table for that model, plus that both genders are
offered - a list that drifted all-male would hide the same bug. `apps/api` cannot
import `livekit.plugins` (that would invert the layering), so the test is the
seam that keeps the two in step. Verified by re-introducing `anushka` and
watching the suite fail with the reason.

### #167 - a customer's Google API key was logged in full

**S1 · FIXED · api · `apps/api/app/domain/providers.py`, `apps/api/app/core/logging.py`**

The Gemini credential probe passed the key as `?key=…`, and httpx logs every
request URL at INFO. `RedactingFilter` did not catch it: `_TOKEN_RE` matches
`api_key=`, `token=`, `secret=` and friends, but not a bare `key=` - verified by
running the regex over a real log line and watching the key come through intact.

**Fix.** The probe sends `x-goog-api-key` instead, so the secret never reaches a
URL; and `_TOKEN_RE` gained `key=\S+` as a backstop. The word boundary is
load-bearing - without it the filter also redacts `monkey=` and `turkey=`.

### #168 - "outbound only" was true for Twilio and false for the other three carriers

**S1 · FIXED · api · `apps/api/app/integrations/telephony/{plivo,telnyx,vonage}.py`**

`connect_number` defaults `attach_number=False` so that provisioning does not
repoint a number's inbound routing (#159), and the sync path depends on that:
every discovered number is provisioned automatically (#158). Plivo, Telnyx and
Vonage each **accepted the flag and ignored it**, attaching unconditionally, and
each said so in its own docstring.

**Impact.** An organisation with a Plivo support line presses "Sync plivo" and
every inbound call to that number is silently rerouted to LiveKit. Nothing asked,
nothing warned, and there is no un-attach path in the product.

**Fix.** All three now guard their final attach step, so the flag means the same
thing on every carrier. `test_telephony_carriers.py` asserts the guard exists in
each adapter *and* that the attach call sits inside it - checked against the
source because the alternative is a live carrier account. Verified by removing
one guard and watching the suite name the carrier.

### #169 - an unverified credential still reported "Connected"

**S2 · FIXED · api + web · `apps/api/app/api/v1/routes/integrations.py`, `apps/web/app/(app)/app/integrations/page.tsx`**

`check_credentials` returns three states and #160 only acted on one of them.
`ok=False` blocked the save; `ok=None` - no probe declared, vendor unreachable,
or a key scoped too narrowly to confirm - was computed, its explanatory message
built, and then dropped, because `ProviderCredentialOut` had nowhere to put it.
The card said "Connected" for a credential nothing had confirmed, which is the
exact failure the verification work exists to remove.

**Fix.** The response carries `verified` and `verification_note`, and the dialog
distinguishes all three: rejected, saved-but-unconfirmed, and confirmed.

### #170 - "Try again" on a retired number reported success and did nothing

**S3 · FIXED · web · `apps/web/components/app/carrier-numbers.tsx`**

`_mirror_to_number` deliberately refuses to move a `disabled` number back into
service (#149), but `connect_number` still marks its own attempt `verified`. The
button was offered for any non-diallable number, so retiring a number and then
pressing "Try again" produced a success toast, a fresh pair of LiveKit trunks,
and no visible change.

**Fix.** The button is not offered for a `disabled` number. Re-enabling stays a
separate, deliberate act.

### #171 - the voice wheel drew a substitution it never saved

**S2 · FIXED · web · `apps/web/components/app/agentic/provider-wheel.tsx`**

#162 stopped the wheel *displaying* a voice the selected provider does not have -
except both branches of the fallback still ended at `voiceOptions[0]`, so the
rendered output was unchanged and nothing propagated to the editor's state.

**Impact.** Any agent saved before that fix still holds the old vendor's voice.
Opening it, editing the prompt and saving re-persisted the stale value: the wheel
showed `ritu`, the payload wrote `Rachel`, and the runtime then dropped it to the
model default. The displayed voice and the voice the contact hears never matched.

**Fix.** The wheel reports the substitution through `onVoiceIdChange` when the
stored value is not one this provider offers, so what is shown is what will save.

### #172 - the Needs-a-person queue could not show what the call got

**S2 · FIXED · api · `apps/api/app/api/v1/routes/escalations.py`**

`repositories/escalations.py` has always selected `collected`,
`missing_required_fields`, `handoff_questions` and `from_number_masked` - the
four columns #155 made real. `EscalationOut` declared none of them, so they were
read from the database and dropped at the response boundary.

**Impact.** The queue exists so somebody can pick a call up, and the only way
they can is by seeing what the agent already established and what it still
needs. They got a transcript and a disposition. `TranscriptView` on that screen
was already written to render all four - it had nothing to render.

**Fix.** The four fields are on `EscalationOut` and mapped in `_row_to_out`.
`Escalation extends Outcome` in `api.ts`, which already declared them, so the
frontend needed no change - the data simply arrives now. Verified end to end
against the real database: a call where the contact asks for a person reaches
the queue carrying `{flying_from: Delhi}`, `missing: [budget]`, and "Ask: Their
budget / They asked to speak to a person - call them back."

### #173 - 39 of the vendors the runtime can drive stored credentials unverified

**S3 · FIXED · api · `apps/api/app/domain/providers.py`**

#160 added credential verification and #161 fixed two probes that proved
nothing, but only 7 of 57 providers had a probe at all. Every other vendor -
including every LLM and most of the speech vendors an agent actually uses -
stored whatever was typed and reported it unconfirmed.

**Fix.** 23 more probes, each **tested unauthenticated first** on the principle
from #161 that a probe which cannot fail is worse than none: `rime`,
`smallestai` and `fishaudio` answer 200 with no credential and were deliberately
left unprobed rather than given a probe that accepts any string. All 23 were then
checked against deliberately-invalid keys - zero false accepts. Coverage is now
30/57, and `test_credential_check.py` pins the remaining wired gaps by name, so a
new vendor cannot quietly join them.

### #174 - an expired session looked like a missing page

**S2 · FIXED · web · `apps/web/lib/api.ts`, `lib/hooks/use-session-expiry.ts`, `components/layout/app-shell.tsx`, `app/(auth)/login/page.tsx`**

`req()` turned every non-2xx into a bare `Error` carrying the response body's
message. A 401 was therefore indistinguishable from any other failure, and each
screen described it in its own terms: the run detail page reported the run
missing. Someone whose token had expired went looking for a run that was sitting
in the database, visible to them, the whole time - confirmed by querying it
directly and by checking RLS as the owner who started it.

**Fix.** `api.ts` throws a named `SessionExpiredError` on 401 - a type rather
than a message match, because every data-loading screen has to tell this apart
from a real failure and comparing strings breaks the moment a message is
reworded. `useSessionExpiry()` listens once, in the shell every authenticated
page renders inside, signs the dead token out, and replaces the route with
`/login?next=…&reason=expired`. The login page explains why they are there,
because arriving at a login screen you did not ask for otherwise reads as the
app being broken - and they arrived from a page that would not load, so that
question is already in their head.

Listening on `unhandledrejection` rather than wrapping each call site: a poll or
a background refresh rejects with nothing awaiting it, which is exactly the case
that matters here. The bounce is guarded so several requests failing together -
a poll, a refresh, a page load - produce one sign-out rather than three.

## Iteration 47 - 2026-08-18 · a UI polish pass, scoped by an audit rather than by taste

> Renumbered from #133/#134 on merge into `arbaaz/agent-run-v1`: that branch
> had independently used both numbers, and its entries are cited from code
> comments. This iteration was renumbered instead because nothing outside
> this file referred to it yet.


### #175 - nine icon-only controls had hit areas below 44x44, and no control moved when pressed

**S3 · FIXED · web · `apps/web/app/globals.css` + 6 components**

Asked to "fix the UI and design". The audit found the design system in good shape - 2,410 lines of tokens, 23 documented rounds, skip links, `aria-label`s, reduced-motion, token-only colour - so this was scoped to preserve-mode polish rather than a restyle. Two real defects came out of it.

**Hit areas.** A dialog's close, a toast's dismiss, the input clear, the avatar trigger, and two overflow menus sat at 32px or 36px. WCAG 2.5.5 asks 44x44; Apple and Google land on 44pt and 48dp. New `.hit-target` grows the tappable region with a centred pseudo-element and leaves the visual untouched, so the deliberate compactness survives. Applied to seven of nine - **not** to `Button`'s `sm`, whose toolbar neighbours would then have *overlapping* hit areas, which mis-taps worse than a small target and is what WCAG's spacing exception exists for.

**Tactile press.** Colour said "registered"; nothing said "pushed". The reason it was missing is documented above `VARIANTS`: `primary`/`secondary` take their pressed colour from unlayered `.btn-glass-*`, so no Tailwind `active:` utility can win on `background`. `.press` uses `translate` instead - a different property, GPU-composited, applied once to the base rather than per variant. Off under `prefers-reduced-motion`.

Tailwind v4 compiles `-translate-y-1/2` to that same `translate` property, so the input's clear button gets `hit-target` **without** `press` - together they would have knocked it out of vertical centre on click.

**Two candidates were left alone**, which is the more reusable half: typography (§20 already re-scaled it, no defect found) and spacing rhythm (a grep suggested `gap-6` vs `gap-1` across pages; the `gap-1` hits were page-*title* stacks where 4px is correct, so the measurement was wrong, not the spacing). `DESIGN_NOTES.md` §24 records both non-findings, because the next person asked to fix the UI will run the same two greps.

**Verified.** `eslint` 0 errors, `tsc` clean on source. Not measured in a browser - hit-area growth is geometric rather than perceptual, but a device check on the toast dismiss and the avatar trigger is worth doing.

### #176 - Settings listed an Integrations tab that threw you out of Settings

**S4 · FIXED · web · `apps/web/app/(app)/app/settings/layout.tsx`, `CAPABILITIES.md`**

Integrations had already moved to the primary nav, and `settings/integrations/page.tsx` was reduced to a bare `redirect('/app/integrations')` - kept deliberately, since the old path is in browser history and in `SYSTEM.md`. What survived the move was the **nav entry**. Clicking "Integrations" inside Settings therefore navigated out of Settings entirely, which reads as a broken tab rather than a relocated feature.

Removed the entry; kept the redirect. A comment sits where the tab used to be so it does not get helpfully restored.

`CAPABILITIES.md` still told readers the frontend lived at `/app/settings/integrations` and now names the real path. `SYSTEM.md` was already correct. Nothing in code linked to the old route - the two remaining mentions describe `ConnectDialog` as a structural template, which is still accurate since that component moved with the page.

**Left alone:** `VOICE_AGENT_PLATFORM.md` still points at the old file for the `COMING_SOON` vendor list. It is a planning document rather than a reference one, so correcting it was not folded into this.

### #177 - with no vendor plugin installed, every Sarvam voice was silently dropped

**S2 · FIXED · voice-runtime · `apps/voice-runtime/app/pipeline.py`**

`_sarvam_speaker()` asks the plugin which speakers its current model accepts, so
a name the model rejects can be dropped before it raises in the constructor
(#162, #166). Its `except` returned `None` - the same value as "not a valid
speaker" - so where the plugin is *not installed* every voice was dropped,
including valid ones.

`None` means "use the model default", so this was the failure the function
exists to prevent, reached by another road: an operator's chosen voice replaced
silently, with nothing logged. CI caught it because the vendor plugins are
optional extras that CI does not install; three green local runs did not,
because this machine has them.

**Fix.** `_sarvam_known_speakers()` returns `None` for "cannot be asked", which
is distinct from "not in the list". With no table to consult the voice is passed
through and the plugin decides - the only component that can. Tests now pin the
table explicitly so both branches run everywhere, and the one test that needs
the real plugin `importorskip`s it rather than failing for the absence it exists
to tolerate.

### #178 - six tests outlived the guards they covered

**S3 · FIXED · api · `apps/api/tests/test_orchestrator.py`**

The per-run ceiling, allowlist, rate limiter, daily budget and per-teammate
credits were removed from `domain/safety.py` at the product owner's direction,
pending a replacement security layer - the module docstring records it. Six
tests still passed `credit_ceiling`, `credits_used_before_run` and
`max_calls_per_run` to a dialler and a `Config` that no longer accept them, so
they failed on `TypeError` and had been red since that commit.

**Impact.** Not the guards - those went deliberately. The red suite: nine
failures nobody was reading meant a real regression would have looked the same,
and it blocked the PR's API check.

**Fix.** The six are removed, and the module docstring says why and what brings
them back. Three others in the same file failed only because a shared helper
passed `max_calls_per_run` - those test room naming and session sharing, which
are still real behaviour, so the argument was dropped and the tests kept.

Worth stating plainly: this was mistaken for uncommitted local work several
times while it was in fact committed, deliberate and documented.

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
