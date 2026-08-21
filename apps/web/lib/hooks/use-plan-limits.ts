'use client';

import { useState } from 'react';
import { api, type Entitlements, type PlanOption } from '@/lib/api';
import { useEntitlementsVersion } from '@/lib/hooks/use-entitlements-version';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';

/**
 * What the current organisation's plan allows, for any signed-in role.
 *
 * Reads `GET /api/v1/billing/plans` rather than `/billing/subscription`, and that
 * is the whole reason this hook exists: the overview endpoint needs
 * `billing:read`, which is admin and owner only, while creating an agent is
 * `agents:write` and reaches further down. An operator who hits the agent cap has
 * to be told what stopped them, and this is the only endpoint that will tell
 * them - it is signed-in-only precisely so it can.
 *
 * **The affordance, never the gate.** The real limit is enforced by a 402 from the
 * API and again by a before-insert trigger in the database. Everything here does
 * is stop someone walking into that refusal. So a slow or failed fetch resolves to
 * "no known limit" and leaves the normal action in place: a network blip must not
 * lock an owner out of creating an agent they are entitled to.
 */
export type PlanLimits =
  | { status: 'loading' }
  | { status: 'unknown' }
  | { status: 'ready'; planName: string; entitlements: Entitlements };

export function usePlanLimits(): PlanLimits {
  const [state, setState] = useState<PlanLimits>({ status: 'loading' });
  const entitlementsVersion = useEntitlementsVersion();

  useOrgScopedEffect(() => {
    let cancelled = false;
    api
      .billingPlans()
      .then((plans: PlanOption[]) => {
        if (cancelled) return;
        const current = plans.find((plan) => plan.current);
        setState(
          current
            ? {
                status: 'ready',
                planName: current.name,
                entitlements: current.entitlements,
              }
            : { status: 'unknown' },
        );
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'unknown' });
      });
    return () => {
      cancelled = true;
    };
  }, [entitlementsVersion]);

  return state;
}

/**
 * `true` only when the limit is known *and* reached.
 *
 * `null` is unlimited and `0` is a real ceiling, so the comparison is written
 * against an explicit `null` check - a falsiness test would read `0` as
 * "unlimited" and hand an organisation with no allowance at all an unrestricted
 * button. That asymmetry is the one the whole entitlement model rests on.
 */
export function isAtLimit(limit: number | null | undefined, used: number): boolean {
  if (limit === null || limit === undefined) return false;
  return used >= limit;
}
