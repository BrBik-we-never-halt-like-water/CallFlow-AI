'use client';

import { cn } from '@/lib/cn';

/**
 * A number that rolls to its new value one digit at a time, like a mechanical
 * counter.
 *
 * Cost and response time are recomputed the instant a provider changes, and a
 * figure that simply swaps is easy to miss - especially when a preset moves
 * all three legs at once. Rolling makes the change the thing you notice, and
 * carries which direction it went.
 *
 * Each digit is a vertical strip 0-9 translated by its own value. Only the
 * digits that actually differ move, so `$0.041` -> `$0.048` rolls the last
 * place and leaves the rest still, exactly as the real thing would.
 */

const DIGITS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];

export function RollingNumber({
  value,
  className,
}: {
  /** The already-formatted figure, symbols and all - `$0.041`, `1.4s`. */
  value: string;
  className?: string;
}) {
  // Keyed from the right, not the left. `$0.041` -> `$0.14` is one character
  // shorter, and a left-anchored key would hand each span a different
  // character than it held last render - React reuses the element and the
  // strip jumps instead of rolling. Counting from the end keeps the units
  // place the units place.
  const chars = value.split('').map((char, index, all) => ({
    char,
    key: `${all.length - index}-${/\d/.test(char) ? 'd' : char}`,
  }));

  return (
    <span className={cn('inline-flex tabular-nums', className)}>
      {/* The whole figure is one accessible string; the per-character strips
          below are decoration and would otherwise be read out as a column of
          loose digits. */}
      <span className="sr-only">{value}</span>

      <span aria-hidden className="inline-flex">
        {chars.map(({ char, key }) => {
          const digit = DIGITS.indexOf(char);

          // Anything that is not a digit - a currency symbol, a decimal
          // point, a unit - has nothing to roll through and stays put.
          if (digit < 0) {
            return (
              <span key={key} className="inline-block">
                {char}
              </span>
            );
          }

          return (
            <span
              key={key}
              className="inline-block overflow-hidden align-bottom"
              // `1lh`: the window has to be exactly one line tall for a whole
              // number of digits to fit, whatever the type size is here.
              style={{ height: '1lh' }}
            >
              <span
                className="flex flex-col transition-transform duration-(--dur-settle) ease-(--ease-out)"
                style={{ transform: `translateY(-${digit}lh)` }}
              >
                {DIGITS.map((d) => (
                  <span key={d} style={{ height: '1lh' }}>
                    {d}
                  </span>
                ))}
              </span>
            </span>
          );
        })}
      </span>
    </span>
  );
}
