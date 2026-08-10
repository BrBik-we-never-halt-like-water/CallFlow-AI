'use client';

import { cn } from '@/lib/cn';
import { Lamp } from '@/components/brand/lamp';
import { Button } from '@/components/ui/button';
import { Tag } from '@/components/ui/badge';
import { Panel } from '@/components/ui/panel';
import { useToast } from '@/components/ui/toast';
import { MaskedPhone } from './masked-phone';
import type { Outcome } from '@/lib/api';
import { useAppStore } from '@/lib/app-store';
import { formatAge, formatDuration } from '@/lib/format';

/**
 * One item in the escalation worklist.
 *
 * The reason is rendered as a chain read from typed fields - `Frustration detected →
 * Needs a person` - not as a sentence someone wrote. That is the product's guarantee
 * made visible: the operator can see which value drove the decision, so disagreeing
 * with it is a two-second check rather than an argument.
 */
export function EscalationCard({
  outcome,
  compact = false,
  onOpen,
}: {
  outcome: Outcome;
  compact?: boolean;
  onOpen?: () => void;
}) {
  const toast = useToast();
  const { resolveEscalation } = useAppStore();

  const chain = buildChain(outcome);

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
          <Lamp state="flare" size="md" label="Needs a person" />
          <div className="flex min-w-0 flex-col">
            <p className="truncate text-small font-medium text-text">
              {outcome.contact_name}
            </p>
            <MaskedPhone phone={outcome.phone_masked} />
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span className="font-mono text-data text-text-mute">
            {formatAge(outcome.created_at)}
          </span>
          {outcome.duration_seconds != null ? (
            <span className="font-mono text-data tabular-nums text-text-mute">
              {formatDuration(outcome.duration_seconds)}
            </span>
          ) : null}
        </div>
      </div>

      {/* The reasoning chain. Tag's own `whitespace-nowrap` is right for a short
          role/template label, but disposition_reason/sentiment_reason are full
          sentences - overridden back to wrapping here so a long one wraps
          inside the card instead of pushing past its edge. */}
      <ol className="flex flex-wrap items-start gap-1.5">
        {chain.map((step, i) => (
          <li key={i} className="flex min-w-0 max-w-full items-center gap-1.5">
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

      {!compact && outcome.transcript ? (
        <blockquote className="border-l-2 border-rule pl-3 text-small text-text-dim">
          {excerpt(outcome.transcript)}
        </blockquote>
      ) : null}

      {!compact && outcome.summary ? (
        <p className="text-small text-text-dim">{outcome.summary}</p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        {onOpen ? (
          <Button variant="secondary" size="sm" onClick={onOpen}>
            Open transcript
          </Button>
        ) : null}
        <Button
          variant="secondary"
          size="sm"
          onClick={() =>
            toast({
              tone: 'info',
              title: "Calling back isn't wired up yet",
              body: `Dial ${outcome.contact_name} from your own phone - the number is on this card.`,
            })
          }
        >
          Call back myself
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() =>
            toast({
              tone: 'info',
              title: "Assignment isn't wired up yet",
              body: 'Team assignment arrives with multi-seat accounts.',
            })
          }
        >
          Reassign
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            // Resolution isn't persisted anywhere yet (ISSUES.md #7) - `resolveEscalation`
            // only drops this outcome from the shared `escalations` list for the rest of
            // this session, which is what actually makes the worklist, the dashboard
            // panel, and the nav badge update immediately. The toast says exactly that
            // instead of implying it was saved, matching "Call back myself"/"Reassign"
            // above - and there is no "Resolved" state to show here afterward, since this
            // card unmounts the moment its outcome drops out of that list.
            resolveEscalation(outcome);
            toast({
              tone: 'info',
              title: 'Hidden for now, not saved',
              body: "This comes back if you reload - resolution tracking isn't wired up yet.",
            });
          }}
        >
          Mark resolved
        </Button>
      </div>
    </Wrapper>
  );
}

/**
 * Build the chain from typed fields only.
 *
 * Deliberately never parses `summary` prose. If the fields do not explain the
 * decision, the chain says the disposition and stops rather than inventing a reason.
 */
function buildChain(outcome: Outcome): string[] {
  const chain: string[] = [];

  if (outcome.sentiment && outcome.sentiment !== 'unknown') {
    chain.push(`Sentiment: ${outcome.sentiment}`);
  }
  if (outcome.disposition_reason) {
    chain.push(outcome.disposition_reason);
  }
  if (
    outcome.sentiment_reason &&
    outcome.sentiment_reason !== outcome.disposition_reason
  ) {
    chain.push(outcome.sentiment_reason);
  }
  chain.push('Needs a person');

  return chain;
}

/** The last few turns, which is where the trigger almost always is. */
function excerpt(transcript: string): string {
  const turns = transcript.split('\n').filter(Boolean);
  return turns.slice(-3).join('\n');
}
