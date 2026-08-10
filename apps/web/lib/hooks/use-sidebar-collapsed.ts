'use client';

import { useStoredJson } from '@/lib/hooks/use-external-store';

const SIDEBAR_COLLAPSED_KEY = 'callflow.sidebar_collapsed';

/**
 * Whether the dashboard sidebar (`AppShell`'s `AppSidebar`) is collapsed to
 * icon-only width. Persisted so the choice survives a reload and applies
 * across the whole dashboard, not just the page it was toggled on.
 */
export function useSidebarCollapsed(): [boolean, (next: boolean) => void] {
  return useStoredJson<boolean>(SIDEBAR_COLLAPSED_KEY, false);
}
