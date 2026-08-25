/**
 * Guards the three token invariants that fail *silently*.
 *
 * Run with `node scripts/check-tokens.mjs`, or `npm run check:tokens`.
 *
 * Every check here exists because the failure it catches is invisible in review
 * and nearly invisible in the browser:
 *
 * 1. **No custom-property cycle.** `.dash` rebinds `--primary` to
 *    `--dash-brand`. If `--dash-brand` is ever written as `var(--primary)` the
 *    chain closes, CSS resolves *both* to invalid, and every brand surface on
 *    the dashboard renders unstyled - no error, no warning, just missing colour.
 *    This is not hypothetical: it was introduced and caught during the token
 *    unification, which is why the check exists.
 *
 * 2. **One accent, and it is the documented one.** CLAUDE.md §10 makes
 *    `--primary` the product's single non-lamp colour. `--dash-brand` has to
 *    restate its value rather than reference it (see 1), so the two can drift.
 *
 * 3. **No accent sitting on a lamp's hue.** The reason the dash palette was
 *    re-based: its coral brand sat 2.2° from `--dash-danger` and 6.3° from
 *    `--lamp-flare` in OKLCh, so every KPI figure and active nav item was the
 *    colour of an error. Hue distance is the thing to assert - the previous
 *    palette separated brand from danger by *value*, which the eye does not
 *    sort by in a table.
 */

import { readFile } from 'node:fs/promises';

const CSS = 'app/globals.css';

/** Minimum OKLCh hue separation between an accent and any lamp or status hue.
 *  CLAUDE.md cites a former green primary at 14° from jade as the mistake, so
 *  the bar sits above that with room to spare. */
const MIN_HUE_SEPARATION = 30;

function srgbToLinear(c) {
  const v = c / 255;
  return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}

/** Hue in degrees, via OKLab. Enough of the transform to compare two hues. */
function hue(hex) {
  const h = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) =>
    srgbToLinear(parseInt(h.slice(i, i + 2), 16)),
  );
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  const a = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
  const bb = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
  return ((Math.atan2(bb, a) * 180) / Math.PI + 360) % 360;
}

function separation(a, b) {
  const d = Math.abs(hue(a) - hue(b));
  return Math.min(d, 360 - d);
}

/** Every literal value a token is given, keyed by token name. A token declared
 *  in several theme scopes collects several values, and all of them count. */
function declarations(css) {
  const found = new Map();
  const re = /^\s*(--[a-z0-9-]+)\s*:\s*([^;]+);/gm;
  for (const [, name, raw] of css.matchAll(re)) {
    if (!found.has(name)) found.set(name, []);
    found.get(name).push(raw.trim());
  }
  return found;
}

const css = await readFile(CSS, 'utf8');
const tokens = declarations(css);
const failures = [];

// --- 1. the cycle ------------------------------------------------------------
for (const value of tokens.get('--dash-brand') ?? []) {
  if (value.includes('var(--primary')) {
    failures.push(
      `--dash-brand is "${value}" while .dash sets --primary: var(--dash-brand). ` +
        `That is a custom-property cycle: both resolve to invalid and the ` +
        `dashboard loses its brand colour with no error. Restate the hex.`,
    );
  }
}

