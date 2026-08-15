'use client';

import { useState } from 'react';
import { Tag } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { cn } from '@/lib/cn';
import { usePermission } from '@/lib/hooks/use-permission';
import {
  type AiProvider,
  type AiProviderCredential,
  type ProviderCatalogEntry,
} from '@/lib/api';
import { ConnectAiKeyDialog } from './connect-ai-key-dialog';
import { VoicePreviewButton } from './voice-preview-button';

const VENDOR_DISPLAY_NAME: Partial<Record<AiProvider, string>> = {
  sarvam: 'Sarvam AI',
  deepgram: 'Deepgram',
  elevenlabs: 'ElevenLabs',
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
};

function voiceOptionLabel(id: string): string {
  return id.charAt(0).toUpperCase() + id.slice(1);
}

/**
 * A Vapi-style grid of provider cards for one leg of the agent builder - STT,
 * TTS, or the OpenRouter model list. Selection, connection state, and (for
 * TTS) the named-voice picker all live here, so `agent-editor.tsx` only hands
 * over a catalog slice and reads back a selection.
 */
export function ProviderPicker({
  entries,
  selectedId,
  onSelect,
  connectProviderId,
  credentials,
  onCredentialsChanged,
  category,
  selectedVoiceId,
  onVoiceIdChange,
}: {
  entries: ProviderCatalogEntry[];
  selectedId: string | null;
  onSelect: (entry: ProviderCatalogEntry) => void;
  /** Override: use THIS as the vendor id for connect/preview instead of each
   *  entry's own id - needed for the LLM step, whose entries are per-model,
   *  not per-vendor (see agent-editor.tsx / the LLM ProviderPicker usage). */
  connectProviderId?: AiProvider;
  credentials: AiProviderCredential[];
  onCredentialsChanged: () => void;
  category: 'stt' | 'tts' | 'llm';
  /** The agent's current `voice_id`, if any - only meaningful for `category === 'tts'`. */
  selectedVoiceId?: string | null;
  onVoiceIdChange?: (entry: ProviderCatalogEntry, voiceId: string) => void;
}) {
  // Connecting/updating a key is INTEGRATIONS_WRITE, a narrower, admin-only
  // permission than AGENTS_WRITE (the permission that gets someone into this
  // editor at all) - an operator can build an agent's shape but not hand it
  // a vendor key, so the connect action itself has to check separately.
  const canManageIntegrations = usePermission('integrations:write');
  const [editingProvider, setEditingProvider] = useState<AiProvider | null>(
    null,
  );

  const editingCredential = editingProvider
    ? (credentials.find((c) => c.provider === editingProvider) ?? null)
    : null;
  const editingVendorName = editingProvider
    ? (VENDOR_DISPLAY_NAME[editingProvider] ?? editingProvider)
    : '';

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2">
        {entries.map((entry) => {
          const vendorId = connectProviderId ?? (entry.id as AiProvider);
          const isSelected = entry.id === selectedId;
          const hasCredential = credentials.some(
            (c) => c.provider === vendorId,
          );
          // `entry.connected` comes from the catalog endpoint, readable by
          // every role via agents:read - the accurate fallback for someone
          // who can build agents but can't read integrations (the
          // AGENTS_* / INTEGRATIONS_* split in app/auth/permissions.py), so
          // "connected" never silently reads as "not connected" just because
          // this session couldn't fetch the credential list.
          const isConnected = entry.connected || hasCredential;

          const voiceOptions = entry.voice_options;
          const hasVoices = voiceOptions.length > 0;
          const displayedVoiceId = hasVoices
            ? isSelected && selectedVoiceId
              ? selectedVoiceId
              : voiceOptions[0]
            : undefined;

          function selectThis() {
            onSelect(entry);
            if (hasVoices && displayedVoiceId) {
              onVoiceIdChange?.(entry, displayedVoiceId);
            }
          }

          return (
            <div
              key={entry.id}
              className={cn(
                'panel-glass flex flex-col gap-3 rounded-xl border p-4 transition-colors duration-(--dur-micro)',
                isSelected
                  ? 'border-accent bg-accent-wash'
                  : 'border-rule hover:border-rule-strong',
              )}
            >
              <button
                type="button"
                onClick={selectThis}
                aria-pressed={isSelected}
                className="flex flex-col gap-1 text-left"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="font-medium text-text">{entry.name}</span>
                  {isSelected ? <Tag>Selected</Tag> : null}
                </span>
                <span className="text-small text-text-mute">
                  {entry.vendor}
                </span>
              </button>

              <div className="flex flex-col gap-1 text-small text-text-dim">
                <p>
                  <span className="font-medium text-text-mute">Cost</span> ·{' '}
                  {entry.cost_note}
                </p>
                <p>
                  <span className="font-medium text-text-mute">Latency</span>{' '}
                  · {entry.latency_note}
                </p>
                <p>
                  <span className="font-medium text-text-mute">Quality</span>{' '}
                  · {entry.quality_note}
                </p>
              </div>

              {hasVoices ? (
                <Select
                  value={displayedVoiceId ?? voiceOptions[0]}
                  onValueChange={(v) => {
                    onVoiceIdChange?.(entry, v);
                    if (!isSelected) onSelect(entry);
                  }}
                  options={voiceOptions.map((v) => ({
                    value: v,
                    label: voiceOptionLabel(v),
                  }))}
                  ariaLabel={`Voice for ${entry.name}`}
                />
              ) : null}

              <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-rule pt-3">
                <div className="flex items-center gap-2">
                  {isConnected ? <Tag>Connected</Tag> : null}
                  {canManageIntegrations ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setEditingProvider(vendorId)}
                    >
                      {isConnected ? 'Update key' : 'Connect'}
                    </Button>
                  ) : !isConnected ? (
                    <p className="text-small text-text-dim">
                      Ask an admin to connect this in Settings →
                      Integrations.
                    </p>
                  ) : null}
                </div>

                {category !== 'llm' &&
                entry.preview_available &&
                isConnected ? (
                  <VoicePreviewButton
                    provider={entry.id}
                    kind={category === 'stt' ? 'stt' : 'tts'}
                    voiceId={displayedVoiceId}
                  />
                ) : null}
              </div>
            </div>
          );
        })}
      </div>

      {editingProvider ? (
        <ConnectAiKeyDialog
          provider={editingProvider}
          vendorName={editingVendorName}
          existing={editingCredential}
          onOpenChange={(open) => !open && setEditingProvider(null)}
          onChanged={() => {
            setEditingProvider(null);
            onCredentialsChanged();
          }}
        />
      ) : null}
    </>
  );
}
