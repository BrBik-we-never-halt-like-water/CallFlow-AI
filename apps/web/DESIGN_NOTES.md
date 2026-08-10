# Design notes

Every decision this build made where the brief left an axis free, plus every place it
deliberately departed from the brief. Written for whoever picks this up next.

---

## 1. Direction change, mid-build

The build started against a brief titled **"The Exchange"** - a light/dark dual-surface
instrument-panel design that explicitly banned parallax, glassmorphism, gradient blobs,
and card shadows.

Partway through, the direction changed to:

- **light mode only**, no dark theme, no surface toggle
- softer, friendlier, card-led visuals
- subtle parallax permitted
- footer credit to **BrBik**

Both were followed in sequence, so the current state is: the original brief's _structure,
copy, and semantics_ (which were strong and are largely intact), with the new
direction's _surface treatment_. Where the two conflicted, the newer instruction won.

Specifically reversed from the original brief:

| Original brief said              | Now                                                                                                                    |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Two surface modes, Paper + Panel | **Light only.** `lib/surface.ts`, `SurfaceProvider`, `SurfaceToggle` deleted.                                          |
| "Cards do not have shadows"      | A four-step soft shadow scale (`--shadow-xs` … `--shadow-lg`). Cards get `shadow-sm`, hover lifts to `shadow-md`.      |
| Parallax banned                  | One parallax layer: the hero's background grid, 60px of travel, compositor-driven, off under `prefers-reduced-motion`. |
| Dashboard defaults to dark Panel | Dashboard is light, same surface as marketing.                                                                         |
| Radius: 2/4/8/12px               | Slightly softer: 3/6/10/16/20px. Nothing is pill-shaped except lamps, badges, avatars.                                 |

**What survived unchanged, and should stay:** the lamp system, the copy deck, the
mono-for-machine-data rule, the safety-first run composer, and the discipline rule below.

---

## 2. The one rule worth protecting

**Colour with meaning is reserved for meaning.** The five lamp colours - `off`, `ice`,
`brass`, `jade`, `flare` - communicate call state and nothing else. They are never used
for buttons, links, headings, hovers, or decoration.

Consequences that look odd until you know the rule:

- The primary CTA is **monochrome** (`--surface-inverse` on `--text-inverse`) everywhere
  except `/app/*`, not brand-coloured - see the Lush Forest note below for the one
  scoped exception.
- JSON syntax highlighting in `CodeBlock` uses **weight and dimming, not hue** - a syntax
  palette would put arbitrary colour on screen.
- Charts and sparklines are drawn in `--rule-strong`, with no series colours.

Three deliberate exceptions, each because the thing being coloured _is_ state:

1. `Button variant="danger"` uses flare - a destructive action must not be misread.
2. Toast tones use lamp colours - a toast reports what happened to a call.
3. Form error borders use flare - a field that will block a run is call state.

**A fourth addition, not an exception - a second category.** `--accent` (`globals.css`)
is the product's one sanctioned _decorative_ colour, added for the dashboard's
2026-08-07 redesign. It carries no meaning and never will - the rule above still holds
for it in reverse: `--accent` must never appear anywhere a lamp colour would be the
honest choice instead (never inside `Lamp`, `LampBadge`, `DonutChart`, or `OutcomeCount`

- verified as of the round below).

**Lush Forest (round-3 dashboard-polish, 2026-08-08).** `--accent` was originally an
indigo, chosen specifically to sit far from every lamp hue. This round repointed it at
the "Lush Forest" palette - four raw swatches, `--forest-deep` (`#2e6f40`), `--forest-mint`
(`#cfffdc`), `--forest-mid` (`#68ba7f`), `--forest-ink` (`#253d2c`) - with `--accent` /
`--accent-text` / `--accent-wash` now aliasing `-deep` / `-ink` / `-mint` respectively,
exactly the same three-token shape as before.

**Known, accepted tradeoff - not an oversight.** `--forest-deep`/`--forest-mid` sit only
~21° apart from `--lamp-jade` on the hue wheel - both read as "green" at a glance, and
for deuteranopia/protanopia colour-blindness specifically (which compress exactly this
part of the spectrum) the two read closer still. This was flagged during review as a
real risk of visual confusion with jade's meaning ("call closed successfully"), and a
muted alternative was proposed and costed - desaturating/darkening toward roughly
`#2c5839` (same hue, pulled down in saturation and lightness) to put more perceptual
distance between the accent and jade while keeping the same "forest" identity. The
tradeoff was put to the product owner explicitly, with the risk stated plainly, and the
decision was: **keep the exact requested hex values - `#2E6F40`, `#CFFFDC`, `#68BA7F`,
`#253D2C` - unmuted, as specified.** This is a deliberate call made with the risk in
view, not a gap that slipped through. What _is_ still true and still holds to the
letter: `--accent` does not appear inside `Lamp`, `LampBadge`, `DonutChart`, or
`OutcomeCount` (checked directly) - the rule above is not violated, only sailing closer
to it than the indigo it replaced ever did. If a colourblind-accessibility audit later
surfaces real confusion in practice, that is the trigger to revisit this, not a
hypothetical hue-wheel measurement alone.

