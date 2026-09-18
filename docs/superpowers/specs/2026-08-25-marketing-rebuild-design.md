# Marketing site rebuild: "The page is a run"

**Date:** 2026-08-25 · **Scope:** `apps/web` marketing surface · **Status:** built in this
session; awaiting product-owner review.

> **Process note.** This session ran autonomously — the user asked for a from-scratch
> rebuild ("new idea, 3D designs, images matching the vibe") and was not available for
> the question-per-message brainstorming loop. The clarifying questions below are
> therefore answered as recorded assumptions, each with the evidence that decided it.
> Anything wrong here is cheap to reverse: no history was destroyed (the pre-rebuild
> working tree is saved as a patch), and nothing is committed.

---

## 1. What the site must say (product truth, verified 2026-08-25)

The product pivoted to **agent-driven runs** (ADR-8): build a voice agent (system
prompt + fields to collect + STT/LLM/TTS legs + a voice), paste contacts, start a run.
The current marketing site still tells the pre-pivot story and **never mentions the
agent builder at all** — while the user's own pitch centres it. That gap is the "new
idea": the new site is the agent story, told as one continuous run.

**Claims the new site makes (all verified in code):**
- Build a voice agent from a plain-English brief; `{name}`/`{context}` placeholders fill
  per contact from your spreadsheet columns (`prompt_assembly.py`).
- Fields you define are collected mid-call by a real tool (`record_field`), recovered
  from the transcript when the agent forgets, and **a completed call missing a required
  field escalates to a person** (`triage.py` rule 8).
- Your carrier, your model keys: 4 carriers, 42 drivable AI providers, keys verified
  against the vendor before storage and encrypted at rest.
- The suppression list is checked before **every single dial** (`check_dial_allowed`).
- Phone numbers are masked everywhere; contacts are never stored.
- Escalations land in a live-synced, assignable queue.
- Stopping a run stops dialling but lets live conversations finish; skipped rows say so.
- Credits are integer paise, metered per second, fail closed at run start.
- Org isolation under RLS with 59+ cross-tenant tests.

**Claims the new site removes (currently on the live site and untrue):**
- Allowlist / per-run ceiling / rate limit (deleted guards; `safety-section.tsx`,
  `capability-grid.tsx` still render them) — the worst liability.
- "Sentiment on every call" (footer band) and the `sentiment: positive` proof chip —
  the worker sends `extracted: {}`; sentiment/frustration/opt-out detection never fires.
- "Queued for a polite retry" as a behaviour — `RETRY` is a label; nothing redials.
- Calling windows, webhooks, personas/prebuilt library — not built.

## 2. Approaches considered

1. **Restyle in place** — keep the deck, add 3D veneer. Cheapest; but the story stays
   pre-pivot and the untrue claims survive. Rejected: fails both halves of the ask.
2. **Dark cinematic relaunch** — new palette, photo-led. Rejected: marketing runs the
   token system with lint-enforced hue distances and light+dark themes already; a
   palette fork breaks `check-tokens.mjs` and the lamp discipline for a look we can get
   inside the system. Also: Higgsfield MCP (imagery) is installed but unauthenticated,
   so photo-led would ship empty frames.
