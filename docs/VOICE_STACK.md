# Voice stack - how we choose STT, TTS and the call LLM

**Status: TTS and the call LLM are decided. STT is not - it awaits measurement.** Task `A2` on the
P0 roadmap.

> **Read this first.** §6.1 (TTS: Sarvam) and §6.2 (LLM: OpenRouter, fastest models) are decisions,
> taken 2026-09-13. **§6.3 is not.** STT is chosen by running §4's protocol and filling in §5's
> scoring sheet, and **nothing in §5 is measured yet.**
>
> The done-when for `A2` is that scoring sheet filled with real numbers from our own audio, and a
> named STT. The deciding number is **field error rate, not word error rate** - §2.1 explains why.
> A stack chosen from vendor marketing rather than from our own recordings is how we discover in
> December that the agent cannot understand a caller in Indore.
>
> **Task ids here (`A2`, `A6`, `A7`, `D7`, `D8`, `H10`, `H13`, `M11`, `R3` and the rest) are not
> defined in this repo.** They refer to
> the plan of record, which lives outside it. Stable labels, nothing more - the same caveat
> `CLAUDE.md` §1 carries for `FEATURES.md`'s `F<n>` numbers.

---

## 1. The constraint that decides everything

**D7: cloud STT, TTS and LLM only. Nothing self-hosted, this year.**

Two VMs at 4 GB each. Whisper plus a TTS model plus an LLM does not coexist with serving live audio
in that envelope - and when it fails it fails mid-call, in front of a stranger, not in a test. VM2 is
sized for 8-12 concurrent calls running *thin* workers that stream audio to cloud APIs. Every
candidate below is therefore an API, and "we could self-host this one cheaply" is not a point in its
favour until the hardware changes.

This also means **cost scales linearly with minutes**, which is why `H13`'s per-leg cost breakdown is
a gate input for pricing and not a nice-to-have.

---

## 2. The deciding criterion: Hinglish, not English

Every vendor publishes English benchmarks and most publish a Hindi number. **Neither predicts our
workload.**

The real audio is code-switched mid-sentence, from a mobile, often on speakerphone, in a room with
other callers:

> *"Haan sir, main abhi ek private company mein work kar raha hoon, around **five years experience**
> hai. Fees kitni hogi total, aur **EMI option** available hai kya?"*

An STT that scores well on clean Hindi and well on clean English can still break on the switch point,
and the switch point is where our fields live - `work_experience_years`, `emi_needed`,
`budget_amount_paise`. A transcript that garbles "five years" into "fine years" costs us an eligibility
field; one that drops "EMI" costs us a `DeclineReason`.

**So the benchmark is our own audio, scored on the fields we extract - not on overall WER.**

### 2.1 Field-weighted error is the number that matters

Overall WER treats "sir" and "twelve lakh" as equally important. They are not. Score two numbers:

- **WER** - overall word error rate, for comparison with published figures.
- **FER (field error rate)** - of the extraction fields present in the audio, what share came out
  wrong or missing. **This is the deciding number.** A stack with worse WER and better FER wins.

---

## 3. The three legs, and what we need from each

### 3.1 STT - the leg that decides whether this works at all

Requirements, in order:

1. **Streaming, with partial results.** Batch transcription is unusable - we cannot wait for the
   caller to stop speaking before the LLM starts thinking.
2. **Code-switched Hindi/English in one stream**, without being told which language a given utterance
   is in.
3. **Endpointing we can tune.** Indian callers pause mid-sentence more than the default VAD settings
   assume. Aggressive endpointing makes the agent interrupt; lazy endpointing makes it feel dead.
4. **Numerals and currency handled sensibly.** "बारह लाख" and "12 lakh" and "twelve lakhs" must all
   reach the extractor as something parseable.
5. Telephony-grade audio: 8 kHz narrowband, mobile codecs, background noise.

**Candidates to test** - verify current capability and pricing directly, this market moves monthly:

