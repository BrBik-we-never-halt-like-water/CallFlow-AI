'use client';

import { Button } from '@/components/ui/button';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import type { SessionProfile, SessionState } from '@/lib/hooks/use-session';

/**
 * Renders `children` once the session resolves to signed-in; a skeleton while
 * loading, an error panel with retry otherwise.
 *
 * Every page that needs the signed-in profile was collapsing "loading", "error",
 * and "signed-out" into a silent blank render (`if (!profile) return null`) - this
 * is the one place that distinction is handled, instead of three copies of it.
 */
export function SessionGate({
  session,
  skeletonClassName = 'h-40 w-full max-w-2xl',
  children,
}: {
  session: SessionState & { refresh: () => void };
  skeletonClassName?: string;
  children: (profile: SessionProfile) => React.ReactNode;
}) {
  if (session.status === 'loading') {
    return <Skeleton className={skeletonClassName} />;
  }

  if (session.status !== 'signed-in') {
    return (
      <Panel className="flex flex-col gap-3 p-5">
        <p className="text-small text-text-dim">
          {session.status === 'error'
            ? session.message
            : 'Sign in again to continue.'}
        </p>
        <Button
          size="sm"
          variant="secondary"
          onClick={session.refresh}
          className="w-fit"
        >
          Try again
        </Button>
      </Panel>
    );
  }

  return <>{children(session.profile)}</>;
}
