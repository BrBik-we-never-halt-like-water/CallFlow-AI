'use client';

import { cn } from '@/lib/cn';

/**
 * Segmented control for a small set of mutually exclusive options.
 *
 * Built as a radiogroup rather than two buttons, so a keyboard user gets arrow-key
 * movement between the options instead of tabbing through each one.
 *
 * It lived in `marketing/pricing-table.tsx` until the pricing pages were removed.
 * It was never pricing-specific - it only happened to be first used by the
 * billing-period and currency toggles - and `RoiCalculator` needs it, so it moved
 * here rather than leaving a pricing module alive purely to export one control.
 */
export function SegmentedToggle<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string; hint?: string }[];
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex items-center gap-0.5 rounded-sm border border-rule bg-surface-sunken p-0.5"
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={cn(
              'inline-flex cursor-pointer items-center gap-1.5 rounded-xs px-3 py-1.5 text-small font-medium',
              'transition-colors duration-(--dur-micro)',
              active
                ? 'bg-surface-inverse text-text-inverse'
                : 'text-text-dim hover:text-text',
            )}
          >
            {option.label}
            {option.hint ? (
              <span
                className={cn(
                  'font-mono text-label',
                  active ? 'opacity-80' : 'text-text-mute',
                )}
              >
                {option.hint}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