| Candidate | Why it is on the list | What to watch for |
| --------- | --------------------- | ----------------- |
| **Sarvam** | Built for Indic languages and code-switching specifically; Indian company, so latency from an Indian region should be good. There is already an adapter at `app/integrations/ai_providers/sarvam.py` | Streaming maturity and concurrency limits |
| **Deepgram** | Strong streaming, tunable endpointing, well-documented telephony path | Hinglish switch points - test, do not assume |
| **Google STT** | Mature Hindi support and explicit multi-language configuration | Cost at volume; latency from an Indian region |
| **AssemblyAI** | Good streaming and formatting | Indic code-switching is the open question |

Test at least **Sarvam and one Western vendor** - that contrast is the point of the exercise.

### 3.2 TTS - the leg that decides whether they stay on the line

1. **Low time-to-first-audio.** More important than the audio being beautiful. Silence after the
   caller stops is what makes a person say "hello? hello?" and hang up.
2. **Streaming synthesis**, so we speak while still generating.
3. **A voice that does not sound foreign to the listener.** An Indian-accented Hindi/English voice.
   A polished American voice reading Hinglish is worse than a plainer local one.
4. **Correct pronunciation of Indian names, numbers and currency.** "Shubhankar", "₹12,50,000",
   "M.Tech".
5. **Interruptible.** When barge-in fires, synthesis must stop immediately, not finish its sentence.

Candidates: **Sarvam**, **ElevenLabs**, **Cartesia**, **Google**. Judge on time-to-first-audio and on
whether a native speaker finds the voice natural - not on demo-page polish.

### 3.3 LLM - two jobs, probably two models

**In the call loop:** must be fast above all. Time-to-first-token is the number; total tokens barely
matter because turns are short. A smaller, cheaper, faster model is usually the right answer, and the
conversation quality difference on a four-question script is smaller than the latency difference.

**Post-call extraction:** accuracy over speed. Nobody is waiting. This is where the transcript becomes
the fields in `GRADING.md` §3, and an extraction error becomes a wrong grade.

**A split is likely correct: a fast small model in the loop, a stronger one for extraction.** Prove it
by measuring FER with both, rather than assuming.

Routing goes through the existing OpenRouter client (`app/integrations/openrouter/client.py`), and
none of it is exposed in the UI - `PLATFORM_PIVOT_PLAN.md` ADR-7 carries that decision and its
reasoning.

---

## 4. The test protocol

Run this before writing pipeline code against any vendor. It is a day of work and it decides an
architecture property that cannot be fixed later.

### 4.1 Build the corpus - 20 clips

Twenty clips of 30-90 seconds each, recorded over a real phone line, not a laptop microphone.

- **12 clips**: teammates and their contacts role-playing a candidate answering an edtech call, in
  natural Hinglish. Use the `GRADING.md` §5 worked examples as scripts so every extraction field is
  exercised at least twice.
- **4 clips**: deliberately hard - speakerphone, background noise, a second person talking, a poor
  signal.
- **2 clips**: a strong regional accent from outside the Hindi belt.
- **2 clips**: someone declining and asking not to be called again. **These are the safety-critical
  ones** - `do_not_contact` must survive every stack we would consider, because losing an opt-out to a
  transcription error is the one failure with a legal consequence (`GRADING.md` §4.2).

Transcribe all twenty by hand. That hand transcript is ground truth, and it is also the answer key for
which fields each clip contains.

> **Consent and storage.** Everyone recorded consents in the recording itself. The corpus holds no
> real customer audio and no real personal data - use fictional names and the reserved test numbers
> (`+1 555 0100-0199`, `CLAUDE.md` §7). Keep it out of git; store it where the team can reach it and
> note the location in `ISSUES.md`.

### 4.1b Lay the corpus out so the scorer can read it

`scripts/score_stt.py` computes §5's numbers. It scores *transcripts*, so a
candidate needs no API key and no SDK - a vendor that only offers a web console
can still be measured. Layout:

