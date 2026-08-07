"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { SettingsSection } from "@/components/app/settings-section";
import { SessionGate } from "@/components/app/session-gate";
import { Button } from "@/components/ui/button";
import { Dialog, DialogRoot } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { ImageUpload } from "@/components/ui/image-upload";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useActiveOrg } from "@/lib/hooks/use-active-org";
import { useSession, type SessionProfile } from "@/lib/hooks/use-session";

export default function OrganisationSettingsPage() {
  const session = useSession();
  return (
    <SessionGate session={session}>
      {(profile) => <OrganisationSettingsContent profile={profile} refresh={session.refresh} />}
    </SessionGate>
  );
}

function OrganisationSettingsContent({
  profile,
  refresh,
}: {
  profile: SessionProfile;
  refresh: () => void;
}) {
  const [name, setName] = useState(profile.active.org_name);
  const [logoUrl, setLogoUrl] = useState(profile.active.org_logo_url);

  const canUpdate = profile.permissions.includes("org:update");
  const canDelete = profile.permissions.includes("org:delete");

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Organisation"
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
            <Input value={name} onChange={(e) => setName(e.target.value)} disabled={!canUpdate} />
          </Field>
        </div>
      </SettingsSection>

      {canDelete ? <DeleteOrgSection orgName={profile.active.org_name} /> : null}
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
      toast({ tone: "success", title: "Organisation updated" });
    } catch (error) {
      toast({
        tone: "error",
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
          <Button variant="danger" size="sm" onClick={() => setConfirming(true)}>
            Delete organisation
          </Button>
        }
      />
      <DeleteOrgDialog open={confirming} onOpenChange={setConfirming} orgName={orgName} />
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
  const [typed, setTyped] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [, setActiveOrgId] = useActiveOrg();

  async function confirmDelete() {
    setDeleting(true);
    try {
      await api.deleteActiveOrganisation();
      // The active org no longer exists — clear the pin so the next request falls
      // back to the server's default (earliest-joined) organisation.
      setActiveOrgId("");
      onOpenChange(false);
      toast({ tone: "success", title: "Organisation deleted" });
      router.replace("/app");
      router.refresh();
    } catch (error) {
      toast({
        tone: "error",
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
        if (!next) setTyped("");
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
          <Input value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus />
        </Field>
      </Dialog>
    </DialogRoot>
  );
}
