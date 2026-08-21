'use client';

import Link from 'next/link';
import { UserPlusIcon } from '@phosphor-icons/react/dist/ssr';
import { Panel, PanelBody } from './panel';
import { DottedWave } from './dotted-wave';
import type { Outcome, TeamPerformance } from '@/lib/api';
import { cn } from '@/lib/cn';

/**
 * Credits: how many calls this organisation has actually been charged for.
 *
 * **What counts.** A call is billable once it reached a real conclusion -
 * `auto_closed` (the agent got what it needed) or `escalated` (it needs a
 * person). Nothing else does: `in_flight` has not finished yet and would
 * make the number jump around mid-run, and `unreachable`/`retry`/`skipped`
 * never held a conversation. A failed dial is not something to charge for.
 *
 * Counted from dispositions rather than the raw provider status, because
 * `triage.py` is what decides how a call actually resolved - status is the
 * vendor's word for what the phone did, disposition is the product's word
 * for what happened.
 *
 * **Why "of ∞".** There is no plan ceiling to divide by yet. Showing a
 * denominator we do not have would be inventing a limit; `∞` says plainly
 * that nothing is capped, and the shape stays right for when pricing lands
 * and a real number replaces it.
 */

/** The dispositions a call is charged for. */
const BILLABLE = new Set(['auto_closed', 'escalated']);

function billableCalls(outcomes: Outcome[] | null): number {
  return (outcomes ?? []).filter((row) => BILLABLE.has(row.disposition)).length;
}

export function CreditsCard({
  members,
  outcomes,
  loading,
  className,
}: {
  members: TeamPerformance[] | null;
  /** Every outcome the dashboard can see - the billable count comes from here. */
  outcomes: Outcome[] | null;
  loading: boolean;
  className?: string;
}) {
  const used = billableCalls(outcomes);

  // A teammate is worth a row once they have run anything at all; an
  // allocation of zero is the norm while pricing is unbuilt, so filtering on
  // it would empty the list entirely.
  const team = (members ?? []).filter(
    (member) => member.total_calls > 0 || member.credits_used_today > 0,
  );

  return (
    <Panel className={cn('dash-branded dash-wave-host', className)}>
      <DottedWave rows={7} alpha={0.34} />
      {/* Label top-left, figure top-right - the KPI cards' own shape rather
          than a panel heading, so the whole first row reads as one family.
          `PanelHeader`'s 13px semibold title would have made this card the
          only one with a different-looking name. */}
      <div className="flex shrink-0 items-start justify-between gap-2 px-3.5 pb-2 pt-3">
        <p
          className="min-w-0 flex-1 truncate text-[0.5rem] font-medium uppercase tracking-[0.05em]"
          style={{ color: 'var(--dash-figure-label)' }}
        >
          Credits
        </p>

        <span className="flex shrink-0 items-baseline gap-1">
          <span
            className="dash-num text-[2.25rem] font-semibold leading-none"
            style={{ color: 'var(--dash-figure)' }}
          >
            {loading ? '—' : used.toLocaleString()}
          </span>
          <span
            className="text-[0.75rem] leading-none"
            style={{ color: 'var(--dash-text-mute)' }}
          >
            / ∞
          </span>
        </span>
      </div>

      <div
        className="shrink-0 px-3.5 pb-1 text-[0.5rem] font-medium uppercase tracking-[0.05em]"
        style={{ color: 'var(--dash-text-mute)' }}
      >
        Team usage
      </div>

      <PanelBody label="Credit usage by teammate" className="px-3.5 pb-3">
        {loading ? null : team.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center">
            <p
              className="text-[0.75rem]"
              style={{ color: 'var(--dash-text-dim)' }}
            >
              No calls yet.
            </p>
            {/* An empty team panel is the moment to offer the thing that
                fills it, rather than only reporting that it is empty. */}
            <Link
              href="/app/settings?tab=team"
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[0.6875rem] font-medium transition-colors"
              style={{
                background: 'var(--dash-brand-soft)',
                color: 'var(--dash-brand-ink)',
              }}
            >
              <UserPlusIcon aria-hidden className="size-3" />
              Invite a teammate
            </Link>
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {team.map((member) => (
              <li
                key={member.user_id ?? member.name ?? 'unassigned'}
                className="flex items-center justify-between gap-3"
              >
                <span
                  className="min-w-0 truncate text-[0.75rem]"
                  style={{ color: 'var(--dash-text-dim)' }}
                >
                  {member.name ?? 'Unassigned'}
                </span>
                <span
                  className="dash-num shrink-0 text-[0.8125rem] font-semibold"
                  style={{ color: 'var(--dash-text)' }}
                >
                  {member.calls_closed.toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </PanelBody>
    </Panel>
  );
}
