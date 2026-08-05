"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { Eyebrow } from "@/components/ui/panel";

const TABS = [
  { slug: "", label: "Organisation" },
  { slug: "team", label: "Team" },
  { slug: "billing", label: "Billing" },
  { slug: "numbers", label: "Numbers" },
  { slug: "api-keys", label: "API keys" },
  { slug: "safety", label: "Safety" },
  { slug: "compliance", label: "Compliance" },
  { slug: "integrations", label: "Integrations" },
  { slug: "notifications", label: "Notifications" },
];

export default function SettingsLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname() ?? "";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Eyebrow>Settings</Eyebrow>
        <h1 className="font-display text-h2 text-text">Settings</h1>
      </div>

      {/* Real links rather than a tab widget: each pane is its own URL, so a setting
          can be linked to directly — which the safety guard popovers rely on. */}
      <nav aria-label="Settings sections" className="-mb-px overflow-x-auto border-b border-rule">
        <ul className="flex min-w-max gap-1">
          {TABS.map((tab) => {
            const href = tab.slug ? `/app/settings/${tab.slug}` : "/app/settings";
            const active = pathname === href;
            return (
              <li key={tab.slug}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative inline-flex items-center whitespace-nowrap px-3 py-2.5 text-small font-medium",
                    "transition-colors duration-(--dur-micro)",
                    "after:absolute after:inset-x-0 after:bottom-0 after:h-0.5",
                    active
                      ? "text-text after:bg-surface-inverse"
                      : "text-text-dim after:bg-transparent hover:text-text",
                  )}
                >
                  {tab.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="max-w-3xl">{children}</div>
    </div>
  );
}
