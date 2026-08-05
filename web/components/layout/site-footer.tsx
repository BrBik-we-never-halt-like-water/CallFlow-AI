import Link from "next/link";
import { Mark } from "@/components/brand/mark";
import { BrandLockup } from "@/components/brand/wordmark";

const COLUMNS = [
  {
    heading: "Product",
    links: [
      { label: "Features", href: "/#capabilities" },
      { label: "How it works", href: "/#how-it-works" },
      { label: "Pricing", href: "/pricing" },
      { label: "Docs", href: "/docs" },
      { label: "Changelog", href: "/docs/changelog" },
    ],
  },
  {
    heading: "Solutions",
    links: [
      { label: "Recruiting screening", href: "/solutions/recruiting-screening" },
      { label: "Appointment recovery", href: "/solutions/appointment-recovery" },
      { label: "Admissions follow-up", href: "/solutions/admissions-followup" },
      { label: "Lead qualification", href: "/solutions/lead-qualification" },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "About", href: "/about" },
      { label: "Contact", href: "/demo" },
      { label: "Status", href: "/status" },
      { label: "Trust", href: "/trust" },
    ],
  },
  {
    heading: "Resources",
    links: [
      { label: "Getting started", href: "/docs/getting-started" },
      { label: "Writing a good goal", href: "/docs/writing-a-good-goal" },
      { label: "Result schemas", href: "/docs/result-schemas" },
      { label: "API reference", href: "/docs/api-reference" },
    ],
  },
];

/**
 * Capability strip. Live text, not a raster.
 *
 * It deliberately does not scroll: a static rule of words reads as intentional, a
 * marquee reads as a template.
 */
const CAPABILITIES = [
  "Always on",
  "Adaptive conversations",
  "Typed results",
  "Sentiment on every call",
  "Human handoff when needed",
];

export function SiteFooter() {
  return (
    <footer className="mt-(--space-section) border-t border-rule bg-surface-raised">
      <div className="mx-auto max-w-(--container-marketing) px-4 py-14 sm:px-6">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.4fr_repeat(4,1fr)]">
          <div className="flex flex-col gap-4">
            <Link href="/" className="w-fit text-text">
              <BrandLockup />
              <span className="sr-only">CallFlow AI home</span>
            </Link>
            <p className="max-w-xs text-small text-text-dim">
              An operations layer for outbound phone calls. Load a list, write a goal,
              and get typed results back — with only the calls that need a person
              reaching one.
            </p>
          </div>

          {COLUMNS.map((column) => (
            <div key={column.heading} className="flex flex-col gap-3">
              <h2 className="eyebrow text-text">{column.heading}</h2>
              <ul className="flex flex-col gap-2">
                {column.links.map((link) => (
                  <li key={`${column.heading}-${link.label}`}>
                    <Link
                      href={link.href}
                      className="text-small text-text-dim transition-colors duration-(--dur-micro) hover:text-text"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Legal row */}
        <div className="mt-10 flex flex-wrap gap-x-5 gap-y-2 border-t border-rule pt-6">
          {[
            { label: "Privacy", href: "/trust" },
            { label: "Terms", href: "/trust" },
            { label: "Acceptable use", href: "/trust" },
            { label: "DPA", href: "/trust#dpa" },
          ].map((link) => (
            <Link
              key={link.label}
              href={link.href}
              className="text-small text-text-mute transition-colors hover:text-text"
            >
              {link.label}
            </Link>
          ))}
        </div>

        <div className="mt-6 flex flex-col-reverse items-start justify-between gap-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3">
            <Mark title={null} className="h-4" />
            <p className="text-small text-text-mute">© 2026 CallFlow AI</p>
          </div>

          <p className="text-small text-text-mute">
            Created by{" "}
            <a
              href="https://brbik.com"
              target="_blank"
              rel="noreferrer"
              className="font-medium text-text underline decoration-rule-strong underline-offset-2 transition-colors hover:decoration-current"
            >
              BrBik
            </a>
          </p>
        </div>
      </div>

      {/* Full-bleed capability band. */}
      <div className="border-t border-rule">
        <div className="mx-auto max-w-(--container-marketing) overflow-x-auto px-4 py-6 sm:px-6">
          <ul className="flex min-w-max items-center justify-center gap-x-6 gap-y-2">
            {CAPABILITIES.map((capability, i) => (
              <li key={capability} className="flex items-center gap-6">
                <span className="eyebrow text-text-mute">{capability}</span>
                {i < CAPABILITIES.length - 1 ? (
                  <span aria-hidden className="h-3 w-px bg-rule" />
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </footer>
  );
}
