import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Eyebrow } from "@/components/ui/panel";
import { Rule } from "@/components/ui/rule";

export const metadata: Metadata = {
  title: "About",
  description:
    "What CallFlow is for, who builds it, and how to reach them.",
};

/**
 * About   deliberately short.
 *
 * This is also where the author credit lives. It was previously in the site footer,
 * which put a personal byline on every page of a product that is asking businesses
 * to trust it with outbound calling; a founder credit belongs on one page, and this
 * is that page.
 */
export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 pt-12 sm:px-6">
      <header className="flex flex-col gap-4">
        <Eyebrow>About</Eyebrow>
        <h1 className="font-display text-display-l text-text">
          Built for the person who owns the phone list.
        </h1>
      </header>

      <div className="mt-10 flex flex-col gap-5">
        <p className="text-body-l text-text-dim">
          CallFlow exists because of one specific frustration: a call log tells you a
          call happened, and almost nothing else. A delighted customer and a furious one
          both read <span className="font-mono text-data">completed</span>, and the
          difference only surfaces when someone escalates   by which point it is a
          complaint rather than a conversation.
        </p>
        <p className="text-body text-text-dim">
          The people who feel this hardest are not developers. They are recruiting
          coordinators, clinic managers, admissions teams, and agency owners   the
          person who owns a spreadsheet of numbers and is judged on what happens to it.
          They are choosing between hiring another tele-caller and finding another way,
          and almost every tool aimed at them is sold to their engineering team instead.
        </p>
        <p className="text-body text-text-dim">
          So this is built as an operations tool, not an API with a dashboard bolted on.
          You write the goal in plain English, you see exactly what each contact would
          hear before anything is dialled, and every call comes back as typed fields you
          can act on. The calls that need judgement reach a person. The rest close
          themselves.
        </p>
      </div>

      <Rule className="my-10" />

      <section className="flex flex-col gap-4">
        <h2 className="font-display text-h3 text-text">Who builds it</h2>
        <p className="text-body text-text-dim">
          CallFlow is built by{" "}
          <a
            href="https://github.com/mohdcodes"
            target="_blank"
            rel="noreferrer"
            className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
          >
            mohdcodes
          </a>
          . If something here is wrong, slow, or missing, that is the person to tell  
          and the fastest way to get it changed is to say which screen you were on and
          what you expected to happen.
        </p>
        <ul className="flex flex-wrap gap-x-6 gap-y-2">
          {[
            { label: "GitHub", href: "https://github.com/mohdcodes" },
            { label: "LinkedIn", href: "https://linkedin.com/in/mohdcodes" },
            { label: "Website", href: "https://mohdcodess.onrender.com" },
          ].map((link) => (
            <li key={link.label}>
              <a
                href={link.href}
                target="_blank"
                rel="noreferrer"
                className="text-small text-text-dim underline decoration-rule-strong underline-offset-4 transition-colors hover:text-text hover:decoration-current"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>
      </section>

      <Rule className="my-10" />

      <section className="flex flex-col gap-4">
        <h2 className="font-display text-h3 text-text">Getting in touch</h2>
        <dl className="flex flex-col gap-3">
          {[
            {
              term: "Sales and demos",
              detail: "Book a 15-minute call and bring your own list   we will run it in dry mode together.",
              href: "/demo",
              cta: "Book a demo",
            },
            {
              term: "Support",
              detail: "support@callflow.ai. Include the run ID from the URL and we can see exactly what you saw.",
            },
            {
              term: "Security",
              detail: "security@callflow.ai. Acknowledged within two business days.",
            },
            {
              term: "Legal and DPA",
              detail: "legal@callflow.ai, or request the agreement from the trust page.",
              href: "/trust#dpa",
              cta: "Request the DPA",
            },
          ].map((item) => (
            <div key={item.term} className="flex flex-col gap-1 border-b border-rule pb-3 last:border-0">
              <dt className="text-small font-medium text-text">{item.term}</dt>
              <dd className="text-small text-text-dim">
                {item.detail}
                {item.href ? (
                  <>
                    {" "}
                    <Link
                      href={item.href}
                      className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
                    >
                      {item.cta}
                    </Link>
                  </>
                ) : null}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <div className="mt-10 flex flex-wrap gap-3">
        <Button asChild size="lg">
          <Link href="/signup">Start free</Link>
        </Button>
        <Button asChild variant="secondary" size="lg">
          <Link href="/demo">Book a 15-min demo</Link>
        </Button>
      </div>
    </div>
  );
}
