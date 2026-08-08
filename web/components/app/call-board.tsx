"use client";

import { cn } from "@/lib/cn";
import { LAMP_LABELS, lampForOutcome, type LampSpec } from "@/lib/lamp";
import { usePrefersReducedMotion } from "@/lib/hooks/use-external-store";
import type { Outcome } from "@/lib/api";

/**
 * A run seen from above: one cell per contact, live ones talking, settled ones
 * quiet and lit.
 *
 * This replaces reading a strip of dots as the only sense of progress. A run is
 * sixty calls happening at once, and the shape of that — how many are mid-
 * conversation, how many have gone quiet, which ones turned red — is the single
 * most useful thing to see on this page.
 *
 * The bars are decorative and carry no data: they say "this call is still
 * happening", which the lamp already says semantically. They stop the moment a
 * call settles, so movement on the board always means a live call.
 */

function talkDelay(seed: string, i: number): string {
  // Deterministic so the board does not reshuffle on every render.
  const n = (seed.charCodeAt(i % Math.max(1, seed.length)) || 65) * (i + 3);
  return `${((n % 110) / 100).toFixed(2)}s`;
}

export function CallBoard({
  outcomes,
  total,
  className,
}: {
  outcomes: Outcome[];
  /** Contacts in the run — cells beyond `outcomes` render as not-yet-dialled. */
  total: number;
  className?: string;
}) {
  const reduced = usePrefersReducedMotion();

  const cells: (LampSpec | null)[] = Array.from({ length: Math.max(total, outcomes.length) }, (_, i) => {
    const o = outcomes[i];
    return o ? lampForOutcome(o) : null;
  });

  const live = outcomes.filter((o) => o.disposition === "in_flight").length;

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div
        className="grid gap-1.5"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(34px, 1fr))" }}
        role="img"
        aria-label={
          `${outcomes.length} of ${total} dialled` +
          (live ? `, ${live} in conversation` : "")
        }
      >
        {cells.map((lamp, i) => {
          const state = lamp?.state ?? "off";
          const talking = state === "brass" || state === "ice";
          return (
            <div
              key={i}
              title={lamp ? LAMP_LABELS[state] : "Not yet dialled"}
              className={cn(
                "relative flex h-9 items-end gap-px overflow-hidden rounded-sm border p-1",
                state === "off" && "border-rule bg-surface-sunken",
                state === "ice" && "border-lamp-ice/40 bg-surface-raised",
                state === "brass" && "border-lamp-brass/45 bg-surface-raised",
                state === "jade" && "border-lamp-jade/40 bg-surface-raised",
                state === "flare" && "border-lamp-flare/50 bg-surface-raised",
              )}
            >
              {[0, 1, 2].map((b) => (
                <i
                  key={b}
                  className={cn(
                    "flex-1 origin-bottom rounded-[1px]",
                    talking ? "bg-rule-strong" : "bg-rule",
                    talking && !reduced && "animate-[talk_1.15s_ease-in-out_infinite]",
                  )}
                  style={{
                    height: talking ? "70%" : "26%",
                    animationDelay: talking ? talkDelay(String(i), b) : undefined,
                  }}
                />
              ))}
              <span
                className={cn(
                  "absolute right-1 top-1 size-1.5 rounded-full",
                  state === "off" && "bg-lamp-off",
                  state === "ice" && "bg-lamp-ice",
                  state === "brass" && "bg-lamp-brass",
                  state === "jade" && "bg-lamp-jade",
                  state === "flare" && "bg-lamp-flare",
                )}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
