"use client";

import Link from "next/link";
import { useEffect } from "react";
import { LampStrip } from "@/components/brand/lamp-strip";
import { BrandLockup } from "@/components/brand/wordmark";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/panel";
import type { LampSpec } from "@/lib/lamp";

/**
 * 500.
 *
 * One flare lamp among seven off ones: something specific failed, and it is not
 * everything. The copy makes the point that matters most to somebody who places phone
 * calls for a living   this is our fault, not their data.
 */
const ONE_FLARE: LampSpec[] = [
  { state: "off", label: "Fine" },
  { state: "off", label: "Fine" },
  { state: "off", label: "Fine" },
  { state: "flare", label: "Failed" },
  { state: "off", label: "Fine" },
  { state: "off", label: "Fine" },
  { state: "off", label: "Fine" },
  { state: "off", label: "Fine" },
];

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // The digest is what support needs to find this in the logs.
    console.error("[callflow] unhandled error", error);
  }, [error]);

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex h-16 shrink-0 items-center px-4 sm:px-6">
        <Link href="/" className="text-text transition-opacity hover:opacity-70">
          <BrandLockup />
          <span className="sr-only">CallFlow AI home</span>
        </Link>
      </header>

      <main className="flex flex-1 items-center px-4 sm:px-6">
        <div className="mx-auto flex w-full max-w-lg flex-col gap-6">
          <Eyebrow>500</Eyebrow>
          <LampStrip lamps={ONE_FLARE} size="lg" />
          <h1 className="font-display text-display-l text-text">The service is down.</h1>
          <p className="text-body-l text-text-dim">
            This isn&apos;t your account or your data. We&apos;re on it   check status for
            updates.
          </p>

          {error.digest ? (
            <p className="font-mono text-data text-text-mute">
              Reference {error.digest}
            </p>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <Button size="lg" onClick={reset}>
              Try again
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="/status">Check status</Link>
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
