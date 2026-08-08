"use client";

import { CaretUpDownIcon, CheckIcon, PlusIcon, XIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { cn } from "@/lib/cn";
import { BrandLockup } from "@/components/brand/wordmark";
import { Lamp } from "@/components/brand/lamp";
import { Tag } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip } from "@/components/ui/tooltip";
import { VRule } from "@/components/ui/rule";
import { useActiveOrg } from "@/lib/hooks/use-active-org";
import { useOrganisations } from "@/lib/hooks/use-organisations";
import { useAppStore } from "@/lib/app-store";
import { AppTabBar, isActive, OrgMark, PRIMARY_NAV_ITEMS } from "./app-nav";
import { UserMenu } from "./user-menu";
import { type SessionProfile, useSession } from "@/lib/hooks/use-session";

/** Routes that get a focused destination, not the persistent app chrome — see
 *  `MinimalTopBar`. A single task to finish and leave, so the header would
 *  only be a way back to a screen the user didn't come here for. Each route
 *  names its own top-bar label, so adding a second route here can't leave it
 *  silently showing "Profile". */
const MINIMAL_CHROME_ROUTES: { path: string; label: string }[] = [
  { path: "/app/profile", label: "Profile" },
];

/**
 * Dashboard shell: header, content. No sidebar — every /app/* destination
 * lives in the header's primary nav row (or the account menu, for the two
 * lower-frequency ones), the same structural decision Twisty makes.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "";
  const minimalRoute = MINIMAL_CHROME_ROUTES.find((r) => r.path === pathname);

  // Tracks whether this AppShell instance has ever rendered a *different*
  // pathname than the one it's on now, so "close" (MinimalTopBar) can tell a
  // real in-app back-navigation apart from a same-tab link in from outside
  // the app — window.history.length alone can't distinguish those. Derived
  // during render (React's own pattern for "update state in response to a
  // prop change" — see lib/hooks/use-external-store.ts), not in an effect: an
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
  const profile = session.status === "signed-in" ? session.profile : null;

  if (minimalRoute) {
    return (
      <div className="flex min-h-dvh flex-col">
        <a href="#app-main" className="skip-link">
          Skip to content
        </a>

        <MinimalTopBar label={minimalRoute.label} canGoBack={hasPriorInAppPage} />

        <main
          id="app-main"
          className="mx-auto w-full max-w-(--container-app) flex-1 px-4 py-6 sm:px-6"
        >
          {children}
        </main>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex min-h-dvh flex-col",
        // Only the dashboard gets the tinted canvas today — every other page
        // keeps the plain surface until this look is approved to roll out
        // further.
        pathname === "/app" && "canvas-tint",
      )}
    >
      <a href="#app-main" className="skip-link">
        Skip to content
      </a>

      <AppTopBar
        profile={profile}
        loading={session.status === "loading"}
        escalationCount={escalations.length}
        refreshSession={session.refresh}
      />

      <main
        id="app-main"
        className="mx-auto w-full max-w-(--container-app) flex-1 px-4 py-6 sm:px-6"
      >
        {children}
      </main>

      <AppTabBar escalationCount={escalations.length} />
    </div>
  );
}

/**
 * The top bar for a minimal-chrome route: the lockup and a single close control,
 * nothing else. No sidebar, no breadcrumb, no tab bar — this is a destination
 * for one task, and closing it is the only navigation decision worth offering.
 */
