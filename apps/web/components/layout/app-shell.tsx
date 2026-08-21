'use client';

import {
  CaretUpDownIcon,
  CheckIcon,
  PlusIcon,
  XIcon,
} from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Fragment, useState } from 'react';
import { cn } from '@/lib/cn';
import { BrandLockup } from '@/components/brand/wordmark';
import { Mark } from '@/components/brand/mark';
import { Tag } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip } from '@/components/ui/tooltip';
import { VRule } from '@/components/ui/rule';
import { useActiveOrg } from '@/lib/hooks/use-active-org';
import { useOrganisations } from '@/lib/hooks/use-organisations';
import { hasRole } from '@/lib/hooks/use-permission';
import { useSidebarCollapsed } from '@/lib/hooks/use-sidebar-collapsed';
import { usePrefersReducedMotion } from '@/lib/hooks/use-external-store';
import { useAppStore } from '@/lib/app-store';
import { useChatUnreadCount } from '@/lib/hooks/use-chat-unread';
import { AppTabBar, OrgMark } from './app-nav';
import { DashSidebar } from '@/components/app/dashboard/dash-sidebar';
import { DashProfileMenu } from '@/components/app/dashboard/dash-profile-menu';
import { type SessionProfile, useSession } from '@/lib/hooks/use-session';
import { useSessionExpiry } from '@/lib/hooks/use-session-expiry';

/** Routes that get a focused destination, not the persistent app chrome - see
 *  `MinimalTopBar`. A single task to finish and leave, so the header would
 *  only be a way back to a screen the user didn't come here for. Each route
 *  names its own top-bar label, so adding a second route here can't leave it
 *  silently showing "Profile". */
const MINIMAL_CHROME_ROUTES: { path: string; label: string }[] = [
  { path: '/app/profile', label: 'Profile' },
];


