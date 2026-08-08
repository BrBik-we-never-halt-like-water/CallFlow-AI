"use client";

import { useEffect } from "react";
import { useActiveOrg } from "@/lib/hooks/use-active-org";

/**
 * `useEffect`, but structurally forced to re-run when the active organisation changes.
 *
 * Every effect that fetches something scoped to "the organisation currently in view"
 * belongs here instead of a plain `useEffect` — the header's org switcher writes the
 * new org id synchronously (`useActiveOrg`'s `setActiveOrgId`), and this hook is the
 * one place that dependency is wired in, so a page can no longer add an org-scoped
 * fetch and forget the dependency that makes it refetch on switch.
 */
export function useOrgScopedEffect(
  effect: () => void | (() => void),
  deps: unknown[] = [],
): void {
  const [activeOrgId] = useActiveOrg();
  // `effect` and `deps` are caller-supplied; exhaustiveness is the caller's
  // responsibility for `deps`, same as any other effect.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(effect, [activeOrgId, ...deps]);
}
