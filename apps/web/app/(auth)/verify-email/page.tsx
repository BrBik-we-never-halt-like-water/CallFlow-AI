'use client';

import Link from 'next/link';
import { useState } from 'react';
import { AuthCard } from '@/components/layout/auth-card';
import { AuthNotice } from '@/components/layout/auth-notice';
import { Button } from '@/components/ui/button';

export default function VerifyEmailPage() {
  const [resent, setResent] = useState(false);

  return (
    <AuthCard
      title="Confirm your email"
      description="We've sent a link to the address you signed up with. Open it and you're in."
      footer={
        <>
          Wrong address?{' '}
          <Link
            href="/signup"
            className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
          >
            Start again
          </Link>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-small text-text-dim">
          The link expires in 24 hours. If it isn&apos;t there, check spam - and
          if it still isn&apos;t, send it again below.
        </p>

        {resent ? (
          <AuthNotice heading="Email sending isn't connected yet">
            There is no mail service on this deployment, so nothing was sent.
            The dashboard is open without verification in the meantime.
          </AuthNotice>
        ) : (
          <Button size="lg" className="w-full" onClick={() => setResent(true)}>
            Send it again
          </Button>
        )}
      </div>
    </AuthCard>
  );
}
