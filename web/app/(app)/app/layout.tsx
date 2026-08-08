import type { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import { OnboardingGate } from "@/components/app/onboarding-gate";
import { AppStoreProvider } from "@/lib/app-store";

export const metadata: Metadata = {
  title: {
    default: "Dashboard",
    template: "%s · CallFlow AI",
  },
  // The dashboard is behind a login in a finished deployment and should never be
  // indexed regardless.
  robots: { index: false, follow: false },
};

export default function AppLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <AppStoreProvider>
      <OnboardingGate>
        <AppShell>{children}</AppShell>
      </OnboardingGate>
    </AppStoreProvider>
  );
}
