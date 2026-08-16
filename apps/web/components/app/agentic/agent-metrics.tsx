'use client';

import { RollingNumber } from '@/components/ui/rolling-number';
import { cn } from '@/lib/cn';
import type { ProviderCatalogEntry } from '@/lib/api';
import { ProviderIcon } from './provider-icons';

/**
 * What the current transcriber/model/voice combination costs and how long it
 * takes, recomputed as the wheels move.
 *
 * The three legs run in sequence on every turn of a call - the caller stops
 * speaking, transcription finishes, the model answers, the voice speaks - so
 * summing their latencies is the round-trip delay the caller actually waits
 * through, and each leg's share of the bar is its share of that wait.
 *
 * Colour comes from the `--leg-*` spectrum (globals.css), never the lamps:
 * this is which part of the pipeline, not how a call went.
 */

/**
 * A minute of conversation, in tokens. The agent speaking at a natural pace
 * produces roughly 200 tokens a minute, and each request re-sends the system
 * prompt plus the transcript so far, which settles around 1,500 input tokens
 * once a call is a few turns in.
 *
 * This is an assumption about conversations, not a vendor quote - the model
 * cost below is labelled an estimate because of it.
 */
const TOKENS_PER_MINUTE = { input: 1_500, output: 200 };

export function llmCostPerMinute(
  entry: ProviderCatalogEntry | null,
): number | null {
  if (!entry) return null;
  const { cost_per_1m_input_usd: input, cost_per_1m_output_usd: output } =
    entry;
  if (input === null || output === null) return null;
  return (
    (input * TOKENS_PER_MINUTE.input + output * TOKENS_PER_MINUTE.output) /
    1_000_000
  );
}

function formatCost(usd: number): string {
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(3)}`;
}

function formatLatency(ms: number): string {
  return ms >= 1_000 ? `${(ms / 1_000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

interface Leg {
  key: string;
  label: string;
  color: string;
  entry: ProviderCatalogEntry | null;
  /** TTS only - the named voice, appended to the provider name. */
  detail?: string | null;
  latencyMs: number | null;
  costPerMin: number | null;
}

export function AgentMetrics({
  stt,
  llm,
  tts,
  voiceId,
}: {
  stt: ProviderCatalogEntry | null;
  llm: ProviderCatalogEntry | null;
  tts: ProviderCatalogEntry | null;
  voiceId?: string | null;
}) {
  const legs: Leg[] = [
    {
      key: 'stt',
      label: 'Transcriber',
      color: 'var(--leg-stt)',
      entry: stt,
      latencyMs: stt?.latency_ms ?? null,
      costPerMin: stt?.cost_per_min_usd ?? null,
    },
    {
      key: 'llm',
      label: 'Model',
      color: 'var(--leg-llm)',
      entry: llm,
      latencyMs: llm?.latency_ms ?? null,
      costPerMin: llmCostPerMinute(llm),
    },
    {
      key: 'tts',
      label: 'Voice',
      color: 'var(--leg-tts)',
      entry: tts,
      detail: voiceId ?? null,
      latencyMs: tts?.latency_ms ?? null,
      costPerMin: tts?.cost_per_min_usd ?? null,
    },
  ];

  // A leg with nothing picked yet contributes nothing rather than blocking the
  // whole readout - a half-built agent should still show what it has.
  const totalLatency = legs.reduce((sum, leg) => sum + (leg.latencyMs ?? 0), 0);
  const totalCost = legs.reduce((sum, leg) => sum + (leg.costPerMin ?? 0), 0);

  return (
    <div className="flex flex-col gap-6 rounded-2xl bg-surface-raised p-5 ring-1 ring-rule">
      <div className="grid gap-x-10 gap-y-5 sm:grid-cols-2">
        <Headline
          label="Cost"
          value={totalCost > 0 ? formatCost(totalCost) : '-'}
          unit="/min"
          note="estimated"
          legs={legs}
          weight={(leg) => leg.costPerMin}
        />
        <Headline
          label="Response time"
          value={totalLatency > 0 ? formatLatency(totalLatency) : '-'}
          unit="per turn"
          legs={legs}
          weight={(leg) => leg.latencyMs}
        />
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        {legs.map((leg) => (
          <LegCard key={leg.key} leg={leg} />
        ))}
      </div>
    </div>
  );
}

function Headline({
  label,
  value,
  unit,
  note,
  legs,
  weight,
}: {
  label: string;
  value: string;
  unit: string;
  note?: string;
  legs: Leg[];
  weight: (leg: Leg) => number | null;
}) {
  const total = legs.reduce((sum, leg) => sum + (weight(leg) ?? 0), 0);

  return (
    <div className="flex flex-col gap-2">
      <span className="text-[0.6875rem] uppercase tracking-[0.09em] text-text-mute">
        {label}
      </span>

      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <RollingNumber
          value={value}
          className="font-mono text-h2 font-medium text-text"
        />
        <span className="text-small text-text-mute">{unit}</span>
        {note ? (
          <span className="text-[0.6875rem] text-text-mute">{note}</span>
        ) : null}
      </div>

      <div
        aria-hidden
        className="flex h-1.5 gap-0.5 overflow-hidden rounded-full bg-surface-sunken"
      >
        {legs.map((leg) => {
          const share = weight(leg);
          if (share === null || total === 0) return null;
          return (
            <span
              key={leg.key}
              className="h-full rounded-full transition-[width] duration-(--dur-base) ease-(--ease-out)"
              style={{
                width: `${(share / total) * 100}%`,
                background: leg.color,
              }}
            />
          );
        })}
      </div>
    </div>
  );
}

/**
 * One leg's card: which provider is selected, and the two numbers that decide
 * whether it is the right one. Empty legs still render, so the row keeps its
 * shape while an agent is half-built.
 */
function LegCard({ leg }: { leg: Leg }) {
  const { entry } = leg;

  return (
    <div className="flex min-w-0 flex-col gap-3 rounded-xl bg-surface-sunken p-3.5">
      <span className="flex items-center gap-2">
        <span
          aria-hidden
          className="size-1.5 shrink-0 rounded-full"
          style={{ background: leg.color }}
        />
        <span className="text-[0.6875rem] uppercase tracking-[0.09em] text-text-mute">
          {leg.label}
        </span>
      </span>

      {entry ? (
        <span className="flex min-w-0 items-center gap-2">
          <ProviderIcon id={entry.id} className="size-4" />
          <span className="min-w-0 truncate text-small font-medium text-text">
            {leg.detail ? `${entry.name} · ${leg.detail}` : entry.name}
          </span>
        </span>
      ) : (
        <span className="text-small text-text-mute">Not set</span>
      )}

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
        <Stat label="Latency" value={leg.latencyMs} format={formatLatency} />
        <Stat
          label="Cost"
          value={leg.costPerMin}
          format={(v) => `${formatCost(v)}/min`}
        />
      </dl>
    </div>
  );
}

function Stat({
  label,
  value,
  format,
}: {
  label: string;
  value: number | null;
  format: (value: number) => string;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <dt className="text-[0.625rem] uppercase tracking-[0.07em] text-text-mute">
        {label}
      </dt>
      <dd
        className={cn(
          'truncate font-mono text-small tabular-nums',
          value === null ? 'text-text-mute' : 'text-text-dim',
        )}
      >
        {value === null ? '-' : <RollingNumber value={format(value)} />}
      </dd>
    </div>
  );
}
