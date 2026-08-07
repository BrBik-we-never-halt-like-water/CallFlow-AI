"use client";

import { MagnifyingGlassIcon } from "@phosphor-icons/react/dist/ssr";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";
import { normalisePhone } from "@/lib/format/phone";
import { useField } from "./field";

/**
 * Shared control chrome. Depth is a 1px rule, never a shadow, and the error
 * state is a flare rule — the only place a lamp colour appears on a control,
 * because a field that will stop a run from starting is call state.
 */
const CONTROL = [
  "w-full rounded-sm border bg-surface-raised text-text",
  "placeholder:text-text-mute",
  "transition-[border-color,background-color] duration-(--dur-micro) ease-(--ease-out)",
  "disabled:cursor-not-allowed disabled:opacity-45",
  "read-only:bg-surface-sunken read-only:text-text-dim",
].join(" ");

function ruleClass(invalid: boolean) {
  return invalid
    ? "border-[var(--lamp-flare)] focus-visible:outline-[var(--lamp-flare)]"
    : "border-rule hover:border-rule-strong";
}

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /** `phone` sets mono type and normalises to E.164 on blur. */
  variant?: "text" | "phone" | "search";
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, variant = "text", invalid, type = "text", onBlur, ...props },
  ref,
) {
  const field = useField();
  const isInvalid = invalid ?? field?.invalid ?? false;

  return (
    <input
      ref={ref}
      id={props.id ?? field?.inputId}
      type={type}
      aria-invalid={isInvalid || undefined}
      aria-describedby={props["aria-describedby"] ?? field?.describedBy}
      disabled={props.disabled ?? field?.disabled}
      onBlur={(e) => {
        // Normalising on blur rather than on every keystroke lets someone paste
        // `98765 43210` and type over it without the caret jumping around.
        if (variant === "phone" && e.target.value.trim()) {
          const normalised = normalisePhone(e.target.value);
          if (normalised !== e.target.value) {
            e.target.value = normalised;
            // Re-dispatch so uncontrolled and controlled forms both see it.
            e.target.dispatchEvent(new Event("input", { bubbles: true }));
          }
        }
        onBlur?.(e);
      }}
      className={cn(
        CONTROL,
        ruleClass(isInvalid),
        "h-10 px-3 text-body",
        variant === "phone" && "font-mono text-data tabular-nums",
        className,
      )}
      {...props}
    />
  );
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean; mono?: boolean }
>(function Textarea({ className, invalid, mono = false, ...props }, ref) {
  const field = useField();
  const isInvalid = invalid ?? field?.invalid ?? false;

  return (
    <textarea
      ref={ref}
      id={props.id ?? field?.inputId}
      aria-invalid={isInvalid || undefined}
      aria-describedby={props["aria-describedby"] ?? field?.describedBy}
      disabled={props.disabled ?? field?.disabled}
      className={cn(
        CONTROL,
        ruleClass(isInvalid),
        "min-h-24 resize-y px-3 py-2.5",
        mono ? "font-mono text-data" : "text-body",
        className,
      )}
      {...props}
    />
  );
});

/** Search field with a leading icon and a clear affordance. */
export const SearchInput = forwardRef<
  HTMLInputElement,
  InputProps & { onClear?: () => void }
>(function SearchInput({ className, onClear, value, ...props }, ref) {
  const hasValue = typeof value === "string" && value.length > 0;

  return (
    <div className="relative">
      <MagnifyingGlassIcon
        aria-hidden
        className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-mute"
      />
      <Input
        ref={ref}
        type="search"
        variant="search"
        value={value}
        className={cn("pl-9", hasValue && onClear && "pr-9", className)}
        {...props}
      />
      {hasValue && onClear ? (
        <button
          type="button"
          onClick={onClear}
          aria-label="Clear search"
          className="absolute right-1 top-1/2 flex size-8 -translate-y-1/2 cursor-pointer items-center justify-center rounded-sm text-text-mute hover:bg-surface-hover hover:text-text"
        >
          ×
        </button>
      ) : null}
    </div>
  );
});

/**
 * Character counter for a control with a minimum length.
 *
 * Used on the campaign goal, where the minimum is not arbitrary: a thin goal
 * genuinely fails at call time, so the counter says why rather than just
 * counting.
 */
export function MinLengthCounter({
  value,
  min,
  reason,
  className,
}: {
  value: string;
  min: number;
  reason: string;
  className?: string;
}) {
  const length = value.trim().length;
  const short = length < min;

  return (
    <p
      className={cn("flex flex-wrap items-baseline gap-x-2 text-small", className)}
      aria-live="polite"
    >
      <span
        className={cn(
          "font-mono text-data tabular-nums",
          short ? "text-lamp-brass-text" : "text-text-mute",
        )}
      >
        {length} / {min} min
      </span>
      {short ? <span className="text-text-dim">{reason}</span> : null}
    </p>
  );
}
