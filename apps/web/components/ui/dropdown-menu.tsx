"use client";

import * as Radix from "@radix-ui/react-dropdown-menu";
import { CheckIcon } from "@phosphor-icons/react/dist/ssr";
import { cn } from "@/lib/cn";

/**
 * Dropdown menu. Used for row overflow actions, the table's column-visibility
 * control, and the user menu.
 *
 * A destructive item is the one place a lamp colour is allowed on a control,
 * for the same reason `Button`'s danger variant is: an operator must not be able
 * to misread `Delete`.
 */

export const DropdownMenu = Radix.Root;
export const DropdownMenuTrigger = Radix.Trigger;

export function DropdownMenuContent({
  children,
  align = "end",
  className,
}: {
  children: React.ReactNode;
  align?: "start" | "center" | "end";
  className?: string;
}) {
  return (
    <Radix.Portal>
      <Radix.Content
        align={align}
        sideOffset={4}
        collisionPadding={12}
        className={cn(
          "z-50 min-w-48 overflow-hidden rounded-md border border-rule-strong bg-surface-raised p-1 shadow-overlay",
          className,
        )}
      >
        {children}
      </Radix.Content>
    </Radix.Portal>
  );
}

const ITEM = [
  "flex w-full cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5",
  "text-small text-text outline-none",
  "data-highlighted:bg-surface-hover",
  "data-disabled:pointer-events-none data-disabled:opacity-45",
].join(" ");

export function DropdownMenuItem({
  children,
  onSelect,
  disabled,
  destructive = false,
  className,
}: {
  children: React.ReactNode;
  onSelect?: () => void;
  disabled?: boolean;
  destructive?: boolean;
  className?: string;
}) {
  return (
    <Radix.Item
      onSelect={onSelect}
      disabled={disabled}
      className={cn(ITEM, destructive && "text-lamp-flare-text", className)}
    >
      {children}
    </Radix.Item>
  );
}

export function DropdownMenuCheckboxItem({
  children,
  checked,
  onCheckedChange,
  className,
}: {
  children: React.ReactNode;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  className?: string;
}) {
  return (
    <Radix.CheckboxItem
      checked={checked}
      onCheckedChange={onCheckedChange}
      // Keeps the menu open so several columns can be toggled in one visit.
      onSelect={(event) => event.preventDefault()}
      className={cn(ITEM, "pl-7", className)}
    >
      <Radix.ItemIndicator className="absolute left-2">
        <CheckIcon aria-hidden weight="bold" className="size-3.5" />
      </Radix.ItemIndicator>
      {children}
    </Radix.CheckboxItem>
  );
}

export function DropdownMenuLabel({ children }: { children: React.ReactNode }) {
  return (
    <Radix.Label className="eyebrow px-2 py-1.5 text-text-mute">{children}</Radix.Label>
  );
}

export function DropdownMenuSeparator() {
  return <Radix.Separator className="my-1 h-px bg-rule" />;
}
