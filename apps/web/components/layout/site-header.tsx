'use client';

import * as RadixPopover from '@radix-ui/react-popover';
import * as RadixDialog from '@radix-ui/react-dialog';
import {
  CaretDownIcon,
  CaretRightIcon,
  ListIcon,
  XIcon,
} from '@phosphor-icons/react/dist/ssr';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/cn';
import { BrandLockup } from '@/components/brand/wordmark';
import { Button } from '@/components/ui/button';

const PRODUCT_LINKS = [
  {
    label: 'How it works',
    href: '/#how-it-works',
    hint: 'Four steps, spreadsheet to queue',
  },
  {
    label: 'Typed results',
    href: '/#capabilities',
    hint: 'Schema-validated, not transcripts',
  },
  {
    label: 'Safety guards',
    href: '/#safety',
    hint: 'Every guard fails closed',
  },
  { label: 'Docs', href: '/docs', hint: 'Goals, schemas, webhooks' },
  { label: 'Changelog', href: '/docs/changelog', hint: 'What shipped, when' },
];

const SOLUTION_LINKS = [
  {
    label: 'Recruiting screening',
    href: '/solutions/recruiting-screening',
    hint: 'Screen a shortlist overnight',
  },
  {
    label: 'Appointment recovery',
    href: '/solutions/appointment-recovery',
    hint: 'Fill the slots that went quiet',
  },
  {
    label: 'Admissions follow-up',
    href: '/solutions/admissions-followup',
    hint: 'Reach every enquiry once',
  },
  {
    label: 'Lead qualification',
    href: '/solutions/lead-qualification',
    hint: 'Only talk to the ones worth talking to',
  },
];

const FLAT_LINKS = [
  { label: 'Pricing', href: '/pricing' },
  { label: 'Docs', href: '/docs' },
  { label: 'Trust', href: '/trust' },
];

export function SiteHeader() {
  // The bottom rule appears only once the page has moved, so the header sits
  // flush with the hero on first paint.
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // One open-menu at a time, owned here rather than per-menu: hovering Solutions
  // opens it and closes Product in the same render, so the two panels can never
  // both be open. The close is delayed so the pointer can cross the gap from a
  // trigger into its panel; opening any menu cancels a pending close.
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelClose = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };
  const openMenuNow = (label: string) => {
    cancelClose();
    setOpenMenu(label);
  };
  const scheduleClose = () => {
    cancelClose();
    // Re-read the DOM's real :hover state when the timer fires rather than
    // trusting which enter/leave events arrived in which order. Moving between
    // two adjacent triggers can deliver the old trigger's `mouseleave` *after*
    // the new trigger's `mouseenter`; trusting that ordering would let a stale
    // leave close the menu the pointer is now sitting on. Whichever menu part is
    // actually hovered wins; if none is, the menus close.
    closeTimer.current = setTimeout(() => {
      const hovered = document.querySelector('[data-menu]:hover');
      setOpenMenu(hovered ? hovered.getAttribute('data-menu') : null);
    }, 140);
  };
  useEffect(() => cancelClose, []);

  return (
    <header
      className={cn(
        'sticky top-0 z-40 h-16 border-b bg-surface',
        'transition-[border-color,box-shadow] duration-(--dur-base) ease-(--ease-out)',
        // Solid, not frosted: the page and the header share --surface, so at the
        // top the header reads as flush with the hero. On scroll a hairline and a
        // soft shadow ease in to lift it above the content passing underneath -
        // an opaque bar never lets text ghost through the way a translucent one does.
        scrolled ? 'border-rule shadow-sm' : 'border-transparent',
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
            open={openMenu === 'Product'}
            onOpen={() => openMenuNow('Product')}
            onScheduleClose={scheduleClose}
            onOpenChange={(next) =>
              next ? openMenuNow('Product') : scheduleClose()
            }
          />
          <MegaMenu
            label="Solutions"
            links={SOLUTION_LINKS}
            open={openMenu === 'Solutions'}
            onOpen={() => openMenuNow('Solutions')}
            onScheduleClose={scheduleClose}
            onOpenChange={(next) =>
              next ? openMenuNow('Solutions') : scheduleClose()
            }
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
          <Button
            asChild
            variant="ghost"
            size="sm"
            className="hidden sm:inline-flex"
          >
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
 * A single-column dropdown: label + one line of context per link, with a caret
 * that slides in on hover. Deliberately just the links - the panel is a way to
 * reach a page, not a place to make the argument twice.
 */
function MegaMenu({
  label,
  links,
  open,
  onOpen,
  onScheduleClose,
  onOpenChange,
}: {
  label: string;
  links: { label: string; href: string; hint: string }[];
  /** Controlled by SiteHeader so only one menu is ever open. */
  open: boolean;
  /** Pointer entered the trigger or panel - open now, cancelling any close. */
  onOpen: () => void;
  /** Pointer left - start the grace timer before closing. */
  onScheduleClose: () => void;
  /** Radix's own open/close (click, Escape, outside-click, keyboard). */
  onOpenChange: (open: boolean) => void;
}) {
  // Hover-driven: opens on pointer-over rather than a click. The grace close and
  // single-open coordination both live in SiteHeader; click and keyboard still
  // work through onOpenChange, so touch and keyboard users are unaffected.
  return (
    <RadixPopover.Root open={open} onOpenChange={onOpenChange}>
      <RadixPopover.Trigger asChild>
        <button
          type="button"
          data-menu={label}
          onMouseEnter={onOpen}
          onMouseLeave={onScheduleClose}
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
          sideOffset={10}
          align="start"
          collisionPadding={16}
          data-menu={label}
          onMouseEnter={onOpen}
          onMouseLeave={onScheduleClose}
          // Don't yank focus/scroll when the menu opens under the pointer;
          // keyboard users still Tab straight into the links.
          onOpenAutoFocus={(e) => e.preventDefault()}
          // Don't return focus to the trigger on close either - otherwise a
          // hover-opened menu leaves a focus-ring box sitting on the trigger
          // after the pointer moves away.
          onCloseAutoFocus={(e) => e.preventDefault()}
          className="menu-pop z-50 w-[min(360px,calc(100vw-32px))] origin-top overflow-hidden rounded-lg border border-rule-strong bg-surface-raised p-2 shadow-overlay"
        >
          <ul className="flex flex-col gap-0.5">
            {links.map((link) => (
              <li key={link.href}>
                <RadixPopover.Close asChild>
                  <Link
                    href={link.href}
                    className="group/row flex items-center justify-between gap-3 rounded-md px-3 py-2.5 transition-colors duration-(--dur-micro) hover:bg-surface-hover"
                  >
                    <span className="flex min-w-0 flex-col gap-0.5">
                      <span className="text-small font-medium text-text">
                        {link.label}
                      </span>
                      <span className="text-small text-text-mute">
                        {link.hint}
                      </span>
                    </span>
                    <CaretRightIcon
                      aria-hidden
                      className="size-4 shrink-0 -translate-x-1 text-text-mute opacity-0 transition-all duration-(--dur-micro) ease-(--ease-out) group-hover/row:translate-x-0 group-hover/row:opacity-100"
                    />
                  </Link>
                </RadixPopover.Close>
              </li>
            ))}
          </ul>
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
    ...FLAT_LINKS.map((l) => ({ ...l, hint: '' })),
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
        <RadixDialog.Content className="sheet-in fixed inset-0 z-50 flex flex-col bg-surface">
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

          <nav
            aria-label="Main"
            className="min-h-0 flex-1 overflow-y-auto px-4 py-6"
          >
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