3. **"The page is a run" (chosen)** — the page is one run happening: brief an agent →
   it compiles → one call up close → the whole list at volume → what needs a person →
   the guards → who it's for → price → start. 3D comes from CSS perspective staging +
   the existing `VoiceField` particle projection. No new dependencies: framer-motion +
   CSS does all of it.

   **Mid-build pivot (product owner, 2026-08-25):** the first cut drove the acts from
   scroll (pinned scrub, extending the repo's uncommitted WIP). The owner's review —
   "these sections are not moving/animating by their own, i have to scroll to move
   them" — reversed that: every act now plays itself on wall-clock timers gated to the
   viewport (`useInView`), loops or holds sensibly, and scrolling only moves between
   sections. The scrub plumbing (DeckSection `scrub` prop, depth-hook exclusion, pinned
   Steps) was reverted; the pre-rebuild tree survives as a scratchpad patch.

## 3. Page architecture (home)

| # | id | Component | Job |
|---|----|-----------|-----|
| 0 | — | `hero.tsx` (rebuilt) | 3D stage: tilted `CallBoard` + orbiting typed-result/escalation cards over `VoiceField`. Headline recentres the agent; proof strip only safe claims. |
| 1 | `problem` | `ProblemCompare` (kept) | The sharpest argument: same call, transcript vs typed row. |
| 2 | `agent` | **new** `agent-forge.tsx` | Pinned scrub: brief types → three legs light (`--leg-*`) → field chips with `required` → voice chip. The section the pivot earned. |
| 3 | `how-it-works` | `Steps` (WIP scrub finished) | One contact through the real UI. |
| 4 | `floor` | **new** `run-floor.tsx` | Scale: full-bleed field + counters; the volume claim without repeating the board. |
| 5 | `escalations` | **new** `needs-person.tsx` | The live queue: owned, assignable rows. |
| 6 | `providers` | **new** `provider-orbit.tsx` | The 56 real logos (`public/brands/`): your carrier, your keys. |
| 7 | `verticals` | `VerticalStrip` (restyled) | Who it's for (pain lines). |
| 8 | `safety` | `safety-section.tsx` (rewritten) | Only the guards that exist. |
| 9 | `pricing` | `PricingPreview` (kept) | Live gateway prices. |
| 10 | — | `FinalCta` (kept, light pass) | Close. |

Header/footer: nav anchors updated (`#capabilities` → `#agent`); footer capability band
loses "Sentiment on every call", gains honest lines.

## 4. Motion & 3D system

- **`components/marketing/stage.tsx`**: `Stage` (CSS `perspective`, `preserve-3d`) +
  `StageLayer` (fixed translateZ per depth 0–5) + pointer tilt (fine pointers only,
  ±3.5°, spring-smoothed) over a static rest pose.
- **Self-playing acts** (post-pivot): wall-clock timers gated by `useInView` — the
  forge cycles brief → legs → fields → ready (~22s loop, click a stage to jump), the
  steps advance every 4.2s, the floor sentence lights at ~9 words/s and replays on
  re-entry. Wall-clock (not tick-counting) so throttled tabs keep the pace and only
  coarsen the steps.
- **GPU-safe only**: transform/opacity/filter/clip-path. `will-change` only while
  animating.
- **Reduced motion**: every act renders assembled and still; the field freezes
  (existing behaviour).
- **Touch/small screens**: no tilt, shorter scrub tracks, all content readable unpinned.
- **Both themes** by construction: every colour is a token; no hex outside
  `globals.css`. New tokens: `--stage-perspective`, `--stage-glow` (from
  `--primary-edge`/`--primary-wash` family).
- **Colour discipline unchanged**: lamps = call state only (the board), `--leg-*` =
  pipeline legs only (agent act), indigo = action/decoration. `check-tokens.mjs` and
  `check-board.mjs` must stay green; `call-board.tsx` keeps its `SLOTS`/`SETTLED`
  schedule. Board run total drops 10,000 → 500 (the real `RUNAWAY_CALL_CEILING` is
  500/day; a 10,000-call board overclaims).

## 5. Imagery

No photography exists in the repo and Higgsfield MCP needs OAuth the session cannot
perform. The build therefore composes everything from code (field, lamps, logos,
glass) — which is also the brand's existing stance ("nothing a competitor can copy").
Image slots are reserved where a generated render could later land (hero backdrop
atmosphere, vertical cards); wiring them is a follow-up once `higgsfield` is
authenticated via `/mcp`.

## 6. Error handling / honesty rails

- Simulated surfaces (board, forge, queue) are deterministic from a second counter,
  SSR-safe, `aria` summarised once, and use only reserved fictional data (Indian names,
  masked numbers, `+1 555 01xx` where a full number is ever shown).
- No fake success states; no claims from the do-not-overclaim list (§1).
- Docs pages that overclaim (`/docs/safety-configuration`, `/docs/webhooks`,
  getting-started §4) are **out of scope here** but logged in ISSUES.md — they need a
  content pass, not a design one.

## 7. Testing / verification plan

1. `npm run lint` (eslint + check-tokens + check-board), `npm run type-check`,
   `npm run build`.
2. Browser pass: light + dark, 1280 and 390 widths, reduced-motion emulation; anchor
   landing for every nav link; keyboard walk of the header.
3. `ISSUES.md` updated (overclaim fixes are bug fixes); `DESIGN_NOTES.md` gains the
   rebuild section; `SYSTEM.md` untouched (no API/schema change).

## 8. Build order

`globals.css` stage tokens → `stage.tsx` → hero → `agent-forge` → `run-floor` →
`needs-person` → `provider-orbit` → safety rewrite → verticals/pricing/final passes →
header/footer copy → page assembly → verify → docs.
