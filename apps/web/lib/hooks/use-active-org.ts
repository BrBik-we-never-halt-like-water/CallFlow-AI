'use client';

import { ACTIVE_ORG_KEY } from '@/lib/api';
import { useStoredString } from '@/lib/hooks/use-external-store';
import { useSession } from '@/lib/hooks/use-session';

/**
 * Which organisation requests act against, when someone belongs to more than one.
 *
 * An empty string means "no preference set" - `lib/api.ts`'s `authHeaders()` then
 * omits `X-Org-Id` entirely and the API falls back to the earliest-joined org, same
 * as before an org switcher existed.
 */
export function useActiveOrg(): [string, (orgId: string) => void] {
  return useStoredString(ACTIVE_ORG_KEY, '');
}

/**
 * The organisation that browser-local state belongs to.
 *
 * Anything kept in `localStorage` that describes work inside one organisation -
 * an unsaved agent draft, say - has to be filed under it, or it follows the
 * person into the next organisation they open (`ISSUES.md` #128).
 *
 * Neither source alone is right. `useActiveOrg()` is empty until someone
 * switches for the first time, so early drafts would land under a key that
 * becomes unreachable the moment they do. The session's copy is always a real
 * id but lags a switch, because it only changes once `/me` comes back - long
 * enough to read the previous organisation's drafts into a freshly-opened
 * editor. Preferring the switcher's value and falling back to the session's
 * gives a real id at all times *and* moves at the same moment the rest of the
 * app does.
 */
export function useScopedOrgId(): string | null {
  const [activeOrgId] = useActiveOrg();
  const session = useSession();
  if (activeOrgId) return activeOrgId;
  return session.status === 'signed-in' ? session.profile.active.org_id : null;
}
