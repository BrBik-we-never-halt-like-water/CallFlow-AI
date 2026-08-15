import { cn } from '@/lib/cn';

const BARS = 5;

/** The same pulsing-bar waveform as the first-paint `SiteLoader`, sized down
 * for inline use - a brief, genuinely-in-progress wait (switching to a
 * conversation that's still fetching) reads better as motion than as a
 * static `Skeleton` block, which is built to mean "nothing back yet" rather
 * than "under a second away". */
export function WavesLoader({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex h-5 items-center gap-[3px]', className)} aria-hidden>
      {Array.from({ length: BARS }).map((_, i) => (
        <span
          key={i}
          className="loader-bar h-full w-[3px] rounded-full bg-text-mute"
          style={{ animationDelay: `${i * 70}ms` }}
        />
      ))}
    </span>
  );
}
