'use client';

import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { Tooltip } from '@/components/ui/tooltip';
import { cn } from '@/lib/cn';
import { usePrefersReducedMotion } from '@/lib/hooks/use-external-store';
import { playTick } from '@/lib/sound/tick';

export interface WheelPickerItem {
  value: string;
  label: string;
  /** A short qualifier shown under the label, e.g. the vendor name. */
  sublabel?: string;
  /** Detail shown on hover and focus. Keeps a one-line summary reachable for
   *  every option without printing all of them down the page. */
  hint?: string;
  icon?: React.ReactNode;
  /** Rendered dimmed and skipped by keyboard navigation, but still visible -
   *  an option someone hasn't connected yet is information, not absence. */
  disabled?: boolean;
}

const ITEM_HEIGHT = 60;
/**
 * Rows on screen at once: the selected one, plus a single neighbour above and
 * below. Enough to show which way the wheel turns and what is coming next,
 * without the column of half-faded options a deeper window produces.
 */
const MAX_VISIBLE_ROWS = 3;

/**
 * How many copies of the list the looping wheel renders, and the shortest
 * list that gets to loop at all.
 *
 * Nine copies is enough that the recentre never lands within sight of an
 * edge even on a fast flick, while staying a small number of DOM rows for
 * the lists this holds (the largest is 43 models).
 */
const LOOPS = 9;
const MIN_LOOP_ITEMS = 4;

/**
 * How tall to make a wheel holding `count` options. A two-option wheel given
 * the full seven rows is five rows of empty air, which reads as a rendering
 * fault rather than a short list - so the window shrinks to what the list can
 * actually fill, staying odd and never dropping below three.
 */
function visibleRows(count: number): number {
  const needed = Math.max(3, count * 2 - 1);
  const capped = Math.min(MAX_VISIBLE_ROWS, needed);
  return capped % 2 === 0 ? capped - 1 : capped;
}

/**
 * A fixed-height row that vertically centres whatever wheels sit in it.
 *
 * Wheels of different lengths are different heights, and left to sit at the
 * top of their columns their selection bands land at different heights across
 * a row - which reads as misalignment, not as variety. Centring them inside a
 * shared frame puts every band on the same line, whatever each list holds.
 */
export function WheelRow({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn('flex items-center', className)}
      style={{ height: MAX_VISIBLE_ROWS * ITEM_HEIGHT }}
    >
      {children}
    </div>
  );
}
/** Degrees of cylinder rotation per row away from the band - roughly the
 *  curvature of a physical thumbwheel across the visible arc. */
const DEGREES_PER_ROW = 20;

/**
 * A physical thumbwheel: rows are laid around a cylinder, rotating away from
 * the reader as they leave the selection band, and clicking as each one
 * arrives under it.
 *
 * The curvature is continuous rather than stepped, so it tracks a half-scrolled
 * position the way the real control does. That needs a value updated every
 * frame, which is exactly the thing that must not go through React state - so
 * scroll position is written to a CSS custom property on the container and each
 * row derives its own angle from it in CSS. React state only ever holds the
 * centred index, which changes once per row rather than once per frame.
 */
