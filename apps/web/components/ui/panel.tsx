import { cn } from '@/lib/cn';
import { WaveLine } from '@/components/brand/wave-spine';

/**
 * A surface: hairline border plus real glass.
 *
 * Frosted, not flat - `--glass-surface` (a translucent fill) over `--glass-blur`
 * (a `backdrop-filter` blur), plus a soft shadow with an inset highlight
 * (`.panel-glass` / `.panel-glass-sunken`, globals.css), so a panel reads as
 * floating above the page rather than painted onto it. The border colour comes
 * from `--glass-border` inside those same classes, not a Tailwind border-color
 * utility - a layered utility couldn't win against the unlayered glass classes
 * anyway (see the comment above `.panel-glass-interactive`), so `border` here only
 * turns the width/style on. `interactive` adds a hover lift, which is the only
 * place anything in this design moves on hover.
 */
export function Panel({
  as: Component = 'div',
  sunken = false,
  interactive = false,
  /** Drop the shadow down to just the hairline highlight - for a panel nested inside another. */
  flat = false,
  className,
  children,
  ...props
}: {
  as?: React.ElementType;
  sunken?: boolean;
  interactive?: boolean;
  flat?: boolean;
  className?: string;
  children?: React.ReactNode;
} & React.HTMLAttributes<HTMLElement>) {
  return (
    <Component
      className={cn(
        'rounded-xl border',
        sunken ? 'panel-glass-sunken' : 'panel-glass',
        !sunken && flat && 'panel-glass-flat',
        interactive && 'panel-glass-interactive hover:-translate-y-0.5',
        className,
      )}
      {...props}
    >
      {children}
    </Component>
  );
}

/** Uppercase mono eyebrow. The one place uppercase is used by design. */
export function Eyebrow({
  children,
  className,
  as: Component = 'p',
}: {
  children: React.ReactNode;
  className?: string;
  as?: React.ElementType;
}) {
  return (
    <Component className={cn('eyebrow text-text-mute', className)}>
      {children}
    </Component>
  );
}

/**
 * A section header: display headline, optional eyebrow, and a sub-line capped at a
 * readable measure.
 */
export function SectionHeading({
  eyebrow,
  title,
  sub,
  className,
  align = 'left',
}: {
  eyebrow?: string;
  title: React.ReactNode;
  sub?: React.ReactNode;
  className?: string;
  align?: 'left' | 'center';
}) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3',
        align === 'center' && 'items-center text-center',
        className,
      )}
    >
      {eyebrow ? (
        <div
          className={cn(
            'flex items-center gap-3',
            align === 'center' && 'justify-center',
          )}
        >
          <Eyebrow>{eyebrow}</Eyebrow>
          {align === 'left' ? <WaveLine className="w-12" /> : null}
        </div>
      ) : null}

      <h2 className="measure-display font-display text-h2 text-text">
        {title}
      </h2>

      {sub ? (
        <p
          className={cn(
            'measure text-body-l text-text-dim',
            align === 'center' && 'mx-auto',
          )}
        >
          {sub}
        </p>
      ) : null}
    </div>
  );
}
