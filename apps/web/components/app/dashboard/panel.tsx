'use client';

import { useLayoutEffect, useRef, useState } from 'react';
import { CaretDownIcon } from '@phosphor-icons/react/dist/ssr';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/cn';

/**
 * The bento grid's building blocks.
 *
 * Every panel is fixed-height by construction: the card is a flex column,
 * the header never shrinks, and the body is the only thing that scrolls.
 * That is what keeps the dashboard a single viewport - a panel receiving
 * more rows scrolls internally instead of growing and pushing the page
 * taller.
 */

export function Panel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn('dash-card flex min-h-0 flex-col', className)}>
      {children}
    </section>
  );
}

export function PanelHeader({
  title,
  children,
  className,
}: {
  title: string;
  /** Controls - a scope toggle, a month selector - sit at the right. */
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        'flex shrink-0 items-center justify-between gap-2 px-3.5 pb-1.5 pt-2',
        className,
      )}
    >
      <h2
        className="min-w-0 flex-1 truncate text-[0.6875rem] font-semibold uppercase tracking-[0.05em]"
        style={{ color: 'var(--dash-text)' }}
      >
        {title}
      </h2>
      {children ? (
        <div className="flex shrink-0 items-center gap-1.5">{children}</div>
      ) : null}
    </header>
  );
}

/** The scrolling region. The only part of a panel that moves. */
export function PanelBody({
  children,
  className,
  label,
}: {
  children: React.ReactNode;
  className?: string;
  /** Names the region for keyboard users, who scroll it without a bar. */
  label?: string;
}) {
  return (
    <div
      className={cn('dash-scroll min-h-0 flex-1', className)}
      tabIndex={0}
      role="region"
      aria-label={label}
    >
      {children}
    </div>
  );
}

/**
 * A compact select styled as a pill. Used for both the scope toggle and the
 * month selector.
 *
 * Built on the shared dropdown rather than a native `<select>`: the native
 * element only lets you style the *trigger*, and the browser then paints its
 * own square, hard-edged option list beside a rounded pill. The menu here is
 * the same rounded, shadowed surface as every other menu in the product.
 */
export function PillSelect<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string }[];
  /** Accessible name - the visible text is the current value alone. */
  label: string;
}) {
  const current = options.find((option) => option.value === value);
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [panel, setPanel] = useState<{ w: number; h: number } | null>(null);

  // Measured rather than inherited: `DropdownMenuContent` is portalled out of
  // the panel, so it can neither inherit a custom property from it nor query
  // it as a container. A layout effect runs before paint, so the menu is never
  // briefly the wrong size.
  useLayoutEffect(() => {
    const card = triggerRef.current?.closest('section');
    if (!card) return;
    const measure = () =>
      setPanel({ w: card.clientWidth, h: card.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(card);
    return () => observer.disconnect();
  }, []);

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          ref={triggerRef}
          type="button"
          aria-label={label}
          className="inline-flex cursor-pointer items-center gap-1 rounded-full px-1 py-0.5 text-[0.6875rem] font-medium outline-none transition-colors"
          style={{ color: 'var(--dash-text-dim)' }}
        >
          <span className="truncate">{current?.label ?? value}</span>
          {/* Points at the menu: down when it is closed, up while it is
              open, so the control says which way the list will go. */}
          <CaretDownIcon
            aria-hidden
            className="size-2.5 shrink-0 transition-transform duration-150 motion-reduce:transition-none"
            style={{
              color: 'var(--dash-text-mute)',
              transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            }}
          />
        </button>
      </DropdownMenuTrigger>

      {/* One width for every menu on the dashboard, stepped up on the wider
          panels rather than scaled continuously - a menu that is a different
          size in each card reads as an accident, and a menu sized as a
          fraction of its panel produced exactly that. Two sizes, chosen by
          how much room the card has. The height is a cap: a long list of
          teammate names scrolls inside it (`dash-scroll`, no visible bar)
          rather than growing the menu. */}
      <DropdownMenuContent
        align="end"
        className="dash-menu dash-scroll"
        style={{
          width: panel && panel.w >= 520 ? 116 : 98,
          minWidth: 0,
          maxHeight: 220,
        }}
      >
        {options.map((option) => (
          <DropdownMenuItem
            key={option.value}
            onSelect={() => onChange(option.value)}
          >
            {/* No tick. The selected row is already legible from its weight
                and full-strength colour, and a checkmark column costs width
                on every row to mark one of them. `aria-current` carries the
                same fact to a screen reader. */}
            <span
              aria-current={option.value === value}
              className="min-w-0 flex-1 truncate"
              style={
                option.value === value
                  ? { color: 'var(--text)', fontWeight: 500 }
                  : { color: 'var(--text-dim)' }
              }
            >
              {option.label}
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * An empty panel body. Says what is missing and what would fill it, never
 * a bare "No data" - and never a plausible-looking zero, which would read
 * as a real measurement.
 */
export function PanelEmpty({
  message,
  hint,
}: {
  message: string;
  hint?: string;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 px-6 py-8 text-center">
      <p className="text-[0.75rem]" style={{ color: 'var(--dash-text-dim)' }}>
        {message}
      </p>
      {hint ? (
        <p
          className="text-[0.6875rem]"
          style={{ color: 'var(--dash-text-mute)' }}
        >
          {hint}
        </p>
      ) : null}
    </div>
  );
}
