import { CapabilityGrid } from "@/components/marketing/capability-grid";
import { FinalCta } from "@/components/marketing/final-cta";
import { Hero } from "@/components/marketing/hero";
import { PricingPreview } from "@/components/marketing/pricing-preview";
import { ProblemCompare } from "@/components/marketing/problem-compare";
import { SafetySection } from "@/components/marketing/safety-section";
import { Steps } from "@/components/marketing/steps";
import { VerticalStrip } from "@/components/marketing/vertical-strip";
import { DeckSection, SectionDeck } from "@/components/marketing/section-deck";

/**
 * The home page, as a deck.
 *
 * Each section fills the screen and depth carries the transition: the one being
 * read sits forward, the ones around it scale back and take a veil. It reads as
 * moving through a stack rather than past a list, which means the page is
 * understood one argument at a time.
 *
 * Order carries that argument, and it moves from scale to detail: a whole list
 * going out (the hero's board), then why a completed call tells you nothing and
 * what one call actually returns, then the four steps, what you get, who it is
 * for, the guards, the price, the close.
 *
 * That first move used to be three moves. The hero, `Listening` and
 * `LiveExtraction` all said *voice becomes typed data*, in ascending order of
 * quality, so the strongest telling arrived third to a reader who had already
 * seen the idea twice. `Listening` is gone and the hero now shows the one thing
 * none of them did - a list of calls at once - which is what lets the section
 * below it go deep on a single call without repeating anything.
 *
 * Pricing reads last before the close on purpose: the cost of something is a
 * fair question only once a visitor knows what it does, and the guards are the
 * argument that most needs to land before a number does.
 */
export default function HomePage() {
  return (
    <>
      <Hero />

      <SectionDeck>
        {/* The ids here are the *public* anchor names — the ones the header's
            Product menu, the footer and any external link point at. They used to
            be split: the deck section carried a short internal name (`how`,
            `guards`) while the component inside it carried the public one
            (`how-it-works`, `safety`), so `/#how-it-works` scrolled to the inner
            element and landed 226px above where the deck section centres its
            content — while `/#capabilities` happened to land correctly, because
            that name existed *twice* and the deck section won on document order.
            One id per section, on the section that owns the screen. */}
        {/* `ProblemCompare` (with `LiveExtraction`) was built, complete, and
            never mounted anywhere — 649 lines of the sharpest argument on the
            site sitting unused. It earns its screen: the same call resolving
            two ways, live, which is exactly the "why not just read the log"
            objection this page otherwise only asserts an answer to. */}
        <DeckSection id="problem">
          <ProblemCompare />
        </DeckSection>

        <DeckSection id="how-it-works">
          <Steps />
        </DeckSection>

        <DeckSection id="capabilities">
          <CapabilityGrid />
        </DeckSection>

        <DeckSection id="verticals">
          <VerticalStrip />
        </DeckSection>

        <DeckSection id="safety">
          <SafetySection />
        </DeckSection>

        <DeckSection id="pricing">
          <PricingPreview />
        </DeckSection>
      </SectionDeck>

      <FinalCta />
    </>
  );
}
