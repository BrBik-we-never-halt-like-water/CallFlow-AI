"use client";

import { useEffect, useState } from "react";
import { api, type Campaign, type CampaignField, type FieldType } from "@/lib/api";
import { CheckIcon, CloseIcon, PlusIcon, TrashIcon } from "./icons";

const FIELD_TYPES: FieldType[] = ["string", "boolean", "integer", "number"];

/** Placeholders the orchestrator can fill. Must match Contact.context keys
 *  produced by lib/contacts.ts — a typo here renders as an empty string. */
const PLACEHOLDERS = [
  { token: "{name}", desc: "Contact's name" },
  { token: "{enquiry_note}", desc: "The note column" },
];

const BLANK_FIELD: CampaignField = { key: "", type: "string", description: "" };

const TEMPLATE = `You are CallFlow AI, calling {name} about ...

Open by greeting them by name and confirming this is a good time to talk. If it
is not, apologise, ask when to call back, and end politely.

Your objective is to ... Find out, conversationally:
  - ...
  - ...

Known context: {enquiry_note}

If they sound annoyed, do not push. Apologise once, offer to have a human
colleague call them, and close warmly.

Thank them by name and end the call.`;

const PRESETS = [
  {
    id: "order",
    label: "Order follow-up",
    name: "Order follow-up",
    goal: `You are CallFlow AI calling {name} about their recent order.

Greet them by name and confirm this is a good time. Ask whether the order
arrived on time and whether they are happy with it. If something went wrong,
apologise, capture what happened, and tell them a colleague will follow up.

Known context: {enquiry_note}

Do not offer refunds or discounts — that is a human decision. Thank them and
close warmly.`,
    fields: [
      { key: "arrived_on_time", type: "boolean" as FieldType, description: "Did the order arrive on time" },
      { key: "satisfaction", type: "integer" as FieldType, description: "Satisfaction rating from 1 to 5" },
      { key: "issue", type: "string" as FieldType, description: "What went wrong, if anything" },
    ],
  },
  {
    id: "renewal",
    label: "Renewal reminder",
    name: "Renewal reminder",
    goal: `You are CallFlow AI calling {name} about their upcoming subscription renewal.

Greet them by name and confirm this is a good time. Remind them the renewal is
approaching and ask whether they intend to continue. If they are unsure, ask
what would help them decide. If they want to cancel, accept it gracefully
without pushing back.

Known context: {enquiry_note}

Do not quote new pricing — a colleague will follow up with options. Thank them
and close warmly.`,
    fields: [
      { key: "will_renew", type: "boolean" as FieldType, description: "Do they intend to renew" },
      { key: "blocker", type: "string" as FieldType, description: "What is stopping them, if anything" },
    ],
  },
];

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (c: Campaign) => void;
}

