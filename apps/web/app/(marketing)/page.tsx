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
 * Pricing is back in that order, between the guards and the close, after being
 * removed for rendering `TODO` chips where the prices belonged. It reads last
 * before the close on purpose: the cost of something is a fair question only once
 * a visitor knows what it does, and the guards are the argument that most needs
 * to land before a number does.
 *
 * Ground alternates so no two adjacent sections share a surface. At this size a
 * repeated ground makes two sections read as one - which is why pricing takes no
 * `ground` prop: `safety` above it is `sand`, and `FinalCta` below sits on the
 * base ground, so the plain surface between them is the one that keeps all three
 * distinct.
 */
export default function HomePage() {
  return (
    <>
      <Hero />

      <SectionDeck>
        <DeckSection id="listening">
          <div className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
            <Listening />
          </div>
        </DeckSection>

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