```
corpus/
  clip01.txt              the hand transcript - ground truth
  clip01.fields.json      the phrases from GRADING.md §3 present in this clip
  candidates/
    sarvam/clip01.txt     what that vendor returned
    deepgram/clip01.txt
```

A `.fields.json` is a flat object mapping each field to **the phrase as spoken**,
not the parsed value - this measures the transcript, not the extractor:

```json
{"work_experience_years": "five years",
 "budget_amount_paise": "12 lakh",
 "do_not_contact": "mujhe call mat karo"}
```

`do_not_contact` is the key the opt-out check looks for, so the two refusal clips
from §4.1 must carry it.

Then:

```
python scripts/score_stt.py corpus/
```

It prints §5's table ready to paste, and **exits non-zero when every candidate is
disqualified** - so it can gate the decision rather than only inform it.

### 4.2 What each number means



The scorer computes all of these. They are spelled out because a number nobody
can explain is a number nobody should act on:

1. **WER** against the hand transcript.
2. **FER** - for each extraction field genuinely present in the audio: correct, wrong, or missing.
   This is the deciding number.
3. **Opt-out recall** - of the two refusal clips, did `do_not_contact` survive? **Anything below 100%
   disqualifies the stack**, regardless of every other number.
4. **Streaming latency** - time from end-of-speech to final transcript.
5. **Numeral handling** - a separate tally. Currency and durations are where our fields live.

### 4.3 Then measure the whole chain

Once an STT is chosen, measure the assembled pipeline on live calls (`A6`, `A7`):

| Leg | Measure | Budget |
| --- | ------ | ------ |
| STT finalise | End of speech to final transcript | ~300 ms |
| LLM first token | Transcript in to first token out | ~400 ms |
| TTS first audio | Text in to first audio frame | ~300 ms |
| Network and jitter | Round trip, VM2 to vendor and back | ~200 ms |
| **Total silence heard** | End of their sentence to start of ours | **under ~1,200 ms** |

Above roughly 1.2 seconds of silence, an Indian mobile caller typically starts talking again - and
once both sides are talking, the call is lost. **Report p50 and p95; p95 is the one that matters**,
because p95 is how often it happens, not how well it usually goes.

**If p95 breaks the budget, change the stack in P1.** Latency is an architecture property, not a
tuning problem, and it does not get better in P4 (roadmap R3).

---

## 5. Scoring sheet - fill this in

**Nothing below is measured yet.** Run `python scripts/score_stt.py corpus/`, paste its table over
the STT rows, fill the TTS and LLM rows by hand, and commit the result. That commit closes `A2`.

A missing transcript is scored as total loss rather than skipped, and a candidate that loses a single
opt-out is marked DISQUALIFIED and sorted last however good its FER - §6.3's kill criteria are
enforced by the tool, not left to whoever reads the table.

### STT

| Candidate | WER | **FER** | Opt-out recall | Finalise p50 | Finalise p95 | Numerals | Cost / min |
| --------- | --- | ------- | -------------- | ------------ | ------------ | -------- | ---------- |
| Sarvam | - | - | - | - | - | - | - |
| Deepgram | - | - | - | - | - | - | - |
| *(third, if run)* | - | - | - | - | - | - | - |

### TTS

| Candidate | First audio p50 | First audio p95 | Naturalness (1-5, native speaker) | Indian names | Interruptible | Cost / min |
| --------- | --------------- | --------------- | --------------------------------- | ------------ | ------------- | ---------- |
| Sarvam | - | - | - | - | - | - |
| ElevenLabs | - | - | - | - | - | - |
| *(third, if run)* | - | - | - | - | - | - |

### LLM

| Role | Model | First token p50 | First token p95 | FER on extraction | Cost / call |
| ---- | ----- | --------------- | --------------- | ----------------- | ----------- |
| In-call | - | - | - | n/a | - |
| Extraction | - | n/a | n/a | - | - |

### The decision

| | |
| --- | --- |
| **Chosen stack** | *(to fill in)* |
| **Measured total silence, p95** | *(to fill in)* |
| **Verdict** | *(acceptable / the stack changes)* |
| **Cost per minute, all legs** | *(feeds `H13` and `M11`)* |
| **Decided on** | *(date)* |

