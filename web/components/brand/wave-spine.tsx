import { cn } from "@/lib/cn";

const SPINE_BARS = 72;

/**
 * Precomputed once at module load — deterministic, no Date/random. The envelope
 * makes the centre loudest and brightest, tapering to silence at the ends, and
 * the staggered delay makes the pulse travel across like a live voice.
 */
const BARS = Array.from({ length: SPINE_BARS }, (_, i) => {
  const x = i / (SPINE_BARS - 1);
  const env = Math.sin(Math.PI * x);
  return {
    height: 0.14 + env * env * 0.86,
    opacity: 0.12 + env * 0.5,
    delay: i * 38,
  };
});

/**
 * The voice-flow spine: a waveform that threads between sections so the whole
 * page reads as one continuous conversation. Tallest and brightest in the
 * centre, with a travelling pulse. Decorative (`aria-hidden`); rests as a static
 * waveform under prefers-reduced-motion.
 */
export function WaveSpine({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("flex h-7 w-full items-center gap-[3px] overflow-hidden", className)}
    >
      {BARS.map((b, i) => (
        <span
          key={i}
          className="spine-bar min-w-0 flex-1 rounded-full bg-text"
          style={{
            height: `${b.height * 100}%`,
            opacity: b.opacity,
            animationDelay: `${b.delay}ms`,
          }}
        />
      ))}
    </div>
  );
}
