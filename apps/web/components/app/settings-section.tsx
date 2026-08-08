import { Panel } from "@/components/ui/panel";

/**
 * A settings group: heading, one line of explanation, then the controls.
 *
 * `effect` is the important prop. Every safety control in this product shows its current
 * effect in plain language underneath it — "Only 1 number can be dialled" rather than
 * just an allowlist field — because a guard whose consequence you have to infer is a
 * guard people set wrong.
 */
export function SettingsSection({
  title,
  description,
  children,
  effect,
  footer,
}: {
  title: string;
  description?: string;
  children?: React.ReactNode;
  effect?: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <Panel className="flex flex-col gap-4 p-4 sm:p-5">
      <div className="flex flex-col gap-1">
        <h2 className="text-h3 font-medium text-text">{title}</h2>
        {description ? (
          <p className="measure text-small text-text-dim">{description}</p>
        ) : null}
      </div>

      {children}

      {effect ? (
        <div className="flex flex-col gap-1 border-t border-rule pt-3">
          <p className="text-small font-bold text-text-mute">What this means right now</p>
          <p className="text-small text-text-dim">{effect}</p>
        </div>
      ) : null}

      {footer ? <div className="border-t border-rule pt-3">{footer}</div> : null}
    </Panel>
  );
}

/**
 * Marks a pane whose values are read-only because the service owns them, or whose
 * changes are held locally. Being explicit beats a control that silently does nothing.
 */
export function NotWiredNotice({ children }: { children: React.ReactNode }) {
  return (
    <Panel sunken className="flex flex-col gap-1.5 p-3">
      <p className="text-small font-bold text-text-mute">On this deployment</p>
      <p className="measure text-small text-text-dim">{children}</p>
    </Panel>
  );
}
