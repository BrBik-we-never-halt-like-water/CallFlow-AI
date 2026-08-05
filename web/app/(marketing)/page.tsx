import { CapabilityGrid } from "@/components/marketing/capability-grid";
import { FinalCta } from "@/components/marketing/final-cta";
import { Hero } from "@/components/marketing/hero";
import { PricingPreview } from "@/components/marketing/pricing-preview";
import { ProblemCompare } from "@/components/marketing/problem-compare";
import { SafetySection } from "@/components/marketing/safety-section";
import { Steps } from "@/components/marketing/steps";
import { VerticalStrip } from "@/components/marketing/vertical-strip";
import { FlowDivider } from "@/components/marketing/flow-divider";

/**
 * The home page.
 *
 * Section order carries the argument: show the product working, explain why a
 * call log is not enough, show the four steps, list what you get, name who it is
 * for, prove the guards, price it, then close on the free dry run.
 *
 * Sections are separated by a lamped rule rather than by alternating background
 * bands. The one surface inversion on the page is saved for the closing CTA.
 */
export default function HomePage() {
  return (
    <>
      <Hero />

      <FlowDivider />
      <ProblemCompare />

      <FlowDivider />
      <Steps />

      <FlowDivider />
      <CapabilityGrid />

      <FlowDivider />
      <VerticalStrip />

      <FlowDivider />
      <SafetySection />

      <FlowDivider />
      <PricingPreview />

      <FinalCta />
    </>
  );
}
