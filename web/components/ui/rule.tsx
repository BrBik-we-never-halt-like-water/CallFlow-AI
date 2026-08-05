import { cn } from "@/lib/cn";
import { Lamp } from "@/components/brand/lamp";

/**
 * A hairline rule. Default elevation in this design is a 1px border, so this is
 * the workhorse separator — there are no card shadows to do the job instead.
 *
 * `withLamps` sets three lamps into the line. Used between home-page sections,
 * where a divider carrying the product's one idea is doing more work than a
 * plain line would. It is not used on pages with no call state: if there is no
 * call, there is no lamp.
 */
export function Rule({
  withLamps = false,
  className,
}: {
  withLamps?: boolean;
  className?: string;
}) {
  if (!withLamps) {
    return <hr className={cn("border-0 border-t border-rule", className)} />;
  }

  return (
    <div className={cn("flex items-center gap-3", className)} role="separator">
      <span className="h-px flex-1 bg-rule" />
      <span aria-hidden className="flex items-center gap-2.5">
        <Lamp state="jade" size="sm" />
        <Lamp state="brass" size="sm" />
        <Lamp state="flare" size="sm" />
      </span>
      <span className="h-px flex-1 bg-rule" />
    </div>
  );
}

/** Vertical hairline, for toolbars and inline groups. */
export function VRule({ className }: { className?: string }) {
  return <span aria-hidden className={cn("h-5 w-px shrink-0 bg-rule", className)} />;
}
