import type { Icon } from "@phosphor-icons/react";

import { cn } from "@/lib/cn";

/**
 * Empty states are invitations to act, not decoration.
 *
 * One line saying what is not here, one line saying what the thing is for, and
 * exactly one action. The explanation matters more than it looks: an operator
 * seeing "No campaigns yet" for the first time does not yet know what a campaign
 * is, and this is the only place the product gets to tell them.
 */
export function EmptyState({
  icon: IconComponent,
  title,
  body,
  action,
  className,
}: {
  icon?: Icon;
  title: string;
  body: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-6 py-16 text-center",
        className,
      )}
    >
      {IconComponent ? (
        <IconComponent
          aria-hidden
          weight="light"
          className="size-7 text-text-mute"
        />
      ) : null}
      <h3 className="text-h4 font-medium text-text">{title}</h3>
      <p className="measure text-small text-text-dim">{body}</p>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
