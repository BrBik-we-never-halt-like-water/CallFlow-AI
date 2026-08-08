"use client";

import * as RadixSelect from "@radix-ui/react-select";
import { CaretDownIcon, CheckIcon } from "@phosphor-icons/react/dist/ssr";
import { cn } from "@/lib/cn";
import { useField } from "./field";

export interface SelectOption {
  value: string;
  label: string;
  hint?: string;
  disabled?: boolean;
}

/**
 * Select built on Radix, which brings keyboard navigation and typeahead   both
 * of which matter here because the longest selects in this product (timezone,
 * calling region) are ones a keyboard user will want to type into.
 */
export function Select({
  value,
  onValueChange,
  options,
  placeholder = "Select…",
  disabled,
  id,
  ariaLabel,
  className,
  triggerClassName,
  mono = false,
}: {
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  id?: string;
  /** Only needed when the select has no visible <label> via Field. */
  ariaLabel?: string;
  className?: string;
  triggerClassName?: string;
  mono?: boolean;
}) {
  const field = useField();

  return (
    <RadixSelect.Root value={value} onValueChange={onValueChange} disabled={disabled ?? field?.disabled}>
      <RadixSelect.Trigger
        id={id ?? field?.inputId}
        aria-label={ariaLabel}
        aria-describedby={field?.describedBy}
        aria-invalid={field?.invalid || undefined}
        className={cn(
          "inline-flex h-10 w-full cursor-pointer items-center justify-between gap-2 rounded-sm border bg-surface-raised px-3",
          "text-body text-text transition-colors duration-(--dur-micro)",
          "data-[placeholder]:text-text-mute",
          "disabled:cursor-not-allowed disabled:opacity-45",
          field?.invalid
            ? "border-[var(--lamp-flare)]"
            : "border-rule hover:border-rule-strong",
          mono && "font-mono text-data",
          className,
          triggerClassName,
        )}
      >
        <RadixSelect.Value placeholder={placeholder} />
        <RadixSelect.Icon>
          <CaretDownIcon aria-hidden className="size-4 shrink-0 text-text-mute" />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>

      <RadixSelect.Portal>
        <RadixSelect.Content
          position="popper"
          sideOffset={4}
          className={cn(
            "z-50 max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md",
            "border border-rule-strong bg-surface-raised shadow-overlay",
          )}
        >
          <RadixSelect.Viewport className="p-1">
            {options.map((option) => (
              <RadixSelect.Item
                key={option.value}
                value={option.value}
                disabled={option.disabled}
                className={cn(
                  "relative flex cursor-pointer select-none items-start gap-2 rounded-sm py-1.5 pl-7 pr-3",
                  "text-small text-text outline-none",
                  "data-highlighted:bg-surface-hover",
                  "data-disabled:pointer-events-none data-disabled:opacity-45",
                )}
              >
                <RadixSelect.ItemIndicator className="absolute left-2 top-2">
                  <CheckIcon aria-hidden weight="bold" className="size-3.5" />
                </RadixSelect.ItemIndicator>
                <span className="flex flex-col">
                  <RadixSelect.ItemText>{option.label}</RadixSelect.ItemText>
                  {option.hint ? (
                    <span className="text-small text-text-mute">{option.hint}</span>
                  ) : null}
                </span>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
}
