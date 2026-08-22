import Image from 'next/image';
import {
  siAlibabacloud,
  siAnthropic,
  siDeepgram,
  siDeepseek,
  siElevenlabs,
  siGooglecloud,
  siGooglegemini,
  siMeta,
  siMistralai,
  siOpenrouter,
  siQwen,
  siRime,
  siX,
} from 'simple-icons';
import { BRAND_LOGOS } from '@/lib/brand-logos';
import { cn } from '@/lib/cn';

/**
 * Provider marks for the agent builder, in each vendor's own colour.
 *
 * This reverses the "written names only" rule `agent-card.tsx` used to carry -
 * that rule existed because reproducing a wordmark from memory is a guess.
 * These are not guesses: they are the brand's own published SVG paths and
 * published hex, from Simple Icons. Where Simple Icons has no entry (Sarvam,
 * OpenAI, Twilio, Plivo) the fallback is a monogram, not an invented logo,
 * built the same way `OrgMark` builds a logo-less organisation's initial in
 * `app-nav.tsx`.
 *
 * Brand colour does not breach the lamp rule (CLAUDE.md non-negotiable #10):
 * these are third-party identities, not this product's own palette, and none
 * of them is being used to signal call state. It is also why the canvas behind
 * them went flat black - eight vendor colours need a neutral ground to sit on.
 */

interface Brand {
  path: string;
  /** The vendor's published hex. */
  hex: string;
  /** Some marks are published as near-black, which disappears on the dark app
   *  canvas. Where a vendor has no light-surface variant, its mark goes white
   *  rather than being tinted into a colour the brand never uses. */
  onDark?: string;
}

const BRANDS: Record<string, Brand> = {
  alibaba: { path: siAlibabacloud.path, hex: `#${siAlibabacloud.hex}` },
  anthropic: { path: siAnthropic.path, hex: `#${siAnthropic.hex}`, onDark: '#FFFFFF' },
  deepgram: { path: siDeepgram.path, hex: `#${siDeepgram.hex}` },
  deepseek: { path: siDeepseek.path, hex: `#${siDeepseek.hex}` },
  elevenlabs: { path: siElevenlabs.path, hex: `#${siElevenlabs.hex}`, onDark: '#FFFFFF' },
  google: { path: siGooglegemini.path, hex: `#${siGooglegemini.hex}` },
  'google-cloud': { path: siGooglecloud.path, hex: `#${siGooglecloud.hex}` },
  meta: { path: siMeta.path, hex: `#${siMeta.hex}` },
  mistralai: { path: siMistralai.path, hex: `#${siMistralai.hex}` },
  openrouter: { path: siOpenrouter.path, hex: `#${siOpenrouter.hex}` },
  qwen: { path: siQwen.path, hex: `#${siQwen.hex}` },
  rime: { path: siRime.path, hex: `#${siRime.hex}`, onDark: '#FFFFFF' },
  'x-ai': { path: siX.path, hex: `#${siX.hex}`, onDark: '#FFFFFF' },
};

/**
 * Real marks supplied as files, for vendors Simple Icons doesn't carry.
 *
 * Checked before the monogram fallback: an actual asset beats initials, and
 * unlike a path written from memory it is the vendor's own artwork. Keyed by
 * `vendorKey`, so every OpenAI id - the LLM models, Whisper, the TTS voices -
 * resolves to the one file.
 */
const ASSETS: Record<string, string> = {
  openai: '/openai.webp',
};

/**
 * A vendor key here to a provider id in `BRAND_LOGOS`, where the two differ.
 *
 * The integrations page keys artwork by the provider ids in
 * `domain/providers.py`; this file keys it by the vendor half of a catalog
 * entry id. Mostly they agree, and these are the ones that do not.
 */
const LOGO_ALIAS: Record<string, string> = {
  azure: 'azure_speech',
  'azure-stt': 'azure_speech',
  'azure-tts': 'azure_speech',
  'groq-whisper': 'groq',
  playht: 'playai',
  'x-ai': 'xai',
};

/**
 * Monogram text for vendors with no artwork from any source. Drawing their
 * marks from memory would be a guess, and a wrong logo is worse than no logo -
 * so these get initials until someone supplies the real asset.
 *
 * Most of this map is now unreachable and kept deliberately: `BRAND_LOGOS`
 * (fetched from each vendor's own site by
 * `apps/web/scripts/fetch-brand-logos.mjs`) covers eleven of these fourteen,
 * and it is checked first. What is left is the fallback for a vendor the fetch
 * script could not reach - and the entries that are currently shadowed cost
 * nothing while making that the answer if a logo is ever removed.
 */
