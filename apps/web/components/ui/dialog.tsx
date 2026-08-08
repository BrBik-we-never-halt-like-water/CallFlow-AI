"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { XIcon } from "@phosphor-icons/react/dist/ssr";
import { cn } from "@/lib/cn";

/**
 * Dialog and Sheet, both on Radix Dialog — so both get a focus trap, `Esc` to
 * close, and focus returned to the trigger on close without us reimplementing
 * any of it.
 *
 * Overlays are the one place a real shadow is allowed, because they genuinely
 * float above everything else.
 */

export const DialogRoot = RadixDialog.Root;
export const DialogTrigger = RadixDialog.Trigger;
export const DialogClose = RadixDialog.Close;

function Overlay() {
  return (
    <RadixDialog.Overlay className="fixed inset-0 z-50 bg-[color-mix(in_oklab,var(--text)_45%,transparent)] backdrop-blur-[3px]" />
  );
}

export function Dialog({
  title,
  description,
  children,
  footer,
  className,
  size = "md",
  dismissible = true,
}: {
  title: string;
  /** Read out with the title. Omit only if the body is self-explanatory. */
  description?: string;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  size?: "sm" | "md" | "lg";
  /** False for a mandatory step: no close button, no Esc, no click-outside. */
  dismissible?: boolean;
}) {
  const width = { sm: "max-w-sm", md: "max-w-lg", lg: "max-w-2xl" }[size];

  return (
    <RadixDialog.Portal>
      <Overlay />
      <RadixDialog.Content
        onEscapeKeyDown={(e) => !dismissible && e.preventDefault()}
        onPointerDownOutside={(e) => !dismissible && e.preventDefault()}
        onInteractOutside={(e) => !dismissible && e.preventDefault()}
        className={cn(
          "fixed left-1/2 top-1/2 z-50 w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2",
          "max-h-[calc(100dvh-64px)] overflow-y-auto rounded-md border border-rule-strong bg-surface-raised shadow-overlay",
          width,
          className,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-rule p-5">
          <div className="flex flex-col gap-1.5">
            <RadixDialog.Title className="font-display text-h3 text-text">
              {title}
            </RadixDialog.Title>
            {description ? (
              <RadixDialog.Description className="measure text-small text-text-dim">
                {description}
              </RadixDialog.Description>
            ) : null}
          </div>
          {dismissible ? (
            <RadixDialog.Close
              aria-label="Close"
              className="-m-1.5 flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-sm text-text-mute transition-colors hover:bg-surface-hover hover:text-text"
            >
              <XIcon aria-hidden className="size-4" />
            </RadixDialog.Close>
          ) : null}
        </div>

        {children ? <div className="p-5">{children}</div> : null}

        {footer ? (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-rule p-5">
            {footer}
          </div>
        ) : null}
      </RadixDialog.Content>
    </RadixDialog.Portal>
  );
}

/**
 * Right-hand sheet on desktop, full-screen on mobile.
 *
 * Used for a call's transcript, where the operator wants the detail without
 * losing their place in the results table behind it.
 */
export function Sheet({
  title,
  description,
  children,
  footer,
  className,
}: {
  title: string;
  description?: string;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}) {
  return (
    <RadixDialog.Portal>
      <Overlay />
      <RadixDialog.Content
        className={cn(
          "fixed inset-0 z-50 flex flex-col bg-surface-raised shadow-overlay",
          "md:inset-y-0 md:left-auto md:right-0 md:w-[min(720px,92vw)] md:border-l md:border-rule-strong",
          className,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-rule p-4 md:p-5">
          <div className="flex min-w-0 flex-col gap-1">
            <RadixDialog.Title className="font-display text-h3 text-text">
              {title}
            </RadixDialog.Title>
            {description ? (
              <RadixDialog.Description className="font-mono text-data text-text-mute">
                {description}
              </RadixDialog.Description>
            ) : null}
          </div>
          <RadixDialog.Close
            aria-label="Close"
            className="-m-1.5 flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-sm text-text-mute transition-colors hover:bg-surface-hover hover:text-text"
          >
            <XIcon aria-hidden className="size-4" />
          </RadixDialog.Close>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>

        {footer ? (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-rule p-4 md:p-5">
            {footer}
          </div>
        ) : null}
      </RadixDialog.Content>
    </RadixDialog.Portal>
  );
}
