# Grading - how a call becomes a lead

**Status: specification, not yet implemented.** This is task `A1` on the P0 roadmap and it is the
source of truth for `LeadGrade`, `DeclineReason`, and the rule that assigns them. Code disagreeing
with this document is a bug in the code, until the Sunday sync says otherwise.

> **Task ids used here are not defined in this repo.** `A1`, `A8`, `S1`, `S3`, `H7`, `D6`-`D9` and
> the rest refer to the plan of record, which lives outside the repository. They are stable labels
> and nothing more - exactly the caveat `CLAUDE.md` §1 carries for `FEATURES.md`'s `F<n>` numbers,
> and for the same reason. Do not treat an id as a promise that something is specified somewhere.

**Who this is for.** Everyone. A floor manager should be able to read §2 and §3 and understand
exactly what they will be handed. Arbaaz implements §4 as `app/domain/grading.py`; Shivam tests it
against §5; Yash renders §2 and §6 on `/app/leads` and `/app/reports`.

**What this replaces.** `Disposition` (`app/domain/entities.py`) answers *"does this call need a
human?"* - a support question. CallFlow sells the answer to *"is this lead worth a human?"* Those are
different questions and the current enum cannot express the second one, which is why the thing we
sell cannot currently be selected from the database. See §8 for the migration.

---

## 1. The two axes, and why they are separate

A single outcome enum forces two unrelated facts into one column. Today `UNREACHABLE` and a person
who politely declined both end up in the same list, and neither can be reported on.

| Axis | Column | Question it answers | Meaningful when |
| ---- | ------ | ------------------- | --------------- |
| Reachability | `result` | Did a conversation happen at all? | Always |
| Qualification | `grade` | Is this person worth a caller's time? | Only when `result = SPOKE` |
| Next step | `next_action` | What does a human do with this row? | Always |

A row with `result = NO_ANSWER` has no grade. Not `COLD` - **no grade**. Never let an unreachable
number look like a rejection; it makes the decline report lie, and the decline report is the half of
the product a floor cannot produce for itself.

---

## 2. The enums, in plain language

### 2.1 `CallResult` - did we speak to them

| Value | Means | Set by |
| ----- | ----- | ------ |
| `IN_FLIGHT` | The call is happening right now. Not an outcome. | `run_dialer` at origination |
| `SPOKE` | A human answered and a conversation occurred. | The runtime, on a completed session |
| `NO_ANSWER` | Rang out. The number is probably fine. | Carrier status |
| `BUSY` | Engaged. Worth another attempt. | Carrier status |
| `VOICEMAIL` | Answering machine detected. No conversation. | Carrier / runtime |
| `INVALID_NUMBER` | Not dialable. Bad data on the list. | The carrier. **Not** E.164 validation - that guard was removed from `check_dial_allowed()` (`CLAUDE.md` §4.8) and nothing validates a number before a dial today |
| `FAILED` | We could not complete the attempt - provider error, timeout, or a call whose callback never arrived. | Gateway, or the reaper (`A8`) |
| `SUPPRESSED` | Never dialled. On the suppression list. | `check_dial_allowed()` |

Only `SPOKE` produces a grade. Everything else produces a `next_action` and nothing more.

### 2.2 `LeadGrade` - is this lead worth a human

| Value | Means, in one line | What a caller does |
| ----- | ------------------ | ------------------ |
| `HOT` | They want it, the terms are known, and a closer could ring them today. | Ring them this shift |
| `WARM` | Real interest, with something still unresolved - money, timing, or somebody else's approval. | Ring them, knowing what to resolve |
| `COLD` | We spoke, there is no present interest, and no objection worth chasing. | Nothing now. Nurture list |
| `REFUSED` | An explicit no, or a request not to be contacted again. | Off this list. Only a do-not-call request is also suppressed - see §4.1 rules 1 and 2 |
| `WRONG_PERSON` | Not the decision maker, or not who the list said they were. | Fix the list, not the lead |
| `UNGRADED` | We could not read the call reliably enough to grade it. | A person listens or re-dials |

