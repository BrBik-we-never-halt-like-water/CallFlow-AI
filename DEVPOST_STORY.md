## Inspiration

Every team doing customer outreach hits the same wall: it doesn't scale, and you're blind while it's happening.

The dialing wasn't what bothered me most — it was that the effort bought no visibility. In a normal call log, a delighted customer and a furious one look identical. Both just say `completed`. You find out a call went badly when someone escalates, which is far too late.

I wanted something that could run at 3am without getting tired or inconsistent, and that could tell me honestly how each call went.

## What it does

CallFlow AI is a 24×7 outbound calling desk built on CALL-E.

Load contacts, pick a campaign, and it dials, holds a real conversation, and returns a **typed outcome** — schema-validated JSON, not a wall of transcript. Then it triages every result:

- **Frustration or an opt-out** → escalate to a human
- **A polite "bad time"** → queue for a retry
- **A clean call** → auto-close

You can build your own campaigns with custom extraction fields. Travel is the demo vertical; the engine underneath is campaign-agnostic.

## How I built it

CALL-E does the hard part — dialing, conversation, real-time adaptation, voicemail and IVR. I built the operations layer around it: campaign templating, safety gates, structured outcomes, and triage.

Each contact gets a goal rendered from a template, sent with a result schema. CALL-E returns validated JSON, so **I never parse a transcript**:

```json
{
  "sentiment": "negative",
  "frustration_signals": false,
  "destination": "Dubai",
  "party_size": 4,
  "summary": "Said it was a bad time; asked to be called back next week."
}
```

Triage reads those typed fields and decides what happens next.

## Challenges I ran into

**`language` is not a valid recipient field.** My first live call failed with a bare `422`. The SDK swallowed the detail, so I probed the API directly and found `extra_forbidden` naming the exact path — the field is `locale`. Not in any doc I could find; only the error payload knew.

**CALL-E validates task substance.** A thin goal is rejected with `call_not_ready`. I learned this the embarrassing way: a probe call went through with placeholder text and the agent said *"I'm calling for the requester to ask what your current trip plans are."* Genuinely confusing to listen to. CALL-E's own summary was blunt — *"the bot's phrasing did not move quickly enough to a clear, direct question."*

**Triage was too eager.** My first real conversation came back `sentiment: negative` but `frustration_signals: false` — I'd said it was a bad time, not that I was angry. The original logic escalated that to "Needs human," wasting a person on a callback. Now frustration escalates and plain negativity retries. A bad time is not a bad mood, and only CALL-E's separation of those two signals made the distinction possible.

**Safety on a public URL.** The hosted demo runs on my credits and could be pointed at a stranger. I added per-IP and daily rate limits on top of E.164 validation, an allowlist, per-run ceilings, and number masking everywhere.

## Accomplishments that I'm proud of

**The triage layer.** Getting a call to happen is the easy part; deciding which calls a human should see is the actual product.

**Safety that fails closed.** Dry run is the default everywhere. One test asserts it by passing a gateway that raises on *any* attribute access — if a dry run ever touched the network, the suite breaks. 71 tests total.

## What I learned

**The goal field is the entire product.** Same platform, same voice, same number: a one-line task produced a confusing robocall, while a well-written goal produced something that sounded like a consultant.

I also learned to trust the platform's structured output over my own post-processing. My first instinct was to run sentiment analysis on the transcript myself. CALL-E's `result_schema` does it better — it had the audio; a transcript parser would only have had words.

## What's next

- **WhatsApp delivery** — send the agreed details in writing after the call
- **Booking tools** — let a confirmed intent book itself
- **Scheduled campaigns** with time-zone-aware calling windows
- **Inbound calls**, not just outbound
