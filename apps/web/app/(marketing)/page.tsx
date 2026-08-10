import { CapabilityGrid } from "@/components/marketing/capability-grid";
import { FinalCta } from "@/components/marketing/final-cta";
import { Hero } from "@/components/marketing/hero";
import { Listening } from "@/components/marketing/listening";
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
 * list what you get, name who it is for, prove the guards, close.
 *
 * There was a pricing section between the guards and the close. It is gone
 * until the numbers are actually decided - it was rendering `TODO` chips where
 * the prices belong, which is worse than not making the claim at all. The close
 * (`FinalCta`) sits on the base ground, so removing the section that preceded it
 * does not put two `sand` grounds next to each other.
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

        <DeckSection id="how">
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
      </SectionDeck>

      <FinalCta />
    </>
  );
}
