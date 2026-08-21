"use client";

import { AddressBookIcon, ProhibitIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ConnectionBanner } from "@/components/app/connection-banner";
import { TranscriptView } from "@/components/app/transcript-view";
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
import { formatAge, formatTimestamp } from "@/lib/format";
import { isE164, normalisePhone } from "@/lib/format/phone";
import { lampForOutcome } from "@/lib/lamp";
import { useAppStore } from "@/lib/app-store";
import { useOrgScopedEffect } from "@/lib/hooks/use-org-scoped-effect";
import { useSession } from "@/lib/hooks/use-session";

/**
 * One row per call, not per person.
 *
 * The page used to fold every call to a number into a single contact, which
 * answered "who have we called" but not "what came back" - and the second is
 * the question someone actually has after a run. Each record opens the full
 * call: transcript, the fields collected, what is still missing, and why triage
 * sent it where it did.
 */

export default function ContactsPage() {
  const toast = useToast();
  const session = useSession();
  const { outcomes, phase, loadingRuns } = useAppStore();
  const [tab, setTab] = useState("all");
  const [query, setQuery] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [suppressed, setSuppressed] = useState<Suppression[] | null>(null);
  const [openRecord, setOpenRecord] = useState<Outcome | null>(null);

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

  // Newest first. Records come from calls because that is the only contact
  // data the service keeps - a standalone contact book needs a store the API
  // does not have yet.
  const records = useMemo(
    () => [...outcomes].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [outcomes],
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return records;
    return records.filter((record) =>
      [
        record.contact_name,
        record.phone_masked,
        record.disposition,
        record.summary ?? "",
        ...record.missing_required_fields,
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [records, query]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-small font-bold text-text-mute">Records</p>
          <h1 className="font-display text-h2 text-text">All records</h1>
          <p className="measure text-small text-text-dim">
            Every call your agents have made, and the numbers you&apos;ve told us never
            to call again. Open a record to read the conversation and what came back.
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
          { value: "all", label: "All records", count: records.length },
          { value: "suppressed", label: "Suppression list", count: suppressed?.length ?? 0 },
        ]}
      >
        {/* ---- All contacts --------------------------------------------- */}
        <TabPanel value="all" className="flex flex-col gap-4 pt-6">
          {records.length > 0 ? (
            <div className="max-w-sm">
              <SearchInput
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onClear={() => setQuery("")}
                placeholder="Search by name, number, or outcome"
                aria-label="Search records"
              />
            </div>
          ) : null}

          {loadingRuns && records.length === 0 ? null : filtered.length === 0 ? (
            <Panel>
              <EmptyState
                icon={AddressBookIcon}
                title={query ? `No matches for “${query}”` : "No records yet"}
                body={
                  query
                    ? "Try a name, a phone number, or an outcome."
                    : "Paste a list or drop a CSV. Numbers are validated before anything is dialled."
                }
                action={
                  query ? (
                    <Button variant="secondary" onClick={() => setQuery("")}>
                      Clear search
                    </Button>
                  ) : canStart ? (
                    <Button asChild>
                      <Link href="/app/runs/new">Import CSV</Link>
                    </Button>
                  ) : undefined
                }
              />
            </Panel>
          ) : (
            <ul className="flex flex-col gap-2">
              {filtered.map((record, index) => (
                <RecordRow
                  key={`${record.run_id}-${record.phone_masked}-${record.created_at}-${index}`}
                  record={record}
                  onOpen={() => setOpenRecord(record)}
                />
              ))}
            </ul>
          )}
        </TabPanel>

        {/* ---- Suppression list ----------------------------------------- */}
        <TabPanel value="suppressed" className="flex flex-col gap-4 pt-6">
          <Panel sunken className="flex flex-col gap-2 p-4">
            <p className="text-small font-bold text-text-mute">How this works</p>
            <p className="measure text-small text-text-dim">
              Anyone who asks not to be called again is added here and is never dialled by
              any agent, ever. This is global across your whole organisation, it cannot
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

      <DialogRoot
        open={openRecord !== null}
        onOpenChange={(open) => {
          if (!open) setOpenRecord(null);
        }}
      >
        {openRecord ? (
          <Dialog
            size="full"
            title={openRecord.contact_name}
            description={`${formatTimestamp(openRecord.created_at)} · ${humaniseDisposition(openRecord.disposition)}`}
            className="flex flex-col p-0"
          >
            {/* The panel's height is fixed, so the record scrolls inside it
                rather than the dialog growing past the viewport. */}
            <div className="min-h-0 flex-1 overflow-y-auto">
              <TranscriptView outcome={openRecord} />
            </div>
          </Dialog>
        ) : null}
      </DialogRoot>

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

/** A record's disposition as a sentence rather than an enum. */
function humaniseDisposition(disposition: string): string {
  const words = disposition.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * One call, as a row.
 *
 * A whole-row button rather than a "View" link: the target is the record, and
 * anything smaller means aiming at a word on a list someone is scanning.
 */
function RecordRow({
  record,
  onOpen,
}: {
  record: Outcome;
  onOpen: () => void;
}) {
  const lamp = lampForOutcome(record);
  const missing = record.missing_required_fields ?? [];
  const collected = Object.keys(record.collected ?? {}).length;

  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="w-full cursor-pointer text-left"
      >
        <Panel className="flex flex-wrap items-center gap-3 p-3 transition-colors duration-(--dur-fast) hover:bg-surface-hover">
          <div className="flex min-w-0 flex-1 flex-col gap-0.5">
            <span className="truncate text-small font-medium text-text">
              {record.contact_name}
            </span>
            <MaskedPhone phone={record.phone_masked} />
          </div>

          <LampBadge state={lamp.state} pulse={lamp.pulse}>
            {lamp.label}
          </LampBadge>

          {/* The count someone is looking for is what is *missing*, so it wins
              the slot when there is anything in it. */}
          {missing.length > 0 ? (
            <span className="font-mono text-data tabular-nums text-lamp-flare-text">
              {missing.length} unanswered
            </span>
          ) : collected > 0 ? (
            <span className="font-mono text-data tabular-nums text-text-mute">
              {collected} {collected === 1 ? "field" : "fields"}
            </span>
          ) : null}

          <span className="font-mono text-data text-text-mute">
            {formatAge(record.created_at)}
          </span>
        </Panel>
      </button>
    </li>
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
