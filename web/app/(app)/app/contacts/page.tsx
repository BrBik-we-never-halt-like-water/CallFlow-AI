"use client";

import { AddressBookIcon, ProhibitIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ConnectionBanner } from "@/components/app/connection-banner";
import { MaskedPhone } from "@/components/app/masked-phone";
import { LampBadge, Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogRoot } from "@/components/ui/dialog";
import { TabPanel, Tabs } from "@/components/ui/disclosure";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Input, SearchInput } from "@/components/ui/input";
import { Eyebrow, Panel } from "@/components/ui/panel";
import { useToast } from "@/components/ui/toast";
import type { Outcome } from "@/lib/api";
import { formatAge, formatTimestamp } from "@/lib/format";
import { isE164, normalisePhone } from "@/lib/format/phone";
import { lampForOutcome } from "@/lib/lamp";
import { useStoredJson } from "@/lib/hooks/use-external-store";
import {
  addSuppressed,
  NO_SUPPRESSED,
  removeSuppressed,
  SUPPRESSION_KEY,
  type SuppressedNumber,
} from "@/lib/suppression";
import { useAppStore } from "@/lib/app-store";

interface ContactRecord {
  name: string;
  phoneMasked: string;
  calls: Outcome[];
  lastCalled: string;
}

export default function ContactsPage() {
  const toast = useToast();
  const { outcomes, phase, wakeSeconds, loadingRuns } = useAppStore();
  const [tab, setTab] = useState("all");
  const [query, setQuery] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  // Subscribed rather than read-on-mount, so the list is correct on first paint and
  // stays in sync if another tab changes it.
  const [suppressed, setSuppressed] = useStoredJson<SuppressedNumber[]>(
    SUPPRESSION_KEY,
    NO_SUPPRESSED,
  );

  /**
   * Contacts are derived from calls, because that is the only contact data the service
   * keeps. A standalone contact book needs a store the API does not have yet.
   */
  const contacts = useMemo<ContactRecord[]>(() => {
    const map = new Map<string, ContactRecord>();
    for (const outcome of outcomes) {
      const key = `${outcome.contact_name}|${outcome.phone_masked}`;
      const existing = map.get(key);
      if (existing) {
        existing.calls.push(outcome);
        if (outcome.created_at > existing.lastCalled) existing.lastCalled = outcome.created_at;
      } else {
        map.set(key, {
          name: outcome.contact_name,
          phoneMasked: outcome.phone_masked,
          calls: [outcome],
          lastCalled: outcome.created_at,
        });
      }
    }
    return [...map.values()].sort((a, b) => b.lastCalled.localeCompare(a.lastCalled));
  }, [outcomes]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return contacts;
    return contacts.filter(
      (contact) =>
        contact.name.toLowerCase().includes(needle) ||
        contact.phoneMasked.toLowerCase().includes(needle),
    );
  }, [contacts, query]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <Eyebrow>Contacts</Eyebrow>
          <h1 className="font-display text-h2 text-text">Who you&apos;ve called</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setAddOpen(true)}>
            Suppress a number
          </Button>
          <Button asChild>
            <Link href="/app/runs/new">Import CSV</Link>
          </Button>
        </div>
      </div>

      <ConnectionBanner phase={phase} wakeSeconds={wakeSeconds} />

      <Tabs
        value={tab}
        onValueChange={setTab}
        tabs={[
          { value: "all", label: "All contacts", count: contacts.length },
          { value: "suppressed", label: "Suppression list", count: suppressed.length },
        ]}
      >
        {/* ---- All contacts --------------------------------------------- */}
        <TabPanel value="all" className="flex flex-col gap-4 pt-6">
          {contacts.length > 0 ? (
            <div className="max-w-sm">
              <SearchInput
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onClear={() => setQuery("")}
                placeholder="Search by name or number"
                aria-label="Search contacts"
              />
            </div>
          ) : null}

          {loadingRuns && contacts.length === 0 ? null : filtered.length === 0 ? (
            <Panel>
              <EmptyState
                icon={AddressBookIcon}
                title={query ? `No matches for “${query}”` : "No contacts yet"}
                body={
                  query
                    ? "Try a name, a phone number, or a campaign."
                    : "Paste a list or drop a CSV. Numbers are validated before anything is dialled."
                }
                action={
                  query ? (
                    <Button variant="secondary" onClick={() => setQuery("")}>
                      Clear search
                    </Button>
                  ) : (
                    <Button asChild>
                      <Link href="/app/runs/new">Import CSV</Link>
                    </Button>
                  )
                }
              />
            </Panel>
          ) : (
            <ul className="flex flex-col gap-2">
              {filtered.map((contact) => {
                const latest = contact.calls[0];
                const lamp = lampForOutcome(latest);
                return (
                  <li key={`${contact.name}-${contact.phoneMasked}`}>
                    <Panel className="flex flex-wrap items-center gap-3 p-3">
                      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <span className="truncate text-small font-medium text-text">
                          {contact.name}
                        </span>
                        <MaskedPhone phone={contact.phoneMasked} />
                      </div>

                      <LampBadge state={lamp.state} pulse={lamp.pulse}>
                        {lamp.label}
                      </LampBadge>

                      <span className="font-mono text-data tabular-nums text-text-mute">
                        {contact.calls.length} {contact.calls.length === 1 ? "call" : "calls"}
                      </span>
                      <span className="font-mono text-data text-text-mute">
                        {formatAge(contact.lastCalled)}
                      </span>
                    </Panel>
                  </li>
                );
              })}
            </ul>
          )}
        </TabPanel>

        {/* ---- Suppression list ----------------------------------------- */}
        <TabPanel value="suppressed" className="flex flex-col gap-4 pt-6">
          <Panel sunken className="flex flex-col gap-2 p-4">
            <Eyebrow>How this works</Eyebrow>
            <p className="measure text-small text-text-dim">
              Anyone who asks not to be called again is added here automatically and is
              never dialled by any campaign, ever. It is not per-campaign, it cannot be
              overridden from a run, and re-importing a CSV containing a suppressed number
              does not bring it back.
            </p>
            <p className="measure text-small text-lamp-brass-text">
              On this deployment the list is held in your browser only — the service has no
              suppression endpoint yet, so it will not apply on another device or to
              someone else on your team.
            </p>
          </Panel>

          {suppressed.length === 0 ? (
            <Panel>
              <EmptyState
                icon={ProhibitIcon}
                title="No suppressed numbers"
                body="Anyone who asks not to be called again is added here automatically and is never dialled by any campaign."
                action={
                  <Button variant="secondary" onClick={() => setAddOpen(true)}>
                    Suppress a number
                  </Button>
                }
              />
            </Panel>
          ) : (
            <ul className="flex flex-col gap-2">
              {suppressed.map((entry) => (
                <li key={entry.phone}>
                  <Panel className="flex flex-wrap items-center gap-3 p-3">
                    <span className="min-w-0 flex-1 font-mono text-data tabular-nums text-text-mute line-through">
                      <MaskedPhone phone={entry.phone} />
                    </span>
                    <Tag>Suppressed</Tag>
                    <span className="font-mono text-data text-text-mute">
                      {entry.reason === "opted_out"
                        ? "opted out"
                        : entry.reason === "imported"
                          ? "imported"
                          : "added by hand"}
                    </span>
                    <span className="font-mono text-data text-text-mute">
                      {formatTimestamp(entry.addedAt)}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setSuppressed(removeSuppressed(suppressed, entry.phone));
                        toast({ tone: "warning", title: "Number un-suppressed" });
                      }}
                    >
                      Remove
                    </Button>
                  </Panel>
                </li>
              ))}
            </ul>
          )}
        </TabPanel>
      </Tabs>

      <SuppressDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onAdd={(phone, note) => {
          setSuppressed(addSuppressed(suppressed, phone, "manual", note));
          toast({ tone: "success", title: "Number suppressed" });
        }}
      />
    </div>
  );
}

function SuppressDialog({
  open,
  onOpenChange,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdd: (phone: string, note?: string) => void;
}) {
  const [phone, setPhone] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit() {
    const normalised = normalisePhone(phone);
    if (!isE164(normalised)) {
      setError("That number isn't valid. Use international format, like +919876543210.");
      return;
    }
    setError(null);
    onAdd(normalised, note.trim() || undefined);
    setPhone("");
    setNote("");
    onOpenChange(false);
  }

  return (
    <DialogRoot open={open} onOpenChange={onOpenChange}>
      <Dialog
        title="Suppress a number"
        description="It will never be dialled by any campaign. This cannot be overridden from a run."
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={submit}>Suppress this number</Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label="Phone number" error={error} required>
            <Input
              variant="phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+919876543210"
              autoFocus
            />
          </Field>
          <Field label="Why" help="Optional, but useful when someone asks later.">
            <Input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Asked not to be contacted again"
            />
          </Field>
        </div>
      </Dialog>
    </DialogRoot>
  );
}
