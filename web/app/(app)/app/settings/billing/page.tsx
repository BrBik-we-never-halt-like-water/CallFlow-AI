"use client";

import Link from "next/link";
import { LampStrip } from "@/components/brand/lamp-strip";
import { NotWiredNotice, SettingsSection } from "@/components/app/settings-section";
import { TodoChip } from "@/components/marketing/price-value";
import { Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Eyebrow } from "@/components/ui/panel";
import type { LampSpec } from "@/lib/lamp";
import { useAppStore } from "@/lib/app-store";

/**
 * Billing.
 *
 * The usage meter is a lamp strip, not a progress bar   same reasoning as everywhere
 * else in the product: a bar reports a fraction, and a strip reports units of the thing
 * being counted. Here each lamp is a slice of today's live-call budget, so "nearly out"
 * looks like nearly out.
 */
export default function BillingSettingsPage() {
  const { health } = useAppStore();
  const limits = health?.limits;

  const segments = 20;
  const used = limits ? Math.min(limits.used_today, limits.daily_budget) : 0;
  const budget = limits?.daily_budget ?? 0;
  const usedSegments = budget > 0 ? Math.round((used / budget) * segments) : 0;
  const remaining = Math.max(0, budget - used);
  const share = budget > 0 ? remaining / budget : 0;

  const meter: LampSpec[] = Array.from({ length: segments }, (_, i) => {
    if (i < usedSegments) {
      return {
        state: share === 0 ? ("flare" as const) : share < 0.2 ? ("brass" as const) : ("jade" as const),
        label: "Used",
      };
    }
    return { state: "off" as const, label: "Remaining" };
  });

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Plan"
        description="What you're on, and what it includes."
        footer={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm">
              <Link href="/pricing">Compare plans</Link>
            </Button>
            <Button asChild variant="secondary" size="sm">
              <Link href="/demo">Talk to us</Link>
            </Button>
          </div>
        }
      >
        <dl className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-3">
            <dt className="text-small text-text-dim">Current plan</dt>
            <dd>
              <Tag>Free</Tag>
            </dd>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-small text-text-dim">Monthly price</dt>
            <dd>
              <TodoChip />
            </dd>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-small text-text-dim">Included calls</dt>
            <dd>
              <TodoChip />
            </dd>
          </div>
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-small text-text-dim">Dry runs</dt>
            <dd className="font-mono text-data text-text">Unlimited, free</dd>
          </div>
        </dl>
      </SettingsSection>

      <SettingsSection
        title="Today's live-call budget"
        description="Dry runs never count against this."
        effect={
          limits
            ? remaining === 0
              ? "You're out of live calls for today. Runs will not dial until the budget resets. Dry runs still work."
              : `${remaining} of ${budget} live calls left today. At ${limits.per_window} per ${limits.window_minutes} minutes, that's the pacing limit as well as the ceiling.`
            : "The service didn't report a budget, so nothing here is confirmed."
        }
      >
        {limits ? (
          <div className="flex flex-col gap-2">
            <LampStrip lamps={meter} size="md" />
            <p className="font-mono text-data tabular-nums text-text-dim">
              {used} used · {remaining} left
            </p>
          </div>
        ) : (
          <p className="text-small text-text-mute">No budget reported.</p>
        )}
      </SettingsSection>

      <SettingsSection title="Payment method">
        <EmptyState
          title="No payment method"
          body="You're on the free plan, so there's nothing to charge. Add a card when you move to a paid plan."
        />
      </SettingsSection>

      <SettingsSection title="Invoices">
        <div className="flex flex-col gap-2">
          <Eyebrow>History</Eyebrow>
          <EmptyState
            title="No invoices yet"
            body="Invoices appear here once you're on a paid plan. Each one lists the calls it covers."
          />
        </div>
      </SettingsSection>

      <NotWiredNotice>
        Plans, cards, top-ups, and invoices need a billing service, which this deployment
        does not have. The daily live-call budget above is real   it comes from the calling
        service and it genuinely governs whether the next run can dial.
      </NotWiredNotice>
    </div>
  );
}
