"use client";

import * as RadixAccordion from "@radix-ui/react-accordion";
import * as RadixTabs from "@radix-ui/react-tabs";
import * as RadixPopover from "@radix-ui/react-popover";
import { CaretDownIcon } from "@phosphor-icons/react/dist/ssr";
import { cn } from "@/lib/cn";

/**
 * Tabs, Accordion, and Popover. Grouped because they share one job   showing one
 * thing at a time   and one visual treatment: a hairline rule marks the active
 * edge, and nothing moves except the content.
 */

/* -------------------------------------------------------------------------- */
/* Tabs                                                                        */
/* -------------------------------------------------------------------------- */

export function Tabs({
  value,
  onValueChange,
  tabs,
  children,
  className,
  listClassName,
}: {
  value: string;
  onValueChange: (value: string) => void;
  tabs: { value: string; label: string; count?: number }[];
  children: React.ReactNode;
  className?: string;
  listClassName?: string;
}) {
  return (
    <RadixTabs.Root value={value} onValueChange={onValueChange} className={className}>
      <RadixTabs.List
        className={cn(
          "-mb-px flex gap-1 overflow-x-auto border-b border-rule",
          listClassName,
        )}
      >
        {tabs.map((tab) => (
          <RadixTabs.Trigger
            key={tab.value}
            value={tab.value}
            className={cn(
              "relative inline-flex cursor-pointer items-center gap-2 whitespace-nowrap px-3 py-2.5",
              "text-small font-medium text-text-dim transition-colors duration-(--dur-micro)",
              "hover:text-text",
              // The active tab is marked by a 2px rule, not a filled pill: the
              // rest of the design separates with hairlines, and a pill here
              // would be the only pill on the page.
              "data-[state=active]:text-text",
              "after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-transparent",
              "data-[state=active]:after:bg-surface-inverse",
            )}
          >
            {tab.label}
            {tab.count != null ? (
              <span className="font-mono text-data tabular-nums text-text-mute">
                {tab.count}
              </span>
            ) : null}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {children}
    </RadixTabs.Root>
  );
}

export const TabPanel = RadixTabs.Content;

/* -------------------------------------------------------------------------- */
/* Accordion                                                                   */
/* -------------------------------------------------------------------------- */

export function Accordion({
  items,
  /** `single` for an FAQ, `multiple` for a settings page. */
  type = "single",
  defaultValue,
  className,
}: {
  items: { value?: string; title: string; content: React.ReactNode }[];
  type?: "single" | "multiple";
  defaultValue?: string;
  className?: string;
}) {
  const resolved = items.map((item, i) => ({ ...item, value: item.value ?? `item-${i}` }));

  const shared = {
    className: cn("divide-y divide-rule border-y border-rule", className),
  };

  const body = resolved.map((item) => (
    <RadixAccordion.Item key={item.value} value={item.value}>
      <RadixAccordion.Header>
        <RadixAccordion.Trigger
          className={cn(
            "group flex w-full cursor-pointer items-center justify-between gap-4 py-4 text-left",
            "text-body font-medium text-text transition-colors duration-(--dur-micro) hover:text-text-dim",
          )}
        >
          {item.title}
          <CaretDownIcon
            aria-hidden
            className="size-4 shrink-0 text-text-mute transition-transform duration-(--dur-base) ease-(--ease-out) group-data-[state=open]:rotate-180"
          />
        </RadixAccordion.Trigger>
      </RadixAccordion.Header>
      <RadixAccordion.Content className="overflow-hidden">
        <div className="measure pb-4 text-small text-text-dim">{item.content}</div>
      </RadixAccordion.Content>
    </RadixAccordion.Item>
  ));

  return type === "single" ? (
    <RadixAccordion.Root type="single" collapsible defaultValue={defaultValue} {...shared}>
      {body}
    </RadixAccordion.Root>
  ) : (
    <RadixAccordion.Root
      type="multiple"
      defaultValue={defaultValue ? [defaultValue] : undefined}
      {...shared}
    >
      {body}
    </RadixAccordion.Root>
  );
}

/* -------------------------------------------------------------------------- */
/* Popover                                                                     */
/* -------------------------------------------------------------------------- */

export function Popover({
  trigger,
  children,
  side = "bottom",
  align = "start",
  className,
}: {
  trigger: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  align?: "start" | "center" | "end";
  className?: string;
}) {
  return (
    <RadixPopover.Root>
      <RadixPopover.Trigger asChild>{trigger}</RadixPopover.Trigger>
      <RadixPopover.Portal>
        <RadixPopover.Content
          side={side}
          align={align}
          sideOffset={6}
          collisionPadding={12}
          className={cn(
            "z-50 w-72 rounded-md border border-rule-strong bg-surface-raised p-3 shadow-overlay",
            "text-small text-text-dim",
            className,
          )}
        >
          {children}
        </RadixPopover.Content>
      </RadixPopover.Portal>
    </RadixPopover.Root>
  );
}
