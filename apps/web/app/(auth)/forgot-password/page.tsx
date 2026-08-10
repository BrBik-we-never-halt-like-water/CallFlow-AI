'use client';

import Link from 'next/link';
import { useState } from 'react';
import { AuthCard } from '@/components/layout/auth-card';
import { Button } from '@/components/ui/button';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { useToast } from '@/components/ui/toast';
import { requestPasswordReset } from '@/lib/auth/actions';

export default function ForgotPasswordPage() {
  const toast = useToast();
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError('Enter the email address on your account.');
      return;
    }

    setSubmitting(true);
    setError(null);

    const result = await requestPasswordReset(email);

    // Rate limiting is worth surfacing - the user can act on it by waiting. Anything
    // else is swallowed: reporting "no such account" here would turn this form into a
    // way to discover which addresses are registered.
    if (!result.ok && result.error?.includes('emails have been sent')) {
      setError(result.error);
      setSubmitting(false);
      return;
    }

    setSubmitting(false);
    setSent(true);
    toast({
      tone: 'success',
      title: 'Reset link sent',
      body: "Check spam if it doesn't arrive in a minute or two.",
    });
  }

  return (
    <AuthCard
      title="Reset your password"
      description="We'll email you a link. It expires in one hour."
      footer={
        <Link
          href="/login"
          className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
        >
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Field label="Email" error={error} required>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            autoFocus
            disabled={submitting || sent}
          />
        </Field>

        <Button
          type="submit"
          size="lg"
          className="w-full"
          loading={submitting}
          disabled={sent}
        >
          {sent ? 'Link sent' : 'Send reset link'}
        </Button>
      </form>
    </AuthCard>
  );
}
