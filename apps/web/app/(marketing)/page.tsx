import { CapabilityGrid } from '@/components/marketing/capability-grid';
import { FinalCta } from '@/components/marketing/final-cta';
import { Hero } from '@/components/marketing/hero';
import { PricingPreview } from '@/components/marketing/pricing-preview';
import { ProblemCompare } from '@/components/marketing/problem-compare';
import { SafetySection } from '@/components/marketing/safety-section';
import { Steps } from '@/components/marketing/steps';
import { VerticalStrip } from '@/components/marketing/vertical-strip';

/**
 * The home page.
 *
 * Section order carries the argument: show the product working, explain why a
 * call log is not enough, show the four steps, list what you get, name who it is
 * for, prove the guards, price it, then close on the free daily call budget.
 *
 * Sections are separated by open space rather than by rules or alternating
 * background bands. The one surface inversion on the page is saved for the
 * closing CTA.
 */
export default function HomePage() {
  return (
    <>
      <Hero />

      <SpineDivider />
      <ProblemCompare />

      <SpineDivider />
      <Steps />

      <SpineDivider />
      <CapabilityGrid />

      <SpineDivider />
      <VerticalStrip />

      <SpineDivider />
      <SafetySection />

      <SpineDivider />
      <PricingPreview />

      <FinalCta />
    </>
  );
}

/** Open space between sections - the page's only separator. */
function SpineDivider() {
  return <div aria-hidden className="h-(--space-section)" />;
}
