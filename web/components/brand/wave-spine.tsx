import { cn } from "@/lib/cn";

/**
 * The finer voice-flow accent: a small flowing wave line that replaces the plain
 * rules beside section eyebrows. Static and quiet — the shape alone carries the
 * voice motif; the WaveCanvas dividers and hero carry the motion. Stretches to
 * its container.
 */
export function WaveLine({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 120 12"
      preserveAspectRatio="none"
      className={cn("h-2.5 text-rule-strong", className)}
    >
      <path
        d="M0 6 Q10 1 20 6 T40 6 T60 6 T80 6 T100 6 T120 6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
