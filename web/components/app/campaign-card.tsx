"use client";

import { DotsThreeIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { LampStrip } from "@/components/brand/lamp-strip";
import { Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Panel } from "@/components/ui/panel";
import { Tooltip } from "@/components/ui/tooltip";
import type { Campaign, Run } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { lampForOutcome, type LampSpec } from "@/lib/lamp";

/**
 * A campaign at a glance.
 *
 * The mini lamp strip shows how the last run of this campaign actually went, which is
 * the most useful thing a card can say about a campaign   a name and a goal tell you
 * what it intends, and only the strip tells you whether it works.
 */
export function CampaignCard({
  campaign,
  lastRun,
  onDuplicate,
  onDelete,
}: {
  campaign: Campaign;
  lastRun?: Run;
  onDuplicate: (campaign: Campaign) => void;
  onDelete: (campaign: Campaign) => void;
}) {
  const fieldNames = Object.keys(campaign.outcome_fields);
  const lamps: LampSpec[] = lastRun ? lastRun.outcomes.map(lampForOutcome) : [];

  return (
    <Panel className="flex flex-col gap-4 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-h4 font-medium text-text">{campaign.name}</h3>
            {campaign.built_in ? (
              <Tooltip content="A starter template. Duplicate it to make changes.">
                <Tag>Template</Tag>
              </Tooltip>
            ) : null}
          </div>
          <p className="line-clamp-2 text-small text-text-dim">{campaign.goal_preview}</p>
        </div>

        {/* Built-in templates have no destructive actions, because they cannot be
            edited or deleted   offering the menu anyway would be a dead end. */}
        {campaign.built_in ? (
          <Button variant="ghost" size="sm" onClick={() => onDuplicate(campaign)}>
            Duplicate
          </Button>
        ) : (
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
              <DropdownMenuItem onSelect={() => onDuplicate(campaign)}>
                Duplicate
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Link href={`/app/campaigns/${campaign.id}`} className="flex-1">
                  Edit
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem destructive onSelect={() => onDelete(campaign)}>
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
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

      <div className="mt-auto flex flex-col gap-3 border-t border-rule pt-3">
        {lamps.length > 0 ? (
          <LampStrip lamps={lamps.slice(0, 20)} size="sm" />
        ) : (
          <p className="font-mono text-data text-text-mute">Not run yet</p>
        )}

        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-data text-text-mute">
            {lastRun ? formatTimestamp(lastRun.started_at) : " "}
          </span>
          <div className="flex items-center gap-1.5">
            {campaign.region ? <Tag>{campaign.region}</Tag> : null}
            {campaign.language ? <Tag>{campaign.language}</Tag> : null}
            <Button asChild size="sm">
              <Link href={`/app/runs/new?campaign=${encodeURIComponent(campaign.id)}`}>
                Run
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </Panel>
  );
}
