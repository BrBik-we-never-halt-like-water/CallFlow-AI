'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';
import { cn } from '@/lib/cn';
import { Tag } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Field } from '@/components/ui/field';
import { Input, Textarea } from '@/components/ui/input';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import { Tooltip } from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/toast';
import {
  api,
  type AiProviderCredential,
  type ProviderCatalog,
  type TelephonyProvider,
  type VoiceAgent,
  type VoiceAgentDraft,
} from '@/lib/api';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { usePermission } from '@/lib/hooks/use-permission';
import { useSession } from '@/lib/hooks/use-session';
import { ProviderPicker } from './provider-picker';

const TELEPHONY_LABEL: Record<TelephonyProvider, string> = {
  twilio: 'Twilio',
  plivo: 'Plivo',
};

/**
 * The voice-agent editor: name, then four legs of provider configuration
 * (STT, TTS, model, phone number) plus the system prompt.
 *
 * Structurally the same shape as `campaign-editor.tsx` - seeded local state,
 * a `blocker` string that names the exact thing standing between here and a
 * save, one save handler that creates or updates depending on `existing`.
 */
export function AgentEditor({ existing }: { existing?: VoiceAgent }) {
  const router = useRouter();
  const toast = useToast();
  const session = useSession();

  const canWrite =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('agents:write');
  // Reading connected AI-vendor credentials is INTEGRATIONS_READ, a
  // narrower, admin-only permission than the AGENTS_WRITE that gets someone
  // into this editor at all (app/auth/permissions.py) - an operator can
  // still build an agent's shape, just without the org's key list, so the
  // fetch below is skipped rather than 403ing on every page load.
  const canReadIntegrations = usePermission('integrations:read');

  const [name, setName] = useState(existing?.name ?? '');
  const [sttProvider, setSttProvider] = useState<string | null>(
    existing?.stt_provider ?? null,
  );
  const [ttsProvider, setTtsProvider] = useState<string | null>(
    existing?.tts_provider ?? null,
  );
  const [voiceId, setVoiceId] = useState<string | null>(
    existing?.voice_id ?? null,
  );
  const [llmModel, setLlmModel] = useState<string | null>(
    existing?.llm_model ?? null,
  );
  const [systemPrompt, setSystemPrompt] = useState(
    existing?.system_prompt ?? '',
  );
  const [telephonyProvider, setTelephonyProvider] =
    useState<TelephonyProvider | null>(existing?.telephony_provider ?? null);

  const [catalog, setCatalog] = useState<ProviderCatalog | null>(null);
  const [credentials, setCredentials] = useState<AiProviderCredential[]>([]);
  const [saving, setSaving] = useState(false);

  function load() {
    Promise.all([
      api.voiceProviderCatalog(),
      canReadIntegrations
        ? api.listAiProviderCredentials()
        : Promise.resolve([]),
    ])
      .then(([catalogResult, credentialsResult]) => {
        setCatalog(catalogResult);
        setCredentials(credentialsResult);
      })
      .catch(() =>
        toast({ tone: 'error', title: "Couldn't load providers" }),
      );
  }

  useOrgScopedEffect(() => {
    load();
  }, [canReadIntegrations]);

  const blocker = useMemo<string | null>(() => {
    if (!canWrite) return 'Your role can view agents but not edit them.';
    if (name.trim().length < 2)
      return 'Give the agent a name of at least 2 characters.';
    if (!llmModel) return 'Pick a model before saving.';
    if (telephonyProvider) {
      const option = catalog?.telephony.find(
        (t) => t.provider === telephonyProvider,
      );
      if (!option?.connected) {
        return `Connect a ${TELEPHONY_LABEL[telephonyProvider]} number in Settings → Integrations before assigning it to an agent.`;
      }
    }
    return null;
  }, [canWrite, name, llmModel, telephonyProvider, catalog]);

  async function save() {
    if (blocker) return;
    setSaving(true);
    try {
      const draft: VoiceAgentDraft = {
        name: name.trim(),
        kind: existing?.kind ?? 'custom',
        stt_provider: sttProvider,
        tts_provider: ttsProvider,
        llm_provider: 'openrouter',
        llm_model: llmModel,
        voice_id: voiceId,
        system_prompt: systemPrompt.trim() || null,
        prebuilt_persona: existing?.prebuilt_persona ?? null,
        telephony_provider: telephonyProvider,
      };
      if (existing) {
        await api.updateVoiceAgent(existing.id, draft);
      } else {
        await api.createVoiceAgent(draft);
      }
      toast({ tone: 'success', title: 'Agent saved' });
      router.push('/app/agentic');
    } catch (error) {
      toast({
        tone: 'error',
        title: "That agent wasn't saved",
        body:
          error instanceof Error
            ? error.message
            : "The service didn't respond.",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      {!canWrite ? (
        <Panel sunken className="flex flex-col gap-2 p-4">
          <p className="text-small font-bold text-text-mute">Read only</p>
          <p className="text-small text-text-dim">
            Your role can view agents but not edit them.
          </p>
        </Panel>
      ) : null}

      <Field label="Agent name" required>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Support line agent"
          disabled={!canWrite}
        />
      </Field>

      {catalog === null ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : (
        <>
          <Panel className="flex flex-col gap-4 p-4">
            <div className="flex flex-col gap-1">
              <p className="text-small font-bold text-text-mute">
                Speech-to-text
              </p>
              <p className="text-small text-text-dim">
                Turns the caller&apos;s audio into text the model reads.
              </p>
            </div>
            <ProviderPicker
              entries={catalog.stt}
              selectedId={sttProvider}
              onSelect={(entry) => setSttProvider(entry.id)}
              credentials={credentials}
              onCredentialsChanged={load}
              category="stt"
            />
          </Panel>

          <Panel className="flex flex-col gap-4 p-4">
            <div className="flex flex-col gap-1">
              <p className="text-small font-bold text-text-mute">
                Text-to-speech
              </p>
              <p className="text-small text-text-dim">
                The voice callers hear back.
              </p>
            </div>
            <ProviderPicker
              entries={catalog.tts}
              selectedId={ttsProvider}
              onSelect={(entry) => setTtsProvider(entry.id)}
              credentials={credentials}
              onCredentialsChanged={load}
              category="tts"
              selectedVoiceId={voiceId}
              onVoiceIdChange={(_entry, id) => setVoiceId(id)}
            />
          </Panel>

          <Panel className="flex flex-col gap-4 p-4">
            <div className="flex flex-col gap-1">
              <p className="text-small font-bold text-text-mute">Model</p>
              <p className="text-small text-text-dim">
                Every model here runs through OpenRouter, so one connected key
                covers all of them.
              </p>
            </div>
            <ProviderPicker
              entries={catalog.llm}
              selectedId={llmModel}
              onSelect={(entry) => setLlmModel(entry.id)}
              connectProviderId="openrouter"
              credentials={credentials}
              onCredentialsChanged={load}
              category="llm"
            />
          </Panel>

          <Panel className="flex flex-col gap-3 p-4">
            <div className="flex flex-col gap-1">
              <p className="text-small font-bold text-text-mute">
                System prompt
              </p>
              <p className="text-small text-text-dim">
                How the agent should behave, what it should ask, and when to
                hand off - the same job a campaign&apos;s goal does for a
                scripted call.
              </p>
            </div>
            <Textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={10}
              mono
              disabled={!canWrite}
              placeholder="You are a helpful support agent for…"
            />
          </Panel>

          <Panel className="flex flex-col gap-4 p-4">
            <div className="flex flex-col gap-1">
              <p className="text-small font-bold text-text-mute">
                Phone number
              </p>
              <p className="text-small text-text-dim">
                Which connected number this agent dials from.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {catalog.telephony.map((option) => {
                const label = TELEPHONY_LABEL[option.provider];
                const isSelected = telephonyProvider === option.provider;

                if (!option.connected) {
                  return (
                    <div
                      key={option.provider}
                      className="flex flex-col gap-2 rounded-xl border border-rule bg-surface-sunken p-4"
                    >
                      <span className="font-medium text-text-mute">
                        {label}
                      </span>
                      <p className="text-small text-text-dim">
                        Not connected.{' '}
                        <Link
                          href="/app/settings/integrations"
                          className="underline decoration-rule-strong underline-offset-2 hover:decoration-current"
                        >
                          Connect a {label} number
                        </Link>{' '}
                        before assigning it here.
                      </p>
                    </div>
                  );
                }

                return (
                  <button
                    key={option.provider}
                    type="button"
                    disabled={!canWrite}
                    aria-pressed={isSelected}
                    onClick={() =>
                      setTelephonyProvider(
                        isSelected ? null : option.provider,
                      )
                    }
                    className={cn(
                      'panel-glass flex flex-col gap-2 rounded-xl border p-4 text-left transition-colors duration-(--dur-micro)',
                      'disabled:cursor-not-allowed disabled:opacity-45',
                      isSelected
                        ? 'border-accent bg-accent-wash'
                        : 'border-rule hover:border-rule-strong',
                    )}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-medium text-text">{label}</span>
                      {isSelected ? <Tag>Selected</Tag> : null}
                    </span>
                    <span className="font-mono text-data text-text-mute">
                      {option.phone_number_masked}
                    </span>
                  </button>
                );
              })}
            </div>
          </Panel>
        </>
      )}

      <div className="flex flex-wrap items-center gap-3">
        {blocker ? (
          <Tooltip content={blocker} wrapTrigger>
            <Button disabled>Save agent</Button>
          </Tooltip>
        ) : (
          <Button loading={saving} onClick={save}>
            Save agent
          </Button>
        )}
        <Button variant="secondary" onClick={() => router.push('/app/agentic')}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
