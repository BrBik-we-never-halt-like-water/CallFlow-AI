import { cn } from "@/lib/cn";
import { Mark } from "./mark";

/**
 * The wordmark: `CallFlow` in the display face, then `AI` in mono at 0.55em with
 * wide tracking, baseline-aligned and dimmed.
 *
 * Set as live text rather than inline SVG paths. The design calls for Archivo
 * Expanded 600 and JetBrains Mono 500 — both already loaded — and real text
 * scales with the type system, stays selectable, gets read correctly by a screen
 * reader, and inherits `currentColor` for free. Outlining it to SVG would buy
 * nothing and lose all four.
 */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-baseline whitespace-nowrap", className)}>
      <span className="font-display text-[1.0625em] leading-none tracking-[-0.02em]">
        CallFlow
      </span>
      <span
        aria-hidden
        className="ml-[0.34em] font-mono text-[0.55em] font-medium leading-none tracking-[0.4em] text-text-dim"
      >
        AI
      </span>
      {/* The mono suffix is styled as a superscript-ish tag, so it is dropped
          from the accessible name and re-added here as plain text. */}
      <span className="sr-only"> AI</span>
    </span>
  );
}

/**
 * Mark + wordmark together. The standard lockup for the site header, the app
 * shell, the footer, and the auth card.
 */
export function BrandLockup({
  className,
  markClassName,
}: {
  className?: string;
  markClassName?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <Mark title={null} className={markClassName} />
      <Wordmark />
    </span>
  );
}
