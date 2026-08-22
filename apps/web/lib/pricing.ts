/**
 * Commercial copy: who each plan is for, and what differs between them.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * PRICES ARE NOT IN THIS FILE, AND MUST NOT COME BACK TO IT.
 *
 * The payment gateway is the Merchant of Record, so it holds the price of
 * record. `GET /api/v1/billing/plans` reads the live amount back and the UI
 * renders that. Keeping a second copy here is how a pricing page ends up
 * disagreeing with the checkout a customer is looking at - which is worse than
 * the missing numbers that got the public `/pricing` page deleted in the first
 * place (`DESIGN_NOTES.md`, 2026-08-10).
 *
 * `ANNUAL_MONTHS_FREE`, `monthlyInr`/`monthlyUsd`, `includedCalls`,
 * `overageInr`/`overageUsd`, `planPrice()`, `planOverage()` and
 * `monthlyEquivalent()` were all removed for that reason. The annual discount is
 * whatever the gateway's annual product costs.
 *
 * Still consumed today:
 *   - `PLANS`        → app/(app)/app/billing/page.tsx
 *   - `ROI_DEFAULTS` → components/marketing/roi-calculator.tsx (solution pages;
 *                      it models the *buyer's* own human-call cost, never ours,
 *                      which is why it survives with pricing undecided)
 *
 * LIMITS ARE NOT IN THIS FILE EITHER. `FEATURE_MATRIX` states them as copy for
 * a buyer to read, but `apps/api/app/domain/plans.py` and the seeded
 * `plan_entitlements` table are what the product enforces. If they disagree, the
 * backend is right and this file is a bug - see `docs/BILLING.md` §1.
 * ─────────────────────────────────────────────────────────────────────────────
 */

export type BillingPeriod = "monthly" | "annual";

/**
 * `enterprise` replaced `scale`. Matches `PlanId` in
 * `apps/api/app/domain/plans.py` and `organisations_plan_id_check` exactly -
 * one value space in three places, and all three move together.
 */
export type PlanId = "free" | "starter" | "growth" | "enterprise";

export interface Plan {
  id: PlanId;
  name: string;
  /** One line on who the plan is for. Never a feature list. */
  tagline: string;
  features: string[];
  /**
   * The verb, and it has to survive the click. "Start free" belongs to Free
   * alone: there is no trial of a paid plan, so putting it on Starter or Growth
   * promises one (CLAUDE.md §4 #9). A paid plan's button chooses the plan; the
   * account it lands on begins on Free and is upgraded from Billing.
   */
  cta: string;
  ctaHref: string;
  /** Marked with a 1px ink border and a small mono tag — never a coloured banner. */
  mostChosen?: boolean;
  /**
   * `false` for plans with no checkout. Enterprise is invoiced outside the
   * product, so its card offers a conversation rather than a price.
   */
  selfServe: boolean;
}

/**
 * The three numbers a buyer decides on, as copy.
 *
 * One home in this file, because they appear twice on the site - the home page's
 * plan cards and `FEATURE_MATRIX`'s rows below both read from here - and two
 * hand-maintained copies of "3 agents" is how one of them ends up saying 5.
 *
 * Still only copy. `apps/api/app/domain/plans.py` and the seeded
 * `plan_entitlements` table are what the product enforces; if these disagree with
 * those, this file is the bug (see the header).
 */
export const PLAN_LIMITS: Record<
  PlanId,
  { agents: string; seats: string; credit: string }
> = {
  free: { agents: "1", seats: "1", credit: "₹100" },
  starter: { agents: "3", seats: "3", credit: "₹850" },
  growth: { agents: "10", seats: "10", credit: "₹4,250" },
  enterprise: { agents: "Custom", seats: "Custom", credit: "Agreed" },
};

/** "3 agents · 3 seats · ₹850 of calling". The plan card's one-line summary.
 *
 *  `callsPerDay` used to be the third value here and was removed, not renamed.
 *  It could never be the binding limit - at 90-second calls Free's credit allows
 *  44 calls a *month* against a cap of 600 - so it was a number no customer would
 *  reach, printed where they look for the one that stops them. The daily ceiling
 *  still exists as a runaway bound (`domain/plans.py`'s `RUNAWAY_CALL_CEILING`),
 *  identical on every plan, and is a Settings → Safety concern rather than a
 *  pricing one. */
export function limitsSummary(id: PlanId): string {
  const { agents, seats, credit } = PLAN_LIMITS[id];
  const plural = (value: string, noun: string) =>
    value === "1" ? `1 ${noun}` : `${value} ${noun}s`;
  return [
    plural(agents, "agent"),
    plural(seats, "seat"),
    `${credit} of calling`,
  ].join(" · ");
}