**`UNGRADED` exists so that failure is visible.** A model that cannot extract must not quietly produce
`COLD`, because a quiet `COLD` is indistinguishable from a real rejection and it inflates the decline
report with calls we simply failed to understand. Shivam's `S3` asserts this explicitly, and it is the
single most important test in the suite.

### 2.3 `NextAction` - what a human does with the row

| Value | Means |
| ----- | ----- |
| `CALL_NOW` | In this shift. The lead is warm and waiting |
| `CALL_AT` | At the time they asked for. `callback_at` carries it |
| `NURTURE` | No call. Marketing's list, not the floor's |
| `DROP` | Do nothing. Not worth a second attempt |
| `SUPPRESS` | Add to the suppression list. Never dial again |
| `FIX_DATA` | The row is wrong, not the person. Bad number, wrong contact, failed extraction |

### 2.4 `DeclineReason` - why they said no

The enum aggregates; the free-text `decline_note` catches what the enum missed. Both, always - an
enum alone loses next quarter's categories, and free text alone cannot be counted.

| Value | Means | Who should see it |
| ----- | ----- | ----------------- |
| `ALREADY_ENROLLED_ELSEWHERE` | Already signed up for a comparable programme. | Sales leadership - this is competitive loss |
| `PRICE_OR_EMI` | Wants it, cannot pay it as offered. | Whoever sets pricing and EMI terms |
| `DEGREE_VALIDITY_DOUBT` | Unsure the qualification is recognised or accepted by employers. | Marketing - this is a trust gap |
| `WRONG_PROGRAMME` | Wanted a different subject, level, or format. | Marketing - targeting is off |
| `NO_TIME` | Cannot commit the hours, usually alongside a job. | Product - is there a lighter format |
| `EMPLOYER_WONT_SPONSOR` | Needed company funding and did not get it. | Sales - is there a B2B motion here |
| `STILL_DECIDING` | Genuinely undecided, not a no. Recorded alongside `intent = maybe`, which §4.1 grades `WARM` | The floor - this is a callback |
| `LANGUAGE_BARRIER` | Could not hold the conversation in the languages we offer. | Us. This is our failure, not theirs |
| `DO_NOT_CONTACT` | Asked not to be called again. Recorded alongside the `do_not_contact` flag, which is what rule 1 reads - **the flag is what suppresses, not this value** | Compliance |
| `OTHER` | None of the above. `decline_note` is mandatory here. | Arbaaz, weekly - this is where new values come from |

> **`OTHER` is a queue, not a bucket.** Review its notes every week (`A9`). When the same phrase
> appears five times, it becomes an enum value. If `OTHER` exceeds 20% of declines, the taxonomy is
> wrong and the decline report is not sellable - that is the "decline coverage" metric on the roadmap.

---

## 3. The extraction fields the rule reads

The agent collects these and nothing else. **A field the grading rule never reads is a question that
wastes twenty seconds of a stranger's time**, and every wasted question lowers the completion rate of
the questions that matter.

| Field | Type | Collected how |
| ----- | ---- | ------------- |
| `extraction_errored` | bool | Set by the extraction step, not the agent. True when the transcript could not be read into fields at all - rule 4 keys on it |
| `intent` | `yes` / `no` / `maybe` / `unknown`, **or null** | The agent's read of whether they want the programme. Null when the call ended before it could be established |
| `intent_explicit_no` | bool or null | They said no in words, rather than drifting off |
| `intake_month` | string or null | Which intake they would join |
| `budget_stated` | bool | They named a figure or agreed to the fee |
| `budget_amount_paise` | int or null | If named. Integers, never floats (`CLAUDE.md` §4.3) |
| `emi_needed` | bool | They need instalments to proceed |
| `emi_accepted` | bool | They accepted the EMI terms we offer |
| `already_enrolled` | bool | Enrolled in a comparable programme elsewhere |
| `competitor_named` | string or null | If they said who |
| `employer_sponsored` | bool | Employer is paying, or would need to |
| `work_experience_years` | int or null | Eligibility for most online degree programmes |
| `is_decision_maker` | bool or null | They can decide, rather than asking a spouse or employer |
| `identity_confirmed` | bool or null | They are the person the list named |
| `do_not_contact` | bool or null | Asked not to be called again |
| `hostile` | bool or null | Abuse, shouting, or a demand to stop |
| `callback_at` | datetime or null | They asked to be called at a specific time |
| `decline_reason` | `DeclineReason` or null | Why, when they declined |
| `decline_note` | string or null | Their own words. Mandatory when reason is `OTHER` |

