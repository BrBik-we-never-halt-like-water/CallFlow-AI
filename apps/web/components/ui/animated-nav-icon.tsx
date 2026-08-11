import type { Icon } from '@phosphor-icons/react';
import { cn } from '@/lib/cn';

/**
 * A nav icon that bounces when the *whole nav row* is hovered, not just the
 * icon glyph itself - the parent `<Link>` needs Tailwind's `group` class for
 * this to trigger (`app-shell.tsx`, `app-nav.tsx`). Driven by the
 * `nav-icon-bounce` keyframe in `globals.css` rather than a JS animation
 * library: the sitewide `prefers-reduced-motion` rule there already collapses
 * every animation/transition duration to 1ms, so this needs no reduced-motion
 * check of its own.
 */
export function AnimatedNavIcon({
  icon: IconComponent,
  active,
  className,
}: {
  icon: Icon;
  active: boolean;
  className?: string;
}) {
  return (
    <span className="inline-flex shrink-0 origin-center transition-transform duration-150 ease-out group-hover:animate-[nav-icon-bounce_0.5s_ease-out_both]">
      <IconComponent
        aria-hidden
        weight={active ? 'fill' : 'regular'}
        className={cn('shrink-0', className)}
      />
    </span>
  );
}
