# H1 - Vendor Signup and Number Provisioning

**Owner:** Het  
**Status:** 🔥 START TODAY - Critical path blocker  
**Time:** 10-15 min signup, 2-5 days KYC approval  
**Date:** 13 Sep 2026

---

## Why This Matters

**H1 is the critical path blocker for P0 → P1.**

```
H1 blocks → H6 blocks → P1 track A blocks → First real call blocks → P1 gate blocks → P2
```

**Vendor KYC is someone else's queue, not our work.** Every day this doesn't start is
a day added to reaching the P1 gate (first real call by 15 Jan 2027).

---

## Decision: Twilio vs Plivo

**Recommendation: Twilio** (per plan preference)

| Factor | Twilio | Plivo |
|--------|--------|-------|
| **Documentation** | Excellent | Good |
| **India support** | Yes, full KYC flow | Yes |
| **Plan integration** | Preferred in probe-dial.py | Supported |
| **DLT portal** | Documents Airtel path | Not specified |
| **Existing code** | Twilio adapter at 360 LOC | Plivo adapter at 280 LOC |

**Both work. Pick one and start TODAY.**

---

## Step 1: Account Creation (5 min)

### For Twilio

```
1. Navigate to: https://www.twilio.com/try-twilio
2. Sign up with:
   - Email: (use company email when M10 entity exists)
   - Password: (strong, save in password manager)
   - Phone: (for 2FA)
3. Verify email
4. Complete 2FA setup
5. Log in to console: https://console.twilio.com/
```

### For Plivo

```
1. Navigate to: https://www.plivo.com/
2. Click "Start Free Trial" or "Sign Up"
3. Provide:
   - Email: (use company email when M10 entity exists)
   - Password: (strong, save in password manager)
   - Phone: (for verification)
4. Verify email
5. Log in to console: https://console.plivo.com/
```

---

## Step 2: Upgrade to Paid Account (2 min)

**Trial accounts silently refuse Indian destinations** - this is load-bearing.

### Twilio
```
1. Console → Billing → Upgrade Your Account
2. Add payment method (credit card or bank transfer)
3. Set up auto-recharge: $50 minimum recommended
4. Note: Trial credit ($15) still usable after upgrade
```

### Plivo
```
1. Console → Account → Billing → Add Funds
2. Add payment method
3. Initial top-up: $20 minimum recommended
4. Enable auto-recharge if available
```

**Save credentials immediately:**
```bash
# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...

# Plivo
PLIVO_AUTH_ID=MA...
PLIVO_AUTH_TOKEN=...
```

---

## Step 3: Entity KYC (Submit today, wait 2-5 days)

### Required Documents (per TELEPHONY_COMPLIANCE.md)

Prepare these before starting:

- [ ] Certificate of incorporation / Partnership deed
- [ ] PAN of entity
- [ ] GST certificate (if applicable)
- [ ] Authorised signatory PAN (masked in our copy)
- [ ] Authorised signatory Aadhaar (masked in our copy)
- [ ] Proof of registered address
- [ ] Board resolution or authorisation letter for signatory
- [ ] Cancelled cheque / bank letter

**Blocker alert:** If M10's entity doesn't exist yet:
1. Document this in ISSUES.md #209 TODAY
2. Use personal entity as placeholder ONLY IF permitted by vendor
3. Plan to re-KYC with company entity when M10 completes

### Twilio KYC Submission

```
1. Console → Settings → Compliance
2. Regulatory Compliance → India
3. Upload documents (usually as one PDF bundle)
4. Wait for approval email (typically 2-3 business days)
5. Check daily: Console → Account → Verification Status
```

### Plivo KYC Submission

```
1. Console → Account → Settings → Verification
2. Select: India - Voice Calling
3. Upload documents
4. Submit for review
5. Check daily: email and console for approval
```

---

## Step 4: Provision Indian Number (10 min, after KYC approval)

### Twilio

```
1. Console → Phone Numbers → Buy a Number
2. Country: India (+91)
3. Capabilities: ✅ Voice (SMS not required)
4. Number type: Mobile or Local (mobile preferred for caller-ID trust)
5. Search → Select a number → Buy

Cost: ~$1/month + per-minute usage

6. Note the number: +91XXXXXXXXXX
7. Do NOT configure voice URL yet - H6 does this
```

### Plivo

```
1. Console → Phone Numbers → Buy Numbers
2. Country: India
3. Number Type: Local or Mobile
4. Voice: ✅ Enabled
5. Search → Select → Buy

Cost: ~$0.80-$1.50/month + per-minute usage

6. Note the number: +91XXXXXXXXXX
7. Do NOT configure application yet - H6 does this
```

