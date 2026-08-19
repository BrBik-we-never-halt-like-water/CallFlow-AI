import type { ContactInput } from './api';
import { isE164, normalisePhone } from './format/phone';

export interface ParsedRow {
  row: number;
  name: string;
  phone: string;
  /** The row's free-text "what this call is about", passed through as the
   *  `detail` block of the prompt. */
  note: string;
  /**
   * Every other column on the row, by header name.
   *
   * This is what makes one sheet produce a different conversation per person:
   * a `destination` column of Dubai / Malaysia / Spain reaches the agent as
   * that contact's own context rather than as a shared template value. Columns
   * the dispatch layer owns are dropped on entry - see `RESERVED_COLUMNS`.
   */
  context: Record<string, string>;
  valid: boolean;
  error?: string;
  /** Which cell the error actually belongs to, so the grid doesn't flag the
   * phone column for a missing name. */
  errorField?: 'name' | 'phone';
}

export const REQUIRED_HEADERS = ['name', 'phone', 'note'] as const;

/**
 * Column names the dispatch layer owns, dropped rather than passed through.
 *
 * A sheet with a column called `goal` or `voice_agent` would otherwise land in
 * the same metadata dict the runtime reads its own instructions from. The
 * server strips these too (`domain/prompt_assembly.py`) - that is the real
 * defence and this is the copy that lets the grid say so before upload.
 */
export const RESERVED_COLUMNS: ReadonlySet<string> = new Set([
  'goal',
  'prompt',
  'detail',
  'name',
  'phone',
  'phone_masked',
  'note',
  'run_id',
  'voice_agent',
  'voice_agent_id',
  'agent_name',
  'collect_schema',
  'language',
  'max_call_duration_seconds',
  'contact_name',
]);

/** Header text → a context key: lowercased, spaces and dashes to underscores,
 *  so `Trip type` and `trip_type` are the same column. */
export function toContextKey(header: string): string {
  return header
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_\s-]/g, '')
    .replace(/[\s-]+/g, '_')
    .slice(0, 40);
}

/** Split a CSV line, honouring double-quoted fields that contain commas. */
function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = '';
  let quoted = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else {
        quoted = !quoted;
      }
    } else if (ch === ',' && !quoted) {
      out.push(cur.trim());
      cur = '';
    } else {
      cur += ch;
    }
  }
  out.push(cur.trim());
  return out;
}

/**
 * Parse a CSV / TSV sheet export into contact rows.
 *
 * Accepts an optional header line. `name`, `phone` and `note` are recognised
 * by name; every other headed column becomes per-contact context, which is how
 * one sheet produces a different conversation per row. Without a header,
 * columns are read positionally as name, phone, note and nothing is context -
 * unnamed columns have no key to travel under.
 *
 * Invalid rows come back flagged rather than dropped - the composer shows the
 * reason inline and offers to remove them, because silently discarding a row
 * means a contact never gets called and nobody finds out why.
 */
export function parseSheet(text: string): ParsedRow[] {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  if (lines.length === 0) return [];

  // Tab-separated exports are common when pasting straight out of Excel.
  const delimiter =
    lines[0].includes('\t') && !lines[0].includes(',') ? '\t' : ',';
  const split = (line: string) =>
    delimiter === '\t'
      ? line.split('\t').map((c) => c.trim())
      : splitCsvLine(line);

  const first = split(lines[0]).map((c) => c.toLowerCase());
  const hasHeader = first.some((c) => REQUIRED_HEADERS.includes(c as never));

  let idxName = 0;
  let idxPhone = 1;
  let idxNote = 2;

  if (hasHeader) {
    const find = (n: string) => first.findIndex((c) => c === n);
    idxName = find('name');
    idxPhone = find('phone');
    idxNote = find('note');
  }

  // Position → context key for the columns that are nobody else's. Built once
  // rather than per row, and only when there is a header to name them by.
  const contextKeys = new Map<number, string>();
  if (hasHeader) {
    first.forEach((header, index) => {
      if (index === idxName || index === idxPhone || index === idxNote) return;
      const key = toContextKey(header);
      if (!key || RESERVED_COLUMNS.has(key)) return;
      contextKeys.set(index, key);
    });
  }

  const body = hasHeader ? lines.slice(1) : lines;

  return body.map((line, i) => {
    const cells = split(line);
    const name = (idxName >= 0 ? cells[idxName] : '')?.trim() ?? '';
    const rawPhone = (idxPhone >= 0 ? cells[idxPhone] : '')?.trim() ?? '';
    const note = (idxNote >= 0 ? cells[idxNote] : '')?.trim() ?? '';
    const phone = normalisePhone(rawPhone);
    const rowNumber = i + (hasHeader ? 2 : 1);

    const context: Record<string, string> = {};
    for (const [index, key] of contextKeys) {
      const value = cells[index]?.trim();
      if (value) context[key] = value;
    }

    return {
      row: rowNumber,
      name,
      phone,
      note,
      context,
      ...validateRow(name, rawPhone, phone),
    };
  });
}

/** Shared so the pasted-grid editor and the CSV importer agree on what's valid. */
export function validateRow(
  name: string,
  rawPhone: string,
  normalised = normalisePhone(rawPhone),
): { valid: boolean; error?: string; errorField?: 'name' | 'phone' } {
  if (!name)
    return {
      valid: false,
      error: 'Add a name for this row.',
      errorField: 'name',
    };
  if (!rawPhone) {
    return {
      valid: false,
      error: 'Add a phone number for this row.',
      errorField: 'phone',
    };
  }
  if (!isE164(normalised)) {
    return {
      valid: false,
      error: 'Not a valid E.164 number - try +919876543210.',
      errorField: 'phone',
    };
  }
  return { valid: true };
}

/**
 * Rows → what the API accepts.
 *
 * `detail` is the row's own "what this call is about" and `note` is kept
 * alongside it for prompts written against the older key. Everything else on
 * the row travels under its own column name. This used to stamp
 * `appointment_time: 'tomorrow at 4pm'` onto every contact in every real run -
 * a fixture that outlived the demo it was written for (`ISSUES.md` #138).
 */
export function toContactInputs(rows: ParsedRow[]): ContactInput[] {
  return rows
    .filter((r) => r.valid)
    .map((r) => {
      const context: Record<string, string> = { ...r.context };
      if (r.note) {
        context.detail = r.note;
        context.note = r.note;
      }
      return { name: r.name, phone: r.phone, context };
    });
}

/** The context columns present across these rows, for the composer's "each
 *  contact brings its own" summary. */
export function contextColumns(rows: ParsedRow[]): string[] {
  const keys = new Set<string>();
  for (const row of rows) {
    for (const key of Object.keys(row.context ?? {})) keys.add(key);
  }
  return [...keys].sort();
}

// Reserved fictional numbers only (+1 555 0100-0199) - sample data must never
// be able to reach a real person if someone runs it in live mode.
export const SAMPLE_CSV = `name,phone,note,destination,travel_month
Aditi Sharma,+15555550100,asked about a beach holiday,Bali,December
Rahul Verma,+15555550101,honeymoon package enquiry,Malaysia,February
Priya Nair,+15555550102,family trip with two children,Singapore,April`;
