'use client';

import { useCallback } from 'react';
import {
  isThemePreference,
  THEME_ATTRIBUTE,
  THEME_STORAGE_KEY,
  type ResolvedTheme,
  type ThemePreference,
} from '@/lib/theme';
import { usePrefersDark, useStoredString } from './use-external-store';

/**
 * The theme, as state.
 *
 * Built on `useStoredString` + `usePrefersDark` rather than a context provider,
 * for the reason CLAUDE.md gives: both are `useSyncExternalStore` over a real
 * external source, so the preference is derived during render instead of
 * synced into state by an effect. A provider would add a tree-wide re-render
 * and a second source of truth for something the DOM attribute already holds.
 *
 * `preference` is what the user chose ('system' included). `resolved` is what
 * is actually on screen, and is the only one worth branching styles on.
 */
export function useTheme(): {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  setPreference: (next: ThemePreference) => void;
} {
  const [raw, setRaw] = useStoredString(THEME_STORAGE_KEY, 'system');
  const prefersDark = usePrefersDark();

  const preference: ThemePreference = isThemePreference(raw) ? raw : 'system';
  const resolved: ResolvedTheme =
    preference === 'system' ? (prefersDark ? 'dark' : 'light') : preference;

  const setPreference = useCallback(
    (next: ThemePreference) => {
      setRaw(next);
      // The attribute is written here as well as by the pre-paint script,
      // because `useStoredString` only re-renders React - it has no opinion
      // about the DOM, and `[data-theme]` on <html> is what CSS actually reads.
      applyTheme(next === 'system' ? undefined : next);
    },
    [setRaw],
  );

  return { preference, resolved, setPreference };
}

/**
 * Writes the resolved theme onto `<html>`.
 *
 * Exported because the toggle needs to apply the theme *inside* a View
 * Transition callback rather than after it - the browser snapshots the DOM
 * before and after that callback, so a theme applied outside it produces no
 * transition at all, just an instant swap.
 */
export function applyTheme(theme: ResolvedTheme | undefined): void {
  const root = document.documentElement;
  if (theme) {
    root.setAttribute(THEME_ATTRIBUTE, theme);
    return;
  }
  // 'system': resolve it now rather than removing the attribute, so the CSS
  // only ever sees a concrete value (see the THEME SWITCH note in globals.css).
  root.setAttribute(
    THEME_ATTRIBUTE,
    window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
  );
}
