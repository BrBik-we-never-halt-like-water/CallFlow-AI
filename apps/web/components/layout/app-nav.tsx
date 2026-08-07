"use client";

import type { Icon } from "@phosphor-icons/react";
import {
  AddressBookIcon,
  BroadcastIcon,
  GaugeIcon,
  GearSixIcon,
  MegaphoneIcon,
  SidebarSimpleIcon,
  UserFocusIcon,
} from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { Tooltip } from "@/components/ui/tooltip";

export interface NavItem {
  label: string;
  href: string;
  icon: Icon;
  /** Only `Needs a person` carries one. */
  badge?: number;
}

export const NAV_ITEMS: Omit<NavItem, "badge">[] = [
  { label: "Dashboard", href: "/app", icon: GaugeIcon },
  { label: "Campaigns", href: "/app/campaigns", icon: MegaphoneIcon },
  { label: "Runs", href: "/app/runs", icon: BroadcastIcon },
  { label: "Needs a person", href: "/app/escalations", icon: UserFocusIcon },
  { label: "Contacts", href: "/app/contacts", icon: AddressBookIcon },
  { label: "Settings", href: "/app/settings", icon: GearSixIcon },
];

/** The four destinations that become the mobile tab bar. */
const MOBILE_ITEMS = ["/app", "/app/runs", "/app/escalations", "/app/campaigns"];

function isActive(pathname: string, href: string): boolean {
  if (href === "/app") return pathname === "/app";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppNav({
  collapsed,
  onToggleCollapsed,
  escalationCount,
  orgName,
}: {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  escalationCount: number;
  orgName: string | null;
}) {
  const pathname = usePathname() ?? "";

  return (
    <nav
      aria-label="Dashboard"
      className={cn(
        "hidden shrink-0 flex-col border-r border-rule bg-surface-raised md:flex",
        "transition-[width] duration-(--dur-base) ease-(--ease-out)",
        collapsed ? "w-(--w-app-nav-collapsed)" : "w-(--w-app-nav)",
      )}
    >
      <OrgSwitcher collapsed={collapsed} orgName={orgName} />

      <ul className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto p-2">
        {NAV_ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          const badge = item.href === "/app/escalations" ? escalationCount : 0;

          const link = (
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex h-10 items-center gap-2.5 rounded-sm px-2.5",
                "text-small transition-colors duration-(--dur-micro)",
                active
                  ? "bg-surface-sunken font-medium text-text"
                  : "text-text-dim hover:bg-surface-hover hover:text-text",
                collapsed && "justify-center px-0",
              )}
            >
              <item.icon
                aria-hidden
                weight={active ? "fill" : "regular"}
                className="size-4.5 shrink-0"
              />
              {!collapsed ? <span className="min-w-0 flex-1 truncate">{item.label}</span> : null}

              {/* The only persistently-coloured element in the nav, because it is the
                  only thing in the product that needs immediate human action. A count
                  of zero renders nothing at all — not a grey zero. */}
              {badge > 0 ? (
                <span
                  className={cn(
                    "inline-flex min-w-5 items-center justify-center rounded-full px-1.5 py-0.5",
                    "font-mono text-label tabular-nums text-white",
                    collapsed && "absolute right-1 top-1 min-w-4 px-1",
                  )}
                  style={{ background: "var(--lamp-flare)" }}
                >
                  {badge > 99 ? "99+" : badge}
                  <span className="sr-only"> waiting for a person</span>
                </span>
              ) : null}
            </Link>
          );

          return (
            <li key={item.href} className={cn(collapsed && "relative")}>
              {collapsed ? (
                <Tooltip
                  content={
                    badge > 0 ? `${item.label} — ${badge} waiting` : item.label
                  }
                  side="right"
                >
                  {link}
                </Tooltip>
              ) : (
                link
              )}
            </li>
          );
        })}
      </ul>

      <div className="border-t border-rule p-2">
        <button
          type="button"
          onClick={onToggleCollapsed}
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          className={cn(
            "flex h-10 w-full cursor-pointer items-center gap-2.5 rounded-sm px-2.5",
            "text-small text-text-mute transition-colors hover:bg-surface-hover hover:text-text",
            collapsed && "justify-center px-0",
          )}
        >
          <SidebarSimpleIcon aria-hidden className="size-4.5 shrink-0" />
          {!collapsed ? <span>Collapse</span> : null}
        </button>
      </div>
    </nav>
  );
}

function OrgSwitcher({
  collapsed,
  orgName,
}: {
  collapsed: boolean;
  orgName: string | null;
}) {
  const label = orgName ?? "Loading…";
  return (
    <div className="border-b border-rule p-2">
      <button
        type="button"
        className={cn(
          "flex h-10 w-full cursor-pointer items-center gap-2.5 rounded-sm px-2.5",
          "text-small transition-colors hover:bg-surface-hover",
          collapsed && "justify-center px-0",
        )}
      >
        {/* Initial rather than a logo: an organisation that has not uploaded one gets a
            consistent mark instead of a broken image. */}
        <span className="flex size-6 shrink-0 items-center justify-center rounded-xs border border-rule bg-surface-sunken font-mono text-label text-text">
          {label.charAt(0).toUpperCase()}
        </span>
        {!collapsed ? (
          <span className="min-w-0 flex-1 truncate text-left font-medium text-text">
            {label}
          </span>
        ) : null}
      </button>
    </div>
  );
}

/** Bottom tab bar. Mobile only — ops managers check escalations from their phone. */
export function AppTabBar({ escalationCount }: { escalationCount: number }) {
  const pathname = usePathname() ?? "";
  const items = NAV_ITEMS.filter((item) => MOBILE_ITEMS.includes(item.href));

  return (
    <nav
      aria-label="Dashboard"
      className="sticky bottom-0 z-30 flex shrink-0 border-t border-rule bg-surface-raised md:hidden"
    >
      {items.map((item) => {
        const active = isActive(pathname, item.href);
        const badge = item.href === "/app/escalations" ? escalationCount : 0;

        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative flex min-h-14 flex-1 flex-col items-center justify-center gap-1 px-1 py-2",
              active ? "text-text" : "text-text-mute",
            )}
          >
            <item.icon aria-hidden weight={active ? "fill" : "regular"} className="size-5" />
            <span className="truncate text-[0.6875rem] leading-none">
              {item.label === "Needs a person" ? "Needs you" : item.label}
            </span>
            {badge > 0 ? (
              <span
                className="absolute right-1/4 top-1.5 inline-flex min-w-4 items-center justify-center rounded-full px-1 font-mono text-[0.625rem] tabular-nums text-white"
                style={{ background: "var(--lamp-flare)" }}
              >
                {badge > 9 ? "9+" : badge}
                <span className="sr-only"> waiting for a person</span>
              </span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
