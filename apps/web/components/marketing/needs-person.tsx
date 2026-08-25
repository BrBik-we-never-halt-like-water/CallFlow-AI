import { Lamp } from "@/components/brand/lamp";
import { SectionHeading } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";
import { Stage, StageLayer } from "@/components/marketing/stage";

/**
 * The escalation queue: where the calls that need a person actually land.
 *
 * Everything this section claims is wired: escalations are persisted rows
 * raised at triage time (a required field the call couldn't collect, or a
 * contact it couldn't reach), the queue syncs live across the team via
 * realtime, rows are assignable and resolvable, and a teammate can ask to
 * take one. The rows below are a still of that surface - illustration, not
 * controls, which is why nothing here is a button.
 */

const QUEUE: {
  name: string;
  lampLabel: string;
  reason: string;
  owner: string | null;
}[] = [
  {
    name: "Meera Nair",
    lampLabel: "Needs a person",
    reason: "The call ended without decision — a person needs to ask.",
    owner: "Dev",
  },
  {
    name: "Rahul Verma",
    lampLabel: "Couldn't be reached",
    reason: "Call did not connect (no answer).",
    owner: null,
  },
  {
    name: "Ananya Bose",
    lampLabel: "Needs a person",
    reason: "The call ended without callback_time and objection — a person needs to ask.",
    owner: "You",
  },
];

const POINTS: { title: string; detail: string }[] = [
  {
    title: "Raised by the call itself",
    detail:
      "A completed call missing a required field, or a contact the run couldn't reach, becomes a row the moment it settles — with the reason written on it.",
  },
  {
    title: "Live across the team",
    detail:
      "The queue syncs in realtime. A row lands for everyone at once; nobody refreshes, nobody double-handles.",
  },
  {
    title: "Owned, not just listed",
    detail:
      "Assign a row, resolve it, or ask a teammate to take it. An escalation is work with a name on it, not a line in a log.",
  },
];

export function NeedsPerson() {
  return (
    <section className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          eyebrow="Escalations"
          title="What needs a person, reaches one."
          sub="Escalations aren't a filter on a log — they're rows your team owns."
        />
      </Reveal>

      <div className="mt-(--deck-gap) grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,520px)] lg:gap-16">
        <div className="flex flex-col gap-7">
          {POINTS.map((point, i) => (
            <Reveal key={point.title} delayMs={i * 70}>
              <div className="flex flex-col gap-1.5 border-l-2 border-l-rule pl-5">
                <h3 className="text-h4 font-medium text-text">{point.title}</h3>
                <p className="max-w-[52ch] text-small text-text-dim">{point.detail}</p>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delayMs={120}>
          <Stage restX={4} restY={7} className="relative">
            <StageLayer
              depth={1}
              aria-hidden
              className="pointer-events-none absolute -inset-10"
            >
              <div className="stage-glow size-full" />
            </StageLayer>

            <StageLayer depth={3} className="relative">
              <div
                role="img"
                aria-label={
                  "The escalation queue, three rows open: Meera Nair, needs a person, ended without decision, assigned to Dev. " +
                  "Rahul Verma, couldn't be reached, unassigned. Ananya Bose, needs a person, ended without callback_time and objection, assigned to you."
                }
                className="card-raised overflow-hidden"
              >
                <div aria-hidden>
                  <div className="flex items-center justify-between gap-4 border-b border-rule px-4 py-3">
                    <span className="text-small font-medium text-text">Needs a person</span>
                    <span className="font-mono text-data text-text-dim">3 open</span>
                  </div>

                  <ul className="divide-y divide-rule">
                    {QUEUE.map((row) => (
                      <li key={row.name} className="flex items-start gap-3 px-4 py-3.5">
                        <span className="mt-1">
                          <Lamp state="flare" size="md" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                            <span className="text-small font-medium text-text">{row.name}</span>
                            <span className="text-label text-lamp-flare-text">{row.lampLabel}</span>
                          </span>
                          <span className="mt-1 block text-small text-text-dim">{row.reason}</span>
                        </span>
                        <span
                          className={
                            row.owner
                              ? "shrink-0 rounded-full bg-surface-sunken px-2.5 py-1 text-label font-medium text-text"
                              : "shrink-0 rounded-full border border-rule px-2.5 py-1 text-label text-text-mute"
                          }
                        >
                          {row.owner ?? "unassigned"}
                        </span>
                      </li>
                    ))}
                  </ul>

                  <p className="border-t border-rule px-4 py-3 text-label text-text-mute">
                    Synced live to everyone on the org — resolve it once, it&apos;s resolved
                    for all.
                  </p>
                </div>
              </div>
            </StageLayer>
          </Stage>
        </Reveal>
      </div>
    </section>
  );
}
