"use client";

import { LampStrip } from "@/components/brand/lamp-strip";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import type { ConnectionPhase } from "@/lib/hooks/use-connection";
import type { LampSpec } from "@/lib/lamp";

/**
 * Connection state, shown as lamps rather than a spinner.
 *
 * A spinner says "wait" and nothing else. A sequence of lamps lighting says something
 * is progressing, which is what is actually true while a sleeping service starts —
 * and the count of seconds turns a wait into visible progress.
 *
 * The copy never says "backend". The user does not have one.
 */
export function ConnectionBanner({
  phase,
  wakeSeconds,
}: {
  phase: ConnectionPhase;
  wakeSeconds: number;
}) {
  if (phase === "up") return null;

  if (phase === "down") {
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

  // A slow left-to-right sequence while connecting or waking.
  const step = Math.floor(wakeSeconds * 1.5) % 9;
  const lamps: LampSpec[] = Array.from({ length: 8 }, (_, i) => ({
    state: i < step ? ("brass" as const) : ("off" as const),
    label: i < step ? "Starting" : "Waiting",
  }));

  return (
    <Panel className="flex flex-wrap items-center justify-between gap-4 p-4">
      <div className="flex flex-col gap-2">
        <LampStrip lamps={lamps} size="sm" />
        <p className="font-mono text-data text-text-dim">
          Waking the service…{wakeSeconds > 3 ? ` ${wakeSeconds}s` : ""}
        </p>
      </div>
      <p className="max-w-sm text-small text-text-mute">
        The service sleeps when it isn&apos;t in use, so the first request of the day
        takes a moment. Nothing is lost while it starts.
      </p>
    </Panel>
  );
}
