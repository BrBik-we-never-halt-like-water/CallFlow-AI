# Usage pricing: the decisions that need an owner

> **Status: proposal for review. Nothing here is built.** The mechanism is designed
> (`docs/BILLING.md` and the implementation plan cover it); every *number* below is a
> placeholder derived from our own cost catalogue, not a researched price. §9 lists the seven
> decisions that need a named owner before any of this bills a customer.

Today a plan grants **a count of calls per day**. This proposes replacing that with a
**credit balance in money**, spent per connected minute at a rate that depends on whose API
keys ran the call.

All figures ₹, converted at **₹88 = $1**. Source: `apps/api/app/integrations/ai_providers/catalog.py`,
whose own docstring calls it *"a best-effort, human-written estimate from public
pricing/marketing pages"* — good enough to size a decision, **not** good enough to bill
against without review (that is decision 6).

---

## 1. The fact everything follows from

A voice call's cost varies **23× in vendor spend** — **12.4× all-in** once LiveKit is
included — depending only on which models the customer picked.

| pipeline | vendor cost/min | + LiveKit | our cost/min |
|---|---|---|---|
| cheapest available | ₹0.54 | ~₹0.50 | **~₹1.04** |
| median | ₹2.96 | ~₹0.50 | **~₹3.46** |
| most expensive | ₹12.43 | ~₹0.50 | **~₹12.93** |

Both multiples are quoted deliberately: 23× is the spread we are exposed to on the vendor
bill, 12.4× is the spread we have to price. The flat LiveKit floor is what separates them.

A call count charges these the same. So does any single per-minute rate. Both are wrong in
opposite directions: we lose money on the premium end and overcharge the cheap end into
churn.

### The counter-intuitive part: TTS dominates, not the LLM

This is worth internalising because it inverts the usual instinct.

| leg | range ₹/min | median |
|---|---|---|
| STT | 0.06 – 1.47 | 0.52 |
| **LLM** | **0.003 – 3.30** | **0.068** |
| **TTS** | **0.48 – 7.67** | **2.38** |

A phone conversation carries very few tokens — the LLM figures above assume **1,500 input +
200 output tokens per minute**, which is our own existing assumption from
`agent-metrics.tsx:30`, not a measured figure (nothing measures tokens today; see §11). At that
rate the model is nearly free: `gpt-4o-mini` costs **₹0.03/min**, and even `claude-sonnet-4.5`
is **₹0.66/min**. Meanwhile `elevenlabs-turbo` alone is **₹7.67/min** — more than twice the
entire median pipeline.

If that token assumption is wrong the whole LLM column moves proportionally, and **the
premium tier is genuinely exposed**:

| tier | tokens would have to be this much higher for the LLM to overtake TTS |
|---|---|
| economy | 30× — safe |
| standard | 10× — safe |
| **premium** | **2.3× — not safe** |

A verbose system prompt, a long transcript replayed as context, or a reasoning model emitting
hidden tokens could plausibly double real usage. So `claude-opus-4.1` at a genuine 3,000
tokens/minute would cost us **₹6.60/min**, not ₹3.30 — and the premium LLM add-on of ₹4.60
would then be underwater on its own.

**This is the single number most worth measuring first**, and measuring it is cheap: the voice
worker's framework already collects per-call token counts and we discard them (§10).

**Consequence for positioning:** below the premium bin, "which model" is close to a free
choice — so we should let customers pick a good one rather than gating intelligence. **Voice
is the expensive selection**, and that is where tiering earns its keep. Any pricing that
treats the LLM as the premium axis is optimising the wrong variable for two of the three
tiers.

---

## 2. Why a flat rate cannot work, in one line

Set the managed rate at **₹3.50/min** (our median cost):

- customer on `groq-whisper + llama-3.1-8b + rime` costs us ₹1.04 → we make ₹2.46/min
- customer on `azure-stt + claude-opus + elevenlabs-turbo` costs us ₹12.93 → **we lose ₹9.43/min**

One premium customer at 500 min/month loses ₹4,715. There is no rate that fixes this,
because the spread is inside the thing we are pricing.

---

## 3. Proposed model: platform fee + per-leg tier

Every voice agent already has four visible parts in the builder — **Hears, Thinks, Speaks,
Dials**. The rate is worked out from exactly those, by asking one question of each: *whose
key paid for it?*

