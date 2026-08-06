import { LampStrip } from "@/components/brand/lamp-strip";
import { LiveLamp } from "./live-lamp";
import { Eyebrow, SectionHeading } from "@/components/ui/panel";
import { Reveal } from "@/components/ui/reveal";
import { Tag } from "@/components/ui/badge";

/**
 * How it works, in four steps.
 *
 * Numbering is justified here because this is a genuine sequence — you cannot
 * triage before you run, or run before you have contacts. Each step shows a small
 * panel of real UI built from the same components as the product, not a
 * screenshot: a screenshot goes stale the first time a button moves.
 */

const STEPS = [
  {
    n: "01",
    title: "Load your contacts",
    body: "Paste them in or drop a CSV. Every row is validated before anything is dialled.",
    panel: <ContactsPanel />,
  },
  {
    n: "02",
    title: "Choose a campaign",
    body: "Use a starter template or write your own goal and pick exactly which fields to extract.",
    panel: <CampaignPanel />,
  },
  {
    n: "03",
    title: "Run it",
    body: "Rows are validated and the guards checked before anything dials. Results arrive as each call ends.",
    panel: <RunPanel />,
  },
  {
    n: "04",
    title: "Triage what matters",
    body: "Clean outcomes close themselves. Only frustration, opt-outs, and requests for a person reach your team.",
    panel: <TriagePanel />,
  },
];

export function Steps() {
  return (
    <section id="how-it-works" className="mx-auto max-w-(--container-marketing) px-4 sm:px-6">
      <Reveal>
        <SectionHeading
          eyebrow="How it works"
          title="Four steps from a spreadsheet to a triaged queue."
        />
      </Reveal>

      <div className="relative mt-10">
        {/* The connecting line only exists on desktop, where the steps actually
            read as a horizontal sequence. A gradient that fades at both ends so
            it reads as a current running through the steps, not a hard rail. */}
        <div
          aria-hidden
          className="absolute inset-x-0 top-3 hidden h-px bg-gradient-to-r from-transparent via-rule-strong to-transparent lg:block"
        />

        <ol className="grid gap-8 lg:grid-cols-4 lg:gap-6">
          {STEPS.map((step, i) => (
            <Reveal key={step.n} delayMs={i * 60}>
              <li className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <span className="relative z-10 bg-surface pr-2">
                    <Eyebrow as="span" className="text-text">
                      {step.n}
                    </Eyebrow>
                  </span>
                </div>
                <h3 className="text-h4 font-medium text-text">{step.title}</h3>
                {/* Fixed heights at desktop so the four cards line up top and
                    bottom into a symmetric row; natural height when stacked. */}
                <p className="text-small text-text-dim lg:min-h-[3.5rem]">{step.body}</p>
                <div className="surface-flow mt-1 flex flex-col justify-center overflow-hidden p-4 shadow-sm transition-[box-shadow,transform] duration-(--dur-base) ease-(--ease-out) hover:-translate-y-0.5 hover:shadow-md lg:min-h-[8rem]">
                  {step.panel}
                </div>
              </li>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}

function ContactsPanel() {
  const rows = [
    { name: "Aditi Sharma", phone: "+91*******210", ok: true },
    { name: "Rahul Verma", phone: "+91*******884", ok: true },
    { name: "Priya Nair", phone: "98765", ok: false },
  ];

  return (
    <div className="flex flex-col gap-1.5">
      {rows.map((row) => (
        <div key={row.name} className="flex items-center gap-2">
          <span className="min-w-0 flex-1 truncate text-small text-text">{row.name}</span>
          <span
            className={
              row.ok
                ? "font-mono text-data tabular-nums text-text-mute"
                : "font-mono text-data tabular-nums text-lamp-flare-text"
            }
          >
            {row.phone}
          </span>
        </div>
      ))}
      <p className="pt-1 text-small text-lamp-flare-text">1 row needs a country code.</p>
    </div>
  );
}

function CampaignPanel() {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-small text-text">Holiday enquiry follow-up</p>
      <div className="flex flex-wrap gap-1">
        <Tag>destination</Tag>
        <Tag>party_size</Tag>
        <Tag>budget</Tag>
      </div>
      <p className="font-mono text-data text-text-mute">4 fields returned</p>
    </div>
  );
}

function RunPanel() {
  return (
    <div className="flex flex-col gap-2">
      <p className="eyebrow text-text-mute">Guards on</p>
      <div className="flex flex-wrap gap-1">
        <Tag>ALLOWLIST</Tag>
        <Tag>CEILING 25</Tag>
        <Tag>RATE 2/HR</Tag>
      </div>
      <LampStrip
        lamps={[
          { state: "jade", label: "Auto-closed" },
          { state: "jade", label: "Auto-closed" },
          { state: "off", label: "Queued" },
          { state: "off", label: "Queued" },
          { state: "off", label: "Queued" },
        ]}
        size="sm"
      />
    </div>
  );
}

function TriagePanel() {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <LiveLamp state="jade" size="sm" label="Auto-closed" />
        <span className="text-small text-text-dim">9 closed themselves</span>
      </div>
      <div className="flex items-center gap-2">
        <LiveLamp state="brass" size="sm" pulse label="Queued for retry" />
        <span className="text-small text-text-dim">2 queued for retry</span>
      </div>
      <div className="flex items-center gap-2">
        <LiveLamp state="flare" size="sm" label="Needs a person" />
        <span className="text-small text-text">3 need a person</span>
      </div>
    </div>
  );
}
