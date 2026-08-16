import { BRAND_PATHS } from '@/lib/brand-paths';
import { cn } from '@/lib/cn';

/**
 * A provider's mark: its real logo where one exists, its initial where one does
 * not.
 *
 * Both render in `currentColor` at the same size on the same plate. That is the
 * decision that makes a mixed set work - 19 of the 57 providers have an
 * obtainable logo and the rest do not, and a grid mixing full-colour brand
 * marks with grey monograms reads as broken rather than as varied. Monochrome
 * also keeps the product's own identity intact (`DESIGN_NOTES.md` §9) and
 * sidesteps 57 arbitrary brand hexes having to clear contrast in two themes.
 *
 * `connected` is carried in the plate, not in a badge beside it: at this grid
 * density the mark is the first thing the eye lands on, so it is the cheapest
 * place to put the one bit of state that matters.
 */
export function BrandMark({
  providerId,
  name,
  connected = false,
  className,
}: {
  providerId: string;
  name: string;
  connected?: boolean;
  className?: string;
}) {
  const path = BRAND_PATHS[providerId];

  return (
    <span
      aria-hidden
      className={cn(
        'flex size-9 shrink-0 items-center justify-center rounded-md border transition-colors duration-[--dur-micro]',
        connected
          ? 'border-rule-strong bg-surface-inverse text-text-inverse'
          : 'border-rule bg-surface-sunken text-text-dim',
        className,
      )}
    >
      {path ? (
        <svg viewBox="0 0 24 24" className="size-4 fill-current" role="presentation">
          <path d={path} />
        </svg>
      ) : (
        <span className="font-mono text-small font-medium leading-none">
          {name.charAt(0).toUpperCase()}
        </span>
      )}
    </span>
  );
}
