'use client';

import { Slot } from '@radix-ui/react-slot';
import { forwardRef } from 'react';
import { cn } from '@/lib/cn';
import { Lamp } from '@/components/brand/lamp';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

/**
 * The primary action is monochrome, not brand-coloured.
 *
 * That is deliberate and it is the most important rule in the design: lamp
 * colours are reserved for call state. Because a button is never brass or jade,
 * a lamp lighting on an otherwise ink-on-paper page carries real weight.
 *
 * `primary` and `secondary` both pick up the same glass material as `Panel`
 * (`.btn-glass-primary` / `.btn-glass-secondary`, globals.css) - a button
 * sitting on a glass panel shouldn't read as a different substance. Their
 * hover/active states live in those CSS classes rather than as `hover:`/
 * `active:` utilities here, because both classes are unlayered and a layered
 * utility touching `background` could never win against them.
 */
const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    'btn-pulse btn-glass-primary text-text-inverse hover:opacity-90 active:opacity-80 border border-transparent',
  secondary: 'btn-glass-secondary border text-text',
  ghost:
    'border border-transparent bg-transparent text-text-dim hover:bg-surface-hover hover:text-text',
  // Flare is a lamp colour, and this is the one exception: a destructive action
  // is a state the operator must not misread, which is the same job a lamp does.
  danger:
    'border border-transparent bg-[var(--lamp-flare)] text-white hover:opacity-90 active:opacity-80',
};

const SIZES: Record<ButtonSize, string> = {
  // Hit targets clear 40px on touch and 32px on pointer.
  sm: 'h-8 min-h-8 px-3 text-small gap-1.5',
  md: 'h-10 min-h-10 px-4 text-small gap-2',
  lg: 'h-12 min-h-12 px-6 text-body gap-2',
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /**
   * Swaps the label for a lamp sequence and locks the width, so a button never
   * changes size while it works.
   */
  loading?: boolean;
  /** Render as the child element - for a link that looks like a button. */
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      className,
      variant = 'primary',
      size = 'md',
      loading = false,
      asChild = false,
      disabled,
      children,
      ...props
    },
    ref,
  ) {
    const Component = asChild ? Slot : 'button';
    const isDisabled = disabled || loading;

    return (
      <Component
        ref={ref}
        // A Slot child owns its own element type, so `type` and `disabled` are only
        // meaningful on a real button.
        {...(asChild
          ? {}
          : { type: props.type ?? 'button', disabled: isDisabled })}
        aria-busy={loading || undefined}
        aria-disabled={asChild && isDisabled ? true : undefined}
        className={cn(
          'relative inline-flex cursor-pointer items-center justify-center rounded-sm font-medium',
          'transition-[background-color,opacity,border-color] duration-(--dur-micro) ease-(--ease-out)',
          'disabled:cursor-not-allowed disabled:opacity-45 aria-disabled:cursor-not-allowed aria-disabled:opacity-45',
          'whitespace-nowrap',
          SIZES[size],
          VARIANTS[variant],
          className,
        )}
        {...props}
      >
        {loading ? (
          <>
            {/* The label stays in flow but invisible, which is what locks the
              width - the button cannot jump as it starts working. */}
            <span className="invisible contents">{children}</span>
            <span className="absolute inset-0 flex items-center justify-center gap-1">
              <LoadingLamps />
            </span>
          </>
        ) : (
          children
        )}
      </Component>
    );
  },
);

/**
 * Loading indicator: lamps lighting in sequence, not a spinner. A spinner says
 * "wait"; a sequence says "something is progressing", which is what is true.
 */
function LoadingLamps() {
  return (
    <span aria-hidden className="inline-flex items-center gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="lamp-pulse"
          style={{ animationDelay: `${i * 200}ms` }}
        >
          <Lamp state="brass" size="sm" />
        </span>
      ))}
    </span>
  );
}
