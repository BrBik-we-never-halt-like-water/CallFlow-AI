# Design notes

Every decision this build made where the brief left an axis free, plus every place it
deliberately departed from the brief. Written for whoever picks this up next.

---

## 1. Direction change, mid-build

The build started against a brief titled **"The Exchange"** — a light/dark dual-surface
instrument-panel design that explicitly banned parallax, glassmorphism, gradient blobs,
and card shadows.

Partway through, the direction changed to:

- **light mode only**, no dark theme, no surface toggle
- softer, friendlier, card-led visuals
- subtle parallax permitted
- footer credit to **BrBik**

Both were followed in sequence, so the current state is: the original brief's *structure,
copy, and semantics* (which were strong and are largely intact), with the new
direction's *surface treatment*. Where the two conflicted, the newer instruction won.

Specifically reversed from the original brief:

| Original brief said | Now |
|---|---|
| Two surface modes, Paper + Panel | **Light only.** `lib/surface.ts`, `SurfaceProvider`, `SurfaceToggle` deleted. |
| "Cards do not have shadows" | A four-step soft shadow scale (`--shadow-xs` … `--shadow-lg`). Cards get `shadow-sm`, hover lifts to `shadow-md`. |
| Parallax banned | One parallax layer: the hero's background grid, 60px of travel, compositor-driven, off under `prefers-reduced-motion`. |
| Dashboard defaults to dark Panel | Dashboard is light, same surface as marketing. |
| Radius: 2/4/8/12px | Slightly softer: 3/6/10/16/20px. Nothing is pill-shaped except lamps, badges, avatars. |

**What survived unchanged, and should stay:** the lamp system, the copy deck, the
mono-for-machine-data rule, the safety-first run composer, and the discipline rule below.

---

## 2. The one rule worth protecting

**Colour with meaning is reserved for meaning.** The five lamp colours — `off`, `ice`,
`brass`, `jade`, `flare` — communicate call state and nothing else. They are never used
for buttons, links, headings, hovers, or decoration.

Consequences that look odd until you know the rule:

- The primary CTA is **monochrome** (`--surface-inverse` on `--text-inverse`), not brand-coloured.
- JSON syntax highlighting in `CodeBlock` uses **weight and dimming, not hue** — a syntax
  palette would put arbitrary colour on screen.
- Charts and sparklines are drawn in `--rule-strong`, with no series colours.

Three deliberate exceptions, each because the thing being coloured *is* state:

1. `Button variant="danger"` uses flare — a destructive action must not be misread.
2. Toast tones use lamp colours — a toast reports what happened to a call.
3. Form error borders use flare — a field that will block a run is call state.

If you add a colour to this product, check it against that rule first.

---

## 3. Free-axis choices

**Type.** Archivo (variable, `wdth` 112) for display, Inter Tight for body, JetBrains
Mono for all machine-produced values. Only Archivo is preloaded. The mono rule is
load-bearing: it is how a user learns at a glance what came from the system versus what
came from a person. Enforce it.

**The `Wordmark` is live text, not SVG paths.** The brief asked for inline SVG. Real text
inherits `currentColor`, scales with the type system, stays selectable, and is read
correctly by a screen reader; outlining it would lose all four and gain nothing. `Mark`
*is* inline SVG, because it is geometry.

**Icons.** Phosphor, `weight="light"` for decorative and `"fill"` for active nav state.
One set, no mixing.

**Page texture.** A single masked draughtsman's grid (`.grid-field`). Not a gradient, not
a mesh, not a blob. Used behind the hero, the auth card, and the closing CTA.

**Section rhythm.** Lamped hairline rules between home-page sections rather than
alternating background bands.

---

## 4. Light-mode contrast

The pure lamp colours do not all clear 4.5:1 against a light surface, so there are two
sets of tokens:

- `--lamp-*` — the dot itself, always the pure colour.
- `--lamp-*-text` — anything setting *text* in a lamp colour.

