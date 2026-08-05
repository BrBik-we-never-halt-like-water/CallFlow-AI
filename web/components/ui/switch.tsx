"use client";

import * as RadixSwitch from "@radix-ui/react-switch";
import { cn } from "@/lib/cn";
import type { LampState } from "@/lib/lamp";

const TRACK_VAR: Record<LampState, string> = {
  off: "var(--lamp-off)",
  ice: "var(--lamp-ice)",
  brass: "var(--lamp-brass)",
  jade: "var(--lamp-jade)",
  flare: "var(--lamp-flare)",
};

export interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  subLabel?: string;
  disabled?: boolean;
  /**
   * Track colour when on. Defaults to the monochrome inverse surface. A lamp
   * colour is only correct where the switch itself sets call state — which in
   * practice means the dry-run switch and nothing else.
   */
  tone?: LampState;
  id?: string;
  className?: string;
}

/**
 * Switch with its label and sub-label as part of the component.
 *
 * The sub-label is not optional decoration: a switch that says "Dry run" tells
 * you what it is called, and one that also says "Nothing will be dialled" tells
 * you what it does. In a product that places real phone calls, the second line
 * is the one that matters.
 */
export function Switch({
  checked,
  onCheckedChange,
  label,
  subLabel,
  disabled = false,
  tone,
  id,
  className,
}: SwitchProps) {
  const generatedId = id ?? `switch-${label.replace(/\s+/g, "-").toLowerCase()}`;
  const subId = subLabel ? `${generatedId}-sub` : undefined;

  return (
    <div className={cn("flex items-start gap-3", className)}>
      <RadixSwitch.Root
        id={generatedId}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        aria-describedby={subId}
        // 40px wide / 24px tall track with a 20px thumb: reads as a physical
        // toggle rather than a chip, and the whole row is the hit target.
        className={cn(
          "relative mt-0.5 h-6 w-10 shrink-0 cursor-pointer rounded-full border transition-colors duration-(--dur-base) ease-(--ease-out)",
          "border-rule-strong bg-surface-sunken",
          "disabled:cursor-not-allowed disabled:opacity-45",
          checked && "border-transparent",
        )}
        style={
          checked
            ? { background: tone ? TRACK_VAR[tone] : "var(--surface-inverse)" }
            : undefined
        }
      >
        <RadixSwitch.Thumb
          className={cn(
            "block size-5 rounded-full bg-surface-raised",
            "translate-x-0.5 transition-transform duration-(--dur-base) ease-(--ease-out)",
            "data-[state=checked]:translate-x-[18px]",
          )}
        />
      </RadixSwitch.Root>

      <div className="flex min-w-0 flex-col">
        <label
          htmlFor={generatedId}
          className={cn(
            "cursor-pointer text-small font-medium text-text",
            disabled && "cursor-not-allowed opacity-45",
          )}
        >
          {label}
        </label>
        {subLabel ? (
          <span id={subId} className="text-small text-text-mute">
            {subLabel}
          </span>
        ) : null}
      </div>
    </div>
  );
}
