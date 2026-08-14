/**
 * The theme contract, in one file, shared by the pre-paint script and the hook.
 *
 * Three stored values, two rendered ones. `system` is a *preference*, never a
 * rendered state: it is resolved against `matchMedia` and written out as a
 * concrete `light` or `dark`, so CSS only ever has to express two cases (see
 * the THEME SWITCH block in globals.css for why one selector beats two).
 */

export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'callflow.theme';
export const THEME_ATTRIBUTE = 'data-theme';

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === 'light' || value === 'dark' || value === 'system';
}

/**
 * The script that runs before first paint.
 *
 * Inlined into `<head>` and executed synchronously, ahead of any rendering, so
 * a dark-theme user never sees a white page flash. Anything async - a provider,
 * an effect, even a deferred script - is already too late: the browser will
 * have painted the light default first.
 *
 * Written as a string of ES5 rather than an imported function on purpose: it is
 * injected via `dangerouslySetInnerHTML` and never goes through the bundler, so
 * it cannot rely on any transform. It is also wrapped in try/catch because
 * `localStorage` throws outright in Safari's private mode, and a theme
 * preference is not worth taking the whole page down for - the catch simply
 * leaves the light default in place.
 */
export const THEME_PRE_PAINT_SCRIPT = `(function(){try{
var s=localStorage.getItem('${THEME_STORAGE_KEY}');
var t=(s==='light'||s==='dark')?s:(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
document.documentElement.setAttribute('${THEME_ATTRIBUTE}',t);
}catch(e){}})();`;
