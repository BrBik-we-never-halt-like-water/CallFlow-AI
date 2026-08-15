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
          title="Teams that live on the phone."
          sub="One engine. The goal and schema come written for your team."
        />
      </Reveal>

      <ul className="mt-(--deck-gap) border-t border-rule">
        {VERTICALS.map((vertical, i) => (
          <Reveal key={vertical.slug} delayMs={Math.min(i, 11) * 60}>
            <li className="border-b border-rule">
              <Link
                href={`/solutions/${vertical.slug}`}
                className="group flex items-center gap-6 py-[clamp(12px,2.2vh,26px)] transition-colors duration-(--dur-micro) hover:bg-surface-hover"
              >
                <div className="min-w-0 flex-1">
                  <span className="block text-h4 font-medium text-text">{vertical.name}</span>

                  {/* The lead pain line, not the goal template. The goal is the
                      better artefact in principle — it is the thing a buyer is
                      really evaluating — but it is stored with its runtime
                      placeholders (`{name}`, `{context[role]}`) and renders as
                      `You are calling {name} about the {context[role]} role`,
                      which reads as a broken page rather than as a real
                      configuration. The goal belongs here once something
                      substitutes example values into it; until then the pain
                      line is true, buyer-facing, and complete on its own. */}
                  <span className="mt-2 block max-w-[68ch] text-small text-text-dim">
                    {vertical.pain[0]}
                  </span>

                  {/* The result schema, in the flesh: the exact fields returned. */}
                  <span className="mt-2.5 hidden flex-wrap items-center gap-1.5 sm:flex">
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

                <span className="hidden max-w-[15rem] shrink-0 flex-col gap-1 md:flex">
                  <span className="font-mono text-label tracking-wider text-text-mute uppercase">
                    {vertical.metricLabel}
                  </span>
                  <span className="text-small text-text-dim">{vertical.metric}</span>
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
