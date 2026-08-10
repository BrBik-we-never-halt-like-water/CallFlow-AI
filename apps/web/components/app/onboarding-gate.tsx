'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { Field } from '@/components/ui/field';
import { ImageUpload } from '@/components/ui/image-upload';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { useToast } from '@/components/ui/toast';
import { ROLES } from '@/components/app/invite-dialog';
import { api } from '@/lib/api';
import { useSession, type SessionProfile } from '@/lib/hooks/use-session';

type WizardStep = 'organisation' | 'profile' | 'invite';

/**
 * Forces the org setup step on any organisation that hasn't completed it, as a
 * non-dismissible modal over the dashboard rather than a separate route.
 *
 * The signal is `active.onboarded_at` from `/api/v1/me` - server data, not a
 * `localStorage` flag - so it can't be bypassed by clearing storage or opening
 * a new device. This component owns one `useSession()` instance and the modal
 * reads/writes through it directly: a previous version used a separate page
 * per step, each with its own independent `useSession()` call, so finishing
 * step one updated a session snapshot nothing else was reading and the app
 * bounced back to step one forever. One instance, one source of truth, fixes
 * that structurally rather than by adding a delay or a retry.
 */
export function OnboardingGate({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const [step, setStep] = useState<WizardStep | null>(null);

  const needsOrgSetup =
    session.status === 'signed-in' &&
    session.profile.active.onboarded_at === null;
  const activeStep: WizardStep | null = needsOrgSetup ? 'organisation' : step;

  return (
    <>
      {children}
      <DialogRoot open={activeStep !== null} onOpenChange={() => {}}>
        {activeStep === 'organisation' && session.status === 'signed-in' ? (
          <OrganisationStep
            profile={session.profile}
            refresh={session.refresh}
            onDone={() => setStep('profile')}
          />
        ) : activeStep === 'profile' && session.status === 'signed-in' ? (
          <ProfileStep
            profile={session.profile}
            onDone={() => setStep('invite')}
          />
        ) : activeStep === 'invite' && session.status === 'signed-in' ? (
          <InviteStep onDone={() => setStep(null)} />
        ) : null}
      </DialogRoot>
    </>
  );
}

function OrganisationStep({
  profile,
  refresh,
  onDone,
}: {
  profile: SessionProfile;
  refresh: () => Promise<void>;
  onDone: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(profile.active.org_name);
  const [saving, setSaving] = useState(false);

  const trimmed = name.trim();
  const valid = trimmed.length >= 2;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!valid || saving) return;
    setSaving(true);
    try {
      await api.completeOnboarding(trimmed);
      // Awaited deliberately: the next render needs the fresh `onboarded_at`
      // before `onDone` hands off to the profile step, or `needsOrgSetup`
      // would still read true for one more render and reopen this same step.
      await refresh();
      onDone();
    } catch (error) {
      toast({
        tone: 'error',
        title: "That didn't save",
        body:
          error instanceof Error
            ? error.message
            : "The service didn't respond.",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Name your organisation" dismissible={false} size="sm">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <p className="measure text-small text-text-dim">
          We guessed a name from your email - {profile.active.org_name}.
          Everyone you invite will see whatever you set here, so make it the one
          your team will recognise.
        </p>

        <Field label="Organisation name" required>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            maxLength={120}
          />
        </Field>

        <div className="flex items-center gap-3 border-t border-rule pt-4">
          <Button type="submit" loading={saving} disabled={!valid}>
            Continue
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function ProfileStep({
  profile,
  onDone,
}: {
  profile: SessionProfile;
  onDone: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(profile.name ?? '');
  const [avatarUrl, setAvatarUrl] = useState(profile.avatar_url);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await api.updateProfile({
        name: name.trim() ? name.trim() : undefined,
        avatar_url: avatarUrl ?? undefined,
      });
      onDone();
    } catch (error) {
      toast({
        tone: 'error',
        title: "That didn't save",
        body:
          error instanceof Error
            ? error.message
            : "The service didn't respond.",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog title="Add your name and photo" dismissible={false} size="sm">
      <div className="flex flex-col gap-4">
        <p className="measure text-small text-text-dim">
          This is how teammates see you next to the calls you triage. You can
          change it any time from Profile.
        </p>

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
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
        </Field>

        <div className="flex items-center gap-3 border-t border-rule pt-4">
          <Button onClick={save} loading={saving}>
            Continue
          </Button>
          <Button variant="ghost" onClick={onDone} disabled={saving}>
            Skip for now
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function InviteStep({ onDone }: { onDone: () => void }) {
  const toast = useToast();
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('operator');
  const [sending, setSending] = useState(false);

  async function send() {
    if (!email.trim()) return;
    setSending(true);
    try {
      await api.inviteMember(email.trim(), role);
      toast({ tone: 'success', title: 'Invitation sent', body: email.trim() });
      onDone();
    } catch (error) {
      toast({
        tone: 'error',
        title: "Couldn't send the invitation",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSending(false);
    }
  }

  return (
    <Dialog title="Invite a teammate" dismissible={false} size="sm">
      <div className="flex flex-col gap-4">
        <p className="measure text-small text-text-dim">
          Optional - they&apos;ll get an email with a link, and nothing happens
          on their account until they accept it. You can always invite people
          later from Settings.
        </p>

        <Field label="Work email">
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoFocus
          />
        </Field>
        <Field
          label="Role"
          help="Operators can run campaigns but not change billing."
        >
          <Select value={role} onValueChange={setRole} options={ROLES} />
        </Field>

        <div className="flex items-center gap-3 border-t border-rule pt-4">
          <Button onClick={send} loading={sending} disabled={!email.trim()}>
            Send invitation
          </Button>
          <Button variant="ghost" onClick={onDone} disabled={sending}>
            Skip for now
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
