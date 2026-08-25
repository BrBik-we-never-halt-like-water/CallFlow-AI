import Link from 'next/link';
import { LampStrip } from '@/components/brand/lamp-strip';
import { WaveCanvas } from '@/components/brand/wave-canvas';
import { Button } from '@/components/ui/button';
import { Reveal } from '@/components/ui/reveal';
import type { LampSpec } from '@/lib/lamp';

const STRIP: LampSpec[] = [
  { state: 'jade', label: 'Auto-closed' },
  { state: 'jade', label: 'Auto-closed' },
  { state: 'jade', label: 'Auto-closed' },
  { state: 'jade', label: 'Auto-closed' },
  { state: 'brass', pulse: true, label: 'Queued for retry' },
  { state: 'jade', label: 'Auto-closed' },
  { state: 'flare', label: 'Needs a person' },
  { state: 'jade', label: 'Auto-closed' },
];

/**
 * The closing note.
 *
 * A raised card rather than an inverted band. The page holds one ground the whole way
 * down, so the emphasis comes from elevation and the waves behind it rather than from
 * flipping the surface out from under the reader at the last section.
 */
export function FinalCta() {
  return (
    <section className="mt-(--space-section) px-4 sm:px-6">
      <Reveal>
        <div className="card-feature relative mx-auto max-w-(--container-marketing) overflow-hidden">
          {/* Bold waves at the top, fading away downward. */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 h-48 [mask-image:linear-gradient(to_bottom,#000,transparent)] [-webkit-mask-image:linear-gradient(to_bottom,#000,transparent)]"
          >
            <WaveCanvas pitch={9} className="h-full text-text opacity-70" />
          </div>

          <div className="relative flex flex-col items-center gap-6 px-6 py-(--space-section) text-center">
            {/* `text-display-l`, not `text-4xl sm:text-5xl lg:text-7xl`. Those three
                steps jumped where every other headline on the site scales fluidly, and
                the top step (4.5rem) came within half a rem of the hero's - the closing
                note reading larger than the opening claim. */}
            <h2 className="measure-display font-display text-display-l text-text">
              Hand over the list and let CallFlow do the rest.
            </h2>

            <p className="measure text-body-l text-text-dim">
              Brief an agent, load your list, and let it dial. Every run passes
              the gates before it places a single call.
            </p>

            <LampStrip
              lamps={STRIP}
              size="lg"
              counts
              className="items-center"
            />

            <div className="flex flex-wrap items-center justify-center gap-3">
              <Button asChild size="lg">
                <Link href="/signup">Start free</Link>
              </Button>
              <Button asChild variant="secondary" size="lg">
                <Link href="/demo">Book a 15-min demo</Link>
              </Button>
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
