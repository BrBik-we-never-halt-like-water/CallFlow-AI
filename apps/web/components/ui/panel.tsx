import { cn } from "@/lib/cn";
import { WaveLine } from "@/components/brand/wave-spine";

/**
 * A surface: hairline border plus a soft shadow.
 *
 * On a light page a border alone reads as flat and a shadow alone reads as floating, so
 * every raised surface gets both — the border gives it an edge, the shadow gives it
 * weight. `interactive` adds a hover lift, which is the only place anything in this
 * design moves on hover.
 */
export function Panel({
  as: Component = "div",
  sunken = false,
  interactive = false,
  /** Drop the shadow — for a panel nested inside another panel. */
  flat = false,
  className,
  children,
  ...props
}: {
  as?: React.ElementType;
  sunken?: boolean;
  interactive?: boolean;
  flat?: boolean;
  className?: string;
  children?: React.ReactNode;
} & React.HTMLAttributes<HTMLElement>) {
  return (
    <Component
      className={cn(
        "rounded-lg border border-rule",
        sunken ? "bg-surface-sunken" : "bg-surface-raised",
        !sunken && !flat && "shadow-sm",
        interactive &&
          "transition-[box-shadow,transform,border-color] duration-(--dur-base) ease-(--ease-out) hover:-translate-y-0.5 hover:border-rule-strong hover:shadow-md",
        className,
      )}
      {...props}
    >
      {children}
    </Component>
  );
}

/** Uppercase mono eyebrow. The one place uppercase is used by design. */
export function Eyebrow({
  children,
  className,
  as: Component = "p",
}: {
  children: React.ReactNode;
  className?: string;
  as?: React.ElementType;
}) {
  return (
    <Component className={cn("eyebrow text-text-mute", className)}>{children}</Component>
  );
}

/**
 * A section header: display headline, optional eyebrow, and a sub-line capped at a
 * readable measure.
 */
export function SectionHeading({
  eyebrow,
  title,
  sub,
  className,
  align = "left",
}: {
  eyebrow?: string;
  title: React.ReactNode;
  sub?: React.ReactNode;
  className?: string;
  align?: "left" | "center";
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3",
        align === "center" && "items-center text-center",
        className,
      )}
    >
      {eyebrow ? (
        <div
          className={cn(
            "flex items-center gap-3",
            align === "center" && "justify-center",
          )}
        >
          <Eyebrow>{eyebrow}</Eyebrow>
          {align === "left" ? <WaveLine className="w-12" /> : null}
        </div>
      ) : null}

      <h2 className="measure-display font-display text-h2 text-text">{title}</h2>

      {sub ? (
        <p
          className={cn(
            "measure text-body-l text-text-dim",
            align === "center" && "mx-auto",
          )}
        >
          {sub}
        </p>
      ) : null}
    </div>
  );
}
