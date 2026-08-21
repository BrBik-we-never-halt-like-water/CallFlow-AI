'use client';

import { useSyncExternalStore } from 'react';

/**
 * A signal that "the current organisation's entitlements just changed" —
 * bumped after an in-place plan change or cancel on Billing, so anything else
 * reading entitlements refetches without waiting for a navigation or a
 * reload. `usePlanLimits` is the first subscriber: the app shell's sidebar
 * org switcher mounts once per session and otherwise only refetches on an org
 * switch, so an in-place upgrade could leave it showing the pre-upgrade
 * ceiling until one of those happened.
 *
 * In-memory only, not persisted — a reload already refetches everything
 * fresh, so this only needs to cover the gap between an in-place change and
 * whichever comes first: the next org switch, page navigation, or reload.
 */
let version = 0;
const listeners = new Set<() => void>();

export function bumpEntitlementsVersion(): void {
  version += 1;
  for (const listener of listeners) listener();
}

export function useEntitlementsVersion(): number {
  return useSyncExternalStore(
    (callback) => {
      listeners.add(callback);
      return () => listeners.delete(callback);
    },
    () => version,
    () => 0,
  );
}
