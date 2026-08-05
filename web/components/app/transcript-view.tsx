"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import { Lamp } from "@/components/brand/lamp";
import { LampBadge, Tag } from "@/components/ui/badge";
import { CodeBlock } from "@/components/ui/code-block";
import { Eyebrow, Panel } from "@/components/ui/panel";
import { TabPanel, Tabs } from "@/components/ui/disclosure";
import { MaskedPhone } from "./masked-phone";
import type { Outcome } from "@/lib/api";
import { formatDuration, formatTimestamp, humaniseKey } from "@/lib/format";
import { lampForOutcome } from "@/lib/lamp";

interface Turn {
  speaker: "agent" | "contact";
  text: string;
  timestamp?: string;
}

/**
 * A call, in full: the conversation on the left, what came out of it on the right.
 *
 * The triage decision is rendered as a chain of typed fields rather than as prose. That
 * is the guarantee the whole product rests on — the reason a call was escalated is a
 * value you can check, not a sentence someone wrote — so it is displayed as a chain of
 * values, and never assembled by reading the summary text.
 */
export function TranscriptView({ outcome }: { outcome: Outcome }) {
  const [tab, setTab] = useState("conversation");
  const lamp = lampForOutcome(outcome);
  const turns = parseTranscript(outcome.transcript);

  return (
    <div className="flex flex-col">
      {/* ---- Header ------------------------------------------------------ */}
      <div className="flex flex-col gap-3 border-b border-rule p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <LampBadge state={lamp.state} pulse={lamp.pulse}>
            {lamp.label}
          </LampBadge>
          {outcome.dry_run ? <Tag>Dry run</Tag> : null}
          {outcome.status ? <Tag>{outcome.status}</Tag> : null}
        </div>

        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-4">
          <Meta label="Contact" value={outcome.contact_name} />
          <Meta label="Number" value={<MaskedPhone phone={outcome.phone_masked} />} />
          <Meta label="Duration" value={formatDuration(outcome.duration_seconds)} mono />
          <Meta label="Ended" value={formatTimestamp(outcome.created_at)} mono />
        </dl>
      </div>

      {/* ---- Mobile: tabs. Desktop: two columns. ------------------------- */}
      <div className="md:hidden">
        <Tabs
          value={tab}
          onValueChange={setTab}
          tabs={[
            { value: "conversation", label: "Conversation" },
            { value: "result", label: "Result" },
          ]}
          listClassName="px-4"
        >
          <TabPanel value="conversation" className="p-4">
            <Conversation turns={turns} outcome={outcome} />
          </TabPanel>
          <TabPanel value="result" className="p-4">
            <ResultColumn outcome={outcome} />
          </TabPanel>
        </Tabs>
      </div>

      <div className="hidden gap-0 md:grid md:grid-cols-[minmax(0,1fr)_minmax(0,340px)]">
        <div className="p-5">
          <Conversation turns={turns} outcome={outcome} />
        </div>
        <div className="border-l border-rule p-5">
          <ResultColumn outcome={outcome} />
        </div>
      </div>
    </div>
  );
}

function Meta({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="eyebrow text-text-mute">{label}</dt>
      <dd className={cn("text-small text-text", mono && "font-mono text-data tabular-nums")}>
        {value}
      </dd>
    </div>
  );
}

