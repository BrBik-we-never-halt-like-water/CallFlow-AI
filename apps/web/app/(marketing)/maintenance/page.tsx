import type { Metadata } from "next";
import Link from "next/link";
import { LampStrip } from "@/components/brand/lamp-strip";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/panel";
import type { LampSpec } from "@/lib/lamp";

export const metadata: Metadata = {
  title: "Maintenance",
  description: "CallFlow is briefly offline for scheduled maintenance.",
  robots: { index: false, follow: false },
};

/** Ice, because a paused run is suspended rather than failed. */
const PAUSED: LampSpec[] = Array.from({ length: 8 }, (_, i) => ({
  state: i < 5 ? ("ice" as const) : ("off" as const),
  label: i < 5 ? "Paused" : "Queued",
}));

export default function MaintenancePage() {
  return (
    <div className="mx-auto flex max-w-lg flex-col gap-6 px-4 pt-16 sm:px-6">
      <Eyebrow>Maintenance</Eyebrow>
      <LampStrip lamps={PAUSED} size="lg" />
      <h1 className="font-display text-display-l text-text">
        CallFlow is briefly offline.
      </h1>
      <p className="text-body-l text-text-dim">
        Scheduled maintenance. Runs already in progress were paused, not lost.
      </p>
      <div className="flex flex-wrap gap-3">
        <Button asChild size="lg">
          <Link href="/status">Check status</Link>
        </Button>
        <Button asChild variant="secondary" size="lg">
          <Link href="/">Back to home</Link>
        </Button>
      </div>
    </div>
  );
}
