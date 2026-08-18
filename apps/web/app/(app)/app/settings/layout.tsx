'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/cn';
import { useSession } from '@/lib/hooks/use-session';

// Integrations is deliberately absent. It lives in the primary nav, and its old
// Settings path is only a redirect now (`settings/integrations/page.tsx`) - so
// listing it here gave Settings a tab that threw you out of Settings the moment
// you clicked it, which reads as a broken tab rather than a moved feature.
const TABS = [
  { slug: 'safety', label: 'Safety', permission: 'safety:read' },
  { slug: 'api-keys', label: 'API keys', permission: 'api_keys:read' },
  { slug: 'billing', label: 'Billing', permission: 'billing:read' },
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
  // visible layout shift. Billing is reachable without `billing:read` too -
  // the user menu's "My credits" link sends operator/viewer straight to
  // /app/settings/billing, which renders its own honest placeholder there
  // rather than the org's real plan/usage.
  const tabs =
    session.status === 'signed-in'
      ? TABS.filter(
          (tab) =>
            session.profile.permissions.includes(tab.permission) ||
            tab.slug === 'billing',
        )
      : TABS;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="text-small font-bold text-text-mute">Settings</p>
        <h1 className="font-display text-h2 text-text">
          The controls behind every run
        </h1>
        <p className="measure text-small text-text-dim">
          Guards, credentials, connected numbers, and the plan this organisation
          is on.
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
