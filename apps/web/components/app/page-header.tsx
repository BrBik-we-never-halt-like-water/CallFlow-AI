import { cn } from '@/lib/cn';

/**
 * The management surface's page header - the dashboard's own header
 * language, shared so every section reads as one product.
 *
 * Deliberately small. The old headers set a display-scale headline over a
 * sub-sentence on every page ("The controls behind every run"), which spent
 * ~120px of vertical space naming a page the sidebar already names. An
 * operational page's title is a label, not a headline: 11px uppercase, the
 * same treatment as a panel title, with whatever the page needs (a count, a
 * primary action) on the same line.
 *
 * `title` stays in the DOM as the page's h1 for assistive tech even though
 * it renders small.
 */
export function PageHeader({
  title,
  /** A live figure beside the title - a count, never decoration. */
  figure,
  /** Controls on the right: the primary action, a filter, a toggle. */
  children,
  className,
}: {
  title: string;
  figure?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        'flex min-h-8 flex-wrap items-center justify-between gap-x-3 gap-y-2',
        className,
      )}
    >
      <div className="flex items-baseline gap-2">
        <h1
          className="text-[0.6875rem] font-semibold uppercase tracking-[0.05em]"
          style={{ color: 'var(--dash-text)' }}
        >
          {title}
        </h1>
        {figure !== undefined ? (
          <span
            className="dash-num text-[1.125rem] font-semibold leading-none"
            style={{ color: 'var(--dash-figure)' }}
          >
            {figure}
          </span>
        ) : null}
      </div>

      {children ? (
        <div className="flex flex-wrap items-center gap-2">{children}</div>
      ) : null}
    </header>
  );
}