Current uses, all on `/app` only:

- `.canvas-tint` - a soft radial wash behind the dashboard's cards (`AppShell`, scoped to
  `pathname === "/app"` only). Now a mint wash rather than a lavender one.
- `AreaChart`'s point markers - the volume trend is not disposition data, so lamp colours
  were never right for it either; `--accent` replaces the previous plain grey dots.
- `NextMoveCard`'s icon badge (`app/(app)/app/page.tsx`) - the dashboard's one CTA card.
- `Button variant="primary"` (`.btn-glass-primary`) and its hover pulse ring, but _only_
  inside `.app-font-scope` - i.e. only on `/app/*`. `Button` is one shared component
  rendered on marketing and auth too (see §13), so the override is a CSS descendant
  selector (`.app-font-scope .btn-glass-primary`, `globals.css`) rather than a change to
  `button.tsx` itself: marketing and auth keep the monochrome CTA untouched, and only a
  button actually nested under the dashboard's font-scope wrapper picks up forest green.
  `--forest-mid` has no solid-fill role of its own (too low-contrast against both white
  and `--surface` to carry text or an icon) - it appears once, as that hover ring's
  colour, where translucency with no text on it is the whole job.
- **New this round:** `.header-glass` (`globals.css`) - the dashboard's sticky top bar,
  previously plain frosted white regardless of page, now tinted `50% --surface-raised /
50% --accent-wash` before the usual glass alpha. `.header-glass` needed no
  `.app-font-scope` scoping trick, unlike `Button` - its only two call sites
  (`components/layout/app-shell.tsx`) are both `/app/*`-exclusive. Deliberately **not**
  extended to the active-state indicator on `PrimaryNav`, `AppTabBar`, the shared `Tabs`
  component, or the Settings sub-nav - see §14 for why.

If you add a colour to this product, check it against the rule above first - and if it's
genuinely decorative, not state, it belongs in `--accent`'s job, not a new token.

---

## 3. Free-axis choices

**Type.** Archivo (variable, `wdth` 112) for display, Inter Tight for body, JetBrains
Mono for all machine-produced values. Only Archivo is preloaded. The mono rule is
load-bearing: it is how a user learns at a glance what came from the system versus what
came from a person. Enforce it.

**The `Wordmark` is live text, not SVG paths.** The brief asked for inline SVG. Real text
inherits `currentColor`, scales with the type system, stays selectable, and is read
correctly by a screen reader; outlining it would lose all four and gain nothing. `Mark`
_is_ inline SVG, because it is geometry.

**Icons.** Phosphor, `weight="light"` for decorative and `"fill"` for active nav state.
One set, no mixing.

**Page texture.** A single masked draughtsman's grid (`.grid-field`). Not a gradient, not
a mesh, not a blob. Used behind the hero, the auth card, and the closing CTA.

**Section rhythm.** Lamped hairline rules between home-page sections rather than
alternating background bands.

**Dashboard "Outcome distribution."** This round replaced the single large lamp-dot
visual - one dot standing in for the whole distribution - with a legend/count row
(closed / retry / needs a person) as the primary visual, per user request. At the
volumes this page usually shows, one dot reads as far more definitive than the sample
backing it; three counts, each behind its own lamp-coloured chip, say the same thing
without the false precision. A zero count still renders, dimmed to `off` - "0 need a
person" is real information. See `OutcomeCount` in `app/(app)/app/page.tsx`.

---

## 4. Light-mode contrast

The pure lamp colours do not all clear 4.5:1 against a light surface, so there are two
sets of tokens:

- `--lamp-*` - the dot itself, always the pure colour.
- `--lamp-*-text` - anything setting _text_ in a lamp colour.

`LampBadge` uses both at once: a `color-mix` surface, a `color-mix` border, `-text` for
the label, and the pure colour for the dot. Never set text in a raw `--lamp-*`.

---

## 5. Where the UI is ahead of the API

This table is a living gap-map, not a one-time note - update the row the moment a surface
moves from fake to real, the same turn as the code change. Auth, org-scoped persistence,
suppression enforcement, team, API keys, and provider (Twilio/Plivo) credential storage
have all shipped since this section was first written; billing and calling-window
enforcement have not, and are still fake if left undocumented here.

