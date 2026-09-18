import { AgentForge } from "@/components/marketing/agent-forge";
import { FinalCta } from "@/components/marketing/final-cta";
import { Hero } from "@/components/marketing/hero";
import { NeedsPerson } from "@/components/marketing/needs-person";
import { PricingPreview } from "@/components/marketing/pricing-preview";
import { ProblemCompare } from "@/components/marketing/problem-compare";
import { ProviderOrbit } from "@/components/marketing/provider-orbit";
import { RunFloor } from "@/components/marketing/run-floor";
import { SafetySection } from "@/components/marketing/safety-section";
import { Steps } from "@/components/marketing/steps";
import { VerticalStrip } from "@/components/marketing/vertical-strip";
import { DeckSection, SectionDeck } from "@/components/marketing/section-deck";

/**
 * The home page is one run, told in order.
 *
 * The page walks the loop the product runs: the hero shows a run mid-flight
 * (staged in depth, the board tilted toward the reader), then why a completed
 * call tells you nothing, the agent being briefed, one contact travelling
 * through the real UI, the whole list at volume, the rows that need a person,
 * the providers it runs on, who it's for, the guards, the price, the close.
 *
 * **Every scene plays itself.** The board ticks, the agent assembles on a
 * loop, the steps advance, the sentence lights - all on timers gated to the
 * viewport, none of it driven by scroll. A scroll-scrubbed version was built
 * and reverted on the product owner's review: the reader should watch the
 * product run, not crank it. Scrolling only moves between sections, which the
 * deck's snap and depth transition already make feel deliberate. Under
 * reduced motion every scene renders assembled and still.
 *
 * The rebuild also retired every claim the code does not keep: the capability
 * grid (allowlist / ceiling / rate-limit / retry / sentiment - see ISSUES.md)
 * is gone rather than reworded, its true halves absorbed by `agent`, `floor`
 * and `safety`. The ids here are the public anchor names the header's Product
 * menu and the footer point at - one id per section, on the section that owns
 * the screen.
 */
export default function HomePage() {
  return (
    <>
      <Hero />

      <SectionDeck>
        {/* The argument: the same call resolving two ways, live. Scale is the
            hero's claim; depth on a single call is this one's. */}
        <DeckSection id="problem">
          <ProblemCompare />
        </DeckSection>

        {/* The product's core object, assembling itself on a loop: brief →
            legs → fields → ready. */}
        <DeckSection id="agent">
          <AgentForge />
        </DeckSection>

        {/* One contact through the real product UI, advancing on its own. */}
        <DeckSection id="how-it-works">
          <Steps />
        </DeckSection>

        {/* The volume claim, lighting word by word over the field. */}
        <DeckSection id="floor">
          <RunFloor />
        </DeckSection>

        <DeckSection id="escalations">
          <NeedsPerson />
        </DeckSection>

        <DeckSection id="providers">
          <ProviderOrbit />
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
