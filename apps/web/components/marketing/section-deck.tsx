"use client";

import { cn } from "@/lib/cn";
import { useScrollDepth } from "@/lib/hooks/use-scroll-depth";

/**
 * The home page as a deck of sections.
 *
 * Depth does the transition: the section nearest the viewport's centre sits
 * forward at full presence while the ones around it scale back and take a veil.
 * Scrolling reads as moving through a stack rather than past a list.
 *
 * **One section fills the screen, and the fix for an empty one is more content,
 * not less height.** These were briefly shortened to content-height because they
 * measured 47-60% empty. That traded one problem for a worse one: at ~700px a
 * neighbouring section is always visible, so navigating to a section no longer
 * shows you that section — it shows you a piece of three. The height is back to
 * `100svh` and the sections have been filled instead.
 *
 * If a section here looks empty, the answer is to give it something to say. Do
 * not shrink it; that breaks the one thing this layout exists to do.
 *
 * `100svh` rather than `100vh` so mobile browser chrome does not cut the last
 * line off, and `min-height` rather than `height` — a section that genuinely
 * needs more room takes it, and nothing is ever clipped. Content wins over the
 * grid.
 */
export function SectionDeck({ children }: { children: React.ReactNode }) {
  const ref = useScrollDepth<HTMLDivElement>();
  return (
    <div ref={ref} className="deck">
      {children}
    </div>
  );
}

export function DeckSection({
  id,
  ground = "base",
  /** Vertically centre the content. Off for sections that are naturally tall. */
  centred = true,
  className,
  children,
}: {
  id?: string;
  ground?: "base" | "sand" | "sunken";
  centred?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      data-deck-section
      className={cn(
        // Height lives in `.deck-section` (globals.css), not here — it is
        // `100svh` minus the sticky header, which needs the token in a calc.
        "deck-section relative flex flex-col",
        centred ? "justify-center" : "justify-start",
        ground === "sand" && "ground-sand",
        ground === "sunken" && "ground-sunken",
        className,
      )}
    >
      {/* Full width on purpose: the section components already bring their own
          container, and wrapping them in a second one doubles the gutter. */}
      <div className="deck-inner w-full">{children}</div>
    </section>
  );
}
