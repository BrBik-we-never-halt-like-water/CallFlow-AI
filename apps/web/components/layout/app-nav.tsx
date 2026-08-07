"use client";

import type { Icon } from "@phosphor-icons/react";
import {
  AddressBookIcon,
  BroadcastIcon,
  CaretUpDownIcon,
  CheckIcon,
  GaugeIcon,
  GearSixIcon,
  MegaphoneIcon,
  PlusIcon,
  SidebarSimpleIcon,
  UserFocusIcon,
} from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { CreateOrgDialog } from "@/components/app/create-org-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tag } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import { useToast } from "@/components/ui/toast";
import { useActiveOrg } from "@/lib/hooks/use-active-org";
import { useOrganisations } from "@/lib/hooks/use-organisations";
import type { SessionProfile } from "@/lib/hooks/use-session";

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
  profile,
  refreshSession,
}: {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  escalationCount: number;
  profile: SessionProfile | null;
  refreshSession: () => void;
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
      <OrgSwitcher collapsed={collapsed} profile={profile} refreshSession={refreshSession} />

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

/**
 * The one real place to switch, create, or manage organisations.
 *
 * This used to be a static display (name only, no dropdown), while the actual
 * switcher lived in the header and a third copy of it lived inside the user's
 * account menu — three controls for one job, none of them labelled clearly
 * enough to tell apart. This is the only one now, in the spot every workspace
 * switcher in a B2B dashboard lives: top of the sidebar.
 */
function OrgSwitcher({
  collapsed,
  profile,
  refreshSession,
}: {
  collapsed: boolean;
  profile: SessionProfile | null;
  refreshSession: () => void;
}) {
  const toast = useToast();
  const { orgs, refresh: refreshOrgs } = useOrganisations(profile);
  const [, setActiveOrgId] = useActiveOrg();
  const [creating, setCreating] = useState(false);

  const label = profile?.active.org_name ?? "Loading…";

  if (!profile) {
    return (
      <div className="border-b border-rule p-2">
        <div
          className={cn(
            "flex h-10 items-center gap-2.5 rounded-sm px-2.5",
            collapsed && "justify-center px-0",
          )}
        >
          <span className="flex size-6 shrink-0 items-center justify-center rounded-xs border border-rule bg-surface-sunken" />
          {!collapsed ? <span className="h-3.5 flex-1 rounded-xs bg-surface-sunken" /> : null}
        </div>
      </div>
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

  return (
    <div className="border-b border-rule p-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`Switch organisation — currently ${label}`}
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
              <>
                <span className="min-w-0 flex-1 truncate text-left font-medium text-text">
                  {label}
                </span>
                <CaretUpDownIcon aria-hidden className="size-3.5 shrink-0 text-text-mute" />
              </>
            ) : null}
          </button>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="start" className="min-w-64">
          <DropdownMenuLabel>Organisations</DropdownMenuLabel>
          {list.map((org) => (
            <DropdownMenuItem key={org.id} onSelect={() => switchOrg(org.id)}>
              {org.id === profile.active.org_id ? (
                <CheckIcon aria-hidden weight="bold" className="size-4 shrink-0" />
              ) : (
                <span className="size-4 shrink-0" aria-hidden />
              )}
              <span className="min-w-0 flex-1 truncate">{org.name}</span>
              <Tag>{org.role}</Tag>
            </DropdownMenuItem>
          ))}

          <DropdownMenuSeparator />

          <DropdownMenuItem onSelect={() => setCreating(true)}>
            <PlusIcon aria-hidden className="size-4" />
            New organisation
          </DropdownMenuItem>
          <DropdownMenuItem>
            <Link href="/app/settings" className="flex flex-1 items-center gap-2">
              <GearSixIcon aria-hidden className="size-4" />
              Organisation settings
            </Link>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <CreateOrgDialog
        open={creating}
        onOpenChange={setCreating}
        onCreated={(org) => {
          refreshOrgs();
          switchOrg(org.id);
          toast({ tone: "success", title: "Organisation created", body: org.name });
        }}
      />
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
