"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { SessionGate } from "@/components/app/session-gate";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { ImageUpload } from "@/components/ui/image-upload";
import { Input } from "@/components/ui/input";
import { Eyebrow, Panel } from "@/components/ui/panel";
import { isPasswordValid, PasswordStrength } from "@/components/ui/password-strength";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { signOut, updatePassword } from "@/lib/auth/actions";
import { useSession, type SessionProfile } from "@/lib/hooks/use-session";

/**
 * Your profile — deliberately not a Settings tab.
 *
 * Settings configures the organisation; this page is about the one person
 * signed in. Splitting them means neither surface has to explain why a personal
 * setting lives inside an organisation-wide screen, or vice versa.
 */
export default function ProfilePage() {
  const session = useSession();

  return (
    <div className="flex flex-col gap-6">
      <Header />
      <SessionGate session={session}>
        {(profile) => (
          <div className="flex max-w-2xl flex-col gap-4">
            <ProfileDetails profile={profile} refresh={session.refresh} />
            <ChangePasswordPanel />
            <SignOutPanel />
          </div>
        )}
      </SessionGate>
    </div>
  );
}

function Header() {
  return (
    <div className="flex flex-col gap-1">
      <Eyebrow>Account</Eyebrow>
      <h1 className="font-display text-h2 text-text">Your profile</h1>
    </div>
  );
}

function ProfileDetails({
  profile,
  refresh,
}: {
  profile: SessionProfile;
  refresh: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(profile.name ?? "");
  const [avatarUrl, setAvatarUrl] = useState(profile.avatar_url);
  const [saving, setSaving] = useState(false);

  const dirty = name.trim() !== (profile.name ?? "") || avatarUrl !== profile.avatar_url;

  async function save() {
    setSaving(true);
    try {
      await api.updateProfile({
        name: name.trim() !== profile.name ? name.trim() : undefined,
        avatar_url: avatarUrl && avatarUrl !== profile.avatar_url ? avatarUrl : undefined,
      });
      refresh();
      toast({ tone: "success", title: "Profile updated" });
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
    <Panel className="flex flex-col gap-4 p-4 sm:p-5">
      <div className="flex flex-col gap-1">
        <h2 className="text-h3 font-medium text-text">Details</h2>
        <p className="measure text-small text-text-dim">
          How you appear to teammates in every organisation you belong to.
        </p>
      </div>

      <Field label="Avatar">
        <ImageUpload
          bucket="avatars"
          ownerId={profile.user_id}
          value={avatarUrl}
          onChange={setAvatarUrl}
          label="Upload a profile picture"
        />
      </Field>

      <Field label="Name">
        <Input value={name} onChange={(e) => setName(e.target.value)} />
      </Field>

      <Field label="Email">
        <Input value={profile.email} disabled />
      </Field>

      <div className="border-t border-rule pt-3">
        <Button size="sm" onClick={save} loading={saving} disabled={!dirty}>
          Save changes
        </Button>
      </div>
    </Panel>
  );
}

function ChangePasswordPanel() {
  const toast = useToast();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({});
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const found: typeof errors = {};
    if (!isPasswordValid(password)) {
      found.password = "Meet all four requirements below before continuing.";
    }
    if (confirm !== password) found.confirm = "These two don't match.";
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSaving(true);
    const result = await updatePassword(password);
    if (!result.ok) {
      setErrors({ password: result.error });
      setSaving(false);
      return;
    }
    setPassword("");
    setConfirm("");
    setSaving(false);
    toast({ tone: "success", title: "Password updated" });
  }

  return (
    <Panel className="flex flex-col gap-4 p-4 sm:p-5">
      <div className="flex flex-col gap-1">
        <h2 className="text-h3 font-medium text-text">Password</h2>
        <p className="measure text-small text-text-dim">
          Changing it signs you out everywhere else.
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="New password" error={errors.password}>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            disabled={saving}
          />
        </Field>

        <PasswordStrength value={password} />

        <Field label="Confirm new password" error={errors.confirm}>
          <Input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            disabled={saving}
          />
        </Field>

        <div className="border-t border-rule pt-3">
          <Button type="submit" size="sm" loading={saving} disabled={!password}>
            Update password
          </Button>
        </div>
      </form>
    </Panel>
  );
}

function SignOutPanel() {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  async function handleSignOut() {
    setSigningOut(true);
    await signOut();
    router.replace("/login");
    router.refresh();
  }

  return (
    <Panel className="flex flex-wrap items-center justify-between gap-3 p-4 sm:p-5">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-h3 font-medium text-text">Sign out</h2>
        <p className="text-small text-text-dim">Ends your session on this device.</p>
      </div>
      <Button variant="secondary" onClick={handleSignOut} loading={signingOut}>
        Sign out
      </Button>
    </Panel>
  );
}
