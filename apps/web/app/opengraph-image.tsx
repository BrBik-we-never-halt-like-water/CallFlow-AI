import { ImageResponse } from 'next/og';
import { BRAND } from '@/lib/brand-assets';
import { countLamps, type LampSpec } from '@/lib/lamp';

/**
 * Social card: wordmark, headline, and a lamp strip on the Panel surface.
 *
 * No photography and no vendor mark. The strip is the whole idea of the product in one
 * row, which is the only thing worth putting on a card that gets seen at thumbnail size.
 *
 * Colours come from `lib/brand-assets`, not from literals - `next/og` resolves no CSS
 * custom properties, so this file used to carry its own copy of the palette and that copy
 * went stale at the dark pivot. The caption is counted from the strip for the same
 * reason: it read `9 closed` while the strip rendered six, and said nothing about the
 * three queued lamps sitting right next to the words.
 */
export const alt = 'CallFlow AI - dial the whole list, hear only what needs you';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

/** One run, as lamps. The caption below is counted from exactly this array. */
const STRIP: LampSpec[] = [
  { state: 'jade', label: 'Auto-closed' },
  { state: 'jade', label: 'Auto-closed' },
  { state: 'jade', label: 'Auto-closed' },
  { state: 'flare', label: 'Needs a person' },
  { state: 'jade', label: 'Auto-closed' },
  { state: 'jade', label: 'Auto-closed' },
  { state: 'brass', pulse: true, label: 'Queued for retry' },
  { state: 'jade', label: 'Auto-closed' },
  { state: 'jade', label: 'Auto-closed' },
  { state: 'off', label: 'Queued' },
  { state: 'off', label: 'Queued' },
  { state: 'off', label: 'Queued' },
];

function caption(): string[] {
  const c = countLamps(STRIP);
  const parts: string[] = [];
  if (c.closed) parts.push(`${c.closed} closed`);
  if (c.retry) parts.push(`${c.retry} retry`);
  if (c.needsPerson)
    parts.push(c.needsPerson === 1 ? '1 needs a person' : `${c.needsPerson} need a person`);
  if (c.queued) parts.push(`${c.queued} queued`);
  return parts;
}

export default function OpengraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        background: BRAND.plate,
        padding: 72,
      }}
    >
      {/* Wordmark */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            border: `2px solid ${BRAND.ruleStrong}`,
            borderRadius: 999,
            padding: '10px 16px',
          }}
        >
          {[BRAND.lamp.jade, BRAND.lamp.brass, BRAND.lamp.flare].map((colour) => (
            <div
              key={colour}
              style={{ width: 14, height: 14, borderRadius: 999, background: colour }}
            />
          ))}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 10,
            color: BRAND.text,
            fontSize: 34,
            fontWeight: 600,
            letterSpacing: '-0.02em',
          }}
        >
          CallFlow
          <span style={{ fontSize: 18, color: BRAND.textMute, letterSpacing: '0.4em' }}>AI</span>
        </div>
      </div>

      {/* Headline - the hero's, so a shared link and the page it opens agree. */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div
          style={{
            display: 'flex',
            color: BRAND.text,
            fontSize: 82,
            fontWeight: 600,
            lineHeight: 1.02,
            letterSpacing: '-0.03em',
            maxWidth: 900,
          }}
        >
          Dial the whole list. Hear only what needs you.
        </div>
        <div
          style={{
            display: 'flex',
            color: BRAND.textDim,
            fontSize: 30,
            lineHeight: 1.4,
            maxWidth: 860,
          }}
        >
          Clean calls close themselves. Only the ones that need a person reach one.
        </div>
      </div>

      {/* Lamp strip */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {STRIP.map((lamp, i) => (
            <div
              key={i}
              style={{
                width: 22,
                height: 22,
                borderRadius: 999,
                background: BRAND.lamp[lamp.state],
              }}
            />
          ))}
        </div>
        <div
          style={{
            display: 'flex',
            gap: 28,
            color: BRAND.textMute,
            fontSize: 22,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
          }}
        >
          {caption().map((part) => (
            <span key={part}>{part}</span>
          ))}
        </div>
      </div>
    </div>,
    size,
  );
}
