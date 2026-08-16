'use client';

import { cn } from '@/lib/cn';
import { primeTick } from '@/lib/sound/tick';
import type { ProviderCatalog, ProviderCatalogEntry } from '@/lib/api';
import { llmCostPerMinute } from './agent-metrics';

/**
 * One-tap starting points for the three wheels.
 *
 * Each preset is a rule over the catalog, not a hard-coded list of provider
 * ids: pick the cheapest, pick the fastest, pick the best. That way a preset
 * cannot silently name a provider the catalog no longer carries, and adding a
 * model to `catalog.py` puts it in contention for every preset automatically.
 */

type Pick = {
  stt: ProviderCatalogEntry | null;
  llm: ProviderCatalogEntry | null;
  tts: ProviderCatalogEntry | null;
};

function cheapest(entries: ProviderCatalogEntry[], isLlm: boolean) {
  const cost = (e: ProviderCatalogEntry) =>
    isLlm ? llmCostPerMinute(e) : e.cost_per_min_usd;
  return (
    entries
      .filter((e) => cost(e) !== null)
      .sort((a, b) => (cost(a) as number) - (cost(b) as number))[0] ?? null
  );
}

function fastest(entries: ProviderCatalogEntry[]) {
  return (
    entries
      .filter((e) => e.latency_ms !== null)
      .sort((a, b) => (a.latency_ms as number) - (b.latency_ms as number))[0] ??
    null
  );
}

/** Costliest as a stand-in for most capable. Within one category, price tracks
 *  capability closely enough for a starting point, and unlike a hand-kept
 *  ranking it cannot go stale against the catalog. */
function strongest(entries: ProviderCatalogEntry[], isLlm: boolean) {
  const cost = (e: ProviderCatalogEntry) =>
    isLlm ? llmCostPerMinute(e) : e.cost_per_min_usd;
  return (
    entries
      .filter((e) => cost(e) !== null)
      .sort((a, b) => (cost(b) as number) - (cost(a) as number))[0] ?? null
  );
}

const PRESETS: {
  id: string;
  label: string;
  describe: string;
  resolve: (catalog: ProviderCatalog) => Pick;
}[] = [
  {
    id: 'balanced',
    label: 'Balanced',
    describe: 'A quick model with accurate transcription',
    resolve: (c) => ({
      stt: fastest(c.stt),
      llm: cheapest(c.llm, true),
      tts: fastest(c.tts),
    }),
  },
  {
    id: 'capable',
    label: 'Most capable',
    describe: 'The strongest model on the list',
    resolve: (c) => ({
      stt: fastest(c.stt),
      llm: strongest(c.llm, true),
      tts: strongest(c.tts, false),
    }),
  },
  {
    id: 'fastest',
    label: 'Fastest',
    describe: 'Lowest round trip on every turn',
    resolve: (c) => ({
      stt: fastest(c.stt),
      llm: fastest(c.llm),
      tts: fastest(c.tts),
    }),
  },
  {
    id: 'cheapest',
    label: 'Lowest cost',
    describe: 'Cheapest combination per minute',
    resolve: (c) => ({
      stt: cheapest(c.stt, false),
      llm: cheapest(c.llm, true),
      tts: cheapest(c.tts, false),
    }),
  },
];

export function AgentPresets({
  catalog,
  sttId,
  llmId,
  ttsId,
  onApply,
  disabled,
}: {
  catalog: ProviderCatalog;
  sttId: string | null;
  llmId: string | null;
  ttsId: string | null;
  onApply: (pick: Pick) => void;
  disabled?: boolean;
}) {
  const resolved = PRESETS.map((preset) => ({
    ...preset,
    pick: preset.resolve(catalog),
  }));

  const activeId = resolved.find(
    (p) =>
      p.pick.stt?.id === sttId &&
      p.pick.llm?.id === llmId &&
      p.pick.tts?.id === ttsId,
  )?.id;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="mr-1 text-[0.6875rem] uppercase tracking-[0.09em] text-text-mute">
        Presets
      </span>

      {resolved.map((preset) => {
        const isActive = preset.id === activeId;
        return (
          <button
            key={preset.id}
            type="button"
            disabled={disabled}
            aria-pressed={isActive}
            title={preset.describe}
            // Primed on press: the wheels are about to tick, and an
            // AudioContext resumed lazily by the first tick makes that one
            // land late. This is also a real user gesture, which is the only
            // moment a browser allows the resume.
            onClick={() => {
              primeTick();
              onApply(preset.pick);
            }}
            className={cn(
              'rounded-full px-3 py-1.5 text-small transition-colors duration-(--dur-micro)',
              'disabled:cursor-not-allowed disabled:opacity-45',
              isActive
                ? 'bg-primary text-primary-on'
                : 'bg-surface-sunken text-text-dim hover:text-text',
            )}
          >
            {preset.label}
          </button>
        );
      })}
    </div>
  );
}
