'use client';

import { MonitorIcon, MoonIcon, SunIcon } from '@phosphor-icons/react/dist/ssr';
import { useRef } from 'react';
import { cn } from '@/lib/cn';
import { usePrefersReducedMotion } from '@/lib/hooks/use-external-store';
import { applyTheme, useTheme } from '@/lib/hooks/use-theme';
import type { ThemePreference } from '@/lib/theme';

const OPTIONS: { value: ThemePreference; label: string; Icon: typeof SunIcon }[] = [
  { value: 'light', label: 'Light', Icon: SunIcon },
  { value: 'dark', label: 'Dark', Icon: MoonIcon },
  { value: 'system', label: 'System', Icon: MonitorIcon },
];

/**
 * The theme control: a three-way segmented switch, and the reveal.
 *
 * **Three options, not a two-state flip.** "System" is a real preference, not
 * the absence of one - a two-state toggle silently opts the user out of their
 * OS setting the first time they touch it, and gives them no way back. The
 * cost is one more control; the benefit is that "follow my machine" stays
 * expressible.
 *
 * **The reveal.** Switching theme is one of the few moments where a large,
 * showy animation is honest: the whole page genuinely does change at once, so
 * animating it explains what happened rather than decorating it. A circular
 * clip-path grows from the button that was clicked, so the new theme arrives
 * *from* the control that caused it - the spatial-continuity rule, applied to a
 * global state change.
 *
 * It runs on the View Transitions API, which is what makes this cheap: the
 * browser snapshots the old and new frames itself, so there is no cross-fading
 * of duplicated DOM, no double render, and no state to unwind if the user
 * clicks again mid-animation. `ViewTransitions` (the route crossfade) already
 * proved the API works in this app.
 *
 * Three fallbacks, in order: no View Transitions support -> the theme still
 * changes, instantly; `prefers-reduced-motion` -> instant on purpose, since a
 * full-screen wipe is exactly the kind of motion that setting exists to
 * refuse; a click with no coordinates (keyboard activation) -> the reveal
 * originates from the button's own centre rather than the top-left corner.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { preference, resolved, setPreference } = useTheme();
  const reduced = usePrefersReducedMotion();
  const ref = useRef<HTMLDivElement>(null);

  function choose(next: ThemePreference, event: React.MouseEvent) {
    if (next === preference) return;

    const nextResolved =
      next === 'system'
        ? window.matchMedia('(prefers-color-scheme: dark)').matches
          ? 'dark'
          : 'light'
        : next;

    // Nothing to animate if the pixels do not actually change - switching
    // 'dark' -> 'system' on a machine already set to dark is a preference
    // change, not a visual one.
    const visuallyChanges = nextResolved !== resolved;

    const startViewTransition = (
      document as Document & {
        startViewTransition?: (cb: () => void) => { ready: Promise<void> };
      }
    ).startViewTransition;

    if (reduced || !visuallyChanges || typeof startViewTransition !== 'function') {
      setPreference(next);
      return;
    }

    // Where the circle grows from. `event.clientX` is 0 for a keyboard-driven
    // click, which would otherwise wipe in from the viewport's top-left corner
    // and look like a glitch rather than a response.
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const x = event.clientX || rect.left + rect.width / 2;
    const y = event.clientY || rect.top + rect.height / 2;

    // The radius has to reach the furthest corner or the old theme is left in
    // the corners of the screen.
    const endRadius = Math.hypot(
      Math.max(x, window.innerWidth - x),
      Math.max(y, window.innerHeight - y),
    );

    const root = document.documentElement;
    // Tells globals.css to suppress the default cross-fade for this one
    // transition, without touching the route crossfade that shares the same
    // pseudo-elements.
    root.setAttribute('data-theme-transition', '');

    const transition = startViewTransition.call(document, () => {
      // Inside the callback on purpose: the browser captures the "before"
      // frame before this runs and the "after" frame once it settles. Applying
      // the theme outside would give it two identical frames and no animation.
      applyTheme(nextResolved);
      setPreference(next);
    });

    transition.ready
      .then(() => {
        const animation = root.animate(
          {
            clipPath: [
              `circle(0px at ${x}px ${y}px)`,
              `circle(${endRadius}px at ${x}px ${y}px)`,
            ],
          },
          {
            duration: 620,
            // A long, decelerating tail: the wipe should arrive quickly and
            // settle, not travel at a constant speed like a loading bar.
            easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
            // Only the incoming theme is clipped. The outgoing one stays put
            // underneath, so the new theme reads as arriving over the old
            // rather than the old tearing away to reveal it.
            pseudoElement: '::view-transition-new(root)',
          },
        );
        return animation.finished;
      })
      // The attribute has to come off however this ends. A rejected `ready`
      // (the transition was skipped, or another started on top of it) would
      // otherwise leave the marker on and permanently disable the route
      // crossfade - a failed animation quietly breaking an unrelated one.
      .catch(() => {})
      .finally(() => root.removeAttribute('data-theme-transition'));
  }

  return (
    <div
      ref={ref}
      role="radiogroup"
      aria-label="Colour theme"
      className={cn(
        'inline-flex items-center gap-0.5 rounded-full border border-rule bg-surface-sunken p-0.5',
        className,
      )}
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = value === preference;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            title={label}
            onClick={(event) => choose(value, event)}
            className={cn(
              'inline-flex size-7 cursor-pointer items-center justify-center rounded-full',
              'transition-colors duration-(--dur-micro)',
              active
                ? 'bg-surface-raised text-text shadow-xs'
                : 'text-text-mute hover:text-text',
            )}
          >
            <Icon aria-hidden weight={active ? 'fill' : 'regular'} className="size-4" />
            <span className="sr-only">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
