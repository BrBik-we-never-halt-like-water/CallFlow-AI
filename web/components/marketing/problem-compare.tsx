import { Eyebrow } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";
import { WaveCanvas } from "@/components/brand/wave-canvas";
import { Tag } from "@/components/ui/badge";
import { LiveLamp } from "./live-lamp";

/**
 * The problem, argued on the left and demonstrated on the right.
 *
 * The demonstration is two call-log rows. The "without" pair is deliberately
 * identical — same status, same duration, no way to tell them apart — and the
 * "with" pair is the same two calls carrying lamps. That contrast *is* the pitch,
 * so it gets room and no caption: explaining it would concede that it doesn't
 * land on its own.
 */

const ROWS = [
  { name: "Aditi Sharma", phone: "+91*******210", duration: "2m 41s" },
  { name: "Rahul Verma", phone: "+91*******884", duration: "2m 08s" },
];

export function ProblemCompare() {
  return (
    <section id="problem" className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <div className="grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,520px)] lg:gap-16">
        <Reveal className="flex flex-col gap-5">
          <h2 className="measure-display font-display text-h2 text-text">
            A completed call tells you nothing.
          </h2>
          <p className="measure text-body-l text-text-dim">
            In a normal call log, a delighted customer and a furious one look identical
            — both just say <span className="font-mono text-data">completed</span>. Your
            team burns hours dialling, repeating the same five questions, and typing
            notes into a CRM afterwards. You find out a call went badly when someone
            escalates, which is far too late.
          </p>
          <p className="measure text-body-l text-text">
            CallFlow turns every conversation into typed data the moment it ends, so the
            work that needs a person is visible immediately and the rest closes itself.
          </p>
        </Reveal>

        <Reveal delayMs={80} className="flex flex-col gap-6">
          <LogGroup label="A normal call log">
            {ROWS.map((row) => (
              <LogRow key={row.name} {...row} status="completed" />
            ))}
          </LogGroup>

          <LogGroup label="The same two calls, understood">
            <LogRow
              {...ROWS[0]}
              wave={0.6}
              outcome="interested"
              sentiment="positive"
              lamp={<LiveLamp state="jade" size="md" label="Auto-closed" />}
            />
            <LogRow
              {...ROWS[1]}
              wave={2.4}
              outcome="needs a person"
              sentiment="frustrated"
              lamp={<LiveLamp state="flare" size="md" label="Needs a person" />}
            />
          </LogGroup>
        </Reveal>
      </div>
    </section>
  );
}

function LogGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <Eyebrow>{label}</Eyebrow>
      <div className="surface-flow overflow-hidden shadow-sm transition-[box-shadow,transform] duration-(--dur-base) ease-(--ease-out) hover:-translate-y-0.5 hover:shadow-md">
        {children}
      </div>
    </div>
  );
}

function LogRow({
  name,
  phone,
  duration,
  status,
  lamp,
  wave,
  outcome,
  sentiment,
}: {
  name: string;
  phone: string;
  duration: string;
  status?: string;
  lamp?: React.ReactNode;
  /** Insight mode: show the call's own voice waveform (seed) and the typed
      fields extracted from it, rather than a bare number and duration. */
  wave?: number;
  outcome?: string;
  sentiment?: string;
}) {
  const insight = wave !== undefined;

  return (
    <div className="flex items-center gap-3 border-b border-rule px-3 py-3 last:border-0">
      <span className="flex size-2.5 shrink-0 items-center justify-center">{lamp}</span>
      <span className="w-24 shrink-0 truncate text-small text-text sm:w-28">{name}</span>

      {insight ? (
        <>
          {/* The call's voice, then the typed fields the system pulled from it. */}
          <span className="hidden min-w-0 flex-1 sm:block">
            <WaveCanvas seed={wave} pitch={6} className="h-6 text-text" />
          </span>
          <div className="flex shrink-0 items-center gap-1.5">
            <Tag mono={false}>{outcome}</Tag>
            <Tag mono={false}>{sentiment}</Tag>
          </div>
        </>
      ) : (
        <>
          <span className="hidden min-w-0 flex-1 font-mono text-data tabular-nums text-text-mute sm:inline">
            {phone}
          </span>
          <span className="font-mono text-data tabular-nums text-text-mute">{duration}</span>
          <span className="w-24 shrink-0 truncate text-right text-small text-text-mute">
            {status}
          </span>
        </>
      )}
    </div>
  );
}
