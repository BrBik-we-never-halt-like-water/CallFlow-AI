import Link from "next/link";
import { LampStrip } from "@/components/brand/lamp-strip";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";
import type { LampSpec } from "@/lib/lamp";

const STRIP: LampSpec[] = [
  { state: "jade", label: "Auto-closed" },
  { state: "jade", label: "Auto-closed" },
  { state: "jade", label: "Auto-closed" },
  { state: "jade", label: "Auto-closed" },
  { state: "brass", pulse: true, label: "Queued for retry" },
  { state: "jade", label: "Auto-closed" },
  { state: "flare", label: "Needs a person" },
  { state: "jade", label: "Auto-closed" },
];

/**
 * The closing note.
 *
 * A raised card rather than an inverted band — the page is light throughout, and the
 * emphasis comes from elevation and the grid behind it rather than from flipping the
 * surface.
 */
export function FinalCta() {
  return (
    <section className="mt-(--space-section) px-4 sm:px-6">
      <Reveal>
        <div className="card-flow relative mx-auto max-w-(--container-marketing) overflow-hidden">
          <div
            aria-hidden
            className="wave-field pointer-events-none absolute inset-0"
          />

          <div className="relative flex flex-col items-center gap-6 px-6 py-(--space-section) text-center">
            <Eyebrow>Start free</Eyebrow>

            <h2 className="measure-display font-display text-display-l text-text">
              Put your list to work.
            </h2>

            <p className="measure text-body-l text-text-dim">
              Load your contacts, write a goal, and let CallFlow dial. Every run is
              validated and guarded before it places a single call.
            </p>

            <LampStrip lamps={STRIP} size="lg" counts className="items-center" />

            <div className="flex flex-wrap items-center justify-center gap-3">
              <Button asChild size="lg">
                <Link href="/signup">Start free</Link>
              </Button>
              <Button asChild variant="secondary" size="lg">
                <Link href="/demo">Book a 15-min demo</Link>
              </Button>
            </div>

            <p className="text-small text-text-mute">No card required.</p>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