const MONOGRAM: Record<string, string> = {
  sarvam: 'Sa',
  assemblyai: 'As',
  groq: 'Gq',
  'groq-whisper': 'Gq',
  speechmatics: 'Sp',
  gladia: 'Gl',
  azure: 'Az',
  'azure-stt': 'Az',
  'azure-tts': 'Az',
  cartesia: 'Ca',
  playht: 'Pl',
  lmnt: 'Lm',
  twilio: 'Tw',
  plivo: 'Pv',
};

/**
 * The vendor behind a catalog entry id. STT and TTS ids are already vendor
 * names (`sarvam`, `deepgram`); LLM ids are OpenRouter model paths whose first
 * segment is the vendor (`anthropic/claude-3.5-haiku`).
 */
export function vendorKey(id: string): string {
  const [head] = id.split('/');
  if (head === 'meta-llama') return 'meta';
  if (head === 'qwen') return 'qwen';
  // STT/TTS ids are `vendor` or `vendor-model` (`deepgram-nova-2`,
  // `google-tts`). Longest-prefix wins so `google-cloud` is not read as
  // `google`, and an unknown suffix still resolves to its vendor.
  const exact = BRANDS[head] ?? MONOGRAM[id];
  if (exact) return BRANDS[head] ? head : id;
  // `ASSETS` joins the prefix search alongside `BRANDS`: `openai-whisper` and
  // `openai-tts` have no monogram of their own any more and must resolve to
  // the `openai` file rather than falling through to a bare initial.
  const prefix = [...Object.keys(BRANDS), ...Object.keys(ASSETS)]
    .filter((k) => id === k || id.startsWith(`${k}-`))
    .sort((a, b) => b.length - a.length)[0];
  return prefix ?? head;
}

export function ProviderIcon({
  id,
  className,
  /** Drop brand colour and inherit the surrounding text colour instead - for
   *  places where the mark is decoration beside a label, not the identifier. */
  monochrome,
}: {
  id: string;
  className?: string;
  monochrome?: boolean;
}) {
  const key = vendorKey(id);
  const brand = BRANDS[key];

  if (brand) {
    return (
      <svg
        role="presentation"
        viewBox="0 0 24 24"
        className={cn('size-4 shrink-0', className)}
        style={{
          // `light-dark()` reads the surface's own `color-scheme`, so one
          // declaration covers both themes without a duplicated dark rule.
          fill: monochrome
            ? 'currentColor'
            : `light-dark(${brand.hex}, ${brand.onDark ?? brand.hex})`,
        }}
      >
        <path d={brand.path} />
      </svg>
    );
  }

  // Self-hosted vendor artwork, shared with the integrations page so the same
  // vendor does not render as a logo on one screen and as initials on another.
  // Below `BRANDS` on purpose: a Simple Icons path is a vector that takes
  // `currentColor`, so it still wins where one exists.
  const logo = BRAND_LOGOS[LOGO_ALIAS[key] ?? key];
  if (logo) {
    return (
      // A plain <img>, matching `BrandMark` and the four other places in this
      // app that do the same: already sized for this slot at 128px or vector,
      // so the optimiser has nothing to gain and would add a request per row of
      // the provider wheel.
      <img
        src={`/brands/${logo}`}
        alt=""
        aria-hidden
        loading="lazy"
        decoding="async"
        className={cn(
          'size-4 shrink-0 rounded-[0.2em] object-contain',
          monochrome && 'opacity-80',
          className,
        )}
      />
    );
  }

  const asset = ASSETS[key];
  if (asset) {
    return (
      // A supplied file, not a path drawn from memory - the same standard the
      // Simple Icons marks above meet. The asset is white-on-transparent, so
      // on a light surface it is inverted rather than left invisible.
      <Image
        src={asset}
        alt=""
        aria-hidden
        // Intrinsic size for the optimiser. The rendered size comes from the
        // `size-*` class, and 32 is 2x the 16px default so it stays sharp on
        // a retina screen and at the 20px the wheel rows use.
        width={32}
        height={32}
        className={cn(
          // The file is white-on-transparent: correct on the dark app canvas,
          // invisible on a light one, so light inverts it to black.
          'size-4 shrink-0 object-contain invert dark:invert-0',
          monochrome && 'opacity-80',
          className,
        )}
      />
    );
  }

  return (
    <span
      aria-hidden
      className={cn(
        'flex size-4 shrink-0 items-center justify-center rounded-[0.25em] bg-text-mute font-mono text-[0.45em] font-bold leading-none text-surface',
        className,
      )}
    >
      {MONOGRAM[key] ?? key.charAt(0).toUpperCase()}
    </span>
  );
}