---

## 6. The stack

Two legs are decided. One is a measured choice against a fixed criterion.

### 6.1 TTS - Sarvam · decided 2026-09-13

**Sarvam.** Indian-language voices from an Indian provider, which is what this leg needs more than
polish: a voice that says "M.Tech", "Shubhankar" and "₹12,50,000" the way a listener in Indore expects
beats a more natural-sounding voice that does not. Regional proximity should also help
time-to-first-audio, which is the number that actually matters here.

Still measure `first_audio_p50/p95` and interruptibility in §5 - not to reconsider the vendor, but
because those figures feed the latency budget and the barge-in implementation. **If time-to-first-audio
p95 breaks the budget, that is a finding to raise, not a silent problem to live with.**

### 6.2 LLM - OpenRouter, fastest models · decided 2026-09-13

**OpenRouter, selecting for speed in the call loop.** Time-to-first-token is the number; total tokens
barely matter on a four-question script. The conversation-quality gap between a fast small model and a
large one is smaller than the latency gap, and latency is the thing that ends calls.

Still likely correct to split the two jobs - a fast model in the loop, a stronger one for post-call
extraction, where nobody is waiting and accuracy decides the grade. **Measure FER both ways (§5) before
assuming the split is worth the second vendor call.**

Routing goes through `app/integrations/openrouter/client.py`, internally only - see
`PLATFORM_PIVOT_PLAN.md` ADR-7, which carries the decision and its reasoning.

### 6.3 STT - the one that must be measured

**The criterion, fixed: the fastest STT with the highest accuracy on Indian speech.** Not on English
benchmarks, not on clean Hindi - on Hinglish code-switching over a mobile line, which is §2's whole
argument and the reason `FER` rather than `WER` is the deciding number.

There is no way to pick this from vendor documentation. Run §4's protocol.

**Order the testing by likelihood, not alphabetically:**

1. **Sarvam** - built for Indic code-switching specifically, an adapter already exists at
   `app/integrations/ai_providers/sarvam.py`, and it keeps both speech legs with one vendor and one
   latency profile. The leading candidate on the stated criterion.
2. **Deepgram** - the strongest streaming-and-endpointing baseline to measure Sarvam against. If
   Sarvam wins on FER the decision is easy; if Deepgram wins we have learned something important for
   the price of a day.
3. **Google STT or AssemblyAI** - only if neither of the first two clears the kill criteria.

**Kill criteria. A candidate is out regardless of every other number if:**

- **opt-out recall is below 100%** on §4.1's two refusal clips - losing "don't call me" to a
  transcription error is the one failure here with a legal consequence
- total silence **p95 exceeds ~1.2 s**
- it cannot stream with partial results

**Record the result in §5 and commit it. That commit closes `A2`.**

---

## 7. What this decision touches

| Area | File |
| ---- | ---- |
| Pipeline wiring | `apps/voice-runtime/app/pipeline.py` |
| Field collection | `apps/voice-runtime/app/collection.py` |
| Provider adapters | `apps/api/app/integrations/ai_providers/` |
| Model routing | `apps/api/app/integrations/openrouter/client.py` |
| Cost per leg | `H10` metrics endpoint, then `H13` |
| Grade quality | Every field in `docs/GRADING.md` §3 |

**The vendor stays behind the adapter boundary** (`CLAUDE.md` §2, §3-D, §3-L). One import outside
`app/integrations/{vendor}/` leaks vendor types through the whole application, and the CALL-E
migration is why that rule exists.

---

## References

- `docs/GRADING.md` §3 - the extraction fields FER is scored against
- `CLAUDE.md` §2 (vendor boundary), §3-D (dependency inversion), §3-L (substitutability), §7 (test numbers)
- `apps/voice-runtime/app/pipeline.py`, `collection.py`
- Roadmap tasks `A2`, `A6`, `A7`; risk R3; decisions D7, D8
