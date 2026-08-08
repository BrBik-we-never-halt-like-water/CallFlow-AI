"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";
import { Dialog, DialogRoot } from "@/components/ui/dialog";
import { Eyebrow } from "@/components/ui/panel";
import { Switch } from "@/components/ui/switch";

export interface DryRunConfirmDetails {
  contacts: number;
  estimatedCredits: number;
  windowStart: string;
  windowEnd: string;
  timezone: string;
  allowlistOn: boolean;
}

/**
 * The dry-run switch.
 *
 * This gets its own component because it is the safety story made visible, and the
 * safety story is also a sales asset. Three things make it different from every other
 * switch in the product:
 *
 *  1. It defaults to on, and the sub-label says what that means   "Nothing will be
 *     dialled"   rather than just naming the setting.
 *  2. It is the only switch that confirms. Turning it off spends money and rings real
 *     people, and the confirmation shows the numbers that decision depends on.
 *  3. Its state is announced politely to assistive tech, because the difference between
 *     dry and live is the single most consequential piece of state on the screen.
 */
export function DryRunSwitch({
  dryRun,
  onChange,
  details,
  disabled = false,
}: {
  dryRun: boolean;
  onChange: (dryRun: boolean) => void;
  details: DryRunConfirmDetails;
  disabled?: boolean;
}) {
  const [confirming, setConfirming] = useState(false);

  function requestChange(next: boolean) {
    // Going back to dry run is always safe and never asks.
    if (next) {
      onChange(true);
      return;
    }
    setConfirming(true);
  }

  return (
    <>
      <div className="flex flex-col gap-3">
        <Switch
          checked={dryRun}
          onCheckedChange={requestChange}
          label="Dry run"
          subLabel={dryRun ? "Nothing will be dialled" : "Real calls will be placed"}
          tone={dryRun ? "ice" : "brass"}
          disabled={disabled}
        />

        {/* Announced on change, not on every render. */}
        <p aria-live="polite" className="sr-only">
          {dryRun
            ? "Dry run is on. Nothing will be dialled."
            : "Live mode is on. Real calls will be placed."}
        </p>
      </div>

      <DialogRoot open={confirming} onOpenChange={setConfirming}>
        <Dialog
          title="Switch to live calling?"
          description="Live mode places real phone calls to the numbers in this run and spends credits. Your allowlist, per-run ceiling, and calling window still apply."
          footer={
            <>
              <Button variant="secondary" onClick={() => setConfirming(false)}>
                Stay in dry run
              </Button>
              <Button
                onClick={() => {
                  setConfirming(false);
                  onChange(false);
                }}
              >
                Switch to live
              </Button>
            </>
          }
        >
          <dl className="flex flex-col gap-0 divide-y divide-rule">
            <ConfirmRow label="Contacts" value={`${details.contacts}`} />
            <ConfirmRow
              label="Credits estimated"
              value={`${details.estimatedCredits}`}
            />
            <ConfirmRow
              label="Calling window"
              value={`${details.windowStart}–${details.windowEnd} ${details.timezone}`}
            />
            <ConfirmRow
              label="Allowlist"
              value={details.allowlistOn ? "On" : "Off"}
              warn={!details.allowlistOn}
            />
          </dl>
        </Dialog>
      </DialogRoot>
    </>
  );
}

function ConfirmRow({
  label,
  value,
  warn = false,
}: {
  label: string;
  value: string;
  warn?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2.5">
      <dt className="text-small text-text-dim">{label}</dt>
      <dd
        className={cn(
          "font-mono text-data tabular-nums",
          warn ? "text-lamp-flare-text" : "text-text",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

/**
 * The persistent mode strip on the run panel.
 *
 * Not dismissible in live mode. Someone who has switched to live should not be able to
 * make that fact disappear from the screen they are about to press Start on.
 */
export function ModeStrip({ dryRun }: { dryRun: boolean }) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-sm border px-3 py-2",
        dryRun
          ? "border-[color-mix(in_oklab,var(--lamp-ice)_30%,transparent)] bg-[color-mix(in_oklab,var(--lamp-ice)_10%,transparent)]"
          : "border-[color-mix(in_oklab,var(--lamp-brass)_35%,transparent)] bg-[color-mix(in_oklab,var(--lamp-brass)_12%,transparent)]",
      )}
    >
      <Eyebrow
        as="span"
        className={dryRun ? "text-lamp-ice-text" : "text-lamp-brass-text"}
      >
        {dryRun ? "Dry run · No credits spent" : "Live · Real calls will be placed"}
      </Eyebrow>
    </div>
  );
}

/** The left border colour the whole run panel carries, keyed to the mode. */
export function modePanelClass(dryRun: boolean): string {
  return dryRun
    ? "border-l-2 border-l-[var(--lamp-ice)]"
    : "border-l-2 border-l-[var(--lamp-brass)]";
}
