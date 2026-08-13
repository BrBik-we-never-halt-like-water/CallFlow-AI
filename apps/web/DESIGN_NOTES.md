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

- The primary CTA is **`--primary`** (CAL-4's Signal indigo) everywhere, marketing and
  `/app/*` alike. It is brand-coloured, and the rule above is what constrains *which*
  colour: indigo sits 110° from jade, 162° from brass and 117° from flare, so a lit lamp
  still reads as state rather than as brand. It was monochrome
  (`--surface-inverse` on `--text-inverse`) off `/app/*` until 2026-08-10 - see §20.
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

> **Superseded by the CAL-4 indigo restore (see the section at the end of this file).**
> The Lush Forest round described immediately below is history, not current state.
> `--forest-*` no longer exists; `--accent`/`--accent-text`/`--accent-wash` are aliases
> of `--primary`/`--primary-ink`/`--primary-wash`. The accepted-tradeoff discussion
> below is retained because it is the reasoning that the restore acts on, not because
> the palette it describes is still in the product.

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
  `.app-font-scope` scoping trick, unlike `Button` - all of its call sites
  (`components/layout/app-shell.tsx`: the top bar, the minimal-chrome top bar, and now
  the sidebar) are `/app/*`-exclusive. Deliberately **not** extended to the active-state
  indicator on `AppSidebar`'s nav, `AppTabBar`, the shared `Tabs` component, or the
  Settings sub-nav - see §14 for why. **Superseded by `.dark-chrome` as of the dark-
  theme-pivot chrome reskin - see §15.** `.header-glass` itself is left defined, just
  unused, in case `/app/*` ever needs a light-chrome path again.

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

- **Active-state indicators on `AppSidebar`'s nav (desktop sidebar), `AppTabBar` (mobile
  tab bar), the shared `Tabs` component (`components/ui/disclosure.tsx`), and the
  Settings sub-nav (`app/(app)/app/settings/layout.tsx`).** All four mark "you are here"
  the same way - a weight/colour shift to `--text`, never a filled colour - and two of
  them say so explicitly in their own comments: `AppSidebar`'s escalation badge is "the
  only persistently-coloured element in the sidebar, because it is the only thing in the
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
- **Popover/`DropdownMenu` chrome.** Shared, product-wide components (like `Panel` and
  `Button` before their explicit `/app/*` overrides) with no call site asking for a
  scoped exception yet - left alone rather than guessed at. **Superseded by §17** - that
  call site arrived (the user asked directly), and it turned out to be a font/color
  inheritance bug (`ISSUES.md` #49, #69) as much as an unmade design decision.

---

## 15. Dark-theme pivot: the chrome reskin, and the token-inheritance trick that made it a one-class change

The dark-theme foundation task (tokens + sidebar footer) deliberately left `AppSidebar`,
`AppTopBar`, `MinimalTopBar`, and `AppTabBar` rendering their existing light chrome, since its
own file scope named only the sidebar footer addition. That was flagged as an open gap - a
round where dashboard/campaigns/runs go dark while the chrome around them stays light would
look actively broken, not just transitional - and closing it is this entry's subject.

**`.dark-chrome` (`globals.css`), not a second `.header-glass`.** Every chrome child - nav
links, `SidebarOrgSwitcher`'s skeleton, `Wordmark`'s hardcoded `text-text-dim` "AI" suffix,
the escalation badge's inline `var(--lamp-flare)` - was already styled
entirely in *generic* tokens (`--text`, `--text-mute`, `--surface-sunken`, `--lamp-flare`, ...).
Rather than hand-editing every one of those call sites to a `dark-` prefixed token, `.dark-
chrome` re-declares the generic custom properties themselves, scoped to whichever element
carries the class. CSS custom properties inherit through the DOM regardless of which component
drew which node, so every descendant's existing class picks up the dark value automatically -
the identical mechanism `.app-font-scope` already uses to flip `--font-sans` to Ubuntu for all
of `/app/*`, just scoped to one chrome element instead of the whole dashboard. Net result: zero
text-colour edits in `app-shell.tsx` or `app-nav.tsx` - only a class swap (`header-glass` /
`bg-surface-raised` -> `dark-chrome`) on four elements. `.dark-panel-glass` (the floating-card
material for the D2-D4 page rebuilds) picked up the same re-scoping block for the same reason,
proactively, so those tasks get legible children for free too.

**Radix portals make this safe, not accidentally leaky.** `DropdownMenu`/`Tooltip` content
renders outside the triggering element's DOM subtree (portaled to `document.body`), so
overriding tokens on `<aside>`/`<header>`/`<nav>` cannot reach the org-switcher dropdown or a
tooltip bubble - they keep reading light, consistent with this file's existing "leave popover
chrome alone" call (§14) without needing a fresh decision to preserve it.

**Superseded by §17.** This paragraph's "keep reading light... without needing a fresh
decision" framing held until the user asked, twice, for exactly that fresh decision.
`DropdownMenu`/`Popover`/`Dialog` (not `Tooltip`/`Select` - see §17) now portal inside
`.app-font-scope` on purpose and pick up real dark styling there.

**Opaque, not translucent - a corrected assumption, not a taste call.** `.dark-panel-glass`
(content cards) stays translucent (42% as of the later card-glassmorphism tuning pass - see
`--dark-glass-surface`'s own citation in globals.css for the current number and its contrast
math), matching every other glass surface in this file. The
chrome does not, for a reason specific to this transitional moment: D2-D4 haven't landed, so the
content that actually scrolls behind these `sticky` bars today is still light. Computing the
composite both ways - against the eventual dark page canvas *and* against today's real light
backdrop - showed translucency pulls `--dark-text-mute` down toward the 4.5:1 AA floor
specifically in the direction that only shows up before the rest of the pivot lands (4.69:1 at
88% opacity against today's backdrop, vs. a stable 6.6:1 either way once fully opaque). Fully
opaque removes the variable entirely rather than threading a needle that moves as later tasks
land. It also happens to match the plan's own screenshot analysis, which calls the reference
sidebar a "solid dark surface" - the two reasons agree, not by coincidence.

**One real bug caught in the process: the escalation badge's white count text.** The first
`--dark-lamp-flare` pick (`#c15f4d`) only gave white badge text 4.19:1 against it - below AA,
and worse than the light theme's own already-thin 4.66:1 for the identical white-on-`--lamp-
flare` pair. Darkened one step (`#b45342`, OKLCH L 0.60 -> 0.56) to 4.93:1, while the dot itself
still clears 3:1 against the opaque chrome background as a small decorative mark. The other four
`--dark-lamp-*` dots were not touched - only flare carries solid white text on top of it anywhere
in this chrome.

## 16. Dashboard dark rebuild (D2) - a stacking-context bug worth knowing about before D3/D4

`page.tsx`'s own file scope can't touch `app-shell.tsx`, so the page bleeds its own
`.dark-canvas` backdrop into `<main>`'s padding with an absolutely-positioned, negative-inset
sibling (`-inset-x-4 -inset-y-6 sm:-inset-x-6`, `-z-10`) rather than asking `AppShell` to add the
class itself. The generic-token re-scope (`--text`, `--surface-raised`, the ten `--lamp-*`
pairs, ...) is applied the same way `.dark-chrome`/`.dark-panel-glass` do it (§15), but inline via
a `style` object on the page's own root instead of a new global class, since the only thing
outside a `.dark-panel-glass` card on this page is the header row's buttons and
`ConnectionBanner` - not enough surface area to justify a new class in `globals.css` for a single
page task.

**The bug, for whoever builds D3/D4 next.** The negative-`z-index` backdrop rendered correctly
almost everywhere, except for a band exactly the height of the page's own header row, which
showed `.canvas-tint`'s light mint wash bleeding through *in front of* the dark backdrop. Root
cause: `template.tsx`'s `.page-enter` wrapper (the route-transition fade, `animation: page-enter
… backwards`) animates `transform`, and a `transform` value other than `none` creates a stacking
context for as long as it's active - which is exactly the ~240ms (`--dur-base`) after every
navigation, confirmed by forcing the backdrop's `z-index` to `999` (the mint disappeared
entirely, proving it was a paint-order issue, not a geometry one) and by disabling the animation
via `prefers-reduced-motion` emulation (same result, cleanly). Without an explicit stacking
context of its own, this page's backdrop-plus-content pairing had its ordering decided by
whatever ancestor happened to be the nearest real stacking context at that instant, which
briefly became `.page-enter` on every route change. **Fix: `isolate` on the page's own wrapper**
(`relative isolate min-h-full`), so the backdrop's negative `z-index` is always resolved against
its one sibling and never depends on what an unrelated ancestor's animation is doing. Any future
page that bleeds its own full-bleed backdrop this way (rather than through a class on `AppShell`)
needs the same `isolate`, not just the negative inset.

**Chart colour, not chart mechanism.** `area-chart.tsx` (`components/ui/`) gained a `tone?:
'light' | 'dark'` prop rather than being hard-converted to dark colours - it's used nowhere else
today, but a colour-only prop keeps it honestly reusable rather than dark-only by accident, and
keeps the diff a colour swap, not a rebuild, per the plan's own instruction. `dark` swaps the
point markers and the "today" callout pill from `--accent`/`--surface-inverse` to `--dark-accent`
or with a soft `drop-shadow` glow (the plan's "glowing chart" ask) - the pill's text flips from
white to `--dark-bg` alongside it, since white-on-solid-`--dark-accent` only clears ~2.4:1 while
near-black-on-it clears ~8.7:1. Picked up `usePrefersReducedMotion` for the dot-entrance
animation while in there, which the previous version didn't gate on that preference.

**The primary button's `--accent` tint, left alone on purpose.** `.app-font-scope
.btn-glass-primary` already tints every primary `Button` on `/app/*` with `--accent` (light
theme's forest green - DESIGN_NOTES §2's "extend `--accent` into primary buttons/CTAs" call).
`--accent` and `--dark-accent` are deliberately independent tokens (CLAUDE.md §4 #10), so that
tint doesn't flip on a dark page by itself. Rather than edit the shared `Button`/`globals.css`
rule (out of this task's file scope, and shared with every other `/app/*` page mid-edit by other
tasks this round), every primary `Button` on the dashboard gets a local inline `style` override -
`background: color-mix(in oklab, var(--dark-accent) 92%, transparent)`, text flipped to
`--dark-bg` for the same contrast reason as the chart's pill above. Still token-only (no raw
hex), just applied per-button instead of through the shared class. D3/D4 should expect the same
green-on-primary-button seam if they don't apply an equivalent override.

**Status color, applied per the plan's resolution (§ shared plan doc, "Status color handling"):
label first, color as a small secondary accent.** The "Needs a person" list re-uses `LampBadge`
as-is (a small dot plus a low-opacity tinted pill, never a solid fill) for its urgency indicator,
and the "Recent calls" table renders outcome as a small `Lamp` dot *plus* the plain-text label
right next to it - color never carries the row's meaning alone. This is also the first real
dark-mode render of `--dark-lamp-off`/`-ice`/`-brass`/`-jade` (only `-flare` had shipped before,
via the escalation badge) - all four read fine at a glance against `.dark-panel-glass` cards in
manual testing; none needed the kind of value correction `-flare` did in §15.

**"Review", not "Takeover".** The plan's own dashboard-card spec suggested a `Takeover` action;
this product has no live call-transfer/takeover feature anywhere, and CLAUDE.md §4 #9 rules out
labelling a link with a verb it can't perform. Each "Needs a person" row links to
`/app/escalations` (the same destination as the card header's own "See all N") labelled "Review
→" instead - an honest link to the one place the real actions (call back, reassign, mark
resolved) already live, not a fabricated per-row deep link (there's no per-outcome id yet to link
to, `ISSUES.md` #7).

**A fixed "outbound" glyph, not a direction toggle.** The reference's recent-calls row has a
small in/out arrow per call. CallFlow only ever dials out - there is no inbound leg - so every row
gets the same `PhoneOutgoingIcon` rather than a direction indicator with only one direction to
show, which would silently imply a capability (inbound calls) this product doesn't have.

**One pre-existing Tailwind gotcha, fixed while it was found:** the campaign-name pill's
`truncate` was applied directly to `Tag`'s own `inline-flex` root - Chrome clips the overflow
correctly there but does not reliably paint the `…` ellipsis for text that's a direct child of a
flex container. Moving `max-w-32 truncate` onto a `block`-level `<span>` *inside* the pill (the
standard "truncate needs a block box of its own inside a flex row" fix) resolved it; worth
remembering for `Tag` composed inside any other flex row in D3/D4.

## 17. Popover chrome joins the dark pivot - reversing §14/§15's "leave it alone" call

§14 left `DropdownMenu`/`Popover` chrome untinted "with no call site asking for a scoped
exception yet." §15 went further and treated the fact that Radix portals these components to
`document.body` - outside every dark-scoped element's DOM subtree - as a *feature*: proof the
"leave popover chrome alone" call needed no active maintenance, since there was structurally no
way for dark tokens to reach them. Both were reasonable calls at the time. Neither survived the
user asking, twice, for the org-switcher dropdown, the Team popover, and the invite dialog to
read as part of the same dark, purple-tinted product as everything around them - the missing
"call site" §14 was waiting for.

**First fix attempt was itself broken - worth recording exactly why.** The obvious fix looked
like a new `.dark-overlay` class, applied directly to `DropdownMenuContent`/`PopoverContent`/
`Dialog`'s content, re-scoping the same `--text`/`--surface-raised`/etc. tokens `.dark-chrome`
already does. Shipped, and the user's very next message was a screenshot of the invite dialog
with no visible background, border, or text at all - only the footer buttons, which carry their
own styling independent of the container, were visible. The bug: `.dark-overlay` referenced
`var(--dark-text)`, `var(--dark-surface)`, and friends - but those raw palette values are
themselves declared inside `.app-font-scope` (the `/app` layout's own wrapper `<div>`), not at
`:root`. §15's own "portals render outside this element's DOM subtree" observation applies just
as much to `.app-font-scope` as it does to `.dark-chrome` - a portal is a sibling of
`.app-font-scope`, not a descendant, so it never inherited the raw dark tokens either. Setting
`--text: var(--dark-text)` when `--dark-text` itself resolves to nothing collapses every
property built on it to its initial value - `transparent` for a background, invisible for text.
The same gap `ISSUES.md` #49 already flagged for the *font* was quietly also blocking the
*color* fix, for the identical reason.

**Real fix: move the portal, not just the tokens.** `usePortalContainer()`
(`lib/hooks/use-portal-container.ts`) resolves `document.getElementById('app-font-scope')` and
passes it as the `container` prop on `DropdownMenu`/`Popover`/`Dialog`/`Sheet`/`Select`'s Radix
`Portal`, so the portaled content becomes a genuine DOM descendant of `.app-font-scope` and
correctly inherits both the font class (closing #49 for these five components specifically, not
universally - see below) and the raw `--dark-*` tokens `.dark-overlay` depends on.
`useSyncExternalStore`, not an effect + `setState` - the container is stable for the whole
mounted lifetime once the DOM exists, so there's nothing to subscribe to, only a value that must
not be read during SSR (`react-hooks/set-state-in-effect` is an error on the naive version; see
`lib/hooks/use-external-store.ts` for the same reasoning already applied to
`localStorage`/`matchMedia`).

**The gradient, not a flat fill.** The ask was specifically "the same purple gradient as the
main content", not just "make it dark" - so `.dark-overlay`'s `background` is `.dark-canvas`'s
own radial-gradient formula verbatim, not a flat `--dark-surface` fill or `.dark-chrome`'s
glass/blur treatment (deliberately neutral there so nothing behind its translucency reads as
coloured chrome - the opposite of what's wanted for an opaque popover). Percentages in a
`radial-gradient()` are relative to the element's own box, so a small popover naturally gets a
tighter, more concentrated version of the same top-anchored purple glow rather than a literal
crop of the page-wide one - same recipe, correctly proportioned per surface, no new constant to
maintain.

**Not universal - `Tooltip` and `Select` are the genuine exception.** Both are shared with a
light-themed marketing page (`pricing-table.tsx`'s row hints; `demo-form.tsx`'s selects) -
grepped every import site of all five components before touching any of them, specifically to
avoid repeating this task's own first mistake in the opposite direction (breaking a light page
to fix a dark one). Both get the portal-container fix unconditionally (harmless everywhere, and
it closes the same font gap there) but only add `.dark-overlay` when
`container.id === 'app-font-scope'` - i.e., only when actually rendered inside `/app`
(`isAppScopeContainer()`, `lib/hooks/use-portal-container.ts`). **Correction, §18: `Tooltip` was
initially left untouched** on the theory that nothing had reported a problem with it - the very
next ask was the sidebar's own collapsed-state tooltips, so it now follows the identical
conditional pattern `Select` already did.

## 18. Finishing the dark pivot: chrome background, Toast, sidebar dividers, the profile route

Four more surfaces, found the same way §17's were - real use, real screenshots, in rapid
succession rather than one planned sweep.

**`.dark-chrome`'s background: opaque purple gradient, not translucent neutral glass.** §15
made a considered, documented call to keep the sidebar/topbar/tab-bar ("the taskbar") neutral -
"no purple mixed into its own resting fill" - specifically so nothing behind its translucency
would read as coloured chrome. The user asked directly for the opposite: the same purple,
gradient-lit look as the content column and the popovers, not a neutral black surface next to
them. `.dark-chrome`'s `background` is now `.dark-canvas`'s exact radial-gradient formula,
verbatim - same reasoning as `.dark-overlay` (§17), same recipe, correctly proportioned per
element regardless of its shape (a tall sidebar and a wide top bar both anchor the same
top-centre glow, just stretched to their own box). `backdrop-filter` and its two dedicated
fallback blocks (`@supports not (backdrop-filter)`, `prefers-reduced-transparency`) are removed
entirely, not just left inert - an opaque background has nothing left to blur, and a
feature-detection fallback for a feature no longer in use is dead code, not defensive code.

**Sidebar section dividers: shown expanded, hidden collapsed.** `AppSidebar`'s four
`border-b`/`border-t border-rule` hairlines (logo row, org-switcher, footer nav, collapse
button) rendered unconditionally regardless of `collapsed` state. Full-width, they read as
intentional section breaks; compressed to the collapsed rail's icon-only width, the same
hairlines just look like stray, unexplained cuts across the icon column. Each now switches to
`border-transparent` when `collapsed` - keeping `border-b`/`border-t` itself (not removing the
class) preserves the exact same spacing in both states, so toggling collapsed never shifts
anything vertically, only the line's visibility.

**Toast joins the dark pivot too - via `createPortal`, not a `container` prop.**
`ToastProvider` is mounted at the true root layout (`app/layout.tsx`), shared by every route,
and its `Viewport` was never inside `.app-font-scope` - not portaled there by default, in fact
not portaled anywhere by default, since `@radix-ui/react-toast` (confirmed against its own type
exports) has no `Portal` primitive at all, unlike Dialog/Popover/DropdownMenu/Select. A toast
fired from `/app` rendered with the light `:root` defaults regardless of the page around it,
same root cause as everything else in §17. Fixed with a plain `createPortal(viewport,
container)` instead of a Radix `container` prop - same destination
(`.app-font-scope`/`document.body`) as everything else, just wired by hand since the library
doesn't offer the prop here. `ToastItem` applies `.dark-overlay` conditionally, the same
`isAppScopeContainer()` check as `Select`/`Tooltip` - a toast can fire on a light marketing or
auth page too. **Also changed alongside it:** the success tone's indicator is a filled
`CheckCircleIcon` (`text-lamp-jade-text`) instead of a plain `Lamp` dot, per direct request -
info/warning/error keep the dot. Not extended to the other three tones without being asked;
a partial icon set was the actual request, not a hint toward a fuller redesign.

**`/app/profile` never had `.dark-canvas` applied to its content at all.** Distinct root cause
from the other three, and the most severe of this round's four: `/app/profile` is `AppShell`'s
one "minimal chrome" route (`MINIMAL_CHROME_ROUTES`, a single-column layout with `MinimalTopBar`
and no sidebar), which is a genuinely different return branch in `AppShell` - not a portal
escaping a scope, but a wrapper `<div>` that plain forgot to carry the `.dark-canvas` class the
normal-route branch's content column has always had. Every generic-token component on the page
(`Panel`'s `panel-glass`, `Button`, `Input`) was already written correctly against
`--surface-raised`/`--glass-surface`/`--accent`/etc. - none of them needed touching, because
`.dark-canvas` re-scopes exactly those tokens. Adding the one class to the minimal-route
wrapper (`MinimalTopBar` already carried its own `.dark-chrome`, unaffected by nesting inside
`.dark-canvas` now) fixed the entire page's header, text, panels, and buttons in one line -
proof that the token-inheritance mechanism §15 built works exactly as designed, once actually
applied.

## 19. Toast's fix from §18 didn't survive contact with `/accept-invite`, a pending badge, a welcome modal, and the viewer-role UI sweep

**Toast's `createPortal` fix (§18) is superseded - it depended on an element that doesn't
exist on every page it needs to run on.** The "Joined" toast fired from
`/accept-invite/[token]` still rendered light. Root cause: that route is in the `(auth)`
group, which never renders `.app-font-scope` at all - it's exclusively rendered by
`(app)/app/layout.tsx`. §18's fix portaled `Viewport` to `.app-font-scope` or fell back to
`document.body`, but the fallback still applied `.dark-overlay` only when
`isAppScopeContainer()` said so - and on a page with no such element anywhere in the DOM,
it never does, so the fallback path was always light. There was nothing to portal *into*.

**Fix: make Toast self-contained instead of dependent on an ancestor.** New
`.toast-dark-overlay` class in `globals.css`, applied unconditionally in `ToastItem`
regardless of what page fired it. Unlike every other dark-mode class in this file, it does
**not** reference `var(--dark-*)` - those tokens are deliberately declared only inside
`.app-font-scope` (§15's own citation), so referencing them from a class that must also work
where that scope doesn't exist would just resolve to nothing, the exact failure mode `#69`
already hit once (`ISSUES.md`). `.toast-dark-overlay` hardcodes the literal values instead -
the one deliberate exception in this codebase to "reference the token, never the hex,"
called out as such in the CSS comment beside it. With Toast no longer needing to be
positioned inside any particular scope for theming to work, the `createPortal` machinery
`ToastProvider` gained in §18 became pure overhead and was removed - `Viewport` renders
in place again, unchanged from before §18 for positioning purposes (`position: fixed` isn't
affected by DOM nesting).

**Pending badge for un-accepted invitations.** The Team member list showed a role tag and a
Revoke button for a pending invite with nothing marking it as pending - indistinguishable at
a glance from an active member. `PendingRow` now renders a plain, neutral `<Tag>Pending</Tag>`
ahead of the role tag - not a lamp colour. Lamp colours are reserved for call-state and
nothing else (CLAUDE.md §4 #10); "pending" is an invitation-lifecycle label, the same class
`Tag` already exists for elsewhere (role tags, `Template`/`Custom` on campaign cards).
Revoke was checked against the backend and already fully invalidates the invitation on click
(`invitations_repo` deletes the row; a revoked token's accept page shows the standard
invalid-invitation state) - no code change was needed there.

**A one-time welcome modal for a freshly-accepted invite.** `accept-invite/[token]` now
writes `{role, orgName}` to `localStorage` (`PENDING_WELCOME_KEY`) right after a successful
accept, before redirecting to `/app`. New `WelcomeModal` (mounted once, as a sibling of
`AppShell` in `(app)/app/layout.tsx`) reads that key via the existing `useStoredJson`
(`useSyncExternalStore`, not an effect + `setState` - same pattern as every other
`localStorage`-backed hook in this codebase) and shows a dismissible dialog naming the org
and the role the person was invited as. Dismissing clears the key, so it never shows twice
for the same invite. If storage is unavailable (private mode), the write is wrapped in a
try/catch that fails silently - the welcome message just doesn't show, which is the correct
degradation for a nice-to-have rather than a guarantee.

**Viewer role had a correct backend and an unenforced frontend.** `app/auth/permissions.py`
has always correctly denied every write permission to the viewer role, and every mutating
route correctly 403s a viewer's request - but nothing in the UI reflected that. A viewer
could open every editor, click every button, and reach every "Start"/"Save"/"Delete" control,
only to have the request rejected server-side - `ISSUES.md` #71 covers why that's a bug in
its own right (not just an inconvenience). Fixed by extending the same inline
`profile.permissions.includes('permission:string')` convention already used correctly
elsewhere (Contacts, Organisation's Team pane, the dashboard's Team preview) to every
remaining page and action component: `settings/safety`, `campaign-editor.tsx` (extended the
existing `readOnly`/`blocker` pair rather than adding a second disabled-state mechanism -
`readOnly = isBuiltIn || !canWrite`), `campaigns/page.tsx` + `campaign-card.tsx`,
`runs/page.tsx`, `runs/new/page.tsx` (the whole composer is blocked behind a
`NotWiredNotice` for anyone without `runs:start`, not just the final Start button - CSV
import/paste/edit read as actions a pure viewer shouldn't be invited to take even though
none of them persist until Start is clicked), `contacts/page.tsx`'s two Import CSV
shortcuts, the dashboard's four "Start a run" entry points (`PageTitle`, `NextMoveCard`, and
both outcome/run empty-states), `escalation-card.tsx`'s three action buttons (gated on
`escalations:resolve` - the dashboard's own condensed escalation preview uses a separate,
already-non-interactive `NeedsPersonRow` and needed no change), and the Organisation page's
logo `ImageUpload`, which had no `disabled` prop at all before this - `ImageUpload` gained
one, wired to `!canUpdate` (`org:update`), matching the org-name field beside it that was
already gated.

## 20. CAL-4 "Signal" indigo restored, opaque header, larger type scale (2026-08-10)

**What was actually wrong.** Not a regression in the usual sense - the colour never
arrived. CAL-4 designed a full indigo family (`--primary` `#3b2fd9` plus `-hover`,
`-active`, `-on`, `-wash`, `-edge`), registered it in the Tailwind `@theme inline`
bridge, and wired `Button variant="primary"`, `:focus-visible` and `::selection` to it.
The merge that brought `dev` onto that branch (`f30f5b9`) resolved the `globals.css`
conflict by keeping this file's older token layer wholesale and **appending** only
CAL-4's marketing surface rules. What survived was a bare `--primary: #3b2fd9` at the
bottom of the file with no siblings and no `@theme` registration, consumed by exactly
two `.card-feature` lines. Everything else fell back: marketing CTAs to near-black
(`--surface-inverse`), the light dashboard to Lush Forest green, the dark dashboard to
`#9333ea` violet. Three primaries, none of them blue.

**Decision.** One primary across the whole product, marketing and dashboard, light and
dark - which is what CAL-4 was designed as. This deliberately reverses two earlier,
separately-approved rounds: the Lush Forest repointing (§2 above) and the dark pivot's
move from indigo to unambiguous violet. Both were made under briefs that no longer hold.

**What changed:**

- `--primary` family restored to `:root`, ahead of the appended marketing block, and the
  duplicate declaration removed from that block - it sat *later* in the file and would
  have silently shadowed the canonical token.
- `--color-primary*` re-registered in `@theme inline`. This is the piece whose absence
  meant `bg-primary` / `text-primary-on` compiled to nothing rather than to a wrong
  colour - worth remembering as a failure mode, because it is invisible in review.
- `--forest-*` deleted. `--accent` / `--accent-text` / `--accent-wash` are now aliases of
  `--primary` / `--primary-ink` / `--primary-wash`, so every existing `--accent*`
  consumer (charts, `NextMoveCard`, `.canvas-tint`, `.header-glass`) resolves unchanged.
- `.btn-glass-primary` tints toward `--primary` instead of `--surface-inverse`, and gains
  real `:hover`/`:active` steps through `--primary-hover`/`--primary-active`. `Button`
  correspondingly drops `hover:opacity-90 active:opacity-80`: on a translucent fill an
  opacity fade washes the button toward its backdrop rather than deepening it.
- The `.app-font-scope .btn-glass-primary` override is **gone**, not retargeted. It only
  ever existed to give the dashboard a different primary from marketing's; with one
  primary it was setting the colour it already had. Likewise `btn-pulse-forest` folded
  back into `btn-pulse`, now tinted `--primary-mid`.
- `:focus-visible` and `::selection` moved from ink to `--primary`.
- Dark pivot: `--dark-bg-glow` and `--dark-accent` both `#4f46e5`, keeping the previous
  round's "one hue for the ambient glow and the interactive accent" decision intact at a
  new hue. `--dark-accent` stays a separate token from `--primary` rather than aliasing
  it, and the lightness gap is load-bearing - see below.

**Why the dark accent is a lighter indigo than the light one.** A solid button on the
near-black `/app` page has to clear two bars pulling in opposite directions: white label
text on the fill (≥4.5:1) and the fill against the page (≥3:1, the non-text bar - a
button nobody can find is not a button). `--primary` `#3b2fd9` dropped straight in gives
8.09:1 for the label but 2.52:1 against `--dark-bg`; it sinks into the page. `#4f46e5`
gives 6.29:1 and 3.24:1. That is the entire reason the dark scope keeps its own token.

**Contrast, recomputed rather than inherited.** Every number below is computed (WCAG
relative luminance, OKLab `color-mix` for composites), and the method was validated by
reproducing this file's own previously-published figures before being trusted for new
ones - the `#231436` canvas peak and the ~16.9:1 / ~7.2:1 / ~4.4:1 chrome composites
come back out exactly.

| | value | check |
|---|---|---|
| `--primary` | `#3b2fd9` | white on it 8.09:1; 7.35:1 as a focus ring on `--surface` |
| `--primary-hover` / `-active` | `#3226b8` / `#2a1f9e` | 9.98:1 / 11.74:1 - hover can never be the state that fails |
| `--primary-ink` (`--accent-text`) | `#221a6b` | 13.36:1 on `--surface` (forest ink was ~10.7:1) |
| `--primary-wash` (`--accent-wash`) | `#f0effd` | `--text-mute` 4.57:1 undiluted at `.canvas-tint`'s 0% stop |
| `--dark-accent` / `--dark-bg-glow` | `#4f46e5` | label 6.29:1, page 3.24:1; chrome composite text 17.06:1, dim 12.59:1, mute 7.29:1, flare dot 4.46:1 - each a shade better than the violet |

The wash is noticeably paler than the mint it replaces, and that is forced, not a taste
call: indigo is a low-luminance hue, so a tint of it darkens far faster than a tint of
mint at the same visual weight. `.canvas-tint` renders it undiluted at the gradient's 0%
stop where `--text-mute` can land directly on it, and `#eceafc` - only slightly deeper -
is already 4.39:1, under the AA floor. `#f0effd` is where it can sit.

**The tradeoff §2 flagged is now resolved.** That section recorded, as a known and
accepted risk, that `--forest-deep`/`--forest-mid` sat ~21° from `--lamp-jade` and read
as the same green at a glance - closer still under deuteranopia/protanopia - and that
this was "sailing closer to the rule than the indigo it replaced ever did". Indigo sits
110° from jade, 162° from brass and 117° from flare (recomputed here: the forest gap to
jade measures 14° by this file's OKLab math, tighter than the 21° originally recorded).
Ice is the nearest lamp at 20°, but ice is a dot on a monochrome panel and never a
filled button, so the two never appear as the same kind of mark.

### Same merge, two more casualties: the header's transparency and the type scale

Found while fixing the colour, and worth reading together with it - all three are the
same `f30f5b9` merge, and all three were invisible in a diff.

**The header was see-through because of an invalid CSS declaration, not a decision.**
`.glass` wrote `backdrop-filter: blur(var(--glass-blur)) saturate(1.4)`. On CAL-4
`--glass-blur` was a bare length (`16px`) and that composed correctly. On this side of
the merge `--glass-blur` is a *complete filter value* (`blur(24px) saturate(150%)`), so
the declaration expanded to `blur(blur(24px) saturate(150%)) saturate(1.4)` - invalid,
and dropped whole by the parser. The blur never applied. `background: var(--glass)` was
a separate declaration and survived at 72% opacity, so the site header rendered as a
translucent bar with none of the blur meant to keep text on it legible, and page content
read straight through the nav.

The header is solid `--surface-raised` when scrolled now. `.glass` had no other
consumers, so it and `--glass`/`--glass-edge` are deleted rather than repaired.

Note for anyone touching this: `--glass`/`--glass-edge` and
`--glass-surface`/`--glass-border`/`--glass-blur` are **two different token families**.
The second is the dashboard's panel and button material and is untouched. Two families
with nearly the same name is precisely what let a cross-branch collision through
unnoticed - if either is ever renamed, rename the dead-sounding one.

**The type scale was the older, smaller ramp.** Same loss as `--primary`. The structural
fault was not that the numbers were small but that `--t-h3`/`--t-h4` were *frozen* at a
single rem value while the display sizes scaled with the viewport: between tablet and
laptop the displays grew away from the headings under them and the hierarchy compressed,
so an h3 beside a 4.5rem display read as body copy. Every step is fluid again, and body
sizes go up a notch to follow (`--t-body` 1rem -> 1.0625rem, `--t-body-l` 1.125 ->
1.1875). `--t-small` and below are deliberately unchanged - metadata, data cells and
labels are already at their ceiling before a table stops reading as a table.

`--w-marketing` went 1180 -> 1280 in the same pass. At 1180 on a 1920 display the column
left ~370px of dead margin each side, and the eye judges the block before it judges the
font - the type alone would not have fixed "the sections look small". Body copy is
already constrained by its own `max-w-*`, so this spreads the layout without lengthening
a line of prose.

### Pricing pages removed (2026-08-10)

`/pricing`, the home page's pricing deck section, `PricingPreview`, `PricingTable`,
`CostComparison` and `PriceValue` are gone. The plans are undecided, and the pages were
rendering visible `TODO` chips where the prices belong - §12's "a wrong number is worse
than a missing one" rule was being honoured, but the honest missing number was still
shipping to visitors. The nav and footer links went with them. `FinalCta` sits on the
base ground, so dropping the section before it does not put two `sand` grounds together.

`lib/pricing.ts` is deliberately **kept whole** rather than trimmed to its two live
consumers (`PLANS` for the in-app billing page; `ROI_DEFAULTS` for the solution pages'
ROI calculator, which models the *buyer's* own human-call cost and never ours, and so is
unaffected by our own pricing being unset). It is the file where the numbers get decided,
and `FEATURE_MATRIX`/`PRICING_FAQ`/`ENTERPRISE` are written content the pages will want
back; its header now carries the checklist for restoring them. Treat those exports as
staged, not dead.

Two knock-ons worth knowing about:

- `SegmentedToggle` moved from `marketing/pricing-table.tsx` to `components/ui/`. It was
  never pricing-specific - it only happened to be first used by the billing-period and
  currency toggles - and `RoiCalculator` imports it.
- `lib/verticals.ts`'s lead-qualification goal script told callers that pricing "is
  published on the website". That script is read to real people on real calls, and it
  stopped being true the moment the page went, so it now says a specialist will confirm
  and explicitly does not send anyone looking. Anything that removes a public page should
  check that file - it is the one place marketing copy escapes the website.

### A note on screenshotting this site

`fullPage: true` is useless on the home page and will make you think sections are empty.
Every `DeckSection` is `min-h-[100svh]`, and full-page capture expands the viewport, so
`svh` resolves against the whole document and each section inflates to page height. Take
real viewport-sized shots and scroll between them.

### Deck sections: anchor targets and the emptiness (2026-08-10)

Two complaints, both about the home page, both measured before being changed.

**"Clicking a Product-menu link doesn't centre the section."** The anchor names
were split across two elements. The `DeckSection` carried a short internal id
(`how`, `guards`) while the component *inside* it carried the public one
(`how-it-works`, `safety`) - so `/#how-it-works` scrolled to the inner element,
which sits ~320px below the section that does the centring. Measured landing:
content centre 226px *above* the viewport centre, section top already scrolled
past. `#capabilities` looked fine only by accident - that id existed **twice**
(deck section and inner section), invalid HTML, and the deck section won on
document order.

Now: one id per section, on the `DeckSection`, using the public name. All three
land identically - section top at 92px (the `scroll-padding-top` clearing the
sticky header), content centre within 92-99px of the viewport centre. The inner
`<section>` elements keep their semantics and lose their ids.

If you add a section, put the anchor on the `DeckSection`, not on the component.
The component does not know how tall the screen it is centred in is.

**"Every section looks too empty."** It was not a feeling - sections were
`min-h-[100svh]` while their content ran 435-573px, so on a 1080px viewport each
one was **47-60% empty**. Height now comes from content plus `--space-section`
top and bottom, with `min-h-[62svh]` as a floor that nothing currently reaches.
Empty space is 32-40% and all of it is the padding, i.e. rhythm rather than dead
air. The page is 5791px instead of 7504px for exactly the same content.

The depth effect did not need the full height: `use-scroll-depth` compares each
section's centre to the viewport's centre and normalises by viewport height, so
it works at any section height. The real tradeoff is that a neighbouring section
is now more often partly visible instead of a screen of nothing - which is the
point. `--space-band` lost its only consumer in this change.

### Sections fill the screen again — the fix for an empty section is content (2026-08-13)

The previous round shrank the deck sections to content height because they
measured 47-60% empty. That was the wrong fix and is reverted. At ~700px a
neighbouring section is always partly on screen, so navigating to a section
stopped showing you *that* section and started showing you a piece of three.
Height is back; the sections are filled instead.

**If a deck section looks empty, give it something to say. Do not shrink it.**

Geometry, which was also wrong in a way that survived both rounds:

- A section is `calc(100svh - var(--h-site-header))`, not `100svh`. At a full
  viewport height the sticky header covers the section's own first 68px, so the
  last 68px always fell past the fold.
- `.deck-section` carries `scroll-margin-top: -24px`, cancelling the 24px that
  `html`'s `scroll-padding-top` adds above every anchor. That gap is right for a
  docs heading and wrong here — it was pulled straight out of the previous
  section and showed as a band under the bar. Anchors now land at exactly 68px,
  flush. It corrects the snap position too, since `scroll-snap-align: start`
  resolves against the same snapport.
- The header was `h-16` (64px) while `--h-site-header` said 68px. Everything
  that positions against the header reads the token, so the 4px lie showed up as
  a sliver. The header takes its height from the token now.

What went into the sections, all of it real product material rather than filler:

| Section | Was | Now | Added |
|---|---|---|---|
| listening | 449 | 621 | The run queue behind the result stack — five contacts, masked numbers, lamp states |
| problem | — | 759 | `ProblemCompare` + `LiveExtraction`, 649 lines that were built and never mounted |
| how-it-works | 444 | 624 | Heading sub; every step shows its own description instead of one swapping line |
| capabilities | 435 | 900 | 2-up grid of taller cards, each proof expanded into a real fragment |
| verticals | 573 | 803 | Per-row pain line and the `metricLabel` that was already in the data |
| safety | 447 | 763 | "When a guard trips, it says so" — the product's real error messages |

Two things deliberately *not* done, both worth knowing:

- **Capabilities stayed at four cards.** Two were cut in an earlier round because
  one asserted a calling window nothing enforces (ISSUES.md D1, CLAUDE.md §4 #8).
  A card added to occupy space says something untrue or something obvious. The
  section fills on card size and proof depth instead.
- **The vertical rows show `pain[0]`, not `goalTemplate`.** The goal is the better
  artefact — it is what a buyer is really evaluating — but it is stored with its
  runtime placeholders and rendered as `You are calling {name} about the
  {context[role]} role`, which reads as a broken page. It belongs there once
  something substitutes example values in.

`StepFlow` was considered for the how-it-works section and rejected: it is a 24px
`aria-hidden` decorative rail built to sit above a *horizontal* step row, and that
section uses a vertical tracker. It is still unmounted.
