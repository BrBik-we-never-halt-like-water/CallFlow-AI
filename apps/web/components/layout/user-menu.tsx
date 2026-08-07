"use client";

import { CheckIcon, PlusIcon, SignOutIcon, UserCircleIcon } from "@phosphor-icons/react/dist/ssr";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { CreateOrgDialog } from "@/components/app/create-org-dialog";
import { Tag } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { signOut } from "@/lib/auth/actions";
import { useActiveOrg } from "@/lib/hooks/use-active-org";
import { useOrganisations } from "@/lib/hooks/use-organisations";
import type { SessionProfile } from "@/lib/hooks/use-session";

export function UserMenu({
  profile,
  loading,
  refreshSession,
}: {
  profile: SessionProfile | null;
  loading: boolean;
  refreshSession: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const [signingOut, setSigningOut] = useState(false);
  const { orgs, refresh: refreshOrgs } = useOrganisations(profile);
  const [creating, setCreating] = useState(false);
  const [, setActiveOrgId] = useActiveOrg();

  if (loading) return <Skeleton className="size-9 rounded-full" />;
  if (!profile) return null;

  const label = profile.name?.trim() || profile.email;
  const initial = label.charAt(0).toUpperCase();

  async function handleSignOut() {
    setSigningOut(true);
    await signOut();
    // replace, not push: the dashboard must not be reachable with Back after
    // signing out. refresh() clears the server-rendered session too.
    router.replace("/login");
    router.refresh();
  }

  function switchOrg(orgId: string) {
    if (orgId === profile?.active.org_id) return;
    setActiveOrgId(orgId);
    refreshSession();
  }

  return (
    <>
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
            <span className="truncate text-small font-medium text-text">{label}</span>
            <span className="truncate text-small text-text-mute">{profile.email}</span>
          </div>

          <DropdownMenuSeparator />
          <DropdownMenuLabel>Organisation</DropdownMenuLabel>

          {(
            orgs ?? [
              {
                id: profile.active.org_id,
                name: profile.active.org_name,
                slug: profile.active.org_slug,
                logo_url: profile.active.org_logo_url,
                role: profile.active.role,
              },
            ]
          ).map((org) => (
            <DropdownMenuItem key={org.id} onSelect={() => switchOrg(org.id)}>
              <span className="flex flex-1 items-center gap-2 truncate">
                {org.id === profile.active.org_id ? (
                  <CheckIcon aria-hidden weight="bold" className="size-4 shrink-0" />
                ) : (
                  <span className="size-4 shrink-0" aria-hidden />
                )}
                <span className="truncate">{org.name}</span>
              </span>
              <Tag>{org.role}</Tag>
            </DropdownMenuItem>
          ))}

          <DropdownMenuItem onSelect={() => setCreating(true)}>
            <PlusIcon aria-hidden className="size-4" />
            New organisation
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          <DropdownMenuItem>
            <Link href="/app/profile" className="flex flex-1 items-center gap-2">
              <UserCircleIcon aria-hidden className="size-4" />
              Profile
            </Link>
          </DropdownMenuItem>

          <DropdownMenuItem>
            <Link href="/app/settings" className="flex flex-1 items-center gap-2">
              <UserCircleIcon aria-hidden className="size-4" />
              Settings
            </Link>
          </DropdownMenuItem>

          <DropdownMenuItem onSelect={handleSignOut} disabled={signingOut}>
            <SignOutIcon aria-hidden className="size-4" />
            {signingOut ? "Signing out…" : "Sign out"}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <CreateOrgDialog
        open={creating}
        onOpenChange={setCreating}
        onCreated={(org) => {
          refreshOrgs();
          switchOrg(org.id);
          toast({ tone: "success", title: "Organisation created", body: org.name });
        }}
      />
    </>
  );
}