export const PLANS: Plan[] = [
  {
    id: "free",
    name: "Free",
    tagline: "Prove the pipeline before you spend anything.",
    features: [
      "Calling credit included, no card required",
      "Connect your own number and carrier",
      "All starter campaign templates",
      "Typed results and sentiment on every call",
      "Escalation queue",
      "1 seat",
    ],
    cta: "Start free",
    ctaHref: "/signup",
    selfServe: false,
  },
  {
    id: "starter",
    name: "Starter",
    tagline: "One person running outbound alongside their day job.",
    features: [
      "Everything in Free",
      "Live calling with your own caller ID",
      "Custom agents and extraction fields",
      "CSV export",
      "Suppression list across every run",
      "3 agents, 3 seats",
    ],
    cta: "Choose Starter",
    ctaHref: "/signup",
    selfServe: true,
  },
  {
    id: "growth",
    name: "Growth",
    tagline: "A team that calls every day and triages the results.",
    features: [
      "Everything in Starter",
      "Assignment and resolution on escalations",
      "Mix any model providers you like",
      "10 agents, 10 seats, 3 organisations",
      "Email support with a one-business-day reply",
    ],
    cta: "Choose Growth",
    ctaHref: "/signup",
    mostChosen: true,
    selfServe: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    tagline: "Outbound is a core operation, and procurement is involved.",
    features: [
      "Everything in Growth",
      "Limits set to whatever you actually need",
      "Seats and organisations sized to your team",
      "Role-based access and audit log",
      "Custom data retention window",
      "Signed DPA and security review",
      "Bring your own numbers and carrier at any scale",
      "SSO and SCIM provisioning",
      "Named contact and priority support",
    ],
    cta: "Book a 15-min demo",
    ctaHref: "/demo",
    selfServe: false,
  },
];

/* ---------------------------------------------------------------------------
   Feature comparison matrix. Collapsible by category, sticky plan headers.
   `true` renders a tick, `false` a dash, a string renders as mono text.

   No cell is `null` any more. `null` used to mean "price not decided yet" and
   rendered a visible TODO chip; prices left this file, so an unset cell would
   now be an oversight rather than an honest gap.
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

/** Builds a matrix row's `values` from a per-plan lookup, so a row that restates
 *  a `PLAN_LIMITS` number reads it rather than repeating it. */
function byPlan(pick: (id: PlanId) => MatrixValue): Record<PlanId, MatrixValue> {
  return {
    free: pick("free"),
    starter: pick("starter"),
    growth: pick("growth"),
    enterprise: pick("enterprise"),
  };
}

export const FEATURE_MATRIX: MatrixCategory[] = [
  {
    name: "Calling",
    rows: [
      {
        label: "Included calling credit",
        hint: "Spent by the second, at a rate that depends on whose model providers ran the call. Your own keys cost the least. Top up any time; unused credit does not roll over.",
        values: byPlan((id) => PLAN_LIMITS[id].credit),
      },
      {
        label: "Your own caller ID",
        hint: "You connect your own carrier account, so the number your contacts see is one you own. Included on every plan.",
        values: { free: true, starter: true, growth: true, enterprise: true },
      },
      {
        label: "Voice agents",
        hint: "A configured STT, LLM and TTS pipeline with a number attached.",
        values: byPlan((id) => PLAN_LIMITS[id].agents),
      },
      {
        label: "Voicemail and IVR handling",
        values: { free: true, starter: true, growth: true, enterprise: true },
      },
    ],
  },
  {
    name: "Results and triage",
    rows: [
      {
        label: "Typed results on every call",
        hint: "Schema-validated fields, not a transcript you have to read.",
        values: { free: true, starter: true, growth: true, enterprise: true },
      },
      {
        label: "Sentiment and escalation reason",
        values: { free: true, starter: true, growth: true, enterprise: true },
      },
      {
        label: "Custom extraction fields",
        values: { free: "Templates only", starter: true, growth: true, enterprise: true },
      },
      {
        label: "Assign and resolve escalations",
        values: { free: false, starter: false, growth: true, enterprise: true },
      },
      {
        label: "Transcript retention",
        values: {
          free: "7 days",
          starter: "30 days",
          growth: "12 months",
          enterprise: "Configurable",
        },
      },
    ],
  },
  {
    name: "Safety and compliance",
    rows: [
      {
        label: "Suppression list across every run",
        values: { free: true, starter: true, growth: true, enterprise: true },
      },
      {
        label: "Audit log",
        values: { free: false, starter: false, growth: false, enterprise: true },
      },
      {
        label: "Signed DPA",
        values: { free: false, starter: false, growth: true, enterprise: true },
      },
    ],
  },
  {
    name: "Team and integrations",
    rows: [
      {
        label: "Seats",
        values: byPlan((id) => PLAN_LIMITS[id].seats),
      },
      {
        label: "Organisations",
        hint: "Separate workspaces, each with its own contacts, campaigns and team.",
        values: { free: "1", starter: "1", growth: "3", enterprise: "Custom" },
      },
      {
        label: "Model providers you can connect",
        hint: "Bring your own speech and language vendor keys. Billed to you by them, not by us.",
        values: { free: "2", starter: "3", growth: "Unlimited", enterprise: "Unlimited" },
      },
      {
        label: "CSV export",
        values: { free: false, starter: true, growth: true, enterprise: true },
      },
      {
        label: "API access",
        values: { free: false, starter: true, growth: true, enterprise: true },
      },
      { label: "SSO", values: { free: false, starter: false, growth: false, enterprise: true } },
    ],
  },
  {
    name: "Support",
    rows: [
      {
        label: "Support channel",
        values: { free: "Docs", starter: "Email", growth: "Email", enterprise: "Priority" },
      },
      {
        label: "First-reply target",
        values: {
          free: "—",
          starter: "2 business days",
          growth: "1 business day",
          enterprise: "4 hours",
        },
      },
      {
        label: "Onboarding session",
        values: { free: false, starter: false, growth: true, enterprise: true },
      },
    ],
  },
];

