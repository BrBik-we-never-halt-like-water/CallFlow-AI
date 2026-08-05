"use client";

import * as RadixPopover from "@radix-ui/react-popover";
import * as RadixDialog from "@radix-ui/react-dialog";
import { CaretDownIcon, ListIcon, XIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { BrandLockup } from "@/components/brand/wordmark";
import { LampStrip } from "@/components/brand/lamp-strip";
import { Button } from "@/components/ui/button";
import type { LampSpec } from "@/lib/lamp";

/** A small proof strip for the mega-panels. Three calls, three outcomes. */
const PANEL_STRIP: LampSpec[] = [
  { state: "jade", label: "Auto-closed" },
  { state: "jade", label: "Auto-closed" },
  { state: "brass", pulse: true, label: "Queued for retry" },
  { state: "jade", label: "Auto-closed" },
  { state: "flare", label: "Needs a person" },
  { state: "jade", label: "Auto-closed" },
];

const PRODUCT_LINKS = [
  { label: "How it works", href: "/#how-it-works", hint: "Four steps, spreadsheet to queue" },
  { label: "Typed results", href: "/#capabilities", hint: "Schema-validated, not transcripts" },
  { label: "Safety guards", href: "/#safety", hint: "Every guard fails closed" },
  { label: "Docs", href: "/docs", hint: "Goals, schemas, webhooks" },
  { label: "Changelog", href: "/docs/changelog", hint: "What shipped, when" },
];

const SOLUTION_LINKS = [
  {
    label: "Recruiting screening",
    href: "/solutions/recruiting-screening",
    hint: "Screen a shortlist overnight",
  },
  {
    label: "Appointment recovery",
    href: "/solutions/appointment-recovery",
    hint: "Fill the slots that went quiet",
  },
  {
    label: "Admissions follow-up",
    href: "/solutions/admissions-followup",
    hint: "Reach every enquiry once",
  },
  {
    label: "Lead qualification",
    href: "/solutions/lead-qualification",
    hint: "Only talk to the ones worth talking to",
  },
];

const FLAT_LINKS = [
  { label: "Pricing", href: "/pricing" },
  { label: "Docs", href: "/docs" },
  { label: "Trust", href: "/trust" },
];

export function SiteHeader() {
  // The bottom rule appears only once the page has moved, so the header sits
  // flush with the hero on first paint.
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-40 h-16 border-b transition-colors duration-(--dur-base)",
        // 92% opacity and no blur: the design leans on hairlines, and a frosted
        // header is the single most recognisable generated-UI tell.
        "bg-[color-mix(in_oklab,var(--surface)_92%,transparent)]",
        scrolled ? "border-rule" : "border-transparent",
      )}
    >
      <div className="mx-auto flex h-full max-w-(--container-marketing) items-center justify-between gap-4 px-4 sm:px-6">
        <Link
          href="/"
          className="shrink-0 rounded-sm text-text transition-opacity hover:opacity-70"
        >
          <BrandLockup />
          <span className="sr-only">CallFlow AI home</span>
        </Link>

        <nav aria-label="Main" className="hidden items-center gap-1 lg:flex">
          <MegaMenu
            label="Product"
            links={PRODUCT_LINKS}
            proof="Every call returns typed fields, not a transcript to read."
          />
          <MegaMenu
            label="Solutions"
            links={SOLUTION_LINKS}
            proof="The same engine, with the goal and schema already written for your vertical."
          />
          {FLAT_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-sm px-3 py-2 text-small font-medium text-text-dim transition-colors duration-(--dur-micro) hover:bg-surface-hover hover:text-text"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild size="sm">
            <Link href="/signup">Start free</Link>
          </Button>
          <MobileNav />
        </div>
      </div>
    </header>
  );
}

/**
 * Two-column panel rather than a plain dropdown: links on the left, and on the
 * right a lamp strip with one line of proof. A nav menu is a page in miniature,
 * and this one gets to make the argument too.
 */
