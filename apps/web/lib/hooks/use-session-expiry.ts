'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { SessionExpiredError } from '@/lib/api';
import { signOut } from '@/lib/auth/actions';

/**
 * Sends someone back to sign in when their session ends, from wherever they are.
 *
 * A token expires mid-session and every subsequent request 401s. Each screen
 * catches its own load failure and says what *it* would say - the run detail
 * page reported the run missing, which sent people looking for a run that was
 * in the database the whole time (`ISSUES.md` #174). Rather than teach every
 * screen to recognise an auth failure, `api.ts` throws a named
 * `SessionExpiredError` and this listens for it once, in the shell every
 * authenticated page renders inside.
 *
 * Listening on `unhandledrejection` rather than wrapping each call: a poll or a
 * background refresh rejects without any component awaiting it, so a try/catch
 * at the call sites would miss exactly the case that matters.
 *
 * `signOut()` first, so the dead token is cleared rather than left to fail the
 * next request too, and `replace` rather than `push` so Back does not return to
 * a page that cannot load. `next=` carries where they were, so signing in
 * returns them there instead of to the dashboard.
 */
export function useSessionExpiry(): void {
  const router = useRouter();

  useEffect(() => {
    let handled = false;

    async function bounce(): Promise<void> {
      // Several requests usually fail together - one poll, one refresh, one
      // page load - and each would otherwise start its own sign-out.
      if (handled) return;
      handled = true;

      const here = window.location.pathname + window.location.search;
      try {
        await signOut();
      } catch {
        // The token is already invalid; failing to tell the server so does not
        // change what happens next.
      }
      router.replace(`/login?next=${encodeURIComponent(here)}&reason=expired`);
    }

    function onRejection(event: PromiseRejectionEvent): void {
      if (event.reason instanceof SessionExpiredError) {
        event.preventDefault();
        void bounce();
      }
    }

    function onError(event: ErrorEvent): void {
      if (event.error instanceof SessionExpiredError) {
        event.preventDefault();
        void bounce();
      }
    }

    window.addEventListener('unhandledrejection', onRejection);
    window.addEventListener('error', onError);
    return () => {
      window.removeEventListener('unhandledrejection', onRejection);
      window.removeEventListener('error', onError);
    };
  }, [router]);
}
