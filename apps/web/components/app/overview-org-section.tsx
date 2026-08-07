"use client";

import {
  CaretDownIcon,
  CheckIcon,
  GearSixIcon,
  PlusIcon,
  UserPlusIcon,
} from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CreateOrgDialog } from "@/components/app/create-org-dialog";
import { InviteDialog } from "@/components/app/invite-dialog";
import { SessionGate } from "@/components/app/session-gate";
import { Tag } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover } from "@/components/ui/disclosure";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { api, type Team } from "@/lib/api";
import { useActiveOrg } from "@/lib/hooks/use-active-org";
import { useOrganisations } from "@/lib/hooks/use-organisations";
import type { SessionProfile, SessionState } from "@/lib/hooks/use-session";

/**
 * Overview's org identity + team, as a slim control row — not a stack of boxes.
 * Organisation setup (rename, logo) lives one click away in Settings, reached
 * from here, rather than a conditional card that can silently fail to appear.
 */
export function OrgTeamControls({
  session,
}: {
  session: SessionState & { refresh: () => void };
}) {
  return (
    <SessionGate session={session} skeletonClassName="h-9 w-64">
      {(profile) => (
        <div className="flex flex-wrap items-center gap-2">
          <OrgMenu profile={profile} refreshSession={session.refresh} />
          <TeamMenu profile={profile} />
        </div>
      )}
    </SessionGate>
  );
}

function OrgAvatar({ name, logoUrl, size = "size-6" }: { name: string; logoUrl: string | null; size?: string }) {
  if (logoUrl) {
    // eslint-disable-next-line @next/next/no-img-element -- remote Supabase Storage URL
    return <img src={logoUrl} alt="" className={`${size} shrink-0 rounded-full object-cover`} />;
  }
  return (
    <span
      aria-hidden
      className={`flex ${size} shrink-0 items-center justify-center rounded-full bg-surface-inverse text-[0.65rem] font-medium text-text-inverse`}
    >
      {name.charAt(0).toUpperCase()}
    </span>
  );
}

function OrgMenu({
  profile,
  refreshSession,
}: {
  profile: SessionProfile;
  refreshSession: () => void;
}) {
  const toast = useToast();
  const { orgs, refresh: refreshOrgs } = useOrganisations(profile);
  const [, setActiveOrgId] = useActiveOrg();
  const [creating, setCreating] = useState(false);

  function switchOrg(orgId: string) {
    if (orgId === profile.active.org_id) return;
    setActiveOrgId(orgId);
    refreshSession();
  }

  const list =
    orgs ?? [
      {
        id: profile.active.org_id,
        name: profile.active.org_name,
        slug: profile.active.org_slug,
        logo_url: profile.active.org_logo_url,
        role: profile.active.role,
      },
    ];

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="flex h-9 items-center gap-2 rounded-sm border border-rule px-2.5 text-small font-medium text-text transition-colors hover:bg-surface-hover"
          >
            <OrgAvatar name={profile.active.org_name} logoUrl={profile.active.org_logo_url} />
            <span className="max-w-40 truncate">{profile.active.org_name}</span>
            <CaretDownIcon aria-hidden className="size-3.5 text-text-mute" />
          </button>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="start" className="min-w-64">
          <DropdownMenuLabel>Organisations</DropdownMenuLabel>
          {list.map((org) => (
            <DropdownMenuItem key={org.id} onSelect={() => switchOrg(org.id)}>
              {org.id === profile.active.org_id ? (
                <CheckIcon aria-hidden weight="bold" className="size-4 shrink-0" />
              ) : (
                <span className="size-4 shrink-0" aria-hidden />
              )}
              <span className="min-w-0 flex-1 truncate">{org.name}</span>
              <Tag>{org.role}</Tag>
            </DropdownMenuItem>
          ))}

          <DropdownMenuSeparator />

          <DropdownMenuItem onSelect={() => setCreating(true)}>
            <PlusIcon aria-hidden className="size-4" />
            New organisation
          </DropdownMenuItem>
          <DropdownMenuItem>
            <Link href="/app/settings" className="flex flex-1 items-center gap-2">
              <GearSixIcon aria-hidden className="size-4" />
              Organisation settings
            </Link>
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

function TeamMenu({ profile }: { profile: SessionProfile }) {
  const [team, setTeam] = useState<Team | null>(null);
  const [loading, setLoading] = useState(true);
  const [inviting, setInviting] = useState(false);
  const canInvite = profile.permissions.includes("team:invite");

  function load() {
    api
      .listMembers()
      .then(setTeam)
      .catch(() => setTeam(null))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    void load();
  }, [profile.active.org_id]);

  const members = team?.members ?? [];
  const shown = members.slice(0, 4);
  const overflow = members.length - shown.length;

  return (
    <>
      <Popover
        align="start"
        trigger={
          <button
            type="button"
            className="flex h-9 items-center gap-1.5 rounded-sm border border-rule px-2.5 transition-colors hover:bg-surface-hover"
            aria-label="Team"
          >
            {loading ? (
              <Skeleton className="size-6 rounded-full" />
            ) : shown.length === 0 ? (
              <span className="text-small text-text-dim">Just you</span>
            ) : (
              <span className="flex -space-x-1.5">
                {shown.map((m) => (
                  <span
                    key={m.user_id}
                    className="flex size-6 items-center justify-center rounded-full border border-surface-raised bg-surface-sunken text-[0.65rem] font-medium text-text"
                  >
                    {(m.name?.trim() || m.email).charAt(0).toUpperCase()}
                  </span>
                ))}
                {overflow > 0 ? (
                  <span className="flex size-6 items-center justify-center rounded-full border border-surface-raised bg-surface-inverse text-[0.6rem] font-medium text-text-inverse">
                    +{overflow}
                  </span>
                ) : null}
              </span>
            )}
            <CaretDownIcon aria-hidden className="size-3.5 text-text-mute" />
          </button>
        }
        className="w-72"
      >
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-2">
            <span className="eyebrow text-text-mute">Team</span>
            <Link
              href="/app/settings/team"
              className="text-small font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
            >
              Manage
            </Link>
          </div>

          {members.length === 0 ? (
            <p className="text-small text-text-dim">Nobody else here yet.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-rule">
              {members.map((m) => (
                <li key={m.user_id} className="flex items-center gap-2 py-2">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-rule bg-surface-sunken text-[0.65rem] font-medium text-text">
                    {(m.name?.trim() || m.email).charAt(0).toUpperCase()}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-small text-text">
                    {m.name?.trim() || m.email}
                  </span>
                  <Tag>{m.role}</Tag>
                </li>
              ))}
            </ul>
          )}

          {canInvite ? (
            <Button variant="secondary" size="sm" onClick={() => setInviting(true)}>
              <UserPlusIcon aria-hidden className="size-4" />
              Invite
            </Button>
          ) : null}
        </div>
      </Popover>

      <InviteDialog open={inviting} onOpenChange={setInviting} onInvited={load} />
    </>
  );
}
