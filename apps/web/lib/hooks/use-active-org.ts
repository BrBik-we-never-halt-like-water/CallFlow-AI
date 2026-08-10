'use client';

import { ACTIVE_ORG_KEY } from '@/lib/api';
import { useStoredString } from '@/lib/hooks/use-external-store';

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