**Every field here is nullable, and null is load-bearing.** A `bool` field carries three states -
true, false, and *we never found out* - and §4.1 rule 3 depends on telling the second from the
third. An implementation that types these as non-nullable booleans grades every unfinished call
`WRONG_PERSON`.

**Required fields** (absent ⇒ `UNGRADED`, unless a §4 hard signal fires first): `intent`,
`is_decision_maker`, `identity_confirmed`. Everything else is optional and shapes the grade rather
than blocking it. This list is per-organisation configuration - see §7.

Two collection paths reach these values and the existing design already handles it
(`apps/voice-runtime/app/collection.py`): `record_field` during the call is the good path;
`recover_missing()` afterwards is the fallback. **A recovered guess never overwrites a heard answer.**
That property must survive this work.

---

## 4. The rule

A pure function. No I/O, no vendor, no database - the standard `safety.py`, `triage.py` and
`collection.py` already hold, and the reason all four can be tested against a dict instead of a
transcript (`CLAUDE.md` §3, Single responsibility).

```
grade_lead(result, fields, config) -> GradeOutcome

GradeOutcome:
    grade:          LeadGrade | None      # None for any result but SPOKE
    grade_reason:   str                   # prose a rep can read; never a rule id
    next_action:    NextAction            # always set, graded or not
    decline_reason: DeclineReason | None  # echoed from the fields, for the report
```

`result` is a parameter, not an afterthought: §1 promises that an unreachable row carries no grade,
and a function that never sees `result` cannot keep that promise.

**`grade` is nullable; `next_action` is not.** An unreachable row still has to tell a human what to
do with it, so the function always returns an outcome and only the grade goes empty. Returning
nothing at all would leave a rang-out number with no instruction, which is the same silence §1
objects to.

### 4.0 Suppression is not a grade, and does not wait for one

**If `do_not_contact` was recorded at any point in the call, that number is suppressed - whatever
`result` says, whatever the grade says, whether or not extraction succeeded.** The write happens
in-call (`A11`), and the post-call path re-asserts it rather than assuming the first write landed.

This is stated here rather than left to §5's worked example because grading is gated on `SPOKE`, and
a call that drops after someone says "remove my number" has `result = FAILED` and no grade. Routing
suppression through the grade would lose exactly that person. **A suppression that depends on a
successful extraction is not a suppression.**

### 4.1 Precedence, top to bottom. The first match wins.

```
0.  result != SPOKE                          -> grade None; next_action from §4.1a

1.  do_not_contact  OR  hostile              -> REFUSED       next: SUPPRESS
2.  intent == no  AND  intent_explicit_no    -> REFUSED       next: DROP

3.  identity_confirmed is False
       OR is_decision_maker is False         -> WRONG_PERSON  next: FIX_DATA

4.  extraction_errored
       OR any required field is None         -> UNGRADED      next: FIX_DATA

5.  intent == yes AND intake_ok AND money_ok -> HOT           next: CALL_NOW
6.  intent == yes                            -> WARM          next: CALL_NOW
7.  intent == maybe                          -> WARM          next: CALL_AT when callback_at
                                                              is set, else CALL_NOW
8.  intent == no                             -> COLD          next: NURTURE
9.  otherwise                                -> UNGRADED      next: FIX_DATA
```

