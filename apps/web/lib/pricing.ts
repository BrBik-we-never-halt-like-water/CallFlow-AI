/**
 * Commercial configuration - the single source of truth for pricing.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * TODO BEFORE LAUNCH - every `null` below is an unset commercial number and
 * renders as a visible `TODO` chip on /pricing. Nothing here is a placeholder
 * guess dressed up as a real price, because a wrong number on a pricing page is
 * worse than an obviously missing one.
 *
 *   [ ] monthlyInr / monthlyUsd for Starter, Growth, Scale
 *   [ ] includedCalls for every tier
 *   [ ] overageInr / overageUsd for every tier
 *   [ ] confirm ANNUAL_MONTHS_FREE matches what Billing actually charges
 *
 * Layout reads these values and never hard-codes one, so filling them in is a
 * single-file change.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import type { Currency } from './format';

export type BillingPeriod = 'monthly' | 'annual';

/** Annual billing bills 10 months for 12. */
export const ANNUAL_MONTHS_FREE = 2;

export type PlanId = 'free' | 'starter' | 'growth' | 'scale';

export interface Plan {
  id: PlanId;
  name: string;
  /** One line on who the plan is for. Never a feature list. */
  tagline: string;
  /** `null` = not set yet; renders as a TODO chip. `0` = genuinely free. */
  monthlyInr: number | null;
  monthlyUsd: number | null;
  /** Calls included in the monthly price. */
  includedCalls: number | null;
  /** Per-call rate once the included volume is used. */
  overageInr: number | null;
  overageUsd: number | null;
  features: string[];
  cta: string;
  ctaHref: string;
  /** Marked with a 1px ink border and a small mono tag - never a coloured banner. */
  mostChosen?: boolean;
}

export const PLANS: Plan[] = [
  {
    id: 'free',
    name: 'Free',
    tagline: 'Prove the pipeline before you spend anything.',
    monthlyInr: 0,
    monthlyUsd: 0,
    includedCalls: null,
    overageInr: null,
    overageUsd: null,
    features: [
      'Free daily call budget, no card required',
      'All starter campaign templates',
      'Typed results and sentiment on every call',
      'Escalation queue',
      '1 seat',
    ],
    cta: 'Start free',
    ctaHref: '/signup',
  },
  {
    id: 'starter',
    name: 'Starter',
    tagline: 'One person running outbound alongside their day job.',
    monthlyInr: null,
    monthlyUsd: null,
    includedCalls: null,
    overageInr: null,
    overageUsd: null,
    features: [
      'Everything in Free',
      'Live calling with your own caller ID',
      'Custom campaigns and extraction fields',
      'CSV export',
      'Suppression list across every campaign',
      '3 seats',
    ],
    cta: 'Start free',
    ctaHref: '/signup',
  },
  {
    id: 'growth',
    name: 'Growth',
    tagline: 'A team that calls every day and triages the results.',
    monthlyInr: null,
    monthlyUsd: null,
    includedCalls: null,
    overageInr: null,
    overageUsd: null,
    features: [
      'Everything in Starter',
      'Webhooks with a delivery log and replay',
      'CRM integrations',
      'Scheduled runs and calling windows per campaign',
      'Assignment and resolution on escalations',
      '10 seats',
      'Email support with a one-business-day reply',
    ],
    cta: 'Start free',
    ctaHref: '/signup',
    mostChosen: true,
  },
  {
    id: 'scale',
    name: 'Scale',
    tagline: 'Outbound is a core operation, not a side project.',
    monthlyInr: null,
    monthlyUsd: null,
    includedCalls: null,
    overageInr: null,
    overageUsd: null,
    features: [
      'Everything in Growth',
      'Multiple organisations and number pools',
      'Role-based access and audit log',
      'Custom data retention window',
      'Priority support',
      'Unlimited seats',
    ],
    cta: 'Book a 15-min demo',
    ctaHref: '/demo',
  },
];

export const ENTERPRISE = {
  name: 'Enterprise',
  tagline: 'Procurement, a DPA, and a number of your own.',
  features: [
    'Signed DPA and security review',
    'Regional data residency',
    'Bring your own numbers and carrier',
    'SSO and SCIM provisioning',
    'Uptime commitment',
    'Named contact',
  ],
  cta: 'Talk to us',
  ctaHref: '/demo',
} as const;

