/**
 * Phone number handling   the ONLY place in the codebase that masks a number.
 *
 * Masking is a product guarantee, not a display preference: a full number must
 * never sit on screen unless the viewer deliberately reveals it and is
 * permitted to. Keeping the implementation here means a new surface cannot
 * accidentally bypass the guarantee by writing its own formatter.
 */

const E164 = /^\+[1-9]\d{7,14}$/;

export function isE164(phone: string): boolean {
  return E164.test(phone);
}

/**
 * Normalise loose input into E.164 where the intent is unambiguous.
 *
 * Anything still not E.164 afterwards is reported as an error rather than
 * guessed at   dialling a wrong number is worse than rejecting a row.
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
 * Mask a number for display: `+919876543210` → `+91*******210`.
 *
 * Keeps the leading `+` and country prefix so an operator can still tell which
 * region a row belongs to, and the last three digits so they can match it
 * against a number a colleague reads out   without the number itself being
 * readable off a shared screen.
 */
export function maskPhone(phone: string): string {
  const trimmed = phone.trim();
  if (!trimmed) return "";
  if (trimmed.length <= 6) return "***";

  const lead = Math.min(3, Math.floor(trimmed.length / 4));
  const tail = Math.min(3, Math.floor(trimmed.length / 4));
  const hidden = trimmed.length - lead - tail;
  return `${trimmed.slice(0, lead)}${"*".repeat(Math.max(hidden, 1))}${trimmed.slice(-tail)}`;
}

/**
 * Group an E.164 number for readability when it is legitimately revealed.
 * Never used as a substitute for `maskPhone`.
 */
export function formatE164(phone: string): string {
  if (!isE164(phone)) return phone;
  const digits = phone.slice(1);
  // Country codes are 1–3 digits; split conservatively and group the rest in
  // fours so the eye can check it against a written number.
  const cc = digits.length > 11 ? digits.slice(0, 2) : digits.slice(0, 1);
  const rest = digits.slice(cc.length);
  const grouped = rest.replace(/(\d{4})(?=\d)/g, "$1 ");
  return `+${cc} ${grouped}`.trim();
}
