"use client";

import * as RadixPopover from "@radix-ui/react-popover";
import * as RadixDialog from "@radix-ui/react-dialog";
import { CaretDownIcon, ListIcon, XIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { BrandLockup } from "@/components/brand/wordmark";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";

/**
 * The site header.
 *
 * **One menu, not two.** This carried a `Product` mega-menu *and* a
 * `Solutions` mega-menu, plus three flat links, a theme toggle and two
 * buttons - eight interactive things in one bar, for a site with five real
 * destinations. `Product` was also mostly page anchors ("How it works",
 * "Typed results", "Safety guards") which the page's own scroll already
 * reveals, and it listed `Docs` a second time when `Docs` was already a flat
 * link beside it.
 *
 * So: the anchors go (scrolling is the navigation for a one-page argument),
 * `Solutions` keeps the menu because four separate routes genuinely need
 * disclosure, and everything else is flat. Five items, one dropdown.
 *
 * **Active route is shown.** Nothing in the old bar indicated where you
 * were. A nav that never marks the current page is a nav you have to re-read
 * on every screen.
 */

/** The four solution routes - the only part of the site deep enough to need
 *  a menu. Hints kept: these are unfamiliar destination names, where a page
 *  anchor like "Pricing" explains itself. */
const SOLUTIONS = [
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
    hint: "Qualify before a rep is spent",
  },
];

/** Flat destinations. `Pricing` points at the home page's own section rather
 *  than a `/pricing` route: the plans and live prices are real, the
 *  standalone page and its comparison matrix are not built, and linking to a
 *  route that does not exist is worse than linking to the section that does. */
const LINKS = [
  { label: "Pricing", href: "/#pricing" },
  { label: "Docs", href: "/docs" },
  { label: "Trust", href: "/trust" },
];

