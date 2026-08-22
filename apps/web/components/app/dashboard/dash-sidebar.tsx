'use client';

import type { Icon } from '@phosphor-icons/react';
import {
  AddressBookIcon,
  BroadcastIcon,
  CaretDoubleLeftIcon,
  ChatCircleIcon,
  CreditCardIcon,
  GaugeIcon,
  GearSixIcon,
  PlugsConnectedIcon,
  RobotIcon,
  ShieldCheckIcon,
  UserFocusIcon,
} from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/cn';
import { isActive } from '@/components/layout/app-nav';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { Tooltip } from '@/components/ui/tooltip';
import { DottedWave } from './dotted-wave';
import { hasPermission, type SessionProfileLike } from './scope';

/**
 * The dashboard's left column.
 *
 * Grouped under quiet section labels rather than one flat list: nine
 * destinations in a single column reads as a wall, and the groups say
 * something true about the product - what you operate, how you talk to
 * people, what the platform holds.
 *
 * Items whose permission the signed-in role lacks are not rendered. A
 * destination you cannot use is not a destination.
 */

interface DashNavItem {
  label: string;
  href: string;
  icon: Icon;
  /** Omitted means every role sees it. */
  permission?: string;
}

const SECTIONS: { label: string; items: DashNavItem[] }[] = [
  {
    label: 'Workspace',
    items: [
      { label: 'Dashboard', href: '/app', icon: GaugeIcon },
      { label: 'Agents', href: '/app/agentic', icon: RobotIcon },
      { label: 'Runs', href: '/app/runs', icon: BroadcastIcon },
      {
        label: 'Needs a person',
        href: '/app/escalations',
        icon: UserFocusIcon,
      },
    ],
  },
  {
    label: 'Communication',
    items: [{ label: 'Messages', href: '/app/chat', icon: ChatCircleIcon }],
  },
  {
    label: 'Platform',
    items: [
      {
        label: 'Integrations',
        href: '/app/integrations',
        icon: PlugsConnectedIcon,
        permission: 'integrations:read',
      },
      { label: 'Data', href: '/app/contacts', icon: AddressBookIcon },
      {
        label: 'Billing',
        href: '/app/billing',
        icon: CreditCardIcon,
        permission: 'billing:read',
      },
      { label: 'Settings', href: '/app/settings', icon: GearSixIcon },
    ],
  },
];

/**
 * CallFlow staff only, and absent from `SECTIONS` entirely rather than
 * filtered out of it - a destination nobody but staff has must not be
 * something every other consumer of that list has to remember to exclude.
 * Its own section, not folded into "Platform" above: that label already
 * means "what the platform holds" for a customer, and a staff-only link
 * among Integrations/Billing would read as a feature every org has.
 *
 * Renders on `profile.is_platform_admin` from `GET /me`, which is display
 * only - the route itself 404s for anyone without a `platform_admins` row,
 * and the database checks again below that (`docs/PLATFORM_ADMIN.md` §2).
 */
const STAFF_SECTION: { label: string; items: DashNavItem[] } = {
  label: 'Staff',
  items: [{ label: 'Platform admin', href: '/app/platform', icon: ShieldCheckIcon }],
};

