import { CaretRightIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { SectionHeading } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";
import { VERTICALS } from "@/lib/verticals";

/**
 * Built for — the four solution pages.
 *
 * Rendered as rows, not cards: this is a list of four things and should look
 * like one. Each row carries the literal artefact that makes the section's claim
 * checkable — the first typed fields the vertical's result schema returns — so
 * the space reads as substance rather than a sparse link list.
 */
export function VerticalStrip() {
  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          eyebrow="Built for"
          title="Teams that live on the phone."
          sub="One engine — the goal and result schema already written for how your team works."
        />
      </Reveal>

      <ul className="mt-8 border-t border-rule">
        {VERTICALS.map((vertical, i) => (
          <Reveal key={vertical.slug} delayMs={Math.min(i, 11) * 60}>
            <li className="border-b border-rule">
              <Link
                href={`/solutions/${vertical.slug}`}
                className="group flex items-center gap-6 py-5 transition-colors duration-(--dur-micro) hover:bg-surface-hover"
              >
                <div className="min-w-0 flex-1">
                  <span className="block text-h4 font-medium text-text">{vertical.name}</span>
                  {/* The result schema, in the flesh: the exact fields returned. */}
                  <span className="mt-2 hidden flex-wrap items-center gap-1.5 sm:flex">
                    <span className="font-mono text-data text-text-mute">returns</span>
                    {vertical.schema.slice(0, 3).map((field) => (
                      <span
                        key={field.key}
                        className="rounded bg-surface-sunken px-1.5 py-0.5 font-mono text-data text-text-mute"
                      >
                        {field.key}
                      </span>
                    ))}
                    <span className="font-mono text-data text-text-mute">
                      +{vertical.schema.length - 3} more
                    </span>
                  </span>
                </div>

                <span className="hidden max-w-[15rem] text-small text-text-dim md:block">
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