// --- 2. one accent -----------------------------------------------------------
const hexes = (name) =>
  (tokens.get(name) ?? []).filter((v) => /^#[0-9a-f]{6}$/i.test(v));
const primaries = hexes('--primary');
const brands = hexes('--dash-brand');
for (const brand of brands) {
  if (!primaries.some((p) => p.toLowerCase() === brand.toLowerCase())) {
    failures.push(
      `--dash-brand ${brand} is not any declared --primary value ` +
        `(${primaries.join(', ') || 'none'}). CLAUDE.md §10 allows the product ` +
        `one non-lamp accent; a second one is what this check exists to stop.`,
    );
  }
}

// --- 3. accents clear of every lamp and status hue ---------------------------
const RESERVED = [
  ['--lamp-flare', hexes('--lamp-flare')],
  ['--lamp-jade', hexes('--lamp-jade')],
  ['--lamp-brass', hexes('--lamp-brass')],
  ['--dash-danger', hexes('--dash-danger')],
  ['--dash-success', hexes('--dash-success')],
  ['--dash-warning', hexes('--dash-warning')],
];
for (const accentToken of ['--primary', '--dash-brand', '--dash-figure']) {
  for (const accent of hexes(accentToken)) {
    for (const [name, values] of RESERVED) {
      for (const reserved of values) {
        const gap = separation(accent, reserved);
        if (gap < MIN_HUE_SEPARATION) {
          failures.push(
            `${accentToken} ${accent} sits ${gap.toFixed(1)}° from ${name} ` +
              `${reserved} in OKLCh (floor ${MIN_HUE_SEPARATION}°). An accent on a ` +
              `status hue makes every figure and active control read as that status.`,
          );
        }
      }
    }
  }
}

// --- 4. the brand-asset mirror still matches its tokens ----------------------
// The favicon, the Apple icon, the social card and the manifest cannot read CSS,
// so `lib/brand-assets.ts` restates the `--dark-*` palette as literal hex and
// `app/icon.svg` restates it again. Nobody looks at their own favicon or their
// own OG card, so drift here is invisible for as long as it likes: all four were
// three versions behind before this check existed.
const MIRROR = 'lib/brand-assets.ts';
const FAVICON = 'app/icon.svg';

const mirrorSrc = await readFile(MIRROR, 'utf8');
const mirror = new Map(
  [...mirrorSrc.matchAll(/(\w+):\s*'(#[0-9a-fA-F]{6})'/g)].map(([, k, v]) => [
    k,
    v.toLowerCase(),
  ]),
);

/** Mirror key -> the token it claims to copy. `rule`/`ruleStrong` are omitted:
 *  they flatten a `color-mix` alpha over the plate, so there is no literal token
 *  to compare them against. */
const MIRRORED = {
  plate: '--dark-surface',
  off: '--dark-lamp-off',
  ice: '--dark-lamp-ice',
  brass: '--dark-lamp-brass',
  jade: '--dark-lamp-jade',
  flare: '--dark-lamp-flare',
  text: '--dark-text',
  textDim: '--dark-text-dim',
  textMute: '--dark-text-mute',
};

for (const [key, token] of Object.entries(MIRRORED)) {
  const mirrored = mirror.get(key);
  if (!mirrored) {
    failures.push(`${MIRROR} no longer declares \`${key}\`, which mirrored ${token}.`);
    continue;
  }
  // A token declared in several scopes offers several values; matching any one
  // of them is the mirror being in step with the palette.
  const declared = hexes(token).map((h) => h.toLowerCase());
  if (declared.length === 0) {
    failures.push(`${token} has no literal value in ${CSS}, so ${MIRROR}.${key} cannot be checked.`);
  } else if (!declared.includes(mirrored)) {
    failures.push(
      `${MIRROR} has ${key} = ${mirrored}, but ${token} is ${declared.join(' / ')}. ` +
        `Every shared link and home-screen icon renders the stale value.`,
    );
  }
}

const allowed = new Set([...mirror.values()]);
const faviconSrc = await readFile(FAVICON, 'utf8');
for (const [, found] of faviconSrc.matchAll(/(?:fill|stroke)="(#[0-9a-fA-F]{6})"/g)) {
  if (!allowed.has(found.toLowerCase())) {
    failures.push(
      `${FAVICON} paints ${found}, which is not a value in ${MIRROR}. ` +
        `The favicon is the one asset nobody notices going stale.`,
    );
  }
}

if (failures.length) {
  console.error(`\ncheck-tokens: ${failures.length} problem(s)\n`);
  for (const f of failures) console.error(`  - ${f}\n`);
  process.exit(1);
}

console.log(
  `check-tokens: ok - no cycle, one accent (${brands.join(' / ')}), ` +
    `all accents >=${MIN_HUE_SEPARATION}° from every lamp and status hue, ` +
    `brand-asset mirror in step with ${Object.keys(MIRRORED).length} tokens.`,
);