---

## Step 5: Test with probe-dial.py (2 min)

**This is the H1 done-when gate.**

```bash
# Set credentials in environment
export TWILIO_ACCOUNT_SID=AC...
export TWILIO_AUTH_TOKEN=...
export TWILIO_NUMBER=+91XXXXXXXXXX

# Or for Plivo
export PLIVO_AUTH_ID=MA...
export PLIVO_AUTH_TOKEN=...
export PLIVO_NUMBER=+91XXXXXXXXXX
export PLIVO_ANSWER_URL=https://<somewhere>/probe-dial-answer.xml

# Test dial to a teammate's Indian mobile
python scripts/probe-dial.py --to +919876543210

# Expected output:
# Twilio accepted. Call SID ACxxxxxxxx. Rang +91...10 from +91...XX.
# The handset should ring within a few seconds. Hang up when it does — that is the proof.
```

**If the call goes through and the handset rings: H1 is COMPLETE.**

---

## Step 6: Record Success (1 min)

Update ISSUES.md #209:

```markdown
**H1 Status:** ✅ COMPLETE (DD MMM 2026)
- Vendor: [Twilio|Plivo]
- Account: [ACCOUNT_SID or AUTH_ID]
- Number: +91XXXXXXXXXX (masked: +91XX...10)
- KYC: Approved [date]
- Test call: Success [date]
- Probe output: [paste the "Twilio accepted" line]

Next: H6 - wire this number to LiveKit trunk
```

---

## Timeline Tracking

| Milestone | Target | Actual | Status |
|-----------|--------|--------|--------|
| Account created | 13 Sep | | |
| Paid upgrade | 13 Sep | | |
| KYC submitted | 13 Sep | | |
| KYC approved | 18 Sep (est.) | | Waiting |
| Number provisioned | 18 Sep | | Waiting |
| Test call success | 18 Sep | | Waiting |

**Update this table daily in ISSUES.md #209**

---

## Blockers and Escalation

### If KYC is rejected
1. Note rejection reason in #209 immediately
2. Check what document is insufficient
3. If it's entity-related and M10 isn't done: use personal entity placeholder
   (get written permission from team first)
4. Re-submit within 24 hours

### If KYC takes >5 days
1. Open support ticket with vendor
2. Reference account SID/ID
3. Ask for status update
4. Escalate to paid support if available

### If number provisioning fails
1. Try different number type (mobile vs local)
2. Try different region within India
3. Open support ticket
4. Worst case: switch to other vendor (Twilio ↔ Plivo)

**Document every blocker in #209 the day it appears, not after it resolves.**

---

## Cost Estimates

### One-time
- Number purchase: Free - $2 (varies by number type)

### Recurring monthly
- Number rental: $0.80 - $1.50/month
- Twilio or Plivo platform fee: $0 (pay-as-you-go)

### Per-call (testing phase)
- Outbound call: $0.02 - $0.05/minute to Indian mobile
- 10 test calls @ 1 min each: ~$0.50

**Budget for first month: ~$5 including testing**

---

## Security Notes

**Credentials are secrets:**
```bash
# Never commit these to git
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
PLIVO_AUTH_ID=...
PLIVO_AUTH_TOKEN=...

# Store in:
# 1. Password manager (primary)
# 2. GitHub secrets: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN (when ready to wire)
# 3. VM .env files (encrypted in our repo context)
```

**Number is PII after first call:**
- Before any real customer call: the number is public config
- After first call to customer list: treat as PII per CLAUDE.md §4.4
- Mask in logs, issues, and commits: +91XX...10

---

## Next Steps After H1

1. **Immediately:** Execute H4 (LiveKit setup) - don't wait
2. **When both done:** Execute H6 (wire trunk)
3. **Then:** P0 gate verification

---

## Done-When (from plan)

> "A throwaway script on your laptop places a call that rings a teammate's Indian mobile."

✅ Checklist:
- [ ] Paid vendor account active
- [ ] KYC approved for India outbound
- [ ] Indian number provisioned (+91...)
- [ ] `python scripts/probe-dial.py --to <teammate>` succeeds
- [ ] Teammate's phone actually rings
- [ ] Call connects and plays "This is a CallFlow probe"
- [ ] Success recorded in ISSUES.md #209

**This is the gate to H6, which is the gate to P1 track A, which is half the P1 gate.**

Start today.
