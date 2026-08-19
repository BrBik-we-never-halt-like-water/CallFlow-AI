/**
 * Settings a run collects that the service does not yet accept.
 *
 * The successor to `campaign-draft.ts`. The calling window, timezone and retry
 * policy are real product requirements and the run composer's guard bar reads
 * them - but no API field exists for them yet, so they are persisted locally
 * against the organisation rather than dropped from the interface (which would
 * make the safety story look narrower than it is) or sent and silently
 * discarded.
 *
 * These moved off the campaign because campaigns are gone (ADR-8). They belong
 * to the run now, which is where an operator sets them.
 *
 * When the API grows these fields, `loadRunSettings` becomes a fallback and this
 * module is the only place that changes.
 */

const SETTINGS_KEY = 'callflow.run.settings';

export interface CallingWindow {
  start: string;
  end: string;
  timezone: string;
}

export interface RetryPolicy {
  /** How many times a contact is re-attempted after a bad-timing outcome. */
  attempts: number;
  /** Hours to wait before the next attempt. */
  spacingHours: number;
}

export interface LocalRunSettings {
  window: CallingWindow;
  retry: RetryPolicy;
  escalateOnNegative: boolean;
}

export const DEFAULT_SETTINGS: LocalRunSettings = {
  window: { start: '09:00', end: '20:00', timezone: 'Asia/Kolkata' },
  retry: { attempts: 2, spacingHours: 24 },
  escalateOnNegative: true,
};

export const TIMEZONES = [
  { value: 'Asia/Kolkata', label: 'India - IST (UTC+5:30)' },
  { value: 'Asia/Dubai', label: 'Gulf - GST (UTC+4)' },
  { value: 'Europe/London', label: 'UK - GMT/BST' },
  { value: 'Europe/Berlin', label: 'Central Europe - CET/CEST' },
  { value: 'America/New_York', label: 'US Eastern - ET' },
  { value: 'America/Los_Angeles', label: 'US Pacific - PT' },
  { value: 'Asia/Singapore', label: 'Singapore - SGT (UTC+8)' },
  { value: 'Australia/Sydney', label: 'Sydney - AEST/AEDT' },
];

export const REGIONS = [
  { value: 'IN', label: 'India' },
  { value: 'AE', label: 'United Arab Emirates' },
  { value: 'GB', label: 'United Kingdom' },
  { value: 'US', label: 'United States' },
  { value: 'SG', label: 'Singapore' },
  { value: 'AU', label: 'Australia' },
];

export const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'Hindi' },
  { value: 'en-IN', label: 'English (India)' },
  { value: 'ar', label: 'Arabic' },
  { value: 'es', label: 'Spanish' },
];

/** One key per organisation, so a settings read is a single subscription. */
export function settingsKey(orgId: string): string {
  return `${SETTINGS_KEY}.${orgId || 'default'}`;
}

/**
 * Non-reactive read, for the places that need the values once inside an event
 * handler rather than as subscribed state (the run composer's guard chips).
 */
export function loadRunSettings(orgId: string): LocalRunSettings {
  try {
    const raw = localStorage.getItem(settingsKey(orgId));
    return raw ? (JSON.parse(raw) as LocalRunSettings) : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveRunSettings(orgId: string, settings: LocalRunSettings): void {
  try {
    localStorage.setItem(settingsKey(orgId), JSON.stringify(settings));
  } catch {
    /* storage unavailable - the settings apply for this session only */
  }
}
