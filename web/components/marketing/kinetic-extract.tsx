"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/cn";
import { usePrefersReducedMotion } from "@/lib/hooks/use-external-store";

/**
 * Extraction shown as a typographic event: the load-bearing words lift out of the
 * spoken line and fly into their field slots, leaving the sentence greyed where
 * they were.
 *
 * The point is that the source and the result are on screen together. A schema
 * block on its own asks you to trust that the fields came from somewhere; this
 * shows which words they came from.
 *
 * Deliberately imperative. The flight is a one-shot DOM effect with no state a
 * re-render could ever need, so it writes to the nodes directly rather than
 * routing three booleans through React — which is also why there is no
 * setState-in-effect here to disable a lint rule over.
 *
 * Fires once, when the section is first reached. It does not replay on scroll:
 * a page that re-animates every time you pass it is what makes a site feel like
 * a template.
 */

const LINE =
  "Hi Aditi, this is CallFlow calling about your holiday enquiry to Dubai. Is now a good time?";

/** word → the field it becomes. `as` overrides when the field value differs. */
const PICKS: { word: string; key: string; as?: string }[] = [
  { word: "Dubai", key: "destination" },
  { word: "holiday", key: "category" },
  { word: "enquiry", key: "outcome", as: "interested" },
];

export function KineticExtract({ className }: { className?: string }) {
  const reduced = usePrefersReducedMotion();
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const land = (pick: (typeof PICKS)[number]) => {
      const slot = root.querySelector<HTMLElement>(`[data-slot="${pick.key}"]`);
      const src = root.querySelector<HTMLElement>(`[data-w="${pick.word}"]`);
      if (slot) slot.textContent = pick.as ?? pick.word;
      src?.setAttribute("data-lifted", "true");
    };

    if (reduced) {
      PICKS.forEach(land);
      return;
    }

    let done = false;
    const timers: number[] = [];
    const flyers: HTMLElement[] = [];

    const play = () => {
      if (done) return;
      done = true;

      PICKS.forEach((pick, i) => {
        timers.push(
          window.setTimeout(() => {
            const src = root.querySelector<HTMLElement>(`[data-w="${pick.word}"]`);
            const dst = root.querySelector<HTMLElement>(`[data-slot="${pick.key}"]`);
            // If either end is missing, still deliver the value rather than
            // leaving the slot permanently empty.
            if (!src || !dst) return land(pick);

            const a = src.getBoundingClientRect();
            const b = dst.getBoundingClientRect();
            const flyer = document.createElement("span");
            flyer.textContent = pick.as ?? pick.word;
            flyer.setAttribute("aria-hidden", "true");
            const cs = getComputedStyle(src);
            Object.assign(flyer.style, {
              position: "fixed",
              left: `${a.left}px`,
              top: `${a.top}px`,
              font: cs.font,
              color: cs.color,
              pointerEvents: "none",
              zIndex: "40",
              willChange: "transform",
            });
            document.body.appendChild(flyer);
            flyers.push(flyer);
            src.setAttribute("data-lifted", "true");

            const anim = flyer.animate(
              [
                { transform: "translate(0,0) scale(1)" },
                {
                  transform: `translate(${(b.left - a.left) * 0.5}px, ${
                    (b.top - a.top) * 0.34
                  }px) scale(1.05)`,
                  offset: 0.55,
                },
                {
                  transform: `translate(${b.left - a.left}px, ${b.top - a.top}px) scale(0.72)`,
                },
              ],
              { duration: 850, easing: "cubic-bezier(.22,1,.36,1)", fill: "forwards" },
            );
            anim.onfinish = () => {
              dst.textContent = pick.as ?? pick.word;
              flyer.remove();
            };
          }, 260 + i * 340),
        );
      });
    };

    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            play();
            io.disconnect();
          }
        }
      },
      { threshold: 0.35 },
    );
    io.observe(root);

    return () => {
      io.disconnect();
      timers.forEach(clearTimeout);
      flyers.forEach((f) => f.remove());
    };
  }, [reduced]);

  return (
    <div ref={rootRef} className={cn("flex flex-col gap-6", className)}>
      <p className="measure text-h3 leading-snug text-text">
        {LINE.split(" ").map((word, i) => {
          const bare = word.replace(/[.,?]/g, "");
          const pick = PICKS.find((p) => p.word === bare);
          return (
            <span
              key={i}
              {...(pick ? { "data-w": bare } : {})}
              className={cn(
                "transition-colors duration-300",
                pick && "data-[lifted=true]:text-text-mute",
              )}
            >
              {word}{" "}
            </span>
          );
        })}
      </p>

      <dl className="flex max-w-md flex-col border-t border-rule">
        {PICKS.map((pick) => (
          <div
            key={pick.key}
            className="flex min-h-11 items-center justify-between gap-4 border-b border-rule py-2"
          >
            <dt className="font-mono text-data text-text-mute">{pick.key}</dt>
            <dd className="text-small font-medium">
              <span data-slot={pick.key} />
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
