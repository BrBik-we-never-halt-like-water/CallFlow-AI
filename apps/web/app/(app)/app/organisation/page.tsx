'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useState } from 'react';
import { InviteDialog, ROLES } from '@/components/app/invite-dialog';
import { SessionGate } from '@/components/app/session-gate';
import {
  NotWiredNotice,
  SettingsSection,
} from '@/components/app/settings-section';
import { Tag } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { EmptyState } from '@/components/ui/empty-state';
import { Field } from '@/components/ui/field';
import { ImageUpload } from '@/components/ui/image-upload';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { TabPanel, Tabs } from '@/components/ui/disclosure';
import { useToast } from '@/components/ui/toast';
import { api, type Member, type PendingInvite, type Team } from '@/lib/api';
import { formatAge, formatTimestamp } from '@/lib/format';
import { useActiveOrg } from '@/lib/hooks/use-active-org';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession, type SessionProfile } from '@/lib/hooks/use-session';

/**
 * Managing this organisation and its team.
 *
 * A real page, not a dialog you navigate away from and lose your place in - this
 * was a modal for one iteration and it read as a demotion of something that
 * deserves a proper screen: who's a member, what they can do, and the identity
 * calls introduce themselves with are all as consequential as anything in Settings.
 */
export default function OrganisationPage() {
  return (
    <Suspense fallback={<PageFallback />}>
      <OrganisationPageContent />
    </Suspense>
  );
}

function OrganisationPageContent() {
  const session = useSession();
  const searchParams = useSearchParams();
  const initialTab =
    searchParams.get('tab') === 'team' ? 'team' : 'organisation';
  const [tab, setTab] = useState(initialTab);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="text-small font-bold text-text-mute">Organisation</p>
        <h1 className="font-display text-h2 text-text">
          <SessionGate session={session} skeletonClassName="h-9 w-64">
            {(profile) => profile.active.org_name}
          </SessionGate>
        </h1>
        <p className="measure text-small text-text-dim">
          How this organisation introduces itself on every call, and who&apos;s
          allowed inside it.
        </p>
      </div>

      <SessionGate session={session}>
        {(profile) => (
          <Tabs
            value={tab}
            onValueChange={setTab}
            tabs={[
              { value: 'organisation', label: 'Organisation' },
              { value: 'team', label: 'Team' },
            ]}
          >
            <TabPanel value="organisation" className="max-w-2xl pt-6">
              <OrganisationPane profile={profile} refresh={session.refresh} />
            </TabPanel>
            <TabPanel value="team" className="max-w-2xl pt-6">
              <TeamPane profile={profile} />
            </TabPanel>
          </Tabs>
        )}
      </SessionGate>
    </div>
  );
}

function PageFallback() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="text-small font-bold text-text-mute">Organisation</p>
        <Skeleton className="h-9 w-64" />
      </div>
      <Skeleton className="h-40 w-full max-w-2xl" />
    </div>
  );
}

function OrganisationPane({
  profile,
  refresh,
}: {
  profile: SessionProfile;
  refresh: () => void;
}) {
  const [name, setName] = useState(profile.active.org_name);
  const [logoUrl, setLogoUrl] = useState(profile.active.org_logo_url);

  const canUpdate = profile.permissions.includes('org:update');
  const canDelete = profile.permissions.includes('org:delete');

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Details"
        effect={`Calls introduce themselves as calling on behalf of "${name || profile.active.org_name}".`}
        footer={
          canUpdate ? (
            <SaveButton
              name={name}
              logoUrl={logoUrl}
              initialName={profile.active.org_name}
              initialLogoUrl={profile.active.org_logo_url}
              refresh={refresh}
            />
          ) : undefined
        }
      >
        <div className="flex flex-col gap-4">
          <Field label="Logo">
            <ImageUpload
              bucket="org-logos"
              ownerId={profile.active.org_id}
              value={logoUrl}
              onChange={setLogoUrl}
              label="Upload an organisation logo"
              shape="square"
            />
          </Field>

          <Field label="Organisation name">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={!canUpdate}
            />
          </Field>
        </div>
      </SettingsSection>

      {canDelete ? (
        <DeleteOrgSection orgName={profile.active.org_name} />
      ) : null}
    </div>
  );
}

