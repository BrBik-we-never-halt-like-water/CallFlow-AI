/**
 * The suppression list.
 *
 * Stored locally because the service has no suppression endpoint yet. That is a real gap
 * and it is called out on the page: a suppression list that only exists in one browser is
 * not the permanent, global guarantee the product promises, and pretending otherwise
 * would be the most dangerous thing this interface could do.
 *
 * The functions here are pure list transforms — the storage read and write are owned by
 * `useStoredJson`, so reading the list is a subscription rather than a mount-time
 * side effect. Wiring this to a server means replacing the two call sites, not this file.
 */

export const SUPPRESSION_KEY = "callflow.suppression";

/** Stable empty array: a fresh `[]` each render would break snapshot identity. */
export const NO_SUPPRESSED: SuppressedNumber[] = [];

export interface SuppressedNumber {
  /** Full E.164. Stored so a re-import can be checked against it. */
  phone: string;
  reason: "opted_out" | "manual" | "imported";
  addedAt: string;
  note?: string;
}

export function addSuppressed(
  list: SuppressedNumber[],
  phone: string,
  reason: SuppressedNumber["reason"],
  note?: string,
): SuppressedNumber[] {
  if (list.some((entry) => entry.phone === phone)) return list;
  // Only ever called from a click handler, so reading the clock here is fine.
  return [...list, { phone, reason, addedAt: new Date().toISOString(), note }];
}

export function removeSuppressed(
  list: SuppressedNumber[],
  phone: string,
): SuppressedNumber[] {
  return list.filter((entry) => entry.phone !== phone);
}

export function isSuppressed(list: SuppressedNumber[], phone: string): boolean {
  return list.some((entry) => entry.phone === phone);
}
