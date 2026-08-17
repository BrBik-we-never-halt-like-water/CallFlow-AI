'use client';

import type { Icon } from '@phosphor-icons/react';
import {
  BuildingsIcon,
  CaretUpDownIcon,
  CheckIcon,
  GearSixIcon,
  PlusIcon,
  SidebarSimpleIcon,
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
import { AppTabBar, isActive, OrgMark, PRIMARY_NAV_ITEMS } from './app-nav';
import { type SessionProfile, useSession } from '@/lib/hooks/use-session';

/** Routes that get a focused destination, not the persistent app chrome - see
 *  `MinimalTopBar`. A single task to finish and leave, so the header would
 *  only be a way back to a screen the user didn't come here for. Each route
 *  names its own top-bar label, so adding a second route here can't leave it
 *  silently showing "Profile". */
const MINIMAL_CHROME_ROUTES: { path: string; label: string }[] = [
  { path: '/app/profile', label: 'Profile' },
];

/**
 * Organisation, Settings - two of the three destinations `UserMenu`'s account
 * dropdown already covers (user-menu.tsx), offered a second way for anyone
 * working from the desktop sidebar. The third, Profile, gets its own bespoke
 * row instead of a slot in this list (`ProfileFooterLink`, below) - it needs
 * to show the signed-in person's actual avatar and name, not a generic icon
 * and label. Deliberately *not* a replacement for `UserMenu`: with `AppTopBar`
 * removed entirely (the user asked for no persistent top bar), `AppSidebar`
 * is still `lg:flex`-only and still disappears below that breakpoint, where
 * `AppTabBar` (app-nav.tsx) now carries its own account-menu trigger instead
 * (`UserMenu`'s `variant="tab"`) rather than losing account access on mobile
 * altogether. Sign out itself stays `UserMenu`-only everywhere: this list is
 * destinations, not actions, and duplicating a destructive action across two
 * surfaces is worse than duplicating a couple of plain links.
 */
const SIDEBAR_FOOTER_ITEMS: { label: string; href: string; icon: Icon }[] = [
  { label: 'Organisation', href: '/app/organisation', icon: BuildingsIcon },
  { label: 'Settings', href: '/app/settings', icon: GearSixIcon },
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

  const { escalations } = useAppStore();
  const session = useSession();
  const profile = session.status === 'signed-in' ? session.profile : null;
  const chatUnreadCount = useChatUnreadCount();

  if (minimalRoute) {
    return (
      // `app-canvas` was missing here entirely - this branch has no sidebar
      // to keep visually separate from the content column (unlike the normal
      // layout below), so the whole wrapper gets it, not just a nested
      // column. `MinimalTopBar` already carries its own `app-chrome`, so
      // nesting it inside this doesn't change its look, only `<main>`'s.
      <div className="app-canvas flex min-h-dvh flex-col">
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
    <div className="flex min-h-dvh bg-surface">
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
      <div className="app-canvas flex min-w-0 flex-1 flex-col">
        <main
          id="app-main"
          className="mx-auto w-full max-w-(--container-app) flex-1 px-4 py-6 sm:px-6"
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
    <header className="app-chrome sticky top-0 z-30 flex h-(--h-app-topbar) shrink-0 items-center gap-3 border-b px-4 sm:px-6">
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
  const pathname = usePathname() ?? '';
  const [collapsed, setCollapsed] = useSidebarCollapsed();
  const reducedMotion = usePrefersReducedMotion();
  // Organisation/Settings are owner+admin destinations - operators and
  // viewers get neither the sidebar link nor the account-menu one
  // (`UserMenu`), not just a read-only version of the page behind it.
  const footerItems = hasRole(profile, 'owner', 'admin')
    ? SIDEBAR_FOOTER_ITEMS
    : [];

  return (
    <aside
      className={cn(
        'app-chrome sticky top-0 hidden h-dvh shrink-0 flex-col border-r lg:flex',
        collapsed ? 'w-(--w-app-sidebar-collapsed)' : 'w-(--w-app-sidebar)',
        !reducedMotion &&
          'transition-[width] duration-(--dur-base) ease-(--ease-out)',
      )}
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

      <div
        className={cn(
          'border-b p-3',
          collapsed ? 'flex justify-center border-transparent' : 'border-rule',
        )}
      >
        <SidebarOrgSwitcher
          profile={profile}
          refreshSession={refreshSession}
          collapsed={collapsed}
        />
      </div>

      <nav
        aria-label="Primary"
        className={cn(
          'flex flex-1 flex-col gap-1 overflow-y-auto p-3',
          collapsed && 'items-center',
        )}
      >
        {PRIMARY_NAV_ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          const badge = item.href === '/app/escalations' ? escalationCount : 0;
          // A plain unread count, not a lamp colour - this is a chat inbox
          // total, not call/run/escalation state, so it takes --primary (the
          // one non-lamp colour) rather than the flare dot below.
          const chatBadge = item.href === '/app/chat' ? chatUnreadCount : 0;

          const link = (
            <Link
              href={item.href}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'relative flex items-center gap-2.5 rounded-md text-small transition-colors duration-(--dur-micro) hover:bg-surface-hover',
                collapsed ? 'size-10 justify-center' : 'px-2.5 py-2',
                active
                  ? 'font-medium text-text'
                  : 'text-text-mute hover:text-text',
              )}
            >
              <item.icon
                aria-hidden
                weight={active ? 'fill' : 'regular'}
                className="size-4.5 shrink-0"
              />
              {!collapsed && (
                <span className="min-w-0 flex-1 truncate">{item.label}</span>
              )}
              {/* Always a plain dot, never a numeric pill, in either sidebar
                  state - the only persistently-coloured element in the
                  sidebar, because it is the only thing in the product that
                  needs immediate human action. A count of zero renders
                  nothing at all - not a grey dot. The exact count still
                  reaches a screen reader either way. */}
              {badge > 0 ? (
                <span
                  aria-hidden
                  className="absolute right-1.5 top-1.5 size-2 rounded-full"
                  style={{ background: 'var(--lamp-flare)' }}
                />
              ) : null}
              {badge > 0 ? (
                <span className="sr-only">{badge} waiting for a person</span>
              ) : null}
              {chatBadge > 0 ? (
                <span
                  aria-hidden
                  className="absolute right-1 top-1 flex min-w-4 items-center justify-center rounded-full px-1 text-[0.625rem] font-bold leading-4 text-primary-on"
                  style={{ background: 'var(--primary)' }}
                >
                  {chatBadge > 99 ? '99+' : chatBadge}
                </span>
              ) : null}
              {chatBadge > 0 ? (
                <span className="sr-only">{chatBadge} unread messages</span>
              ) : null}
            </Link>
          );

          return collapsed ? (
            <Tooltip key={item.href} content={item.label} side="right">
              {link}
            </Tooltip>
          ) : (
            <span key={item.href} className="contents">
              {link}
            </span>
          );
        })}
      </nav>

      {/* Plain icon+label rows, no filled pill even when active - the same
          "weight/colour shift only" active-state rule every other nav
          surface in this product follows (DESIGN_NOTES §14), not the
          primary list's look above it. See SIDEBAR_FOOTER_ITEMS and
          ProfileFooterLink for why these exist alongside, not instead of,
          UserMenu. */}
      <div
        className={cn(
          'flex flex-col gap-1 border-t p-3',
          collapsed ? 'items-center border-transparent' : 'border-rule',
        )}
      >
        <ProfileFooterLink
          profile={profile}
          collapsed={collapsed}
          active={isActive(pathname, '/app/profile')}
        />

        {footerItems.map((item) => {
          const active = isActive(pathname, item.href);

          const link = (
            <Link
              href={item.href}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'flex items-center gap-2.5 rounded-md text-small transition-colors duration-(--dur-micro) hover:bg-surface-hover',
                collapsed ? 'size-10 justify-center' : 'px-2.5 py-2',
                active
                  ? 'font-medium text-text'
                  : 'text-text-mute hover:text-text',
              )}
            >
              <item.icon
                aria-hidden
                weight={active ? 'fill' : 'regular'}
                className="size-4.5 shrink-0"
              />
              {!collapsed && (
                <span className="min-w-0 flex-1 truncate">{item.label}</span>
              )}
            </Link>
          );

          return collapsed ? (
            <Tooltip key={item.href} content={item.label} side="right">
              {link}
            </Tooltip>
          ) : (
            <span key={item.href} className="contents">
              {link}
            </span>
          );
        })}
      </div>

      <div
        className={cn(
          'border-t p-3',
          collapsed ? 'flex justify-center border-transparent' : 'border-rule',
        )}
      >
        <Tooltip
          content={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          side="right"
        >
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-pressed={collapsed}
            className={cn(
              'flex items-center gap-2.5 rounded-md text-small text-text-mute transition-colors hover:bg-surface-hover hover:text-text',
              collapsed ? 'size-10 justify-center' : 'w-full px-2.5 py-2',
            )}
          >
            <SidebarSimpleIcon
              aria-hidden
              weight={collapsed ? 'fill' : 'regular'}
              className="size-4.5 shrink-0"
            />
            {!collapsed && <span>Collapse sidebar</span>}
          </button>
        </Tooltip>
      </div>
    </aside>
  );
}

