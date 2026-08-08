import { cn } from "@/lib/cn";

/**
 * A surface, at one of the three levels defined in globals.css.
 *
 * `quiet` (flat) is a hairline with no shadow, for rows and nested panels; `raised`
 * is the default; `feature` adds elevation and a primary edge for the one card in a
 * group that should draw the eye. Marketing and the dashboard both render through
 * this, which is what keeps them looking like one product.
 */
export function Panel({
  as: Component = "div",
  sunken = false,
  interactive = false,
  /** Drop the shadow — for a panel nested inside another panel. */
  flat = false,
  /** The one card in a group that should draw the eye. */
  feature = false,
  className,
  children,
  ...props
}: {
  as?: React.ElementType;
  sunken?: boolean;
  interactive?: boolean;
  flat?: boolean;
  feature?: boolean;
  className?: string;
  children?: React.ReactNode;
} & React.HTMLAttributes<HTMLElement>) {
  return (
    <Component
      className={cn(
        sunken ? "card-sunken" : feature ? "card-feature" : flat ? "card" : "card-raised",
        interactive && "card-interactive",
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
      {/* No trailing squiggle. A decorative mark beside every eyebrow on every
          section is a tic, not a system — it says nothing and it appears
          everywhere, which is the definition of noise. */}
      {eyebrow ? (
        <div className={cn("flex items-center", align === "center" && "justify-center")}>
          <Eyebrow>{eyebrow}</Eyebrow>
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
