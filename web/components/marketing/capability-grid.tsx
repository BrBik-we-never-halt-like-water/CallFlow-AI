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
import { WaveCanvas } from "@/components/brand/wave-canvas";

/**
 * The six capabilities.
 *
 * Every line names something the operator controls or receives, never how the system is
 * built — "returns schema-validated data", not "calls a structured extraction endpoint".
 * One icon set, one stroke weight, and no colour: these are capabilities, not call
 * states, so they get none of the lamp palette.
 */
const CAPABILITIES: { icon: Icon; title: string; body: string; detail: string }[] = [
  {
    icon: SlidersIcon,
    title: "Goal-driven, not scripted",
    body: "Write an objective in plain English. The agent improvises and adapts when people go off-script.",
    detail: "No call trees, no branching scripts to maintain.",
  },
  {
    icon: TableIcon,
    title: "Typed results, not transcripts",
    body: "Every call returns schema-validated data — outcome, sentiment, and your own fields — ready for your systems.",
    detail: "You define the fields; they come back the same shape every time.",
  },
  {
    icon: UserSoundIcon,
    title: "Knows when to back off",
    body: "Frustration and opt-outs go to a person. Bad timing is queued for a polite retry instead.",
    detail: "A bad time isn't a bad mood — and the difference is in your data.",
  },
  {
    icon: ShieldCheckIcon,
    title: "Safe by default",
    body: "An allowlist and a per-run ceiling stop accidental calls, and every run is validated before it dials.",
    detail: "Every guard fails closed, and every guard is visible before you start.",
  },
  {
    icon: ClockIcon,
    title: "Runs while you sleep",
    body: "Campaigns work through evenings and weekends, inside the calling window you set.",
    detail: "Your team reads outcomes in the morning.",
  },
  {
    icon: PhoneCallIcon,
    title: "Real conversations",
    body: "Dialling, speech, turn-taking, voicemail, and IVR are handled end to end.",
    detail: "There's no telephony stack for you to maintain.",
  },
];

export function CapabilityGrid() {
  return (
    <section id="capabilities" className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          eyebrow="What you get"
          title="An operations layer, not a robocall dialler."
          sub="Six things that make the difference between a tool your team uses every day and one they abandon in a fortnight."
        />
      </Reveal>

      <RevealGroup className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CAPABILITIES.map(({ icon: IconComponent, title, body, detail }, i) => (
          <RevealItem key={title} className="flex">
            <div className="surface-flow group flex h-full flex-col overflow-hidden shadow-sm transition-[box-shadow,transform] duration-(--dur-base) ease-(--ease-out) hover:-translate-y-0.5 hover:shadow-md">
              {/* Waveform masthead: the voice is the card's structural header. */}
              <div className="relative flex h-14 shrink-0 items-center bg-surface-inverse px-5">
                <WaveCanvas
                  tone="inverse"
                  seed={i * 1.7}
                  pitch={7}
                  className="absolute inset-0 opacity-55"
                />
                <span className="relative flex size-8 items-center justify-center rounded-md bg-white/10 text-text-inverse">
                  <IconComponent aria-hidden weight="light" className="size-5" />
                </span>
              </div>

              <div className="flex flex-1 flex-col gap-3 p-5">
                <h3 className="text-h4 font-medium text-text">{title}</h3>
                <p className="text-small text-text-dim">{body}</p>

                <div className="seam-x mt-auto" />
                <p className="text-small text-text-mute">{detail}</p>
              </div>
            </div>
          </RevealItem>
        ))}
      </RevealGroup>
    </section>
  );
}
