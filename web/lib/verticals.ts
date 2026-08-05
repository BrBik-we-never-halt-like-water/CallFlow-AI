/**
 * The four solution verticals.
 *
 * The goal template and the result schema are shown in full on each page, and
 * that is the point rather than a detail: buyers in this category have been shown
 * a lot of vague AI demos, and the literal artefact — the exact instruction the
 * agent is given, and the exact fields that come back — is the thing that makes
 * the claim checkable. Anything trimmed for tidiness here weakens the page.
 */

export interface Objection {
  question: string;
  answer: string;
}

export interface SchemaField {
  key: string;
  type: "string" | "number" | "boolean" | "date" | "enum";
  /** For enums, the permitted values. */
  options?: string[];
  description: string;
}

export interface Vertical {
  slug: string;
  name: string;
  /** Headline names the outcome, never the technology. */
  headline: string;
  sub: string;
  /** Shown on the home page's vertical strip. */
  metricLabel: string;
  metric: string;
  /** The specific pain, in three lines. */
  pain: string[];
  /** The campaign goal, exactly as it is stored. */
  goalTemplate: string;
  schema: SchemaField[];
  objections: [Objection, Objection];
  /** Defaults for this vertical's ROI calculator. */
  roi: {
    contactsPerMonth: number;
    currentConversionPct: number;
    minutesPerCall: number;
  };
}