| Surface                                                | Data                                                                                                                                                               |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Overview, runs, escalations, contacts                  | **Real.** Org-scoped, persisted in Postgres. Escalations are outcomes with `disposition === "escalated"`, contacts are grouped from call history.                  |
| Suppression list                                       | **Real.** `public.suppressions`, org-scoped and RLS-enforced, and it's the actual table `check_dial_allowed()` checks before every dial (ISSUES.md #3).            |
| Auth, team, profile                                    | **Real.** Supabase auth, real invitations sent via email, real role-based permissions (`app/auth/permissions.py`).                                                 |
| API keys                                               | **Real.** Org-scoped, hashed at rest, shown once.                                                                                                                  |
| Integrations (Twilio, Plivo)                           | **Real** credential storage only. Connecting a number does not yet change which number a run dials from - that needs the voice-agent platform (`FEATURES.md` F17). |
| Campaign editor - name, goal, fields, region, language | **Real.**                                                                                                                                                          |
| Campaign editor - calling window, retry policy         | **Local.** `localStorage`, per campaign id - the create-campaign payload never sends these. `NotWiredNotice` says so on the panel.                                 |
| Safety pane - calling window                           | **Not enforced.** The fields save, but no guard in `check_dial_allowed()` reads them (ISSUES.md #20).                                                              |
| Billing                                                | **Partly real.** Usage numbers are the same limiter every run passes through. No payment processor is connected - upgrade/downgrade aren't wired.                  |
| Notifications                                          | **Not wired.** Forms validate, then say nothing was sent, via `AuthNotice` / `NotWiredNotice`.                                                                     |

The rule applied throughout: **never show a success state for something that did not
happen.** A fake "check your inbox" leaves someone waiting for an email that will never
arrive, and they blame the product rather than the gap.

`Stop run` was the sharpest case, and it's why the button no longer exists: it claimed
to stop calls that were, in fact, still being placed - the service has no cancel
endpoint, and the control's own confirmation dialog and success toast contradicted each
other about that within the same flow. Removed entirely rather than reworded, since
"Pause run" (pauses _polling_ only, and says so) already covers the honest version of
what a person wants from this button. See `ISSUES.md` #39.

---

## 6. Field types: five in the editor, four on the wire

The editor offers `string | number | boolean | date | enum`. The service accepts
`string | number | integer | boolean`.

`date` and `enum` map to `string`, with their constraint folded into the field
description - and the description _is_ the extraction instruction, so "one of: onsite,
hybrid, remote_only" genuinely constrains the answer. See `lib/campaign-fields.ts`.
Better than dropping two useful types from the editor.

---

## 7. React 19 patterns

`eslint-config-next` enables `react-hooks/set-state-in-effect`, which flags the common
"read localStorage in an effect, then setState" shape. The codebase avoids it three ways:

1. **`lib/hooks/use-external-store.ts`** - `useSyncExternalStore` over `localStorage` and
   `matchMedia`. Correct on first paint, SSR-safe, no cascading render. Use this for any
   new browser-state read.
2. **Render-phase derivation** - `useTypewriter`, `useRunPoll`, `StatusBoard`, and the
   hero's lamp sequence compare a key during render instead of resetting in an effect.
3. **Two justified `eslint-disable`s**, both genuine external-system reads:
   the campaign editor's one-shot `sessionStorage` handoff (which must also _clear_ it),
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

1. `calle-ai` in `requirements.txt` / `pyproject.toml` - the real distribution name; the
   install breaks otherwise.
2. `CALLE_API_KEY` as an environment variable - the brief explicitly permits this. Every
   _label_ says "Voice API key".
3. `"call-e/customerMetadata"` in `orchestrator.py` - an API payload key. Changing it
   would break extraction.

**Left in place, for you to decide:** `DEVPOST_STORY.md` at the repo root is entirely a
hackathon artefact. Deleting authored narrative felt like your call rather than mine - but
it is the one remaining hackathon reference in the repo.

**Still worth doing:** check the vendor's terms for an attribution requirement. Most
infrastructure vendors permit white-labelling on paid plans but require it on free tiers.
Five-minute check, avoids a takedown.

---

## 10. Commercial numbers are unset on purpose

Everything in `lib/pricing.ts` that is a price, an included volume, or an overage rate is
`null`, and renders as a visible `TODO` chip. A wrong number on a pricing page is worse
than an obviously missing one - nobody signs off a placeholder, but they will quote one
back at you.

The comparison and ROI calculators are different: those are **editable estimate inputs**
with real defaults, clearly labelled as the buyer's assumptions rather than our claims.

Fill in the checklist at the top of `lib/pricing.ts` and the whole page is correct - no
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
public URL - worth knowing before debugging an opaque "fetch failed".

---

## 13. Glassmorphism: scope and a deliberate exclusion

**Product-wide, not `/app/*`-only.** The `.panel-glass`/`.panel-glass-sunken`/`-flat`/
`-interactive` treatment (`globals.css`; see `ISSUES.md`'s iteration-8 "Monochrome-glass
panels" entry for its introduction) is a product-wide decision. `Panel` and `Button`
render through it everywhere they're used, including the marketing site and the auth
pages, by product decision - contrast-checked as safe against those pages' light
backgrounds. If an earlier note here read as confining it to the dashboard, that was
wrong; nothing about the treatment is `/app/*`-specific.

**Deliberate exclusion: shared dialogs stay opaque.** `components/ui/dialog.tsx`
(`Dialog`, `Sheet`) does not take the glass treatment, and should not. A dialog
composites over its own dark overlay, not the page behind it - glass there measured
roughly 3.68:1 for `--text-mute`, short of the 4.5:1 WCAG AA bar `ISSUES.md #47` exists
to hold across the product. This is a considered exclusion, not an oversight: a future
"finish the glass pass" effort should leave `dialog.tsx` alone. (One call site briefly
applied `panel-glass` to a `Dialog` anyway - `components/app/invite-dialog.tsx` - and
the fix was to remove the class, not to add glass support to `dialog.tsx` itself, since
the same contrast math fails there too.)

---

## 14. Lush Forest, applied strictly - what got tinted and what stayed neutral

A follow-up pass audited every `/app/*` surface for the old indigo (none left - `--accent`
was repointed at the token level, not hardcoded per call site, so nothing needed a
second edit) and for plain-neutral surfaces where the forest palette would now read as
more consistent. One surface changed; several were considered and deliberately left
alone, each for a reason found directly in the surrounding code, not a guess.

**Changed: `.header-glass`.** The dashboard's sticky top bar read as a plain frosted-white
bar sitting on an otherwise green-tinted page - see the entry in §2 above for the exact
tint recipe and contrast numbers.

**Left neutral, on purpose:**

- **Active-state indicators on `PrimaryNav` (desktop header nav), `AppTabBar` (mobile tab
  bar), the shared `Tabs` component (`components/ui/disclosure.tsx`), and the Settings
  sub-nav (`app/(app)/app/settings/layout.tsx`).** All four mark "you are here" the same
  way - a weight/colour shift to `--text`, never a filled colour - and two of them say so
  explicitly in their own comments: `PrimaryNav`'s escalation badge is "the only
  persistently-coloured element in the header, because it is the only thing in the
  product that needs immediate human action," and `Tabs` marks its active edge with "a
  hairline rule... not a filled pill: the rest of the design separates with hairlines,
  and a pill here would be the only pill on the page." Recolouring just one of these four
  (the Settings sub-nav was the closest candidate, since it already uses the same
  `after:bg-surface-inverse` underline mechanism as `Tabs`) would both contradict a
  documented design decision and create a new inconsistency - an underline that's green
  in Settings and monochrome everywhere else `Tabs` renders the identical pattern. Left
  all four exactly as they were.
- **`.hero-flow` / `.card-flow`** (the volume-trend hero card, `NextMoveCard`'s
  container). These carry real data - `AreaChart`'s stems, dots, and axis labels sit
  directly on top, contrast-calibrated against the existing grey gradient. Tinting the
  card risks the same problem the primary-CTA rule exists to prevent in reverse: cosmetic
  colour interfering with reading real numbers. Same reasoning the task brief itself gave
  for `Panel`'s default background.
- **Table/data chrome** - `DataTable`'s `<thead>`, `contact-grid.tsx`'s grid header,
  `runs/[id]`'s results table header (all `bg-surface-sunken`). Consistent with the
  product's existing "data stays monochrome" rule (`CodeBlock` uses weight and dimming,
  not hue; charts are drawn in `--rule-strong`) - a tinted header row over untinted body
  rows would read as a hierarchy signal that isn't there.
- **Skeleton loading placeholders.** A tinted skeleton would risk being misread as an
  already-loaded, "successful" state rather than a pending one.
- **`:focus-visible` outline.** Product-wide, not `/app/*`-specific, and load-bearing for
  accessibility - stays `--text`, the highest-contrast choice available on every surface
  it needs to work on, including ones this palette doesn't touch.
- **`CreditBalance`'s pill** (`app-shell.tsx`). Already carries its own semantic colour -
  brass under 20% remaining, flare at zero, via the lamp tokens - reporting a real budget
  state. Layering a second, unrelated colour signal (decorative accent) on the same small
  pill would blur two different meanings into one swatch.
- **Popover/`DropdownMenu` chrome.** Shared, product-wide components (like `Panel` and
  `Button` before their explicit `/app/*` overrides) with no call site asking for a
  scoped exception yet - left alone rather than guessed at.