export function planPrice(plan: Plan, currency: Currency): number | null {
  return currency === 'INR' ? plan.monthlyInr : plan.monthlyUsd;
}

export function planOverage(plan: Plan, currency: Currency): number | null {
  return currency === 'INR' ? plan.overageInr : plan.overageUsd;
}

/**
 * Price for the chosen period, expressed per month so the columns stay
 * comparable. Annual shows the discounted monthly equivalent.
 */
export function monthlyEquivalent(
  plan: Plan,
  currency: Currency,
  period: BillingPeriod,
): number | null {
  const monthly = planPrice(plan, currency);
  if (monthly == null) return null;
  if (period === 'monthly' || monthly === 0) return monthly;
  return Math.round((monthly * (12 - ANNUAL_MONTHS_FREE)) / 12);
}

/* ---------------------------------------------------------------------------
   Feature comparison matrix. Collapsible by category, sticky plan headers.
   `true` renders a tick, `false` a dash, a string renders as mono text.
   --------------------------------------------------------------------------- */

export type MatrixValue = boolean | string | null;

export interface MatrixRow {
  label: string;
  /** One-sentence explanation, shown in a tooltip on the row label. */
  hint?: string;
  values: Record<PlanId, MatrixValue>;
}

export interface MatrixCategory {
  name: string;
  rows: MatrixRow[];
}

export const FEATURE_MATRIX: MatrixCategory[] = [
  {
    name: 'Calling',
    rows: [
      {
        label: 'Live calls included',
        values: { free: false, starter: null, growth: null, scale: null },
      },
      {
        label: 'Calls placed per hour',
        hint: 'A pacing limit, so a run never looks like a burst of robocalls.',
        values: { free: '-', starter: null, growth: null, scale: null },
      },
      {
        label: 'Your own caller ID',
        values: { free: false, starter: true, growth: true, scale: true },
      },
      {
        label: 'Voicemail and IVR handling',
        values: { free: true, starter: true, growth: true, scale: true },
      },
      {
        label: 'Calling windows per campaign',
        values: { free: false, starter: false, growth: true, scale: true },
      },
    ],
  },
  {
    name: 'Results and triage',
    rows: [
      {
        label: 'Typed results on every call',
        hint: 'Schema-validated fields, not a transcript you have to read.',
        values: { free: true, starter: true, growth: true, scale: true },
      },
      {
        label: 'Sentiment and escalation reason',
        values: { free: true, starter: true, growth: true, scale: true },
      },
      {
        label: 'Custom extraction fields',
        values: {
          free: 'Templates only',
          starter: true,
          growth: true,
          scale: true,
        },
      },
      {
        label: 'Assign and resolve escalations',
        values: { free: false, starter: false, growth: true, scale: true },
      },
      {
        label: 'Transcript retention',
        values: {
          free: '7 days',
          starter: '30 days',
          growth: '12 months',
          scale: 'Configurable',
        },
      },
    ],
  },
  {
    name: 'Safety and compliance',
    rows: [
      {
        label: 'Allowlist, per-run ceiling, rate limit',
        values: { free: true, starter: true, growth: true, scale: true },
      },
      {
        label: 'Suppression list across every campaign',
        values: { free: true, starter: true, growth: true, scale: true },
      },
      {
        label: 'Editable AI-disclosure line',
        hint: 'On by default and cannot be fully removed.',
        values: { free: true, starter: true, growth: true, scale: true },
      },
      {
        label: 'Audit log',
        values: { free: false, starter: false, growth: false, scale: true },
      },
      {
        label: 'Signed DPA',
        values: { free: false, starter: false, growth: true, scale: true },
      },
    ],
  },
  {
    name: 'Team and integrations',
    rows: [
      {
        label: 'Seats',
        values: { free: '1', starter: '3', growth: '10', scale: 'Unlimited' },
      },
      {
        label: 'CSV export',
        values: { free: false, starter: true, growth: true, scale: true },
      },
      {
        label: 'Webhooks with replay',
        values: { free: false, starter: false, growth: true, scale: true },
      },
      {
        label: 'CRM integrations',
        values: { free: false, starter: false, growth: true, scale: true },
      },
      {
        label: 'API access',
        values: { free: false, starter: true, growth: true, scale: true },
      },
      {
        label: 'SSO',
        values: { free: false, starter: false, growth: false, scale: true },
      },
    ],
  },
  {
    name: 'Support',
    rows: [
      {
        label: 'Support channel',
        values: {
          free: 'Docs',
          starter: 'Email',
          growth: 'Email',
          scale: 'Priority',
        },
      },
      {
        label: 'First-reply target',
        values: {
          free: '-',
          starter: '2 business days',
          growth: '1 business day',
          scale: '4 hours',
        },
      },
      {
        label: 'Onboarding session',
        values: { free: false, starter: false, growth: true, scale: true },
      },
    ],
  },
];

