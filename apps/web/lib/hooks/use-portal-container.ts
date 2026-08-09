'use client';

import { useSyncExternalStore } from 'react';

export const APP_FONT_SCOPE_ID = 'app-font-scope';

/**
 * Radix portals mount straight to `document.body` by default - a *sibling*
 * of `.app-font-scope` (the `/app` layout's own wrapper div), never a
 * descendant of it. CSS custom properties and the font class only inherit
 * through the real DOM tree, so a portaled menu/dialog never saw either one
 * (`ISSUES.md` #49 for the font; the same gap broke the dark theme fix for
 * DropdownMenu/Popover/Dialog too - a `.dark-overlay` class re-scoping
 * `var(--dark-text)` etc. is useless if `--dark-text` itself was never
 * inherited in the first place).
 *
 * Mounting the portal *inside* `.app-font-scope` instead fixes both at once.
 * Falls back to `document.body` outside `/app` (marketing/auth, which never
 * render this element) - same default Radix already has.
 *
 * `useSyncExternalStore`, not an effect + `setState` - the element is present
 * for this component's whole mounted lifetime once it exists, so there is
 * nothing to subscribe to, only a value that must not be read during SSR
 * (`react-hooks/set-state-in-effect` is an error here; see
 * `lib/hooks/use-external-store.ts` for the same reasoning applied to
 * `localStorage`/`matchMedia`).
 */
function subscribe(): () => void {
  return () => {};
}

function getSnapshot(): HTMLElement {
  return document.getElementById(APP_FONT_SCOPE_ID) ?? document.body;
}

function getServerSnapshot(): undefined {
  return undefined;
}

export function usePortalContainer(): HTMLElement | undefined {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/**
 * Whether a `usePortalContainer()` result is actually `/app`'s scope - not
 * every consumer can also assume `.dark-overlay` styling is wanted. `Select`
 * is shared with a light-themed marketing form
 * (`app/(marketing)/demo/demo-form.tsx`), so it needs the portal-container
 * fix (for the font) without the dark colour override that would break it
 * there. A plain function, not a hook - compares `container.id` against
 * this constant rather than against `document.body` directly, since the
 * fallback value's identity isn't part of the contract.
 */
export function isAppScopeContainer(container: HTMLElement | undefined): boolean {
  return container?.id === APP_FONT_SCOPE_ID;
}
