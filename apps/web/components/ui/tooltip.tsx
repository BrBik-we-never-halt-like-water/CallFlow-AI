'use client';

import * as RadixTooltip from '@radix-ui/react-tooltip';
import { cn } from '@/lib/cn';

/**
 * Tooltip. 400ms open delay, keyboard-reachable via the trigger's focus.
 *
 * A tooltip may explain, but it may never be the only place information lives -
 * anything required to complete a task belongs in the layout. The one thing it
 * is genuinely responsible for: every disabled control in this product carries a
 * tooltip saying *why* it is disabled.
 */
export function TooltipProvider({ children }: { children: React.ReactNode }) {
  return (
    <RadixTooltip.Provider delayDuration={400} skipDelayDuration={200}>
      {children}
    </RadixTooltip.Provider>
  );
}

export function Tooltip({
  content,
  children,
  side = 'top',
  /** Wrap the trigger in a span. Needed when the trigger is disabled, since a
      disabled button emits no pointer events of its own. */
  wrapTrigger = false,
  className,
}: {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: 'top' | 'right' | 'bottom' | 'left';
  wrapTrigger?: boolean;
  className?: string;
}) {
  return (
    <RadixTooltip.Root>
      <RadixTooltip.Trigger asChild>
        {wrapTrigger ? (
          <span tabIndex={0} className="inline-flex">
            {children}
          </span>
        ) : (
          children
        )}
      </RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          side={side}
          sideOffset={6}
          collisionPadding={12}
          className={cn(
            'z-50 max-w-64 rounded-sm border border-rule-strong bg-surface-raised px-2.5 py-1.5',
            'text-small text-text shadow-overlay',
            'data-[state=delayed-open]:animate-in',
            className,
          )}
        >
          {content}
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
}