export function WheelPicker({
  items,
  value,
  onChange,
  ariaLabel,
  className,
  animateChanges = false,
}: {
  items: WheelPickerItem[];
  value: string | null;
  onChange: (value: string) => void;
  ariaLabel: string;
  className?: string;
  /**
   * Spin to a value the caller set, clicking through the rows on the way,
   * instead of jumping to it silently.
   *
   * Off by default because most caller-driven changes are corrections, not
   * choices - a dependent wheel repopulating, or an agent loading in - and
   * animating those would announce work the reader did not ask for. A preset
   * is the opposite: the whole point is watching the three wheels move.
   */
  animateChanges?: boolean;
}) {
  const listId = useId();
  const scrollRef = useRef<HTMLDivElement>(null);
  const reducedMotion = usePrefersReducedMotion();

  /**
   * A wheel with enough options to be worth spinning wraps around instead of
   * hitting a wall.
   *
   * The list is repeated `LOOPS` times and the scroll starts in the middle
   * copy, so there is always a copy above and below to travel into; when the
   * position drifts near either end it is moved back by a whole copy, which
   * is invisible because every copy is identical. Two options cannot be a
   * cylinder - the repetition would read as a bug, not as continuity - so
   * short lists stay linear.
   */
  const looping = items.length >= MIN_LOOP_ITEMS;
  const loops = looping ? LOOPS : 1;
  const rendered = looping
    ? Array.from({ length: loops }, () => items).flat()
    : items;
  /** Where the middle copy starts, in rows. */
  const loopBase = looping ? Math.floor(loops / 2) * items.length : 0;

  const selectedIndex = items.findIndex((item) => item.value === value);
  const [centredIndex, setCentredIndex] = useState(
    (selectedIndex >= 0 ? selectedIndex : 0) + loopBase,
  );

  const lastTickedIndex = useRef(centredIndex);
  const frame = useRef<number | null>(null);
  const settleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Suppresses the tick while the wheel scrolls itself to a position the
  // caller set, rather than following a real gesture.
  const programmatic = useRef(true);
  // A caller-driven scroll that should still be heard (a preset). Separate
  // from `programmatic`, which also gates the commit - a preset has already
  // set the value, so re-committing it would be a redundant round trip.
  const audibleProgrammatic = useRef(false);
  /** The in-flight eased scroll, so a new target or a real gesture can stop it
   *  rather than fight it frame by frame. */
  const animation = useRef<number | null>(null);

  const paintOffset = useCallback(() => {
    const element = scrollRef.current;
    if (!element) return;
    element.style.setProperty(
      '--wheel-offset',
      (element.scrollTop / ITEM_HEIGHT).toFixed(3),
    );
  }, []);

  const scrollToIndex = useCallback(
    (index: number, smooth: boolean, audible = false) => {
      const element = scrollRef.current;
      if (!element) return;
      const top = index * ITEM_HEIGHT;
      // Already there: scrolling anyway would fire no scroll event, leaving
      // `programmatic` stuck true and swallowing the next real gesture's tick.
      if (Math.abs(element.scrollTop - top) < 1) return;
      programmatic.current = true;

      if (animation.current !== null) {
        cancelAnimationFrame(animation.current);
        animation.current = null;
      }

      if (!smooth || reducedMotion) {
        element.scrollTop = top;
        return;
      }

      // Hand-driven rather than `behavior: 'smooth'`. The track is
      // `snap-mandatory`, and the browser re-snaps a native smooth scroll
      // while it is still running - the animation lurches between rows
      // instead of gliding. Writing `scrollTop` each frame keeps snapping out
      // of it until the gesture is over, and gives the wheel a real ease
      // instead of the fixed curve the platform picks.
      const from = element.scrollTop;
      const distance = top - from;
      const rows = Math.abs(distance) / ITEM_HEIGHT;
      // Longer trips take longer, but sub-linearly - a spin across ten rows
      // should not take ten times as long as one.
      const duration = Math.min(1_800, 700 + Math.sqrt(rows) * 320);
      const start = performance.now();

      // Snapping off for the duration. `snap-mandatory` re-snaps the track on
      // every scroll position written underneath it, so an animation that
      // moves in sub-row steps gets yanked to the nearest row each frame -
      // which is the judder. Restored on the last frame so a real gesture
      // still snaps.
      element.style.scrollSnapType = 'none';

      const step = (now: number) => {
        const t = Math.min(1, (now - start) / duration);
        // easeInOutCubic: winds up, travels at a readable speed, settles.
        // A pure ease-out spends most of the duration nearly stopped, which
        // over a long spin reads as a lurch followed by a stall rather than
        // as a wheel turning.
        const eased = t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
        element.scrollTop = from + distance * eased;

        // Painted and ticked here rather than from the scroll events this
        // generates: one loop owns the frame, so the curvature and the clicks
        // land on the same position the wheel is actually at. Both are plain
        // DOM/audio writes - no React state - so a spin costs no renders.
        element.style.setProperty(
          '--wheel-offset',
          (element.scrollTop / ITEM_HEIGHT).toFixed(3),
        );

        const row = Math.round(element.scrollTop / ITEM_HEIGHT);
        if (row !== lastTickedIndex.current) {
          lastTickedIndex.current = row;
          if (audible) playTick();
        }

        if (t < 1) {
          animation.current = requestAnimationFrame(step);
          return;
        }

        element.style.scrollSnapType = '';
        animation.current = null;
        // One render at the end, to move the highlight onto the row the wheel
        // stopped on. Doing it per row is what made a long spin re-render the
        // whole list a dozen times.
        setCentredIndex(row);
      };

      animation.current = requestAnimationFrame(step);
    },
    [reducedMotion],
  );

  // Keep the wheel aligned with a value the caller changed underneath it - a
  // dependent wheel being repopulated, or an agent loading into the editor.
  // Derived during render rather than in an effect: an effect would set this a
  // render late, and `react-hooks/set-state-in-effect` is an error here.
  /**
   * The rendered row holding `selectedIndex` that is nearest where the wheel
   * already sits. On a looping wheel the same option exists once per copy, and
   * spinning to the far copy would travel the whole list to reach a
   * neighbour.
   */
  const nearestRowFor = useCallback(
    (index: number, from: number) => {
      if (!looping) return index;
      const copy = Math.round((from - index) / items.length);
      const clamped = Math.min(Math.max(copy, 0), loops - 1);
      return index + clamped * items.length;
    },
    [looping, items.length, loops],
  );

  const [lastSyncedValue, setLastSyncedValue] = useState(value);
  if (value !== lastSyncedValue) {
    setLastSyncedValue(value);
    if (selectedIndex >= 0) {
      const target = nearestRowFor(selectedIndex, centredIndex);
      if (target !== centredIndex) setCentredIndex(target);
    }
  }

  useEffect(() => {
    if (selectedIndex < 0) return;
    const target = nearestRowFor(selectedIndex, lastTickedIndex.current);

    // Animated: the spin walks `lastTickedIndex` forward itself, clicking on
    // each row as it passes the band, so the sound is locked to the position
    // rather than to scroll events arriving a frame or two behind it.
    if (animateChanges && target !== lastTickedIndex.current) {
      audibleProgrammatic.current = true;
      scrollToIndex(target, true, true);
      return;
    }

    lastTickedIndex.current = target;
    scrollToIndex(target, false);
    paintOffset();
  }, [
    selectedIndex,
    scrollToIndex,
    paintOffset,
    animateChanges,
    nearestRowFor,
  ]);

  useEffect(() => {
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      if (animation.current !== null) cancelAnimationFrame(animation.current);
      if (settleTimer.current !== null) clearTimeout(settleTimer.current);
    };
  }, []);

  function cancelAnimation() {
    if (animation.current === null) return;
    cancelAnimationFrame(animation.current);
    animation.current = null;
    // Snapping was turned off for the animation; the gesture needs it back.
    if (scrollRef.current) scrollRef.current.style.scrollSnapType = '';
    // The gesture owns the wheel from here, so its ticks and its commit are
    // real ones.
    programmatic.current = false;
    audibleProgrammatic.current = false;
  }

  function commit(index: number) {
    const item = rendered[index];
    if (!item || item.disabled) return;
    if (item.value !== value) onChange(item.value);
  }

  /**
   * Jump back by whole copies when the scroll nears an end.
   *
   * Every copy is identical and the shift is an exact multiple of the list
   * height, so the rows under the band do not change - the wheel simply has
   * road ahead of it again. Done during a scroll frame rather than on settle,
   * because a flick has to be able to keep going.
   */
  function recentre(element: HTMLDivElement) {
    if (!looping) return;
    const copyHeight = items.length * ITEM_HEIGHT;
    const lowerBound = copyHeight;
    const upperBound = (loops - 2) * copyHeight;

    if (element.scrollTop < lowerBound) {
      element.scrollTop += copyHeight;
      lastTickedIndex.current += items.length;
    } else if (element.scrollTop > upperBound) {
      element.scrollTop -= copyHeight;
      lastTickedIndex.current -= items.length;
    }
  }

  function handleScroll() {
    // The eased animation already paints, ticks and settles from inside its
    // own frame. Letting the scroll events it generates schedule a second
    // rAF - one that re-runs all of that and re-renders every row - is what
    // made a preset spin stutter: two loops writing the same wheel, plus a
    // React render per row crossed.
    if (animation.current !== null) return;
    if (frame.current !== null) return;

    frame.current = requestAnimationFrame(() => {
      frame.current = null;
      const element = scrollRef.current;
      if (!element) return;

      recentre(element);
      paintOffset();

      const index = Math.max(
        0,
        Math.min(
          rendered.length - 1,
          Math.round(element.scrollTop / ITEM_HEIGHT),
        ),
      );

      if (index !== lastTickedIndex.current) {
        lastTickedIndex.current = index;
        setCentredIndex(index);
        if (!programmatic.current || audibleProgrammatic.current) playTick();
      }

      // `scrollend` is not in every browser yet, so settling is detected by
      // the absence of further scroll events rather than by the event itself.
      if (settleTimer.current !== null) clearTimeout(settleTimer.current);
      settleTimer.current = setTimeout(() => {
        if (!programmatic.current) commit(index);
        programmatic.current = false;
        audibleProgrammatic.current = false;
      }, 120);
    });
  }

  function step(direction: 1 | -1) {
    let next = centredIndex + direction;
    while (rendered[next]?.disabled) next += direction;
    if (next < 0 || next >= rendered.length) return;

    programmatic.current = false;
    setCentredIndex(next);
    lastTickedIndex.current = next;
    playTick();
    scrollToIndex(next, true);
    commit(next);
  }

  function handleKeyDown(event: React.KeyboardEvent) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      step(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      step(-1);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      commit(centredIndex);
    }
  }

  const rows = visibleRows(items.length);
  const padding = ((rows - 1) / 2) * ITEM_HEIGHT;

  return (
    <div
      className={cn('group/wheel relative isolate select-none', className)}
      style={{ height: rows * ITEM_HEIGHT }}
    >
      {/* The band the wheel reads against. Sits behind the rows so the centred
          row's text stays fully opaque over it.

          Frosted, not a flat fill: `--glass-surface`/`--glass-border`/
          `--glass-blur` are the dashboard's panel material (globals.css).
          `--glass-blur` is a *complete* filter value, so it is assigned to
          `backdrop-filter` directly - wrapping it in `blur()` yields
          `blur(blur(24px) …)`, which the parser drops whole and leaves a
          see-through band with no blur at all (globals.css records that exact
          regression). */}
      <div
        aria-hidden
        className={cn(
          // Inset rather than `inset-x-0`: the band tracked the full column
          // width while the row it highlights is content-width, so it read as
          // a long empty capsule with the label parked at one end.
          'pointer-events-none absolute inset-x-1 top-1/2 z-0 -translate-y-1/2',
          'rounded-full border',
          'transition-[box-shadow,border-color] duration-(--dur-base) ease-(--ease-out)',
          'group-focus-within/wheel:border-primary',
        )}
        style={{
          height: ITEM_HEIGHT,
          background: 'var(--glass-surface)',
          borderColor: 'var(--glass-border)',
          backdropFilter: 'var(--glass-blur)',
          WebkitBackdropFilter: 'var(--glass-blur)',
        }}
      />

      <div
        ref={scrollRef}
        role="listbox"
        tabIndex={0}
        aria-label={ariaLabel}
        aria-activedescendant={`${listId}-${centredIndex}`}
        onScroll={handleScroll}
        onKeyDown={handleKeyDown}
        // Touching the wheel mid-spin takes it over. Without this the eased
        // animation keeps writing scrollTop underneath the gesture and the
        // two pull against each other.
        onPointerDown={cancelAnimation}
        onWheel={cancelAnimation}
        onTouchStart={cancelAnimation}
        className={cn(
          'relative z-10 h-full overflow-y-auto overscroll-contain rounded-lg outline-none',
          'snap-y snap-mandatory',
          // `!important` is load-bearing: globals.css sets `scrollbar-width:
          // thin` on `*` in an unlayered `@supports` block, and unlayered CSS
          // beats anything in `@layer utilities` no matter its specificity.
          '[scrollbar-width:none]! [&::-webkit-scrollbar]:hidden',
          // Rows dissolve toward the top and bottom edges. Together with the
          // rotation below this is what reads as a cylinder rather than a list.
          '[mask-image:linear-gradient(to_bottom,transparent,black_26%,black_74%,transparent)]',
        )}
        style={{
          scrollPaddingBlock: padding,
          perspective: reducedMotion ? undefined : '640px',
          perspectiveOrigin: 'center center',
        }}
      >
        <div aria-hidden style={{ height: padding }} />

        {rendered.map((item, index) => {
          const isCentred = index === centredIndex;

          const row = (
            // Keyed by position, not by value: on a looping wheel the same
            // option appears once per copy, so the value is not unique.
            <div
              key={`${index}-${item.value}`}
              id={`${listId}-${index}`}
              role="option"
              // Only the copy under the band is the selection - marking every
              // copy would announce the same option nine times.
              aria-selected={isCentred && item.value === value}
              aria-disabled={item.disabled || undefined}
              onClick={() => {
                if (item.disabled) return;
                programmatic.current = false;
                scrollToIndex(index, true);
                commit(index);
              }}
              className={cn(
                'flex snap-center items-center justify-center gap-3 px-3.5',
                item.disabled ? 'cursor-not-allowed' : 'cursor-pointer',
                item.disabled && 'opacity-40',
              )}
              style={{
                height: ITEM_HEIGHT,
                // The row's own seat on the cylinder. `--i` is its index and
                // `--wheel-offset` is the live scroll position in rows, so the
                // difference is how far this row currently sits from the band.
                ...(reducedMotion
                  ? null
                  : ({
                      '--i': index,
                      transform: `rotateX(calc((var(--wheel-offset, 0) - var(--i)) * ${DEGREES_PER_ROW}deg))`,
                      transformOrigin: 'center center',
                      backfaceVisibility: 'hidden',
                    } as React.CSSProperties)),
              }}
            >
              {/* Rendered only when there is a mark. An empty span is still a
                  flex child, so the row's `gap-3` reserved space beside it and
                  pushed icon-less lists - the named-voice wheel - off centre. */}
              {item.icon ? (
                <span
                  className={cn(
                    'flex shrink-0 items-center justify-center transition-[filter,opacity] duration-(--dur-base) ease-(--ease-out)',
                    // Off-band marks desaturate rather than dim, so the centred
                    // vendor's colour is what the eye lands on.
                    isCentred
                      ? 'opacity-100 saturate-100'
                      : 'opacity-70 saturate-0',
                  )}
                >
                  {item.icon}
                </span>
              ) : null}

              {/* `min-w-0` without `flex-1`: the label shrinks to its content
                  so the icon and text sit centred together, and still
                  truncates rather than pushing the row wider. */}
              <span className="min-w-0 text-center">
                <span
                  className={cn(
                    'block truncate leading-tight transition-colors duration-(--dur-base)',
                    // The centred row is the selection, so it takes the
                    // brightest text the theme has while everything else
                    // recedes - the contrast is what makes the band readable
                    // at a glance instead of a list of equals.
                    isCentred
                      ? 'text-body font-semibold text-text'
                      : 'text-small font-normal text-text-mute opacity-70',
                  )}
                >
                  {item.label}
                </span>
                {item.sublabel ? (
                  <span
                    className={cn(
                      'mt-1 block truncate text-[0.6875rem] leading-tight transition-colors duration-(--dur-base)',
                      isCentred ? 'text-text-dim' : 'text-text-mute opacity-60',
                    )}
                  >
                    {item.sublabel}
                  </span>
                ) : null}
              </span>
            </div>
          );

          // Hover detail rather than a paragraph under the wheel: with dozens
          // of options, printing every note would be the wall of text the
          // wheel replaced.
          return item.hint ? (
            <Tooltip key={`${index}-${item.value}`} content={item.hint} side="right">
              {row}
            </Tooltip>
          ) : (
            row
          );
        })}

        <div aria-hidden style={{ height: padding }} />
      </div>
    </div>
  );
}