Rule 9 is `otherwise`, not `intent == unknown`. It is the terminal arm, so the table is total: a
null `intent`, or a fifth value added later, lands on `UNGRADED` rather than falling off the bottom
with nothing returned. A new `intent` value should be a deliberate new rule, not a silent `COLD`.

### 4.1a What an unreachable row gets instead

Rule 0 produces no grade, but §2.1 promises every row carries a `next_action`. This is that mapping.

| `result` | `next_action` | Why |
| -------- | ------------- | --- |
| `NO_ANSWER`, `BUSY` | `CALL_NOW` | The number is fine and nobody has spoken to them |
| `VOICEMAIL` | `NURTURE` | Reached, not spoken to. Not a caller's time |
| `INVALID_NUMBER`, `FAILED` | `FIX_DATA` | The row is wrong, or we never completed the attempt |
| `SUPPRESSED` | `SUPPRESS` | Already on the list; the row records that it was skipped |
| `IN_FLIGHT` | none yet | Not an outcome |

Where:

- `intake_ok` - `intake_month` is set and falls inside `config.intake_horizon_months`.
- `money_ok` - `budget_stated` **and** the amount clears `config.budget_floor_paise`; or
  `emi_accepted`, when `config.emi_qualifies_alone` is true. A stated budget with no figure (§3
  allows "agreed to the fee" without naming one) does not clear a floor that is set; it does clear a
  null floor. **The amount is never compared when it is null.**
- `is False` in rule 3 means *known to be false*, not falsy. A null means we never found out, which
  is rule 4's business, not rule 3's.

### 4.2 Why the order is what it is

**Rules 1 and 2 outrank rule 4, deliberately.** If extraction failed but we did capture "remove my
number", that instruction must survive. Losing an opt-out to a parsing gap is the one failure here
with a legal consequence, so the hard signals are evaluated before we admit the extraction was
unreliable. Same fail-closed reasoning as `CLAUDE.md` §4.2.

*An earlier draft of this table put `extraction_errored` at rule 0, above the hard signals, which
produced precisely the loss the paragraph above forbids: an opt-out recorded live, an extraction that
then errored, and a row graded `UNGRADED` / `FIX_DATA` - which §2.2 defines as "a person listens or
re-dials". The prose was right and the table was wrong. Left visible here because the ordering looks
arbitrary until you know what it costs.*

**A hostile contact who also stated a budget is `REFUSED`, not `HOT`.** This is the precedence case
Shivam tests by name (`S3`). It is easy to write a rule set where a rich set of positive fields
outvotes a single negative one; that rule set gets us reported.

**Rule 3 outranks rule 4 because it is a fact we established, not one we failed to.** "They told us
they cannot decide" is knowledge; a failed extraction is the absence of it. Both route to
`FIX_DATA`, so the operational cost of the order is nil - but the grade is a claim about the list,
and it should only be made from something we actually heard.

**Rule 3 tests `is False`, never falsy, and never a missing field.** An earlier draft used
`NOT is_decision_maker`, which fired on `null` - so every call that ended before we could ask graded
`WRONG_PERSON`, and any organisation that dropped `is_decision_maker` from `required_fields` graded
its entire run `WRONG_PERSON` from a settings change with no code change. "We asked and they said no"
and "we never got to ask" are different facts and get different grades.

**`intent == unknown` is `UNGRADED`, not `COLD`.** `unknown` is a declared *value* of the field, not
an absence, so rule 4 does not catch it - and without rule 9 it falls to the bottom and fabricates a
rejection out of a call we could not read. That is the quiet `COLD` §2.2 calls the most important
test in the suite, and it needs its own rule rather than trusting the default.

**Anything with `intent == yes` is at worst `WARM`.** Rule 6 is unconditional after rule 5, so a
contact who said yes with *both* the intake and the money unresolved is still handed to a human. An
earlier draft required "exactly one missing" and dropped the both-missing case to `COLD`.

