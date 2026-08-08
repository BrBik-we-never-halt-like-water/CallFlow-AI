"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import { Lamp } from "@/components/brand/lamp";
import { Button } from "@/components/ui/button";
import { Tag } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import { useToast } from "@/components/ui/toast";
import { MaskedPhone } from "./masked-phone";
import type { Outcome } from "@/lib/api";
import { formatAge, formatDuration } from "@/lib/format";

/**
 * One item in the escalation worklist.
 *
 * The reason is rendered as a chain read from typed fields   `Frustration detected →
 * Needs a person`   not as a sentence someone wrote. That is the product's guarantee
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
  const [resolved, setResolved] = useState(false);

  const chain = buildChain(outcome);

  return (
    <Panel
      className={cn(
        "flex flex-col gap-3 p-3 sm:p-4",
        // A flare left border, because this is call state and it is the one thing on
        // the page that needs action.
        "border-l-2 border-l-[var(--lamp-flare)]",
        resolved && "opacity-50",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Lamp state={resolved ? "jade" : "flare"} size="md" label={resolved ? "Resolved" : "Needs a person"} />
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

      {/* The reasoning chain. */}
      <ol className="flex flex-wrap items-center gap-1.5">
        {chain.map((step, i) => (
          <li key={i} className="flex items-center gap-1.5">
            {i > 0 ? (
              <span aria-hidden className="font-mono text-data text-text-mute">
                →
              </span>
            ) : null}
            <Tag mono={false} className={i === chain.length - 1 ? "text-lamp-flare-text" : undefined}>
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
          disabled={resolved}
          onClick={() =>
            toast({
              tone: "info",
              title: "Calling back isn't wired up yet",
              body: `Dial ${outcome.contact_name} from your own phone   the number is on this card.`,
            })
          }
        >
          Call back myself
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={resolved}
          onClick={() =>
            toast({
              tone: "info",
              title: "Assignment isn't wired up yet",
              body: "Team assignment arrives with multi-seat accounts.",
            })
          }
        >
          Reassign
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={resolved}
          onClick={() => {
            setResolved(true);
            // The verb matches the button, so the confirmation is unmistakably about
            // the thing that was just clicked.
            toast({ tone: "success", title: "Marked resolved" });
          }}
        >
          {resolved ? "Resolved" : "Mark resolved"}
        </Button>
      </div>
    </Panel>
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

  if (outcome.sentiment && outcome.sentiment !== "unknown") {
    chain.push(`Sentiment: ${outcome.sentiment}`);
  }
  if (outcome.disposition_reason) {
    chain.push(outcome.disposition_reason);
  }
  if (outcome.sentiment_reason && outcome.sentiment_reason !== outcome.disposition_reason) {
    chain.push(outcome.sentiment_reason);
  }
  chain.push("Needs a person");

  return chain;
}

/** The last few turns, which is where the trigger almost always is. */
function excerpt(transcript: string): string {
  const turns = transcript.split("\n").filter(Boolean);
  return turns.slice(-3).join("\n");
}
