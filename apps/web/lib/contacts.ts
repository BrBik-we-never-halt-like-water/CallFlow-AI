import type { ContactInput } from './api';
import { isE164, normalisePhone } from './format/phone';

export interface ParsedRow {
  row: number;
  name: string;
  phone: string;
  note: string;
  valid: boolean;
  error?: string;
  /** Which cell the error actually belongs to, so the grid doesn't flag the
   * phone column for a missing name. */
  errorField?: 'name' | 'phone';
}

export const REQUIRED_HEADERS = ['name', 'phone', 'note'] as const;

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
 * Accepts an optional header line. Recognised columns: name, phone, note.
 * Without a header, columns are read positionally as name, phone, note.
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

  const body = hasHeader ? lines.slice(1) : lines;

  return body.map((line, i) => {
    const cells = split(line);
    const name = (idxName >= 0 ? cells[idxName] : '')?.trim() ?? '';
    const rawPhone = (idxPhone >= 0 ? cells[idxPhone] : '')?.trim() ?? '';
    const note = (idxNote >= 0 ? cells[idxNote] : '')?.trim() ?? '';
    const phone = normalisePhone(rawPhone);
    const rowNumber = i + (hasHeader ? 2 : 1);

    return {
      row: rowNumber,
      name,
      phone,
      note,
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

export function toContactInputs(rows: ParsedRow[]): ContactInput[] {
  return rows
    .filter((r) => r.valid)
    .map((r) => ({
      name: r.name,
      phone: r.phone,
      context: {
        enquiry_note: r.note || 'no note on file',
        appointment_time: 'tomorrow at 4pm',
      },
    }));
}

// Reserved fictional numbers only (+1 555 0100-0199) - sample data must never
// be able to reach a real person if someone runs it in live mode.
export const SAMPLE_CSV = `name,phone,note
Aditi Sharma,+15555550100,asked about Bali in December
Rahul Verma,+15555550101,honeymoon package enquiry
Priya Nair,+15555550102,family trip to Singapore`;