/* ---------------------------------------------------------------------------
   Cost comparison. This is the argument that closes deals in this market: the
   buyer is comparing against hiring a tele-caller, not against an API.

   These are ESTIMATE INPUTS, not claims - the page exposes them as editable
   fields and recomputes, so a buyer can put their own salary figure in.
   --------------------------------------------------------------------------- */

export const COMPARISON_DEFAULTS = {
  /** Monthly cost of one full-time tele-caller, fully loaded. */
  callerMonthlyInr: 25000,
  callerMonthlyUsd: 3200,
  /** Connected calls one person completes in a working day. */
  callsPerDay: 60,
  workingDaysPerMonth: 22,
  /** Hours per day the desk is actually covered. */
  coveredHoursPerDay: 8,
  /** Minutes spent typing notes into a CRM after each call. */
  notesMinutesPerCall: 2,
} as const;

/* ---------------------------------------------------------------------------
   ROI calculator defaults, used on the solution pages.
   --------------------------------------------------------------------------- */

export const ROI_DEFAULTS = {
  contactsPerMonth: 500,
  /** Share of contacts that reach a useful outcome today, as a percentage. */
  currentConversionPct: 18,
  /** Fully-loaded cost of one human call attempt. */
  costPerHumanCallInr: 35,
  costPerHumanCallUsd: 0.45,
  /** Minutes of human time one call attempt consumes, dialling and notes included. */
  minutesPerHumanCall: 7,
} as const;

/* ---------------------------------------------------------------------------
   Pricing FAQ.
   --------------------------------------------------------------------------- */

export const PRICING_FAQ: { q: string; a: string }[] = [
  {
    q: 'What counts as a billable call?',
    a: 'A call is billable once it connects and the conversation starts. Busy signals, unanswered rings, and numbers blocked by your safety guards are not billable. A call that reaches voicemail is billable only if the agent leaves the message you asked it to leave.',
  },
  {
    q: 'What happens when I go over my included volume?',
    a: "Calls keep going and the extra ones bill at your plan's overage rate. You are not cut off mid-run. If you would rather stop than overspend, set a daily budget in Settings → Safety and runs will halt at the ceiling instead.",
  },
  {
    q: 'Can I bring my own number?',
    a: 'Yes, from Starter up. You verify a caller ID you already own and campaigns dial from it, so the number your contacts see is the one they recognise. Enterprise can bring an entire number pool and carrier.',
  },
  {
    q: 'What happens if I run out of credits during a run?',
    a: 'The run pauses rather than failing. Contacts already called keep their results, contacts not yet reached stay queued, and the run resumes from where it stopped once you top up.',
  },
  {
    q: 'Do you offer refunds?',
    a: 'Unused subscription time is refunded pro-rata if you cancel within the first 30 days of a paid plan. Call volume already spent is not refundable, because the calls were placed.',
  },
  {
    q: 'How long is the contract?',
    a: 'Monthly plans are month to month and you can cancel any time. Annual plans run twelve months and bill ten, which is the discount. There is no minimum term on Free.',
  },
  {
    q: 'How long do you keep call data?',
    a: "Transcripts and recordings follow your plan's retention window, and you can shorten it on any plan. Typed results and outcomes are kept for the life of the account so your reporting stays intact. You can export or delete everything at any time from Settings → Compliance.",
  },
  {
    q: 'How do I cancel?',
    a: 'Settings → Billing, in one click, without talking to anyone. Your data stays available for export for 30 days after cancellation, then it is deleted.',
  },
];