function MinimalTopBar({ label, canGoBack }: { label: string; canGoBack: boolean }) {
  const router = useRouter();

  function close() {
    // window.history.length alone isn't "has app history" — it counts every
    // entry in the tab's session history, including pages from a different
    // origin visited before the app ever loaded. A same-tab link straight in
    // from outside (an email, a Slack message) can have length > 1 and still
    // send router.back() out of the app entirely. canGoBack instead reflects
    // pages *this app instance actually rendered* (tracked in AppShell), so
    // it's only true when there's somewhere in-app to actually go back to.
    if (canGoBack) {
      router.back();
    } else {
      router.push("/app");
    }
  }

  return (
    <header className="header-glass sticky top-0 z-30 flex h-(--h-app-topbar) shrink-0 items-center gap-3 border-b px-4 sm:px-6">
      <Link href="/app" className="flex shrink-0 items-center gap-2.5 text-text">
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
 * A true 3-column grid — `1fr auto 1fr` — so the center column (primary nav)
 * centers against the full header width rather than against whatever space
 * two unequal side clusters happen to leave behind. Left: brand only. Right:
 * credits, org switcher, account. Shares `main`'s exact max-width and padding
 * so the header's edges land on the same x-position as the first card's edges
 * below it.
 *
 * There is no sidebar: this row is the only navigation surface at `lg` and
 * above (`AppTabBar` covers everything narrower).
 */
function AppTopBar({
  profile,
  loading,
  escalationCount,
  refreshSession,
}: {
  profile: SessionProfile | null;
  loading: boolean;
  escalationCount: number;
  refreshSession: () => void;
}) {
  return (
    <header className="header-glass sticky top-0 z-30 flex h-(--h-app-topbar) shrink-0 items-center border-b px-4 sm:px-6">
      <div className="mx-auto grid w-full max-w-(--container-app) grid-cols-[1fr_auto_1fr] items-center gap-4">
        <Link href="/app" className="flex min-w-0 items-center gap-2 text-text">
          <BrandLockup />
          <span className="sr-only">CallFlow AI dashboard</span>
        </Link>

        <PrimaryNav escalationCount={escalationCount} />

        <div className="flex min-w-0 items-center justify-end gap-2">
          <CreditBalance />
          <HeaderOrgSwitcher profile={profile} refreshSession={refreshSession} />
          <UserMenu profile={profile} loading={loading} />
        </div>
      </div>
    </header>
  );
}

/** Every /app/* destination worth a permanent, one-click slot — the same
 *  five links that become the mobile tab bar, as text rather than icons,
 *  hidden below `lg` where the tab bar takes over instead. */
function PrimaryNav({ escalationCount }: { escalationCount: number }) {
  const pathname = usePathname() ?? "";

  return (
    <nav aria-label="Primary" className="hidden min-w-0 items-center justify-center gap-1 lg:flex">
      {PRIMARY_NAV_ITEMS.map((item) => {
        const active = isActive(pathname, item.href);
        const badge = item.href === "/app/escalations" ? escalationCount : 0;

        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-2 text-small transition-colors duration-(--dur-micro)",
              active ? "font-medium text-text" : "text-text-mute hover:text-text",
            )}
          >
            {item.label}
            {/* The only persistently-coloured element in the header, because it is
                the only thing in the product that needs immediate human action. A
                count of zero renders nothing at all — not a grey zero. */}
            {badge > 0 ? (
              <span
                className="inline-flex min-w-5 items-center justify-center rounded-full px-1.5 py-0.5 text-label text-white"
                style={{ background: "var(--lamp-flare)" }}
              >
                {badge > 99 ? "99+" : badge}
                <span className="sr-only"> waiting for a person</span>
              </span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}

/**
 * The one real place to switch, create, or manage organisations — relocated
 * from the sidebar into the header now that there is no sidebar. Same
 * behaviour, compact horizontal trigger instead of a full-width block.
 */
function HeaderOrgSwitcher({
  profile,
  refreshSession,
}: {
  profile: SessionProfile | null;
  refreshSession: () => void;
}) {
  const { orgs } = useOrganisations(profile);
  const [, setActiveOrgId] = useActiveOrg();

  const label = profile?.active.org_name ?? "Loading…";

  if (!profile) {
    return <span className="hidden h-8 w-28 shrink-0 rounded-full bg-surface-sunken sm:block" />;
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
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Switch organisation — currently ${label}`}
          className="hidden shrink-0 cursor-pointer items-center gap-1.5 rounded-full px-2 py-1.5 text-small transition-colors hover:bg-surface-hover sm:inline-flex"
        >
          <OrgMark name={label} logoUrl={profile.active.org_logo_url} size="sm" />
          <span className="max-w-28 truncate font-medium text-text">{label}</span>
          <CaretUpDownIcon aria-hidden className="size-3.5 shrink-0 text-text-mute" />
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
            <OrgMark name={org.name} logoUrl={org.logo_url} size="sm" />
            <span className="min-w-0 flex-1 truncate">{org.name}</span>
            <Tag>{org.role}</Tag>
          </DropdownMenuItem>
        ))}

        <DropdownMenuSeparator />

        <DropdownMenuItem>
          <Link href="/app/organisation/new" className="flex flex-1 items-center gap-2">
            <PlusIcon aria-hidden className="size-4" />
            New organisation
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/**
 * Credit balance pill.
 *
 * Under 20% it gains a brass dot; at zero it goes flare. The service exposes a daily
 * live-call budget rather than a credit wallet, so that is what this reports: the
 * number that actually governs whether the next run can dial.
 *
 * Deliberate, flagged exception to "every machine-produced value is set in mono"
 * (CLAUDE.md conventions): every other pill in the header (search, org switcher) is
 * body-font, and a monospace badge read as visually inconsistent with the rest of
 * the row rather than as a meaningful "this is data" signal. `tabular-nums` stays —
 * that's what actually stops the count jittering as it changes, independent of typeface.
 */
function CreditBalance() {
  const { safetySettings } = useAppStore();

  if (!safetySettings) {
    return (
      <span className="hidden text-small text-text-mute sm:inline">— calls left</span>
    );
  }

  const remaining = Math.max(0, safetySettings.daily_budget - safetySettings.used_today);
  const share = safetySettings.daily_budget > 0 ? remaining / safetySettings.daily_budget : 0;
  const lamp = remaining === 0 ? "flare" : share < 0.2 ? "brass" : null;

  return (
    <Tooltip
      content={
        remaining === 0
          ? "You're out of calls for today. Resets tomorrow."
          : `${remaining} of ${safetySettings.daily_budget} calls left today.`
      }
    >
      <Link
        href="/app/settings/safety"
        className={cn(
          "hidden items-center gap-1.5 rounded-full bg-surface-sunken px-3 py-1.5 sm:inline-flex",
          "text-small tabular-nums transition-colors hover:bg-surface-hover",
          remaining === 0 ? "text-lamp-flare-text" : "text-text-dim",
        )}
      >
        {lamp ? <Lamp state={lamp} size="sm" /> : null}
        {remaining} left
      </Link>
    </Tooltip>
  );
}
