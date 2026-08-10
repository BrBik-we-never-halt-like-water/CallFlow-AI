import type { Metadata } from 'next';
import { Ubuntu } from 'next/font/google';
import { AppShell } from '@/components/layout/app-shell';
import { OnboardingGate } from '@/components/app/onboarding-gate';
import { AppStoreProvider } from '@/lib/app-store';

/**
 * The dashboard's body face - Ubuntu, scoped to `/app/*` only via
 * `.app-font-scope` (globals.css) on the wrapper below. Marketing and auth
 * stay Inter Tight, set in the true root layout (`app/layout.tsx`), which
 * this layout does not render (`<html>`/`<body>` live there, not here).
 * Weights: 400/500 cover every `font-medium` under `/app/*` today; 700 is
 * loaded as the round's stated minimum for headings that reach for it later.
 */
const ubuntu = Ubuntu({
  variable: '--font-ubuntu',
  subsets: ['latin'],
  weight: ['400', '500', '700'],
  display: 'swap',
  preload: false,
});

export const metadata: Metadata = {
  title: {
    default: 'Dashboard',
    template: '%s · CallFlow AI',
  },
  // The dashboard is behind a login in a finished deployment and should never be
  // indexed regardless.
  robots: { index: false, follow: false },
};

export default function AppLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className={`${ubuntu.variable} app-font-scope`}>
      <AppStoreProvider>
        <OnboardingGate>
          <AppShell>{children}</AppShell>
        </OnboardingGate>
      </AppStoreProvider>
    </div>
  );
}