export function SiteHeader() {
  const pathname = usePathname();

  // The bottom rule appears only once the page has moved, so the header sits
  // flush with the hero on first paint.
  const [scrolled, setScrolled] = useState(false);

  // Clicking the logo while already on the page it links to is a route no-op, so
  // Next never scrolls. Take over that case and scroll to the top ourselves.
  const scrollTopIfHere = (href: string) => (e: React.MouseEvent) => {
    if (pathname !== href) return;
    e.preventDefault();
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  };

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // The grace close lets the pointer cross the gap from the trigger into the
  // panel without the menu shutting under it.
  const [menuOpen, setMenuOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelClose = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };
  const openNow = () => {
    cancelClose();
    setMenuOpen(true);
  };
  const scheduleClose = () => {
    cancelClose();
    // Re-read the DOM's real :hover state when the timer fires rather than
    // trusting which enter/leave events arrived in which order - moving from
    // the trigger to the panel can deliver the trigger's `mouseleave` after
    // the panel's `mouseenter`.
    closeTimer.current = setTimeout(() => {
      setMenuOpen(Boolean(document.querySelector("[data-solutions]:hover")));
    }, 140);
  };
  useEffect(() => cancelClose, []);

  const onSolutions = pathname.startsWith("/solutions");

  return (
    <header
      className={cn(
        // Height comes from the token, not a literal. `--h-site-header` is what
        // `scroll-padding-top` and the deck sections' own height are computed
        // from, so a literal here becomes a sliver of the previous section
        // showing under the bar.
        "sticky top-0 z-40 h-(--h-site-header) border-b",
        "transition-[border-color,box-shadow,background-color] duration-(--dur-base) ease-(--ease-out)",
        // Flush with the page at the top - header and hero share `--surface`,
        // so there is nothing to lift. Once content passes underneath, the bar
        // lifts with a rule and a shadow but stays **opaque**: nav labels sit
        // on a known surface at a known contrast rather than on whatever
        // happens to be scrolling beneath them.
        scrolled
          ? "border-rule bg-surface-raised shadow-sm"
          : "border-transparent bg-surface",
      )}
    >
      <div className="mx-auto flex h-full max-w-(--container-marketing) items-center gap-4 px-4 sm:px-6">
        <Link
          href="/"
          onClick={scrollTopIfHere("/")}
          className="shrink-0 rounded-sm text-text transition-opacity hover:opacity-70"
        >
          <BrandLockup />
          <span className="sr-only">CallFlow AI home</span>
        </Link>

        {/* Centre, not hard-left after the logo: with five items the bar reads
            as three zones - identity, navigation, action - instead of a left
            pile and a right pile with a gap in the middle. */}
        <nav
          aria-label="Main"
          className="hidden flex-1 items-center justify-center gap-0.5 lg:flex"
        >
          <SolutionsMenu
            open={menuOpen}
            active={onSolutions}
            onOpen={openNow}
            onScheduleClose={scheduleClose}
            onOpenChange={(next) => (next ? openNow() : scheduleClose())}
          />

          {LINKS.map((link) => (
            <NavLink
              key={link.href}
              href={link.href}
              // A hash link is "active" only by pathname; `/#pricing` and `/`
              // are the same document, so it never marks itself.
              active={!link.href.includes("#") && pathname.startsWith(link.href)}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2 lg:ml-0">
          {/* Hidden below md: at that width the bar is the wordmark, a CTA and
              the menu button, and a third control pushes the CTA off. It
              reappears inside the mobile sheet. */}
          <ThemeToggle className="hidden md:inline-flex" />
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild size="sm">
            <Link href="/signup">Start free</Link>
          </Button>
          <MobileNav pathname={pathname} />
        </div>
      </div>
    </header>
  );
}

/**
 * A nav item. The active one is marked by weight and colour plus a short rule
 * under the label - not a filled pill, which would be the only pill in the
 * bar and would read as a button rather than a location.
 */
function NavLink({
  href,
  active,
  children,
}: {
  href: string;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative rounded-sm px-3 py-2 text-small transition-colors duration-(--dur-micro)",
        "after:absolute after:inset-x-3 after:-bottom-0.5 after:h-px after:transition-colors",
        active
          ? "font-medium text-text after:bg-text"
          : "font-medium text-text-dim after:bg-transparent hover:bg-surface-hover hover:text-text",
      )}
    >
      {children}
    </Link>
  );
}

/**
 * The one dropdown: four solution routes, each with a line of context.
 *
 * Hover-driven, with the grace close and the single-open coordination in
 * `SiteHeader`. Click and keyboard still work through `onOpenChange`, so
 * touch and keyboard users are unaffected by the hover behaviour.
 */
function SolutionsMenu({
  open,
  active,
  onOpen,
  onScheduleClose,
  onOpenChange,
}: {
  open: boolean;
  /** True on any `/solutions/*` route, so the trigger marks itself. */
  active: boolean;
  onOpen: () => void;
  onScheduleClose: () => void;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <RadixPopover.Root open={open} onOpenChange={onOpenChange}>
      <RadixPopover.Trigger asChild>
        <button
          type="button"
          data-solutions=""
          onMouseEnter={onOpen}
          onMouseLeave={onScheduleClose}
          className={cn(
            "group relative inline-flex cursor-pointer items-center gap-1 rounded-sm px-3 py-2 text-small font-medium",
            "transition-colors duration-(--dur-micro)",
            "after:absolute after:inset-x-3 after:-bottom-0.5 after:h-px after:transition-colors",
            active
              ? "text-text after:bg-text"
              : "text-text-dim after:bg-transparent hover:bg-surface-hover hover:text-text",
          )}
        >
          Solutions
          <CaretDownIcon
            aria-hidden
            className="size-3 transition-transform duration-(--dur-base) group-data-[state=open]:rotate-180"
          />
        </button>
      </RadixPopover.Trigger>

      <RadixPopover.Portal>
        <RadixPopover.Content
          sideOffset={10}
          align="center"
          collisionPadding={16}
          data-solutions=""
          onMouseEnter={onOpen}
          onMouseLeave={onScheduleClose}
          // Don't yank focus or scroll when the menu opens under the pointer;
          // keyboard users still Tab straight into the links.
          onOpenAutoFocus={(e) => e.preventDefault()}
          // Don't return focus to the trigger on close either, or a
          // hover-opened menu leaves a focus ring sitting on it.
          onCloseAutoFocus={(e) => e.preventDefault()}
          className="menu-pop z-50 w-[min(340px,calc(100vw-32px))] origin-top overflow-hidden rounded-lg border border-rule-strong bg-surface-raised p-1.5 shadow-overlay"
        >
          <ul className="flex flex-col">
            {SOLUTIONS.map((item) => (
              <li key={item.href}>
                <RadixPopover.Close asChild>
                  <Link
                    href={item.href}
                    className="flex flex-col gap-0.5 rounded-md px-3 py-2.5 transition-colors duration-(--dur-micro) hover:bg-surface-hover"
                  >
                    <span className="text-small font-medium text-text">
                      {item.label}
                    </span>
                    <span className="text-small text-text-mute">{item.hint}</span>
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

/**
 * Full-screen sheet below `lg`.
 *
 * Grouped, not flattened: the old version concatenated every menu into one
 * undifferentiated list of twelve, which is the pattern that makes a mobile
 * menu feel like a sitemap. Solutions sit under their own label.
 */
function MobileNav({ pathname }: { pathname: string }) {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

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

          <div className="flex h-(--h-site-header) shrink-0 items-center justify-between border-b border-rule px-4">
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
              {LINKS.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    onClick={close}
                    aria-current={
                      !link.href.includes("#") && pathname.startsWith(link.href)
                        ? "page"
                        : undefined
                    }
                    className="block rounded-sm px-2 py-3 text-h3 text-text transition-colors hover:bg-surface-hover"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>

            <p className="eyebrow mt-8 px-2 text-text-mute">Solutions</p>
            <ul className="mt-2 flex flex-col gap-1">
              {SOLUTIONS.map((item) => (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={close}
                    aria-current={
                      pathname === item.href ? "page" : undefined
                    }
                    className="block rounded-sm px-2 py-2.5 text-body text-text-dim transition-colors hover:bg-surface-hover hover:text-text"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>

          <div className="flex shrink-0 flex-col gap-2 border-t border-rule p-4">
            {/* The toggle the top bar hides at this width. */}
            <div className="flex items-center justify-between pb-2">
              <span className="text-small text-text-mute">Theme</span>
              <ThemeToggle />
            </div>
            <Button asChild size="lg">
              <Link href="/signup" onClick={close}>
                Start free
              </Link>
            </Button>
            <Button asChild variant="secondary" size="lg">
              <Link href="/login" onClick={close}>
                Sign in
              </Link>
            </Button>
          </div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
