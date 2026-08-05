import { CaretRightIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { SectionHeading } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";
import { VERTICALS } from "@/lib/verticals";

/**
 * Built for — the four solution pages.
 *
 * Rendered as rows, not cards. This is a list of four things, and a list should
 * look like one; three-across cards would give each vertical more visual weight
 * than it earns and make the section compete with the capability grid above it.
 */
export function VerticalStrip() {
  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          eyebrow="Built for"
          title="Teams that live on the phone."
          sub="The same engine, with the goal and the result schema already written for the way your team works."
        />
      </Reveal>

      <ul className="mt-8 border-t border-rule">
        {VERTICALS.map((vertical, i) => (
          <Reveal key={vertical.slug} delayMs={Math.min(i, 11) * 60}>
            <li className="border-b border-rule">
              <Link
                href={`/solutions/${vertical.slug}`}
                className="group flex items-center gap-4 py-5 transition-colors duration-(--dur-micro) hover:bg-surface-hover"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-h4 font-medium text-text">
                    {vertical.name}
                  </span>
                  <span className="mt-0.5 block text-small text-text-mute">
                    {vertical.metricLabel}
                  </span>
                </span>

                <span className="hidden max-w-xs text-small text-text-dim sm:block">
                  {vertical.metric}
                </span>

                <CaretRightIcon
                  aria-hidden
                  className="size-4 shrink-0 text-text-mute transition-transform duration-(--dur-base) ease-(--ease-out) group-hover:translate-x-1"
                />
              </Link>
            </li>
          </Reveal>
        ))}
      </ul>
    </section>
  );
}