```
                        ONE CALL  ·  4 minutes
                                 │
              ┌──────────────────┴──────────────────┐
              │  Whose API key ran each part?       │
              └──────────────────┬──────────────────┘
                                 │
      ┌──────────────┬───────────┼───────────┬──────────────────┐
      │              │           │           │                  │
    HEARS          THINKS      SPEAKS      DIALS          ORCHESTRATION
    (STT)          (LLM)       (TTS)     (carrier)      (always ours)
      │              │           │           │                  │
   their key      their key    OUR key    their own          ours
      │              │           │        Twilio               │
      ▼              ▼           ▼           ▼                  ▼
    ₹0.00          ₹0.00      ₹10.75    never charged        ₹1.50
      │              │           │       (they pay             │
      │              │           │        Twilio direct)       │
      └──────────────┴─────┬─────┴──────────────────────────────┘
                           │
                    ₹12.25  per minute
                           │
                      × 4 minutes
                           ▼
                  ₹49  taken from credit
```

Same call, if they had also brought their own voice:

```
    ₹0.00 + ₹0.00 + ₹0.00 + ₹1.50  =  ₹1.50/min  →  ₹6 for the call
                                                     (was ₹49)
```

That difference is the point of the model. Bringing your own keys is visibly, arithmetically
cheaper — and the builder can show it at the moment a model is selected, not on a bill three
weeks later.

**Per-leg, not per-pipeline**, because mixing is normal and expected — a customer's own
Deepgram key with our ElevenLabs is a realistic setup, and a pipeline-level tier would
either overcharge or undercharge it.

```
  rate/min  =  platform fee          (everyone)
             + STT tier add-on       (only if OUR key)
             + LLM tier add-on       (only if OUR key)
             + TTS tier add-on       (only if OUR key)
```

A customer bringing all their own keys pays the **platform fee alone**, and can see on the
invoice that they did. That is the mechanism that makes bring-your-own-keys feel like a
saving rather than a chore.

### Tier bins, derived from the catalogue

Boundaries chosen at natural gaps in the real data, not round numbers.

| tier | STT | LLM | TTS |
|---|---|---|---|
| **economy** | ≤ ₹0.25<br>`groq-whisper`, `gladia`, `assemblyai` | ≤ ₹0.05<br>~20 models incl. `gpt-4o-mini`, `gemini-2.0-flash`, `llama-3.3-70b`, `deepseek-chat` | ≤ ₹1.50<br>`rime`, `openai-tts`, `azure-tts`, `sarvam` |
| **standard** | ≤ ₹0.70<br>`deepgram`, `sarvam`, `openai-whisper`, `speechmatics` | ≤ ₹0.25<br>`gpt-5-mini`, `gemini-2.5-flash`, `claude-haiku-4.5`, `o4-mini`, `deepseek-r1` | ≤ ₹2.60<br>`cartesia`, `deepgram-aura`, `google-tts`, `playht`, `lmnt` |
| **premium** | > ₹0.70<br>`google-stt`, `azure-stt` | > ₹0.25<br>`gpt-5`, `gpt-4o`, `gemini-2.5-pro`, `claude-sonnet-4.5`, `claude-opus-4.1` | > ₹2.60<br>`elevenlabs`, `elevenlabs-turbo` |

**Note the economy LLM bin holds ~20 models including `gpt-4o-mini` and `gemini-2.0-flash`.**
That is not a compromise tier — it is most of what anyone would actually pick for a phone
call.

### What we pay at the worst case in each bin

The number that matters, because it is what a customer can cost us while staying in-tier.

| tier | STT | LLM | TTS | + LiveKit | **our worst case** |
|---|---|---|---|---|---|
| economy | 0.25 | 0.05 | 1.50 | 0.50 | **₹2.30** |
| standard | 0.70 | 0.25 | 2.60 | 0.50 | **₹4.05** |
| premium | 1.47 | 3.30 | 7.67 | 0.50 | **₹12.94** |

### Proposed card — placeholders at worst-case × 1.4

The 1.4 is the one lever. Change it and every number below moves; that is decision 3.

| | economy | standard | premium |
|---|---|---|---|
| STT add-on | ₹0.35 | ₹1.00 | ₹2.05 |
| LLM add-on | ₹0.07 | ₹0.35 | ₹4.60 |
| TTS add-on | ₹2.10 | ₹3.65 | ₹10.75 |

**Platform fee: ₹1.50/min** — covers orchestration, LiveKit media, the safety guards, triage,
transcripts and storage. LiveKit sits inside it rather than as a line item because it is our
cost on every call regardless of keys.

