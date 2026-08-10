import { CheckIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { SectionHeading } from "@/components/ui/panel";
import { cn } from "@/lib/cn";
import { Reveal } from "@/components/ui/reveal";
import { PLANS } from "@/lib/pricing";
import { PriceValue, VolumeValue } from "./price-value";

/**
 * Compact three-plan preview on the home page, with the detail one click away.
 *
 * A visitor who cannot find out roughly what something costs assumes it is
 * expensive, so the number belongs on the landing page — but the full comparison
 * matrix does not. The recommended plan is made dominant by elevation, a neutral
 * gradient, and a raised badge — never a coloured banner, since colour on this
 * page means call state.
 */
export function PricingPreview() {
  const shown = PLANS.filter((plan) => plan.id !== "scale");

  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          title="Start free, pay when you dial."
          sub="You only spend on calls that actually connect — on every plan, including the free one."
        />
      </Reveal>

      <div className="mt-8 grid items-stretch gap-4 md:grid-cols-3">
        {shown.map((plan, i) => {
          const featured = !!plan.mostChosen;
          return (
            <Reveal key={plan.id} delayMs={i * 60} className="h-full">
              <div
                className={cn(
                  "relative flex h-full flex-col gap-4 overflow-hidden p-5",
                  featured ? "card-feature" : "card-raised",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-h4 font-medium text-text">{plan.name}</h3>
                  {featured ? (
                    <span className="rounded-full bg-text px-2.5 py-1 text-label uppercase tracking-[0.12em] text-surface">
                      Most chosen
                    </span>
                  ) : null}
                </div>

                <div className="flex flex-col gap-1">
                  <PriceValue amount={plan.monthlyInr} currency="INR" suffix="/ month" />
                  <VolumeValue calls={plan.includedCalls} />
                </div>

                <p className="text-small text-text-dim">{plan.tagline}</p>

                <div aria-hidden className="h-px bg-rule" />

                <ul className="flex flex-1 flex-col gap-2.5">
                  {plan.features.slice(0, 2).map((feature) => (
                    <li key={feature} className="flex items-start gap-2.5 text-small text-text-dim">
                      <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full bg-surface-sunken">
                        <CheckIcon aria-hidden weight="bold" className="size-2.5 text-text-mute" />
                      </span>
                      {feature}
                    </li>
                  ))}
                </ul>

                <Button asChild variant={featured ? "primary" : "secondary"} className="mt-auto">
                  <Link href={plan.ctaHref}>{plan.cta}</Link>
                </Button>
              </div>
            </Reveal>
          );
        })}
      </div>

      <Reveal delayMs={200} className="mt-6">
        <Link
          href="/pricing"
          className="inline-flex items-center gap-1.5 text-small font-medium text-text underline decoration-rule-strong underline-offset-4 transition-colors hover:decoration-current"
        >
          See full pricing
          <span aria-hidden>→</span>
        </Link>
      </Reveal>
    </section>
  );
}
