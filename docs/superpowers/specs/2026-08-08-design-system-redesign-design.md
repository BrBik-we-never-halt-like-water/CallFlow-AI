# CallFlow AI — design system redesign

**Date:** 2026-08-08
**Branch:** `het/design-polish-v2`
**Status:** approved, implementing

---

## 1. What this is

A full redesign of the CallFlow AI web surface: a new three-colour system, Ubuntu
as the primary typeface, one card system replacing five, and a rebuilt section
rhythm across the marketing site and dashboard.

**Scope is visual and structural only.** The correctness and copy findings from the
audit are logged in `ISSUES.md` as D1–D23 and deliberately left alone, so the
redesign lands without entangling itself in behaviour changes.

---

## 2. Two rules this deliberately reverses

Both were documented as load-bearing. Both were overridden by explicit decision,
recorded here so the next person knows it was a choice and not an oversight.

**Colour is no longer reserved for call state.** `DESIGN_NOTES.md` §2 held that the
five lamp colours communicate call state and nothing else, which is why the primary
CTA was monochrome. The product now has a brand primary, used on CTAs, links and
focus.

*What survives the reversal:* the lamps keep their five colours and keep their
meaning. The primary was chosen specifically so it cannot be confused with any of
them — see §3.

**Ubuntu replaces the three-face system.** Archivo (display) and Inter Tight (body)
are retired in favour of Ubuntu for both roles.

*What survives:* **JetBrains Mono stays** for machine-produced data. `DESIGN_NOTES.md`
§3 calls the mono rule load-bearing — it is how a user tells system output from
human input — and Ubuntu Mono is materially less readable in the dense tables,
phone numbers, durations and costs the dashboard is built from. Brand coherence
loses to legibility here.

---

## 3. Colour — "Signal"

Three cores, plus a neutral ramp derived from the foundation.

### The constraint that picked the hue

Call state occupies five hues already: grey (idle), blue (dialling), amber (in
conversation), green (closed), red (needs a person). A primary landing near any of
them makes state ambiguous at a glance. Indigo is the furthest available hue from
all five, which is the whole reason it was chosen over the cyan and plum
alternatives.

### Tokens

| Role | Token | Value | Notes |
|---|---|---|---|
| Primary | `--primary` | `#3B2FD9` | CTA, links, focus, active nav |
| Primary hover | `--primary-hover` | `#3226B8` | |
| Primary active | `--primary-active` | `#2A1F9E` | |
| Primary on | `--primary-on` | `#FFFFFF` | text on primary — 7.6:1 |
| Primary wash | `--primary-wash` | `color-mix(--primary 10%)` | selected rows, quiet chips |
| Primary edge | `--primary-edge` | `color-mix(--primary 28%)` | focus ring, active border |
| Secondary surface | `--secondary` | `#F0E9DE` | warm sand — marketing sections, featured cards |
| Secondary edge | `--secondary-edge` | `#E2D7C4` | |
| Secondary text | `--secondary-text` | `#7A5C2E` | on sand — 5.1:1 |
| Foundation | `--surface` | `#F5F6F6` | page ground |
| Raised | `--surface-raised` | `#FFFFFF` | cards, inputs |
| Sunken | `--surface-sunken` | `#ECEFEF` | wells, table headers |
| Hover | `--surface-hover` | `#E7EBEB` | |
| Inverse | `--surface-inverse` | `#0E1114` | inverse sections, footer |
| Text | `--text` | `#0E1114` | 16.8:1 |
| Text dim | `--text-dim` | `#4A5358` | 7.6:1 |
| Text mute | `--text-mute` | `#69757A` | 4.6:1 — placeholders, metadata only |
| Text inverse | `--text-inverse` | `#FFFFFF` | |
| Rule | `--rule` | `#DFE3E3` | |
| Rule strong | `--rule-strong` | `#C2CACA` | |

Lamp tokens (`--lamp-*` and `--lamp-*-text`) carry over unchanged. The text-safe
variants remain mandatory for any lamp-coloured text.

**Secondary is a surface, not an action.** Sand never appears on a button or link,
so it cannot be mistaken for an interactive or state colour. It exists to warm the
marketing pages; the dashboard stays on the cool neutral for density.

---

## 4. Type — Ubuntu

Loaded via `next/font/google`: Ubuntu 300/400/500/700, JetBrains Mono 400/500.
Archivo and Inter Tight are removed.

Ubuntu needs tight negative tracking at display sizes or it reads soft. That is set
explicitly at every step rather than left to default.

**Every step is fluid.** The current scale freezes `h3` and `h4` while display sizes
scale, so hierarchy compresses between tablet and laptop. Fixed.

| Token | Size | Weight | Line | Tracking |
|---|---|---|---|---|
| `display-xl` | `clamp(2.75rem, 5.5vw, 4.5rem)` | 700 | 0.98 | −0.035em |
| `display-l` | `clamp(2.25rem, 4vw, 3.25rem)` | 700 | 1.05 | −0.03em |
| `h2` | `clamp(1.75rem, 2.8vw, 2.5rem)` | 500 | 1.15 | −0.02em |
| `h3` | `clamp(1.25rem, 1.6vw, 1.5rem)` | 500 | 1.3 | −0.01em |
| `h4` | `clamp(1rem, 1.1vw, 1.125rem)` | 500 | 1.4 | 0 |
| `body-l` | `1.125rem` | 400 | 1.6 | 0 |
| `body` | `1rem` | 400 | 1.65 | 0 |
| `small` | `0.875rem` | 400 | 1.5 | 0 |
| `data` | `0.8125rem` | 400 | 1.45 | 0 — **JetBrains Mono**, tabular |
| `label` | `0.6875rem` | 500 | 1 | 0.14em — **JetBrains Mono**, uppercase |

