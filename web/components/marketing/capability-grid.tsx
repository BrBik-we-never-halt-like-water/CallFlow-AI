import type { ReactNode } from "react";
import type { Icon } from "@phosphor-icons/react";
import {
  ClockIcon,
  PhoneCallIcon,
  ShieldCheckIcon,
  SlidersIcon,
  TableIcon,
  UserSoundIcon,
} from "@phosphor-icons/react/dist/ssr";
import { SectionHeading } from "@/components/ui/panel";
import { Reveal, RevealGroup, RevealItem } from "@/components/ui/reveal";
import { Tag } from "@/components/ui/badge";
import { WaveCanvas } from "@/components/brand/wave-canvas";

/**
 * The six capabilities. Each names something the operator controls or receives,
 * never how the system is built — and carries a small proof: a scrap of the real
 * product (a waveform, typed fields, the escalation lamps, the guards) so the
 * card shows what you get, not just claims it. The proofs are muted and static;
 * the lamp colours are the one meaningful use of colour here — they are call
 * states.
 */
const CAPABILITIES: { icon: Icon; title: string; body: string; proof: ReactNode }[] = [
  {
    icon: SlidersIcon,
    title: "Goal-driven, not scripted",
    body: "Write the objective in plain English. The agent adapts when people go off-script.",
    proof: (
      <span className="font-mono text-data text-text-mute">goal: confirm the appointment</span>
    ),
  },
  {
    icon: TableIcon,
    title: "Typed results, not transcripts",
    body: "Every call returns schema-validated data — outcome, sentiment, and your own fields.",
    proof: (
      <span className="flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-data text-text-mute">outcome</span>
        <Tag mono={false}>interested</Tag>
      </span>
    ),
  },
  {
    icon: UserSoundIcon,
    title: "Knows when to back off",
    body: "Frustration and opt-outs reach a person; bad timing is queued for a polite retry.",
    proof: (
      <span className="flex flex-wrap items-center gap-4 text-small text-text-mute">
        <ProofLamp color="var(--lamp-jade)" label="auto-closed" />
        <ProofLamp color="var(--lamp-flare)" label="needs a person" />
      </span>
    ),
  },
  {
    icon: ShieldCheckIcon,
    title: "Safe by default",
    body: "An allowlist and a per-run ceiling stop accidental calls. Every run validates first.",
    proof: (
      <span className="flex flex-wrap gap-1.5">
        <Tag>ALLOWLIST</Tag>
        <Tag>CEILING 25</Tag>
      </span>
    ),
  },
  {
    icon: ClockIcon,
    title: "Runs while you sleep",
    body: "Campaigns work evenings and weekends, inside the window you set.",
    proof: <span className="font-mono text-data text-text-mute">window · 09:00–20:00</span>,
  },
  {
    icon: PhoneCallIcon,
    title: "Real conversations",
    body: "Dialling, speech, turn-taking, voicemail, and IVR — handled end to end.",
    proof: (
      <span className="block h-6 w-full opacity-70">
        <WaveCanvas pitch={5} />
      </span>
    ),
  },
];

function ProofLamp({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="size-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

export function CapabilityGrid() {
  return (
    <section id="capabilities" className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          eyebrow="What you get"
          title="An operations layer, not a robocall dialler."
          sub="The difference between a tool your team keeps and one they abandon in a fortnight."
        />
      </Reveal>

      <RevealGroup className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CAPABILITIES.map(({ icon: IconComponent, title, body, proof }) => (
          <RevealItem key={title} className="flex">
            <div className="surface-flow group flex h-full flex-col gap-3 p-5 shadow-sm transition-[box-shadow,transform] duration-(--dur-base) ease-(--ease-out) hover:-translate-y-0.5 hover:shadow-md">
              <span className="flex size-10 items-center justify-center rounded-lg bg-surface-sunken text-text-dim transition-colors duration-(--dur-base) group-hover:text-text">
                <IconComponent aria-hidden weight="light" className="size-5" />
              </span>

              <h3 className="text-h4 font-medium text-text">{title}</h3>
              <p className="text-small text-text-dim">{body}</p>

              <span className="mt-auto flex min-h-6 items-center border-t border-rule/60 pt-3">
                {proof}
              </span>
            </div>
          </RevealItem>
        ))}
      </RevealGroup>
    </section>
  );
}
