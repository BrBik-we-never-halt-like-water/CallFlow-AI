"use client";

import { useEffect, useState } from "react";
import { BrandLockup } from "@/components/brand/wordmark";

const BARS = 14;
/** Hard ceiling: the overlay is removed from the DOM by now no matter what. */
const DISMISS_MS = 1700;

/**
 * First-paint brand loader: the CallFlow wordmark over a voice waveform that
 * "listens" while the page settles, then the overlay fades and is removed.
 *
 * Belt and suspenders on dismissal so it can never trap the page: the CSS fade
 * (see `.site-loader` in globals.css) hides it visually and, even with JS off,
 * `visibility: hidden` stops it blocking; a JS timeout then unmounts it outright.
 * Rendered in the root layout, so it plays once per full load — not on
 * client-side navigations — and it is skipped under prefers-reduced-motion.
 */
export function SiteLoader() {
  const [gone, setGone] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setGone(true), DISMISS_MS);
    return () => clearTimeout(timer);
  }, []);

  if (gone) return null;

  return (
    <div className="site-loader" aria-hidden>
      <div className="flex flex-col items-center gap-7">
        <BrandLockup />
        <div className="flex h-10 items-center gap-[3px]">
          {Array.from({ length: BARS }).map((_, i) => (
            <span
              key={i}
              className="loader-bar h-full w-[3px] rounded-full bg-text"
              style={{ animationDelay: `${i * 70}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
