"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { Eyebrow } from "@/components/ui/panel";

/**
 * Shown when a specific step of an auth flow isn't wired up yet (e.g. resending a
 * verification email — accounts and sign-in themselves are real, Supabase-backed).
 *
 * Saying so plainly and opening the dashboard is the honest behaviour: a fake
 * "check your inbox" screen leaves someone waiting for an email that will never
 * arrive, and they will blame the product rather than the gap.
 */
export function AuthNotice({
  heading = "That part isn't connected yet",
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
        {children ?? "This step isn't wired up on this deployment yet. The dashboard is open in the meantime."}
      </p>
      <Button asChild size="sm" className="w-fit">
        <Link href="/app">Open dashboard</Link>
      </Button>
    </Panel>
  );
}