**Never infer intent from sentiment.** A polite "no thank you, I've already joined Amity" is
`NEUTRAL` sentiment and zero intent. `Sentiment` stays on the row as context for a human and is never
an input to the grade.

**`STILL_DECIDING` reaches `WARM` through `intent`, not through the reason.** A contact who is
deciding is `intent = maybe`, which rule 7 grades `WARM`. The reason code records why for the report;
it never overrides the grade. If an agent records `intent = no` alongside `STILL_DECIDING`, the grade
is `COLD` and the agent's field extraction is what needs fixing.

### 4.3 `grade_reason` is prose, not a rule ID

It is rendered inline on `/app/leads` and read by a caller with sixty seconds before they dial.

- Good: `"Said yes, wants the March intake, budget not discussed."`
- Good: `"Asked not to be contacted again."`
- Bad: `"rule_6_partial"` - means nothing to a caller and nothing to a manager auditing us.

A rep who disagrees with a grade must be able to see, in one line, what we thought we heard. That is
what makes `human_verdict` (§6) an honest measurement rather than a complaint box.


## 5. Worked examples - two per grade

These are the acceptance cases for `S3`. Each shows the fields, the grade, and the `grade_reason`
a caller would read.

### HOT

**H1.** *"Haan sir, March intake chahiye. Fees 12 lakh tak theek hai."*
`intent=yes · intake_month="March 2027" · budget_stated=true · budget_amount_paise=120000000 ·
is_decision_maker=true · identity_confirmed=true`
→ **HOT** · `CALL_NOW` · *"Said yes, wants the March intake, confirmed a budget of ₹12L."*

**H2.** Wants it, cannot pay outright, accepted the instalment terms on the call.
`intent=yes · intake_month="January 2027" · budget_stated=false · emi_needed=true ·
emi_accepted=true · is_decision_maker=true · identity_confirmed=true`
→ **HOT** · `CALL_NOW` · *"Said yes for January, needs EMI and accepted the terms offered."*

### WARM

**W1.** Interested, no timeline.
`intent=yes · intake_month=null · budget_stated=true · is_decision_maker=true ·
identity_confirmed=true`
→ **WARM** · `CALL_NOW` · *"Said yes and confirmed budget, but has not picked an intake."*

**W2.** Interested, wants to be called back Sunday evening.
`intent=maybe · callback_at="2026-09-20T18:30+05:30" · is_decision_maker=true ·
identity_confirmed=true`
→ **WARM** · `CALL_AT` · *"Interested but busy - asked to be called Sunday evening."*

### COLD

**C1.** Answered, heard it out, no interest and nothing to chase.
`intent=no · intent_explicit_no=false · is_decision_maker=true · identity_confirmed=true ·
decline_reason=NO_TIME`
→ **COLD** · `NURTURE` · *"Listened, but says they cannot commit the hours right now."*

**C2.** Wanted something we do not sell.
`intent=no · intent_explicit_no=false · decline_reason=WRONG_PROGRAMME ·
decline_note="wanted a data science diploma, not an MBA" · is_decision_maker=true ·
identity_confirmed=true`
→ **COLD** · `NURTURE` · *"Wanted a data science diploma rather than an MBA."*

### REFUSED

**R1.** *"Mujhe call mat karo dobara."*
`do_not_contact=true · decline_reason=DO_NOT_CONTACT`
→ **REFUSED** · `SUPPRESS` · *"Asked not to be contacted again."*
The suppression row is written **before the call ends** (`A11`), not in a later batch.

**R2.** Already enrolled, said no in words.
`intent=no · intent_explicit_no=true · already_enrolled=true · competitor_named="Amity" ·
decline_reason=ALREADY_ENROLLED_ELSEWHERE`
→ **REFUSED** · `DROP` · *"Already enrolled with Amity - declined outright."*
Note this is a **competitive-loss data point**, and the reason it is worth capturing honestly even
though the lead is dead.

### WRONG_PERSON

