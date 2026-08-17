'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { AuthCard } from '@/components/layout/auth-card';
import { Tag } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import {
  isPasswordValid,
  PasswordStrength,
} from '@/components/ui/password-strength';
import { useToast } from '@/components/ui/toast';
import { PENDING_WELCOME_KEY } from '@/components/app/welcome-modal';
import { api, type InvitationPreview } from '@/lib/api';
import {
  signInWithPassword,
  signOut,
  signUpWithPassword,
} from '@/lib/auth/actions';
import { useActiveOrg } from '@/lib/hooks/use-active-org';
import { useSession } from '@/lib/hooks/use-session';

const REASON_COPY: Record<string, string> = {
  not_found: "This invitation link isn't valid.",
  expired:
    'This invitation has expired. Ask whoever invited you to send a new one.',
  used: 'This invitation has already been used.',
};

export default function AcceptInvitePage() {
  const params = useParams<{ token: string }>();
  const token = typeof params?.token === 'string' ? params.token : '';

  const router = useRouter();
  const toast = useToast();
  const session = useSession();
  const [, setActiveOrgId] = useActiveOrg();

  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(true);

  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ name?: string; password?: string }>(
    {},
  );
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api
      .previewInvitation(token)
      .then((result) => {
        if (!cancelled) setPreview(result);
      })
      .catch(() => {
        if (!cancelled)
          setPreview({
            valid: false,
            reason: 'not_found',
            org_name: null,
            role: null,
            email: null,
            account_exists: false,
          });
      })
      .finally(() => {
        if (!cancelled) setLoadingPreview(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function acceptAndEnter() {
    setSubmitting(true);
    try {
      const result = await api.acceptInvitation(token);
      setActiveOrgId(result.org_id);
      toast({ tone: 'success', title: 'Joined', body: result.org_name });
      // Read by `WelcomeModal` the moment `/app` mounts, then cleared - a
      // plain write is enough here (no need for useStoredJson's notify
      // machinery) since `/app` mounts fresh after this redirect and reads
      // localStorage directly on its first render regardless.
      try {
        localStorage.setItem(
          PENDING_WELCOME_KEY,
          JSON.stringify({ role: result.role, orgName: result.org_name }),
        );
      } catch {
        /* private mode or blocked storage - the welcome message just won't show */
      }
      router.replace('/app');
      router.refresh();
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "That didn't work.",
      );
      setSubmitting(false);
    }
  }

  async function handleSignOut() {
    setSigningOut(true);
    await signOut();
    // useSession's onAuthStateChange listener flips status to 'signed-out' on
    // its own, which re-renders this page into the real signup form below -
    // no manual redirect needed.
  }

  async function submitNewAccount(event: React.FormEvent) {
    event.preventDefault();
    const next: typeof errors = {};
    if (!name.trim())
      next.name = 'Add your name so teammates can see who you are.';
    if (!isPasswordValid(password)) {
      next.password = 'Meet all four requirements below before continuing.';
    }
    setErrors(next);
    if (Object.keys(next).length > 0 || !preview?.email) return;

    setSubmitting(true);
    setFormError(null);
    const result = await signUpWithPassword(preview.email, password, name);
    if (!result.ok) {
      setFormError(result.error ?? "That didn't work.");
      setSubmitting(false);
      return;
    }
    await acceptAndEnter();
  }

  /** Sign in and join, for an invitee who already has an account. Signing in
   *  first and accepting second is the whole point: the previous flow offered
   *  this person a signup form, which could only ever fail. */
  async function submitExistingAccount(event: React.FormEvent) {
    event.preventDefault();
    if (!preview?.email) return;
    if (!password) {
      setErrors({ password: 'Enter your password to continue.' });
      return;
    }
    setErrors({});
    setSubmitting(true);
    setFormError(null);
    const result = await signInWithPassword(preview.email, password);
    if (!result.ok) {
      setFormError(result.error ?? "That didn't work.");
      setSubmitting(false);
      return;
    }
    await acceptAndEnter();
  }

  if (loadingPreview || session.status === 'loading') {
    return (
      <AuthCard title="Accept your invitation">
        <Skeleton className="h-40 w-full" />
      </AuthCard>
    );
  }

  if (!preview?.valid) {
    return (
      <AuthCard
        title="Invitation"
        footer={
          <Link
            href="/"
            className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
          >
            Go home
          </Link>
        }
      >
        <p className="text-small text-text-dim">
          {(preview?.reason && REASON_COPY[preview.reason]) ??
            "This invitation isn't valid."}
        </p>
      </AuthCard>
    );
  }

  const alreadySignedIn = session.status === 'signed-in';
  const signedInEmail =
    session.status === 'signed-in' ? session.profile.email : null;
  const emailMismatch =
    alreadySignedIn &&
    !!preview.email &&
    signedInEmail?.trim().toLowerCase() !== preview.email.trim().toLowerCase();

  return (
    <AuthCard
      title="Accept your invitation"
      description={
        alreadySignedIn
          ? undefined
          : preview.account_exists
            ? 'Sign in to join the team.'
            : "Set a password and you'll join the team."
      }
      footer={
        alreadySignedIn ? undefined : (
          <>
            Not expecting this?{' '}
            <Link
              href="/"
              className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
            >
              Ignore it
            </Link>{' '}
            - nothing happens until you{' '}
            {preview.account_exists ? 'sign in' : 'set a password'}.
          </>
        )
      }
    >
      <div className="flex flex-col gap-4">
        <Panel sunken className="flex flex-col gap-2 p-3">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-small text-text-mute">Organisation</span>
            <span className="text-small font-medium text-text">
              {preview.org_name}
            </span>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-small text-text-mute">Role</span>
            <Tag>{preview.role}</Tag>
          </div>
        </Panel>

        {alreadySignedIn ? (
          emailMismatch ? (
            <>
              <p className="text-small text-text-dim">
                You&apos;re signed in as{' '}
                <span className="font-medium text-text">{signedInEmail}</span>
                , but this invitation was sent to{' '}
                <span className="font-medium text-text">{preview.email}</span>
                . Sign out to accept it as that address.
              </p>
              <Button
                variant="secondary"
                size="lg"
                className="w-full"
                loading={signingOut}
                onClick={handleSignOut}
              >
                Sign out
              </Button>
            </>
          ) : (
            <>
              {formError ? (
                <p className="text-small text-lamp-flare-text">{formError}</p>
              ) : null}
              <Button
                size="lg"
                className="w-full"
                loading={submitting}
                onClick={acceptAndEnter}
              >
                Join {preview.org_name}
              </Button>
            </>
          )
        ) : preview.account_exists ? (
          <form
            onSubmit={submitExistingAccount}
            noValidate
            className="flex flex-col gap-4"
          >
            <p className="text-small text-text-dim">
              You already have a CallFlow account for this address. Sign in and
              you&apos;ll join {preview.org_name} straight away.
            </p>

            <Field
              label="Email"
              help="This invitation was sent to this address - it can't be changed here."
            >
              <Input value={preview.email ?? ''} readOnly />
            </Field>

            <Field label="Password" error={errors.password ?? formError} required>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                autoFocus
                disabled={submitting}
              />
            </Field>

            <Button
              type="submit"
              size="lg"
              className="w-full"
              loading={submitting}
            >
              Sign in and join
            </Button>

            <Link
              href="/forgot-password"
              className="text-small text-text-dim underline decoration-rule-strong underline-offset-2 hover:text-text hover:decoration-current"
            >
              Forgot your password?
            </Link>
          </form>
        ) : (
          <form
            onSubmit={submitNewAccount}
            noValidate
            className="flex flex-col gap-4"
          >
            <Field
              label="Email"
              help="This invitation was sent to this address - it can't be changed here."
            >
              <Input value={preview.email ?? ''} readOnly />
            </Field>

            <Field label="Your name" error={errors.name} required>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                autoFocus
                disabled={submitting}
              />
            </Field>

            <Field
              label="Password"
              error={errors.password ?? formError}
              required
            >
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                disabled={submitting}
              />
            </Field>

            <PasswordStrength value={password} />

            <Button
              type="submit"
              size="lg"
              className="w-full"
              loading={submitting}
            >
              Join the team
            </Button>
          </form>
        )}
      </div>
    </AuthCard>
  );
}
