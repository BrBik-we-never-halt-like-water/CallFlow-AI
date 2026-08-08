import { CheckIcon } from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { Tag } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Panel, SectionHeading } from '@/components/ui/panel';
import { Reveal } from '@/components/ui/reveal';
import { PLANS } from '@/lib/pricing';
import { PriceValue, VolumeValue } from './price-value';

/**
 * Compact three-plan preview on the home page, with the detail one click away.
 *
 * A visitor who cannot find out roughly what something costs assumes it is
 * expensive, so the number belongs on the landing page - but the full comparison
 * matrix does not, and putting it here would bury everything below it.
 */
export function PricingPreview() {
  const shown = PLANS.filter((plan) => plan.id !== 'scale');

  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          eyebrow="Pricing"
          title="Start free, pay when you dial."
          sub="Every plan, including Free, only bills for calls that actually connect. A call blocked by one of your safety guards is never billable."
        />
      </Reveal>

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {shown.map((plan, i) => (
          <Reveal key={plan.id} delayMs={i * 60}>
            <Panel
              className={cn(
                'flex h-full flex-col gap-4 p-5',
                // The recommended plan is marked with a 1px ink border and a mono
                // tag - not a coloured banner, which would put arbitrary colour on
                // a page whose colour means call state.
                plan.mostChosen && 'border-text',
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-h4 font-medium text-text">{plan.name}</h3>
                {plan.mostChosen ? <Tag>Most chosen</Tag> : null}
              </div>

              <PriceValue
                amount={plan.monthlyInr}
                currency="INR"
                suffix="/ month"
              />
              <VolumeValue calls={plan.includedCalls} />

              <p className="text-small text-text-dim">{plan.tagline}</p>

              <ul className="flex flex-col gap-1.5">
                {plan.features.slice(0, 4).map((feature) => (
                  <li
                    key={feature}
                    className="flex items-start gap-2 text-small text-text-dim"
                  >
                    <CheckIcon
                      aria-hidden
                      weight="bold"
                      className="mt-1 size-3 shrink-0 text-text-mute"
                    />
                    {feature}
                  </li>
                ))}
              </ul>

              <Button
                asChild
                variant={plan.mostChosen ? 'primary' : 'secondary'}
                className="mt-auto"
              >
                <Link href={plan.ctaHref}>{plan.cta}</Link>
              </Button>
            </Panel>
          </Reveal>
        ))}
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
