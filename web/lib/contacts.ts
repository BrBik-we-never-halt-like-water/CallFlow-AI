import type { ContactInput } from "./api";

export interface ParsedRow {
  row: number;
  name: string;
  phone: string;
  note: string;
  valid: boolean;
  error?: string;
}

export const REQUIRED_HEADERS = ["name", "phone", "note"] as const;

const E164 = /^\+[1-9]\d{7,14}$/;

/** Split a CSV line, honouring double-quoted fields that contain commas. */
function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
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
    } else if (ch === "," && !quoted) {
      out.push(cur.trim());
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur.trim());
  return out;
}

/**
 * Normalise loose phone input into E.164 where the intent is unambiguous.
 * Anything still not E.164 after this is reported as an error rather than
 * guessed at — dialing a wrong number is worse than rejecting a row.
 */
export function normalisePhone(raw: string, defaultCountryCode = "91"): string {
  let p = raw.replace(/[\s\-()./]/g, "");
  if (p.startsWith("00")) p = `+${p.slice(2)}`;
  if (!p.startsWith("+")) {
    // A bare 10-digit number is assumed to be in the default country.
    if (/^\d{10}$/.test(p)) p = `+${defaultCountryCode}${p}`;
    else if (/^\d{11,15}$/.test(p)) p = `+${p}`;
  }
  return p;
}

/**
 * Parse a CSV / TSV sheet export into contact rows.
 *
 * Accepts an optional header line. Recognised columns: name, phone, note.
 * Without a header, columns are read positionally as name, phone, note.
 */
export function parseSheet(text: string): ParsedRow[] {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  if (lines.length === 0) return [];

  // Tab-separated exports are common when pasting straight out of Excel.
  const delimiter = lines[0].includes("\t") && !lines[0].includes(",") ? "\t" : ",";
  const split = (line: string) =>
    delimiter === "\t" ? line.split("\t").map((c) => c.trim()) : splitCsvLine(line);

  const first = split(lines[0]).map((c) => c.toLowerCase());
  const hasHeader = first.some((c) => REQUIRED_HEADERS.includes(c as never));

  let idxName = 0;
  let idxPhone = 1;
  let idxNote = 2;

  if (hasHeader) {
    const find = (n: string) => first.findIndex((c) => c === n);
    idxName = find("name");
    idxPhone = find("phone");
    idxNote = find("note");
  }

  const body = hasHeader ? lines.slice(1) : lines;

  return body.map((line, i) => {
    const cells = split(line);
    const name = (idxName >= 0 ? cells[idxName] : "")?.trim() ?? "";
    const rawPhone = (idxPhone >= 0 ? cells[idxPhone] : "")?.trim() ?? "";
    const note = (idxNote >= 0 ? cells[idxNote] : "")?.trim() ?? "";
    const phone = normalisePhone(rawPhone);
    const rowNumber = i + (hasHeader ? 2 : 1);

    if (!name) {
      return { row: rowNumber, name, phone, note, valid: false, error: "Missing name" };
    }
    if (!rawPhone) {
      return { row: rowNumber, name, phone, note, valid: false, error: "Missing phone" };
    }
    if (!E164.test(phone)) {
      return {
        row: rowNumber,
        name,
        phone,
        note,
        valid: false,
        error: "Not a valid number — use +country code",
      };
    }
    return { row: rowNumber, name, phone, note, valid: true };
  });
}

export function toContactInputs(rows: ParsedRow[]): ContactInput[] {
  return rows
    .filter((r) => r.valid)
    .map((r) => ({
      name: r.name,
      phone: r.phone,
      context: {
        enquiry_note: r.note || "no note on file",
        appointment_time: "tomorrow at 4pm",
      },
    }));
}

/** Mask a number for display so full numbers never sit on screen. */
export function maskPhone(phone: string): string {
  if (phone.length <= 6) return "***";
  const reveal = Math.min(3, Math.floor(phone.length / 4));
  return `${phone.slice(0, reveal)}${"*".repeat(phone.length - 2 * reveal)}${phone.slice(-reveal)}`;
}

// Reserved fictional numbers only (+1 555 0100-0199) — sample data must never
// be able to reach a real person if someone runs it in live mode.
export const SAMPLE_CSV = `name,phone,note
Aditi Sharma,+15555550100,asked about Bali in December
Rahul Verma,+15555550101,honeymoon package enquiry
Priya Nair,+15555550102,family trip to Singapore`;
