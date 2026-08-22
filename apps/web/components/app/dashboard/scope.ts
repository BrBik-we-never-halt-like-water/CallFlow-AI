import type { TeamPerformance } from '@/lib/api';

/**
 * Who may see whose data, in one place.
 *
 * The rule the product wants: an owner sees everyone; anyone else sees
 * themselves, and sees the team only if their role carries
 * `runs:read_team`. This module decides *which controls to offer*; it is
 * not the enforcement boundary. Enforcement is the API's - RLS scopes
 * every query and `RequirePermission(RUNS_READ_TEAM)` gates the team
 * endpoint - so a scope this module refuses to offer is also a scope the
 * server would not answer.
 *
 * Keeping it as data rather than inline conditionals means a new role, or
 * a change to what a role may see, is one edit here instead of four
 * scattered ternaries across the panels.
 */

/** The shape these helpers need - a subset of the session profile. */
export interface SessionProfileLike {
  user_id: string;
  permissions: string[];
  active: { role: string };
  /** CallFlow staff only - absent or false for every ordinary customer. */
  is_platform_admin?: boolean;
}

/**
 * `mine`, `all`, or one teammate's user id. A raw id rather than a wrapped
 * variant because that is what a row carries - selecting a name is then a
 * direct comparison, with no lookup table to keep in step.
 */
export type Scope = 'mine' | 'all' | (string & {});

export interface ScopeOption {
  value: Scope;
  label: string;
}

export function hasPermission(
  profile: SessionProfileLike | null,
  permission: string,
): boolean {
  return profile?.permissions.includes(permission) ?? false;
}

/** True when the role may see beyond its own rows. */
export function canSeeTeam(profile: SessionProfileLike | null): boolean {
  return hasPermission(profile, 'runs:read_team');
}

/**
 * Mine, All, then one entry per teammate by name.
 *
 * A role without `runs:read_team` gets `Mine` alone - the control then
 * renders as nothing at all rather than as a disabled box, since the data
 * behind the other options was never sent to this client.
 *
 * The signed-in person is filtered out of the name list - they are already
 * `Mine`, and listing them twice invites the reader to think the two differ.
 * `All` is the org total, which is why it stays a separate option rather
 * than the sum of the names shown.
 *
 * Note this lists every teammate the *team-performance endpoint returned*.
 * Hiding the owner's row from non-owners is a server-side decision - if the
 * product wants that, it belongs in the endpoint's query, not in a filter
 * here, since a client-side omission would still ship the row over the wire.
 */
export function scopeOptions(
  profile: SessionProfileLike | null,
  members: TeamPerformance[] | null,
): ScopeOption[] {
  const options: ScopeOption[] = [{ value: 'mine', label: 'Mine' }];
  if (!canSeeTeam(profile)) return options;

  options.push({ value: 'all', label: 'All' });

  for (const member of members ?? []) {
    if (!member.user_id || !member.name) continue;
    if (member.user_id === profile?.user_id) continue;
    options.push({ value: member.user_id, label: member.name });
  }

  return options;
}
