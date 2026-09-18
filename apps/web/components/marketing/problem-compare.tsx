import { SectionHeading } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";
import { LiveExtraction } from "./live-extraction";

/**
 * The problem and the product, side by side.
 *
 * The header makes the case in words; below it, the same call runs in two live
 * sections — what a plain log leaves you guessing at, and what CallFlow hands you
 * the moment the call ends.
 */
export function ProblemCompare() {
  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      {/* `SectionHeading`, not a hand-rolled eyebrow and h2. This section had its
          own copy of that markup, which meant it alone rendered without the wave
          line beside the eyebrow - the one detail that makes the other six
          sections read as a set. */}
      <Reveal>
        <SectionHeading
          eyebrow="Every call, understood"
          title="A completed call tells you nothing."
          sub="The same call, the moment it ends — scored by hand on the left, understood by CallFlow on the right."
        />
      </Reveal>

      <Reveal delayMs={120} className="mt-(--deck-gap)">
        <LiveExtraction />
      </Reveal>
    </section>
  );
}
