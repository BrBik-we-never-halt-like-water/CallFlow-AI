'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Field } from '@/components/ui/field';
import { Input, Textarea } from '@/components/ui/input';
import { PromptPlaceholders } from '@/components/app/agentic/prompt-placeholders';
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import { Tooltip } from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/toast';
import {
  api,
  type CollectField,
  type ProviderCatalog,
  type VoiceAgent,
  type VoiceAgentDraft,
} from '@/lib/api';
import {
  type AgentDraftSeed,
  clearAgentDraft,
  loadAgentDraft,
  saveAgentDraft,
} from '@/lib/agent-draft';
import { useScopedOrgId } from '@/lib/hooks/use-active-org';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession } from '@/lib/hooks/use-session';
import { AgentMetrics } from './agent-metrics';
import { AgentPresets } from './agent-presets';
import { CollectFieldsEditor } from './collect-fields-editor';
import { ProviderWheel } from './provider-wheel';

/**
 * The voice-agent editor: name, then three legs of provider configuration
 * (STT, TTS, model) plus the system prompt and the fields to collect.
 *
 * No number here: which line a call comes from is chosen per run (ADR-8), which
 * is what lets one agent dial through any carrier the organisation has
 * connected. Seeded local state,
 * a `blocker` string that names the exact thing standing between here and a
 * save, one save handler that creates or updates depending on `existing`.
 *
 * The three provider legs are scroll wheels rather than card grids, and the
 * numbers that used to sit in prose on every card are now one live readout
 * (`AgentMetrics`) above them, so choosing a combination shows what that
 * combination costs instead of asking someone to add it up while reading.
 */
