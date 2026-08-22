'use client';

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';
import {
  api,
  type Escalation,
  type Outcome,
  type Run,
  type RunSummary,
} from '@/lib/api';
import { useActiveOrg } from '@/lib/hooks/use-active-org';
import { useConnection, type Connection } from '@/lib/hooks/use-connection';
import { useOrgRealtime } from '@/lib/hooks/use-org-realtime';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession } from '@/lib/hooks/use-session';

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
 * overview, and it is bounded - see HYDRATE_LIMIT.
 */

/** How many recent runs to fetch in full. Enough for the overview's 100-call strip. */
const HYDRATE_LIMIT = 10;

/** While any listed run is still going, re-fetch this often so the dashboard and
 * the runs list don't sit on a "running" row for a run that finished seconds ago -
 * only the run-detail page itself polls today. */
const LIVE_POLL_MS = 4000;

export interface AppState extends Connection {
  runs: RunSummary[];
  /** Recent runs with their outcomes loaded, newest first. */
  hydratedRuns: Run[];
  /** Every outcome across the hydrated runs, newest first. */
  outcomes: Outcome[];
  /** Real, persisted escalations this session can see, oldest first - the
   *  worklist order. Assigning or resolving one (`api.assignEscalation`/
   *  `api.resolveEscalation`) survives a reload and reaches every other
   *  signed-in teammate live, via Supabase Realtime on the `escalations`
   *  table - not local component state (closes `ISSUES.md` #7). */
  escalations: Escalation[];
  loadingEscalations: boolean;
  refreshEscalations: () => void;
  loadingRuns: boolean;
  refresh: () => void;
}

const AppStoreContext = createContext<AppState | null>(null);

export function useAppStore(): AppState {
  const context = useContext(AppStoreContext);
  if (!context)
    throw new Error('useAppStore must be used inside <AppStoreProvider>');
  return context;
}

export function AppStoreProvider({ children }: { children: React.ReactNode }) {
  const connection = useConnection();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [hydratedRuns, setHydratedRuns] = useState<Run[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [nonce, setNonce] = useState(0);
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [loadingEscalations, setLoadingEscalations] = useState(true);
  const [escalationsNonce, setEscalationsNonce] = useState(0);
  const session = useSession();
  const activeOrgId =
    session.status === 'signed-in' ? session.profile.active.org_id : null;

  /**
   * Drop the previous organisation's data the instant the org changes, before
   * anything can render it.
   *
   * Re-fetching on switch is not the same as isolating. The effects below all
   * re-fetch, but they only replace state when the new response *arrives* -
   * so for the length of a request the dashboard showed the previous
   * organisation's runs and escalations while the switcher
   * already said you were somewhere else. Their `catch` branches make it
   * worse: keeping stale data on a failed refresh is right for a refresh of
   * the same org, and wrong across a switch, where it leaves the old
   * organisation's rows on screen indefinitely (`ISSUES.md` #127).
   *
   * Keyed on `useActiveOrg()` rather than `session.profile.active.org_id`
   * deliberately: that is the same value `useOrgScopedEffect` keys on, so the
   * clear and the re-fetch are driven by one signal and land in the right
   * order. The session's copy updates only after `/me` comes back, which is
   * *after* the re-fetch - resetting on it would wipe the new organisation's
   * freshly-loaded data and leave nothing to trigger another load.
   */
  const [scopedOrgId] = useActiveOrg();
  const [loadedOrgId, setLoadedOrgId] = useState(scopedOrgId);
  if (loadedOrgId !== scopedOrgId) {
    setLoadedOrgId(scopedOrgId);
    setRuns([]);
    setHydratedRuns([]);
    setLoadingRuns(true);
    setEscalations([]);
    setLoadingEscalations(true);
  }

  const refresh = useCallback(() => setNonce((n) => n + 1), []);
  const refreshEscalations = useCallback(
    () => setEscalationsNonce((n) => n + 1),
    [],
  );

  // Live sync: an assignment or resolution anyone on the team makes shows up
  // here immediately, not on the next poll - see the hook's own docstring
  // for why RLS, not this filter, is the actual security boundary.
  useOrgRealtime('escalations', activeOrgId, refreshEscalations);

  // Runs and their outcomes, on the same mechanism. The 4s poll below only
  // runs while a run's status is still `running`, so a call that lands after
  // a run settles - or a run started by a teammate - never reached the
  // dashboard until something else forced a refetch. Every count on that
  // screen is derived from these two tables, so this is what makes the whole
  // dashboard live rather than live-until-the-run-ends.
  useOrgRealtime('runs', activeOrgId, refresh);
  useOrgRealtime('call_outcomes', activeOrgId, refresh);

  // Runs are organisation-scoped - re-fetching on every org switch (not just on
  // mount, or when `refresh()`/the live poll bump `nonce`) is what makes the
  // dashboard, runs list, and escalations queue stop showing the previous org's
  // data the moment someone switches.
  useOrgScopedEffect(() => {
    // Wait for the connection to be established; fetching while the service is still
    // waking would just fail and clear the list.
    if (connection.phase !== 'up') return;

    let cancelled = false;
    let livePoll: ReturnType<typeof setTimeout> | null = null;

    async function load() {
      try {
        const summaries = await api.listRuns();
        if (cancelled) return;
        setRuns(summaries);

        const hydrated = await Promise.all(
          summaries
            .slice(0, HYDRATE_LIMIT)
            .map((summary) => api.getRun(summary.id).catch(() => null)),
        );
        if (cancelled) return;
        setHydratedRuns(hydrated.filter((run): run is Run => run !== null));

        // A run still going means the summary/list view will otherwise show a
        // stale "running" row for however long the visitor leaves the tab open.
        if (summaries.some((r) => r.status === 'running')) {
          livePoll = setTimeout(() => void load(), LIVE_POLL_MS);
        }
      } catch {
        // A failed refresh leaves the previous data in place rather than blanking the
        // dashboard - stale numbers are more useful than empty ones, and the
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

  // Same reasoning as the runs effect above: escalations are organisation-scoped, real rows now
  // (not derived from `outcomes`) - re-fetch on org switch, on `refresh()`,
  // and whenever the realtime subscription above says something changed.
  useOrgScopedEffect(() => {
    if (connection.phase !== 'up') return;
    let cancelled = false;
    api
      .listEscalations()
      .then((rows) => {
        if (cancelled) return;
        // Oldest first: the oldest escalation is the most expensive one.
        setEscalations(
          [...rows].sort((a, b) => a.created_at.localeCompare(b.created_at)),
        );
      })
      .catch(() => {
        // Leaves the previous list in place - same reasoning as the runs effect.
      })
      .finally(() => {
        if (!cancelled) setLoadingEscalations(false);
      });
    return () => {
      cancelled = true;
    };
  }, [connection.phase, escalationsNonce]);

  const outcomes = useMemo(
    () =>
      hydratedRuns
        .flatMap((run) => run.outcomes)
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [hydratedRuns],
  );

  const value = useMemo<AppState>(
    () => ({
      ...connection,
      runs,
      hydratedRuns,
      outcomes,
      escalations,
      loadingEscalations,
      refreshEscalations,
      loadingRuns,
      refresh,
    }),
    [
      connection,
      runs,
      hydratedRuns,
      outcomes,
      escalations,
      loadingEscalations,
      refreshEscalations,
      loadingRuns,
      refresh,
    ],
  );

  return (
    <AppStoreContext.Provider value={value}>
      {children}
    </AppStoreContext.Provider>
  );
}
