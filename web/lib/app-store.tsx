"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api, type Outcome, type Run, type RunSummary } from "@/lib/api";
import { useConnection, type Connection } from "@/lib/hooks/use-connection";

/**
 * Shared app state.
 *
 * Every dashboard page reads from here so they agree with each other: the
 * escalation count in the nav, the outcome strip on the overview, and the
 * escalation worklist are all derived from the same hydrated runs rather than each
 * fetching its own view of the truth.
 *
 * The list endpoint returns runs without their outcomes, so the most recent runs are
 * hydrated individually. That is the only way to get real outcome data for the
 * overview, and it is bounded — see HYDRATE_LIMIT.
 */

/** How many recent runs to fetch in full. Enough for the overview's 100-call strip. */
const HYDRATE_LIMIT = 10;

export interface AppState extends Connection {
  runs: RunSummary[];
  /** Recent runs with their outcomes loaded, newest first. */
  hydratedRuns: Run[];
  /** Every outcome across the hydrated runs, newest first. */
  outcomes: Outcome[];
  /** Outcomes that need a person, oldest first — the worklist order. */
  escalations: Outcome[];
  loadingRuns: boolean;
  refresh: () => void;
}

const AppStoreContext = createContext<AppState | null>(null);

export function useAppStore(): AppState {
  const context = useContext(AppStoreContext);
  if (!context) throw new Error("useAppStore must be used inside <AppStoreProvider>");
  return context;
}

export function AppStoreProvider({ children }: { children: React.ReactNode }) {
  const connection = useConnection();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [hydratedRuns, setHydratedRuns] = useState<Run[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [nonce, setNonce] = useState(0);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    // Wait for the connection to be established; fetching while the service is still
    // waking would just fail and clear the list.
    if (connection.phase !== "up") return;

    let cancelled = false;

    async function load() {
      try {
        const summaries = await api.listRuns();
        if (cancelled) return;
        setRuns(summaries);

        const hydrated = await Promise.all(
          summaries.slice(0, HYDRATE_LIMIT).map((summary) =>
            api.getRun(summary.id).catch(() => null),
          ),
        );
        if (cancelled) return;
        setHydratedRuns(hydrated.filter((run): run is Run => run !== null));
      } catch {
        // A failed refresh leaves the previous data in place rather than blanking the
        // dashboard — stale numbers are more useful than empty ones, and the
        // connection banner already reports that something is wrong.
      } finally {
        if (!cancelled) setLoadingRuns(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [connection.phase, nonce]);

  const outcomes = useMemo(
    () =>
      hydratedRuns
        .flatMap((run) => run.outcomes)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [hydratedRuns],
  );

  const escalations = useMemo(
    () =>
      outcomes
        .filter((outcome) => outcome.disposition === "escalated" && !outcome.dry_run)
        // Oldest first: the oldest escalation is the most expensive one.
        .sort((a, b) => a.created_at.localeCompare(b.created_at)),
    [outcomes],
  );

  const value = useMemo<AppState>(
    () => ({
      ...connection,
      runs,
      hydratedRuns,
      outcomes,
      escalations,
      loadingRuns,
      refresh,
    }),
    [connection, runs, hydratedRuns, outcomes, escalations, loadingRuns, refresh],
  );

  return <AppStoreContext.Provider value={value}>{children}</AppStoreContext.Provider>;
}
