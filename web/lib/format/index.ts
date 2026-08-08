/**
 * Shared formatters. Never inline a variant of one of these in a component  
 * a duration that reads `2m 14s` on one screen and `134s` on another is how a
 * product starts to feel like several products.
 */

export { formatE164, isE164, maskPhone, normalisePhone } from "./phone";

/** `134` → `2m 14s`. Durations are always mono. */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return " ";
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return " ";
  return new Intl.NumberFormat("en-IN").format(value);
}

export type Currency = "INR" | "USD";

export function formatCurrency(
  amount: number | null | undefined,
  currency: Currency,
  { compact = false }: { compact?: boolean } = {},
): string {
  if (amount == null || Number.isNaN(amount)) return " ";
  return new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: compact || Number.isInteger(amount) ? 0 : 2,
    notation: compact ? "compact" : "standard",
  }).format(amount);
}

/** Per-call overage rates are small; they need decimals the plan price doesn't. */
export function formatRate(amount: number | null | undefined, currency: Currency): string {
  if (amount == null || Number.isNaN(amount)) return " ";
  return new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return " ";
  return `${Math.round(value)}%`;
}

/**
 * Absolute timestamp, mono-friendly and unambiguous. Fixed to a stable locale
 * so a server-rendered timestamp cannot disagree with the client's.
 */
export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return " ";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return " ";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

export function formatTimeOnly(iso: string | null | undefined): string {
  if (!iso) return " ";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return " ";
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(d);
}

/**
 * `4h ago`. Used where age is the point   the escalation worklist sorts oldest
 * first, because the oldest escalation is the most expensive one.
 */
export function formatAge(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return " ";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return " ";
  const mins = Math.max(0, Math.round((now - then) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Turn `party_size` into `Party size` for a field label. */
export function humaniseKey(key: string): string {
  const spaced = key.replace(/[_-]+/g, " ").replace(/([a-z0-9])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1).toLowerCase();
}

export function pluralise(count: number, singular: string, plural = `${singular}s`): string {
  return count === 1 ? singular : plural;
}
