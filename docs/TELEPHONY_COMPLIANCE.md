# Telephony compliance — DLT / TRAI, and the customer's own account

H2 of the plan of record. Started 12 Sep 2026. Hand-off to Mridul at M10 is the
entity paperwork through to a registrable invoice; this page is the technical
half: what we must file, and what a customer must hand us so we can dial on
*their* account (D6).

Nothing here is a legal opinion. It is the checklist we work from until a
lawyer and a completed registration replace it.

The live status of *our* application lives in `ISSUES.md` #209. When a
reference number exists, it goes there the same day — not in chat.

---

## Why this exists

Indian commercial outbound is two separate queues, both someone else's:

1. **The carrier account** (Twilio / Plivo). Entity KYC, billing live, one
   outbound-capable number. That is H1. Without it, no probe call, no P1.
2. **DLT / TRAI telemarketing registration.** Headers, content templates, and
   principal-entity linkage for commercial communication. That is this page.
   Without it, a working number can still be a compliance complaint.

D6 is the pilot's real route: we dial on the *customer's* Twilio or Plivo
account, their number, their caller-ID reputation, their DLT registration.
Our own registration is a convenience (demos, our own test list) rather than
the thing that unblocks a paying floor.

---

## Our application (start on day one)

File against the current TRAI Distributed Ledger for commercial communication.
The operator of record is one of the TSPs' DLT portals (VIL, Airtel, BSNL,
Jio — pick the one whose onboarding the carrier asks for; Twilio and Plivo
each document a preferred path).

What to submit, in the order the form asks:

1. **Principal Entity (PE) registration** — legal name, PAN, GSTIN if we have
   it, registered address, authorised signatory. This is M10's entity; if the
   company is not incorporated yet, stop and say so in #209 rather than filing
   as a person and having to redo it.
2. **Header registration** — the CLI / alphanumeric identity the callee sees.
   For voice this is the number itself, not an SMS header, but the PE still
   has to exist before a header can be linked.
3. **Content templates** — required for SMS; for voice, record that we are
   *not* sending promotional SMS from this PE until a template exists. Do not
   invent SMS traffic to "get the form filled".
4. **Telemarketer / chain binding** — if the carrier requires us to bind as a
   telemarketer under the customer's PE (D6), that binding is *their* action
   in the portal. We document it; we do not click it for them.

**Documents typically asked for** (confirm on the live form, they change):

- Certificate of incorporation / Partnership deed / GST certificate
- PAN of the entity
- Authorised signatory PAN + Aadhaar (masked in our copies)
- Board resolution or authorisation letter for the signatory
- Proof of address
- Cancelled cheque / bank letter (some portals)

**Do not wait for a perfect entity.** If incorporation is still in M10's
queue, file what can be filed (H1 KYC at the carrier uses the same pack) and
write the missing item in #209 the day it blocks the form.

---

## What a customer must hand us (D6 — the pilot path)

A floor running on their own telephony, which is every pilot. Collect this
before we promise a date. None of it is a CallFlow setting we can invent.

### Carrier

| Item | Why |
| --- | --- |
| Provider (Twilio or Plivo only — Telnyx/Vonage are out of the maintained path) | H6 stops testing the other two |
| Account SID / Auth ID | Stored encrypted in `provider_credentials` |
| Auth token | Same. Verify on save; do not accept and fail later (J9) |
| The outbound number, E.164 | Must be on *that* account, voice-enabled, Indian CLI if they want Indian answer-rates |
| Confirmation billing is live, not trial | Trial accounts silently refuse Indian destinations |

### TRAI / DLT, on *their* PE

| Item | Why |
| --- | --- |
| PE registration ID | We do not dial a promotional list against an unregistered PE |
| Header / CLI they will present | Must match the number they gave us |
| Written confirmation they are the principal, we are the platform | Who is answerable when a consumer complains — drafted in `docs/COMPLIANCE.md` at M9, named here so it is not a surprise |
| Their DNC / NDNC export, if they keep one | Imports onto our suppression list (J10). We still honour in-call "don't call me" regardless |

### Consent

| Item | Why |
| --- | --- |
| How they obtained the list | Purchased lists are the market; we still need *their* statement that they have a lawful basis to call |
| Opt-out they already honour | Goes onto suppressions before the first run, not after the first complaint |

If any row is missing, the run does not start. That is fail-closed, not a
sales conversation.

---

## What this page is not

- A substitute for `docs/COMPLIANCE.md` (M9 — consent language, retention,
  who is legally answerable). That document is written later; this one
  unblocks the filing.
- Permission to skip H11's dial gate. Registration without a gate that
  actually runs is how a complaint gets a screen recording.
