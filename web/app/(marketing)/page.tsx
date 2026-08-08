import { CapabilityGrid } from "@/components/marketing/capability-grid";
import { FinalCta } from "@/components/marketing/final-cta";
import { Hero } from "@/components/marketing/hero";
import { Listening } from "@/components/marketing/listening";
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
 * Order carries that argument: show the product working, show it still working
 * while you read, explain why a call log is not enough, show the four steps,
 * list what you get, name who it is for, prove the guards, price it, close.
 *
 * Ground alternates so no two adjacent sections share a surface. At this size a
 * repeated ground makes two sections read as one.
 */
export default function HomePage() {
  return (
    <>
      <Hero />

      <SectionDeck>
        <DeckSection id="listening" ground="sand">
          <div className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
            <Listening />
          </div>
        </DeckSection>

        <DeckSection id="problem">
          <ProblemCompare />
        </DeckSection>

        <DeckSection id="how" ground="sand">
          <Steps />
        </DeckSection>

        <DeckSection id="capabilities">
          <CapabilityGrid />
        </DeckSection>

        <DeckSection id="verticals" ground="sunken">
          <VerticalStrip />
        </DeckSection>

        <DeckSection id="guards" ground="sand">
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