**P1.** Spouse answered, could not decide.
`identity_confirmed=false · is_decision_maker=false`
→ **WRONG_PERSON** · `FIX_DATA` · *"Spoke to someone else at this number - not the person on the list."*

**P2.** Right person, but the employer decides.
`identity_confirmed=true · is_decision_maker=false · employer_sponsored=true · intent=yes`
→ **WRONG_PERSON** · `FIX_DATA` · *"Interested, but their employer makes the decision on sponsorship."*
An edge worth watching: this is arguably a B2B lead rather than a bad row. If these accumulate,
raise it - it may deserve its own grade. Left as `WRONG_PERSON` for now rather than inventing a
seventh value before we have seen one real call.

### UNGRADED

**U1.** Extraction returned an error. The conversation may have gone perfectly.
`extraction_errored=true`
→ **UNGRADED** · `FIX_DATA` · *"We could not read this call reliably - needs a person."*
**Never `COLD`.** See §2.2.

**U1b - the precedence case, and the reason rule 4 sits where it does.** The same extraction failure,
but `record_field` caught the opt-out live before it happened.
`do_not_contact=true · extraction_errored=true`
→ **REFUSED** · `SUPPRESS` · *"Asked not to be contacted again."*
Rule 1 fires before rule 4. If the order were reversed this would grade `UNGRADED` / `FIX_DATA`,
which routes a person who asked to be left alone into a queue that re-dials them.

**U2.** Conversation ended before the required fields were reached.
`intent=unknown · is_decision_maker=null · identity_confirmed=true`
→ **UNGRADED** · `FIX_DATA` · *"Call ended before we could establish whether they were interested."*

---

## 6. What the customer is handed

Grading exists to produce two deliverables. Both are P2 work (`Y4`, `Y5`); the shape is fixed here so
the schema serves them.

**The graded lead list.** `HOT` first, then `WARM`, each row carrying `grade_reason`, the collected
fields, and the two-line `handoff_brief` (`A10`) - what they said, what to open with. A caller with
sixty seconds must not have to click through.

**The decline report.** `decline_reason` aggregated across the run, ranked with counts, drilling
through to the leads behind each. *31% already enrolled, 60% of those with one named competitor.
18% blocked on EMI. 12% thought it was full-time.* No human floor produces this, because a caller
working a talk-time quota logs whatever closes the ticket fastest. Our agent has no quota and no
incentive to be economical with the truth, which is the whole reason this data can exist at all.

**`human_verdict`** is the one thing we ask the customer for in return: a single thumbs up or down on
each handed-over lead. Of the leads we graded `HOT` or `WARM`, what share did their rep agree were
qualified? Above roughly 70% there is a business here; at 30% no feature fixes it and the grading
rule is wrong. Without this column every quality claim we make is an opinion.

---

## 7. What is configuration, not code

**We cannot speak to a customer before launch, so parts of this document are educated inference and
some of it will be wrong in January.** Being wrong is survivable; needing a deploy to stop being
wrong is not. The following are per-organisation settings, editable without shipping code:

| Setting | Default | Why it varies |
| ------- | ------- | ------------- |
| `budget_floor_paise` | null (any stated budget qualifies) | A ₹12L programme and a ₹40k certificate do not share a floor |
| `enabled_decline_reasons` | all ten | A floor selling one programme will not see half of them |
| `required_fields` | `intent`, `is_decision_maker`, `identity_confirmed` | Some floors care about eligibility, some do not. **`intent` cannot be removed** - see below. Note that rule 3 reads `is_decision_maker` and `identity_confirmed` whether or not they are required: dropping them means a null, which rule 3 ignores, not a field the rule stops consulting |
| `intake_horizon_months` | 12 | How far ahead an intake still counts as live interest |
| `emi_qualifies_alone` | true | Whether accepted EMI substitutes for a stated budget |

Everything else - the precedence order, the grade values, the meaning of `UNGRADED` - is code, and
changing it is a decision at the Sunday sync, not a setting.

