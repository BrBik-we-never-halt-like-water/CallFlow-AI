'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { PageHeader } from '@/components/app/page-header';
import { SessionGate } from '@/components/app/session-gate';
import { TabPanel, Tabs } from '@/components/ui/disclosure';
import { Skeleton } from '@/components/ui/skeleton';
import { useSession, type SessionProfile } from '@/lib/hooks/use-session';
import {
  OrganisationPane,
  SharingPane,
  TeamPane,
} from '@/app/(app)/app/organisation/page';
import {
  ChangePasswordPanel,
  ProfileDetails,
  SignOutPanel,
} from '@/app/(app)/app/profile/page';
import { ApiKeysContent } from '@/app/(app)/app/settings/api-keys/page';

/**
 * Settings, as tabs - the same shape the Agents page uses.
 *
 * Organisation and Team used to live at `/app/organisation`, which the
 * sidebar never linked to: the only route in was the account menu's
 * submenu, so inviting a teammate was effectively unreachable. Putting both
 * here alongside Profile means one destination holds everything about *you*
 * and *your workspace*, and the sidebar's existing Settings entry reaches
 * all of it.
 *
 * The panes are imported from their original pages rather than moved.
 * `/app/organisation` and `/app/profile` still resolve - the account menu
 * links to them, and so may a bookmark - so duplicating ~900 lines to
 * relocate them would leave two copies to keep in step.
 */

const TAB_VALUES = [
  'organisation',
  'profile',
  'team',
  'sharing',
  'api-keys',
] as const;
type TabValue = (typeof TAB_VALUES)[number];

export default function SettingsPage() {
  return (
    <Suspense fallback={<SettingsFallback />}>
      <SettingsContent />
    </Suspense>
  );
}

function SettingsContent() {
  const session = useSession();
  const searchParams = useSearchParams();
  // Deep-linkable: `?tab=team` is what the "Invite a teammate" prompt on the
  // dashboard's credits card points at, so the link lands on the pane that
  // actually does the thing.
  const requested = searchParams.get('tab');
  const [tab, setTab] = useState<TabValue | null>(
    (TAB_VALUES as readonly string[]).includes(requested ?? '')
      ? (requested as TabValue)
      : null,
  );

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Settings" />

      <SessionGate session={session}>
        {(profile) => {
          const tabs = visibleTabs(profile);
          // Falls back to the first tab this role can actually see, rather
          // than a fixed default an operator would find hidden.
          const active =
            tab && tabs.some((t) => t.value === tab)
              ? tab
              : (tabs[0]?.value as TabValue);

          return (
            <Tabs
              value={active}
              onValueChange={(value) => setTab(value as TabValue)}
              tabs={tabs}
            >
              <TabPanel value="organisation" className="max-w-2xl pt-5">
                <OrganisationPane profile={profile} refresh={session.refresh} />
              </TabPanel>

              <TabPanel value="profile" className="max-w-2xl pt-5">
                <div className="flex flex-col gap-4">
                  <ProfileDetails profile={profile} refresh={session.refresh} />
                  <ChangePasswordPanel />
                  <SignOutPanel />
                </div>
              </TabPanel>

              <TabPanel value="team" className="max-w-2xl pt-5">
                <TeamPane profile={profile} />
              </TabPanel>

              <TabPanel value="sharing" className="max-w-2xl pt-5">
                <SharingPane profile={profile} />
              </TabPanel>

              <TabPanel value="api-keys" className="max-w-2xl pt-5">
                <ApiKeysContent profile={profile} />
              </TabPanel>
            </Tabs>
          );
        }}
      </SessionGate>
    </div>
  );
}

/**
 * Organisation and Sharing are owner/admin concerns; Team and Profile are
 * everyone's. A tab whose pane would only show a permission refusal is not
 * shown at all - the same rule the sidebar already applies to its own
 * destinations.
 */
function visibleTabs(profile: SessionProfile) {
  const canManageOrg = profile.permissions.includes('org:update');
  const canReadKeys = profile.permissions.includes('api_keys:read');
  return [
    ...(canManageOrg
      ? [{ value: 'organisation', label: 'Organisation' }]
      : []),
    { value: 'profile', label: 'Profile' },
    { value: 'team', label: 'Teammates' },
    { value: 'sharing', label: 'Sharing' },
    ...(canReadKeys ? [{ value: 'api-keys', label: 'API keys' }] : []),
  ];
}

function SettingsFallback() {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Settings" />
      <Skeleton className="h-9 w-64 rounded-full" />
      <Skeleton className="h-64 w-full max-w-2xl rounded-xl" />
    </div>
  );
}
