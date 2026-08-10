'use client';

import { createContext, useContext, useId } from 'react';
import { cn } from '@/lib/cn';

/**
 * Form field plumbing.
 *
 * Every input in this product gets a visible label, and an error is linked to
 * its input via `aria-describedby` rather than left as nearby red text. Doing
 * that by hand on every form is how a field eventually ships without it, so the
 * wiring lives here and inputs read it off context.
 */

interface FieldContextValue {
  inputId: string;
  describedBy: string | undefined;
  invalid: boolean;
  disabled: boolean;
}

const FieldContext = createContext<FieldContextValue | null>(null);

export function useField(): FieldContextValue | null {
  return useContext(FieldContext);
}

export interface FieldProps {
  label: string;
  /** Explanation shown under the label, before the control. */
  hint?: string;
  /** Error message. Its presence is what puts the field into the error state. */
  error?: string | null;
  /** Help text below the control. Hidden while an error is showing. */
  help?: string;
  required?: boolean;
  disabled?: boolean;
  /** Hide the label visually but keep it for assistive tech. Use sparingly. */
  labelHidden?: boolean;
  className?: string;
  children: React.ReactNode;
}

export function Field({
  label,
  hint,
  error,
  help,
  required = false,
  disabled = false,
  labelHidden = false,
  className,
  children,
}: FieldProps) {
  const base = useId();
  const inputId = `${base}-input`;
  const hintId = hint ? `${base}-hint` : undefined;
  const errorId = error ? `${base}-error` : undefined;
  const helpId = help && !error ? `${base}-help` : undefined;

  const describedBy =
    [hintId, errorId, helpId].filter(Boolean).join(' ') || undefined;

  return (
    <FieldContext.Provider
      value={{ inputId, describedBy, invalid: Boolean(error), disabled }}
    >
      <div className={cn('flex flex-col gap-1.5', className)}>
        <label
          htmlFor={inputId}
          className={cn(
            'text-small font-medium text-text',
            labelHidden && 'sr-only',
            disabled && 'opacity-45',
          )}
        >
          {label}
          {required ? (
            <span className="ml-1 text-text-mute" aria-hidden>
              *
            </span>
          ) : null}
          {required ? <span className="sr-only"> (required)</span> : null}
        </label>

        {hint ? (
          <p id={hintId} className="text-small text-text-mute">
            {hint}
          </p>
        ) : null}

        {children}

        {error ? (
          <p
            id={errorId}
            role="alert"
            className="flex items-start gap-1.5 text-small text-lamp-flare-text"
          >
            <span
              aria-hidden
              className="mt-[0.45em] size-1.5 shrink-0 rounded-full bg-[var(--lamp-flare)]"
            />
            {error}
          </p>
        ) : help ? (
          <p id={helpId} className="text-small text-text-mute">
            {help}
          </p>
        ) : null}
      </div>
    </FieldContext.Provider>
  );
}

/**
 * Error summary for long forms, anchored to each offending field.
 *
 * A screen-reader user filling a twelve-field form should not have to walk the
 * whole thing to find what failed.
 */
export function ErrorSummary({
  errors,
  className,
}: {
  errors: { id: string; label: string; message: string }[];
  className?: string;
}) {
  if (errors.length === 0) return null;

  return (
    <div
      role="alert"
      className={cn(
        'rounded-md border border-[color-mix(in_oklab,var(--lamp-flare)_30%,transparent)] bg-[color-mix(in_oklab,var(--lamp-flare)_10%,transparent)] p-4',
        className,
      )}
    >
      <h2 className="text-h4 font-medium text-lamp-flare-text">
        {errors.length === 1
          ? 'One field needs attention'
          : `${errors.length} fields need attention`}
      </h2>
      <ul className="mt-2 flex flex-col gap-1">
        {errors.map((e) => (
          <li key={e.id}>
            <a
              href={`#${e.id}`}
              className="text-small text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
            >
              <span className="font-medium">{e.label}</span> - {e.message}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
