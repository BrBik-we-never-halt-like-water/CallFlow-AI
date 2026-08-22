/**
 * Fetch each provider's own logo once, into `public/brands/`.
 *
 * Run with `node scripts/fetch-brand-logos.mjs`. Committed rather than fetched
 * at runtime: a favicon request per card would tell a third party which vendors
 * an organisation is shopping for, and would leave the grid blank offline.
 *
 * Every candidate is downloaded and the *largest* one wins, rather than the
 * first that answers. Order-of-preference alone picks wrong often enough to
 * matter here - several vendors serve a 32px `apple-touch-icon` beside a
 * multi-resolution `favicon.ico` carrying a 256px frame, and at this grid's
 * density a soft mark is the thing you notice.
 *
 * `DOMAINS` is the brand domain, not the console subdomain in `docs_url`:
 * `platform.openai.com` and `openai.com` serve the same mark, and the apex is
 * the one that stays put.
 */
import { readdir, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';

/** 128px covers the 36px plate at 3x. Anything larger is bytes nobody sees -
 *  one vendor serves its mark at 3972px. */
const TARGET = 128;

const DOMAINS = {
  openrouter: 'openrouter.ai', openai: 'openai.com', anthropic: 'anthropic.com',
  google: 'ai.google.dev', groq: 'groq.com', xai: 'x.ai', mistral: 'mistral.ai',
  cerebras: 'cerebras.ai', fireworks: 'fireworks.ai', together: 'together.ai',
  deepseek: 'deepseek.com', perplexity: 'perplexity.ai',
  azure_openai: 'azure.microsoft.com', aws_bedrock: 'aws.amazon.com', minimax: 'minimax.io',
  deepgram: 'deepgram.com', assemblyai: 'assemblyai.com', gladia: 'gladia.io',
  speechmatics: 'speechmatics.com', soniox: 'soniox.com', sarvam: 'sarvam.ai',
  azure_speech: 'azure.microsoft.com', clova: 'ncloud.com', gnani: 'gnani.ai',
  rtzr: 'rtzr.ai', spitch: 'spi-tch.com', baseten: 'baseten.co', fal: 'fal.ai',
  elevenlabs: 'elevenlabs.io', cartesia: 'cartesia.ai', playai: 'play.ht',
  lmnt: 'lmnt.com', rime: 'rime.ai', hume: 'hume.ai', inworld: 'inworld.ai',
  neuphonic: 'neuphonic.com', resemble: 'resemble.ai', speechify: 'speechify.com',
  murf: 'murf.ai', smallestai: 'smallest.ai', fishaudio: 'fish.audio',
  upliftai: 'upliftai.org', twilio: 'twilio.com', plivo: 'plivo.com',
  telnyx: 'telnyx.com', vonage: 'vonage.com', aws_s3: 'aws.amazon.com',
  gcp_storage: 'cloud.google.com', cloudflare_r2: 'cloudflare.com',
  make: 'make.com', n8n: 'n8n.io', zapier: 'zapier.com',
  gohighlevel: 'gohighlevel.com', slack: 'slack.com', hubspot: 'hubspot.com',
  salesforce: 'salesforce.com', langfuse: 'langfuse.com',
};

const UA = { 'user-agent': 'Mozilla/5.0 (compatible; CallFlowBrandFetch/1)' };

/**
 * Vendors whose vector is unusable inside a plate, so the raster wins instead.
 *
 * `BrandMark` renders these through `<img>`, which is what makes an otherwise
 * fine SVG fail here. Two failure modes, both checked by eye:
 *
 * - **Theme-reactive fill.** An SVG carrying its own
 *   `@media (prefers-color-scheme: dark)` resolves that against the *viewer's OS*,
 *   not against the plate it sits on - so on a light plate under a dark OS the
 *   mark fills white and vanishes. `looksTheme()` catches these automatically;
 *   the list below is only for ones it cannot see.
 * - **Near-transparent line art.** A white-on-transparent export designed for a
 *   dark browser tab is invisible on anything else.
 *
 * Monochrome alone is *not* a reason - ElevenLabs and Perplexity are both
 * monochrome vectors and both read correctly, so this stays a short list of
 * confirmed problems rather than a heuristic that swaps out good marks.
 */
const PREFER_RASTER = new Set([
  // A 341px Inkscape export of white line art: a faint outline on any plate.
  'lmnt',
]);

/** An SVG that recolours itself from the OS theme. See `PREFER_RASTER`. */
function looksTheme(bytes) {
  return new TextDecoder().decode(bytes.subarray(0, 2048)).includes(
    'prefers-color-scheme',
  );
}

/** Longest edge in pixels, or Infinity for a vector. 0 = not an image we want. */
function measure(bytes, type) {
  if (type.includes('svg')) return Infinity;
  if (bytes[0] === 0x89 && bytes[1] === 0x50) {
    const view = new DataView(bytes.buffer, bytes.byteOffset);
    return Math.max(view.getUint32(16), view.getUint32(20));
  }
  // ICO: a directory of frames, each 16 bytes; a 0 dimension byte means 256.
  if (bytes[0] === 0 && bytes[1] === 0 && bytes[2] === 1) {
    const count = bytes[4] | (bytes[5] << 8);
    let best = 0;
    for (let i = 0; i < count; i++) {
      const at = 6 + i * 16;
      best = Math.max(best, bytes[at] || 256, bytes[at + 1] || 256);
    }
    return best;
  }
  return 0;
}

async function candidate(url) {
  try {
    const res = await fetch(url, { headers: UA, redirect: 'follow', signal: AbortSignal.timeout(15000) });
    if (!res.ok) return null;
    const type = res.headers.get('content-type') ?? '';
    const bytes = new Uint8Array(await res.arrayBuffer());
    if (bytes.byteLength < 200) return null;
    const size = measure(bytes, type);
    if (!size) return null;
    const ext = type.includes('svg') ? 'svg' : bytes[0] === 0x89 ? 'png' : 'ico';
    return { bytes, size, ext, theme: ext === 'svg' && looksTheme(bytes) };
  } catch { return null; }
}

/**
 * Down to a `TARGET`-square PNG. Vectors pass through untouched.
 *
 * `sharp` arrives with Next rather than being declared here, so a missing one
 * skips the resize instead of failing the fetch - a 512px logo is oversized,
 * not broken.
 */
async function normalise(found) {
  if (found.ext === 'svg' || found.size <= TARGET) return found;
  let sharp;
  try {
    sharp = createRequire(import.meta.url)('sharp');
  } catch {
    return found;
  }
  try {
    const bytes = new Uint8Array(
      await sharp(found.bytes)
        .resize(TARGET, TARGET, { fit: 'inside', withoutEnlargement: true })
        .png({ compressionLevel: 9 })
        .toBuffer(),
    );
    return { bytes, size: TARGET, ext: 'png' };
  } catch {
    return found;
  }
}

/**
 * The largest frame of an ICO, when it is stored as a PNG - which is how every
 * modern encoder writes anything above 48px. Unwrapping it hands `normalise` an
 * image `sharp` can actually read (libvips has no ICO reader) and drops the
 * container: one vendor's `favicon.ico` is 209 kB of frames for a 20px mark.
 */
function unwrapIco(found) {
  if (found.ext !== 'ico') return found;
  const b = found.bytes;
  const count = b[4] | (b[5] << 8);
  let best = null;
  for (let i = 0; i < count; i++) {
    const at = 6 + i * 16;
    const size = Math.max(b[at] || 256, b[at + 1] || 256);
    const length = new DataView(b.buffer, b.byteOffset).getUint32(at + 8, true);
    const offset = new DataView(b.buffer, b.byteOffset).getUint32(at + 12, true);
    const frame = b.subarray(offset, offset + length);
    if (frame[0] !== 0x89 || frame[1] !== 0x50) continue;
    if (!best || size > best.size) best = { bytes: frame, size, ext: 'png' };
  }
  return best ?? found;
}

const report = [];
for (const [id, domain] of Object.entries(DOMAINS)) {
  const urls = [
    `https://${domain}/favicon.svg`,
    `https://${domain}/icon.svg`,
    `https://${domain}/apple-touch-icon.png`,
    `https://${domain}/apple-touch-icon-precomposed.png`,
    `https://${domain}/favicon.ico`,
    `https://www.google.com/s2/favicons?sz=256&domain=${domain}`,
    `https://icons.duckduckgo.com/ip3/${domain}.ico`,
  ];
  let found = (await Promise.all(urls.map(candidate))).filter(Boolean);

  // Drop the vector where it is the thing that breaks, but only if a raster
  // actually answered - a bad mark still beats an empty plate.
  if (found.some((c) => c.ext !== 'svg')) {
    found = found.filter(
      (c) => c.ext !== 'svg' || !(c.theme || PREFER_RASTER.has(id)),
    );
  }
  // An ICO whose frames are BMP rather than PNG survives `unwrapIco` intact,
  // and neither sharp nor libvips can shrink it - one vendor's is 205 kB for a
  // 20px mark. Where a plain raster of usable size also answered, take that
  // instead: a little less resolution, an order of magnitude fewer bytes.
  const usable = found.some((c) => c.ext !== 'ico' && c.size >= 64)
    ? found.filter((c) => c.ext !== 'ico' || unwrapIco(c).ext === 'png')
    : found;
  const largest = usable.sort((a, b) => b.size - a.size)[0];
  if (!largest) {
    report.push(`MISS         ${id.padEnd(14)} ${domain}`);
    continue;
  }
  const best = await normalise(unwrapIco(largest));
  await writeFile(`public/brands/${id}.${best.ext}`, best.bytes);
  report.push(
    `${best.ext.padEnd(4)} ${(best.size === Infinity ? 'vector' : `${best.size}px`).padStart(7)} ` +
      `${String(Math.round(best.bytes.byteLength / 1024)).padStart(4)}kB  ${id.padEnd(14)} ${domain}`,
  );
}
// The extension varies by what each vendor serves, so `BrandMark` cannot guess
// the filename. Written from the directory rather than from this run's results,
// so the manifest stays correct whether every provider was re-fetched or one was.
const onDisk = (await readdir('public/brands'))
  .map((f) => [f.slice(0, f.lastIndexOf('.')), f.slice(f.lastIndexOf('.') + 1)])
  .filter(([id]) => id in DOMAINS)
  .sort(([a], [b]) => (a < b ? -1 : 1));

const entries = onDisk.map(([id, ext]) => `  ${id}: '${id}.${ext}',`).join('\n');

await writeFile(
  'lib/brand-logos.ts',
  `/**
 * Which file in \`public/brands/\` holds each provider's logo.
 *
 * Generated by \`scripts/fetch-brand-logos.mjs\` - do not hand-edit.
 *
 * The extension differs per vendor, because it is whatever each one serves its
 * mark at the best resolution: a vector where there is one, a raster where there
 * is not. So the filename cannot be derived from a provider id, and a provider
 * with no entry here is what makes \`BrandMark\` fall back to a monogram.
 */
export const BRAND_LOGOS: Record<string, string> = {
${entries}
};
`,
);

console.log(report.join('\n'));
console.log(`\n${report.filter((r) => !r.startsWith('MISS')).length}/${report.length} fetched`);
console.log(`lib/brand-logos.ts: ${onDisk.length} entries`);
