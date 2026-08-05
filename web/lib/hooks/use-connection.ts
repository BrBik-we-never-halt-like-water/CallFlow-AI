"use client";

import { useEffect, useState } from "react";
import { api, type Campaign, type Health } from "@/lib/api";

export type ConnectionPhase = "connecting" | "waking" | "up" | "down";

export interface Connection {
  phase: ConnectionPhase;
  health: Health | null;
  campaigns: Campaign[];
  /** Seconds spent waiting on a cold start, so the wait can look like progress. */
  wakeSeconds: number;
  refreshHealth: () => void;
}

/** Cold starts on a sleeping instance can run past two minutes. */
const WAKE_ATTEMPTS = 40;
const WAKE_INTERVAL_MS = 4000;

/**
 * Establishes the connection to the service and loads what every app page needs.
 *
 * The service may be asleep when someone arrives. `phase` distinguishes "not
 * fetched yet" from "failed" from "waking" — collapsing those into one nullable
 * value is how an error banner ends up flashing before the first request has
 * even finished.
 *
 * Nothing here says the word "backend" to the user; the run view renders this as
 * a lamp sequence captioned "Waking the service…".
 */
export function useConnection(): Connection {
  const [phase, setPhase] = useState<ConnectionPhase>("connecting");
  const [health, setHealth] = useState<Health | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [wakeSeconds, setWakeSeconds] = useState(0);
  const [healthNonce, setHealthNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let ticker: ReturnType<typeof setInterval> | null = null;

    async function load(): Promise<boolean> {
      const nextHealth = await api.health();
      if (cancelled) return true;
      setHealth(nextHealth);

      const nextCampaigns = await api.campaigns();
      if (cancelled) return true;
      setCampaigns(nextCampaigns);
      setPhase("up");
      return true;
    }

    async function connect() {
      // Try once directly — if the service is already warm this is instant.
      try {
        await load();
        return;
      } catch {
        /* asleep: fall through to the wake path */
      }

      if (cancelled) return;
      setPhase("waking");

      const started = Date.now();
      ticker = setInterval(() => {
        setWakeSeconds(Math.floor((Date.now() - started) / 1000));
      }, 1000);

      // Ask our own server to wake the service: no CORS preflight and no browser
      // fetch timeout, so this survives a multi-minute start.
      void fetch("/api/wake", { cache: "no-store" }).catch(() => {});

      for (let attempt = 0; attempt < WAKE_ATTEMPTS && !cancelled; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, WAKE_INTERVAL_MS));
        try {
          await load();
          return;
        } catch {
          /* still starting */
        }
      }

      if (!cancelled) {
        setPhase("down");
        setHealth(null);
      }
    }

    void connect();

    return () => {
      cancelled = true;
      if (ticker) clearInterval(ticker);
    };
  }, []);

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
    wakeSeconds,
    refreshHealth: () => setHealthNonce((n) => n + 1),
  };
}
