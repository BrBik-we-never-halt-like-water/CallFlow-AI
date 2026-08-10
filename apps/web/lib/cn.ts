import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge class names, letting a caller's `className` win over a component's
 * defaults. Every component in `components/ui` accepts `className`, so this is
 * how a one-off override happens without a one-off style.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
