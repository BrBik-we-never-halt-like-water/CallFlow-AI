'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ACTIVE_ORG_KEY } from '@/lib/api';
import { supabaseBrowser } from '@/lib/supabase/client';

export interface ActiveOrg {
  org_id: string;
  org_name: string;
  org_slug: string;
  org_logo_url: string | null;
  /** Null until a person confirms the org's name in the onboarding gate. */
  onboarded_at: string | null;
  plan_id: string;
  role: string;
}

export interface SessionProfile {
  user_id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  active: ActiveOrg;
  permissions: string[];
}

export type SessionState =
  | { status: 'loading' }
  | { status: 'signed-out' }
  | { status: 'signed-in'; profile: SessionProfile }
  | { status: 'error'; message: string };

/**
 * The signed-in user as the API sees them.
 *
 * Deliberately sourced from `/api/v1/me` rather than from the Supabase user object:
 * the organisation, role, and permission set are decided by the API and the database,
 * so asking them is the only way the client's view cannot drift from what will
 * actually be authorised.
 *
 * `refresh()` is awaitable - it resolves once the re-fetched profile has actually
 * landed in state, not just once it's been requested. A caller that changes
 * something server-side (completing onboarding, renaming the org) and then reads
 * `profile` again needs that ordering guarantee, or it acts on stale data for one
 * more render.
 */
export function useSession(): SessionState & { refresh: () => Promise<void> } {
  const [state, setState] = useState<SessionState>({ status: 'loading' });
  const [nonce, setNonce] = useState(0);
  const pendingResolvers = useRef<Array<() => void>>([]);

  const refresh = useCallback(() => {
    return new Promise<void>((resolve) => {
      pendingResolvers.current.push(resolve);
      setNonce((n) => n + 1);
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    const supabase = supabaseBrowser();

    async function load() {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (cancelled) return;

      if (!session?.access_token) {
        setState({ status: 'signed-out' });
        return;
      }

      try {
        const base = process.env.NEXT_PUBLIC_API_URL ?? '';

        // Without X-Org-Id, the profile this hook returns never reflects a
        // switch made in the org switcher - every other call in lib/api.ts
        // attaches it, but this hook fetches directly and was missing it
        // entirely, so `active` silently stayed pinned to the server's default
        // organisation.
        let pinnedOrgId: string | null = null;
        try {
          pinnedOrgId = localStorage.getItem(ACTIVE_ORG_KEY);
        } catch {
          /* private mode or blocked storage - fall back to the server's default org */
        }

        async function fetchMe(orgId: string | null): Promise<Response> {
          const headers: Record<string, string> = {
            Authorization: `Bearer ${session!.access_token}`,
          };
          if (orgId) headers['X-Org-Id'] = orgId;
          return fetch(`${base}/api/v1/me`, { headers, cache: 'no-store' });
        }

        let response = await fetchMe(pinnedOrgId);

        // The pinned org can go stale - left, removed, or deleted since the
        // browser last wrote it. Rather than get stuck on a 403 the org switcher
        // can't fix (it never re-renders once loading this profile has already
        // failed), drop the pin and fall back to the server's own default org.
        if (response.status === 403 && pinnedOrgId) {
          try {
            localStorage.removeItem(ACTIVE_ORG_KEY);
          } catch {
            /* private mode or blocked storage */
          }
          response = await fetchMe(null);
        }

        if (cancelled) return;

        if (response.status === 401) {
          setState({ status: 'signed-out' });
          return;
        }

        if (!response.ok) {
          const body = await response.json().catch(() => null);
          setState({
            status: 'error',
            message: body?.detail ?? "Your account couldn't be loaded.",
          });
          return;
        }

        setState({ status: 'signed-in', profile: await response.json() });
      } catch {
        if (!cancelled) {
          setState({ status: 'error', message: "The service didn't respond." });
        }
      }
    }

    async function run() {
      await load();
      if (cancelled) return;
      const resolvers = pendingResolvers.current;
      pendingResolvers.current = [];
      resolvers.forEach((resolve) => resolve());
    }

    void run();

    // Sign-in, sign-out, and token refresh all land here, so the shell updates
    // without a page reload.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(() => {
      void run();
    });

    return () => {
      cancelled = true;
      subscription.unsubscribe();
    };
  }, [nonce]);

  return { ...state, refresh };
}