/**
 * The sidebar footer's Profile row - the signed-in person's actual avatar
 * (or their initial, the same fallback `OrgMark` already uses for a
 * logo-less organisation - not a new pattern) plus their name, instead of a
 * generic icon and the word "Profile". Collapsed, the name drops the same
 * way every other row's label does, leaving just the photo - still enough
 * to recognise at a glance, which a generic person-outline icon never was.
 */
function ProfileFooterLink({
  profile,
  collapsed,
  active,
}: {
  profile: SessionProfile | null;
  collapsed: boolean;
  active: boolean;
}) {
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

  const label = profile.name?.trim() || profile.email;
  const initial = label.charAt(0).toUpperCase();

  const avatar = profile.avatar_url ? (
    <img
      src={profile.avatar_url}
      alt=""
      className="size-6 shrink-0 rounded-full border border-rule object-cover"
    />
  ) : (
    <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-rule bg-surface-sunken font-mono text-label text-text">
      {initial}
    </span>
  );

  const link = (
    <Link
      href="/app/profile"
      aria-current={active ? 'page' : undefined}
      className={cn(
        'flex items-center gap-2.5 rounded-md text-small transition-colors duration-(--dur-micro) hover:bg-surface-hover',
        collapsed ? 'size-10 justify-center' : 'px-2.5 py-2',
        active ? 'font-medium text-text' : 'text-text-mute hover:text-text',
      )}
    >
      {avatar}
      {!collapsed && <span className="min-w-0 flex-1 truncate">{label}</span>}
    </Link>
  );

  return collapsed ? (
    <Tooltip content={label} side="right">
      {link}
    </Tooltip>
  ) : (
    <span className="contents">{link}</span>
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