/**
 * Dashboard shell: a fixed-width left sidebar (brand, org switcher, primary
 * nav) plus a header+content column that takes the remaining space. Below
 * `lg`, the sidebar disappears and `AppTabBar` carries navigation instead.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? '';
  const minimalRoute = MINIMAL_CHROME_ROUTES.find((r) => r.path === pathname);

  /**
   * Every page remounts when the active organisation changes.
   *
   * Pages keep their own state - lists, filters, a loaded record - and
   * re-fetching on switch does not clear any of it: the old organisation's
   * rows stay on screen until the new response arrives, and stay indefinitely
   * if it fails. Auditing ten pages for that would fix ten pages; keying the
   * subtree fixes the class, including pages not written yet, because a
   * remount resets every `useState` to its initial value (`ISSUES.md` #127).
   *
   * Keyed on `useActiveOrg()` - the value `useOrgScopedEffect` and the API
   * client's `X-Org-Id` both read - rather than the session's copy, which
   * only updates once `/me` returns and would remount *after* the new data
   * had already loaded, throwing it away.
   *
   * Losing scroll position and in-page state on a switch is the correct
   * outcome here: you are looking at a different tenant.
   */
  const [activeOrgId] = useActiveOrg();
  const scopedChildren = <Fragment key={activeOrgId}>{children}</Fragment>;

  // Tracks whether this AppShell instance has ever rendered a *different*
  // pathname than the one it's on now, so "close" (MinimalTopBar) can tell a
  // real in-app back-navigation apart from a same-tab link in from outside
  // the app - window.history.length alone can't distinguish those. Derived
  // during render (React's own pattern for "update state in response to a
  // prop change" - see lib/hooks/use-external-store.ts), not in an effect: an
  // effect would only set this a render late, exactly when MinimalTopBar's
  // very first render on the new route needs the answer.
  const [lastSeenPathname, setLastSeenPathname] = useState(pathname);
  const [hasPriorInAppPage, setHasPriorInAppPage] = useState(false);
  if (pathname !== lastSeenPathname) {
    setLastSeenPathname(pathname);
    setHasPriorInAppPage(true);
  }

  // Fixed-viewport routes: the page fills the screen and its panes scroll
  // internally, instead of the page scrolling. The dashboard's grid and the
  // chat's two panes both need a bounded height to divide - chat previously
  // approximated one with `calc(100dvh - 15rem)`, which guessed the header's
  // height and broke the moment the header changed (same failure class as
  // the dashboard's retired `--dash-chrome`).
  const isFixedViewport = pathname === '/app' || pathname === '/app/chat';
  const isDashboard = isFixedViewport;

  const { escalations } = useAppStore();
  const session = useSession();
  // Once, in the one component every authenticated page renders inside, rather
  // than in each screen's own load handler.
  useSessionExpiry();
  const profile = session.status === 'signed-in' ? session.profile : null;
  const chatUnreadCount = useChatUnreadCount();

  if (minimalRoute) {
    return (
      // `app-canvas` was missing here entirely - this branch has no sidebar
      // to keep visually separate from the content column (unlike the normal
      // layout below), so the whole wrapper gets it, not just a nested
      // column. `MinimalTopBar` already carries its own `app-chrome`, so
      // nesting it inside this doesn't change its look, only `<main>`'s.
      <div className="dash app-canvas flex min-h-dvh flex-col">
        <a href="#app-main" className="skip-link">
          Skip to content
        </a>

        <MinimalTopBar
          label={minimalRoute.label}
          canGoBack={hasPriorInAppPage}
        />

        <main
          id="app-main"
          className="mx-auto w-full max-w-(--container-app) flex-1 px-4 py-6 sm:px-6"
        >
          {scopedChildren}
        </main>
      </div>
    );
  }

  return (
    // `bg-dark-bg` is flat, deliberately no gradient - the purple lives on
    // the content column below (`app-canvas`), not here. This wrapper is
    // what actually shows through the sidebar's translucent glass (they're
    // flex siblings, not stacked), so it stays plain near-black, never
    // purple - see `.app-canvas`'s own comment in globals.css.
    // The dashboard is a fixed viewport, not a page: `h-dvh` + `overflow-hidden`
    // rather than `min-h-dvh`, because `min-h` only sets a floor - it leaves the
    // height unbounded, so a child's `h-full` has nothing to resolve against and
    // the grid grows to fit its content instead of fitting the screen.
    <div
      className={cn(
        'dash flex bg-surface',
        isDashboard ? 'h-dvh overflow-hidden' : 'min-h-dvh',
      )}
    >
      <a href="#app-main" className="skip-link">
        Skip to content
      </a>

      <AppSidebar
        profile={profile}
        refreshSession={session.refresh}
        escalationCount={escalations.length}
        chatUnreadCount={chatUnreadCount}
      />

      {/* No more per-page opt-in (`pathname === '/app' && 'app-canvas'`) -
          the dark canvas is the content column's resting background on
          every /app/* route now, not a dashboard-only accent. Page content
          itself (cards, tables) is still the light theme until D2-D4 rebuild
          it - the same "chrome/canvas dark, content light" transitional
          state this round's report documents as expected, just now visible
          on every route instead of only behind the sidebar. */}
      <div
        className={cn(
          'flex min-w-0 flex-1 flex-col',
          // The dashboard is a fixed viewport managing its own grid; every
          // other route scrolls normally. Both sit on the same flat canvas -
          // `app-canvas`'s indigo gradient is overridden to `--dash-bg`
          // inside `.dash` (see the bridge in globals.css), so the class is
          // kept only for the routes that still reference it in their own
          // styles rather than for the gradient it used to paint.
          isDashboard ? 'min-h-0 overflow-hidden' : 'app-canvas',
        )}
      >
        <main
          id="app-main"
          className={cn(
            'w-full flex-1',
            isDashboard
              ? 'flex min-h-0 flex-col'
              : 'mx-auto max-w-(--container-app) px-4 py-6 sm:px-6',
          )}
        >
          {scopedChildren}
        </main>

        <AppTabBar
          escalationCount={escalations.length}
          profile={profile}
          loading={session.status === 'loading'}
        />
      </div>
    </div>
  );
}

/**
 * The top bar for a minimal-chrome route: the lockup and a single close control,
 * nothing else. No sidebar, no breadcrumb, no tab bar - this is a destination
 * for one task, and closing it is the only navigation decision worth offering.
 */
