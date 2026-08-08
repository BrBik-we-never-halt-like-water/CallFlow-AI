"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { formatDuration } from "@/lib/format";

/**
 * A finished call as a timeline you can hold.
 *
 * Time is the natural axis of a phone call, so it becomes the control: drag the
 * playhead and the waveform fills, the transcript greys ahead of you, and each
 * extracted field appears at the point in the conversation it was determined.
 *
 * The point is not decoration — it answers "where did this field come from?",
 * which is the question a reviewer actually has when a run returns something
 * surprising. Every field gets a moment rather than appearing as a finished
 * block at the end.
 *
 * Turn timings are derived, not measured: the API returns a transcript and a
 * duration but no per-turn timestamps, so turns are distributed across the
 * duration by their length. That is stated in the UI rather than implied to be
 * exact.
 */

export interface ScrubTurn {
  speaker: "agent" | "contact";
  text: string;
}

const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

export function CallScrubber({
  turns,
  durationSeconds,
  fields,
  className,
}: {
  turns: ScrubTurn[];
  durationSeconds: number | null;
  /** Extracted fields, revealed in order across the call. */
  fields: { key: string; value: string }[];
  className?: string;
}) {
  const [p, setP] = useState(1);

  // Distribute turns across the call by their length — a long turn takes longer
  // to say than a short one, which is closer to true than an even split.
  const marks = useMemo(() => {
    const lens = turns.map((t) => Math.max(8, t.text.length));
    const total = lens.reduce((a, b) => a + b, 0) || 1;
    // Prefix sums built without a running accumulator — quadratic, but a call
    // has tens of turns, not thousands, and it keeps the memo free of mutation.
    return lens.map((l, i) => {
      const before = lens.slice(0, i).reduce((a, b) => a + b, 0);
      return { start: before / total, end: (before + l) / total };
    });
  }, [turns]);

  const bars = useMemo(() => {
    const seed = turns.map((t) => t.text).join("").slice(0, 400) || "callflow";
    return Array.from({ length: 72 }, (_, i) => {
      const c = seed.charCodeAt(i % seed.length) || 70;
      const env = Math.sin((i / 72) * Math.PI);
      return 12 + ((c * (i + 5)) % 74) * env;
    });
  }, [turns]);

  const spokenTurns = marks.filter((m) => m.start < p).length;
  const shownFields = fields.filter((_, i) => p >= (i + 1) / (fields.length + 1));
  const elapsed = durationSeconds != null ? Math.round(durationSeconds * p) : null;

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="flex items-end justify-between gap-3">
        <p className="eyebrow text-text-mute">Scrub the call</p>
        <p className="font-mono text-data text-text-mute">
          {elapsed != null ? formatDuration(elapsed) : "—"}
          {durationSeconds != null ? ` / ${formatDuration(durationSeconds)}` : null}
        </p>
      </div>

      <div aria-hidden className="flex h-12 items-center gap-px">
        {bars.map((height, i) => {
          const at = i / bars.length;
          const head = Math.abs(at - p) < 1 / bars.length;
          return (
            <i
              key={i}
              className={cn(
                "min-h-[3px] flex-1 rounded-[1px] transition-colors duration-100",
                head ? "bg-lamp-brass" : at < p ? "bg-text-dim" : "bg-rule",
              )}
              style={{ height: `${height}%` }}
            />
          );
        })}
      </div>

      <label className="sr-only" htmlFor="call-playhead">
        Call playhead
      </label>
      <input
        id="call-playhead"
        type="range"
        min={0}
        max={1000}
        value={Math.round(p * 1000)}
        onChange={(e) => setP(clamp(Number(e.target.value) / 1000, 0, 1))}
        className="h-1 w-full cursor-pointer appearance-none rounded-full bg-rule accent-[var(--primary)]"
      />

      <div className="mt-1 grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        <div className="flex flex-col gap-2">
          {turns.map((t, i) => (
            <p
              key={i}
              className={cn(
                "text-small transition-opacity duration-200",
                i < spokenTurns ? "opacity-100" : "opacity-35",
              )}
            >
              <span className="eyebrow mr-2 text-text-mute">
                {t.speaker === "agent" ? "CallFlow" : "Contact"}
              </span>
              {t.text}
            </p>
          ))}
        </div>

        <div className="flex flex-col">
          {fields.map((f, i) => {
            const on = shownFields.length > i;
            return (
              <div
                key={f.key}
                className={cn(
                  "flex items-center justify-between gap-3 border-b border-rule py-2 last:border-0",
                  "transition-opacity duration-200",
                  on ? "opacity-100" : "opacity-30",
                )}
              >
                <span className="font-mono text-data text-text-mute">{f.key}</span>
                <span className="text-small font-medium">{on ? f.value : "—"}</span>
              </div>
            );
          })}
          <p className="pt-3 text-data text-text-mute">
            Turn timings are estimated from turn length — the call record has no
            per-turn timestamps.
          </p>
        </div>
      </div>
    </div>
  );
}
