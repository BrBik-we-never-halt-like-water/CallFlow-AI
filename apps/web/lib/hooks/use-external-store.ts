'use client';

import { useCallback, useSyncExternalStore } from 'react';

/**
 * Bridges to browser state that React does not own - `localStorage` and
 * `matchMedia`.
 *
 * Both of these are genuinely external stores, and the tempting shape - read them in an
 * effect and call `setState` - causes a cascading render on every mount and is exactly
 * what `react-hooks/set-state-in-effect` is warning about. `useSyncExternalStore` is the
 * sanctioned tool: it subscribes, it returns a server snapshot so SSR and hydration
 * agree, and it never renders twice to arrive at the same value.
 */

/* -------------------------------------------------------------------------- */
/* localStorage                                                                */
/* -------------------------------------------------------------------------- */

const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

function subscribeToStorage(callback: () => void): () => void {
  listeners.add(callback);
  // `storage` fires for changes made in *other* tabs; local writes call notify().
  window.addEventListener('storage', callback);
  return () => {
    listeners.delete(callback);
    window.removeEventListener('storage', callback);
  };
}

function readRaw(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    // Private mode or blocked storage. Behaves as "nothing stored".
    return null;
  }
}

function writeRaw(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Not persisted. The notify() below still updates this session.
  }
  notify();
}

/**
 * A string in `localStorage`, as React state.
 *
 * `getSnapshot` returns a string, so React's `Object.is` check is a value comparison and
 * no caching layer is needed.
 */
export function useStoredString(
  key: string,
  fallback: string,
): [string, (next: string) => void] {
  const value = useSyncExternalStore(
    subscribeToStorage,
    () => readRaw(key) ?? fallback,
    // Server snapshot: the fallback, which is also what the pre-hydration markup shows.
    () => fallback,
  );

  const set = useCallback((next: string) => writeRaw(key, next), [key]);
  return [value, set];
}

/**
 * A JSON value in `localStorage`, as React state.
 *
 * Parsed results are memoised against the raw string, because `getSnapshot` must return
 * a referentially stable value - parsing on every call would return a fresh object each
 * time and send React into an infinite loop.
 */
const jsonCache = new Map<string, { raw: string | null; parsed: unknown }>();

export function useStoredJson<T>(
  key: string,
  fallback: T,
): [T, (next: T | ((current: T) => T)) => void] {
  const getSnapshot = useCallback((): T => {
    const raw = readRaw(key);
    const cached = jsonCache.get(key);
    if (cached && cached.raw === raw) return cached.parsed as T;

    let parsed: unknown = fallback;
    if (raw !== null) {
      try {
        parsed = JSON.parse(raw);
      } catch {
        parsed = fallback;
      }
    }
    jsonCache.set(key, { raw, parsed });
    return parsed as T;
  }, [key, fallback]);

  const value = useSyncExternalStore(
    subscribeToStorage,
    getSnapshot,
    () => fallback,
  );

  // Accepts an updater as well as a value, so callers read like `useState` and can patch
  // one field of a settings object without restating the rest.
  const set = useCallback(
    (next: T | ((current: T) => T)) => {
      const resolved =
        typeof next === 'function'
          ? (next as (current: T) => T)(getSnapshot())
          : next;
      writeRaw(key, JSON.stringify(resolved));
    },
    [key, getSnapshot],
  );

  return [value, set];
}

/* -------------------------------------------------------------------------- */
/* matchMedia                                                                  */
/* -------------------------------------------------------------------------- */

/**
 * A media query as a boolean. Always `false` on the server, which is the safe default
 * for both of the queries this product asks about.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (callback: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener('change', callback);
      return () => list.removeEventListener('change', callback);
    },
    [query],
  );

  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false,
  );
}

export function usePrefersReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
}

export function usePrefersDark(): boolean {
  return useMediaQuery('(prefers-color-scheme: dark)');
}
