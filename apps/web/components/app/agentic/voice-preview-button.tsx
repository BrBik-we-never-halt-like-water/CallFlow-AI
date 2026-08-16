'use client';

import { PauseIcon, PlayIcon } from '@phosphor-icons/react/dist/ssr';
import { useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Tooltip } from '@/components/ui/tooltip';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api';

/**
 * Preview a provider's voice output.
 *
 * Only the TTS path is wired: the Sarvam adapter is the only one this
 * codebase has a real preview call for (`catalog.py`'s own docstring). STT
 * preview would need microphone/file capture, which is a separate piece of
 * work - `kind === 'stt'` renders nothing rather than a fake recorder, so
 * wiring it up later only means filling in this one branch.
 */
export function VoicePreviewButton({
  provider,
  kind,
  text,
  voiceId,
  iconOnly,
}: {
  provider: string;
  kind: 'stt' | 'tts';
  /** For `kind === 'tts'`. */
  text?: string;
  /** For `kind === 'tts'`. */
  voiceId?: string;
  /** Render as a bare icon beside a heading rather than a labelled button. */
  iconOnly?: boolean;
}) {
  const toast = useToast();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [state, setState] = useState<'idle' | 'loading' | 'playing'>('idle');
  const [reason, setReason] = useState<string | null>(null);

  if (kind === 'stt') return null;

  function stop() {
    audioRef.current?.pause();
    setState('idle');
  }

  async function play() {
    if (state === 'loading') return;
    if (state === 'playing') {
      stop();
      return;
    }

    setState('loading');
    setReason(null);
    try {
      const result = await api.previewVoice({
        provider,
        kind: 'tts',
        text: text || 'Hello, this is a preview of my voice.',
        voice_id: voiceId,
      });

      if (!result.available || !result.audio_base64) {
        setReason(result.reason ?? "This voice can't be previewed right now.");
        setState('idle');
        return;
      }

      const audio = audioRef.current ?? new Audio();
      audioRef.current = audio;
      audio.src = `data:audio/wav;base64,${result.audio_base64}`;
      audio.onended = () => setState('idle');
      audio.onerror = () => setState('idle');
      await audio.play();
      setState('playing');
    } catch (error) {
      setState('idle');
      toast({
        tone: 'error',
        title: "That preview didn't play",
        body:
          error instanceof Error
            ? error.message
            : "The service didn't respond.",
      });
    }
  }

  const label = state === 'playing' ? 'Stop the preview' : 'Hear this voice';

  if (iconOnly) {
    return (
      <Tooltip content={reason ?? label}>
        <button
          type="button"
          onClick={() => void play()}
          aria-label={label}
          disabled={state === 'loading'}
          className="flex size-7 items-center justify-center rounded-full text-text-mute transition-colors duration-(--dur-micro) hover:bg-surface-hover hover:text-text disabled:opacity-45"
        >
          {state === 'playing' ? (
            <PauseIcon aria-hidden weight="fill" className="size-4" />
          ) : (
            <PlayIcon aria-hidden weight="fill" className="size-4" />
          )}
        </button>
      </Tooltip>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <Button
        variant="secondary"
        size="sm"
        onClick={() => void play()}
        loading={state === 'loading'}
      >
        {state === 'playing' ? (
          <>
            <PauseIcon aria-hidden className="size-4" />
            Playing…
          </>
        ) : (
          <>
            <PlayIcon aria-hidden className="size-4" />
            Play preview
          </>
        )}
      </Button>
      {reason ? <p className="text-small text-text-dim">{reason}</p> : null}
    </div>
  );
}
