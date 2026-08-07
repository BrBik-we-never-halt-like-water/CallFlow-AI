"use client";

import { CaretDownIcon, UserPlusIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useEffect, useState } from "react";
import { InviteDialog } from "@/components/app/invite-dialog";
import { SessionGate } from "@/components/app/session-gate";
import { Tag } from "@/components/ui/badge";
import { Popover } from "@/components/ui/disclosure";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Team } from "@/lib/api";
import type { SessionProfile, SessionState } from "@/lib/hooks/use-session";

/**
 * The dashboard's team roster popover — who else is in this organisation.
 *
 * Switching organisations lives in exactly one place now: the sidebar's org
 * switcher. This used to also render its own org-switching dropdown here,
 * which — alongside a third copy inside the user menu — meant three controls
 * for one job. This popover's only job is "who's on the team."
 */
export function TeamControls({
  session,
}: {
  session: SessionState & { refresh: () => void };
}) {
  return (
    <SessionGate session={session} skeletonClassName="h-9 w-24">
      {(profile) => <TeamMenu profile={profile} />}
    </SessionGate>
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
            className="flex h-9 items-center gap-2 rounded-sm border border-rule px-2.5 transition-colors hover:bg-surface-hover"
            aria-label="Team"
          >
            <span className="eyebrow text-text-mute">Team</span>
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
