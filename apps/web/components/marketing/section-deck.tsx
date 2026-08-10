"use client";

import { cn } from "@/lib/cn";
import { useScrollDepth } from "@/lib/hooks/use-scroll-depth";

/**
 * The home page as a deck of full-height sections.
 *
 * One section fills the screen at a time, and depth does the transition: the
 * section at the centre of the viewport sits forward at full presence while the
 * ones around it scale back and take a veil. Scrolling reads as moving through
 * a stack rather than past a list.
 *
 * `100svh` rather than `100vh` so mobile browser chrome does not cut the last
 * line off, and `min-height` rather than `height` throughout — a section that
 * genuinely needs more room takes it, and nothing is ever clipped. Content wins
 * over the grid.
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
        "deck-section relative flex min-h-[100svh] flex-col py-(--space-band)",
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