### Worked examples

| setup | rate/min | our cost | margin |
|---|---|---|---|
| all own keys | **₹1.50** | ₹0.50 | ₹1.00 |
| economy on our keys | 1.50 + 0.35 + 0.07 + 2.10 = **₹4.02** | ₹2.30 | ₹1.72 |
| own STT + LLM, our ElevenLabs | 1.50 + 10.75 = **₹12.25** | ₹8.17 | ₹4.08 |
| all premium on our keys | 1.50 + 2.05 + 4.60 + 10.75 = **₹18.90** | ₹12.94 | ₹5.96 |

At 500 minutes/month a BYO customer pays **₹750** and an all-premium one **₹9,450**.

**Worth surfacing as a weakness:** that is a **12.6× spread in price** against a **12.4×
spread in cost** — so the flat platform fee compresses the range almost not at all. If a
tighter headline range matters for selling (and "from ₹750 to ₹9,450" is a hard price list to
put on a page), the only levers are a materially higher platform fee or thinner premium
margin. Both are decision 1 and decision 3.

Note also that absolute margin is **thinnest at economy** (₹1.72/min) and **fattest at
premium** (₹5.96/min). That is arguably backwards: premium customers are the ones with budget,
and economy is where volume lives. A flat multiplier is simple but not obviously the right
shape.

---

### How credit actually moves

A call's cost is not known until it ends, so credit is *held* first and settled after — the
same way a card authorisation works at a hotel.

```
   Credit: ₹850
       │
       │   run starts, first contact
       ▼
   ┌────────────────────────────────────────┐
   │ HOLD  a typical call at this rate      │   Credit ₹850
   │       3 min × ₹12.25  =  ₹37           │   Held    ₹37
   └────────────────────┬───────────────────┘   Usable  ₹813
                        │
              ┌─────────┴─────────┐
              │                   │
        answered                nobody picked up
              │                   │
              ▼                   ▼
   ┌──────────────────┐   ┌──────────────────┐
   │ talked 4 min     │   │ RELEASE the hold │
   │ SETTLE ₹49       │   │ nothing spent    │
   │ release the ₹37  │   │                  │
   └────────┬─────────┘   └────────┬─────────┘
            ▼                      ▼
      Credit ₹801              Credit ₹850
```

Three rules this has to obey, and they are all deliberate:

- **A call already talking to a person is never cut off for money.** If it runs long past
  its hold, the balance goes slightly negative and we absorb it. Cutting a live conversation
  mid-sentence over ₹12 is worse for everyone.
- **A call that never connects costs nothing.** The hold is released in full.
- **Replaying the same settlement changes nothing.** The worker can retry its callback; the
  ledger is keyed so a second identical settle is ignored rather than double-charging.

---

## 4. The comparison: both sides, and where the money goes

Same call, same models, same customer. Only the keys differ.
Pipeline: `deepgram` + `gpt-5-mini` + `cartesia` — all three land in **standard**.

```
                   ONE CALL  ·  4 minutes  ·  identical agent both sides
   ┌──────────────────────────────────────┬──────────────────────────────────────┐
   │  A.  THEIR OWN KEYS                  │  B.  OUR KEYS                        │
   ╞══════════════════════════════════════╪══════════════════════════════════════╡
   │  THEY PAY US                         │  THEY PAY US                         │
   │    platform fee          ₹1.50       │    platform fee          ₹1.50       │
   │                                      │    STT  standard         ₹1.00       │
   │                                      │    LLM  standard         ₹0.35       │
   │                                      │    TTS  standard         ₹3.65       │
   │                          ──────      │                          ──────      │
   │                          ₹1.50 /min  │                          ₹6.50 /min  │
   │                       = ₹6 per call  │                       = ₹26 per call │
   ├──────────────────────────────────────┼──────────────────────────────────────┤
   │  THEY ALSO PAY, DIRECT               │  THEY PAY NO VENDOR                  │
   │    Deepgram              ₹0.68       │    we hold the keys, so their        │
   │    OpenAI                ₹0.07       │    vendor spend is ₹0                │
   │    Cartesia              ₹2.53       │                                      │
   │                          ──────      │                                      │
   │                          ₹3.28 /min  │                          ₹0.00       │
   ├──────────────────────────────────────┴──────────────────────────────────────┤
   │  Twilio is their own account on BOTH sides. It never flows through us.      │
   ╞══════════════════════════════════════╤══════════════════════════════════════╡
   │  COSTS THEM       ₹4.78 /min         │  COSTS THEM       ₹6.50 /min         │
   ╞══════════════════════════════════════╪══════════════════════════════════════╡
   │  WE RECEIVE              ₹1.50       │  WE RECEIVE              ₹6.50       │
   │  we pay out                          │  we pay out                          │
   │    LiveKit              −₹0.50       │    LiveKit              −₹0.50       │
   │                                      │    the three vendors    −₹3.28       │
   │                          ──────      │                          ──────      │
   │  WE KEEP                 ₹1.00 /min  │  WE KEEP                 ₹2.72 /min  │
   └──────────────────────────────────────┴──────────────────────────────────────┘

     ₹1.72 /min is the same number three ways:
       what they save by bringing keys · what we earn extra when they don't ·
       our markup on managed vendors

     Both choices are rational, and that is the design working.
     Nobody is punished for bringing keys; nobody is punished for not bothering.
```