`LampBadge` uses both at once: a `color-mix` surface, a `color-mix` border, `-text` for
the label, and the pure colour for the dot. Never set text in a raw `--lamp-*`.

---

## 5. Where the UI is ahead of the API

This table is a living gap-map, not a one-time note — update the row the moment a surface
moves from fake to real, the same turn as the code change. Auth, org-scoped persistence,
suppression enforcement, team, API keys, and provider (Twilio/Plivo) credential storage
have all shipped since this section was first written; billing and calling-window
enforcement have not, and are still fake if left undocumented here.

| Surface | Data |
|---|---|
| Overview, runs, escalations, contacts | **Real.** Org-scoped, persisted in Postgres. Escalations are outcomes with `disposition === "escalated"`, contacts are grouped from call history. |
| Suppression list | **Real.** `public.suppressions`, org-scoped and RLS-enforced, and it's the actual table `check_dial_allowed()` checks before every dial (ISSUES.md #3). |
| Auth, team, profile | **Real.** Supabase auth, real invitations sent via email, real role-based permissions (`app/auth/permissions.py`). |
| API keys | **Real.** Org-scoped, hashed at rest, shown once. |
| Integrations (Twilio, Plivo) | **Real** credential storage only. Connecting a number does not yet change which number a run dials from — that needs the voice-agent platform (`FEATURES.md` F17). |
| Campaign editor — name, goal, fields, region, language | **Real.** |
| Campaign editor — calling window, retry policy | **Local.** `localStorage`, per campaign id — the create-campaign payload never sends these. `NotWiredNotice` says so on the panel. |
| Safety pane — calling window | **Not enforced.** The fields save, but no guard in `check_dial_allowed()` reads them (ISSUES.md #20). |
| Billing | **Partly real.** Usage numbers are the same limiter every run passes through. No payment processor is connected — upgrade/downgrade aren't wired. |
| Notifications | **Not wired.** Forms validate, then say nothing was sent, via `AuthNotice` / `NotWiredNotice`. |

The rule applied throughout: **never show a success state for something that did not
happen.** A fake "check your inbox" leaves someone waiting for an email that will never
arrive, and they blame the product rather than the gap.

`Stop run` is the sharpest case — the service has no cancel endpoint, so it stops
*polling* and the toast says exactly that: "Updates stopped, run not cancelled."

---

## 6. Field types: five in the editor, four on the wire

The editor offers `string | number | boolean | date | enum`. The service accepts
`string | number | integer | boolean`.

`date` and `enum` map to `string`, with their constraint folded into the field
description — and the description *is* the extraction instruction, so "one of: onsite,
hybrid, remote_only" genuinely constrains the answer. See `lib/campaign-fields.ts`.
Better than dropping two useful types from the editor.

---

## 7. React 19 patterns

`eslint-config-next` enables `react-hooks/set-state-in-effect`, which flags the common
"read localStorage in an effect, then setState" shape. The codebase avoids it three ways:

1. **`lib/hooks/use-external-store.ts`** — `useSyncExternalStore` over `localStorage` and
   `matchMedia`. Correct on first paint, SSR-safe, no cascading render. Use this for any
   new browser-state read.
2. **Render-phase derivation** — `useTypewriter`, `useRunPoll`, `StatusBoard`, and the
   hero's lamp sequence compare a key during render instead of resetting in an effect.
3. **Two justified `eslint-disable`s**, both genuine external-system reads:
   the campaign editor's one-shot `sessionStorage` handoff (which must also *clear* it),
   and the docs table-of-contents DOM scan.

Also: no `Date.now()` during render (`react-hooks/purity`). The overview sparkline buckets
relative to the newest result rather than the wall clock.

---

## 8. Accessibility

Targeted WCAG 2.2 AA. Implemented: visible focus everywhere, skip links, full keyboard
operation via Radix primitives, real `<table>` semantics with `<caption>`/`scope`/`aria-sort`,
labelled inputs with `aria-describedby` errors, `ErrorSummary` for long forms, and
`prefers-reduced-motion` + `prefers-contrast: more` support.

Two specifics worth keeping:

- **The lamp strip carries one summarising label** ("20 calls: 9 closed, 2 queued for
  retry, 3 need a person"), not twenty individual ones. Its lamps are `aria-hidden`.
  See `describeStrip` in `lib/lamp.ts`.
- **Run progress is announced once per settled-count change, debounced 1.2s.** A screen
  reader must not read out every row as it lands. See `useProgressAnnouncement`.

**Not yet done:** no manual screen-reader pass (VoiceOver/NVDA) and no automated axe run.
Both are worth doing before launch.

---

## 9. Vendor de-branding

The product reads as first-party throughout. No vendor is named in any UI copy, metadata,
asset, or filename. `callflow/calle_client.py` → `engine_client.py`, `CalleGateway` →
`EngineGateway`, and the SDK is imported under a neutral alias so nothing above that
module speaks the vendor's name.

Three deliberate exceptions, all functional:

1. `calle-ai` in `requirements.txt` / `pyproject.toml` — the real distribution name; the
   install breaks otherwise.
2. `CALLE_API_KEY` as an environment variable — the brief explicitly permits this. Every
   *label* says "Voice API key".
3. `"call-e/customerMetadata"` in `orchestrator.py` — an API payload key. Changing it
   would break extraction.

**Left in place, for you to decide:** `DEVPOST_STORY.md` at the repo root is entirely a
hackathon artefact. Deleting authored narrative felt like your call rather than mine — but
it is the one remaining hackathon reference in the repo.

**Still worth doing:** check the vendor's terms for an attribution requirement. Most
infrastructure vendors permit white-labelling on paid plans but require it on free tiers.
Five-minute check, avoids a takedown.

---

## 10. Commercial numbers are unset on purpose

Everything in `lib/pricing.ts` that is a price, an included volume, or an overage rate is
`null`, and renders as a visible `TODO` chip. A wrong number on a pricing page is worse
than an obviously missing one — nobody signs off a placeholder, but they will quote one
back at you.

The comparison and ROI calculators are different: those are **editable estimate inputs**
with real defaults, clearly labelled as the buyer's assumptions rather than our claims.

Fill in the checklist at the top of `lib/pricing.ts` and the whole page is correct — no
layout changes needed.

---

## 11. Known gaps

- **No test suite for the frontend.** The backend has 84 passing tests; `web/` has none.
  The highest-value targets are `lib/format/phone.ts` (the masking guarantee),
  `lib/lamp.ts` (the disposition→lamp mapping), and `lib/contacts.ts` (row validation).
- **Three high-severity npm advisories**, all pre-existing in Next 16.2.12's transitive
  deps (`postcss`, `sharp`). Fixed by upgrading to Next 16.3.0, which was out of scope
  as a pinned-version change. Worth doing.
- **`DataTable` sorts and paginates client-side** on the runs page because the list
  endpoint returns everything at once. Its props are already server-driven, so swapping in
  a real query touches the page, not the component.
- **No manual screen-reader pass** (see §8).
- The brief this was built from was **truncated at §13.5**; §14–16, including its own final
  checklist, were never received. Anything specified there is unimplemented by definition.

---

## 12. Environment

`web/.env.local` holds dummy values so the app runs immediately; `web/.env.example`
documents each one. Backend env is `.env.example` at the repo root.

```
NEXT_PUBLIC_API_URL    where the browser reaches the calling API
NEXT_PUBLIC_SITE_URL   absolute site URL, for canonical links and social cards
```

`lib/api.ts` rejects internal hostnames a browser cannot resolve and falls back to the
public URL — worth knowing before debugging an opaque "fetch failed".
