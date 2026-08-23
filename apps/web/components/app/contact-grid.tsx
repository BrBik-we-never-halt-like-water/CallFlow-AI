'use client';

import {
  PlusIcon,
  TrashIcon,
  UploadSimpleIcon,
} from '@phosphor-icons/react/dist/ssr';
import { useRef, useState } from 'react';
import { cn } from '@/lib/cn';
import { Button } from '@/components/ui/button';
import { Panel } from '@/components/ui/panel';
import { Tag } from '@/components/ui/badge';
import { useToast } from '@/components/ui/toast';
import { normalisePhone } from '@/lib/format/phone';
import { api } from '@/lib/api';
import {
  parseSheet,
  SAMPLE_CSV,
  validateRow,
  type ParsedRow,
} from '@/lib/contacts';

/**
 * Spreadsheet-style contact editor.
 *
 * Three things matter here and all three are about not losing a contact silently:
 *
 *  - An invalid row is flagged in place with the reason, never dropped. A dropped row
 *    is a person who never got called and nobody ever finds out why.
 *  - The reason is specific. "Not a valid E.164 number - try +919876543210" tells you
 *    what to type; "invalid" does not.
 *
 * Native paste still works on any cell - click in and Ctrl+V, same as any text
 * input. What was removed is the dedicated "Paste" button that read the whole
 * clipboard through the Clipboard API and parsed it as a sheet; browsers gate
 * that read behind a permission prompt most people have never seen before, so
 * it read as broken more often than it read as a shortcut.
 */