export default function CampaignBuilder({ open, onClose, onCreated }: Props) {
  const [presetId, setPresetId] = useState<string>("blank");
  const [name, setName] = useState("");
  const [goal, setGoal] = useState(TEMPLATE);
  const [fields, setFields] = useState<CampaignField[]>([{ ...BLANK_FIELD }]);
  const [region, setRegion] = useState("IN");
  const [language, setLanguage] = useState("en");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  function applyPreset(p: (typeof PRESETS)[number]) {
    setPresetId(p.id);
    setName(p.name);
    setGoal(p.goal);
    setFields([...p.fields, { ...BLANK_FIELD }]);
    setError(null);
  }

  function applyBlank() {
    setPresetId("blank");
    setName("");
    setGoal(TEMPLATE);
    setFields([{ ...BLANK_FIELD }]);
    setError(null);
  }

  function insertToken(token: string) {
    setGoal((g) => `${g}${g.endsWith("\n") || !g ? "" : " "}${token}`);
  }

  const goalLength = goal.trim().length;
  const goalTooShort = goalLength < 40;
  const hasName = goal.includes("{name}");
  const stillHasEllipsis = goal.includes("...");
  const namedFields = fields.filter((f) => f.key.trim());
  const canSave = name.trim().length >= 2 && !goalTooShort && !saving;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const created = await api.createCampaign({
        name: name.trim(),
        goal_template: goal.trim(),
        extra_fields: namedFields.map((f) => ({
          ...f,
          key: f.key.trim(),
          description: f.description.trim(),
        })),
        region: region || null,
        language: language || null,
      });
      onCreated(created);
      onClose();
      applyBlank();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[60] overflow-y-auto bg-slate-900/30 backdrop-blur-sm"
      onClick={onClose}
    >
      <div className="flex min-h-full items-start justify-center p-4 sm:p-8">
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Create campaign"
          onClick={(e) => e.stopPropagation()}
          className="card my-auto w-full max-w-3xl shadow-2xl"
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-4 border-b border-[var(--color-border)] px-6 py-4">
            <div>
              <h2 className="text-base font-semibold text-[var(--color-ink)]">
                New campaign
              </h2>
              <p className="mt-0.5 text-xs text-[var(--color-muted)]">
                A goal the agent pursues, plus the fields to extract from the call.
              </p>
            </div>
            <button
              onClick={onClose}
              aria-label="Close"
              className="-mr-2 -mt-1 cursor-pointer rounded-lg p-2 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-subtle)] hover:text-[var(--color-ink)]"
            >
              <CloseIcon className="h-4 w-4" />
            </button>
          </div>

          <div className="max-h-[70vh] space-y-6 overflow-y-auto px-6 py-5">
            {/* Presets */}
            <section>
              <span className="mb-2.5 block text-[11px] font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                Start from
              </span>
              <div className="grid gap-2 sm:grid-cols-3">
                {PRESETS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => applyPreset(p)}
                    className={`cursor-pointer rounded-lg border px-3 py-2.5 text-left transition-colors ${
                      presetId === p.id
                        ? "border-[var(--color-brand)] bg-[var(--color-brand-soft)]"
                        : "border-[var(--color-border)] hover:border-slate-300 hover:bg-[var(--color-subtle)]"
                    }`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span
                        className={`text-xs font-medium ${
                          presetId === p.id
                            ? "text-[var(--color-brand)]"
                            : "text-[var(--color-ink)]"
                        }`}
                      >
                        {p.label}
                      </span>
                      {presetId === p.id && (
                        <CheckIcon className="h-3.5 w-3.5 text-[var(--color-brand)]" />
                      )}
                    </span>
                    <span className="mt-0.5 block text-[10px] text-[var(--color-muted)]">
                      {p.fields.length} fields
                    </span>
                  </button>
                ))}
                <button
                  onClick={applyBlank}
                  className={`cursor-pointer rounded-lg border border-dashed px-3 py-2.5 text-left transition-colors ${
                    presetId === "blank"
                      ? "border-[var(--color-brand)] bg-[var(--color-brand-soft)]"
                      : "border-[var(--color-border)] hover:border-slate-300"
                  }`}
                >
                  <span
                    className={`text-xs font-medium ${
                      presetId === "blank"
                        ? "text-[var(--color-brand)]"
                        : "text-[var(--color-ink)]"
                    }`}
                  >
                    Blank
                  </span>
                  <span className="mt-0.5 block text-[10px] text-[var(--color-muted)]">
                    Start fresh
                  </span>
                </button>
              </div>
            </section>

            {/* Name + locale */}
            <section className="grid gap-3 sm:grid-cols-[1fr_92px_92px]">
              <Field label="Campaign name" required>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Order follow-up"
                  className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-sm outline-none transition focus:border-[var(--color-brand)] focus:ring-2 focus:ring-indigo-100"
                />
              </Field>
              <Field label="Region">
                <input
                  value={region}
                  onChange={(e) => setRegion(e.target.value.toUpperCase().slice(0, 2))}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-center font-mono text-sm outline-none transition focus:border-[var(--color-brand)] focus:ring-2 focus:ring-indigo-100"
                />
              </Field>
              <Field label="Language">
                <input
                  value={language}
                  onChange={(e) => setLanguage(e.target.value.toLowerCase().slice(0, 5))}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-white px-3 py-2 text-center font-mono text-sm outline-none transition focus:border-[var(--color-brand)] focus:ring-2 focus:ring-indigo-100"
                />
              </Field>
            </section>

            {/* Goal */}
            <section>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-medium text-[var(--color-ink)]">
                  Goal — what the agent should do
                  <span className="ml-1 text-[var(--color-brand)]">*</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="text-[10px] text-[var(--color-muted)]">Insert:</span>
                  {PLACEHOLDERS.map((p) => (
                    <button
                      key={p.token}
                      onClick={() => insertToken(p.token)}
                      title={p.desc}
                      className="cursor-pointer rounded border border-[var(--color-border)] bg-[var(--color-subtle)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-brand)] transition-colors hover:border-[var(--color-brand)] hover:bg-[var(--color-brand-soft)]"
                    >
                      {p.token}
                    </button>
                  ))}
                </span>
              </div>

              <textarea
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                rows={12}
                spellCheck={false}
                className="w-full resize-y rounded-lg border border-[var(--color-border)] bg-white px-3.5 py-3 font-mono text-[11px] leading-[1.7] outline-none transition focus:border-[var(--color-brand)] focus:ring-2 focus:ring-indigo-100"
              />

              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px]">
                <span
                  className={`nums ${
                    goalTooShort ? "font-medium text-amber-600" : "text-[var(--color-muted)]"
                  }`}
                >
                  {goalLength} characters
                  {goalTooShort && " — need 40+"}
                </span>
                {!hasName && (
                  <Hint tone="warn">
                    No <code className="font-mono">{"{name}"}</code> — the agent
                    won&apos;t greet them
                  </Hint>
                )}
                {stillHasEllipsis && (
                  <Hint tone="warn">Replace the “…” placeholders</Hint>
                )}
                {!goalTooShort && hasName && !stillHasEllipsis && (
                  <Hint tone="ok">Ready to save</Hint>
                )}
              </div>
            </section>

            {/* Extraction fields */}
            <section>
              <div className="mb-1 flex items-baseline justify-between">
                <span className="text-xs font-medium text-[var(--color-ink)]">
                  Extract from the call
                </span>
                <span className="nums text-[11px] text-[var(--color-muted)]">
                  {namedFields.length} custom
                </span>
              </div>
              <p className="mb-2.5 text-[11px] leading-relaxed text-[var(--color-muted)]">
                CALL-E returns these as typed JSON. Sentiment, frustration, and
                opt-out are always included.
              </p>

              <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
                <div className="grid grid-cols-[1fr_96px_1.5fr_32px] border-b border-[var(--color-border)] bg-[var(--color-subtle)] px-3 py-2 text-[10px] font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                  <span>Field</span>
                  <span>Type</span>
                  <span>What to capture</span>
                  <span />
                </div>
                {fields.map((f, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-[1fr_96px_1.5fr_32px] items-center border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-subtle)]"
                  >
                    <input
                      value={f.key}
                      onChange={(e) =>
                        setFields(
                          fields.map((x, j) => (j === i ? { ...x, key: e.target.value } : x)),
                        )
                      }
                      placeholder="budget"
                      className="w-full bg-transparent px-3 py-2 font-mono text-xs outline-none placeholder:text-slate-300 focus:bg-white"
                    />
                    <select
                      value={f.type}
                      onChange={(e) =>
                        setFields(
                          fields.map((x, j) =>
                            j === i ? { ...x, type: e.target.value as FieldType } : x,
                          ),
                        )
                      }
                      className="w-full cursor-pointer bg-transparent px-2 py-2 text-xs outline-none focus:bg-white"
                    >
                      {FIELD_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                    <input
                      value={f.description}
                      onChange={(e) =>
                        setFields(
                          fields.map((x, j) =>
                            j === i ? { ...x, description: e.target.value } : x,
                          ),
                        )
                      }
                      placeholder="Their stated budget in INR"
                      className="w-full bg-transparent px-3 py-2 text-xs outline-none placeholder:text-slate-300 focus:bg-white"
                    />
                    <button
                      onClick={() => setFields(fields.filter((_, j) => j !== i))}
                      aria-label={`Remove field ${i + 1}`}
                      className="flex h-full cursor-pointer items-center justify-center text-slate-300 transition-colors hover:text-red-500"
                    >
                      <TrashIcon className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
                <button
                  onClick={() => setFields([...fields, { ...BLANK_FIELD }])}
                  className="flex w-full cursor-pointer items-center justify-center gap-1.5 border-t border-[var(--color-border)] bg-[var(--color-subtle)] py-2 text-[11px] font-medium text-[var(--color-brand)] transition-colors hover:bg-[var(--color-brand-soft)]"
                >
                  <PlusIcon className="h-3 w-3" />
                  Add field
                </button>
              </div>
            </section>

            {error && (
              <p className="rounded-lg bg-red-50 px-3.5 py-2.5 text-xs leading-relaxed text-red-700 ring-1 ring-inset ring-red-200">
                {error}
              </p>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between gap-3 border-t border-[var(--color-border)] bg-[var(--color-subtle)] px-6 py-4">
            <span className="text-[11px] text-[var(--color-muted)]">
              Press <kbd className="font-mono">Esc</kbd> to cancel
            </span>
            <div className="flex gap-2">
              <button
                onClick={onClose}
                className="cursor-pointer rounded-lg border border-[var(--color-border)] bg-white px-4 py-2 text-sm font-medium text-[var(--color-ink)] transition-colors hover:bg-[var(--color-subtle)]"
              >
                Cancel
              </button>
              <button
                onClick={save}
                disabled={!canSave}
                className="brand-gradient cursor-pointer rounded-lg px-5 py-2 text-sm font-medium text-white shadow-sm transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:brightness-100"
              >
                {saving ? "Creating…" : "Create campaign"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-[var(--color-ink)]">
        {label}
        {required && <span className="ml-1 text-[var(--color-brand)]">*</span>}
      </span>
      {children}
    </label>
  );
}

function Hint({ tone, children }: { tone: "warn" | "ok"; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 ${
        tone === "warn" ? "text-amber-600" : "text-emerald-600"
      }`}
    >
      {tone === "ok" && <CheckIcon className="h-3 w-3" />}
      {children}
    </span>
  );
}
