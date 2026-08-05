"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { Eyebrow } from "@/components/ui/panel";

/**
 * Shown after a valid auth submission.
 *
 * Accounts are not enabled on this deployment — there is no auth service behind these
 * forms yet. Saying so and opening the dashboard is the honest behaviour: a fake
 * "check your inbox" screen leaves someone waiting for an email that will never
 * arrive, and they will blame the product rather than the gap.
 */
export function AuthNotice({
  heading = "Accounts aren't enabled yet",
  children,
}: {
  heading?: string;
  children?: React.ReactNode;
}) {
  return (
    <Panel sunken className="flex flex-col gap-3 p-4">
      <Eyebrow>Not connected</Eyebrow>
      <h2 className="text-h4 font-medium text-text">{heading}</h2>
      <p className="text-small text-text-dim">
        {children ??
          "This deployment has no account service behind it yet, so nothing was created and no email was sent. The dashboard is open in the meantime — you can run a campaign in dry mode without an account."}
      </p>
      <Button asChild size="sm" className="w-fit">
        <Link href="/app">Open dashboard</Link>
      </Button>
    </Panel>
  );
}

/** Google OAuth button. Same honest treatment — it explains rather than pretending. */
export function GoogleButton({ label }: { label: string }) {
  return (
    <Button variant="secondary" size="lg" disabled className="w-full" title="Not configured on this deployment yet">
      <GoogleGlyph />
      {label}
    </Button>
  );
}

function GoogleGlyph() {
  return (
    <svg aria-hidden viewBox="0 0 18 18" className="size-4">
      <path
        fill="currentColor"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
        opacity=".9"
      />
      <path
        fill="currentColor"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.34A9 9 0 0 0 9 18Z"
        opacity=".7"
      />
      <path
        fill="currentColor"
        d="M3.97 10.72a5.41 5.41 0 0 1 0-3.44V4.94H.96a9 9 0 0 0 0 8.12l3.01-2.34Z"
        opacity=".5"
      />
      <path
        fill="currentColor"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.59A9 9 0 0 0 .96 4.94l3.01 2.34C4.68 5.16 6.66 3.58 9 3.58Z"
        opacity=".8"
      />
    </svg>
  );
}
