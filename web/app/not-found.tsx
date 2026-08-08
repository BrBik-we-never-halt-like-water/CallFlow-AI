import Link from "next/link";
import { LampStrip } from "@/components/brand/lamp-strip";
import { BrandLockup } from "@/components/brand/wordmark";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/panel";
import type { LampSpec } from "@/lib/lamp";

/**
 * 404.
 *
 * The lamp strip is the illustration, and every lamp is off   there is nothing here,
 * and an unlit board says that more precisely than an apology would.
 */
const ALL_OFF: LampSpec[] = Array.from({ length: 8 }, () => ({
  state: "off" as const,
  label: "Nothing here",
}));

export default function NotFound() {
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
          <Eyebrow>404</Eyebrow>
          <LampStrip lamps={ALL_OFF} size="lg" />
          <h1 className="font-display text-display-l text-text">That page isn&apos;t here.</h1>
          <p className="text-body-l text-text-dim">
            Check the address, or head back to the dashboard.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/app">Open dashboard</Link>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="/">Back to home</Link>
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
