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

/**
 * The six capabilities — one line each. Every line names something the operator
 * controls or receives, never how the system is built. One icon set, one stroke
 * weight, no colour: these are capabilities, not call states.
 */
const CAPABILITIES: { icon: Icon; title: string; body: string }[] = [
  {
    icon: SlidersIcon,
    title: "Goal-driven, not scripted",
    body: "Write the objective in plain English. The agent adapts when people go off-script.",
  },
  {
    icon: TableIcon,
    title: "Typed results, not transcripts",
    body: "Every call returns schema-validated data — outcome, sentiment, and your own fields.",
  },
  {
    icon: UserSoundIcon,
    title: "Knows when to back off",
    body: "Frustration and opt-outs reach a person; bad timing is queued for a polite retry.",
  },
  {
    icon: ShieldCheckIcon,
    title: "Safe by default",
    body: "An allowlist and a per-run ceiling stop accidental calls. Every run validates first.",
  },
  {
    icon: ClockIcon,
    title: "Runs while you sleep",
    body: "Campaigns work evenings and weekends, inside the window you set.",
  },
  {
    icon: PhoneCallIcon,
    title: "Real conversations",
    body: "Dialling, speech, turn-taking, voicemail, and IVR — handled end to end.",
  },
];

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
        {CAPABILITIES.map(({ icon: IconComponent, title, body }) => (
          <RevealItem key={title} className="flex">
            <div className="surface-flow group flex h-full flex-col gap-3 p-5 shadow-sm transition-[box-shadow,transform] duration-(--dur-base) ease-(--ease-out) hover:-translate-y-0.5 hover:shadow-md">
              <span className="flex size-10 items-center justify-center rounded-lg bg-surface-sunken text-text-dim transition-colors duration-(--dur-base) group-hover:text-text">
                <IconComponent aria-hidden weight="light" className="size-5" />
              </span>

              <h3 className="text-h4 font-medium text-text">{title}</h3>
              <p className="text-small text-text-dim">{body}</p>
            </div>
          </RevealItem>
        ))}
      </RevealGroup>
    </section>
  );
}
