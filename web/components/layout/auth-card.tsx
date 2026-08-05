import { Panel } from "@/components/ui/panel";
import { Rule } from "@/components/ui/rule";

/**
 * The auth card.
 *
 * A single `Rule withLamps` sits above the form. It is the one decorative use of the
 * lamp strip anywhere in the product, and it is justified because signing in is the
 * doorway to a surface where lamps carry meaning — it reads as the instrument
 * powering on rather than as ornament.
 */
export function AuthCard({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <Panel className="flex flex-col gap-6 p-6">
      <div className="flex flex-col gap-4">
        <Rule withLamps />
        <div className="flex flex-col gap-1.5">
          <h1 className="font-display text-h3 text-text">{title}</h1>
          {description ? (
            <p className="text-small text-text-dim">{description}</p>
          ) : null}
        </div>
      </div>

      {children}

      {footer ? (
        <div className="border-t border-rule pt-4 text-small text-text-dim">{footer}</div>
      ) : null}
    </Panel>
  );
}
