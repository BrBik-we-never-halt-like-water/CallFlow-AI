import { cn } from "@/lib/cn";

/**
 * The logo mark: three lamps in a row, set into a 1px-rule capsule.
 *
 * The capsule inherits `currentColor` so the mark works on any surface without
 * a variant. The lamps keep their own tokens   jade, brass, flare   because the
 * mark is a miniature of the product's one idea: three calls, three different
 * things that happened, visible at a glance.
 *
 * At favicon size the lamps merge into a readable tri-colour bar; `public/
 * favicon.svg` carries a version with the geometry thickened for 16px.
 */
export function Mark({
  className,
  title = "CallFlow AI",
}: {
  className?: string;
  /** Pass `null` for a decorative mark sitting next to the wordmark. */
  title?: string | null;
}) {
  return (
    <svg
      viewBox="0 0 44 20"
      fill="none"
      className={cn("h-5 w-auto", className)}
      {...(title
        ? { role: "img", "aria-label": title }
        : { "aria-hidden": true as const, focusable: false as const })}
    >
      <rect
        x="0.75"
        y="0.75"
        width="42.5"
        height="18.5"
        rx="9.25"
        stroke="currentColor"
        strokeWidth="1.5"
        opacity="0.55"
      />
      <circle cx="12" cy="10" r="3.5" fill="var(--lamp-jade)" />
      <circle cx="22" cy="10" r="3.5" fill="var(--lamp-brass)" />
      <circle cx="32" cy="10" r="3.5" fill="var(--lamp-flare)" />
    </svg>
  );
}
