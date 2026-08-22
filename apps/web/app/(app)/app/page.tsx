'use client';

import { useState } from 'react';
import { Dashboard } from '@/components/app/dashboard/dashboard';
import { ConnectionBanner } from '@/components/app/connection-banner';
import { api, type TeamPerformance, type VoiceAgent } from '@/lib/api';
import { useAppStore } from '@/lib/app-store';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession } from '@/lib/hooks/use-session';
import { canSeeTeam } from '@/components/app/dashboard/scope';

/**
 * The single-page operations dashboard.
 *
 * Data comes from three places: the app store (runs, outcomes, escalations,
 * already org-scoped and kept live), the team-performance endpoint (credits
 * per teammate), and the voice-agent list.
 *
 * Two panels have no endpoint behind them yet - calls per month and calls
 * per day. There is no time-series aggregation anywhere in the API, so both
 * are passed `null` and render an empty state saying so. They are not fed
 * derived or placeholder numbers: a credit meter or an activity chart that
 * shows invented figures is worse than one that shows a gap, because
 * nothing about it looks wrong.
 */
export default function DashboardPage() {
  const { runs, outcomes, escalations, phase, loadingRuns } = useAppStore();
  const session = useSession();
  const profile = session.status === 'signed-in' ? session.profile : null;

  const [members, setMembers] = useState<TeamPerformance[] | null>(null);
  const [agents, setAgents] = useState<VoiceAgent[] | null>(null);
  const [agentsLoaded, setAgentsLoaded] = useState(false);

  // Only a role that may read the team has an endpoint to call - asking
  // anyway would be a guaranteed 403 on every dashboard load.
  const teamVisible = canSeeTeam(profile);

  useOrgScopedEffect(() => {
    if (!teamVisible) {
      setMembers([]);
      return;
    }
    let cancelled = false;
    api
      .teamPerformance()
      .then((rows) => {
        if (!cancelled) setMembers(rows);
      })
      .catch(() => {
        if (!cancelled) setMembers([]);
      });
    return () => {
      cancelled = true;
    };
  }, [teamVisible]);

  useOrgScopedEffect(() => {
    let cancelled = false;
    api
      .listVoiceAgents()
      .then((rows) => {
        if (!cancelled) {
          setAgents(rows);
          setAgentsLoaded(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAgents([]);
          setAgentsLoaded(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loading = members === null || !agentsLoaded || loadingRuns;

  return (
    <div className="dash flex min-h-0 flex-1 flex-col">
      <ConnectionBanner phase={phase} />

      <Dashboard
        profile={profile}
        members={members}
        runs={runs}
        agents={agents}
        outcomes={outcomes}
        escalations={escalations}
        monthlyCalls={null}
        dailyCalls={null}
        loading={loading}
      />
    </div>
  );
}
