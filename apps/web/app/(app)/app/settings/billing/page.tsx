'use client';

import {
  NotWiredNotice,
  SettingsSection,
} from '@/components/app/settings-section';
import { SessionGate } from '@/components/app/session-gate';
import { Skeleton } from '@/components/ui/skeleton';
import { formatNumber } from '@/lib/format';
import { PLANS } from '@/lib/pricing';
import { useAppStore } from '@/lib/app-store';
import { useSession, type SessionProfile } from '@/lib/hooks/use-session';

export default function BillingSettingsPage() {
  const session = useSession();
  return (
    <SessionGate session={session}>
      {(profile) => <BillingContent profile={profile} />}
    </SessionGate>
  );
}

function BillingContent({ profile }: { profile: SessionProfile }) {
  const { safetySettings } = useAppStore();
  const plan = PLANS.find((p) => p.id === profile.active.plan_id);

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Plan"
        description="What this organisation is on right now."
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="text-h3 font-medium text-text">
            {plan?.name ?? profile.active.plan_id}
          </span>
          {plan ? (
            <span className="text-small text-text-dim">{plan.tagline}</span>
          ) : null}
        </div>
      </SettingsSection>

      <SettingsSection
        title="Usage today"
        description="The same limiter every run passes through - nothing here is estimated."
      >
        {!safetySettings ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-2 w-full" />
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-h2 tabular-nums text-text">
                {formatNumber(safetySettings.used_today)}
              </span>
              <span className="text-body text-text-dim">
                of {formatNumber(safetySettings.daily_budget)} calls used
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken">
              <div
                className="h-full rounded-full bg-surface-inverse"
                style={{
                  width: `${Math.min(100, (safetySettings.used_today / Math.max(1, safetySettings.daily_budget)) * 100)}%`,
                }}
              />
            </div>
            <p className="text-small text-text-mute">
              Resets daily. Paced at {safetySettings.calls_per_window} calls per{' '}
              {Math.round(safetySettings.window_minutes)} minutes.
            </p>
          </div>
        )}
      </SettingsSection>

      <NotWiredNotice>
        There&apos;s no payment processor connected on this deployment yet -
        upgrading, downgrading, and adding a payment method aren&apos;t wired
        up. What&apos;s shown above is real usage against your
        organisation&apos;s actual daily budget.
      </NotWiredNotice>
    </div>
  );
}
