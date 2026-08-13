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
      <span className="flex flex-col gap-1.5">
        <span className="flex flex-wrap gap-1.5">
          <Tag>ALLOWLIST</Tag>
          <Tag>CEILING 25</Tag>
          <Tag>2 / HOUR</Tag>
        </span>
        <span className="text-small text-text-mute">
          Fails closed — if a check cannot complete, the dial does not happen.
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

      {/* Sized so the whole section clears a 900px-tall viewport — a maximised
          browser with chrome is ~950px, not the 1080 a headless check defaults
          to, and at the previous card size this section overflowed by 68px
          there and spilled into the next one. Padding and type do the fitting;
          nothing was cut from what the cards say. */}
      {/* Four identical cards, and "identical" is doing real work here.
          `h-full` alone only equalises the card's *outer* box — the row inside
          each one still started wherever its own copy happened to end, so the
          four proof wells sat at four different heights and the grid read as
          four unrelated tiles. Every row is pinned instead:

            header  icon + title on one line   — fixed by the icon's own size
            body    min-h, two lines of copy   — the longest body sets it
            proof   h-26, a fixed well          — so all four wells align exactly

          The icon moved inline with the title rather than sitting above it,
          which is what buys back the height the fixed well costs, and gives the
          card a flatter, more deliberate shape than the stacked version.

          Sized so the whole section still clears a 900px-tall viewport — a
          maximised browser with chrome is ~950px, not the 1080 a headless check
          defaults to. */}
      <RevealGroup className="mt-(--deck-gap) grid gap-4 sm:grid-cols-2">
        {CAPABILITIES.map(({ icon: IconComponent, title, body, proof }) => (
          <RevealItem key={title} className="flex">
            {/* `w-full` is load-bearing, not defensive. `RevealItem` is a flex
                container, so without an explicit width this card shrinks to its
                own content instead of filling its grid column — which is why the
                four had ragged right edges (606/559/518/514px) and read as four
                different shapes. `h-full` was already here and only ever fixed
                the other axis. */}
            <div className="card-raised card-interactive group flex h-full w-full flex-col gap-3 p-5 sm:p-6">
              <div className="flex items-center gap-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-surface-sunken text-text-dim transition-colors duration-(--dur-base) group-hover:text-text">
                  <IconComponent aria-hidden weight="light" className="size-5" />
                </span>
                <h3 className="text-h4 font-medium text-text">{title}</h3>
              </div>

              <p className="min-h-[2.625rem] text-small text-text-dim">{body}</p>

              {/* The proof sits in a well rather than under a hairline: at this
                  card size a single rule read as a stray line, and the fragment
                  is the point of the card — it should look like a piece of the
                  product, not a footnote. Fixed height, not `min-h`: a taller
                  proof in one card is exactly what knocked the four out of
                  alignment before. */}
              <span className="mt-auto flex h-26 flex-col justify-center rounded-md bg-surface-sunken/70 px-3.5 py-2.5">
                {proof}
              </span>
            </div>
          </RevealItem>
        ))}
      </RevealGroup>
    </section>
  );
}