### The same thing over a month, at 500 minutes

| | they pay us | they pay vendors | **their total** | we keep |
|---|---|---|---|---|
| **their keys** | ₹750 | ₹1,639 | **₹2,389** | ₹500 |
| **our keys** | ₹3,250 | ₹0 | **₹3,250** | ₹1,361 |

Read the two right-hand columns together: managed costs them **₹861 more** and earns us
**₹861 more**. There is no hidden third party — the gap is exactly the markup.

---

## 5. How a plan is actually charged

Two separate money movements, both through Dodo. **The subscription is fixed. Usage is
prepaid, never invoiced in arrears.**

```
   ┌─ 1. SUBSCRIPTION ─ fixed, monthly, auto-debit ───────────────────────┐
   │                                                                      │
   │   Starter   ₹999 / month   ──▶  grants ₹850 credit on renewal        │
   │                                 (unused credit does NOT roll over)   │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
   ┌─ 2. CREDIT ─ spent per connected minute at the call's own rate ──────┐
   │                                                                      │
   │   ₹850  ████████████████████░░░░░░░░  ₹610 spent · ₹240 left         │
   │                                                                      │
   │   their keys  ₹1.50/min → ₹850 goes ~567 min                         │
   │   our keys    ₹6.50/min → ₹850 goes ~131 min                         │
   └──────────────────────────────────────────────────────────────────────┘
                                    │
                       credit runs out mid-month
                                    ▼
   ┌─ 3. TOP-UP ─ one-time purchase, optional ────────────────────────────┐
   │                                                                      │
   │   [ Top up ₹500 ]  ──▶  Dodo one-time checkout  ──▶  credit granted  │
   │                          valid 365 days                              │
   └──────────────────────────────────────────────────────────────────────┘

   Runs stop when credit is exhausted and say so. A call already talking to
   a person always finishes — we absorb the overrun rather than cut it off.
```

**So a monthly bill is:** `₹999 subscription + whatever top-ups they chose to buy`. Nothing
is ever charged after the fact, and no invoice can surprise them — the worst case is that
runs stop.

**The trade-off to be explicit about:** this makes revenue lumpy and puts a friction step
(buy a top-up) in the middle of a customer's busy week. The alternative — bill overage in
arrears — is smoother for them and riskier for us, and it would make the existing pricing-FAQ
promise *"you will never get a bill that depends on how busy last month was"* false. Prepaid
keeps that promise.

---

## 6. What is never charged

| leg | who pays | in our deduction? |
|---|---|---|
| Twilio / carrier | **the customer's own account** | **never** |
| STT/LLM/TTS on the customer's keys | **the customer**, billed by that vendor | **no** — platform fee only |
| STT/LLM/TTS on our keys | **us** | yes, at the tier rate |
| LiveKit media | **us** | yes, inside the platform fee |

Deducting carrier spend or a customer's own vendor spend would charge them twice for money
they have already paid someone else. Their Twilio CDR does carry a price and we already store
`provider_call_id`, so we could **show** them their carrier spend as a convenience — but it
must never touch their credit.

---

## 7. Free tier exposure

A free organisation pointing at `azure-stt + claude-opus-4.1 + elevenlabs-turbo` costs us
**₹12.94/min** against zero revenue. At 20 calls/day averaging 3 minutes that is
**₹776/day, ~₹23,000/month, per free signup.**

**Proposal: Free may use our keys only at the economy tier.** Any tier on their own keys is
fine. Worst case becomes ₹2.30/min, and a ₹100 credit grant caps total exposure at ₹100 per
free org regardless of what they pick.

