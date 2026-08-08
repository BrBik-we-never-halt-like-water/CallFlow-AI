# CallFlow AI - Current System Capabilities

A snapshot of what this product can actually do today, for anyone evaluating it
without reading the full codebase. This is a capability summary, not the technical
reference - `SYSTEM.md` is the exhaustive as-built doc (every endpoint, every module,
every field); `ISSUES.md` is the living bug log; `CALLE_INTEGRATION_STATUS.md` covers
the voice-vendor integration specifically. This file exists to answer one question:
**what works, what's partial, and what's a stub, right now.**

Last updated: 2026-08-08.

---

## 1. What it is

CallFlow AI is an operations layer for outbound phone calls. A user loads contacts,
writes a goal in plain English, and the system dials, holds a conversation toward
that goal using CALL-E (the underlying voice AI provider), and returns
schema-validated structured data per call. Calls that go cleanly close themselves;
frustration, opt-outs, or requests for a human get escalated to the team's worklist.

---

## 2. Fully real and working today

**Identity, organisations, and roles**

- Email/password signup and login via Supabase Auth. Every user belongs to one or
  more organisations via a real `memberships` table, with row-level security
  enforced at the database layer, not just checked in application code.
- Four roles - owner, admin, operator, viewer - each with a distinct, enforced
  permission set (`app/auth/permissions.py`), checked at both the API layer
  (`RequirePermission`) and the database layer (RLS policies), independently.
