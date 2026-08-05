"use client";

import { CheckIcon } from "@phosphor-icons/react/dist/ssr";
import { cn } from "@/lib/cn";
import { Lamp } from "@/components/brand/lamp";
import type { LampState } from "@/lib/lamp";

export interface PasswordRule {
  label: string;
  test: (value: string) => boolean;
}

/**
 * Requirements are listed upfront and tick off as they are satisfied — never revealed
 * only on failure. Someone should be able to write a valid password on the first
 * attempt, which means telling them the rules before they type, not after.
 */
export const PASSWORD_RULES: PasswordRule[] = [
  { label: "At least 12 characters", test: (v) => v.length >= 12 },
  { label: "One capital letter", test: (v) => /[A-Z]/.test(v) },
  { label: "One number", test: (v) => /\d/.test(v) },
  { label: "One symbol", test: (v) => /[^A-Za-z0-9]/.test(v) },
];

export function passwordScore(value: string): number {
  return PASSWORD_RULES.filter((rule) => rule.test(value)).length;
}

export function isPasswordValid(value: string): boolean {
  return passwordScore(value) === PASSWORD_RULES.length;
}

/** Four segments, four rules. The strip is the meter. */
const SEGMENT_STATE: LampState[] = ["flare", "brass", "brass", "jade"];

export function PasswordStrength({
  value,
  className,
}: {
  value: string;
  className?: string;
}) {
  const score = passwordScore(value);
  const label =
    score === 0
      ? "No requirements met yet"
      : score === PASSWORD_RULES.length
        ? "Strong"
        : `${score} of ${PASSWORD_RULES.length} requirements met`;

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center gap-2">
        <div
          role="img"
          aria-label={`Password strength: ${label}`}
          className="flex items-center gap-1"
        >
          {PASSWORD_RULES.map((_, i) => (
            <Lamp
              key={i}
              // Every lit segment takes the colour of the level reached, so the strip
              // reads as one meter rather than four independent lamps.
              state={i < score ? SEGMENT_STATE[score - 1] : "off"}
              size="sm"
            />
          ))}
        </div>
        <span className="font-mono text-data text-text-mute">{label}</span>
      </div>

      <ul className="flex flex-col gap-1">
        {PASSWORD_RULES.map((rule) => {
          const met = value.length > 0 && rule.test(value);
          return (
            <li
              key={rule.label}
              className={cn(
                "flex items-center gap-1.5 text-small",
                met ? "text-lamp-jade-text" : "text-text-mute",
              )}
            >
              {met ? (
                <CheckIcon aria-hidden weight="bold" className="size-3" />
              ) : (
                <span aria-hidden className="size-3 text-center leading-none">
                  ·
                </span>
              )}
              {rule.label}
              <span className="sr-only">{met ? " — met" : " — not yet met"}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
