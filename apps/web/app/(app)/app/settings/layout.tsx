'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/cn';
import { useSession } from '@/lib/hooks/use-session';

// Integrations and Billing are both deliberately absent, for the same reason and
// by two independent decisions that met in a merge. Each lives in the primary nav
// now, and each old Settings path is only a redirect - so listing either here gave
// Settings a tab that threw you out of Settings the moment you clicked it, which
// reads as a broken tab rather than a moved feature.
//
// Billing left because the plan gates how much of the product exists at all and
// every 402 points there; Integrations because connecting a carrier and a speech
// vendor is what a new organisation must do before anything works.
const TABS = [
  { slug: 'safety', label: 'Safety', permission: 'safety:read' },
  { slug: 'api-keys', label: 'API keys', permission: 'api_keys:read' },
] as const;

export default function SettingsLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname() ?? '';
  const session = useSession();
  // While the session is still resolving, show every tab rather than
  // narrowing to none and then snapping wider a moment later - the
  // permission check below is a convenience for the nav, not the guard
  // (each page gates its own content), so a one-frame "too wide" beats a
  // visible layout shift.
  const tabs =
    session.status === 'signed-in'
      ? TABS.filter((tab) => session.profile.permissions.includes(tab.permission))
      : TABS;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="text-small font-bold text-text-mute">Settings</p>
        <h1 className="font-display text-h2 text-text">
          The controls behind every run
        </h1>
        <p className="measure text-small text-text-dim">
          Guards, credentials, and the vendors this organisation is connected
          to.
        </p>
      </div>

      {/* Real links rather than a tab widget: each pane is its own URL, so a setting
          can be linked to directly - which the safety guard popovers rely on. */}
      <nav
        aria-label="Settings sections"
        className="-mb-px overflow-x-auto border-b border-rule"
      >
        <ul className="flex min-w-max gap-1">
          {tabs.map((tab) => {
            const href = `/app/settings/${tab.slug}`;
            const active = pathname === href;
            return (
              <li key={tab.slug}>
                <Link
                  href={href}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'relative inline-flex items-center whitespace-nowrap px-3 py-2.5 text-small font-medium',
                    'transition-colors duration-(--dur-micro)',
                    'after:absolute after:inset-x-0 after:bottom-0 after:h-0.5',
                    active
                      ? 'text-text after:bg-surface-inverse'
                      : 'text-text-dim after:bg-transparent hover:text-text',
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
