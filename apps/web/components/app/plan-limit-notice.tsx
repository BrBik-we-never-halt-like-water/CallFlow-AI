'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/cn';

/**
 * What a plan limit looks like *before* someone spends effort hitting it.
 *
 * The gate is the API's 402 and, below it, a database trigger. This is only the
 * courtesy of saying so first - so nothing here may be the reason an action is
 * allowed or refused, and every caller renders its normal action whenever the
 * limit is not known to be reached.
 *
 * Two shapes rather than a disabled button: a greyed-out control reads as "this
 * product is broken", while naming the plan's actual number and offering the
 * upgrade says what happened and what to do next (CLAUDE.md §5). Only an owner
 * holds `billing:write`, so anyone else gets the reason and no button rather than
 * one that would 403 on them.
 */
export function PlanLimitNotice({
  reason,
  canUpgrade,
  className,
}: {
  /** Names the plan and its number. Written by the caller, because only it knows
   *  which limit was reached. */
  reason: string;
  canUpgrade: boolean;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col items-start gap-2', className)}>
      <p className="measure text-small text-text-dim">
        {reason}
        {canUpgrade ? null : ' Ask an owner to upgrade.'}
      </p>
      {canUpgrade ? (
        <Button asChild size="sm">
          <Link href="/app/billing">Upgrade plan</Link>
        </Button>
      ) : null}
    </div>
  );
}
