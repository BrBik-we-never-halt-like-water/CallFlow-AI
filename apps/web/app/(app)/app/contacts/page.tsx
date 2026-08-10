"use client";

import { AddressBookIcon, ProhibitIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ConnectionBanner } from "@/components/app/connection-banner";
import { DataTable, type Column, type SortState } from "@/components/app/data-table";
import { MaskedPhone } from "@/components/app/masked-phone";
import { LampBadge, Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogRoot } from "@/components/ui/dialog";
import { TabPanel, Tabs } from "@/components/ui/disclosure";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Input, SearchInput } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { api, type Outcome, type Suppression } from "@/lib/api";
import { formatAge, formatDuration, formatTimestamp } from "@/lib/format";
import { isE164, normalisePhone } from "@/lib/format/phone";
import { lampForOutcome } from "@/lib/lamp";
import { useAppStore } from "@/lib/app-store";
import { useOrgScopedEffect } from "@/lib/hooks/use-org-scoped-effect";
import { useSession } from "@/lib/hooks/use-session";

interface ContactRecord {
  name: string;
  phoneMasked: string;
  calls: Outcome[];
  lastCalled: string;
}

export default function ContactsPage() {
  const toast = useToast();
  const session = useSession();
  const { outcomes, phase, loadingRuns } = useAppStore();
  const [tab, setTab] = useState("all");
  const [query, setQuery] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [suppressed, setSuppressed] = useState<Suppression[] | null>(null);
  const [sort, setSort] = useState<SortState>({ id: "lastCalled", dir: "desc" });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const profile = session.status === "signed-in" ? session.profile : null;
  const canAdd = profile?.permissions.includes("suppressions:add") ?? false;
  const canRemove = profile?.permissions.includes("suppressions:remove") ?? false;
  const canStart = profile?.permissions.includes("runs:start") ?? false;

  function loadSuppressions() {
    api
      .listSuppressions()
      .then(setSuppressed)
      .catch(() => toast({ tone: "error", title: "Couldn't load the suppression list" }));
  }

  useOrgScopedEffect(() => {
    loadSuppressions();
  });

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
    // Newest call first within each contact - `calls[0]` is what the status,
    // duration, and call-time columns below all read as "the latest call",
    // so it has to actually be sorted rather than just appended in arrival order.
    return [...map.values()]
      .map((contact) => ({
        ...contact,
        calls: [...contact.calls].sort((a, b) =>
          b.created_at.localeCompare(a.created_at),
        ),
      }))
      .sort((a, b) => b.lastCalled.localeCompare(a.lastCalled));
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

  /**
   * Sorting and pagination are done here rather than server-side because contacts
   * are derived client-side from the whole outcomes list already in memory - same
   * reasoning as `/app/runs`, whose DataTable this mirrors.
   */
  const sorted = useMemo(() => {
    const list = [...filtered];
    list.sort((a, b) => {
      const dir = sort.dir === "asc" ? 1 : -1;
      switch (sort.id) {
        case "name":
          return a.name.localeCompare(b.name) * dir;
        case "calls":
          return (a.calls.length - b.calls.length) * dir;
        case "duration": {
          const da = a.calls[0]?.duration_seconds ?? -1;
          const db = b.calls[0]?.duration_seconds ?? -1;
          return (da - db) * dir;
        }
        default:
          return a.lastCalled.localeCompare(b.lastCalled) * dir;
      }
    });
    return list;
  }, [filtered, sort]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const paged = useMemo(
    () => sorted.slice((safePage - 1) * pageSize, safePage * pageSize),
    [sorted, safePage, pageSize],
  );

  const columns: Column<ContactRecord>[] = [
    {
      id: "name",
      header: "Name",
      sortable: true,
      cell: (contact) => (
        <span className="block truncate text-text">{contact.name}</span>
      ),
      value: (contact) => contact.name,
    },
    {
      id: "phone",
      header: "Number",
      cell: (contact) => <MaskedPhone phone={contact.phoneMasked} />,
      value: (contact) => contact.phoneMasked,
    },
    {
      id: "status",
      header: "Status",
      cell: (contact) => {
        const lamp = lampForOutcome(contact.calls[0]);
        return (
          <LampBadge state={lamp.state} pulse={lamp.pulse}>
            {lamp.label}
          </LampBadge>
        );
      },
      value: (contact) => lampForOutcome(contact.calls[0]).label,
    },
    {
      id: "calls",
      header: "Calls",
      align: "right",
      mono: true,
      sortable: true,
      cell: (contact) => contact.calls.length,
      value: (contact) => contact.calls.length,
    },
    {
      id: "duration",
      header: "Duration",
      align: "right",
      mono: true,
      sortable: true,
      cell: (contact) => formatDuration(contact.calls[0]?.duration_seconds),
      value: (contact) => contact.calls[0]?.duration_seconds ?? null,
    },
    {
      id: "callTime",
      header: "Call time",
      align: "right",
      mono: true,
      cell: (contact) => formatTimestamp(contact.lastCalled),
      value: (contact) => contact.lastCalled,
    },
    {
      id: "lastCalled",
      header: "Last called",
      align: "right",
      mono: true,
      sortable: true,
      cell: (contact) => formatAge(contact.lastCalled),
      value: (contact) => contact.lastCalled,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-small font-bold text-text-mute">Contacts</p>
          <h1 className="font-display text-h2 text-text">Who you&apos;ve called</h1>
          <p className="measure text-small text-text-dim">
            Everyone your campaigns have dialled, and the numbers you&apos;ve told us never
            to call again.
          </p>
        </div>
        <div className="flex gap-2">
          {canAdd ? (
            <Button variant="secondary" onClick={() => setAddOpen(true)}>
              Suppress a number
            </Button>
          ) : null}
          {canStart ? (
            <Button asChild>
              <Link href="/app/runs/new">Import CSV</Link>
            </Button>
          ) : null}
        </div>
      </div>

      <ConnectionBanner phase={phase} />

      <Tabs
        value={tab}
        onValueChange={setTab}
        tabs={[
          { value: "all", label: "All contacts", count: contacts.length },
          { value: "suppressed", label: "Suppression list", count: suppressed?.length ?? 0 },
        ]}
      >
        {/* ---- All contacts --------------------------------------------- */}
        <TabPanel value="all" className="flex flex-col gap-4 pt-6">
          <DataTable
            caption="Contacts, derived from call history, with call count, duration, and timing."
            columns={columns}
            rows={paged}
            rowKey={(contact) => `${contact.name}-${contact.phoneMasked}`}
            loading={loadingRuns && contacts.length === 0}
            sort={sort}
            onSortChange={setSort}
            page={safePage}
            pageSize={pageSize}
            totalRows={sorted.length}
            onPageChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
            exportFileName="callflow-contacts"
            toolbar={
              contacts.length > 0 ? (
                <div className="max-w-sm">
                  <SearchInput
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onClear={() => setQuery("")}
                    placeholder="Search by name or number"
                    aria-label="Search contacts"
                  />
                </div>
              ) : null
            }
            mobileCard={(contact) => {
              const lamp = lampForOutcome(contact.calls[0]);
              return (
                <div className="flex flex-col gap-1.5">
                  <span className="min-w-0 flex-1 truncate text-small font-medium text-text">
                    {contact.name}
                  </span>
                  <MaskedPhone phone={contact.phoneMasked} />
                  <div className="flex flex-wrap items-center gap-3">
                    <LampBadge state={lamp.state} pulse={lamp.pulse}>
                      {lamp.label}
                    </LampBadge>
                    <span className="font-mono text-data tabular-nums text-text-mute">
                      {contact.calls.length}{" "}
                      {contact.calls.length === 1 ? "call" : "calls"}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="font-mono text-data tabular-nums text-text-mute">
                      {formatDuration(contact.calls[0]?.duration_seconds)}
                    </span>
                    <span className="font-mono text-data text-text-mute">
                      {formatTimestamp(contact.lastCalled)}
                    </span>
                  </div>
                </div>
              );
            }}
            empty={
              contacts.length === 0 ? (
                <EmptyState
                  icon={AddressBookIcon}
                  title="No contacts yet"
                  body="Paste a list or drop a CSV. Numbers are validated before anything is dialled."
                  action={
                    canStart ? (
                      <Button asChild>
                        <Link href="/app/runs/new">Import CSV</Link>
                      </Button>
                    ) : undefined
                  }
                />
              ) : (
                <EmptyState
                  icon={AddressBookIcon}
                  title={query ? `No matches for "${query}"` : "No contacts match this filter"}
                  body="Try a name, a phone number, or a campaign."
                  action={
                    query ? (
                      <Button variant="secondary" onClick={() => setQuery("")}>
                        Clear search
                      </Button>
                    ) : undefined
                  }
                />
              )
            }
          />
        </TabPanel>

        {/* ---- Suppression list ----------------------------------------- */}
        <TabPanel value="suppressed" className="flex flex-col gap-4 pt-6">
          <Panel sunken className="flex flex-col gap-2 p-4">
            <p className="text-small font-bold text-text-mute">How this works</p>
            <p className="measure text-small text-text-dim">
              Anyone who asks not to be called again is added here and is never dialled by
              any campaign, ever. This is global across your whole organisation, it cannot
              be overridden from a run, and re-importing a CSV containing a suppressed
              number does not bring it back. Only an owner can remove a number.
            </p>
          </Panel>

          {suppressed === null ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : suppressed.length === 0 ? (
            <Panel>
              <EmptyState
                icon={ProhibitIcon}
                title="No suppressed numbers"
                body="Add one by hand with the button below, or wait for someone to opt out during a call."
                action={
                  canAdd ? (
                    <Button variant="secondary" onClick={() => setAddOpen(true)}>
                      Suppress a number
                    </Button>
                  ) : undefined
                }
              />
            </Panel>
          ) : (
            <ul className="flex flex-col gap-2">
              {suppressed.map((entry) => (
                <SuppressionRow
                  key={entry.id}
                  entry={entry}
                  canRemove={canRemove}
                  onRemoved={loadSuppressions}
                />
              ))}
            </ul>
          )}
        </TabPanel>
      </Tabs>

      <SuppressDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onAdded={() => {
          toast({ tone: "success", title: "Number suppressed" });
          loadSuppressions();
        }}
      />
    </div>
  );
}

function SuppressionRow({
  entry,
  canRemove,
  onRemoved,
}: {
  entry: Suppression;
  canRemove: boolean;
  onRemoved: () => void;
}) {
  const toast = useToast();
  const [removing, setRemoving] = useState(false);

  async function remove() {
    setRemoving(true);
    try {
      await api.removeSuppression(entry.id);
      toast({ tone: "warning", title: "Number un-suppressed" });
      onRemoved();
    } catch (error) {
      toast({
        tone: "error",
        title: "Couldn't un-suppress that number",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setRemoving(false);
    }
  }

  return (
    <li>
      <Panel className="flex flex-wrap items-center gap-3 p-3">
        <span className="min-w-0 flex-1 font-mono text-data tabular-nums text-text-mute line-through">
          {entry.phone_masked}
        </span>
        <Tag>Suppressed</Tag>
        <span className="font-mono text-data text-text-mute">
          {entry.reason ||
            (entry.source === "opt_out"
              ? "opted out"
              : entry.source === "imported"
                ? "imported"
                : entry.source === "api"
                  ? "via API"
                  : "added by hand")}
        </span>
        <span className="font-mono text-data text-text-mute">
          {formatTimestamp(entry.suppressed_at)}
        </span>
        {canRemove ? (
          <Button variant="ghost" size="sm" onClick={remove} loading={removing}>
            Remove
          </Button>
        ) : null}
      </Panel>
    </li>
  );
}

function SuppressDialog({
  open,
  onOpenChange,
  onAdded,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdded: () => void;
}) {
  const toast = useToast();
  const [phone, setPhone] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit() {
    const normalised = normalisePhone(phone);
    if (!isE164(normalised)) {
      setError("That number isn't valid. Use international format, like +919876543210.");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await api.addSuppression(normalised, note.trim() || undefined);
      setPhone("");
      setNote("");
      onOpenChange(false);
      onAdded();
    } catch (error) {
      toast({
        tone: "error",
        title: "Couldn't suppress that number",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <DialogRoot open={open} onOpenChange={onOpenChange}>
      <Dialog
        title="Suppress a number"
        description="Once you confirm, only an owner can remove this number again."
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={submit} loading={saving}>
              Suppress this number
            </Button>
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
