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
    body: "An allowlist, a per-run ceiling, and a permanent suppression list stop accidental or unwanted calls.",
    detail: "Every guard fails closed, and every guard is visible before you start.",
  },
  {
    icon: ClockIcon,
    title: "Runs in the background",
    body: "Start a run and walk away — it keeps dialling while you do something else.",
    detail: "Come back to typed results, not a spinner.",
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
        {CAPABILITIES.map(({ icon: IconComponent, title, body, detail }) => (
          <RevealItem key={title} className="flex">
            <div className="surface-flow group flex h-full flex-col gap-3 p-5 shadow-sm transition-[box-shadow,transform] duration-(--dur-base) ease-(--ease-out) hover:-translate-y-0.5 hover:shadow-md">
              <span className="flex size-10 items-center justify-center rounded-lg bg-surface-sunken text-text-dim transition-colors duration-(--dur-base) group-hover:text-text">
                <IconComponent aria-hidden weight="light" className="size-5" />
              </span>

              <h3 className="text-h4 font-medium text-text">{title}</h3>
              <p className="text-small text-text-dim">{body}</p>

              <div className="seam-x mt-auto" />
              <p className="text-small text-text-mute">{detail}</p>
            </div>
          </RevealItem>
        ))}
      </RevealGroup>
    </section>
  );
}
