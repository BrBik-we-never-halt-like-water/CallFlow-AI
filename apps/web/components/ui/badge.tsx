import { cn } from "@/lib/cn";
import { Lamp } from "@/components/brand/lamp";
import type { LampState } from "@/lib/lamp";

/**
 * Status badge — a lamp plus its label, in one pill.
 *
 * Construction follows §4.2 exactly: the surface and rule are mixed from the
 * lamp colour, but the *text* uses the `-text` alias. On a light surface that
 * resolves to the darkened `-ink` variant, because the pure lamp colours do not
 * reach 4.5:1 against paper. The dot keeps the pure colour, so the badge and the
 * lamp it refers to are visibly the same thing.
 *
 * The label is never optional. Colour is not allowed to be the only carrier of
 * meaning — a colourblind operator has to be able to run this product.
 */
const LAMP_VAR: Record<LampState, string> = {
  off: "var(--lamp-off)",
  ice: "var(--lamp-ice)",
  brass: "var(--lamp-brass)",
  jade: "var(--lamp-jade)",
  flare: "var(--lamp-flare)",
};

const TEXT: Record<LampState, string> = {
  off: "text-lamp-off-text",
  ice: "text-lamp-ice-text",
  brass: "text-lamp-brass-text",
  jade: "text-lamp-jade-text",
  flare: "text-lamp-flare-text",
};

export function LampBadge({
  state,
  children,
  pulse = false,
  className,
}: {
  state: LampState;
  children: React.ReactNode;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-2.5 py-1 shadow-xs",
        "text-small leading-none font-medium whitespace-nowrap",
        TEXT[state],
        className,
      )}
      style={{
        background: `color-mix(in oklab, ${LAMP_VAR[state]} 12%, transparent)`,
        borderColor: `color-mix(in oklab, ${LAMP_VAR[state]} 30%, transparent)`,
      }}
    >
      <Lamp state={state} size="sm" pulse={pulse} />
      {children}
    </span>
  );
}

/**
 * Neutral tag. Used for structural labels — `TEMPLATE`, `SUPPRESSED`, field
 * names — where nothing about call state is being communicated and a lamp
 * colour would therefore be wrong.
 */
export function Tag({
  children,
  mono = true,
  className,
}: {
  children: React.ReactNode;
  mono?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-xs border border-rule bg-surface-sunken px-1.5 py-0.5 whitespace-nowrap text-text-dim",
        mono ? "font-mono text-label uppercase tracking-[0.14em]" : "text-small",
        className,
      )}
    >
      {children}
    </span>
  );
}