function MegaMenu({
  label,
  links,
  proof,
}: {
  label: string;
  links: { label: string; href: string; hint: string }[];
  proof: string;
}) {
  return (
    <RadixPopover.Root>
      <RadixPopover.Trigger asChild>
        <button
          type="button"
          className="group inline-flex cursor-pointer items-center gap-1 rounded-sm px-3 py-2 text-small font-medium text-text-dim transition-colors duration-(--dur-micro) hover:bg-surface-hover hover:text-text"
        >
          {label}
          <CaretDownIcon
            aria-hidden
            className="size-3 transition-transform duration-(--dur-base) group-data-[state=open]:rotate-180"
          />
        </button>
      </RadixPopover.Trigger>

      <RadixPopover.Portal>
        <RadixPopover.Content
          sideOffset={8}
          align="start"
          collisionPadding={16}
          className="z-50 w-[min(640px,calc(100vw-32px))] overflow-hidden rounded-md border border-rule-strong bg-surface-raised shadow-overlay"
        >
          <div className="grid gap-0 sm:grid-cols-[1fr_240px]">
            <ul className="p-2">
              {links.map((link) => (
                <li key={link.href}>
                  <RadixPopover.Close asChild>
                    <Link
                      href={link.href}
                      className="flex flex-col gap-0.5 rounded-sm px-3 py-2 transition-colors duration-(--dur-micro) hover:bg-surface-hover"
                    >
                      <span className="text-small font-medium text-text">{link.label}</span>
                      <span className="text-small text-text-mute">{link.hint}</span>
                    </Link>
                  </RadixPopover.Close>
                </li>
              ))}
            </ul>

            <div className="flex flex-col gap-3 border-t border-rule bg-surface-sunken p-4 sm:border-l sm:border-t-0">
              <LampStrip lamps={PANEL_STRIP} size="sm" />
              <p className="text-small text-text-dim">{proof}</p>
            </div>
          </div>
        </RadixPopover.Content>
      </RadixPopover.Portal>
    </RadixPopover.Root>
  );
}

/** Full-screen sheet on mobile: links at h3, actions pinned to the bottom. */
function MobileNav() {
  const [open, setOpen] = useState(false);
  const all = [
    ...PRODUCT_LINKS.map((l) => l),
    ...SOLUTION_LINKS.map((l) => l),
    ...FLAT_LINKS.map((l) => ({ ...l, hint: "" })),
  ];

  return (
    <RadixDialog.Root open={open} onOpenChange={setOpen}>
      <RadixDialog.Trigger asChild>
        <button
          type="button"
          aria-label="Open menu"
          className="flex size-10 cursor-pointer items-center justify-center rounded-sm text-text transition-colors hover:bg-surface-hover lg:hidden"
        >
          <ListIcon aria-hidden className="size-5" />
        </button>
      </RadixDialog.Trigger>

      <RadixDialog.Portal>
        <RadixDialog.Content className="fixed inset-0 z-50 flex flex-col bg-surface">
          <RadixDialog.Title className="sr-only">Menu</RadixDialog.Title>

          <div className="flex h-16 shrink-0 items-center justify-between border-b border-rule px-4">
            <BrandLockup />
            <RadixDialog.Close
              aria-label="Close menu"
              className="flex size-10 cursor-pointer items-center justify-center rounded-sm text-text hover:bg-surface-hover"
            >
              <XIcon aria-hidden className="size-5" />
            </RadixDialog.Close>
          </div>

          <nav aria-label="Main" className="min-h-0 flex-1 overflow-y-auto px-4 py-6">
            <ul className="flex flex-col gap-1">
              {all.map((link) => (
                <li key={`${link.href}-${link.label}`}>
                  <Link
                    href={link.href}
                    onClick={() => setOpen(false)}
                    className="block rounded-sm px-2 py-3 text-h3 text-text transition-colors hover:bg-surface-hover"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div className="flex shrink-0 flex-col gap-2 border-t border-rule p-4">
            <Button asChild size="lg">
              <Link href="/signup" onClick={() => setOpen(false)}>
                Start free
              </Link>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="/login" onClick={() => setOpen(false)}>
                Sign in
              </Link>
            </Button>
          </div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
