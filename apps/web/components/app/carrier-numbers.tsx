'use client';

import { useCallback, useMemo, useState } from 'react';
import {
  ArrowsClockwiseIcon,
  CheckIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react/dist/ssr';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/cn';
import { api, type TelephonyNumber, type VoiceAgent } from '@/lib/api';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';

/**
 * The numbers a connected carrier holds, and whether a run may dial from one.
 *
 * This section exists because connecting a carrier is only the first of three
 * steps, and the other two were invisible. A credential proves the account;
 * a sync discovers what it owns; pointing a number at LiveKit is what actually
 * makes it diallable. Until that last step runs, the run composer reports no
 * line to dial from - so someone would connect a carrier, be told to connect a
 * carrier, and have nowhere to go. Integrations is where the carrier is, so
 * this is where the rest of the chain belongs.
 */
export function CarrierNumbers({
  providers,
  canWrite,
}: {
  providers: string[];
  canWrite: boolean;
}) {
  const toast = useToast();
  const [numbers, setNumbers] = useState<TelephonyNumber[] | null>(null);
  const [agents, setAgents] = useState<VoiceAgent[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .listNumbers()
      .then(setNumbers)
      .catch(() => setNumbers([]));
  }, []);

  useOrgScopedEffect(() => {
    load();
    api
      .listVoiceAgents()
      .then(setAgents)
      .catch(() => setAgents([]));
  }, [load]);

  const sync = useCallback(
    async (provider: string) => {
      setBusy(`sync:${provider}`);
      try {
        const found = await api.syncNumbers(provider);
        setNumbers(found);
        toast({
          tone: 'success',
          title:
            found.length === 0
              ? `${provider} holds no voice numbers`
              : `Found ${found.length} number${found.length === 1 ? '' : 's'}`,
        });
      } catch (error) {
        toast({
          tone: 'error',
          title: "Couldn't reach the carrier",
          body: error instanceof Error ? error.message : undefined,
        });
      } finally {
        setBusy(null);
      }
    },
    [toast],
  );

  /**
   * The step that was missing entirely. A number needs a voice agent because
   * the dispatch rule it creates is what routes an inbound call to one - so
   * with no agent built yet there is nothing to point the number at, and
   * saying so is more use than a disabled button with no explanation.
   */
  const connect = useCallback(
    async (number: TelephonyNumber) => {
      const agent = agents[0];
      if (!agent) {
        toast({
          tone: 'error',
          title: 'Build an agent first',
          body: 'A number is routed to an agent, so there has to be one to point it at.',
        });
        return;
      }
      setBusy(`connect:${number.id}`);
      try {
        const attempt = await api.connectNumber(agent.id, {
          provider: number.provider,
          number_id: number.id,
          // Stable per number, so a double-click resumes the same attempt
          // instead of building a second pair of LiveKit trunks.
          idempotency_key: `connect-${number.id}`,
        });
        if (attempt.status === 'verified') {
          toast({ tone: 'success', title: 'Number ready to dial from' });
        } else {
          toast({
            tone: 'error',
            title: "Couldn't finish connecting",
            body: attempt.last_error ?? 'Try again to resume where it stopped.',
          });
        }
        load();
      } catch (error) {
        toast({
          tone: 'error',
          title: "Couldn't connect the number",
          body: error instanceof Error ? error.message : undefined,
        });
      } finally {
        setBusy(null);
      }
    },
    [agents, load, toast],
  );

  const ready = useMemo(
    () => (numbers ?? []).filter((n) => n.diallable).length,
    [numbers],
  );

  if (providers.length === 0) return null;

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <h2 className="text-small font-medium text-text">Numbers</h2>
        {numbers ? (
          <span className="text-small tabular-nums text-text-mute">
            {ready}/{numbers.length} ready
          </span>
        ) : null}
        <span aria-hidden className="h-px flex-1 bg-rule" />
        {canWrite
          ? providers.map((p) => (
              <Button
                key={p}
                variant="secondary"
                size="sm"
                onClick={() => void sync(p)}
                disabled={busy !== null}
              >
                <ArrowsClockwiseIcon
                  aria-hidden
                  className={cn(
                    'size-3.5',
                    busy === `sync:${p}` && 'animate-spin',
                  )}
                />
                Sync {p}
              </Button>
            ))
          : null}
      </div>

      {numbers === null ? (
        <Skeleton className="h-20 w-full rounded-md" />
      ) : numbers.length === 0 ? (
        <p className="text-small text-text-dim">
          Nothing synced yet. Sync a carrier to see the numbers it holds.
        </p>
      ) : (
        <ul className="flex flex-col gap-px overflow-hidden rounded-md border border-rule bg-rule">
          {numbers.map((number) => (
            <li
              key={number.id}
              className="flex flex-wrap items-center gap-x-4 gap-y-2 bg-surface px-4 py-3"
            >
              <span className="font-mono text-small text-text">
                {number.phone_masked}
              </span>
              <span className="text-small text-text-mute">
                {number.label ?? number.provider}
              </span>
              <span className="flex-1" />
              {number.diallable ? (
                // Paired with a word, never colour alone.
                <span className="flex items-center gap-1.5 text-small text-text-dim">
                  <CheckIcon aria-hidden weight="bold" className="size-3.5" />
                  Ready to dial
                </span>
              ) : (
                <>
                  {number.last_error ? (
                    // The carrier's or LiveKit's own words. Sync provisions
                    // every number it discovers, so a number that is still not
                    // diallable failed for a reason, and the reason is the only
                    // part that says what to do about it.
                    <span className="text-small text-lamp-flare-text">
                      <WarningCircleIcon
                        aria-hidden
                        className="mr-1.5 inline size-3.5 align-[-2px]"
                      />
                      {number.last_error}
                    </span>
                  ) : (
                    <span className="text-small text-text-mute">
                      {number.status}
                    </span>
                  )}
                  {/* Not offered for a retired number. Provisioning marks its
                      own attempt verified and returns, but deliberately will not
                      move a `disabled` number back into service - so the button
                      reported success, built a fresh pair of LiveKit trunks, and
                      changed nothing the operator could see (`ISSUES.md` #170).
                      Re-enabling is a separate, deliberate act. */}
                  {canWrite && number.status !== 'disabled' ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => void connect(number)}
                      disabled={busy !== null}
                    >
                      {busy === `connect:${number.id}`
                        ? 'Connecting…'
                        : 'Try again'}
                    </Button>
                  ) : null}
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
