'use client';

import { EyeIcon } from '@phosphor-icons/react/dist/ssr';
import { useState } from 'react';
import { cn } from '@/lib/cn';
import { formatE164, maskPhone } from '@/lib/format/phone';
import { Tooltip } from '@/components/ui/tooltip';
import { CopyButton } from '@/components/ui/code-block';

/**
 * A phone number on screen.
 *
 * Masked by default, everywhere, with no prop to turn that off. Revealing the
 * full number is a separate, permissioned action - masking is a product
 * guarantee we make to the people being called, not a display preference, so the
 * component makes the guarded path the easy one and gives the unguarded path no
 * API at all.
 */
export function MaskedPhone({
  phone,
  /**
   * Whether this viewer may reveal the full number. Comes from the caller's
   * permission check; absent or false, there is no reveal control at all.
   */
  canReveal = false,
  className,
}: {
  phone: string;
  canReveal?: boolean;
  className?: string;
}) {
  const [revealed, setRevealed] = useState(false);

  if (!phone) return <span className={cn('text-text-mute', className)}>-</span>;

  if (!canReveal) {
    return (
      <span
        className={cn(
          'font-mono text-data tabular-nums text-text-dim',
          className,
        )}
      >
        {maskPhone(phone)}
      </span>
    );
  }

  return (
    <span className={cn('inline-flex items-center gap-1.5', className)}>
      <span className="font-mono text-data tabular-nums text-text-dim">
        {revealed ? formatE164(phone) : maskPhone(phone)}
      </span>

      {revealed ? (
        <CopyButton value={phone} label="Copy" className="h-6" />
      ) : (
        <Tooltip content="Show the full number. Numbers are masked by default so they can't be read off a shared screen.">
          <button
            type="button"
            onClick={() => setRevealed(true)}
            aria-label="Reveal the full phone number"
            className="flex size-6 cursor-pointer items-center justify-center rounded-xs text-text-mute transition-colors hover:bg-surface-hover hover:text-text"
          >
            <EyeIcon aria-hidden className="size-3.5" />
          </button>
        </Tooltip>
      )}
    </span>
  );
}
