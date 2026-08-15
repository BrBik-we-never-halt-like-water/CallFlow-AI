'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useRef } from 'react';

/**
 * Cross-dissolve between routes using the browser's View Transitions API.
 *
 * Mounted once in the root layout, this intercepts internal link clicks in the
 * capture phase and drives the navigation through `document.startViewTransition`,
 * so the browser crossfades the old page into the new one (and morphs any
 * elements that share a `view-transition-name` - see the app cards).
 *
 * The transition callback resolves only once the route has actually changed
 * (watched via `usePathname`), which is what makes the browser capture the *new*
 * page rather than a half-rendered frame. A timeout backstops a navigation that
 * never lands so the page can never freeze mid-transition.
 *
 * Where the API is unavailable, or for modified / new-tab / external / same-page
 * clicks, this does nothing and the normal Next.js navigation runs - the CSS
 * `.page-enter` fade in globals.css is the fallback.
 */
export function ViewTransitions() {
  const router = useRouter();
  const pathname = usePathname();
  const resolveRef = useRef<(() => void) | null>(null);

  // A route change finishes whatever transition is in flight.
  useEffect(() => {
    if (resolveRef.current) {
      resolveRef.current();
      resolveRef.current = null;
    }
  }, [pathname]);

  useEffect(() => {
    if (
      typeof document === 'undefined' ||
      !('startViewTransition' in document)
    ) {
      return;
    }

    const onClick = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }

      const anchor = (event.target as Element | null)?.closest?.('a');
      if (!anchor) return;
      if (anchor.target === '_blank' || anchor.hasAttribute('download')) return;

      const href = anchor.getAttribute('href');
      if (!href || href.startsWith('#')) return;

      let url: URL;
      try {
        url = new URL(anchor.href, location.href);
      } catch {
        return;
      }
      if (url.origin !== location.origin) return;
      // Same-path (hash or query-only) changes shouldn't crossfade the whole page.
      if (url.pathname === location.pathname) return;

      event.preventDefault();

      const navigate = () =>
        new Promise<void>((resolve) => {
          resolveRef.current = resolve;
          router.push(url.pathname + url.search + url.hash);
          // Backstop: if the route never changes, don't leave the page frozen.
          setTimeout(() => {
            if (resolveRef.current === resolve) {
              resolveRef.current = null;
              resolve();
            }
          }, 500);
        });

      (
        document as Document & {
          startViewTransition: (cb: () => Promise<void>) => void;
        }
      ).startViewTransition(navigate);
    };

    // Capture phase so this runs before Next's own Link handler; preventDefault
    // then makes Link stand down and we own the navigation.
    document.addEventListener('click', onClick, true);
    return () => document.removeEventListener('click', onClick, true);
  }, [router]);

  return null;
}