- **Role-hierarchy enforcement is real and tested**: an Admin cannot grant
  themselves or anyone else `owner` or `admin`, cannot act on (demote/remove) a
  member who already holds `admin` or `owner`, and cannot escalate a pending
  invitation's role after the fact - closed in three fix rounds this session after
  a genuine privilege-escalation vulnerability was found and fixed (`ISSUES.md`
  #43–#45). 174 backend tests pass, including live cross-role and cross-tenant
  checks against a real database, not mocks.
- Mandatory org-naming step on first login (server-enforced via `onboarded_at`, not
  a client-side flag that can be bypassed), with an optional add-a-teammate step.
- Switching organisations now correctly refreshes every panel on screen - this was
  a real bug (every data-fetch effect had its own dependency array that never
  included the active org) found and fixed this session (`ISSUES.md` - the
  org-scoped-fetch fix); the fix introduced one shared hook
  (`use-org-scoped-effect.ts`) that's now the standard pattern for all org-scoped
  data fetching, closing the whole bug class rather than patching instances.

**Calling and results**

- Campaigns are real, persisted, org-scoped Postgres rows - not the in-memory dict
  this product used to run on.
- Runs and call outcomes persist the same way, survive a restart/redeploy, and are
  correctly scoped per organisation.
- The suppression list (opt-outs) is enforced on every dial, not just displayed -
  checked inside `check_dial_allowed()` before any call goes out.
- E.164 phone validation, a per-run call ceiling, an allowlist, and per-IP rate
  limiting are all real, active guards. There is no dry-run mode - every run dials
  for real, by design (a deliberate, confirmed product decision from earlier this
  session).
- **Transcript capture is now real** - until this session, `_extract_transcript()`
  read from a response key that doesn't exist in CALL-E's actual API shape, so the
  transcript panel almost certainly showed "No transcript was recorded" for every
  real call ever made. Fixed and tested against CALL-E's actual documented response
  shape (`ISSUES.md` #52).
- Call polling is now resilient to transient read failures - a single flaky status
  check no longer marks a call that actually completed successfully as failed
  (`ISSUES.md` #53).
- Structured result extraction (the schema-validated JSON a campaign defines) works
  correctly and was independently verified this session against CALL-E's real
  response shape.

**Team and invitations**

- Real invitations, end to end: creating one, a real email being sent via Resend,
  accepting it, and being seated as a member - all backed by real Postgres rows and
  RLS policies, not a decorative "coming soon" screen.
- **Sending the invitation email itself currently fails for real teammates** - see
  §3, this is the one capability in this section with a real, live gap.

**Dashboard and visual design**

- A from-scratch visual rework this session: header consolidated into one row (no
  sidebar), a two-column dashboard grid, glassmorphism surfaces, Ubuntu typography,
  and a "Lush Forest" accent palette - all scoped to the `/app/*` dashboard only;
  the public marketing site and auth screens are deliberately untouched.
- Lamp colours (the five call/run/escalation state colours) remain strictly
  reserved for that purpose throughout - verified repeatedly this session, including
  a deliberate, documented decision to keep the new accent palette's exact
  requested hue even though it sits closer to the "jade" success colour than is
  ideal (a known, accepted tradeoff - see `DESIGN_NOTES.md` §2).

---

## 3. Partial or currently broken - know this before demoing

- **Team invitation emails cannot currently be delivered to a real teammate.**
  Root cause confirmed directly against Resend's API: the configured from-address's
  domain (`callflow-ai.brbik.com`) is not verified in the Resend account. This is
  not a code bug - Resend enforces domain verification account-side, and no
  application code can bypass it. The error message is now specific and actionable
  (names the unverified domain, points at Resend's dashboard) instead of a raw
  exception. **Action needed: verify a real, owned domain in Resend's dashboard**
  (`SUPABASE_SETUP.md` §3 has the exact steps) before real invitations can go out.
- **Escalation resolution is session-only, not persisted.** Clicking "Mark
  resolved" now correctly updates the list, the dashboard panel, and the header
  badge together (a real fix this session), but the resolution itself is not saved
  to the database - it reappears on reload. The UI says this honestly rather than
  claiming it's saved.
- **Contacts are not a persisted entity.** They exist only as an upload-per-run
  artifact; there's no standalone contacts table yet.
- **Rate limiting and the daily call budget are in-process, not persisted.** They
  reset on every restart/redeploy and don't share state across replicas. Known,
  unchanged gap - not addressed this session, out of scope for the work done here.
- **Billing shows real usage data but no payment processing.** The number shown is
  live (sourced from the same in-process rate limiter, so it inherits that gap
  too), but there's no Stripe or equivalent integration - this is disclosed
  honestly in the UI, not faked.
- **Reassigning an escalation to a teammate does nothing** - the button exists and
  is honest about it ("Assignment isn't wired up yet"), but there's no
  implementation behind it.
- **Overlay UI (dialogs, dropdowns, tooltips, selects, toasts) under `/app/*` still
  renders in the old font**, not this session's new Ubuntu - these components
  portal outside the scoped wrapper that carries the font, a real gap logged this
  session (`ISSUES.md` #49) with the reason a naive fix would make it worse
  explained in the entry.
- **An Admin can still be offered "Admin" as a role option** in the invite dialog
  and role-change dropdown, even though the backend will always reject it - a
  real, logged UX gap (`ISSUES.md` #50), not a security issue (the rejection is
  real and correctly worded).

---

## 4. Integrated but not fully exploited

CALL-E (the voice provider) offers more than this codebase currently uses - see
`CALLE_INTEGRATION_STATUS.md` for the full breakdown. Highlights: the Goals API
(a higher-level campaign-definition primitive) is entirely unintegrated; CALL-E's
own judgment fields (`task_completed`, `completion_confidence`, `evidence[]`) are
computed by the vendor but discarded by this codebase; live per-call event
streaming is declared as a supported capability but never actually called; and
true multi-recipient batching in a single CALL-E request is unused (this product
currently dials one contact per request).

CALL-E is also the only voice provider integrated - the `VoiceProvider` protocol
this codebase's own architecture principles call for (so a second adapter, like
Twilio or Plivo, could be substituted in) is scaffolded (`protocol.py`) but has
exactly one real implementation, which is not yet a proven abstraction by this
codebase's own stated standard.

---

## 5. Security posture

The one severe finding this session - an Admin-to-Owner privilege escalation
allowing full, unilateral organisation takeover - is closed, verified two
independent ways (reverting the fix and confirming the attack succeeds again; a
live end-to-end call through the real API), and covered by tests that hit the
actual behavior directly rather than just checking the permission matrix. Every
other role/permission boundary checked this session (org-scoped data visibility,
viewer-role write rejection, cross-tenant isolation) was confirmed correctly
enforced at both the API and database layers.

---

## For more detail

- `SYSTEM.md` - the full as-built technical reference (every endpoint, table, module).
- `ISSUES.md` - the living, severity-ranked bug log this file's §3 draws from.
- `CALLE_INTEGRATION_STATUS.md` - CALL-E's full service surface, integration gaps,
  and the two bugs fixed this session.
- `apps/web/DESIGN_NOTES.md` - every deliberate visual-design decision and
  documented deviation from the codebase's default conventions.
