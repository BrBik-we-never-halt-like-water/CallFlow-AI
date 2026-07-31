"use client";

import { useRef, useState } from "react";
import { normalisePhone, parseSheet, type ParsedRow } from "@/lib/contacts";
import { DownloadIcon, PlusIcon, TrashIcon, UploadIcon } from "./icons";

interface Props {
  rows: ParsedRow[];
  onRows: (rows: ParsedRow[]) => void;
}

const BLANK = { name: "", phone: "", note: "" };

/**
 * Reserved fictional numbers only.
 *
 * +1 555 0100-0199 is the North American range set aside for fiction, so these
 * can never reach a real person if someone runs live mode with the seed data
 * still loaded. Never seed real-looking numbers — they belong to somebody.
 */
const STARTER = [
  { name: "Aditi Sharma", phone: "+15555550100", note: "asked about Bali in December" },
  { name: "Rahul Verma", phone: "+15555550101", note: "honeymoon package enquiry" },
];

interface Draft {
  name: string;
  phone: string;
  note: string;
}

/** Re-validate drafts by round-tripping them through the shared CSV parser,
 *  so the table and an uploaded file are held to exactly the same rules. */
function validate(drafts: Draft[]): ParsedRow[] {
  return drafts.map((d, i) => {
    const csv = `${d.name.replace(/,/g, " ")},${d.phone},${d.note.replace(/,/g, " ")}`;
    const [parsed] = parseSheet(csv);
    return { ...parsed, row: i + 1 } as ParsedRow;
  });
}

