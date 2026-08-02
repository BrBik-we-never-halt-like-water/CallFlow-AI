import Link from "next/link";
import Prewarm from "./ui/prewarm";
import { SiteFooter, SiteHeader } from "./ui/site";
import {
  ArrowRightIcon,
  ChartIcon,
  CheckIcon,
  ClockIcon,
  PhoneIcon,
  ShieldIcon,
  SparkIcon,
  UsersIcon,
} from "./ui/icons";

const FEATURES = [
  {
    Icon: SparkIcon,
    title: "Goal-driven, not scripted",
    body: "You write an objective in plain English. The agent improvises the conversation and adapts when people go off-script.",
  },
  {
    Icon: ChartIcon,
    title: "Typed results, not transcripts",
    body: "Every call returns schema-validated JSON — destination, dates, budget, sentiment — ready for your systems.",
  },
  {
    Icon: UsersIcon,
    title: "Knows when to back off",
    body: "Frustration and opt-outs escalate to a person. Bad timing gets queued for a polite retry instead.",
  },
  {
    Icon: ShieldIcon,
    title: "Safe by default",
    body: "Dry run is on until you turn it off. An allowlist and a per-run ceiling stop accidental calls.",
  },
  {
    Icon: ClockIcon,
    title: "Runs while you sleep",
    body: "Campaigns work through evenings and weekends. Your team reads outcomes in the morning.",
  },
  {
    Icon: PhoneIcon,
    title: "Real phone calls",
    body: "CALL-E handles dialing, speech, turn-taking, voicemail, and IVR. No telephony stack to maintain.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Load your contacts",
    body: "Type them into the table or import a CSV. Every row is validated before anything is dialed.",
  },
  {
    n: "02",
    title: "Choose a campaign",
    body: "Use a built-in one or write your own goal and pick exactly which fields to extract.",
  },
  {
    n: "03",
    title: "Run it",
    body: "Dry run proves the pipeline for free. Live mode dials, and results stream back as each call ends.",
  },
  {
    n: "04",
    title: "Triage what matters",
    body: "Clean outcomes auto-close. Only frustration, opt-outs, and human requests reach a person.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Start waking the API while the visitor reads, so the dashboard is
          warm by the time they click through. */}
      <Prewarm />
      <SiteHeader />

      {/* ---- Hero ---- */}
      <section className="relative isolate overflow-hidden">
        <div className="hero-dots pointer-events-none absolute inset-0 -z-10" />
        {/* Short top padding so the CTAs clear the fold; generous below. */}
        <div className="mx-auto max-w-3xl px-6 pb-16 pt-10 text-center sm:pt-12">
          <a
            href="https://heycall-e.com"
            target="_blank"
            rel="noreferrer"
            className="group inline-flex cursor-pointer items-center gap-2.5 rounded-full border border-[var(--color-border)] bg-white py-1 pl-1 pr-3.5 text-xs shadow-sm transition-all hover:border-[var(--color-brand)]/40 hover:shadow"
          >
            <span className="brand-gradient inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-semibold text-white">
              <PhoneIcon className="h-3 w-3" />
              CALL-E
            </span>
            <span className="font-medium text-[var(--color-ink-soft)]">
              Real phone calls, powered by CALL-E
            </span>
            <ArrowRightIcon className="h-3 w-3 text-[var(--color-muted)] transition-transform group-hover:translate-x-0.5" />
          </a>

          <h1 className="mt-6 text-4xl font-semibold leading-[1.1] tracking-tight text-[var(--color-ink)] sm:text-6xl">
            Your outbound calls,
            <br />
            <span className="brand-text-gradient">running themselves.</span>
          </h1>

          <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-[var(--color-ink-soft)]">
            Customer outreach eats hours, and you never know how a call went
            until someone complains. CallFlow AI dials 24×7, holds real
            conversations, and escalates only what needs a person.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/dashboard"
              className="brand-gradient inline-flex cursor-pointer items-center gap-2 rounded-lg px-6 py-3 text-sm font-medium text-white shadow-sm transition hover:brightness-110 active:scale-[0.98]"
            >
              Open the dashboard
              <ArrowRightIcon className="h-4 w-4" />
            </Link>
            <Link
              href="#how"
              className="cursor-pointer rounded-lg border border-[var(--color-border)] bg-white px-6 py-3 text-sm font-medium text-[var(--color-ink)] transition-colors hover:bg-[var(--color-subtle)]"
            >
              See how it works
            </Link>
          </div>

          <p className="mt-4 text-xs text-[var(--color-muted)]">
            Dry run is on by default — nothing is dialed until you turn it off.
          </p>

          {/* Inline proof points keep the fold useful without adding height. */}
          <div className="mt-9 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 border-t border-[var(--color-border)] pt-6">
            {[
              { stat: "24×7", label: "Always dialing" },
              { stat: "100%", label: "Calls scored" },
              { stat: "0", label: "Credits in dry run" },
            ].map((p) => (
              <div key={p.label} className="text-center">
                <div className="nums brand-text-gradient text-xl font-semibold">
                  {p.stat}
                </div>
                <div className="text-[11px] text-[var(--color-muted)]">{p.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---- Problem ---- */}
      <section
        id="problem"
        className="border-y border-[var(--color-border)] bg-[var(--color-subtle)] py-16"
      >
        <div className="mx-auto max-w-6xl px-6">
          <div className="grid items-start gap-12 lg:grid-cols-[1fr_1fr]">
            <div>
              <h2 className="text-3xl font-semibold tracking-tight text-[var(--color-ink)]">
                A completed call tells you nothing
              </h2>
              <p className="mt-5 text-sm leading-relaxed text-[var(--color-ink-soft)]">
                In a normal call log, a delighted customer and a furious one look
                identical — both just say <em>completed</em>. Teams burn hours
                dialing, repeating the same questions, and typing notes into a
                CRM afterwards, and still find out a call went badly only when it
                escalates.
              </p>
              <p className="mt-4 text-sm leading-relaxed text-[var(--color-ink-soft)]">
                CallFlow AI turns every conversation into typed data the moment
                it ends, so the work that needs a human is visible immediately
                and the rest closes itself.
              </p>
            </div>

            {/* Before / after */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="card p-5">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                  Without CallFlow AI
                </h3>
                <ul className="mt-3 space-y-2.5">
                  {[
                    "Every call dialed by hand",
                    "Notes typed up afterwards",
                    "Sentiment invisible until escalation",
                    "Nothing happens after 6pm",
                  ].map((t) => (
                    <li
                      key={t}
                      className="flex gap-2 text-xs leading-relaxed text-[var(--color-ink-soft)]"
                    >
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-300" />
                      {t}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="card border-[var(--color-brand)]/25 bg-[var(--color-brand-soft)] p-5">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-brand)]">
                  With CallFlow AI
                </h3>
                <ul className="mt-3 space-y-2.5">
                  {[
                    "Campaigns dial themselves",
                    "Typed JSON, no transcription",
                    "Sentiment scored on every call",
                    "Runs overnight and weekends",
                  ].map((t) => (
                    <li
                      key={t}
                      className="flex gap-2 text-xs leading-relaxed text-[var(--color-ink)]"
                    >
                      <CheckIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-brand)]" />
                      {t}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ---- Features ---- */}
      <section className="py-16">
        <div className="mx-auto max-w-6xl px-6">
          <div className="max-w-2xl">
            <h2 className="text-3xl font-semibold tracking-tight text-[var(--color-ink)]">
              An operations layer, not a robocall dialer
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-[var(--color-ink-soft)]">
              CALL-E handles the conversation. CallFlow AI handles everything
              around it — campaigns, safety, structure, and triage.
            </p>
          </div>

          <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ Icon, title, body }) => (
              <div key={title} className="card card-hover p-6">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--color-brand-soft)] text-[var(--color-brand)]">
                  <Icon className="h-4.5 w-4.5" />
                </div>
                <h3 className="mt-4 text-sm font-semibold text-[var(--color-ink)]">
                  {title}
                </h3>
                <p className="mt-2 text-xs leading-relaxed text-[var(--color-ink-soft)]">
                  {body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---- How it works ---- */}
      <section
        id="how"
        className="border-y border-[var(--color-border)] bg-[var(--color-subtle)] py-16"
      >
        <div className="mx-auto max-w-6xl px-6">
          <div className="max-w-2xl">
            <h2 className="text-3xl font-semibold tracking-tight text-[var(--color-ink)]">
              How it works
            </h2>
            <p className="mt-3 text-sm text-[var(--color-ink-soft)]">
              Four steps from a spreadsheet to a triaged queue.
            </p>
          </div>

          <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => (
              <div key={s.n} className="card p-6">
                <span className="nums text-xs font-semibold text-[var(--color-brand)]">
                  {s.n}
                </span>
                <h3 className="mt-3 text-sm font-semibold text-[var(--color-ink)]">
                  {s.title}
                </h3>
                <p className="mt-2 text-xs leading-relaxed text-[var(--color-ink-soft)]">
                  {s.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---- CTA ---- */}
      <section className="py-16">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-[var(--color-ink)]">
            Try it without spending a credit
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-sm leading-relaxed text-[var(--color-ink-soft)]">
            Dry run walks the whole pipeline — validation, safety gates, and the
            exact words each contact would hear — without placing a single call.
          </p>
          <Link
            href="/dashboard"
            className="brand-gradient mt-8 inline-flex cursor-pointer items-center gap-2 rounded-lg px-6 py-3 text-sm font-medium text-white shadow-sm transition hover:brightness-110 active:scale-[0.98]"
          >
            Open the dashboard
            <ArrowRightIcon className="h-4 w-4" />
          </Link>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}
