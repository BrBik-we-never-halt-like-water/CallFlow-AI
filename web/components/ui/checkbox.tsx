"use client";

import * as RadixCheckbox from "@radix-ui/react-checkbox";
import * as RadixRadio from "@radix-ui/react-radio-group";
import { CheckIcon, MinusIcon } from "@phosphor-icons/react/dist/ssr";
import { cn } from "@/lib/cn";

export function Checkbox({
  checked,
  onCheckedChange,
  label,
  disabled,
  id,
  className,
}: {
  /** `"indeterminate"` drives the header checkbox of a partially-selected table. */
  checked: boolean | "indeterminate";
  onCheckedChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  id?: string;
  className?: string;
}) {
  const generatedId = id ?? `cb-${label.replace(/\s+/g, "-").toLowerCase()}`;

  return (
    <div className={cn("inline-flex items-center gap-2", className)}>
      <RadixCheckbox.Root
        id={generatedId}
        checked={checked}
        onCheckedChange={(next) => onCheckedChange(next === true)}
        disabled={disabled}
        className={cn(
          "flex size-4 shrink-0 cursor-pointer items-center justify-center rounded-xs border border-rule-strong bg-surface-raised",
          "transition-colors duration-(--dur-micro)",
          "data-[state=checked]:border-transparent data-[state=checked]:bg-surface-inverse",
          "data-[state=indeterminate]:border-transparent data-[state=indeterminate]:bg-surface-inverse",
          "disabled:cursor-not-allowed disabled:opacity-45",
        )}
      >
        <RadixCheckbox.Indicator className="text-text-inverse">
          {checked === "indeterminate" ? (
            <MinusIcon aria-hidden weight="bold" className="size-3" />
          ) : (
            <CheckIcon aria-hidden weight="bold" className="size-3" />
          )}
        </RadixCheckbox.Indicator>
      </RadixCheckbox.Root>

      <label
        htmlFor={generatedId}
        className={cn(
          "cursor-pointer text-small text-text select-none",
          disabled && "cursor-not-allowed opacity-45",
        )}
      >
        {label}
      </label>
    </div>
  );
}

export function RadioGroup({
  value,
  onValueChange,
  options,
  name,
  className,
}: {
  value: string;
  onValueChange: (value: string) => void;
  options: { value: string; label: string; hint?: string }[];
  name: string;
  className?: string;
}) {
  return (
    <RadixRadio.Root
      value={value}
      onValueChange={onValueChange}
      name={name}
      className={cn("flex flex-col gap-2.5", className)}
    >
      {options.map((option) => {
        const id = `${name}-${option.value}`;
        return (
          <div key={option.value} className="flex items-start gap-2">
            <RadixRadio.Item
              id={id}
              value={option.value}
              className={cn(
                "mt-0.5 flex size-4 shrink-0 cursor-pointer items-center justify-center rounded-full border border-rule-strong bg-surface-raised",
                "transition-colors duration-(--dur-micro)",
                "data-[state=checked]:border-surface-inverse",
              )}
            >
              <RadixRadio.Indicator className="size-2 rounded-full bg-surface-inverse" />
            </RadixRadio.Item>
            <div className="flex flex-col">
              <label htmlFor={id} className="cursor-pointer text-small text-text select-none">
                {option.label}
              </label>
              {option.hint ? (
                <span className="text-small text-text-mute">{option.hint}</span>
              ) : null}
            </div>
          </div>
        );
      })}
    </RadixRadio.Root>
  );
}
