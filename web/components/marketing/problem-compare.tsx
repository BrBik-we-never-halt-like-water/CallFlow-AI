import { Eyebrow } from "@/components/ui/panel";
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
    <section id="problem" className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal className="flex max-w-2xl flex-col gap-4">
        <Eyebrow>Every call, understood</Eyebrow>
        <h2 className="measure-display font-display text-h2 text-text">
          A completed call tells you nothing.
        </h2>
        <p className="text-body-l text-text-dim">
          Here’s one call the moment it hangs up — scored by hand on the left, understood
          by CallFlow on the right. Same conversation. Two completely different places to
          start your day.
        </p>
      </Reveal>

      <Reveal delayMs={120} className="mt-12">
        <LiveExtraction />
      </Reveal>
    </section>
  );
}
