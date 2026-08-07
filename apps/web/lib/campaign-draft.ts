/**
 * Campaign settings the editor collects but the service does not yet accept.
 *
 * The calling window, timezone, and retry policy are real product requirements and
 * the guards on the run composer read them — but the campaign API has no field for
 * them yet. Rather than drop them from the editor (which would make the safety story
 * incomplete) or send them and have them silently discarded, they are persisted
 * locally against the campaign id.
 *
 * When the API grows these fields, `loadLocalSettings` becomes a fallback and this
 * module is the only place that needs changing.
 */

export const CAMPAIGN_DRAFT_KEY = "callflow.campaign.draft";
const SETTINGS_KEY = "callflow.campaign.settings";

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

export interface LocalCampaignSettings {
  window: CallingWindow;
  retry: RetryPolicy;
  escalateOnNegative: boolean;
}

export const DEFAULT_SETTINGS: LocalCampaignSettings = {
  window: { start: "09:00", end: "20:00", timezone: "Asia/Kolkata" },
  retry: { attempts: 2, spacingHours: 24 },
  escalateOnNegative: true,
};

export const TIMEZONES = [
  { value: "Asia/Kolkata", label: "India — IST (UTC+5:30)" },
  { value: "Asia/Dubai", label: "Gulf — GST (UTC+4)" },
  { value: "Europe/London", label: "UK — GMT/BST" },
  { value: "Europe/Berlin", label: "Central Europe — CET/CEST" },
  { value: "America/New_York", label: "US Eastern — ET" },
  { value: "America/Los_Angeles", label: "US Pacific — PT" },
  { value: "Asia/Singapore", label: "Singapore — SGT (UTC+8)" },
  { value: "Australia/Sydney", label: "Sydney — AEST/AEDT" },
];

export const REGIONS = [
  { value: "IN", label: "India" },
  { value: "AE", label: "United Arab Emirates" },
  { value: "GB", label: "United Kingdom" },
  { value: "US", label: "United States" },
  { value: "SG", label: "Singapore" },
  { value: "AU", label: "Australia" },
];

export const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "en-IN", label: "English (India)" },
  { value: "ar", label: "Arabic" },
  { value: "es", label: "Spanish" },
];

/** One key per campaign, so a settings read is a single subscription. */
export function settingsKey(campaignId: string): string {
  return `${SETTINGS_KEY}.${campaignId || "default"}`;
}

/**
 * Non-reactive read, for the places that need the values once inside an event handler
 * rather than as subscribed state (the run composer's guard chips).
 */
export function loadLocalSettings(campaignId: string): LocalCampaignSettings {
  try {
    const raw = localStorage.getItem(settingsKey(campaignId));
    return raw ? (JSON.parse(raw) as LocalCampaignSettings) : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveLocalSettings(
  campaignId: string,
  settings: LocalCampaignSettings,
): void {
  try {
    localStorage.setItem(settingsKey(campaignId), JSON.stringify(settings));
  } catch {
    /* storage unavailable — the settings apply for this session only */
  }
}

/** Sample contacts for the editor's live preview. */
export const PREVIEW_CONTACTS = [
  {
    name: "Aditi Sharma",
    context: {
      enquiry_note: "asked about Bali in December",
      role: "Senior Nurse",
      company: "Meridian Health",
      location: "Pune",
      programme: "MSc Data Science",
      institution: "Northgate University",
      clinic_name: "Lakeview Clinic",
      missed_date: "Tuesday 4 August",
      available_slots: "Thursday 10am, Friday 2pm, Monday 9am",
      product_interest: "outbound calling",
      appointment_time: "tomorrow at 4pm",
    },
  },
  {
    name: "Rahul Verma",
    context: {
      enquiry_note: "honeymoon package enquiry",
      role: "Backend Engineer",
      company: "Meridian Health",
      location: "Remote",
      programme: "MBA",
      institution: "Northgate University",
      clinic_name: "Lakeview Clinic",
      missed_date: "Friday 1 August",
      available_slots: "Wednesday 11am, Thursday 3pm",
      product_interest: "lead qualification",
      appointment_time: "Thursday at 11am",
    },
  },
  {
    name: "Priya Nair",
    context: {
      enquiry_note: "family trip to Singapore",
      role: "Operations Lead",
      company: "Meridian Health",
      location: "Bengaluru",
      programme: "BSc Nursing",
      institution: "Northgate University",
      clinic_name: "Lakeview Clinic",
      missed_date: "Monday 28 July",
      available_slots: "Tuesday 9am, Wednesday 4pm",
      product_interest: "appointment recovery",
      appointment_time: "Monday at 2pm",
    },
  },
];
