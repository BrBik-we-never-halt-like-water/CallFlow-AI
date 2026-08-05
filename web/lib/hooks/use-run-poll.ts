"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Run } from "@/lib/api";

const POLL_MS = 2500;

export interface RunPoll {
  run: Run | null;
  error: string | null;
  /** True while the run is still going. */
  live: boolean;
  /** Seconds since polling began. A live call has real queue and ring time. */
  elapsed: number;
}

interface PollState {
  runId: string | null;
  run: Run | null;
  error: string | null;
  elapsed: number;
}

/**
 * Polls a run until it settles.
 *
 * Progress is announced to assistive tech once per meaningful change, not once per row —
 * see `useProgressAnnouncement`. A screen reader reading out twenty individual rows as
 * they land is worse than no announcement at all.
 */
export function useRunPoll(runId: string | null, { paused = false } = {}): RunPoll {
  const [state, setState] = useState<PollState>({
    runId,
    run: null,
    error: null,
    elapsed: 0,
  });

  // A new run id clears the previous run's results during render, so a stale run is
  // never painted under a new run's heading.
  if (state.runId !== runId) {
    setState({ runId, run: null, error: null, elapsed: 0 });
  }

  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!runId || paused) return;

    let cancelled = false;
    const startedAt = Date.now();

    const ticker = setInterval(() => {
      setState((current) =>
        current.runId === runId
          ? { ...current, elapsed: Math.floor((Date.now() - startedAt) / 1000) }
          : current,
      );
    }, 1000);

    async function tick() {
      try {
        const latest = await api.getRun(runId!);
        if (cancelled) return;
        setState((current) =>
          current.runId === runId ? { ...current, run: latest, error: null } : current,
        );
        if (latest.status !== "running") {
          if (timer.current) {
            clearInterval(timer.current);
            timer.current = null;
          }
          clearInterval(ticker);
        }
      } catch (e) {
        if (cancelled) return;
        const message = e instanceof Error ? e.message : "The service didn't respond.";
        setState((current) =>
          current.runId === runId ? { ...current, error: message } : current,
        );
      }
    }

    void tick();
    timer.current = setInterval(tick, POLL_MS);

    return () => {
      cancelled = true;
      clearInterval(ticker);
      if (timer.current) {
        clearInterval(timer.current);
        timer.current = null;
      }
    };
  }, [runId, paused]);

  return {
    run: state.run,
    error: state.error,
    live: state.run?.status === "running",
    elapsed: state.elapsed,
  };
}

/**
 * Debounced progress message for an `aria-live="polite"` region.
 *
 * Returns a sentence only when the settled count has actually moved and has then held
 * still briefly — so a burst of results produces one announcement rather than five.
 */
export function useProgressAnnouncement(settled: number, total: number): string {
  const [message, setMessage] = useState("");
  const lastAnnounced = useRef(-1);

  useEffect(() => {
    if (settled === lastAnnounced.current) return;

    const timeout = setTimeout(() => {
      lastAnnounced.current = settled;
      setMessage(
        settled >= total && total > 0
          ? `All ${total} calls settled.`
          : `${settled} of ${total} calls settled.`,
      );
    }, 1200);

    return () => clearTimeout(timeout);
  }, [settled, total]);

  return message;
}
