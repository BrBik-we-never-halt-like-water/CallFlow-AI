'use client';

import { DotsThreeIcon } from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { Lamp } from '@/components/brand/lamp';
import { Button } from '@/components/ui/button';
import { Tag } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Panel } from '@/components/ui/panel';
import { Tooltip } from '@/components/ui/tooltip';
import type { Campaign, Run } from '@/lib/api';
import { formatTimestamp } from '@/lib/format';
import { lampForRunStatus, type LampSpec } from '@/lib/lamp';

/** A campaign with no run yet reads as an "off" lamp, worded for the case
 * rather than reusing a per-call disposition label that wouldn't fit. */
const NOT_RUN: LampSpec = { state: 'off', label: 'Not run yet' };

/**
 * A campaign at a glance.
 *
 * Status is one lamp, not a strip: the card names the *campaign's* current
 * state (its most recent run, or that it has never run) rather than
 * itemising every past call the way the run detail page does - that level
 * of detail belongs one click away, not on every card in a grid.
 *
 * Editing is available for every campaign this org owns, in every state -
 * confirmed against the backend (`update_campaign` in
 * `apps/api/app/api/v1/routes/campaigns.py`), which only rejects built-ins
 * and has no run-state check at all. A run already in flight holds its own
 * snapshot of the campaign, resolved once at start (`CampaignRunner`,
 * `apps/api/app/services/campaign_runner.py` + `runs.py`), so editing the
 * template never touches a call that's already dialling - only runs
 * started afterward see the change. Built-in templates are the one real
 * exception, and it is enforced server-side: duplicate them instead.
 */
export function CampaignCard({
  campaign,
  lastRun,
  onDuplicate,
  onDelete,
  canWrite,
  canDelete,
  canStart,
}: {
  campaign: Campaign;
  lastRun?: Run;
  onDuplicate: (campaign: Campaign) => void;
  onDelete: (campaign: Campaign) => void;
  /** `campaigns:write` - duplicate, edit. */
  canWrite: boolean;
  /** `campaigns:delete`. */
  canDelete: boolean;
  /** `runs:start`. */
  canStart: boolean;
}) {
  const fieldNames = Object.keys(campaign.outcome_fields);
  const status = lastRun ? lampForRunStatus(lastRun.status) : NOT_RUN;
  const showMenu = canWrite || canDelete;

  return (
    <Panel interactive className="panel-glass flex flex-col gap-4 p-4">
      <div className="flex items-start justify-between gap-2">
        <h3 className="min-w-0 truncate text-h4 font-medium text-text">
          {campaign.name}
        </h3>

        {/* Built-in templates have no destructive actions, because they cannot be
            edited or deleted - offering the menu anyway would be a dead end.
            A viewer (neither canWrite nor canDelete) gets no menu at all - a
            viewer can view data and scroll, not act on it. */}
        {campaign.built_in ? (
          canWrite ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onDuplicate(campaign)}
            >
              Duplicate
            </Button>
          ) : null
        ) : showMenu ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                aria-label={`Actions for ${campaign.name}`}
                className="flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-sm text-text-mute transition-colors hover:bg-surface-hover hover:text-text"
              >
                <DotsThreeIcon aria-hidden weight="bold" className="size-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              {canWrite ? (
                <DropdownMenuItem onSelect={() => onDuplicate(campaign)}>
                  Duplicate
                </DropdownMenuItem>
              ) : null}
              {canDelete ? (
                <DropdownMenuItem
                  destructive
                  onSelect={() => onDelete(campaign)}
                >
                  Delete
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>

      <p className="line-clamp-2 text-small text-text-dim">
        {campaign.goal_preview}
      </p>

      <div className="flex flex-wrap items-center gap-1.5">
        {campaign.built_in ? (
          <Tooltip content="A starter template. Duplicate it to make changes.">
            <Tag>Template</Tag>
          </Tooltip>
        ) : (
          <Tag>Custom</Tag>
        )}
        {campaign.region ? <Tag>{campaign.region}</Tag> : null}
        {campaign.language ? <Tag>{campaign.language}</Tag> : null}
      </div>

      {fieldNames.length > 0 ? (
        <ul className="flex flex-wrap gap-1">
          {fieldNames.slice(0, 6).map((name) => (
            <li key={name}>
              <Tag>{name}</Tag>
            </li>
          ))}
          {fieldNames.length > 6 ? (
            <li>
              <Tag>+{fieldNames.length - 6}</Tag>
            </li>
          ) : null}
        </ul>
      ) : null}

      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-rule pt-3">
        <div className="flex min-w-0 items-center gap-2">
          <Lamp state={status.state} size="sm" pulse={status.pulse} />
          <span className="truncate text-small text-text-dim">
            {status.label}
          </span>
          {lastRun ? (
            <span className="font-mono text-data text-text-mute">
              · {formatTimestamp(lastRun.started_at)}
            </span>
          ) : null}
        </div>

        <div className="flex items-center gap-1.5">
          {!campaign.built_in && canWrite ? (
            <Button asChild variant="secondary" size="sm">
              <Link href={`/app/campaigns/${campaign.id}`}>Edit</Link>
            </Button>
          ) : null}
          {canStart ? (
            <Button asChild size="sm">
              <Link
                href={`/app/runs/new?campaign=${encodeURIComponent(campaign.id)}`}
              >
                Run
              </Link>
            </Button>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}