function SaveButton({
  name,
  logoUrl,
  initialName,
  initialLogoUrl,
  refresh,
}: {
  name: string;
  logoUrl: string | null;
  initialName: string;
  initialLogoUrl: string | null;
  refresh: () => void;
}) {
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const dirty = name.trim() !== initialName || logoUrl !== initialLogoUrl;

  async function save() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await api.updateActiveOrganisation({
        name: name.trim() !== initialName ? name.trim() : undefined,
        logo_url: logoUrl && logoUrl !== initialLogoUrl ? logoUrl : undefined,
      });
      refresh();
      toast({ tone: 'success', title: 'Organisation updated' });
    } catch (error) {
      toast({
        tone: 'error',
        title: "Couldn't save changes",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Button size="sm" onClick={save} loading={saving} disabled={!dirty}>
      Save changes
    </Button>
  );
}

function DeleteOrgSection({ orgName }: { orgName: string }) {
  const [confirming, setConfirming] = useState(false);

  return (
    <>
      <SettingsSection
        title="Delete this organisation"
        description="Removes everyone's access. Campaigns and runs made under it are gone for good."
        footer={
          <Button
            variant="danger"
            size="sm"
            onClick={() => setConfirming(true)}
          >
            Delete organisation
          </Button>
        }
      />
      <DeleteOrgDialog
        open={confirming}
        onOpenChange={setConfirming}
        orgName={orgName}
      />
    </>
  );
}

function DeleteOrgDialog({
  open,
  onOpenChange,
  orgName,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  orgName: string;
}) {
  const router = useRouter();
  const toast = useToast();
  const [typed, setTyped] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [, setActiveOrgId] = useActiveOrg();

  async function confirmDelete() {
    setDeleting(true);
    try {
      await api.deleteActiveOrganisation();
      setActiveOrgId('');
      onOpenChange(false);
      toast({ tone: 'success', title: 'Organisation deleted' });
      router.replace('/app');
      router.refresh();
    } catch (error) {
      toast({
        tone: 'error',
        title: "Couldn't delete the organisation",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setDeleting(false);
    }
  }

  return (
    <DialogRoot
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) setTyped('');
      }}
    >
      <Dialog
        title={`Delete "${orgName}"?`}
        description="This can't be undone. Type the organisation name to confirm."
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={confirmDelete}
              loading={deleting}
              disabled={typed.trim() !== orgName}
            >
              Delete organisation
            </Button>
          </>
        }
      >
        <Field label={`Type "${orgName}" to confirm`}>
          <Input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            autoFocus
          />
        </Field>
      </Dialog>
    </DialogRoot>
  );
}

function TeamPane({ profile }: { profile: SessionProfile }) {
  const toast = useToast();
  const [team, setTeam] = useState<Team | null>(null);
  const [loading, setLoading] = useState(true);
  const [inviting, setInviting] = useState(false);

  function load() {
    api
      .listMembers()
      .then(setTeam)
      .catch(() => toast({ tone: 'error', title: "Couldn't load the team" }))
      .finally(() => setLoading(false));
  }

  useOrgScopedEffect(() => {
    void load();
  });

  const canInvite = profile.permissions.includes('team:invite');
  const canRemove = profile.permissions.includes('team:remove');
  const canSetRole = profile.permissions.includes('team:set_role');

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
        ) : !team ||
          (team.members.length === 0 && team.pending.length === 0) ? (
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
              <PendingRow
                key={invite.id}
                invite={invite}
                canRevoke={canInvite}
                onChanged={load}
              />
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
                <span className="text-small font-medium text-text">
                  {r.label}
                </span>
                <span className="text-small text-text-dim">{r.hint}</span>
              </div>
              {r.value === 'admin' ? <Tag>Billing &amp; safety</Tag> : null}
            </li>
          ))}
        </ul>
      </SettingsSection>

      <NotWiredNotice>
        Owners get every permission, including deleting the organisation and
        transferring ownership. There is no dedicated &ldquo;Owner&rdquo; row
        above because it can&apos;t be granted here - it moves with the
        organisation.
      </NotWiredNotice>

      <InviteDialog
        open={inviting}
        onOpenChange={setInviting}
        onInvited={load}
      />
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
  const isOwner = member.role === 'owner';

  async function remove() {
    setBusy(true);
    try {
      await api.removeMember(member.user_id);
      toast({
        tone: 'success',
        title: self ? 'You left the organisation' : 'Teammate removed',
      });
      onChanged();
    } catch (error) {
      toast({
        tone: 'error',
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
      toast({ tone: 'success', title: 'Role updated' });
      onChanged();
    } catch (error) {
      toast({
        tone: 'error',
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
          {self ? ' (you)' : ''}
        </span>
        <span className="truncate text-small text-text-dim">
          {member.email}
        </span>
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
                    <DropdownMenuItem
                      key={r.value}
                      onSelect={() => setRole(r.value)}
                    >
                      Make {r.label}
                    </DropdownMenuItem>
                  ))
                : null}
              {canRemove || self ? (
                <DropdownMenuItem destructive onSelect={remove}>
                  {self ? 'Leave organisation' : 'Remove'}
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
      toast({ tone: 'info', title: 'Invitation revoked' });
      onChanged();
    } catch {
      toast({ tone: 'error', title: "Couldn't revoke the invitation" });
    } finally {
      setRevoking(false);
    }
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-small font-medium text-text">
          {invite.email}
        </span>
        <span className="truncate text-small text-text-dim">
          Invited {formatAge(invite.created_at)} · expires{' '}
          {formatTimestamp(invite.expires_at)}
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
