'use client';

import { useState } from 'react';
import { BRAND_LOGOS } from '@/lib/brand-logos';
import { cn } from '@/lib/cn';

/**
 * A provider's mark: its real logo where we have one, its initial where we
 * don't.
 *
 * This used to be 19 monochrome SVG paths inlined from `simple-icons`, with a
 * monogram for the other 38. That was the right call while the only source of
 * marks was a library that had lost most of them to trademark requests - a grid
 * mixing full-colour logos with grey letters reads as broken rather than as
 * varied, so *everything* was grey. The constraint is gone: the marks are now
 * fetched from each vendor's own site into `public/brands/`
 * (`scripts/fetch-brand-logos.mjs`), which covers 56 of the 57. At that ratio
 * the monogram is a genuine exception rather than a third of the page, and the
 * grid is coherent in the other direction - real logos, one fallback.
 *
 * Self-hosted rather than loaded from a favicon service, for two reasons worth
 * stating: a per-card request to a third party would tell them which vendors an
 * organisation is shopping for, and the whole grid would be empty offline.
 *
 * **The logo fills the plate.** Roughly half of these are app-icon style, with
 * the vendor's own colour bled to the edges; the other half are transparent
 * marks. Padding the plate would frame the first kind as a small square inside
 * a square. `overflow-hidden` plus `object-contain` lets a full-bleed icon read
 * as a tile and a transparent mark sit on the plate's own surface, without the
 * component having to know which it has.
 *
 * `connected` is carried in the plate's ring rather than a badge beside it: at
 * this grid density the mark is the first thing the eye lands on, so it is the
 * cheapest place to put the one bit of state that matters.
 */
export function BrandMark({
  providerId,
  name,
  connected = false,
  className,
}: {
  providerId: string;
  name: string;
  connected?: boolean;
  className?: string;
}) {
  const file = BRAND_LOGOS[providerId];
  // A logo that 404s or is corrupt leaves an empty plate, which looks like a
  // rendering bug. Falling back to the monogram makes it look intentional.
  const [broken, setBroken] = useState(false);

  return (
    <span
      aria-hidden
      className={cn(
        'flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-md border',
        'transition-colors duration-(--dur-micro)',
        connected
          ? 'border-rule-strong bg-surface'
          : 'border-rule bg-surface-sunken',
        className,
      )}
    >
      {file && !broken ? (
        // A plain <img>, not next/image: these are 128px-or-vector files already
        // sized for this plate, so there is nothing left to optimise, and the
        // loader would add a request per card to gain it.
        <img
          src={`/brands/${file}`}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setBroken(true)}
          className="size-full object-contain"
        />
      ) : (
        <span className="font-mono text-small font-medium leading-none text-text-dim">
          {name.charAt(0).toUpperCase()}
        </span>
      )}
    </span>
  );
}