export function ContactGrid({
  rows,
  onChange,
}: {
  rows: ParsedRow[];
  onChange: (rows: ParsedRow[]) => void;
}) {
  const toast = useToast();
  const fileInput = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);
  const [reading, setReading] = useState(false);

  const invalid = rows.filter((r) => !r.valid);
  const valid = rows.filter((r) => r.valid);

  function renumber(next: Omit<ParsedRow, 'row'>[]): ParsedRow[] {
    return next.map((row, i) => ({ ...row, row: i + 1 }));
  }

  function ingest(text: string, { append }: { append: boolean }) {
    const parsed = parseSheet(text);
    if (parsed.length === 0) {
      toast({
        tone: 'warning',
        title: 'Nothing to import',
        body: 'Expected columns name, phone, and note - with or without a header row.',
      });
      return;
    }
    const next = append ? [...rows, ...parsed] : parsed;
    onChange(renumber(next));

    const bad = parsed.filter((r) => !r.valid).length;
    toast({
      tone: bad > 0 ? 'warning' : 'success',
      title: `${parsed.length} ${parsed.length === 1 ? 'row' : 'rows'} imported`,
      body:
        bad > 0
          ? `${bad} ${bad === 1 ? 'row needs' : 'rows need'} fixing before the run can start.`
          : undefined,
    });
  }

  function updateCell(index: number, patch: Partial<ParsedRow>) {
    const next = rows.map((row, i) => {
      if (i !== index) return row;
      const merged = { ...row, ...patch };
      const normalised = normalisePhone(merged.phone);
      return {
        ...merged,
        ...validateRow(merged.name, merged.phone, normalised),
      };
    });
    onChange(next);
  }

  /**
   * A dropped or chosen file, by kind.
   *
   * CSV is a string split and is parsed here. An .xlsx is a zip of XML with
   * shared strings and typed cells - a phone number typed as digits is stored
   * as a float - so it goes to the server, which has a real reader for it.
   */
  async function onFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;

    if (/\.xls[xm]$/i.test(file.name)) {
      await ingestWorkbook(file);
      return;
    }
    if (/\.xls$/i.test(file.name)) {
      toast({
        tone: 'warning',
        title: 'That is the older Excel format',
        body: 'Save it as .xlsx or export it as CSV, then try again.',
      });
      return;
    }

    try {
      ingest(await file.text(), { append: rows.length > 0 });
    } catch {
      toast({
        tone: 'error',
        title: "That file couldn't be read",
        body: 'Export it again as CSV and try once more.',
      });
    }
  }

  async function ingestWorkbook(file: File) {
    setReading(true);
    try {
      const parsed = await api.parseSheet(file);
      if (parsed.rows.length === 0) {
        toast({
          tone: 'warning',
          title: 'Nothing to import',
          body: 'That sheet has a header row but no contacts under it.',
        });
        return;
      }

      // Mapped back onto the same row shape a pasted CSV produces, so
      // everything downstream - the grid, the counts, `toContactInputs` - has
      // one row type to deal with rather than two.
      const imported: ParsedRow[] = parsed.rows.map((row) => ({
        row: row.row,
        name: row.name,
        phone: row.contact?.phone ?? '',
        note: row.note,
        context: row.context,
        // Re-validated locally rather than trusting the server's wording: this
        // is what decides which *cell* the grid outlines, and matching on the
        // text of a message would break the moment that message is reworded.
        // The two validators apply the same rules (`lib/contacts.ts` and
        // `domain/spreadsheet.py`), so the verdict agrees either way.
        ...validateRow(row.name, row.contact?.phone ?? ''),
      }));

      const next =
        rows.length > 0 ? [...rows, ...imported] : imported;
      onChange(renumber(next));

      const bad = imported.filter((r) => !r.valid).length;
      toast({
        tone: bad > 0 ? 'warning' : 'success',
        title: `${imported.length} ${imported.length === 1 ? 'row' : 'rows'} imported`,
        body:
          bad > 0
            ? `${bad} ${bad === 1 ? 'row needs' : 'rows need'} fixing before the run can start.`
            : undefined,
      });
    } catch (error) {
      toast({
        tone: 'error',
        title: "That sheet couldn't be read",
        body:
          error instanceof Error
            ? error.message
            : 'Save it as .xlsx or export it as CSV, then try again.',
      });
    } finally {
      setReading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* ---- Import controls -------------------------------------------- */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          void onFiles(e.dataTransfer.files);
        }}
        className={cn(
          'flex flex-wrap items-center justify-between gap-3 rounded-md border border-dashed p-4',
          'transition-colors duration-(--dur-micro)',
          dragging ? 'border-rule-strong bg-surface-hover' : 'border-rule',
        )}
      >
        <div className="flex flex-col gap-1">
          <p className="text-small text-text">
            Drop a CSV or Excel file here, or add rows below
          </p>
          <p className="text-small text-text-mute">
            Columns: name, phone, note. Any other column becomes that
            contact&apos;s own context. A header row is optional for CSV and
            required for Excel.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={fileInput}
            type="file"
            accept=".csv,.tsv,.xlsx,.xlsm,text/csv,text/plain,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="sr-only"
            onChange={(e) => void onFiles(e.target.files)}
          />
          <Button
            variant="secondary"
            size="sm"
            loading={reading}
            onClick={() => fileInput.current?.click()}
          >
            <UploadSimpleIcon aria-hidden className="size-4" />
            Import a file
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => ingest(SAMPLE_CSV, { append: false })}
          >
            Use sample
          </Button>
        </div>
      </div>

      {/* ---- The grid --------------------------------------------------- */}
      {rows.length === 0 ? (
        <Panel sunken className="p-6 text-center">
          <p className="text-small text-text-dim">
            No contacts yet. Import a CSV, paste a list, or add a row by hand.
          </p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() =>
              onChange([
                {
                  row: 1,
                  name: '',
                  phone: '',
                  note: '',
                  context: {},
                  valid: false,
                  error: 'Add a name for this row.',
                  errorField: 'name',
                },
              ])
            }
          >
            <PlusIcon aria-hidden className="size-4" />
            Add a row
          </Button>
        </Panel>
      ) : (
        <div className="overflow-x-auto rounded-md border border-rule">
          <table className="w-full min-w-2xl border-collapse text-left">
            <caption className="sr-only">
              Contacts for this run. Invalid rows show the reason inline.
            </caption>
            <thead className="bg-surface-sunken">
              <tr className="border-b border-rule">
                <th
                  scope="col"
                  className="text-small font-bold w-10 px-3 py-2 text-text-mute"
                >
                  #
                </th>
                <th
                  scope="col"
                  className="text-small font-bold px-3 py-2 text-text-mute"
                >
                  Name
                </th>
                <th
                  scope="col"
                  className="text-small font-bold px-3 py-2 text-text-mute"
                >
                  Phone
                </th>
                <th
                  scope="col"
                  className="text-small font-bold px-3 py-2 text-text-mute"
                >
                  Note
                </th>
                <th scope="col" className="w-10 px-3 py-2">
                  <span className="sr-only">Remove</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                // A freshly added, completely empty row is obviously incomplete -
                // it doesn't need a red border and an error message to say so
                // before anyone has typed a single character into it. Once any
                // field has content, show real validation feedback on whichever
                // cell is actually the problem.
                const touched = Boolean(row.name || row.phone || row.note);
                const flagged = !row.valid && touched;

                return (
                  <tr
                    key={index}
                    className={cn(
                      'border-b border-rule last:border-0',
                      flagged &&
                        'bg-[color-mix(in_oklab,var(--lamp-flare)_6%,transparent)]',
                    )}
                  >
                    <td className="px-3 py-1.5 font-mono text-data tabular-nums text-text-mute">
                      {row.row}
                    </td>
                    <td className="px-2 py-1.5">
                      <GridInput
                        value={row.name}
                        onChange={(value) => updateCell(index, { name: value })}
                        placeholder="Aditi Sharma"
                        label={`Name, row ${row.row}`}
                        invalid={flagged && row.errorField === 'name'}
                        error={
                          row.errorField === 'name' ? row.error : undefined
                        }
                      />
                    </td>
                    <td className="px-2 py-1.5">
                      <GridInput
                        value={row.phone}
                        onChange={(value) =>
                          updateCell(index, { phone: value })
                        }
                        placeholder="+919876543210"
                        label={`Phone, row ${row.row}`}
                        mono
                        invalid={flagged && row.errorField === 'phone'}
                        error={
                          row.errorField === 'phone' ? row.error : undefined
                        }
                      />
                    </td>
                    <td className="px-2 py-1.5">
                      <GridInput
                        value={row.note}
                        onChange={(value) => updateCell(index, { note: value })}
                        placeholder="asked about Bali in December"
                        label={`Note, row ${row.row}`}
                      />
                    </td>
                    <td className="px-2 py-1.5">
                      <button
                        type="button"
                        aria-label={`Remove row ${row.row}`}
                        onClick={() =>
                          onChange(renumber(rows.filter((_, i) => i !== index)))
                        }
                        className="hit-target press flex size-8 cursor-pointer items-center justify-center rounded-sm text-text-mute transition-colors hover:bg-surface-hover hover:text-text"
                      >
                        <TrashIcon aria-hidden className="size-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ---- Row summary ------------------------------------------------ */}
      {rows.length > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-small font-bold text-text-mute">
              {valid.length} of {rows.length} ready
            </span>
            {invalid.length > 0 ? (
              <Tag mono={false} className="text-lamp-flare-text">
                {invalid.length}{' '}
                {invalid.length === 1 ? 'row needs' : 'rows need'} fixing
              </Tag>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                onChange(
                  renumber([
                    ...rows,
                    {
                      name: '',
                      phone: '',
                      note: '',
                      context: {},
                      valid: false,
                      error: 'Add a name for this row.',
                      errorField: 'name',
                    },
                  ]),
                )
              }
            >
              <PlusIcon aria-hidden className="size-4" />
              Add a row
            </Button>
            {invalid.length > 0 ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onChange(renumber(rows.filter((r) => r.valid)))}
              >
                Remove all invalid
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

/**
 * A cell. Borderless until focused so the grid reads as a sheet rather than as a wall
 * of inputs, with the error message inline beneath the offending cell.
 */
function GridInput({
  value,
  onChange,
  placeholder,
  label,
  mono = false,
  invalid = false,
  error,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  label: string;
  mono?: boolean;
  invalid?: boolean;
  error?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={label}
        aria-invalid={invalid || undefined}
        className={cn(
          'w-full rounded-sm border border-transparent bg-transparent px-2 py-1.5',
          'text-small text-text placeholder:text-text-mute',
          'hover:border-rule focus:border-rule-strong focus:bg-surface-raised',
          'transition-colors duration-(--dur-micro)',
          mono && 'font-mono text-data tabular-nums',
          invalid &&
            'border-[color-mix(in_oklab,var(--lamp-flare)_40%,transparent)]',
        )}
      />
      {invalid && error ? (
        <span className="px-2 text-small text-lamp-flare-text">{error}</span>
      ) : null}
    </div>
  );
}
