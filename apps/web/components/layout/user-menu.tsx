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
import type { SessionProfile } from '@/lib/hooks/use-session';

/**
 * The signed-in user's own menu - the one account entry point now that there
 * is no sidebar to also carry one. Organisation and Settings are lower-
 * frequency than the header's primary nav row (`PrimaryNav`, app-shell.tsx),
 * so they fold in here rather than compressing that row to fit all seven
 * destinations. Organisation *switching* stays a separate control
 * (`HeaderOrgSwitcher`) - this menu is "you," not "which workspace."
 */
export function UserMenu({
  profile,
  loading,
}: {
  profile: SessionProfile | null;
  loading: boolean;
}) {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  if (loading) return <Skeleton className="size-9 rounded-full" />;
  if (!profile) return null;

  const label = profile.name?.trim() || profile.email;
  const initial = label.charAt(0).toUpperCase();

  async function handleSignOut() {
    setSigningOut(true);
    await signOut();
    // replace, not push: the dashboard must not be reachable with Back after
    // signing out. refresh() clears the server-rendered session too.
    router.replace('/login');
    router.refresh();
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Account menu for ${label}`}
          className="flex size-9 cursor-pointer items-center justify-center rounded-full border border-rule bg-surface-sunken text-small font-medium text-text transition-colors hover:bg-surface-hover"
        >
          {initial}
        </button>
      </DropdownMenuTrigger>

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

        <DropdownMenuItem onSelect={handleSignOut} disabled={signingOut}>
          <SignOutIcon aria-hidden className="size-4" />
          {signingOut ? 'Signing out…' : 'Sign out'}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