function MinimalTopBar({
  label,
  canGoBack,
}: {
  label: string;
  canGoBack: boolean;
}) {
  const router = useRouter();

  function close() {
    // window.history.length alone isn't "has app history" - it counts every
    // entry in the tab's session history, including pages from a different
    // origin visited before the app ever loaded. A same-tab link straight in
    // from outside (an email, a Slack message) can have length > 1 and still
    // send router.back() out of the app entirely. canGoBack instead reflects
    // pages *this app instance actually rendered* (tracked in AppShell), so
    // it's only true when there's somewhere in-app to actually go back to.
    if (canGoBack) {
      router.back();
    } else {
      router.push('/app');
    }
  }

  return (
    <header
      className="sticky top-0 z-30 flex h-(--h-app-topbar) shrink-0 items-center gap-3 border-b px-4 sm:px-6"
      style={{
        background: 'var(--dash-sidebar)',
        borderColor: 'var(--dash-border)',
      }}
    >
      <Link
        href="/app"
        className="flex shrink-0 items-center gap-2.5 text-text"
      >
        <BrandLockup />
        <span className="sr-only">CallFlow AI dashboard</span>
      </Link>

      <VRule />
      <span className="text-small font-medium text-text-dim">{label}</span>

      <Tooltip content="Close" side="left">
        <button
          type="button"
          onClick={close}
          aria-label="Close and return to the dashboard"
          className="ml-auto flex size-9 items-center justify-center rounded-sm text-text-dim transition-colors hover:bg-surface-hover hover:text-text"
        >
          <XIcon aria-hidden className="size-4" />
        </button>
      </Tooltip>
    </header>
  );
}

/**
 * The left nav column: brand, organisation switcher, then every primary
 * destination as a vertical list. The only nav surface at `lg` and above -
 * `AppTabBar` (app-nav.tsx) is its equivalent below `lg`, where there's no
 * room for a fixed column.
 */
function AppSidebar({
  profile,
  refreshSession,
  escalationCount,
  chatUnreadCount,
}: {
  profile: SessionProfile | null;
  refreshSession: () => void;
  escalationCount: number;
  chatUnreadCount: number;
}) {
  const [collapsed, setCollapsed] = useSidebarCollapsed();
  const reducedMotion = usePrefersReducedMotion();
  // Organisation/Settings are owner+admin destinations - operators and
  // viewers get neither the sidebar link nor the account-menu one
  // (`UserMenu`), not just a read-only version of the page behind it.
  // The grouped nav (`DashSidebar`) carries Settings and the plan card, so
  // the shell's own footer list is always a duplicate of both.

  return (
    <aside
      className={cn(
        'sticky top-0 hidden h-dvh min-h-0 shrink-0 flex-col overflow-hidden border-r lg:flex',

        collapsed ? 'w-(--w-app-sidebar-collapsed)' : 'w-(--w-app-sidebar)',
        !reducedMotion &&
          'transition-[width] duration-(--dur-base) ease-(--ease-out)',
      )}
      style={{
        background: 'var(--dash-sidebar)',
        borderColor: 'var(--dash-border)',
      }}
    >
      <Link
        href="/app"
        className={cn(
          'flex h-(--h-app-topbar) shrink-0 items-center border-b text-text',
          collapsed ? 'justify-center border-transparent px-0' : 'gap-2 border-rule px-4',
        )}
      >
        {collapsed ? <Mark title={null} /> : <BrandLockup />}
        <span className="sr-only">CallFlow AI dashboard</span>
      </Link>

      {/* On the dashboard this slot is the account control, which names the
          organisation and switches it as well - two controls asking "which
          context am I in" cost a whole row of the nav column. */}
      <div
        className={cn(
          'p-3',
          collapsed ? 'flex justify-center' : '',
          // No rule under the account control on the dashboard: the card it
          // sits in already has its own edge, and a second line directly
          // beneath reads as a stray divider.
        )}
      >
        <DashProfileMenu
          profile={profile}
          refreshSession={refreshSession}
          collapsed={collapsed}
        />
      </div>

      <DashSidebar
        profile={profile}
        escalationCount={escalationCount}
        chatUnreadCount={chatUnreadCount}
        planName={null}
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed(!collapsed)}
      />

    </aside>
  );
}


