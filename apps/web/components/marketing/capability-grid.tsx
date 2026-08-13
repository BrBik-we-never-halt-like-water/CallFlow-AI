import type { ReactNode } from "react";
import type { Icon } from "@phosphor-icons/react";
import {
  ShieldCheckIcon,
  SlidersIcon,
  TableIcon,
  UserSoundIcon,
} from "@phosphor-icons/react/dist/ssr";
import { SectionHeading } from "@/components/ui/panel";
import { Reveal, RevealGroup, RevealItem } from "@/components/ui/reveal";
import { Tag } from "@/components/ui/badge";

/**
 * The four capabilities. Each names something the operator controls or receives,
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
      <span className="flex flex-col gap-1.5 font-mono text-data text-text-mute">
        <span>
          <span className="text-text-dim">goal:</span> confirm the appointment, and get a
          reason if they cannot make it
        </span>
        <span>
          <span className="text-text-dim">then:</span> offer the next two slots
        </span>
      </span>
    ),
  },
  {
    icon: TableIcon,
    title: "Typed results, not transcripts",
    body: "Every call returns schema-validated data — outcome, sentiment, and your own fields.",
    proof: (
      <span className="flex flex-col gap-1.5">
        <ProofField k="outcome" v={<Tag mono={false}>rebooked</Tag>} />
        <ProofField k="slot" v={<span className="text-data text-text">Tomorrow 15:00</span>} />
        <ProofField k="sentiment" v={<Tag mono={false}>positive</Tag>} />
      </span>
    ),
  },
  {
    icon: UserSoundIcon,
    title: "Knows when to back off",
    body: "Frustration and opt-outs reach a person; bad timing is queued for a polite retry.",
    proof: (
      <span className="flex flex-col gap-2 text-small text-text-mute">
        <ProofLamp color="var(--lamp-jade)" label="closed itself — no one reads it" />
        <ProofLamp color="var(--lamp-brass)" label="bad timing — queued for a retry" />
        <ProofLamp color="var(--lamp-flare)" label="asked for a person — escalated" />
      </span>
    ),
  },
  {
    icon: ShieldCheckIcon,
    title: "Safe by default",
    body: "An allowlist and a per-run ceiling stop accidental calls. Every run validates first.",
    proof: (
      <span className="flex flex-col gap-2">
        <span className="flex flex-wrap gap-1.5">
          <Tag>ALLOWLIST</Tag>
          <Tag>CEILING 25</Tag>
          <Tag>2 / HOUR</Tag>
        </span>
        <span className="text-small text-text-mute">
          Every guard fails closed — if a check cannot complete, the dial does not happen.
        </span>
      </span>
    ),
  },
];
// Still four, and it stays four. Two were cut and must not come back as filler:
// "Runs while you sleep" asserted that calls are held inside a calling window,
// which nothing enforces (ISSUES.md D1, CLAUDE.md §4 #8), and "Real
// conversations" claimed table stakes every competitor also has.
//
// When this section needed to fill a screen, the fix was a 2-up grid of taller
// cards with more of the real artefact in each — not six cards. A card that
// exists to occupy space says something untrue or something obvious, and both
// are worse than the space.

function ProofLamp({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="size-2 shrink-0 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

/** One `key    value` line, laid out the way the product's own result table is. */
function ProofField({ k, v }: { k: string; v: ReactNode }) {
  return (
    <span className="flex items-center justify-between gap-3">
      <span className="font-mono text-data text-text-mute">{k}</span>
      {v}
    </span>
  );
}

export function CapabilityGrid() {
  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          title="An operations layer, not a robocall dialler."
          sub="The difference between a tool your team keeps and one they abandon in a fortnight."
        />
      </Reveal>

      <RevealGroup className="mt-10 grid gap-5 sm:grid-cols-2">
        {CAPABILITIES.map(({ icon: IconComponent, title, body, proof }) => (
          <RevealItem key={title} className="flex">
            <div className="card-raised card-interactive group flex h-full flex-col gap-4 p-6 sm:p-7">
              <span className="flex size-11 items-center justify-center rounded-lg bg-surface-sunken text-text-dim transition-colors duration-(--dur-base) group-hover:text-text">
                <IconComponent aria-hidden weight="light" className="size-6" />
              </span>

              <h3 className="text-h3 font-medium text-text">{title}</h3>
              <p className="text-body text-text-dim">{body}</p>

              {/* The proof sits in a well rather than under a hairline: at this
                  card size a single rule read as a stray line, and the fragment
                  is the point of the card — it should look like a piece of the
                  product, not a footnote. */}
              <span className="mt-auto flex min-h-16 flex-col justify-center rounded-md bg-surface-sunken/70 px-4 py-3">
                {proof}
              </span>
            </div>
          </RevealItem>
        ))}
      </RevealGroup>
    </section>
  );
}
