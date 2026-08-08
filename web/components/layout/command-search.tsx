"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { MagnifyingGlassIcon } from "@phosphor-icons/react/dist/ssr";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { Lamp } from "@/components/brand/lamp";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { maskPhone } from "@/lib/format/phone";
import { lampForOutcome } from "@/lib/lamp";
import { useAppStore } from "@/lib/app-store";
import { NAV_ITEMS } from "./app-nav";

interface Result {
  id: string;
  label: string;
  detail: string;
  href: string;
  lamp?: React.ReactNode;
}

/**
 * Global search, opened with ⌘K or Ctrl+K.
 *
 * Searches destinations, campaigns, and contacts already called. Contact matching
 * runs against the full number so an operator can paste one in, but the number is
 * only ever *displayed* masked   the search is a lookup, not a way around masking.
 */
export function CommandSearch() {
  const router = useRouter();
  const { campaigns, outcomes } = useAppStore();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const results = useMemo<Result[]>(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return NAV_ITEMS.map((item) => ({
        id: item.href,
        label: item.label,
        detail: "Go to",
        href: item.href,
      }));
    }

    const destinations: Result[] = NAV_ITEMS.filter((item) =>
      item.label.toLowerCase().includes(needle),
    ).map((item) => ({ id: item.href, label: item.label, detail: "Go to", href: item.href }));

    const campaignHits: Result[] = campaigns
      .filter((campaign) => campaign.name.toLowerCase().includes(needle))
      .map((campaign) => ({
        id: `campaign-${campaign.id}`,
        label: campaign.name,
        detail: "Campaign",
        href: `/app/campaigns/${campaign.id}`,
      }));

    const seen = new Set<string>();
    const contactHits: Result[] = [];
    for (const outcome of outcomes) {
      const key = `${outcome.contact_name}-${outcome.phone_masked}`;
      if (seen.has(key)) continue;
      const matches =
        outcome.contact_name.toLowerCase().includes(needle) ||
        outcome.phone_masked.toLowerCase().includes(needle);
      if (!matches) continue;
      seen.add(key);
      const lamp = lampForOutcome(outcome);
      contactHits.push({
        id: key,
        label: outcome.contact_name,
        detail: maskPhone(outcome.phone_masked),
        href: outcome.run_id ? `/app/runs/${outcome.run_id}` : "/app/runs",
        lamp: <Lamp state={lamp.state} size="sm" pulse={lamp.pulse} />,
      });
      if (contactHits.length >= 8) break;
    }

    return [...destinations, ...campaignHits, ...contactHits];
  }, [query, campaigns, outcomes]);

  function go(href: string) {
    setOpen(false);
    setQuery("");
    router.push(href);
  }

  return (
    <RadixDialog.Root open={open} onOpenChange={setOpen}>
      <RadixDialog.Trigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex h-9 cursor-pointer items-center gap-2 rounded-sm border border-rule bg-surface-sunken px-2.5",
            "text-small text-text-mute transition-colors hover:text-text",
          )}
        >
          <MagnifyingGlassIcon aria-hidden className="size-4" />
          <span className="hidden sm:inline">Search</span>
          <kbd className="hidden font-mono text-label text-text-mute sm:inline">⌘K</kbd>
        </button>
      </RadixDialog.Trigger>

      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-50 bg-[color-mix(in_oklab,var(--text)_45%,transparent)]" />
        <RadixDialog.Content className="fixed left-1/2 top-[12vh] z-50 w-[calc(100vw-32px)] max-w-lg -translate-x-1/2 overflow-hidden rounded-md border border-rule-strong bg-surface-raised shadow-overlay">
          <RadixDialog.Title className="sr-only">Search</RadixDialog.Title>

          <div className="border-b border-rule p-3">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search campaigns, contacts, or pages…"
              autoFocus
              aria-label="Search"
            />
          </div>

          {results.length === 0 ? (
            <EmptyState
              title={`No matches for “${query}”`}
              body="Try a name, a phone number, or a campaign."
            />
          ) : (
            <ul className="max-h-80 overflow-y-auto p-1.5">
              {results.map((result) => (
                <li key={result.id}>
                  <button
                    type="button"
                    onClick={() => go(result.href)}
                    className="flex w-full cursor-pointer items-center gap-2.5 rounded-sm px-2.5 py-2 text-left transition-colors hover:bg-surface-hover"
                  >
                    {result.lamp ?? null}
                    <span className="min-w-0 flex-1 truncate text-small text-text">
                      {result.label}
                    </span>
                    <span className="shrink-0 font-mono text-data text-text-mute">
                      {result.detail}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
