'use client';

import { useSession, type SessionProfile } from '@/lib/hooks/use-session';

/**
 * Pure - usable wherever a `profile` is already in hand. Nav components
 * (`app-nav.tsx`, `app-shell.tsx`) receive `profile` as a prop rather than
 * calling `useSession()` a second time, so the check itself has to be
 * callable without a hook.
 */
export function hasPermission(
  profile: SessionProfile | null,
  permission: string,
): boolean {
  return profile?.permissions.includes(permission) ?? false;
}

/** True if the signed-in profile's role is one of the given roles. */
export function hasRole(
  profile: SessionProfile | null,
  ...roles: string[]
): boolean {
  return profile !== null && roles.includes(profile.active.role);
}

/**
 * `profile.permissions.includes(...)` is how every page already checks
 * this - these hooks exist so the *session lookup* isn't repeated too, not
 * to introduce a second checking convention alongside it.
 */
export function usePermission(permission: string): boolean {
  const session = useSession();
  const profile = session.status === 'signed-in' ? session.profile : null;
  return hasPermission(profile, permission);
}

export function useRole(): string | null {
  const session = useSession();
  return session.status === 'signed-in' ? session.profile.active.role : null;
}
