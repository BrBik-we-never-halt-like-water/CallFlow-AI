'use client';

import { Tooltip } from '@/components/ui/tooltip';
import { cn } from '@/lib/cn';

/**
 * The placeholders a system prompt can carry, as something you can see.
 *
 * `{name}` and `{note}` are filled in per contact when the call is assembled,
 * which is what makes one prompt work for a whole sheet instead of naming one
 * person. Nothing on the screen said so, so prompts got written with a real
 * name typed into them - correct for the contact they were tested against and
 * wrong for every other row in the run.
 *
 * Clicking one inserts it, because the point of showing them is that they get
 * used.
 */

const PLACEHOLDERS = [
  {
    token: '{name}',
    label: "The contact's name",
    detail:
      'From the name column of the sheet. Greet them with it rather than typing one person’s name into the prompt.',
  },
  {
    token: '{note}',
    label: 'Why you are calling them',
    detail:
      'From the note column - what this person got in touch about. Blank rows fall back to "no specific detail was recorded", so the sentence still reads.',
  },
] as const;

export function PromptPlaceholders({
  onInsert,
  disabled,
}: {
  onInsert: (token: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-small text-text-mute">Fills in per contact:</span>
      {PLACEHOLDERS.map((placeholder) => (
        <Tooltip
          key={placeholder.token}
          content={
            <span className="block max-w-64 text-left">
              <span className="font-medium">{placeholder.label}</span>
              <span className="mt-1 block text-text-dim">
                {placeholder.detail}
              </span>
            </span>
          }
          wrapTrigger={disabled}
        >
          <button
            type="button"
            onClick={() => onInsert(placeholder.token)}
            disabled={disabled}
            className={cn(
              'rounded-xs border border-rule bg-surface-sunken px-1.5 py-0.5',
              'font-mono text-small text-text-dim transition-colors duration-[--dur-micro]',
              'hover:border-rule-strong hover:text-text',
              'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-rule',
            )}
          >
            {placeholder.token}
          </button>
        </Tooltip>
      ))}
      <span className="text-small text-text-mute">
        Any other column in your sheet works too.
      </span>
    </div>
  );
}