export const VERTICALS: Vertical[] = [
  {
    slug: "recruiting-screening",
    name: "Recruiting screening",
    headline: "Screen a shortlist overnight, interview only the ones worth interviewing.",
    sub: "CallFlow calls every candidate on your list, asks your screening questions, and returns notice period, expected salary, and location fit as typed fields. Your coordinators read a ranked list in the morning instead of dialling all day.",
    metricLabel: "Time to first interview",
    metric: "Screen 200 candidates in a night, not a fortnight",
    pain: [
      "A coordinator spends most of a week reaching a shortlist of two hundred, and half of them never pick up on the first try.",
      "The same five questions get asked in every call, then typed into the ATS from memory an hour later.",
      "By the time the good candidates are screened, the best of them have accepted somewhere else.",
    ],
    goalTemplate: `You are calling {name} about the {context[role]} role at {context[company]}.

Open by confirming you are speaking to {name}, say who you are calling on behalf of, and state clearly that you are an automated assistant. Ask whether now is a good time. If it is not, ask when would suit and end the call politely.

If they are happy to continue, screen for four things, in this order:
1. Are they still open to a new role right now?
2. What notice period would they need to serve?
3. What salary range are they looking for?
4. Can they work from {context[location]}, or would they need remote?

Keep it conversational. If they ask a question you cannot answer — about the team, the interview process, or anything contractual — tell them a recruiter will follow up and note that they asked.

If they say they are not interested, thank them and ask whether they would like to be contacted about future roles. If they ask to be removed from the list, confirm that you will remove them and end the call.

If at any point they sound frustrated, ask to speak to a person, or ask you to stop, stop screening immediately, apologise once, and hand off.`,
    schema: [
      {
        key: "still_open",
        type: "boolean",
        description: "True if the candidate is actively open to a new role.",
      },
      {
        key: "notice_period_weeks",
        type: "number",
        description: "Notice period in weeks. Null if they would not say.",
      },
      {
        key: "salary_expectation",
        type: "string",
        description: "Expected salary in the candidate's own words, including currency.",
      },
      {
        key: "location_fit",
        type: "enum",
        options: ["onsite", "hybrid", "remote_only", "unclear"],
        description: "Whether the candidate can work from the role's location.",
      },
      {
        key: "wants_future_roles",
        type: "boolean",
        description: "True if a declining candidate agreed to future contact.",
      },
      {
        key: "recruiter_question",
        type: "string",
        description: "Any question the candidate asked that needs a human answer.",
      },
    ],
    objections: [
      {
        question: "Won't candidates be put off by an automated screening call?",
        answer:
          "The call says it is automated in the first few seconds — that line is on by default and cannot be fully removed. In practice the objection candidates actually raise is the opposite one: being asked the same five questions by a person, at a time that does not suit them, and then waiting a week for a reply. This calls at a reasonable hour, takes two minutes, and anyone who would rather speak to a human is handed to one immediately.",
      },
      {
        question: "What happens when a candidate asks something the agent can't answer?",
        answer:
          "It says a recruiter will follow up and records the question in the `recruiter_question` field, so the follow-up starts with the answer already known. It does not guess at package details, interview stages, or anything contractual — a wrong answer on a call is worse than a deferred one.",
      },
    ],
    roi: { contactsPerMonth: 400, currentConversionPct: 35, minutesPerCall: 8 },
  },
  {
    slug: "appointment-recovery",
    name: "Appointment recovery",
    headline: "Fill the slots that went quiet, without a receptionist on the phone all afternoon.",
    sub: "CallFlow calls the patients and clients who missed an appointment or never confirmed one, offers the openings you actually have, and returns a confirmed slot or a clear reason. Your front desk handles the exceptions instead of the whole list.",
    metricLabel: "Recovered bookings per month",
    metric: "Turn a no-show list into a filled diary",
    pain: [
      "Every no-show is a paid-for slot that earned nothing, and nobody has time to chase them.",
      "Confirmation calls land in the same hours as walk-ins, so the front desk is choosing between the phone and the person in front of them.",
      "When someone does answer, the available slots have to be read out from a screen the caller is also trying to use.",
    ],
    goalTemplate: `You are calling {name} about their missed appointment at {context[clinic_name]} on {context[missed_date]}.

Confirm you are speaking to {name}, say which clinic you are calling from, and state clearly that you are an automated assistant. Ask whether now is a good time to talk about rebooking.

If yes, say that the appointment on {context[missed_date]} was missed and ask whether they would like to rebook. Offer these openings, one at a time, and stop as soon as they accept one: {context[available_slots]}.

If none of the openings suit, ask what days and times generally work for them and record that instead of forcing a choice.

If they say they no longer need the appointment, ask briefly whether that is because the issue resolved, they went elsewhere, or something else — then thank them and close.

Do not give any clinical advice, discuss test results, or comment on their treatment, even if asked directly. If they raise anything clinical, tell them a member of the practice will call back about it.

If they sound distressed or frustrated, or ask for a person, stop and hand off to a human immediately.`,
    schema: [
      {
        key: "rebooked",
        type: "boolean",
        description: "True if the contact accepted one of the offered openings.",
      },
      {
        key: "slot_accepted",
        type: "string",
        description: "The opening they accepted, as offered. Null if none.",
      },
      {
        key: "preferred_window",
        type: "string",
        description: "Days and times that suit them, when no offered slot worked.",
      },
      {
        key: "no_longer_needed_reason",
        type: "enum",
        options: ["resolved", "went_elsewhere", "other", "not_given"],
        description: "Why the appointment is no longer wanted, if it isn't.",
      },
      {
        key: "clinical_question_raised",
        type: "boolean",
        description: "True if anything clinical came up and needs a practice callback.",
      },
    ],
    objections: [
      {
        question: "We're a clinic — can this touch patient data at all?",
        answer:
          "The call is given only the name, the missed date, and the openings you want offered. It is instructed not to discuss anything clinical and to hand off if a patient raises it, and the `clinical_question_raised` field tells you exactly which calls need a practice callback. Numbers are masked everywhere in the interface, retention is configurable, and a signed DPA is available.",
      },
      {
        question: "What if the slot gets taken while the call is happening?",
        answer:
          "Offer the openings you are willing to hold, and treat the returned `slot_accepted` as a request rather than a booking — the front desk confirms it against the diary. Teams running this at volume usually reserve a small pool of recovery slots so the confirmation is a formality.",
      },
    ],
    roi: { contactsPerMonth: 300, currentConversionPct: 22, minutesPerCall: 5 },
  },
  {
    slug: "admissions-followup",
    name: "Admissions follow-up",
    headline: "Reach every enquiry once, properly, before they enrol somewhere else.",
    sub: "CallFlow calls every prospective student who enquired, answers the practical questions, and returns intended programme, start term, and what is holding them back. Your admissions team spends its time on the people who are actually deciding.",
    metricLabel: "Enquiries reached within 48 hours",
    metric: "Every enquiry called back, not just the recent ones",
    pain: [
      "Enquiries arrive in bursts around deadlines, and the team can only call back the newest ones.",
      "The questions are the same every time — fees, start dates, entry requirements, hostel — but the answers still need a person.",
      "A student who enquired ten days ago has usually already applied somewhere that called them back on day one.",
    ],
    goalTemplate: `You are calling {name}, who enquired about studying {context[programme]} at {context[institution]}.

Confirm you are speaking to {name}, say which institution you are calling from, and state clearly that you are an automated assistant. Ask whether now is a good time — many of these calls reach students in class, and a bad time is not a bad outcome.

If they can talk, work through three things:
1. Confirm which programme they are interested in, and which intake or start term they are aiming for.
2. Ask how far along they are: still exploring, planning to apply, already applied, or applied elsewhere too.
3. Ask what would help them decide, and record it in their own words.

You may confirm these facts and nothing more: the programmes offered, published start terms, and that fees and entry requirements are on the website. Do not quote a fee figure, promise a scholarship, or comment on whether their grades would be accepted — an admissions officer follows up on all of that.

If they say they have already accepted an offer elsewhere, congratulate them, ask which institution if they are willing to say, and close politely.

If they sound frustrated, ask for a person, or ask not to be called again, stop and hand off.`,
    schema: [
      {
        key: "programme_confirmed",
        type: "string",
        description: "The programme the student is actually interested in.",
      },
      {
        key: "start_term",
        type: "string",
        description: "Intended intake or start term, in the student's words.",
      },
      {
        key: "stage",
        type: "enum",
        options: ["exploring", "will_apply", "applied", "accepted_elsewhere"],
        description: "How far along the student's decision is.",
      },
      {
        key: "blocker",
        type: "string",
        description: "What is holding them back, recorded in their own words.",
      },
      {
        key: "needs_officer_callback",
        type: "boolean",
        description: "True if they asked about fees, scholarships, or eligibility.",
      },
      {
        key: "competing_institution",
        type: "string",
        description: "Where else they accepted or applied, if volunteered.",
      },
    ],
    objections: [
      {
        question: "Our enquiries are students — is calling them appropriate?",
        answer:
          "They enquired, which is consent to be contacted about the thing they asked about, and the call opens by saying which institution it is from. The calling window keeps it inside reasonable hours, and the agent asks whether now is a good time before doing anything else. A student who says it is a bad time is queued for a polite retry rather than pushed.",
      },
      {
        question: "What stops it from over-promising to get an application?",
        answer:
          "The goal lists exactly what may be confirmed — programmes, published start terms, and where the fee information lives — and the agent is told not to quote figures, promise scholarships, or comment on eligibility. Anything in that territory sets `needs_officer_callback` instead, and an officer follows up. The agent has no incentive to close; it is scored on returning accurate fields, not on conversions.",
      },
    ],
    roi: { contactsPerMonth: 800, currentConversionPct: 28, minutesPerCall: 6 },
  },
  {
    slug: "lead-qualification",
    name: "Lead qualification",
    headline: "Only talk to the leads worth talking to.",
    sub: "CallFlow calls every inbound lead within minutes, establishes budget, timeline, and who actually decides, and returns it as typed fields. Your closers get a shortlist with the qualifying already done.",
    metricLabel: "Cost per qualified conversation",
    metric: "Call every lead in minutes, qualify before a rep is spent",
    pain: [
      "Inbound leads go cold in under an hour, and nobody is free the moment one lands.",
      "Reps spend their most expensive hours discovering that a lead had no budget and no authority.",
      "The notes that do get typed up are inconsistent, so nobody trusts the pipeline numbers.",
    ],
    goalTemplate: `You are calling {name} from {context[company]}, who enquired about {context[product_interest]}.

Confirm you are speaking to {name}, say who you are calling from, and state clearly that you are an automated assistant. Ask whether now is a good time; if not, ask when suits and end politely.

If they can talk, qualify on four things, conversationally rather than as a checklist:
1. What problem prompted the enquiry — in their words, not a category.
2. Roughly how many people or how much volume this would need to cover.
3. What timeline they are working to.
4. Who else would be involved in deciding.

Do not quote prices, offer a discount, or commit to any date. If they ask what it costs, say pricing depends on volume, that it is published on the website, and that a specialist will confirm the detail.

If they are clearly not a fit — no budget, no timeline, or a problem this does not solve — say so kindly, thank them, and close. It is better to mark a lead unqualified than to book a meeting nobody wants.

If they ask to speak to a person, ask not to be called again, or sound annoyed, stop qualifying and hand off immediately.`,
    schema: [
      {
        key: "problem",
        type: "string",
        description: "The problem that prompted the enquiry, in the lead's words.",
      },
      {
        key: "volume",
        type: "string",
        description: "Rough scale — seats, users, calls, or units.",
      },
      { key: "timeline", type: "string", description: "When they are looking to decide." },
      {
        key: "decision_makers",
        type: "string",
        description: "Who else is involved in the decision.",
      },
      {
        key: "qualified",
        type: "boolean",
        description: "True if the lead is worth a rep's time.",
      },
      {
        key: "asked_about_pricing",
        type: "boolean",
        description: "True if pricing came up and needs a specialist reply.",
      },
    ],
    objections: [
      {
        question: "Our leads expect a human — won't this cost us deals?",
        answer:
          "The alternative is not a human calling in five minutes, it is a human calling tomorrow. This calls while the enquiry is still live, asks four questions, and hands anyone who wants a person straight to one. Reps then spend their hours on qualified conversations rather than on discovery calls that end in the first two minutes.",
      },
      {
        question: "How do we know the qualification is honest and not just optimistic?",
        answer:
          "Because it is typed, and the agent has nothing to gain. `qualified` is a boolean derived from the fields around it, and the goal explicitly tells the agent that marking a lead unqualified is the better outcome when it does not fit. Every field is traceable to the transcript, so a rep who disagrees can check in one click.",
      },
    ],
    roi: { contactsPerMonth: 600, currentConversionPct: 15, minutesPerCall: 7 },
  },
];

export function getVertical(slug: string): Vertical | undefined {
  return VERTICALS.find((v) => v.slug === slug);
}

/** Render the schema as the JSON Schema the campaign actually returns. */
export function schemaToJson(fields: SchemaField[]): string {
  const properties: Record<string, unknown> = {
    outcome: {
      type: "string",
      description: "How the call ended, in one or two words.",
    },
    sentiment: {
      type: "string",
      enum: ["positive", "neutral", "negative"],
      description: "How the contact sounded.",
    },
  };

  for (const field of fields) {
    properties[field.key] =
      field.type === "enum"
        ? { type: "string", enum: field.options ?? [], description: field.description }
        : field.type === "date"
          ? { type: "string", format: "date", description: field.description }
          : { type: field.type, description: field.description };
  }

  return JSON.stringify(
    { type: "object", properties, required: ["outcome", "sentiment"] },
    null,
    2,
  );
}
