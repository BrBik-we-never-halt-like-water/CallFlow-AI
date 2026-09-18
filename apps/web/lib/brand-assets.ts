/**
 * The brand palette as literal hex, for the assets that cannot read CSS.
 *
 * Everything that renders in a browser takes its colour from `globals.css`, and
 * `components/brand/mark.tsx` fills its lamps with `var(--lamp-*)` so the logo
 * follows the theme. Four things cannot: the favicon (a static SVG), the Apple
 * touch icon and the social card (both rendered server-side by `next/og`, which
 * resolves no custom properties), and the web manifest (JSON). Each of those had
 * its own copy of the palette, and each copy was a pre-dark-pivot one - so every
 * shared link and every home-screen icon showed three colours the product had
 * stopped using, while `apple-icon.tsx` claimed in its own docstring that there
 * was exactly one definition of the mark.
 *
 * So: one mirror, checked. These are the `--dark-*` values from `globals.css`,
 * because all four assets render on a dark plate - the mark as it appears on the
 * product's own dark surface. `scripts/check-tokens.mjs` fails the build if any
 * value here, or in `app/icon.svg`, stops matching its token.
 */

export const BRAND = {
  /** `--dark-surface`. The plate every generated asset sits on. */
  plate: '#141419',

  /**
   * `--dark-rule` and `--dark-rule-strong` are `color-mix(... 12%/22% white,
   * transparent)`. An alpha over a known plate has one flat equivalent, and
   * these are it - `next/og` supports neither `color-mix` nor a stacked alpha.
   */
  rule: '#303035',
  ruleStrong: '#48484c',

  lamp: {
    off: '#838787',
    ice: '#5883b7',
    brass: '#a47f47',
    jade: '#4b9073',
    flare: '#c15f4d',
  },

  text: '#f1f5f9',
  textDim: '#cbd5e1',
  textMute: '#94a3b8',
} as const;
