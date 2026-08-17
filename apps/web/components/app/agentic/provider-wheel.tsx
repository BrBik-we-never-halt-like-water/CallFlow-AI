'use client';

import {
  WheelPicker,
  WheelRow,
  type WheelPickerItem,
} from '@/components/ui/wheel-picker';
import { cn } from '@/lib/cn';
import type { ProviderCatalogEntry } from '@/lib/api';
import { ProviderIcon } from './provider-icons';
import { VoicePreviewButton } from './voice-preview-button';

function voiceLabel(id: string): string {
  return id.charAt(0).toUpperCase() + id.slice(1);
}

/**
 * One leg of the agent - transcriber, model, or voice - as a scroll wheel with
 * the centred option's details beneath it.
 *
 * The wheel replaces the grid of provider cards this used to be: every model
 * as a card carrying three sentences of cost, latency, and quality prose made
 * the page a wall of text to read rather than a set of choices to make. Only
 * the centred option's details are on screen now, and the numbers that compare
 * across options moved up to `AgentMetrics`.
 *
 * Vendor API keys are deliberately absent: calls run on the platform's own
 * credentials for now, and bring-your-own keys belongs on the Integrations
 * screens rather than inline on every wheel.
 */
export function ProviderWheel({
  title,
  entries,
  selectedId,
  onSelect,
  category,
  selectedVoiceId,
  onVoiceIdChange,
  disabled,
  animateChanges,
}: {
  title: string;
  entries: ProviderCatalogEntry[];
  selectedId: string | null;
  onSelect: (entry: ProviderCatalogEntry) => void;
  category: 'stt' | 'tts' | 'llm';
  selectedVoiceId?: string | null;
  onVoiceIdChange?: (entry: ProviderCatalogEntry, voiceId: string) => void;
  disabled?: boolean;
  /** Spin audibly to a value set from outside - see `WheelPicker`. */
  animateChanges?: boolean;
}) {
  const selected = entries.find((entry) => entry.id === selectedId) ?? null;

  // No `sublabel`: the vendor is already the icon, and printing "Deepgram"
  // under "Deepgram Nova-3" spent a second line saying what the mark says.
  const items: WheelPickerItem[] = entries.map((entry) => ({
    value: entry.id,
    label: entry.name,
    hint: entry.quality_note,
    icon: <ProviderIcon id={entry.id} className="size-5" />,
  }));

  const voiceOptions = selected?.voice_options ?? [];
  const activeVoiceId = selectedVoiceId ?? voiceOptions[0] ?? null;

  return (
    <section className="flex h-full min-w-0 flex-col gap-4">
      {/* The preview sits with the heading as an icon, not as a button in a
          card below - it is one affordance, and it was the only thing keeping
          that card alive once the quality notes moved to hover. */}
      <div className="flex items-center justify-center gap-1.5">
        <h2 className="text-center font-display text-h4 leading-none text-text">
          {title}
        </h2>
        {category === 'tts' && selected?.preview_available ? (
          <VoicePreviewButton
            provider={selected.id}
            kind="tts"
            voiceId={activeVoiceId ?? undefined}
            iconOnly
          />
        ) : null}
      </div>

      <WheelRow className="grid min-w-0 gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
        <WheelPicker
          items={items}
          value={selectedId}
          onChange={(id) => {
            const entry = entries.find((e) => e.id === id);
            if (entry) onSelect(entry);
          }}
          ariaLabel={title}
          className={disabled ? 'pointer-events-none opacity-45' : undefined}
          animateChanges={animateChanges}
        />

        {/* The voice wheel only exists once a provider with named voices is
            centred, and re-populates from that provider - the linked-column
            behaviour of an iOS date picker. */}
        {category === 'tts' && voiceOptions.length > 0 ? (
          <WheelPicker
            items={voiceOptions.map((id) => ({
              value: id,
              label: voiceLabel(id),
            }))}
            value={activeVoiceId}
            onChange={(id) => selected && onVoiceIdChange?.(selected, id)}
            ariaLabel={`Voice for ${selected?.name ?? title}`}
            className={cn(
              'w-full sm:w-28',
              disabled && 'pointer-events-none opacity-45',
            )}
            animateChanges={animateChanges}
          />
        ) : null}
      </WheelRow>

    </section>
  );
}