function Conversation({ turns, outcome }: { turns: Turn[]; outcome: Outcome }) {
  if (turns.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <Eyebrow>Conversation</Eyebrow>
        <p className="text-small text-text-dim">
          {outcome.dry_run
            ? "Dry runs don't produce a transcript — nothing was said, because nothing was dialled."
            : "No transcript was recorded for this call."}
        </p>
        {outcome.summary ? (
          <Panel sunken className="p-3">
            <p className="text-small text-text-dim">{outcome.summary}</p>
          </Panel>
        ) : null}
      </div>
    );
  }

  // The turn where sentiment shifted, marked with an inline lamp. Approximated as the
  // last contact turn on a negative call, which is where the trigger nearly always is.
  const shiftIndex =
    outcome.sentiment === "negative"
      ? turns.reduce((last, turn, i) => (turn.speaker === "contact" ? i : last), -1)
      : -1;

  return (
    <div className="flex flex-col gap-3">
      <Eyebrow>Conversation</Eyebrow>

      <ol className="flex flex-col gap-2">
        {turns.map((turn, i) => (
          <li key={i} className="flex gap-3">
            <span className="w-12 shrink-0 pt-2 text-right font-mono text-data text-text-mute">
              {turn.timestamp ?? ""}
            </span>

            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <div
                className={cn(
                  "rounded-md border border-rule p-3",
                  turn.speaker === "agent" ? "bg-surface-raised" : "bg-surface-sunken",
                )}
              >
                <p className="eyebrow mb-1.5 text-text-mute">
                  {turn.speaker === "agent" ? "CallFlow" : outcome.contact_name}
                </p>
                <p className="text-small text-text">{turn.text}</p>
              </div>

              {i === shiftIndex ? (
                <p className="flex items-center gap-1.5 text-small text-lamp-flare-text">
                  <Lamp state="flare" size="sm" />
                  Sentiment turned negative here
                </p>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ResultColumn({ outcome }: { outcome: Outcome }) {
  const extracted = outcome.extracted ?? {};
  const hasFields = Object.keys(extracted).length > 0;
  const chain = triageChain(outcome);

  return (
    <div className="flex flex-col gap-5">
      {/* ---- Extracted fields ------------------------------------------- */}
      <div className="flex flex-col gap-2">
        {hasFields ? (
          <CodeBlock
            label="Extracted"
            code={JSON.stringify(extracted, null, 2)}
            maxHeight="max-h-72"
          />
        ) : (
          <>
            <Eyebrow>Extracted</Eyebrow>
            <p className="text-small text-text-mute">No fields came back from this call.</p>
          </>
        )}
      </div>

      {/* ---- Field-by-field readout, so a value is scannable without JSON */}
      {hasFields ? (
        <dl className="flex flex-col gap-2">
          {Object.entries(extracted).map(([key, value]) => (
            <div key={key} className="flex items-baseline justify-between gap-3">
              <dt className="text-small text-text-mute">{humaniseKey(key)}</dt>
              <dd className="text-right font-mono text-data tabular-nums text-text">
                {formatValue(value)}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}

      {/* ---- Triage decision -------------------------------------------- */}
      <div className="flex flex-col gap-2 border-t border-rule pt-4">
        <Eyebrow>Why it went here</Eyebrow>
        <ol className="flex flex-col gap-1.5">
          {chain.map((step, i) => (
            <li key={i} className="flex items-start gap-2">
              <span aria-hidden className="pt-0.5 font-mono text-data text-text-mute">
                {i === chain.length - 1 ? "→" : "·"}
              </span>
              <span
                className={cn(
                  "text-small",
                  i === chain.length - 1 ? "font-medium text-text" : "text-text-dim",
                )}
              >
                {step}
              </span>
            </li>
          ))}
        </ol>
        <p className="text-small text-text-mute">
          Read from typed fields, not from the summary text.
        </p>
      </div>

      {outcome.error ? (
        <div className="flex flex-col gap-1 border-t border-rule pt-4">
          <Eyebrow>Error</Eyebrow>
          <p className="font-mono text-data text-lamp-flare-text">{outcome.error}</p>
        </div>
      ) : null}
    </div>
  );
}

/** Only typed fields. Never parses prose. */
function triageChain(outcome: Outcome): string[] {
  const chain: string[] = [];

  chain.push(`Status: ${outcome.status || "unknown"}`);
  if (outcome.sentiment && outcome.sentiment !== "unknown") {
    chain.push(`Sentiment: ${outcome.sentiment}`);
  }
  if (outcome.sentiment_reason) chain.push(outcome.sentiment_reason);
  if (outcome.disposition_reason) chain.push(outcome.disposition_reason);
  chain.push(lampForOutcome(outcome).label);

  return chain;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/**
 * Split a transcript into turns.
 *
 * The stored format is `Speaker: text` per line. Anything that does not match keeps its
 * text and is attributed to the contact, so an unexpected shape degrades to readable
 * rather than to empty.
 */
function parseTranscript(transcript: string | null): Turn[] {
  if (!transcript?.trim()) return [];

  return transcript
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^([\w .'-]{1,40}?)\s*:\s*(.+)$/);
      if (!match) return { speaker: "contact" as const, text: line };

      const [, rawSpeaker, text] = match;
      const speaker = /agent|assistant|callflow|bot|ai/i.test(rawSpeaker)
        ? ("agent" as const)
        : ("contact" as const);
      return { speaker, text };
    });
}
