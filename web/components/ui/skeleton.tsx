import { cn } from "@/lib/cn";

/**
 * Loading placeholder   a static block, with no shimmer.
 *
 * A shimmer is ambient looping animation, which this design does not use: it
 * draws the eye to the thing that has no information yet. A quiet block holds
 * the space and lets the content arrive.
 */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("rounded-sm bg-surface-sunken", className)} />;
}

/** A block of text-shaped skeletons, last line short like real text. */
export function SkeletonText({
  lines = 3,
  className,
}: {
  lines?: number;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton
          key={i}
          className={cn("h-3.5", i === lines - 1 ? "w-2/5" : "w-full")}
        />
      ))}
    </div>
  );
}