**Three constraints on the settings themselves, because a setting that can disable a fail-closed
property is not a setting.**

1. **`required_fields` has a floor: `intent` is always required and cannot be removed.** Empty it
   entirely and rule 4 stops firing, so every unreadable call falls to rule 9 and is reported as
   `UNGRADED` - which is survivable but makes the whole run look like an extraction failure. The
   floor keeps rule 4 doing the work, so `UNGRADED` keeps meaning what §2.2 says it means.
2. **Writing these settings needs its own permission**, declared in `app/auth/permissions.py` and
   applied with `Depends(RequirePermission(...))`. Never an inline role comparison in a handler
   (`CLAUDE.md` §4b).
3. **Every write is audited** - who changed which threshold, when, and from what to what. A run
   graded under one configuration and read under another is otherwise unexplainable, and these
   settings decide what a customer is billed for as a qualified lead.

The table these live in is tenant-scoped, so it gets all four parts in one revision per
`CLAUDE.md` §4b. Note that `call_outcomes` and this table are both invisible to Alembic's
autogenerate (`CLAUDE.md` §6), so the RLS is hand-authored - which is the standing way a table ships
with three parts of four.

---

## 8. Migration from `Disposition`

Additive, in this order. `H7` owns the schema half.

1. Add the new columns beside `disposition`. Nothing reads them yet.
2. Backfill what can be inferred. `ESCALATED` → `SPOKE` + `UNGRADED`; `UNREACHABLE` → the matching
   `CallResult` with no grade; `AUTO_CLOSED` → `SPOKE` + `UNGRADED`. **Do not invent grades for
   historical rows** - they were produced by a rule that was asking a different question, and a
   fabricated `COLD` in the backfill poisons the first decline report.
3. Ship `grade_lead()` and the rewritten `triage.py` (`A3`, `A4`) writing both old and new columns.
4. Move every reader across - API, repositories, web, docs.
5. Drop `disposition` in a later revision, once `grep -rn "disposition" apps/` is clean.

Every new tenant-scoped table gets all four parts in the same revision, per `CLAUDE.md` §4b, and a
cross-tenant test that hits the database directly.

---

## 9. Open questions, to settle with real calls in January

Listed rather than guessed at, so that January's corrections are deliberate.

1. **Is `employer_sponsored` + `is_decision_maker=false` really `WRONG_PERSON`?** It may be a B2B
   lead worth its own path. Watch the volume before adding a grade.
2. **Does `WARM` need splitting?** "Yes but no date" and "yes but no money" are different work for a
   caller. One grade with a clear `grade_reason` may be enough. Two grades may be better.
3. **How long does a `HOT` lead stay hot?** A row graded on Monday may be worthless by Friday on a
   list this perishable. There is no decay rule here yet, deliberately.
4. **Is `LANGUAGE_BARRIER` a decline or a retry?** If we could have held the call in Telugu, it is
   our failure and the lead should be re-dialled, not reported as a no.
5. **Does the floor trust a grade it cannot override?** A manual re-grade control may be necessary for
   adoption. It also contaminates `human_verdict` as a measurement. Decide before building it.

---

## References

- `CLAUDE.md` §3 (single responsibility, substitutability), §4.2 (fail closed), §4.3 (money as
  integers), §4b (tenant table rules)
- `apps/api/app/domain/entities.py` - `Disposition`, `Sentiment`, `CallOutcome`
- `apps/api/app/domain/triage.py` - the current rules, to be replaced by `A4`
- `apps/api/app/domain/collection.py` and `apps/voice-runtime/app/collection.py` - field collection,
  and the recorded-beats-recovered rule this spec depends on
- `docs/MARKET_RESEARCH.md` - **does not exist yet.** It is task `S1`/`M1` and is where the
  `DeclineReason` values are meant to be sourced from. Until it lands, §2.4's values are reasoned
  inference, not evidence. Treat them accordingly, and see §9.
