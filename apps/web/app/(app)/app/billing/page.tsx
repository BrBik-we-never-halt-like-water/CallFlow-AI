'use client';

import {
  NotWiredNotice,
  SettingsSection,
} from '@/components/app/settings-section';
import { SessionGate } from '@/components/app/session-gate';
import { PLANS } from '@/lib/pricing';
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
  const plan = PLANS.find((p) => p.id === profile.active.plan_id);
  const canReadOrgBilling = profile.permissions.includes('billing:read');

  if (!canReadOrgBilling) {
    return (
      <div className="flex flex-col gap-4">
        <SettingsSection
          title="Usage"
          description="What this organisation has called so far."
        >
          <NotWiredNotice>
            Per-person call budgets have been withdrawn while a new limits
            layer is designed, so there is nothing to show you here yet. Ask
            an owner or admin what this organisation is on.
          </NotWiredNotice>
        </SettingsSection>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Plan"
        description="What this organisation is on right now."
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="dash-num text-[1.125rem] font-semibold" style={{ color: 'var(--dash-figure)' }}>
            {plan?.name ?? profile.active.plan_id}
          </span>
          {plan ? (
            <span className="text-small text-text-dim">{plan.tagline}</span>
          ) : null}
        </div>
      </SettingsSection>

      <NotWiredNotice>
        There&apos;s no payment processor connected on this deployment yet -
        upgrading, downgrading, and adding a payment method aren&apos;t wired
        up. Daily call budgets and per-person credits have been withdrawn
        while a new limits layer is designed, so no usage is metered against
        this plan right now.
      </NotWiredNotice>
    </div>
  );
}