Measures: `--measure: 68ch` for body, `--measure-display: 20ch` for headlines.

**Table column headers move off `label`.** 11px uppercase at 0.14em tracking is
currently carrying every column header and several data values. Headers move to
`data` size at weight 500, sentence case. `label` is reserved for true eyebrows.

---

## 5. Surfaces — one card, three levels

Replaces `.pool`, `.surface-flow`, `.panel-raised`, `.card-flow`, `.plan-featured`.

| Level | Border | Fill | Shadow | Used for |
|---|---|---|---|---|
| `quiet` | 1px `--rule` | `--surface-raised` | none | list rows, dense dashboard panels |
| `raised` | 1px `--rule` | `--surface-raised` | `--shadow-sm` | the default card |
| `feature` | 1px `--primary-edge` | `--surface-raised` | `--shadow-md` | featured plan, hero readout |

Radius: `--r-md: 12px` for dense/inline, `--r-lg: 16px` for cards, `--r-xl: 22px`
for large marketing surfaces. Nothing pill-shaped except lamps, badges, avatars.

**Deleted:** `.seam-x`, `.seam-y`, `.wave-field`, `.plan-featured` — no source
usages. `.pool`, `.card-flow`, `.surface-flow` fold into the levels above.

**The hero shadow goes.** Currently `0 40px 80px -32px rgba(11,15,18,0.4)` — an
80px blur at 40% opacity, which is what makes the hero card read as pasted on.
Replaced by `--shadow-md` plus a hairline.

### Shadow scale

Softer and shorter-throw than the current set:

```
--shadow-xs: 0 1px 2px rgba(14,17,20,.04)
--shadow-sm: 0 1px 2px rgba(14,17,20,.04), 0 2px 6px -2px rgba(14,17,20,.06)
--shadow-md: 0 1px 3px rgba(14,17,20,.05), 0 8px 20px -6px rgba(14,17,20,.10)
--shadow-lg: 0 2px 6px rgba(14,17,20,.05), 0 18px 36px -12px rgba(14,17,20,.12)
```

---

## 6. Buttons

| Variant | Fill | Text | Border |
|---|---|---|---|
| `primary` | `--primary` | `--primary-on` | none |
| `secondary` | transparent | `--text` | `--rule-strong` |
| `ghost` | transparent | `--text-dim` | none |
| `danger` | `--lamp-flare` | white | none |

Sizes `sm` 32px / `md` 38px / `lg` 46px, all ≥44px touch target on coarse pointers
via padding. Focus is `2px --primary` at `2px` offset, everywhere, no exceptions.

The `btn-pulse` hover animation is removed — it was tuned for a monochrome CTA and
reads as noise on a coloured one.

---

## 7. Spacing, grid, motion

**Spacing scale** — one 4px-based ramp, replacing the six ad-hoc panel paddings
found in the audit: `4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 56 · 72 · 96`.

Panel padding standardises to `20px` dense / `24px` default / `32px` marketing.

**Section rhythm** — `--space-section: clamp(64px, 8vw, 112px)`.

**Widths** — `--w-marketing: 1180px`, `--w-app: 1440px`, `--w-form: 720px`
(Settings and Profile currently disagree at 768 and 672).

**Viewport-aware sections** — major marketing sections get `min-height` sized to
leave one section dominant per screen, never a fixed `100vh`, never clipping.
Content always wins over the viewport target.

**Motion** — durations `150 / 240 / 420ms`, easing `cubic-bezier(.22,1,.36,1)`.
Scroll reveals stay at one stagger step. Parallax stays to the hero only. Every
motion path keeps its `prefers-reduced-motion` branch.

---

## 8. Section-level changes

**Hero.** Shadow removed. Headline steps up to `display-xl` at the new tracking.
The two-beat scripted call (voice → typed result) is kept — it is the strongest
thing on the page and demonstrates the product in one glance. Primary CTA becomes
indigo; secondary stays outlined.

**Home page order** stays as-is; the seven `SpineDivider`s are replaced by section
grounds that alternate foundation and sand, so the rhythm comes from surface rather
than from a rule between every block.

**Cards** across capability grid, verticals, pricing and safety move onto the three
levels in §5. The featured plan is set apart by `feature` level and a badge, never
by colour alone.

**Dashboard** adopts the same card levels — currently it uses one of five
treatments while marketing uses the rest, which is the largest single source of
"these are two different products" feel.

**Navigation.** Site header gains an active state on the primary. App nav active
state moves from a monochrome fill to `--primary-wash` with a `--primary` left
edge.

---

## 9. Accessibility floor

Non-negotiable, checked before this is called done:

- Every text/background pair ≥ 4.5:1; large display ≥ 3:1. `--text-mute` is
  metadata-only and never carries body copy.
- Focus visible on every interactive element, `2px --primary`, `2px` offset.
- State never carried by colour alone — lamps keep their text label or `sr-only`
  name.
- `prefers-reduced-motion` honoured on every animation and the parallax layer.
- `prefers-contrast: more` block retained.
- Touch targets ≥ 44px on coarse pointers.

Pre-existing accessibility defects (D14 keyboard rows, D15 mobile routes) are
logged, not fixed here.

---

## 10. Out of scope

`ISSUES.md` D1–D23. Explicitly: no copy corrections to `/trust` or the docs, no
auth flow fixes, no campaign-duplicate fix, no webhook page changes. Those are a
separate pass.
