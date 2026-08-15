'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Tag } from '@/components/ui/badge';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { Panel } from '@/components/ui/panel';
import { useToast } from '@/components/ui/toast';
import { api, type AiProvider, type VoiceAgent } from '@/lib/api';
import { useSession } from '@/lib/hooks/use-session';

/**
 * Written names only - the same reasoning as `ProviderMark` in the
 * integrations settings page: reproducing a vendor's actual wordmark needs
 * their asset, not a guess, so this product's identity stays monochrome text
 * throughout. Unknown or not-yet-catalogued provider ids still render
 * (capitalised) rather than disappearing.
 */
const AI_PROVIDER_LABEL: Partial<Record<AiProvider, string>> = {
  sarvam: 'Sarvam',
  deepgram: 'Deepgram',
  elevenlabs: 'ElevenLabs',
  openai: 'OpenAI',
  openrouter: 'OpenRouter',
};

const TELEPHONY_LABEL: Record<'twilio' | 'plivo', string> = {
  twilio: 'Twilio',
  plivo: 'Plivo',
};

function providerLabel(id: string | null): string {
  if (!id) return 'Not configured';
  return AI_PROVIDER_LABEL[id as AiProvider] ?? id.charAt(0).toUpperCase() + id.slice(1);
}

/**
 * One voice agent's summary card.
 *
 * Edit is always offered - the editor re-checks `agents:write` itself, so
 * hiding it here would only be UX, not a real gate (same "client-side hiding
 * is not the gate" reasoning as the page's own `agents:read` check). Delete
 * owns its own confirm step, since - unlike `CampaignCard` - nothing above it
 * in the tree keeps a "pending delete" dialog of its own.
 */
export function AgentCard({
  agent,
  canDelete,
  onChanged,
}: {
  agent: VoiceAgent;
  /** `agents:delete`. */
  canDelete: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const session = useSession();
  const currentUserId =
    session.status === 'signed-in' ? session.profile.user_id : null;
  const showAttribution =
    !!agent.created_by_name && agent.created_by !== currentUserId;

  const [pendingDelete, setPendingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function confirmDelete() {
    setDeleting(true);
    try {
      await api.deleteVoiceAgent(agent.id);
      toast({ tone: 'success', title: 'Agent deleted' });
      setPendingDelete(false);
      onChanged();
    } catch (error) {
      toast({
        tone: 'error',
        title: "That agent wasn't deleted",
        body:
          error instanceof Error
            ? error.message
            : "The service didn't respond.",
      });
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <Panel interactive className="panel-glass flex flex-col gap-4 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="min-w-0 truncate text-h4 font-medium text-text">
            {agent.name}
          </h3>
          <Tag>{agent.kind === 'prebuilt' ? 'Prebuilt' : 'Custom'}</Tag>
        </div>

        {showAttribution ? (
          <p className="truncate text-small text-text-dim">
            by {agent.created_by_name}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-1.5">
          <Tag>STT · {providerLabel(agent.stt_provider)}</Tag>
          <Tag>TTS · {providerLabel(agent.tts_provider)}</Tag>
          <Tag>LLM · {agent.llm_model ?? 'Not configured'}</Tag>
          <Tag>
            {agent.telephony_provider
              ? TELEPHONY_LABEL[agent.telephony_provider]
              : 'No number connected'}
          </Tag>
        </div>

        <div className="mt-auto flex items-center justify-between gap-2 border-t border-rule pt-3">
          <Button asChild variant="secondary" size="sm">
            <Link href={`/app/agentic/${agent.id}`}>Edit</Link>
          </Button>
          {canDelete ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPendingDelete(true)}
            >
              Delete
            </Button>
          ) : null}
        </div>
      </Panel>

      <DialogRoot
        open={pendingDelete}
        onOpenChange={(open) => !deleting && setPendingDelete(open)}
      >
        <Dialog
          title="Delete this agent?"
          description={`"${agent.name}" will be removed and can't be recovered.`}
          size="sm"
          footer={
            <>
              <Button
                variant="secondary"
                onClick={() => setPendingDelete(false)}
              >
                Keep it
              </Button>
              <Button
                variant="danger"
                loading={deleting}
                onClick={() => void confirmDelete()}
              >
                Delete agent
              </Button>
            </>
          }
        />
      </DialogRoot>
    </>
  );
}