This keeps first-run working with no "go get a Deepgram key" friction, which matters — the
alternative is a signup that cannot place a single call until the customer has opened an
account with a third party.

Enforced twice: at agent save, and **again at dial time**, because an agent configured on
Starter must not keep dialling premium after a downgrade to Free.

---

## 8. The unit customers see

**Money, not minutes.** With a 23× spread, "500 minutes included" would mean four different
things depending on the pipeline, so minutes cannot be the headline.

Proposal: plans include **credit in ₹**, and minutes appear as a live per-customer estimate:

```
  ₹530 of ₹850 left   ·   ~132 min at your current rate
```

The estimate adapts to what they actually run, and it makes the BYO saving legible without
anyone doing arithmetic: the same ₹530 reads as ~353 minutes on their own keys.

---

## 9. The decisions

Each needs a named owner. My recommendation is given, with what it trades away.

| # | decision | recommendation | trade-off |
|---|---|---|---|
| 1 | **Platform fee** — ₹1.50/min | Keep, pending competitor check | It is the *entire* margin on BYO customers. If most customers are BYO, this single number is the business. Too low and BYO is unprofitable; too high and BYO stops being attractive, pushing everyone onto our keys where cost is variable |
| 2 | **Tier boundaries** | As §3 — chosen at real gaps in the data | Economy LLM at ≤₹0.05 includes `gpt-4o-mini`, which is generous and probably right; a tighter bin would raise margin but make economy feel punitive |
| 3 | **Margin multiplier** — 1.4× worst case | 1.4× | The one lever over the whole card. Note margin is thin in *absolute* terms at economy (₹1.72/min) and fat at premium (₹5.96/min) — arguably backwards, since premium customers are the ones with budget. A flat multiplier is simple; per-tier multipliers extract more |
| 4 | **"At cost" or "with margin"** | **Say "our rates", never "at cost"** | We are charging worst-case × 1.4, which is not at cost. Claiming otherwise is a trust problem the first time a customer prices it themselves. Either publish the card as our rates with no cost claim, or genuinely pass through and take the variance |
| 5 | **Free tier** | Economy keys only, ₹100 credit | Bounds exposure to ₹100/org. The alternative — BYO-only — is cheaper still but breaks first-run |
| 6 | **Rate card ownership** | Named owner + quarterly review; **fail closed to `premium`** on unknown providers | The catalogue is self-described as an estimate from marketing pages. Vendor prices move. Stale card = we absorb the difference silently. An unknown model must bill as premium, never economy |
| 7 | **Measure tokens before pricing premium** | Wire the worker's usage collector first | Not a pricing decision but a prerequisite for one: the premium LLM add-on is only safe if ~1,700 tokens/min holds, and it breaks at 2.3× (§1). This is days of work, not weeks, and it de-risks the one number the model is most sensitive to |

### Also worth a decision, lower stakes

- **Included credit per plan.** With money as the headline this is the number on the pricing
  page. Sizing it needs decisions 1–3 settled first.
- **Top-up expiry.** Proposed 365 days for purchased credit, matching how prepaid credit
  works at OpenAI/AWS; plan credit does not roll over.
- **The AI-key count limit** currently exists as packaging (`docs/BILLING.md` §1). Under this
  model a customer's own key *reduces* our cost, so capping how many they connect is
  actively counterproductive. Recommend removing it.

---

## 10. What is not being proposed

- **Per-token billing.** Not needed under tiers, and it produces unpredictable bills, which
  customers dislike more than a slightly higher fixed rate. We will still *measure* tokens
  (the voice worker's framework already collects them and we discard it) — but for margin
  analysis, to check whether these tiers hold, not to charge.
- **Charging for the carrier.** Their own Twilio account on both sides — see §6.
- **Using the payment gateway's own credit system.** Its deduction is asynchronous, so it
  cannot gate a dial; a run of 100 contacts would pass the check 100 times before the balance
  moved.

---

## 11. One thing to know about the state of the code

`POST /api/v1/runs` **cannot currently place a call** — the run route never passes a trunk or
a voice agent to the runner, so every contact is skipped with "no connected number". So there
is no historical duration data to calibrate against, and no way to validate any of these
numbers against real traffic yet.

This does not block the decisions above — they are commercial, and the mechanism can be built
and unit-tested regardless. It does mean **every number here stays an assumption until
dialling works**, which is the strongest argument for putting the card in a database table
rather than in code: changing it should be a data change, not a deploy.
