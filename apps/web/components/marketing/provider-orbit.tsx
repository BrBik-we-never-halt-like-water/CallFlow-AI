"use client";

import Image from "next/image";
import { useRef } from "react";
import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion";
import { SectionHeading } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";
import { BRAND_LOGOS } from "@/lib/brand-logos";

/**
 * The provider wall: your carrier, your keys.
 *
 * Every mark here is a provider the product can actually drive today - the
 * carriers a run dials from and the STT/TTS/LLM legs an agent is built on.
 * The storage/automation providers whose keys merely save ("not in use yet"
 * on the Integrations page) are deliberately absent: a logo on a marketing
 * page is a claim.
 *
 * Three rows drift at slightly different rates as the page scrolls - depth
 * from parallax, not decoration; still under reduced motion. Logos are the
 * real self-hosted assets (`public/brands/`, DESIGN_NOTES §23): full colour,
 * on plates, `object-contain` so app-icon marks and transparent marks read
 * the same.
 */

const NAMES: Record<string, string> = {
  twilio: "Twilio",
  plivo: "Plivo",
  telnyx: "Telnyx",
  vonage: "Vonage",
  deepgram: "Deepgram",
  assemblyai: "AssemblyAI",
  speechmatics: "Speechmatics",
  gladia: "Gladia",
  soniox: "Soniox",
  sarvam: "Sarvam",
  google: "Google",
  elevenlabs: "ElevenLabs",
  cartesia: "Cartesia",
  murf: "Murf",
  resemble: "Resemble",
  speechify: "Speechify",
  rime: "Rime",
  openai: "OpenAI",
  anthropic: "Anthropic",
  mistral: "Mistral",
  groq: "Groq",
  cerebras: "Cerebras",
  deepseek: "DeepSeek",
  openrouter: "OpenRouter",
  xai: "xAI",
  perplexity: "Perplexity",
  together: "Together AI",
  fireworks: "Fireworks",
  azure_openai: "Azure OpenAI",
  aws_bedrock: "AWS Bedrock",
};

/** Three drift rows: carriers lead, then ears-and-voices, then minds. */
const ROWS: string[][] = [
  ["twilio", "plivo", "telnyx", "vonage", "deepgram", "assemblyai", "speechmatics", "gladia", "soniox", "google"],
  ["elevenlabs", "cartesia", "sarvam", "murf", "resemble", "speechify", "rime", "openai", "anthropic", "mistral"],
  ["groq", "cerebras", "deepseek", "openrouter", "xai", "perplexity", "together", "fireworks", "azure_openai", "aws_bedrock"],
];

const FACTS = [
  { figure: "4", label: "carriers to dial from" },
  { figure: "10", label: "transcribers" },
  { figure: "11", label: "voice providers" },
  { figure: "40+", label: "models, via OpenRouter" },
] as const;

export function ProviderOrbit() {
  const reduced = !!useReducedMotion();
  const sectionRef = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start end", "end start"],
  });

  // Each row drifts a different way and a different amount - the nearest row
  // (visually the middle, drawn largest) moves the most, which is what makes
  // the drift read as depth rather than as a marquee.
  const x0 = useTransform(scrollYProgress, [0, 1], [24, -24]);
  const x1 = useTransform(scrollYProgress, [0, 1], [-44, 44]);
  const x2 = useTransform(scrollYProgress, [0, 1], [16, -16]);
  const drifts = [x0, x1, x2];

  return (
    <section ref={sectionRef} className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          eyebrow="Providers"
          title="Your carrier. Your keys. Your models."
          sub="Connect Twilio, Plivo, Telnyx or Vonage and dial from your own numbers — outbound only, never touching what already answers them. Bring your own keys for every leg of the pipeline."
        />
      </Reveal>

      <div className="mt-(--deck-gap) flex flex-col gap-4 sm:gap-5">
        {ROWS.map((row, i) => (
          <Reveal key={i} delayMs={i * 80}>
            <motion.ul
              style={reduced ? undefined : { x: drifts[i] }}
              className={
                i === 1
                  ? "flex flex-wrap items-center justify-center gap-3 sm:gap-4"
                  : "flex flex-wrap items-center justify-center gap-3 opacity-80 sm:gap-4"
              }
            >
              {row.map((key) => {
                const file = BRAND_LOGOS[key];
                if (!file) return null;
                return (
                  <li
                    key={key}
                    className={
                      "flex items-center gap-2.5 rounded-lg border border-rule bg-surface-raised py-1.5 pl-1.5 pr-3 shadow-xs " +
                      (i === 1 ? "scale-[1.06]" : "")
                    }
                  >
                    <span className="size-7 shrink-0 overflow-hidden rounded-md">
                      <Image
                        src={`/brands/${file}`}
                        alt=""
                        width={28}
                        height={28}
                        unoptimized
                        className="size-full object-contain"
                      />
                    </span>
                    <span className="whitespace-nowrap text-small text-text-dim">
                      {NAMES[key] ?? key}
                    </span>
                  </li>
                );
              })}
            </motion.ul>
          </Reveal>
        ))}
      </div>

      <Reveal delayMs={200}>
        <dl className="mx-auto mt-(--deck-gap) grid max-w-3xl grid-cols-2 gap-6 border-t border-rule pt-8 sm:grid-cols-4">
          {FACTS.map((fact) => (
            <div key={fact.label} className="flex flex-col items-center gap-1 text-center">
              <dd className="font-mono text-h3 font-medium tabular-nums text-text">
                {fact.figure}
              </dd>
              <dt className="text-small text-text-dim">{fact.label}</dt>
            </div>
          ))}
        </dl>
        <p className="mx-auto mt-6 max-w-2xl text-center text-small text-text-mute">
          Keys are verified against the vendor before they&apos;re stored, and encrypted
          at rest. No keys yet? Platform keys get your first runs out.
        </p>
      </Reveal>
    </section>
  );
}
