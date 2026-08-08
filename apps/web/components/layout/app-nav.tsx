"use client";

import type { Icon } from "@phosphor-icons/react";
import {
  AddressBookIcon,
  BroadcastIcon,
  BuildingsIcon,
  GaugeIcon,
  GearSixIcon,
  MegaphoneIcon,
  UserFocusIcon,
} from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";

export interface NavItem {
  label: string;
  href: string;
  icon: Icon;
  /** Only `Needs a person` carries one. */
  badge?: number;
}

/**
 * Every /app/* destination. The header (`AppShell`'s `AppTopBar`) renders the
 * first five as its primary nav row; `Organisation` and `Settings` are lower-
 * frequency and live in the account menu (`UserMenu`) instead — folding them
 * into the header row would mean either compressing type or cramming seven
 * links into one line, both worse than one extra click for a rare action.
 */
export const NAV_ITEMS: Omit<NavItem, "badge">[] = [
  { label: "Dashboard", href: "/app", icon: GaugeIcon },
  { label: "Campaigns", href: "/app/campaigns", icon: MegaphoneIcon },
  { label: "Runs", href: "/app/runs", icon: BroadcastIcon },
  { label: "Needs a person", href: "/app/escalations", icon: UserFocusIcon },
  { label: "Contacts", href: "/app/contacts", icon: AddressBookIcon },
  { label: "Organisation", href: "/app/organisation", icon: BuildingsIcon },
  { label: "Settings", href: "/app/settings", icon: GearSixIcon },
];

/** The five destinations shown as text links in the header's primary nav row. */
export const PRIMARY_NAV_ITEMS = NAV_ITEMS.filter(
  (item) => item.href !== "/app/organisation" && item.href !== "/app/settings",
);

/** The four destinations that become the mobile tab bar. */
const MOBILE_ITEMS = ["/app", "/app/runs", "/app/escalations", "/app/campaigns"];

export function isActive(pathname: string, href: string): boolean {
  if (href === "/app") return pathname === "/app";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * An organisation's mark: its uploaded logo, or a consistent initial when it has
 * none, so a missing upload never renders as a broken image.
 */
export function OrgMark({
  name,
  logoUrl,
  size = "md",
}: {
  name: string;
  logoUrl: string | null;
  size?: "sm" | "md";
}) {
  const dimension = size === "sm" ? "size-4.5" : "size-6";
  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt=""
        className={cn(dimension, "shrink-0 rounded-xs border border-rule object-cover")}
      />
    );
  }
  return (
    <span
      className={cn(
        dimension,
        "flex shrink-0 items-center justify-center rounded-xs border border-rule bg-surface-sunken font-mono text-label text-text",
      )}
    >
      {name.charAt(0).toUpperCase()}
    </span>
  );
}

/** Bottom tab bar — the only nav surface below `lg`, where the header's
 *  primary nav row doesn't have room to show without compressing type. */
export function AppTabBar({ escalationCount }: { escalationCount: number }) {
  const pathname = usePathname() ?? "";
  const items = NAV_ITEMS.filter((item) => MOBILE_ITEMS.includes(item.href));

  return (
    <nav
      aria-label="Dashboard"
      className="sticky bottom-0 z-30 flex shrink-0 border-t border-rule bg-surface-raised lg:hidden"
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
