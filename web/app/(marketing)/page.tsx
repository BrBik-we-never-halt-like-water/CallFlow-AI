import { CapabilityGrid } from "@/components/marketing/capability-grid";
import { FinalCta } from "@/components/marketing/final-cta";
import { Hero } from "@/components/marketing/hero";
import { PricingPreview } from "@/components/marketing/pricing-preview";
import { ProblemCompare } from "@/components/marketing/problem-compare";
import { SafetySection } from "@/components/marketing/safety-section";
import { Steps } from "@/components/marketing/steps";
import { VerticalStrip } from "@/components/marketing/vertical-strip";
import { cn } from "@/lib/cn";

/**
 * The home page.
 *
 * Section order carries the argument: show the product working, explain why a
 * call log is not enough, show the four steps, list what you get, name who it is
 * for, prove the guards, price it, then close on the free daily call budget.
 *
 * Rhythm comes from the ground rather than from a rule or a gap. Each section is
 * a full-bleed band that owns its own vertical space, so one section reads as
 * dominant at a time instead of several fragments sharing a screen.
 *
 * Sand is punctuation, not alternation: it lands on the two explanatory
 * sections — how it works, and the guards — which are the moments the page most
 * needs to feel reassuring rather than technical. Using it twice in six keeps it
 * a deliberate accent; using it every other band would just make the page beige.
 */
export default function HomePage() {
  return (
    <>
      <Band top>
        <Hero />
      </Band>

      <Band>
        <ProblemCompare />
      </Band>

      <Band ground="sand">
        <Steps />
      </Band>

      <Band>
        <CapabilityGrid />
      </Band>

      <Band>
        <VerticalStrip />
      </Band>

      <Band ground="sand">
        <SafetySection />
      </Band>

      <Band>
        <PricingPreview />
      </Band>

      <FinalCta />
    </>
  );
}

/**
 * A full-bleed horizontal band. The ground runs edge to edge while the section
 * inside stays on the marketing measure.
 *
 * `top` halves the leading space: the hero sits directly under the header and
 * does not need a full section gap above it.
 */
function Band({
  ground = "base",
  top = false,
  children,
}: {
  ground?: "base" | "sand";
  top?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "pb-(--space-band)",
        // The hero owns its own leading space and sits directly under the
        // header, so it takes no band padding above it.
        top ? "pt-0" : "pt-(--space-band)",
        ground === "sand" && "ground-sand",
      )}
    >
      {children}
    </div>
  );
}
