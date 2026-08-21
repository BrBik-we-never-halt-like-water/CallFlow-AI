'use client';

import {
  BuildingsIcon,
  CaretDownIcon,
  CaretRightIcon,
  PlusIcon,
  SignOutIcon,
  UserPlusIcon,
} from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { OrgMark } from '@/components/layout/app-nav';
import { signOut } from '@/lib/auth/actions';
import { useActiveOrg } from '@/lib/hooks/use-active-org';
import { useOrganisations } from '@/lib/hooks/use-organisations';
import type { SessionProfile } from '@/lib/hooks/use-session';
import { cn } from '@/lib/cn';

/**
 * The sidebar's account control: who you are, which organisation you are in,
 * and the three things you do from here - profile settings, switching
 * organisation, signing out.
 *
 * Replaces the separate organisation switcher that sat at the top of the
 * sidebar. Both were asking "which account context am I in", and answering it
 * twice cost a whole row of the nav column.
 */
export function DashProfileMenu({
  profile,
  refreshSession,
  collapsed = false,
}: {
  profile: SessionProfile | null;
  refreshSession: () => void;
  /** Avatar only. The rail shows who you are, not the org - one mark, and
   *  the same menu behind it. */
  collapsed?: boolean;
}) {
  const { orgs } = useOrganisations(profile);
  const [, setActiveOrgId] = useActiveOrg();

  if (!profile) {
    return (
      <span
        className={cn(
          'block rounded-[10px]',
          collapsed ? 'size-9' : 'h-10 w-full',
        )}
        style={{ background: 'var(--dash-hover)' }}
      />
    );
  }

  const fullName = profile.name?.trim() || profile.email;
  // First name only. The trigger is 208px wide minus an avatar and a caret,
  // which truncated most full names to "Mohd Arbaaz Sid..." - a first name
  // fits whole and identifies the account just as well. The full name still
  // reaches assistive tech through the trigger's `aria-label`.
  const name = fullName.split(/\s+/)[0];
  const role = profile.active.role;

  function switchOrg(orgId: string) {
    if (orgId === profile?.active.org_id) return;
    setActiveOrgId(orgId);
    refreshSession();
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Account - ${fullName}, ${role}`}
          className={cn(
            'flex cursor-pointer items-center rounded-[10px] text-left transition-colors',
            collapsed
              ? 'size-9 justify-center'
              : 'w-full gap-2 px-2 py-1.5',
          )}
          style={
            collapsed
              ? undefined
              : {
                  background: 'var(--dash-surface)',
                  border: '1px solid var(--dash-border)',
                }
          }
        >
          {profile.avatar_url ? (
            <img
              src={profile.avatar_url}
              alt=""
              className="size-7 shrink-0 rounded-full object-cover"
            />
          ) : (
            <span
              aria-hidden
              className="flex size-7 shrink-0 items-center justify-center rounded-full text-[0.6875rem] font-semibold"
              style={{
                background: 'var(--dash-brand-soft)',
                color: 'var(--dash-brand-ink)',
              }}
            >
              {name.charAt(0).toUpperCase()}
            </span>
          )}

          {!collapsed ? (
            <>
              <span className="min-w-0 flex-1">
                <span
                  className="block truncate text-[0.75rem] font-semibold"
                  style={{ color: 'var(--dash-text)' }}
                >
                  {name}
                </span>
                <span
                  className="block truncate text-[0.625rem] capitalize"
                  style={{ color: 'var(--dash-text-mute)' }}
                >
                  {role}
                </span>
              </span>

              <CaretDownIcon
                aria-hidden
                className="size-3 shrink-0"
                style={{ color: 'var(--dash-text-mute)' }}
              />
            </>
          ) : null}
        </button>
      </DropdownMenuTrigger>

      {/* Three actions, not a second navigation surface. Settings and the
          organisation list moved into `/app/settings` (its own tabs), so what
          is left here is only what has nowhere else to live: switching or
          creating an organisation, inviting someone, and signing out. */}
      <DropdownMenuContent align="start" className="dash-menu w-56">
        {/* Switching organisation still needs the list, so this stays a
            submenu - it grows with the number of organisations and scrolls,
            where inline rows had nowhere to put themselves past two. */}
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <BuildingsIcon aria-hidden className="size-3.5 shrink-0" />
            <span className="min-w-0 flex-1 truncate">Organisation</span>
            <CaretRightIcon
              aria-hidden
              className="size-3 shrink-0"
              style={{ color: 'var(--text-mute)' }}
            />
          </DropdownMenuSubTrigger>

          <DropdownMenuSubContent className="dash-menu dash-scroll w-56">
            {(orgs ?? []).map((org) => (
              <DropdownMenuItem key={org.id} onSelect={() => switchOrg(org.id)}>
                <OrgMark name={org.name} logoUrl={org.logo_url} size="sm" />
                <span className="min-w-0 flex-1 truncate">{org.name}</span>
                {org.id === profile.active.org_id ? (
                  <span
                    aria-label="Current organisation"
                    className="size-1.5 shrink-0 rounded-full"
                    style={{ background: 'var(--dash-brand)' }}
                  />
                ) : null}
              </DropdownMenuItem>
            ))}

            <DropdownMenuSeparator />

            <DropdownMenuItem>
              <Link
                href="/app/organisation/new"
                className="flex flex-1 items-center gap-2.5"
              >
                <PlusIcon aria-hidden className="size-3.5 shrink-0" />
                New organisation
              </Link>
            </DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>

        {/* Deep-links straight to the pane that does it, rather than to
            Settings for the reader to find. Only for a role that may
            actually send an invite. */}
        {profile.permissions.includes('team:invite') ? (
          <DropdownMenuItem>
            <Link
              href="/app/settings?tab=team"
              className="flex flex-1 items-center gap-2.5"
            >
              <UserPlusIcon aria-hidden className="size-3.5 shrink-0" />
              Invite teammate
            </Link>
          </DropdownMenuItem>
        ) : null}

        <DropdownMenuItem destructive onSelect={() => void signOut()}>
          <SignOutIcon aria-hidden className="size-3.5 shrink-0" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
