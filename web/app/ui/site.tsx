"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeftIcon } from "./icons";

export function SiteHeader({ cta = true }: { cta?: boolean }) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`sticky top-0 z-50 border-b bg-white/85 backdrop-blur-md transition-colors duration-200 ${
        scrolled ? "border-[var(--color-border)]" : "border-transparent"
      }`}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/"
            className="shrink-0 cursor-pointer transition-opacity hover:opacity-70"
          >
            <Image
              src="/assets/navbarLogo.jpg"
              alt="CallFlow AI"
              width={408}
              height={103}
              priority
              className="h-7 w-auto"
            />
          </Link>

          <span className="hidden h-5 w-px bg-[var(--color-border)] sm:block" />

          <a
            href="https://heycall-e.com"
            target="_blank"
            rel="noreferrer"
            title="CallFlow AI runs on the CALL-E voice platform"
            className="hidden shrink-0 cursor-pointer items-center gap-1.5 text-[11px] font-medium text-[var(--color-muted)] transition-colors hover:text-[var(--color-brand)] sm:inline-flex"
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
            </span>
            Powered by CALL-E
          </a>
        </div>

        <nav className="flex items-center gap-1 text-sm">
          {/* Anchor links only make sense on the landing page. */}
          {cta && (
            <>
              <Link
                href="/#problem"
                className="hidden cursor-pointer rounded-lg px-3 py-2 text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-subtle)] hover:text-[var(--color-ink)] sm:block"
              >
                Why
              </Link>
              <Link
                href="/#how"
                className="hidden cursor-pointer rounded-lg px-3 py-2 text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-subtle)] hover:text-[var(--color-ink)] sm:block"
              >
                How it works
              </Link>
            </>
          )}
          {cta ? (
            <Link
              href="/dashboard"
              className="ml-2 cursor-pointer rounded-lg bg-[var(--color-ink)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
            >
              Open dashboard
            </Link>
          ) : (
            <Link
              href="/"
              aria-label="Back to home"
              className="ml-2 inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm font-medium text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-subtle)] hover:text-[var(--color-ink)]"
            >
              <ArrowLeftIcon className="h-4 w-4" />
              Back
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}

const FOOTER_LINKS = [
  {
    heading: "Product",
    items: [
      { label: "Dashboard", href: "/dashboard" },
      { label: "How it works", href: "/#how" },
      { label: "Why it exists", href: "/#problem" },
    ],
  },
  {
    heading: "Built on",
    items: [
      { label: "CALL-E", href: "https://heycall-e.com", ext: true },
      { label: "Documentation", href: "https://docs.heycall-e.com", ext: true },
      {
        label: "Integrations",
        href: "https://github.com/CALLE-AI/call-e-integrations",
        ext: true,
      },
    ],
  },
  {
    heading: "Developer",
    items: [
      { label: "GitHub", href: "https://github.com/mohdcodes", ext: true },
      { label: "LinkedIn", href: "https://linkedin.com/in/mohdcodes", ext: true },
      { label: "Website", href: "https://mohdcodess.onrender.com", ext: true },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="mt-20 border-t border-[var(--color-border)] bg-white">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.5fr_repeat(3,1fr)]">
          <div>
            <Image
              src="/assets/navbarLogo.jpg"
              alt="CallFlow AI"
              width={408}
              height={103}
              className="h-7 w-auto"
            />
            <p className="mt-4 max-w-xs text-xs leading-relaxed text-[var(--color-muted)]">
              A 24×7 AI calling desk. Feed in contacts and a goal — CallFlow AI
              dials, holds real conversations, extracts typed results, and
              escalates only what needs a person.
            </p>
          </div>

          {FOOTER_LINKS.map((col) => (
            <div key={col.heading}>
              <h3 className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-ink)]">
                {col.heading}
              </h3>
              <ul className="mt-3 space-y-2.5">
                {col.items.map((item) => (
                  <li key={item.label}>
                    {"ext" in item && item.ext ? (
                      <a
                        href={item.href}
                        target="_blank"
                        rel="noreferrer"
                        className="cursor-pointer text-xs text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-brand)]"
                      >
                        {item.label}
                      </a>
                    ) : (
                      <Link
                        href={item.href}
                        className="cursor-pointer text-xs text-[var(--color-ink-soft)] transition-colors hover:text-[var(--color-brand)]"
                      >
                        {item.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-[var(--color-border)] pt-6 sm:flex-row">
          <p className="text-xs text-[var(--color-muted)]">
            Built by{" "}
            <a
              href="https://mohdcodess.onrender.com"
              target="_blank"
              rel="noreferrer"
              className="cursor-pointer font-medium text-[var(--color-ink)] hover:text-[var(--color-brand)]"
            >
              mohdcodes
            </a>{" "}
            · Powered by CALL-E
          </p>
          <p className="font-mono text-[11px] text-[var(--color-muted)]">v0.1.0</p>
        </div>
      </div>

      {/* Capability strip closes the page. */}
      <div className="border-t border-[var(--color-border)] bg-white">
        <div className="mx-auto max-w-6xl overflow-x-auto px-6 py-10">
          <Image
            src="/assets/footerBranding.jpg"
            alt="Always On · Smart Calls · Real Conversations · Typed Results · Books Follow-through · Human Handoff When Needed"
            width={1247}
            height={189}
            className="mx-auto h-auto w-full min-w-[680px] max-w-3xl"
          />
        </div>
      </div>
    </footer>
  );
}
