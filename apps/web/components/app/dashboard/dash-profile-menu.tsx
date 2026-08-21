'use client';

import {
  BuildingsIcon,
  CaretDownIcon,
  CaretRightIcon,
  GearSixIcon,
  PlusIcon,
  SignOutIcon,
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

      <DropdownMenuContent align="start" className="dash-menu w-52">
        <DropdownMenuItem>
          <Link
            href="/app/profile"
            className="flex flex-1 items-center gap-2"
          >
            <GearSixIcon aria-hidden className="size-3.5 shrink-0" />
            Settings
          </Link>
        </DropdownMenuItem>

        {/* Organisation opens a submenu rather than carrying its controls
            inline: with more than a couple of organisations the row had
            nowhere to put them, and a hover-only control cannot be reached
            by keyboard at all. The submenu grows with the list and scrolls
            past the viewport, so an account in twenty organisations works
            the same as one in two. */}
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
                className="flex flex-1 items-center gap-2"
              >
                <PlusIcon aria-hidden className="size-3.5 shrink-0" />
                Add organisation
              </Link>
            </DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>

        {/* `destructive` is the shared menu's own red - signing out is the
            one irreversible thing in this list. */}
        <DropdownMenuItem destructive onSelect={() => void signOut()}>
          <SignOutIcon aria-hidden className="size-3.5 shrink-0" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