/* ---------------------------------------------------------------------------
   Cost comparison. This is the argument that closes deals in this market: the
   buyer is comparing against hiring a tele-caller, not against an API.

   These are ESTIMATE INPUTS, not claims — the page exposes them as editable
   fields and recomputes, so a buyer can put their own salary figure in.

   Currently unused: `CostComparison` was deleted with the pricing pages. Staged,
   not dead.
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

   Rewritten for entitlement-based plans. The previous answers described a
   metered product this one is not: an overage rate, "you are not cut off
   mid-run", a run that "pauses and resumes once you top up", and a pro-rata
   refund window. There is no overage and no pause/resume endpoint, so those
   were promises the code contradicted. Top-up shipped afterward
   (`POST /api/v1/billing/top-up`) - the FAQ answer below about topping up is
   current; this comment is about what was true when the rewrite happened.
   --------------------------------------------------------------------------- */

export const PRICING_FAQ: { q: string; a: string }[] = [
  {
    q: "Am I charged per call?",
    a: "Not per call, no. Your plan includes calling credit, and a call spends it by the second — so a twelve-second voicemail costs a twelve-second slice rather than a whole call. The rate depends on whose model providers ran it: bring your own keys and you pay only our platform fee. Runs stop when the credit is spent, so nothing arrives as a surprise on a bill.",
  },
  {
    q: "What happens when my calling credit runs out?",
    a: "Runs stop and tell you that is why. Nothing is billed extra and nothing is silently dropped — contacts that were not reached stay in the run. A call already in progress always finishes; we would rather absorb the overrun than cut someone off mid-sentence. You can top up straight away, or wait for the next period, when a fresh allowance lands. Unused credit does not roll over.",
  },
  {
    q: "Who pays for the phone calls and the AI?",
    a: "The phone calls are yours: you connect your own carrier account and it bills you directly, at any plan including Free. For the AI you have a choice. Bring your own speech and language keys and those vendors bill you directly — you pay us only our per-minute platform fee, which is the cheapest way to run. Use ours instead and we charge a published per-minute rate for each part we supply, so the convenience has a price you can see before you pick a model rather than after.",
  },
  {
    q: "Can I bring my own number?",
    a: "Yes, from Starter up. You verify a caller ID you already own and runs dial from it, so the number your contacts see is the one they recognise. Enterprise can bring an entire number pool and carrier.",
  },
  {
    q: "Can I use it on the free plan without a card?",
    a: "Yes. Free includes calling credit, one voice agent and one seat, and it dials real numbers through your own carrier. No card is required and there is no trial clock.",
  },
  {
    q: "What happens if a payment fails?",
    a: "Your plan keeps working until the end of the period you have already paid for, so a card that expires mid-campaign does not stop calls that day. We email you, and you can update the payment method from Billing. If the period ends without a successful payment, the organisation moves to Free.",
  },
  {
    q: "What happens to my data if I downgrade?",
    a: "Nothing is deleted. Numbers and provider keys you have already connected keep working — a downgrade only stops you adding new ones. If a downgrade puts you over a limit, what exists stays; you just cannot create more until you are back under it.",
  },
  {
    q: "How long is the contract, and how do I cancel?",
    a: "Monthly plans are month to month. Cancel from Billing in one click, without talking to anyone — your plan then runs to the end of the period you paid for rather than stopping that instant. Annual plans run twelve months. There is no minimum term on Free.",
  },
  {
    q: "How long do you keep call data?",
    a: "Transcripts and recordings follow your plan's retention window, and you can shorten it on any plan. Typed results and outcomes are kept for the life of the account so your reporting stays intact. You can export or delete everything at any time from Settings → Compliance.",
  },
  {
    q: "What does Enterprise change?",
    a: "Every limit becomes whatever you actually need rather than a fixed tier, and billing moves to an invoice instead of a card. It also adds the audit log, SSO, a signed DPA and a named contact. It is the one plan you cannot self-serve, because the limits are agreed rather than published.",
  },
];
