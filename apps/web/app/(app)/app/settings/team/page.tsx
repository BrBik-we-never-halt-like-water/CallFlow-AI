"use client";

import { useEffect, useState } from "react";
import { NotWiredNotice, SettingsSection } from "@/components/app/settings-section";
import { SessionGate } from "@/components/app/session-gate";
import { InviteDialog, ROLES } from "@/components/app/invite-dialog";
import { Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { formatAge, formatTimestamp } from "@/lib/format";
import { api, type Member, type PendingInvite, type Team } from "@/lib/api";
import { useSession, type SessionProfile } from "@/lib/hooks/use-session";

export default function TeamSettingsPage() {
  const session = useSession();
  return (
    <SessionGate session={session}>
      {(profile) => <TeamSettingsContent profile={profile} />}
    </SessionGate>
  );
}

function TeamSettingsContent({ profile }: { profile: SessionProfile }) {
  const toast = useToast();

  const [team, setTeam] = useState<Team | null>(null);
  const [loading, setLoading] = useState(true);
  const [inviting, setInviting] = useState(false);

  function load() {
    api
      .listMembers()
      .then(setTeam)
      .catch(() =>
        toast({ tone: "error", title: "Couldn't load the team" }),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile.active.org_id]);

  const canInvite = profile.permissions.includes("team:invite");
  const canRemove = profile.permissions.includes("team:remove");
  const canSetRole = profile.permissions.includes("team:set_role");

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Members"
        description="Who can get into this organisation, and what they're allowed to do."
        footer={
          canInvite ? (
            <Button size="sm" onClick={() => setInviting(true)}>
              Invite a teammate
            </Button>
          ) : undefined
        }
      >
        {loading ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : !team || (team.members.length === 0 && team.pending.length === 0) ? (
          <EmptyState
            title="It's just you"
            body="Invite the people who triage escalations. Give them Operator, and reserve Admin for whoever manages billing and safety settings."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-rule">
            {team.members.map((member) => (
              <MemberRow
                key={member.user_id}
                member={member}
                self={member.user_id === profile.user_id}
                canRemove={canRemove}
                canSetRole={canSetRole}
                onChanged={load}
              />
            ))}
            {team.pending.map((invite) => (
              <PendingRow key={invite.id} invite={invite} canRevoke={canInvite} onChanged={load} />
            ))}
          </ul>
        )}
      </SettingsSection>

      <SettingsSection
        title="Roles"
        description="What each role can do. Permissions are fixed rather than per-user, so access is predictable."
      >
        <ul className="flex flex-col">
          {ROLES.map((r) => (
            <li
              key={r.value}
              className="flex flex-wrap items-start justify-between gap-3 border-b border-rule py-3 last:border-0"
            >
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="text-small font-medium text-text">{r.label}</span>
                <span className="text-small text-text-dim">{r.hint}</span>
              </div>
              {r.value === "admin" ? <Tag>Billing &amp; safety</Tag> : null}
            </li>
          ))}
        </ul>
      </SettingsSection>

      <NotWiredNotice>
        Owners get every permission, including deleting the organisation and
        transferring ownership. There is no dedicated &ldquo;Owner&rdquo; row above because
        it can&apos;t be granted here — it moves with the organisation.
      </NotWiredNotice>

      <InviteDialog open={inviting} onOpenChange={setInviting} onInvited={load} />
    </div>
  );
}

function MemberRow({
  member,
  self,
  canRemove,
  canSetRole,
  onChanged,
}: {
  member: Member;
  self: boolean;
  canRemove: boolean;
  canSetRole: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const canAct = (canRemove || self) && !busy;
  const isOwner = member.role === "owner";

  async function remove() {
    setBusy(true);
    try {
      await api.removeMember(member.user_id);
      toast({
        tone: "success",
        title: self ? "You left the organisation" : "Teammate removed",
      });
      onChanged();
    } catch (error) {
      toast({
        tone: "error",
        title: "Couldn't remove",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setBusy(false);
    }
  }

  async function setRole(role: string) {
    setBusy(true);
    try {
      await api.setMemberRole(member.user_id, role);
      toast({ tone: "success", title: "Role updated" });
      onChanged();
    } catch (error) {
      toast({
        tone: "error",
        title: "Couldn't update the role",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-small font-medium text-text">
          {member.name?.trim() || member.email}
          {self ? " (you)" : ""}
        </span>
        <span className="truncate text-small text-text-dim">{member.email}</span>
      </div>
      <div className="flex items-center gap-2">
        <Tag>{member.role}</Tag>
        {(canRemove || (canSetRole && !isOwner) || self) && !isOwner ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" disabled={!canAct}>
                Manage
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {canSetRole && !self
                ? ROLES.map((r) => (
                    <DropdownMenuItem key={r.value} onSelect={() => setRole(r.value)}>
                      Make {r.label}
                    </DropdownMenuItem>
                  ))
                : null}
              {canRemove || self ? (
                <DropdownMenuItem destructive onSelect={remove}>
                  {self ? "Leave organisation" : "Remove"}
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>
    </li>
  );
}

function PendingRow({
  invite,
  canRevoke,
  onChanged,
}: {
  invite: PendingInvite;
  canRevoke: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [revoking, setRevoking] = useState(false);

  async function revoke() {
    setRevoking(true);
    try {
      await api.revokeInvitation(invite.id);
      toast({ tone: "info", title: "Invitation revoked" });
      onChanged();
    } catch {
      toast({ tone: "error", title: "Couldn't revoke the invitation" });
    } finally {
      setRevoking(false);
    }
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-small font-medium text-text">{invite.email}</span>
        <span className="truncate text-small text-text-dim">
          Invited {formatAge(invite.created_at)} · expires {formatTimestamp(invite.expires_at)}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Tag>{invite.role}</Tag>
        {canRevoke ? (
          <Button variant="ghost" size="sm" onClick={revoke} loading={revoking}>
            Revoke
          </Button>
        ) : null}
      </div>
    </li>
  );
}
