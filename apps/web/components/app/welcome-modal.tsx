'use client';

import { CheckCircleIcon } from '@phosphor-icons/react/dist/ssr';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { useStoredJson } from '@/lib/hooks/use-external-store';

export const PENDING_WELCOME_KEY = 'callflow.pending-welcome';

export interface PendingWelcome {
  role: string;
  orgName: string;
}

/**
 * A one-time "you're in" moment for someone who just accepted a teammate
 * invitation - written to storage by the accept-invite page right before it
 * redirects here (`app/(auth)/accept-invite/[token]/page.tsx`), consumed and
 * cleared the first time this mounts. Not the org-owner onboarding wizard
 * (`OnboardingGate`) - that forces org/profile setup on a brand-new
 * organisation; this is for someone joining an already-established one, who
 * has nothing to set up, just something worth being told plainly.
 */
export function WelcomeModal() {
  const [pending, setPending] = useStoredJson<PendingWelcome | null>(
    PENDING_WELCOME_KEY,
    null,
  );

  if (!pending) return null;

  function dismiss() {
    setPending(null);
  }

  return (
    <DialogRoot open onOpenChange={(open) => !open && dismiss()}>
      <Dialog
        title="Welcome to CallFlow AI"
        size="sm"
        footer={
          <Button className="w-full" onClick={dismiss}>
            Let&apos;s go
          </Button>
        }
      >
        <div className="flex flex-col items-center gap-3 py-2 text-center">
          <CheckCircleIcon
            aria-hidden
            weight="fill"
            className="size-10 text-lamp-jade-text"
          />
          <p className="measure text-body text-text-dim">
            You&apos;ve been invited to{' '}
            <span className="font-medium text-text">{pending.orgName}</span>{' '}
            as <span className="font-medium text-text">{pending.role}</span>.
            Do your best.
          </p>
        </div>
      </Dialog>
    </DialogRoot>
  );
}
