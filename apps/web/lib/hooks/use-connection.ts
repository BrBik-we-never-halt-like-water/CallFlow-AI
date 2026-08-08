'use client';

import { useEffect, useState } from 'react';
import { api, type Campaign, type Health } from '@/lib/api';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';

export type ConnectionPhase = 'connecting' | 'up' | 'down';

export interface Connection {
  phase: ConnectionPhase;
  health: Health | null;
  campaigns: Campaign[];
  refreshHealth: () => void;
}

/** A couple of quick retries absorbs a transient blip without a long wait. */
const RETRY_ATTEMPTS = 2;
const RETRY_DELAY_MS = 1500;

/**
 * Establishes the connection to the service and loads what every app page needs.
 *
 * The service runs on an always-on VM, so there is no cold start to wait out - a
 * failed request here means something is actually wrong, not asleep.
 */
export function useConnection(): Connection {
  const [phase, setPhase] = useState<ConnectionPhase>('connecting');
  const [health, setHealth] = useState<Health | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [healthNonce, setHealthNonce] = useState(0);

  // Campaigns are organisation-scoped, so this whole connect sequence re-runs on
  // every org switch, not just on mount - otherwise switching orgs would keep
  // showing the previous org's campaigns until a hard reload.
  useOrgScopedEffect(() => {
    let cancelled = false;

    async function load(): Promise<void> {
      const nextHealth = await api.health();
      if (cancelled) return;
      setHealth(nextHealth);

      const nextCampaigns = await api.campaigns();
      if (cancelled) return;
      setCampaigns(nextCampaigns);
      setPhase('up');
    }

    async function connect() {
      for (
        let attempt = 0;
        attempt <= RETRY_ATTEMPTS && !cancelled;
        attempt++
      ) {
        try {
          await load();
          return;
        } catch {
          if (attempt < RETRY_ATTEMPTS) {
            await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
          }
        }
      }

      if (!cancelled) {
        setPhase('down');
        setHealth(null);
      }
    }

    void connect();

    return () => {
      cancelled = true;
    };
  });

  // Refreshing health after a run updates the remaining live-call budget.
  useEffect(() => {
    if (healthNonce === 0) return;
    let cancelled = false;
    api
      .health()
      .then((next) => {
        if (!cancelled) setHealth(next);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [healthNonce]);

  return {
    phase,
    health,
    campaigns,
    refreshHealth: () => setHealthNonce((n) => n + 1),
  };
}
