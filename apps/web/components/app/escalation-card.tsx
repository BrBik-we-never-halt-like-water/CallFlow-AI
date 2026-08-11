'use client';

import { useState } from 'react';
import { cn } from '@/lib/cn';
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
import { useToast } from '@/components/ui/toast';
import { MaskedPhone } from './masked-phone';
import { api, type Campaign, type Escalation, type Member } from '@/lib/api';
import { useAppStore } from '@/lib/app-store';
import { formatAge, formatDuration, formatTimestamp } from '@/lib/format';
import { useSession } from '@/lib/hooks/use-session';

/**
 * One item in the escalation worklist.
 *
 * The reason is rendered as a chain read from typed fields - `Frustration detected →
 * Needs a person` - not as a sentence someone wrote. That is the product's guarantee
 * made visible: the operator can see which value drove the decision, so disagreeing
 * with it is a two-second check rather than an argument.
 */
export function EscalationCard({
  escalation,
  members,
  campaigns,
  compact = false,
  onOpen,
}: {
  escalation: Escalation;
  /** The org's team, for the "Reassign" picker - fetched once by the page,
   *  not per card, since every card on `/app/escalations` would otherwise
   *  duplicate the same `GET /api/v1/organisations/me/members` call. */
  members?: Member[];
  /** For the campaign-name tag - same "fetched once by the page" reasoning
   *  as `members`. */
  campaigns?: Campaign[];
  compact?: boolean;
  onOpen?: () => void;
}) {
  const toast = useToast();
  const { refreshEscalations } = useAppStore();
  const session = useSession();
  const canResolve =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('escalations:resolve');
  const canAssign =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('escalations:assign');
  const [resolving, setResolving] = useState(false);
  const [assigning, setAssigning] = useState(false);

  const chain = buildChain(escalation);
  const isOpen = escalation.escalation_status === 'open';
  const campaign = campaigns?.find((c) => c.id === escalation.campaign_id);

  async function resolve() {
    setResolving(true);
    try {
      await api.resolveEscalation(escalation.id);
      refreshEscalations();
    } catch (error) {
      toast({
        tone: 'error',
        title: "That escalation wasn't resolved",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setResolving(false);
    }
  }

  async function assignTo(member: Member) {
    setAssigning(true);
    try {
      await api.assignEscalation(escalation.id, member.user_id);
      refreshEscalations();
      toast({
        tone: 'success',
        title: 'Assigned',
        body: `${member.name?.trim() || member.email} will follow up.`,
      });
    } catch (error) {
      toast({
        tone: 'error',
        title: "That escalation wasn't assigned",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setAssigning(false);
    }
  }

  // The dashboard's condensed preview reads as a list - hairline dividers
  // between rows, like the rest of that column - not a stack of boxed cards.
  // The dedicated /app/escalations worklist keeps the full card: there, each
  // item is the thing being acted on, not a row in a summary.
  const Wrapper = compact ? 'div' : Panel;
  const wrapperClassName = cn(
    'flex flex-col gap-3',
    compact
      ? 'border-b border-rule pb-4 last:border-0 last:pb-0'
      : 'p-3 sm:p-4',
  );

  return (
    <Wrapper className={wrapperClassName}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          {/* `escalations/page.tsx` only ever passes an open escalation
              (resolved ones stay out of the worklist by design), so the
              `jade` branch is currently unreached - kept for whichever
              future view lists resolved items too, rather than assuming
              this card will only ever see one status. */}
          <Lamp
            state={isOpen ? 'flare' : 'jade'}
            size="md"
            label={isOpen ? 'Needs a person' : 'Resolved'}
          />
          <div className="flex min-w-0 flex-col gap-0.5">
            <div className="flex min-w-0 flex-wrap items-center gap-1.5">
              <p className="truncate text-small font-medium text-text">
                {escalation.contact_name}
              </p>
              {campaign ? (
                <Tag className="shrink-0">{campaign.name}</Tag>
              ) : null}
            </div>
            <MaskedPhone phone={escalation.phone_masked} />
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-0.5">
          {escalation.assigned_to_name ? (
            <Tag>Assigned · {escalation.assigned_to_name}</Tag>
          ) : null}
          <span
            className="font-mono text-data text-text-mute"
            title={formatTimestamp(escalation.created_at)}
          >
            {isOpen
              ? `Waiting ${formatAge(escalation.created_at)}`
              : formatAge(escalation.created_at)}
          </span>
          {escalation.duration_seconds != null ? (
            <span className="font-mono text-data tabular-nums text-text-mute">
              {formatDuration(escalation.duration_seconds)} call
            </span>
          ) : null}
        </div>
      </div>

      {/* The reasoning chain. No boxed background here - kept flush with
          "Last thing they said"/"Summary" below so all three read as one
          consistent rhythm of label-then-content, not one section singled
          out with heavier chrome. Tag's own `whitespace-nowrap` is right for
          a short role/template label, but disposition_reason/sentiment_reason
          are full sentences - overridden back to wrapping here so a long one
          wraps inside the card instead of pushing past its edge. */}
      <div className="flex flex-col gap-1.5">
        <p className="text-small font-bold text-text-mute">Why it&apos;s here</p>
        <ol className="flex flex-wrap items-start gap-x-1.5 gap-y-2">
          {chain.map((step, i) => (
            <li
              key={i}
              className="flex min-w-0 max-w-full items-center gap-1.5"
            >
              {i > 0 ? (
                <span
                  aria-hidden
                  className="shrink-0 font-mono text-data text-text-mute"
                >
                  →
                </span>
              ) : null}
              <Tag
                mono={false}
                className={cn(
                  'min-w-0 whitespace-normal break-words',
                  i === chain.length - 1 && 'text-lamp-flare-text',
                )}
              >
                {step}
              </Tag>
            </li>
          ))}
        </ol>
      </div>

      {!compact && escalation.transcript ? (
        <div className="flex flex-col gap-1">
          <p className="text-small font-bold text-text-mute">
            Last thing they said
          </p>
          <blockquote className="border-l-2 border-rule pl-3 text-small text-text-dim">
            {excerpt(escalation.transcript)}
          </blockquote>
        </div>
      ) : null}

      {!compact && escalation.summary ? (
        <div className="flex flex-col gap-1">
          <p className="text-small font-bold text-text-mute">Summary</p>
          <p className="text-small text-text-dim">{escalation.summary}</p>
        </div>
      ) : null}

      {isOpen ? (
        <div className="flex flex-wrap items-center gap-2">
          {onOpen ? (
            <Button variant="secondary" size="sm" onClick={onOpen}>
              Open transcript
            </Button>
          ) : null}
          {canResolve ? (
            <>
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  toast({
                    tone: 'info',
                    title: "Calling back isn't wired up yet",
                    body: `Dial ${escalation.contact_name} from your own phone - the number is on this card.`,
                  })
                }
              >
                Call back myself
              </Button>
              {canAssign && members && members.length > 0 ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="sm" loading={assigning}>
                      Reassign
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    {members.map((member) => (
                      <DropdownMenuItem
                        key={member.user_id}
                        onSelect={() => void assignTo(member)}
                      >
                        {member.name?.trim() || member.email}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : null}
              <Button
                variant="ghost"
                size="sm"
                loading={resolving}
                onClick={() => void resolve()}
              >
                Mark resolved
              </Button>
            </>
          ) : null}
        </div>
      ) : onOpen ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" size="sm" onClick={onOpen}>
            Open transcript
          </Button>
        </div>
      ) : null}
    </Wrapper>
  );
}

/**
 * Build the chain from typed fields only.
 *
 * Deliberately never parses `summary` prose. If the fields do not explain the
 * decision, the chain says the disposition and stops rather than inventing a reason.
 */
function buildChain(escalation: Escalation): string[] {
  const chain: string[] = [];

  if (escalation.sentiment && escalation.sentiment !== 'unknown') {
    chain.push(`Sentiment: ${escalation.sentiment}`);
  }
  if (escalation.disposition_reason) {
    chain.push(escalation.disposition_reason);
  }
  if (
    escalation.sentiment_reason &&
    escalation.sentiment_reason !== escalation.disposition_reason
  ) {
    chain.push(escalation.sentiment_reason);
  }
  chain.push(
    escalation.escalation_status === 'open' ? 'Needs a person' : 'Resolved',
  );

  return chain;
}

/** The last few turns, which is where the trigger almost always is. */
function excerpt(transcript: string): string {
  const turns = transcript.split('\n').filter(Boolean);
  return turns.slice(-3).join('\n');
}
