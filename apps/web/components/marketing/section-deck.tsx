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
 * **Sections are sized by their content, not by the viewport.** They used to be
 * `min-h-[100svh]`, one full screen each. Measured on a 1080px-tall viewport
 * that left every section between 47% and 60% empty — content ran 435-573px
 * inside a 1080px box — which is what made the page read as a series of mostly
 * blank screens. Height now comes from the content plus `--space-section` top
 * and bottom, so the whitespace is section *rhythm* rather than dead air.
 *
 * The depth effect is unaffected: `use-scroll-depth` compares each section's
 * centre to the viewport's centre and normalises by viewport height, so it never
 * depended on a section being exactly one screen tall. Shorter sections mean a
 * neighbour is more often partly visible, which is the intended tradeoff — the
 * alternative was keeping half a screen of nothing to preserve the illusion.
 *
 * `min-h-[62svh]` stays as a floor, not a target. Nothing on the page currently
 * reaches it (content + padding is taller), so it adds no emptiness today; it
 * exists so a future short section still commands the screen instead of reading
 * as a strip, and so `centred` keeps meaning something. `svh` rather than `vh`
 * so mobile browser chrome cannot cut a line off.
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
        "deck-section relative flex min-h-[62svh] flex-col py-(--space-section)",
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
