"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { api, type Outcome, type Run, type RunSummary, type SafetySettings } from "@/lib/api";
import { useConnection, type Connection } from "@/lib/hooks/use-connection";
import { useOrgScopedEffect } from "@/lib/hooks/use-org-scoped-effect";
import { lampForOutcome } from "@/lib/lamp";

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

/**
 * A stable-enough key for one outcome, for tracking local-only escalation
 * resolution (see `resolveEscalation` below). The API has no per-outcome id yet —
 * `provider_call_id` is only set for a live call, and `run_id` can be null — so this
 * is a content key, not a real identifier: good enough to dedupe within one loaded
 * session, not a replacement for the `escalations` table `ISSUES.md #7` still wants.
 */
function outcomeKey(outcome: Outcome): string {
  return `${outcome.run_id ?? ""}|${outcome.provider_call_id ?? ""}|${outcome.contact_name}|${outcome.created_at}`;
}

/** While any listed run is still going, re-fetch this often so the dashboard and
 * the runs list don't sit on a "running" row for a run that finished seconds ago —
 * only the run-detail page itself polls today. */
const LIVE_POLL_MS = 4000;

export interface AppState extends Connection {
  runs: RunSummary[];
  /** Recent runs with their outcomes loaded, newest first. */
  hydratedRuns: Run[];
  /** Every outcome across the hydrated runs, newest first. */
  outcomes: Outcome[];
  /** Outcomes that need a person, oldest first — the worklist order. Excludes
   *  anything resolved this session (see `resolveEscalation`). */
  escalations: Outcome[];
  /** Mark one escalation resolved for the rest of this session: it drops out of
   *  `escalations` immediately, everywhere that list is read (the worklist, the
   *  dashboard panel, the nav badge) — not persisted (`ISSUES.md #7`), so it comes
   *  back on reload. */
  resolveEscalation: (outcome: Outcome) => void;
  loadingRuns: boolean;
  refresh: () => void;
  /** This organisation's own safety overrides + live usage. Null until loaded. */
  safetySettings: SafetySettings | null;
  refreshSafety: () => void;
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
  const [safetySettings, setSafetySettings] = useState<SafetySettings | null>(null);
  const [safetyNonce, setSafetyNonce] = useState(0);
  const [resolvedKeys, setResolvedKeys] = useState<Set<string>>(() => new Set());

  const refresh = useCallback(() => setNonce((n) => n + 1), []);
  const refreshSafety = useCallback(() => setSafetyNonce((n) => n + 1), []);
  const resolveEscalation = useCallback((outcome: Outcome) => {
    setResolvedKeys((prev) => {
      const next = new Set(prev);
      next.add(outcomeKey(outcome));
      return next;
    });
  }, []);

  // Runs are organisation-scoped — re-fetching on every org switch (not just on
  // mount, or when `refresh()`/the live poll bump `nonce`) is what makes the
  // dashboard, runs list, and escalations queue stop showing the previous org's
  // data the moment someone switches.
  useOrgScopedEffect(() => {
    // Wait for the connection to be established; fetching while the service is still
    // waking would just fail and clear the list.
    if (connection.phase !== "up") return;

    let cancelled = false;
    let livePoll: ReturnType<typeof setTimeout> | null = null;

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

        // A run still going means the summary/list view will otherwise show a
        // stale "running" row for however long the visitor leaves the tab open.
        if (summaries.some((r) => r.status === "running")) {
          livePoll = setTimeout(() => void load(), LIVE_POLL_MS);
        }
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
      if (livePoll) clearTimeout(livePoll);
    };
  }, [connection.phase, nonce]);

  // Same reasoning as the runs effect above: safety settings (allowlist, ceilings,
  // daily budget) belong to the organisation, not the browser tab.
  useOrgScopedEffect(() => {
    if (connection.phase !== "up") return;
    let cancelled = false;
    api
      .getSafetySettings()
      .then((settings) => {
        if (!cancelled) setSafetySettings(settings);
      })
      .catch(() => {
        // Leaves the previous value in place — the safety bar renders each
        // guard as unconfirmed rather than a wrong reassuring default either way.
      });
    return () => {
      cancelled = true;
    };
  }, [connection.phase, safetyNonce]);

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
        // "Needs a person" is defined once, by the lamp a call gets — flare — not by
        // a second, independent list of dispositions here. The two drifted apart
        // before: this queue showed only `escalated`, while the dashboard's own
        // outcome-distribution counted `escalated` and `unreachable` alike as
        // needing a person, so the two disagreed about the same three calls.
        .filter((outcome) => lampForOutcome(outcome).state === "flare")
        // Drops anything resolved this session — see `resolveEscalation`.
        .filter((outcome) => !resolvedKeys.has(outcomeKey(outcome)))
        // Oldest first: the oldest escalation is the most expensive one.
        .sort((a, b) => a.created_at.localeCompare(b.created_at)),
    [outcomes, resolvedKeys],
  );

  const value = useMemo<AppState>(
    () => ({
      ...connection,
      runs,
      hydratedRuns,
      outcomes,
      escalations,
      resolveEscalation,
      loadingRuns,
      refresh,
      safetySettings,
      refreshSafety,
    }),
    [
      connection,
      runs,
      hydratedRuns,
      outcomes,
      escalations,
      resolveEscalation,
      loadingRuns,
      refresh,
      safetySettings,
      refreshSafety,
    ],
  );

  return <AppStoreContext.Provider value={value}>{children}</AppStoreContext.Provider>;
}
