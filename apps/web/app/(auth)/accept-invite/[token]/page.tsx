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
import { api, type InvitationPreview } from '@/lib/api';
import { signUpWithPassword } from '@/lib/auth/actions';
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
      router.replace('/app');
      router.refresh();
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : "That didn't work.",
      );
      setSubmitting(false);
    }
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

  return (
    <AuthCard
      title="Accept your invitation"
      description={
        alreadySignedIn ? undefined : "Set a password and you'll join the team."
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
            - nothing happens until you set a password.
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
        ) : (
          <form
            onSubmit={submitNewAccount}
            noValidate
            className="flex flex-col gap-4"
          >
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