export function AgentEditor({ existing }: { existing?: VoiceAgent }) {
  const router = useRouter();
  const toast = useToast();
  const session = useSession();

  const canWrite =
    session.status === 'signed-in' &&
    session.profile.permissions.includes('agents:write');
  // A refresh, or a trip to Contacts and back, must not cost the work done so
  // far. The draft is read once as the initial state rather than synced in an
  // effect - deriving during render is the rule here, and an effect would also
  // flash the server values before replacing them.
  const agentId = existing?.id ?? null;
  // Drafts belong to one organisation. Read and written under the org the
  // rest of the app is currently in, so a draft started elsewhere never
  // prefills an agent being built here (`ISSUES.md` #128).
  const scopedOrgId = useScopedOrgId();
  const [draft] = useState(() =>
    typeof window === 'undefined' ? null : loadAgentDraft(scopedOrgId, agentId),
  );

  const [name, setName] = useState(draft?.name ?? existing?.name ?? '');
  const [sttProvider, setSttProvider] = useState<string | null>(
    draft?.sttProvider ?? existing?.stt_provider ?? null,
  );
  const [ttsProvider, setTtsProvider] = useState<string | null>(
    draft?.ttsProvider ?? existing?.tts_provider ?? null,
  );
  const [voiceId, setVoiceId] = useState<string | null>(
    draft?.voiceId ?? existing?.voice_id ?? null,
  );
  const [llmModel, setLlmModel] = useState<string | null>(
    draft?.llmModel ?? existing?.llm_model ?? null,
  );
  const [systemPrompt, setSystemPrompt] = useState(
    draft?.systemPrompt ?? existing?.system_prompt ?? '',
  );
  const promptRef = useRef<HTMLTextAreaElement>(null);

  /** Insert at the caret, not at the end - someone clicking `{name}` is
   *  almost always mid-sentence. Falls back to appending when the field has
   *  never been focused and there is no caret to insert at. */
  function insertPlaceholder(token: string) {
    const field = promptRef.current;
    if (!field) {
      setSystemPrompt((prompt) => prompt + token);
      return;
    }
    const start = field.selectionStart ?? field.value.length;
    const end = field.selectionEnd ?? start;
    setSystemPrompt(field.value.slice(0, start) + token + field.value.slice(end));
    // After React has written the new value, or the caret lands on the old one.
    requestAnimationFrame(() => {
      field.focus();
      field.setSelectionRange(start + token.length, start + token.length);
    });
  }
  const [collectFields, setCollectFields] = useState<CollectField[]>(
    draft?.collectFields ?? existing?.collect_fields ?? [],
  );
  const [catalog, setCatalog] = useState<ProviderCatalog | null>(null);
  const [saving, setSaving] = useState(false);
  // Carried forward from a restored draft, so a resumed session still knows
  // which providers it never chose.
  const seed = useRef<AgentDraftSeed | undefined>(draft?.seed);

  // The org credential list used to be fetched alongside this, to drive the
  // per-provider connect buttons. Those are gone - calls run on the platform's
  // own keys for now - so the editor needs the catalog and nothing else.
  useOrgScopedEffect(() => {
    api
      .voiceProviderCatalog()
      .then((loaded) => {
        setCatalog(loaded);
        // A wheel with no value still *centres* its first row, so a new agent
        // showed "Deepgram Nova-3" while the state behind it was null - the
        // metrics read "Not set" for a provider the builder could plainly see
        // selected. Commit what the wheel is already displaying so the two
        // agree from the first render. Only for a new agent: an existing one
        // arrives with its own providers and must not be overwritten.
        setSttProvider((current) => current ?? loaded.stt[0]?.id ?? null);
        setTtsProvider((current) => current ?? loaded.tts[0]?.id ?? null);
        setLlmModel((current) => current ?? loaded.llm[0]?.id ?? null);
        // Remember what was filled in automatically. Without this the drafts
        // list cannot tell "opened the page" from "chose these three", and
        // every visit would leave a card behind. Only for a new agent - an
        // existing one's providers are its own, never a seed.
        if (!existing) {
          seed.current = {
            sttProvider: loaded.stt[0]?.id ?? null,
            ttsProvider: loaded.tts[0]?.id ?? null,
            llmModel: loaded.llm[0]?.id ?? null,
          };
        }
      })
      .catch(() => toast({ tone: 'error', title: "Couldn't load providers" }));
  });

  // Persisting is a side effect on state that has already rendered, which is
  // what an effect is actually for. `saved` guards the write so the clear that
  // follows a successful save is not immediately undone by this.
  const saved = useRef(false);
  useEffect(() => {
    if (saved.current) return;
    saveAgentDraft(scopedOrgId, agentId, {
      name,
      sttProvider,
      ttsProvider,
      voiceId,
      llmModel,
      systemPrompt,
      collectFields,
      seed: seed.current,
    });
  }, [
    scopedOrgId,
    agentId,
    name,
    sttProvider,
    ttsProvider,
    voiceId,
    llmModel,
    systemPrompt,
    collectFields,
  ]);

  const blocker = useMemo<string | null>(() => {
    if (!canWrite) return 'Your role can view agents but not edit them.';
    // The API enforces a 2-character minimum (`VoiceAgentIn`). Without this
    // the save reaches the server and comes back as a raw 422 rather than a
    // sentence saying what to fix.
    if (name.trim().length < 2)
      return 'Give the agent a name of at least 2 characters.';
    if (!llmModel) return 'Pick a model before saving.';
    return null;
  }, [canWrite, name, llmModel]);

  async function save() {
    if (blocker) return;
    setSaving(true);
    try {
      const payload: VoiceAgentDraft = {
        name: name.trim(),
        kind: existing?.kind ?? 'custom',
        stt_provider: sttProvider,
        tts_provider: ttsProvider,
        llm_provider: 'openrouter',
        llm_model: llmModel,
        voice_id: voiceId,
        system_prompt: systemPrompt.trim() || null,
        prebuilt_persona: existing?.prebuilt_persona ?? null,
        collect_fields: collectFields.filter((f) => f.key.trim().length > 0),
      };
      if (existing) {
        await api.updateVoiceAgent(existing.id, payload);
      } else {
        await api.createVoiceAgent(payload);
      }
      // The server copy is the truth now; leaving the draft would have it
      // reappear over a later edit. Set before clearing so the persist effect
      // does not immediately write it back.
      saved.current = true;
      clearAgentDraft(scopedOrgId, agentId);
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

  const selectedStt = catalog?.stt.find((e) => e.id === sttProvider) ?? null;
  const selectedTts = catalog?.tts.find((e) => e.id === ttsProvider) ?? null;
  const selectedLlm = catalog?.llm.find((e) => e.id === llmModel) ?? null;

  return (
    <div className="flex flex-col gap-8">
      {!canWrite ? (
        <Panel sunken className="flex flex-col gap-2 p-4">
          <p className="text-small font-bold text-text-mute">Read only</p>
          <p className="text-small text-text-dim">
            Your role can view agents but not edit them.
          </p>
        </Panel>
      ) : null}

      {/* Name and the save controls share the top line: they are the two ends
          of the same act, and the buttons no longer have to live at the bottom
          of a long scroll to be reachable. */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <Field label="Agent name" required className="w-full max-w-sm">
          <Input
            value={name}
            placeholder="enter name"
            onChange={(e) => setName(e.target.value)}
            disabled={!canWrite}
          />
        </Field>

        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => router.push('/app/agentic')}
          >
            Cancel
          </Button>
          {blocker ? (
            <Tooltip content={blocker} wrapTrigger>
              <Button disabled>Save agent</Button>
            </Tooltip>
          ) : (
            <Button loading={saving} onClick={save}>
              Save agent
            </Button>
          )}
        </div>
      </div>

      {catalog === null ? (
        <div className="flex flex-col gap-8">
          <Skeleton className="h-40 w-full" />
          <div className="grid gap-8 lg:grid-cols-3">
            <Skeleton className="h-80 w-full" />
            <Skeleton className="h-80 w-full" />
            <Skeleton className="h-80 w-full" />
          </div>
        </div>
      ) : (
        <>
          <AgentPresets
            catalog={catalog}
            sttId={sttProvider}
            llmId={llmModel}
            ttsId={ttsProvider}
            disabled={!canWrite}
            onApply={(pick) => {
              if (pick.stt) setSttProvider(pick.stt.id);
              if (pick.llm) setLlmModel(pick.llm.id);
              if (pick.tts) {
                setTtsProvider(pick.tts.id);
                setVoiceId(pick.tts.voice_options[0] ?? null);
              }
            }}
          />

          <AgentMetrics
            stt={selectedStt}
            llm={selectedLlm}
            tts={selectedTts}
            voiceId={voiceId}
          />

          {/* Voice takes the wider track: it is the only leg carrying two
              wheels, and splitting an equal third between provider and named
              voice truncated both. */}
          <div className="grid min-w-0 gap-8 lg:grid-cols-[1fr_1fr_1.6fr]">
            <ProviderWheel
              title="Transcriber"
              entries={catalog.stt}
              selectedId={sttProvider}
              onSelect={(entry) => setSttProvider(entry.id)}
              category="stt"
              disabled={!canWrite}
              animateChanges
            />

            <ProviderWheel
              title="Model"
              entries={catalog.llm}
              selectedId={llmModel}
              onSelect={(entry) => setLlmModel(entry.id)}
              category="llm"
              disabled={!canWrite}
              animateChanges
            />

            <ProviderWheel
              title="Voice"
              entries={catalog.tts}
              selectedId={ttsProvider}
              // The voice moves with the provider. `voice_id` is one column
              // shared by every vendor and the names do not carry across -
              // ElevenLabs' "Rachel" is not a speaker Sarvam's bulbul model
              // has - so keeping the old value made the wheel *display* a
              // valid voice (it falls back to the first option) while the
              // saved agent still held the previous vendor's name, and the
              // call then failed at the pipeline with the contact already
              // ringing (`ISSUES.md` #162).
              onSelect={(entry) => {
                setTtsProvider(entry.id);
                setVoiceId(entry.voice_options[0] ?? null);
              }}
              category="tts"
              selectedVoiceId={voiceId}
              onVoiceIdChange={(_entry, id) => setVoiceId(id)}
              disabled={!canWrite}
              animateChanges
            />
          </div>

          {/* Full width, below the wheels: a prompt is prose, and prose in a
              22rem rail wraps every few words. This is the one thing on the
              page that benefits from the whole line length. */}
          <section className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-[0.6875rem] font-semibold uppercase tracking-[0.05em] leading-none" style={{ color: 'var(--dash-text)' }}>
                System prompt
              </h2>
              <PersonaTag persona={existing?.prebuilt_persona ?? null} />
            </div>
            <PromptPlaceholders onInsert={insertPlaceholder} disabled={!canWrite} />
            <Textarea
              ref={promptRef}
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={16}
              mono
              disabled={!canWrite}
              placeholder="Add a system prompt for the agent"
            />
          </section>

          <CollectFieldsEditor
            fields={collectFields}
            onChange={setCollectFields}
            disabled={!canWrite}
          />

          {blocker ? (
            <p className="text-[0.6875rem] leading-relaxed text-text-mute">
              {blocker}
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}

/**
 * The agent's persona, when it was created from a prebuilt one.
 *
 * `prebuilt_persona` is set at creation and is not editable here, so this is a
 * label rather than a control. A custom agent shows nothing - an empty "no
 * persona" chip would be noise on every card.
 */
function PersonaTag({ persona }: { persona: string | null }) {
  if (!persona) return null;
  return (
    <span className="rounded-full bg-surface-sunken px-2.5 py-1 text-[0.6875rem] text-text-dim">
      {persona}
    </span>
  );
}