export default function ContactUpload({ rows, onRows }: Props) {
  const [drafts, setDrafts] = useState<Draft[]>(STARTER);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function push(next: Draft[]) {
    setDrafts(next);
    onRows(validate(next.filter((d) => d.name || d.phone || d.note)));
  }

  function update(i: number, key: keyof Draft, value: string) {
    const next = drafts.map((d, j) => (j === i ? { ...d, [key]: value } : d));
    push(next);
  }

  function addRow() {
    push([...drafts, { ...BLANK }]);
  }

  function removeRow(i: number) {
    const next = drafts.filter((_, j) => j !== i);
    push(next.length ? next : [{ ...BLANK }]);
  }

  async function handleFile(file: File) {
    const lower = file.name.toLowerCase();

    if (lower.endsWith(".xlsx") || lower.endsWith(".xls")) {
      setFileError(
        "Excel workbooks aren't read directly. In Excel choose File → Save As → CSV, then upload that.",
      );
      setFileName(file.name);
      return;
    }
    if (!/\.(csv|tsv|txt)$/.test(lower)) {
      setFileError("Unsupported file. Upload a .csv, .tsv, or .txt export.");
      return;
    }

    try {
      const parsed = parseSheet(await file.text());
      if (parsed.length === 0) {
        setFileError("That file had no readable rows.");
        return;
      }
      setFileError(null);
      setFileName(file.name);
      // Fill the table from the file so it stays editable.
      push(parsed.map((p) => ({ name: p.name, phone: p.phone, note: p.note })));
    } catch {
      setFileError("Could not read that file.");
    }
  }

  const validCount = rows.filter((r) => r.valid).length;
  const invalidCount = rows.length - validCount;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <label className="text-xs font-medium text-[var(--color-muted)]">
          Contacts
        </label>
        <div className="flex items-center gap-3 text-[11px]">
          <button
            onClick={() => inputRef.current?.click()}
            className="inline-flex cursor-pointer items-center gap-1 font-medium text-[var(--color-brand)] hover:underline"
          >
            <UploadIcon className="h-3 w-3" />
            Import CSV
          </button>
          <a
            href="/sample-contacts.csv"
            download
            className="inline-flex cursor-pointer items-center gap-1 font-medium text-[var(--color-muted)] hover:underline"
          >
            <DownloadIcon className="h-3 w-3" />
            Template
          </a>
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".csv,.tsv,.txt,text/csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void handleFile(f);
          e.target.value = "";
        }}
      />

      {/* Editable table */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files?.[0];
          if (f) void handleFile(f);
        }}
        className={`overflow-hidden rounded-xl border transition ${
          dragging
            ? "border-[var(--color-brand)] ring-2 ring-indigo-100"
            : "border-[var(--color-border)]"
        }`}
      >
        <div className="grid grid-cols-[1fr_1fr_1.2fr_28px] gap-px border-b border-[var(--color-border)] bg-[var(--color-subtle)] px-3 py-2 text-[10px] font-semibold uppercase tracking-wide text-[var(--color-muted)]">
          <span>Name</span>
          <span>Phone</span>
          <span>Note</span>
          <span />
        </div>

        <div className="max-h-64 overflow-y-auto">
          {drafts.map((d, i) => {
            const row = rows[i];
            const bad = row && !row.valid && (d.name || d.phone);
            return (
              <div
                key={i}
                className="grid grid-cols-[1fr_1fr_1.2fr_28px] items-center gap-px border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-subtle)]"
              >
                <input
                  value={d.name}
                  onChange={(e) => update(i, "name", e.target.value)}
                  placeholder="Full name"
                  className="w-full bg-transparent px-3 py-2 text-xs outline-none placeholder:text-slate-300 focus:bg-white focus:ring-1 focus:ring-inset focus:ring-[var(--color-brand)]"
                />
                <input
                  value={d.phone}
                  onChange={(e) => update(i, "phone", e.target.value)}
                  onBlur={(e) => update(i, "phone", normalisePhone(e.target.value))}
                  placeholder="+91…"
                  inputMode="tel"
                  className={`w-full bg-transparent px-3 py-2 font-mono text-xs outline-none placeholder:text-slate-300 focus:bg-white focus:ring-1 focus:ring-inset focus:ring-[var(--color-brand)] ${
                    bad ? "text-red-600" : ""
                  }`}
                />
                <input
                  value={d.note}
                  onChange={(e) => update(i, "note", e.target.value)}
                  placeholder="Why you're calling"
                  className="w-full bg-transparent px-3 py-2 text-xs outline-none placeholder:text-slate-300 focus:bg-white focus:ring-1 focus:ring-inset focus:ring-[var(--color-brand)]"
                />
                <button
                  onClick={() => removeRow(i)}
                  aria-label={`Remove row ${i + 1}`}
                  className="flex h-full cursor-pointer items-center justify-center text-slate-300 transition-colors hover:text-red-500"
                >
                  <TrashIcon className="h-3.5 w-3.5" />
                </button>
              </div>
            );
          })}
        </div>

        <button
          onClick={addRow}
          className="flex w-full cursor-pointer items-center justify-center gap-1.5 border-t border-[var(--color-border)] bg-[var(--color-subtle)] py-2 text-[11px] font-medium text-[var(--color-brand)] transition-colors hover:bg-[var(--color-brand-soft)]"
        >
          <PlusIcon className="h-3 w-3" />
          Add contact
        </button>
      </div>

      {/* Status line */}
      <div className="mt-2 flex items-center justify-between text-[11px]">
        <span className="text-[var(--color-muted)]">
          {fileName ? (
            <>
              Imported <span className="font-medium">{fileName}</span>
            </>
          ) : (
            "Type directly, or drop a CSV onto the table"
          )}
        </span>
        <span>
          <span className="font-medium text-emerald-700">{validCount} ready</span>
          {invalidCount > 0 && (
            <span className="text-red-600"> · {invalidCount} need fixing</span>
          )}
        </span>
      </div>

      {fileError && (
        <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-800 ring-1 ring-inset ring-amber-200">
          {fileError}
        </p>
      )}

      {/* Per-row errors */}
      {rows.some((r) => !r.valid) && (
        <ul className="mt-2 space-y-1">
          {rows
            .map((r, i) => ({ r, i }))
            .filter(({ r }) => !r.valid)
            .map(({ r, i }) => (
              <li key={i} className="text-[11px] text-red-600">
                Row {i + 1}: {r.error}
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
