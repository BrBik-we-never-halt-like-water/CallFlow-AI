"use client";

import { useEffect, useState } from "react";
import { api, type Organisation } from "@/lib/api";
import type { SessionProfile } from "@/lib/hooks/use-session";

/**
 * Every organisation the signed-in user belongs to.
 *
 * Shared by the user-menu's org switcher and Overview's org strip so there is one
 * fetch, not two independent copies of the same list drifting apart.
 */
export function useOrganisations(profile: SessionProfile | null): {
  orgs: Organisation[] | null;
  refresh: () => void;
} {
  const [orgs, setOrgs] = useState<Organisation[] | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!profile) return;
    let cancelled = false;
    api
      .listOrganisations()
      .then((list) => {
        if (!cancelled) setOrgs(list);
      })
      .catch(() => {
        if (!cancelled) setOrgs(null);
      });
    return () => {
      cancelled = true;
    };
    // Re-list whenever the active org changes (a switch or a create) or a manual
    // refresh is requested.
  }, [profile, profile?.active.org_id, nonce]);

  return { orgs, refresh: () => setNonce((n) => n + 1) };
}
