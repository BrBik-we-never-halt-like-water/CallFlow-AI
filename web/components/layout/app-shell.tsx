"use client";

import { QuestionIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { useStoredString } from "@/lib/hooks/use-external-store";
import { BrandLockup } from "@/components/brand/wordmark";
import { Lamp } from "@/components/brand/lamp";
import { Tooltip } from "@/components/ui/tooltip";
import { VRule } from "@/components/ui/rule";
import { useAppStore } from "@/lib/app-store";
import { AppNav, AppTabBar, NAV_ITEMS } from "./app-nav";
import { CommandSearch } from "./command-search";

const COLLAPSE_KEY = "callflow.nav.collapsed";

/**
 * Dashboard shell: fixed left nav, top bar, content.
 *
 * The collapsed state of the nav persists, because a user who collapses it wants it
 * collapsed tomorrow too.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { escalations } = useAppStore();
  const [stored, setStored] = useStoredString(COLLAPSE_KEY, "false");
  const collapsed = stored === "true";

  function toggleCollapsed() {
    setStored(collapsed ? "false" : "true");
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#app-main" className="skip-link">
        Skip to content
      </a>

      <div className="flex min-h-dvh flex-1">
        <AppNav
          collapsed={collapsed}
          onToggleCollapsed={toggleCollapsed}
          escalationCount={escalations.length}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <AppTopBar />

          <main
            id="app-main"
            className="mx-auto w-full max-w-(--container-app) flex-1 px-4 py-6 sm:px-6"
          >
            {children}
          </main>

          <AppTabBar escalationCount={escalations.length} />
        </div>
      </div>
    </div>
  );
}

function AppTopBar() {
  return (
    <header className="sticky top-0 z-30 flex h-(--h-app-topbar) shrink-0 items-center gap-3 border-b border-rule bg-surface-raised px-4 sm:px-6">
      {/* The lockup lives in the top bar on mobile, where the left nav is absent. */}
      <Link href="/app" className="shrink-0 text-text md:hidden">
        <BrandLockup />
        <span className="sr-only">CallFlow AI dashboard</span>
      </Link>

      <Breadcrumb />

      <div className="ml-auto flex items-center gap-1.5">
        <CommandSearch />
        <VRule className="hidden sm:block" />
        <CreditBalance />
        <Tooltip content="Docs and help">
          <Link
            href="/docs"
            aria-label="Docs and help"
            className="flex size-9 items-center justify-center rounded-sm text-text-dim transition-colors hover:bg-surface-hover hover:text-text"
          >
            <QuestionIcon aria-hidden className="size-4" />
          </Link>
        </Tooltip>
      </div>
    </header>
  );
}

/** Derived from the path, so a new page cannot forget to set it. */
function Breadcrumb() {
  const pathname = usePathname() ?? "";
  const segments = pathname.split("/").filter(Boolean).slice(1);
  const top = NAV_ITEMS.find(
    (item) => item.href === `/app/${segments[0] ?? ""}` || (segments.length === 0 && item.href === "/app"),
  );

  return (
    <nav aria-label="Breadcrumb" className="hidden min-w-0 md:block">
      <ol className="flex items-center gap-2">
        <li>
          <Link
            href="/app"
            className="text-small text-text-mute transition-colors hover:text-text"
          >
            Dashboard
          </Link>
        </li>
        {top && top.href !== "/app" ? (
          <>
            <li aria-hidden className="text-text-mute">
              /
            </li>
            <li className="truncate text-small font-medium text-text">{top.label}</li>
          </>
        ) : null}
        {segments.length > 1 ? (
          <>
            <li aria-hidden className="text-text-mute">
              /
            </li>
            <li className="truncate font-mono text-data text-text-dim">
              {segments[segments.length - 1]}
            </li>
          </>
        ) : null}
      </ol>
    </nav>
  );
}

/**
 * Credit balance   always visible, always mono.
 *
 * Under 20% it gains a brass dot; at zero it goes flare. The service exposes a daily
 * live-call budget rather than a credit wallet, so that is what this reports: the
 * number that actually governs whether the next run can dial.
 */
function CreditBalance() {
  const { health } = useAppStore();
  const limits = health?.limits;

  if (!limits) {
    return (
      <span className="hidden font-mono text-data text-text-mute sm:inline">
          calls left
      </span>
    );
  }

  const remaining = Math.max(0, limits.daily_budget - limits.used_today);
  const share = limits.daily_budget > 0 ? remaining / limits.daily_budget : 0;
  const lamp = remaining === 0 ? "flare" : share < 0.2 ? "brass" : null;

  return (
    <Tooltip
      content={
        remaining === 0
          ? "You're out of live calls for today. Dry runs are still unlimited."
          : `${remaining} of ${limits.daily_budget} live calls left today. Dry runs don't count.`
      }
    >
      <Link
        href="/app/settings/billing"
        className={cn(
          "hidden items-center gap-1.5 rounded-sm px-2 py-1 sm:inline-flex",
          "font-mono text-data tabular-nums transition-colors hover:bg-surface-hover",
          remaining === 0 ? "text-lamp-flare-text" : "text-text-dim",
        )}
      >
        {lamp ? <Lamp state={lamp} size="sm" /> : null}
        {remaining} left
      </Link>
    </Tooltip>
  );
}
