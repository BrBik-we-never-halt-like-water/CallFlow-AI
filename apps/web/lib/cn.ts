import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * `text-*` carries two independent Tailwind v4 theme scales - colour
 * (`--color-*`, e.g. `text-text-dim`) and font size (`--text-*`, e.g.
 * `text-label`) - and unconfigured `tailwind-merge` only recognises Tailwind's
 * *default* size keywords (`xs`/`sm`/`base`/...) as the font-size axis.
 * Anything else after `text-` falls through to its colour matcher (which
 * accepts any value, by design, for CSS-first custom themes), so a component
 * combining a colour utility with one of this project's own size names -
 * `text-text-dim text-label`, say - got both classified into the *same*
 * conflict group: `twMerge` kept only the last one and silently dropped the
 * other, sometimes invisibly (a `Tag` losing its text colour entirely). This
 * is `globals.css`'s actual font-size scale (`--text-display-xl` through
 * `--text-label`, registered in `@theme inline`) - keep the two lists in sync.
 */
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: [
        "display-xl",
        "display-l",
        "h2",
        "h3",
        "h4",
        "body-l",
        "body",
        "small",
        "data",
        "label",
      ],
    },
  },
});

/**
 * Merge class names, letting a caller's `className` win over a component's
 * defaults. Every component in `components/ui` accepts `className`, so this is
 * how a one-off override happens without a one-off style.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
