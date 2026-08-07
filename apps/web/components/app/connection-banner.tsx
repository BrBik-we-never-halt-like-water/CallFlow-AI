"use client";

import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { ConnectionPhase } from "@/lib/hooks/use-connection";

/**
 * Connection state. Silent while connecting or once up — only surfaces when the
 * service genuinely doesn't respond, which on an always-on deployment means
 * something is actually wrong rather than still starting.
 */
export function ConnectionBanner({ phase }: { phase: ConnectionPhase }) {
  if (phase !== "down") return null;

  return (
    <Panel className="flex flex-wrap items-center justify-between gap-4 p-4">
      <div className="flex flex-col gap-1">
        <p className="text-small font-medium text-lamp-flare-text">
          The service didn&apos;t respond.
        </p>
        <p className="text-small text-text-dim">
          Nothing was dialled and no run was started. Reload to try again.
        </p>
      </div>
      <Button variant="secondary" size="sm" onClick={() => window.location.reload()}>
        Try again
      </Button>
    </Panel>
  );
}