export function DashSidebar({
  profile,
  escalationCount,
  chatUnreadCount,
  planName,
  collapsed = false,
  onToggleCollapsed,
  className,
}: {
  profile: SessionProfileLike | null;
  escalationCount: number;
  chatUnreadCount: number;
  planName: string | null;
  /** Icon rail. Same destinations, same order, labels as tooltips - the
   *  collapsed sidebar used to fall back to an entirely different nav list,
   *  so collapsing changed which pages were reachable. */
  collapsed?: boolean;
  /** Omitted when the shell offers no collapse control. */
  onToggleCollapsed?: () => void;
  className?: string;
}) {
  const pathname = usePathname() ?? '';
  const sections = profile?.is_platform_admin
    ? [...SECTIONS, STAFF_SECTION]
    : SECTIONS;

  return (
    // The nav list scrolls; the plan card and theme control do not. Both were
    // inside the scrolling region before, which pushed them off-screen and put
    // a scrollbar through the whole column - the reason the sidebar looked
    // truncated rather than complete.
    <div className={cn('flex min-h-0 flex-1 flex-col', className)}>
      <nav
        aria-label="Primary"
        className={cn(
          'dash-scroll flex min-h-0 flex-1 flex-col gap-4 py-3',
          collapsed ? 'items-center px-2' : 'px-3',
        )}
      >
        {sections.map((section) => {
          const items = section.items.filter(
            (item) => !item.permission || hasPermission(profile, item.permission),
          );
          if (items.length === 0) return null;

          return (
            <div
              key={section.label}
              className={cn(
                'flex flex-col gap-0.5',
                collapsed && 'items-center',
              )}
            >
              {/* The section label becomes a hairline on the rail: the
                  grouping still reads, without text there is no room for. */}
              {collapsed ? (
                <span
                  aria-hidden
                  className="mb-1 h-px w-5"
                  style={{ background: 'var(--dash-border)' }}
                />
              ) : (
                <p
                  className="px-2.5 pb-1 text-[0.5625rem] font-semibold uppercase tracking-[0.12em]"
                  style={{ color: 'var(--dash-text-mute)' }}
                >
                  {section.label}
                </p>
              )}

              {items.map((item) => {
                const active = isActive(pathname, item.href);
                const badge =
                  item.href === '/app/escalations'
                    ? escalationCount
                    : item.href === '/app/chat'
                      ? chatUnreadCount
                      : 0;

                const link = (
                  <Link
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      'relative flex items-center rounded-[7px] text-[0.8125rem] transition-colors',
                      collapsed ? 'size-9 justify-center' : 'gap-2.5 px-2.5 py-2',
                    )}
                    style={
                      active
                        ? {
                            background: 'var(--dash-brand-soft)',
                            color: 'var(--dash-brand-ink)',
                            fontWeight: 500,
                          }
                        : { color: 'var(--dash-text-dim)' }
                    }
                  >
                    <item.icon
                      aria-hidden
                      weight={active ? 'fill' : 'regular'}
                      className="size-4 shrink-0"
                    />
                    {!collapsed ? (
                      <span className="min-w-0 flex-1 truncate">
                        {item.label}
                      </span>
                    ) : null}

                    {badge > 0 ? (
                      collapsed ? (
                        <span
                          aria-hidden
                          className="absolute right-0.5 top-0.5 size-2 rounded-full"
                          style={{ background: 'var(--dash-brand)' }}
                        />
                      ) : (
                        <span
                          className="dash-num shrink-0 rounded-full px-1.5 text-[0.625rem] font-semibold leading-4"
                          style={{
                            background: 'var(--dash-brand)',
                            color: 'var(--dash-brand-on)',
                          }}
                        >
                          {badge > 99 ? '99+' : badge}
                        </span>
                      )
                    ) : null}
                    {badge > 0 && collapsed ? (
                      <span className="sr-only">{badge} waiting</span>
                    ) : null}
                  </Link>
                );

                // Collapsed, the label has nowhere to render - the tooltip is
                // the only thing naming the destination, so it is required
                // rather than decorative.
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
          );
        })}

      </nav>

      {/* Theme, collapse, plan. The account row moved to the top of the
          sidebar (`DashProfileMenu`), where it also names the organisation -
          keeping a copy here would be the same identity stated twice. */}
      <div
        className={cn(
          'flex shrink-0 flex-col gap-2 py-2.5',
          collapsed ? 'items-center px-2' : 'px-2.5',
        )}
      >
        <div
          className={cn(
            'relative flex items-center justify-center',
            collapsed && 'hidden',
          )}
        >
          <ThemeToggle />
          {onToggleCollapsed ? (
            <button
              type="button"
              onClick={onToggleCollapsed}
              aria-label="Collapse sidebar"
              className="absolute right-0 flex size-7 shrink-0 items-center justify-center rounded-[7px] transition-colors"
              style={{ color: 'var(--dash-text-mute)' }}
            >
              <CaretDoubleLeftIcon aria-hidden className="size-3.5" />
            </button>
          ) : null}
        </div>

        {collapsed ? (
          onToggleCollapsed ? (
            <Tooltip content="Expand sidebar" side="right">
              <button
                type="button"
                onClick={onToggleCollapsed}
                aria-label="Expand sidebar"
                className="flex size-9 items-center justify-center rounded-[7px] transition-colors"
                style={{ color: 'var(--dash-text-mute)' }}
              >
                <CaretDoubleLeftIcon
                  aria-hidden
                  className="size-3.5 rotate-180"
                />
              </button>
            </Tooltip>
          ) : null
        ) : (
          <PlanCard
            planName={planName}
            canUpgrade={hasPermission(profile, 'billing:write')}
          />
        )}
      </div>
    </div>
  );
}

/**
 * The plan card. Names the current plan and offers the upgrade only to
 * someone who can actually buy one - an operator seeing "Upgrade" and
 * landing on a page they cannot act on is worse than not seeing it.
 *
 * No usage bar here: credits are their own card on the dashboard, and
 * repeating the meter in the sidebar would make it look like two different
 * measurements.
 */
function PlanCard({
  planName,
  canUpgrade,
}: {
  planName: string | null;
  canUpgrade: boolean;
}) {
  return (
    <div
      className="dash-branded dash-wave-host flex flex-col gap-2 rounded-[10px] p-3"
      style={{ border: '1px solid var(--dash-border)' }}
    >
      <DottedWave rows={3} alpha={0.3} />
      <div>
        <p
          className="text-[0.5625rem] font-semibold uppercase tracking-[0.12em]"
          style={{ color: 'var(--dash-text-mute)' }}
        >
          Current plan
        </p>
        <p
          className="mt-0.5 text-[0.8125rem] font-semibold"
          style={{ color: 'var(--dash-text)' }}
        >
          {planName ?? 'Free'}
        </p>
      </div>

      {canUpgrade ? (
        <Link
          href="/app/billing"
          className="flex h-8 items-center justify-center rounded-[7px] text-[0.75rem] font-medium transition-colors"
          style={{
            background: 'var(--dash-brand)',
            color: 'var(--dash-brand-on)',
          }}
        >
          Upgrade plan
        </Link>
      ) : null}
    </div>
  );
}