/**
 * The one real place to switch, create, or manage organisations. Same
 * behaviour as before the header rebuild, now a full-width vertical trigger
 * instead of a compact horizontal one to match the sidebar it lives in.
 */
function SidebarOrgSwitcher({
  profile,
  refreshSession,
  collapsed,
}: {
  profile: SessionProfile | null;
  refreshSession: () => void;
  collapsed: boolean;
}) {
  const { orgs } = useOrganisations(profile);
  const [, setActiveOrgId] = useActiveOrg();

  const label = profile?.active.org_name ?? 'Loading…';

  if (!profile) {
    return (
      <span
        className={cn(
          'block h-9 rounded-md bg-surface-sunken',
          collapsed ? 'w-9' : 'w-full',
        )}
      />
    );
  }

  function switchOrg(orgId: string) {
    if (orgId === profile?.active.org_id) return;
    setActiveOrgId(orgId);
    refreshSession();
  }

  const list = orgs ?? [
    {
      id: profile.active.org_id,
      name: profile.active.org_name,
      slug: profile.active.org_slug,
      logo_url: profile.active.org_logo_url,
      role: profile.active.role,
    },
  ];

  // Belonging to more than one organisation is what entitles someone to move
  // between them - their role is not part of that question. This used to be
  // gated on owner/admin, which read reasonably ("managing several orgs is an
  // admin concern") and stranded people in practice: anyone whose role differs
  // between organisations - an owner of A who is a viewer in B - lost the
  // control the moment they arrived in B, with no way back short of clearing
  // site data (`ISSUES.md` #127). Role governs what you can do *inside* an
  // organisation; `GET /organisations` has always returned every membership to
  // every member, so the API never agreed with that gate either.
  //
  // The admin case stays in the condition because this menu is also where
  // "New organisation" lives: a single-org owner still needs it.
  const canSwitch = list.length > 1 || hasRole(profile, 'owner', 'admin');

  if (!canSwitch) {
    return (
      <div
        className={cn(
          'flex items-center gap-2 rounded-md text-small',
          collapsed ? 'size-9 justify-center' : 'w-full px-2 py-2',
        )}
      >
        <OrgMark name={label} logoUrl={profile.active.org_logo_url} size="sm" />
        {!collapsed && (
          <span className="min-w-0 flex-1 truncate font-medium text-text">
            {label}
          </span>
        )}
      </div>
    );
  }

  const trigger = (
    <button
      type="button"
      aria-label={`Switch organisation - currently ${label}`}
      className={cn(
        'flex cursor-pointer items-center gap-2 rounded-md text-small transition-colors hover:bg-surface-hover',
        collapsed ? 'size-9 justify-center' : 'w-full px-2 py-2',
      )}
    >
      <OrgMark
        name={label}
        logoUrl={profile.active.org_logo_url}
        size="sm"
      />
      {!collapsed && (
        <>
          <span className="min-w-0 flex-1 truncate text-left font-medium text-text">
            {label}
          </span>
          <CaretUpDownIcon
            aria-hidden
            className="size-3.5 shrink-0 text-text-mute"
          />
        </>
      )}
    </button>
  );

  return (
    <DropdownMenu>
      {collapsed ? (
        <Tooltip content={label} side="right">
          <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
        </Tooltip>
      ) : (
        <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      )}

      <DropdownMenuContent align="start" className="min-w-64">
        <DropdownMenuLabel>Organisations</DropdownMenuLabel>
        {list.map((org) => (
          <DropdownMenuItem key={org.id} onSelect={() => switchOrg(org.id)}>
            {org.id === profile.active.org_id ? (
              <CheckIcon
                aria-hidden
                weight="bold"
                className="size-4 shrink-0"
              />
            ) : (
              <span className="size-4 shrink-0" aria-hidden />
            )}
            <OrgMark name={org.name} logoUrl={org.logo_url} size="sm" />
            <span className="min-w-0 flex-1 truncate">{org.name}</span>
            <Tag>{org.role}</Tag>
          </DropdownMenuItem>
        ))}

        <DropdownMenuSeparator />

        <DropdownMenuItem>
          <Link
            href="/app/organisation/new"
            className="flex flex-1 items-center gap-2"
          >
            <PlusIcon aria-hidden className="size-4" />
            New organisation
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

