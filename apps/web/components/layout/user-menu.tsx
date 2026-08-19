'use client';

import {
  BuildingsIcon,
  GearSixIcon,
  SignOutIcon,
  UserCircleIcon,
} from '@phosphor-icons/react/dist/ssr';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useState } from 'react';
import { cn } from '@/lib/cn';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { signOut } from '@/lib/auth/actions';
import { hasRole } from '@/lib/hooks/use-permission';
import type { SessionProfile } from '@/lib/hooks/use-session';

/**
 * The signed-in user's own menu - the one account entry point. Organisation
 * and Settings are lower-frequency than the sidebar's primary nav list
 * (`AppSidebar`, app-shell.tsx), so they fold in here rather than adding two
 * more rows to that list for two rarely-visited destinations. Organisation
 * *switching* stays a separate control (`SidebarOrgSwitcher`) - this menu is
 * "you," not "which workspace." Both entries are owner/admin-only - an
 * operator or viewer gets "My credits" in Settings' place instead, since
 * neither section has anything relevant to them (role-based UI roadmap,
 * Phase 0).
 *
 * `variant="tab"` (default `"avatar"`) swaps only the trigger's own shape -
 * the round avatar button becomes a tab-bar-style column (photo/initial on
 * top, a short label below), matching `AppTabBar`'s other items
 * (`app-nav.tsx`) exactly, since that is now this menu's only mobile entry
 * point with `AppTopBar` removed. The dropdown content, and everything in
 * it including sign-out, is identical either way - one account menu, two
 * trigger shapes for the two surfaces it can sit on.
 */
export function UserMenu({
  profile,
  loading,
  variant = 'avatar',
}: {
  profile: SessionProfile | null;
  loading: boolean;
  variant?: 'avatar' | 'tab';
}) {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  if (loading) {
    return variant === 'tab' ? (
      <div className="flex min-h-14 flex-1 items-center justify-center">
        <Skeleton className="size-6 rounded-full" />
      </div>
    ) : (
      <Skeleton className="size-9 rounded-full" />
    );
  }
  if (!profile) return null;

  const label = profile.name?.trim() || profile.email;
  const initial = label.charAt(0).toUpperCase();
  const isOwnerOrAdmin = hasRole(profile, 'owner', 'admin');

  async function handleSignOut() {
    setSigningOut(true);
    await signOut();
    // replace, not push: the dashboard must not be reachable with Back after
    // signing out. refresh() clears the server-rendered session too.
    router.replace('/login');
    router.refresh();
  }

  const avatar = profile.avatar_url ? (
    <img
      src={profile.avatar_url}
      alt=""
      className={cn(
        'shrink-0 rounded-full object-cover',
        variant === 'tab' ? 'size-5' : 'size-full',
      )}
    />
  ) : (
    <span
      className={cn(
        'flex shrink-0 items-center justify-center rounded-full font-medium text-text',
        variant === 'tab'
          ? 'size-5 bg-surface-sunken text-label'
          : 'size-full bg-surface-sunken text-small',
      )}
    >
      {initial}
    </span>
  );

  const trigger =
    variant === 'tab' ? (
      <button
        type="button"
        aria-label={`Account menu for ${label}`}
        className="relative flex min-h-14 flex-1 flex-col items-center justify-center gap-1 px-1 py-2 text-text-mute"
      >
        {avatar}
        <span className="truncate text-[0.6875rem] leading-none">
          Account
        </span>
      </button>
    ) : (
      <button
        type="button"
        aria-label={`Account menu for ${label}`}
        // The avatar (a photo or an opaque initials fallback) fills the
        // whole button, so a hover *background* would never show through
        // it - a ring around the outside is the one hover treatment that
        // still reads regardless of which fallback state is showing.
        className="flex size-9 cursor-pointer items-center justify-center overflow-hidden rounded-full border border-rule ring-2 ring-transparent transition-[background-color,box-shadow] hover:ring-surface-hover"
      >
        {avatar}
      </button>
    );

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>

      <DropdownMenuContent>
        <DropdownMenuLabel>Signed in</DropdownMenuLabel>

        <div className="flex flex-col gap-1 px-2 pb-2">
          <span className="truncate text-small font-medium text-text">
            {label}
          </span>
          <span className="truncate text-small text-text-mute">
            {profile.email}
          </span>
        </div>

        <DropdownMenuSeparator />

        <DropdownMenuItem>
          <Link href="/app/profile" className="flex flex-1 items-center gap-2">
            <UserCircleIcon aria-hidden className="size-4" />
            Profile
          </Link>
        </DropdownMenuItem>

        {/* Organisation/Settings are owner+admin destinations, matching the same
            restriction the sidebar's footer links apply (app-shell.tsx). An
            operator or viewer gets neither - and no longer gets a "My credits"
            entry either, because Billing became a sidebar destination and that
            page already shows a non-admin their own credits rather than the
            organisation's plan. Two links to one page is how one of them goes
            stale. */}
        {isOwnerOrAdmin ? (
          <>
            <DropdownMenuItem>
              <Link
                href="/app/organisation"
                className="flex flex-1 items-center gap-2"
              >
                <BuildingsIcon aria-hidden className="size-4" />
                Organisation
              </Link>
            </DropdownMenuItem>

            <DropdownMenuItem>
              <Link href="/app/settings" className="flex flex-1 items-center gap-2">
                <GearSixIcon aria-hidden className="size-4" />
                Settings
              </Link>
            </DropdownMenuItem>
          </>
        ) : null}

        <DropdownMenuItem onSelect={handleSignOut} disabled={signingOut}>
          <SignOutIcon aria-hidden className="size-4" />
          {signingOut ? 'Signing out…' : 'Sign out'}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
