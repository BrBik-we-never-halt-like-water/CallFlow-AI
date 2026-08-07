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
