# Next Steps - Complete H1 Setup

**Status:** Twilio account created ✅  
**Date:** 13 Sep 2026  
**Time Remaining:** 5-7 minutes of active work + 2-3 days wait

---

## ✅ What's Done

- ✅ Twilio account created
- ✅ Account SID: `AC...fb2` (saved in temp file, not committed)
- ✅ Auth Token: saved securely in temp file
- ✅ LiveKit project configured
- ✅ Credentials saved to temp file

---

## 🔥 Complete These NOW (7 minutes)

You have 3 browser tabs open. Complete each one:

### Tab 1: Twilio Billing (2 min)
**URL:** https://console.twilio.com/us1/billing/manage-billing/upgrade

```
□ Add payment method (credit card)
□ Set auto-recharge: $50 when balance drops below $10
□ Click "Upgrade Account"
□ Verify: Account shows "Active" (not "Trial")
```

**After upgrade:**
```bash
# Update ISSUES.md:
# - Upgraded to paid: ✅ 2026-09-13

git commit -am "chore(P0-H1): upgraded to paid account"
```

---

### Tab 2: Twilio Regulatory Compliance (5 min)
**URL:** https://console.twilio.com/us1/develop/phone-numbers/regulatory-compliance/bundles

```
□ Click "Create new Bundle"
□ Region: India
□ Type: Business OR Individual
□ Fill in details
□ Upload documents:
  □ PAN card
  □ Aadhaar (masked)
  □ Address proof
  □ (+ company docs if available)
□ Click "Submit for Review"
□ Note the Bundle ID
```

**After submission:**
```bash
# Update ISSUES.md:
# - KYC submitted: ✅ 2026-09-13
# - Bundle ID: [paste from Twilio]

git commit -am "chore(P0-H1): KYC submitted for approval"
```

**Timeline:** 2-3 business days for approval (check Mon-Fri)

---

### Tab 3: LiveKit SIP Trunk (2 min)
**URL:** https://cloud.livekit.io/

```
□ SIP → Trunks → Create Trunk
□ Name: callflow-twilio-out
□ Type: Outbound
□ Host: [YOUR_ACCOUNT_SID].pstn.twilio.com
□ Port: 5060
□ Transport: UDP
□ Username: [YOUR_ACCOUNT_SID]
□ Password: [YOUR_AUTH_TOKEN]
  
  (Use values from temp-twilio-credentials.txt)
□ Click "Create"
□ Note the Trunk ID (TR_...)
```

**After creation:**
```bash
# Update ISSUES.md:
# - LiveKit trunk: ✅ TR_[paste ID]

git commit -am "feat(P0-H4): SIP trunk configured"
git push origin dev
```

---

## 📅 Daily Checks (14-18 Sep)

**Every morning:**
```bash
pwsh scripts/check-h1-status.ps1
```

**Or manually:**
1. https://console.twilio.com/
2. Phone Numbers → Regulatory Compliance → Bundles
3. Check status: "Approved" (green) or "In Review" (yellow)

**If still "In Review" after 5 days:** Open support ticket

---

## 🎉 When KYC Approves (~16-18 Sep)

### 1. Provision Number (5 min)

```bash
# In Twilio Console:
# Phone Numbers → Buy a Number

Country: India (+91)
Capabilities: Voice ✓
Type: Mobile (preferred) or Local
Search → Select a number → Buy

# Save the number
# Example: +919876543210
```

**Update credentials:**
```bash
# Add to temp-twilio-credentials.txt:
TWILIO_NUMBER=+91___YOUR_NUMBER___
```

---

### 2. Configure Inbound Routing (2 min)

```bash
# In Twilio Console:
# Phone Numbers → Active Numbers → [your number]

Voice & Fax:
  Configure With: SIP
  SIP Domain: callflow-dev-odwy9nv9.sip.livekit.cloud

Save
```

---

### 3. Test with Probe Dial (2 min)

```powershell
# Set environment variables (use values from temp-twilio-credentials.txt)
$env:TWILIO_ACCOUNT_SID = "AC..."  # Your Account SID
$env:TWILIO_AUTH_TOKEN = "..."     # Your Auth Token
$env:TWILIO_NUMBER = "+91___YOUR_NUMBER___"

# Test dial to YOUR mobile
python scripts/probe-dial.py --to +91___YOUR_MOBILE___

# Expected output:
# "Twilio accepted. Call SID ACxxxxxx. Rang +91...XX from +91...XX."
# Your phone should ring within 5-10 seconds!
```

**If successful:**
```bash
# H1 IS COMPLETE! ✅
git commit -am "feat(P0-H1): number provisioned and tested successfully"
git push origin dev
```

---

### 4. Execute H6 - Wire End-to-End (10 min)

```bash
# Follow the guide:
cat docs/H6_WIRING_GUIDE.md

# Steps:
1. Verify trunk connected
2. Test from dashboard
3. Record video of first call
4. Update ISSUES.md #209: "H6 complete"
```

**When H6 passes:**
- ✅ P0 is COMPLETE
- ✅ P1 track A is 50% done
- ✅ First real call has happened
- ✅ Product viability proven

---

## 📊 Timeline from Here

```
TODAY (13 Sep)
├─ ✅ Account created
├─ ⏳ Upgrade to paid (2 min)
├─ ⏳ Submit KYC (5 min)
└─ ⏳ Configure SIP trunk (2 min)

14-17 SEP
└─ Check KYC status daily (1 min/day)

WHEN APPROVED (~18 Sep)
├─ Provision number (5 min)
├─ Configure inbound (2 min)
├─ Test with probe-dial (2 min)
└─ Execute H6 (10 min)

P0 COMPLETE (~18 Sep)
└─ First call rings! 📞 🎉
```

---

## 🛟 Troubleshooting

### "Cannot upgrade without payment method"
- Add credit card first
- Billing → Payment Methods → Add
- Then try upgrade again

### "KYC submission requires more documents"
- Check the error message
- Usually needs: PAN + Aadhaar + Address
- Aadhaar must be masked (show only last 4 digits)
- Upload as single PDF if possible

### "LiveKit trunk creation fails"
- Check Twilio credentials are correct
- Verify Account SID starts with "AC"
- Verify Auth Token is the primary token (not test)
- Try again - sometimes transient

### "Probe dial fails"
- Verify account is upgraded (not trial)
- Check number is Voice-enabled
- Verify credentials in environment variables
- Check Twilio Console → Logs for error details

---

## 📞 Support

**Twilio Issues:**
- Help Center: https://support.twilio.com/
- Phone: Check Twilio Console for support number
- Response time: Usually <24 hours

**LiveKit Issues:**
- Docs: https://docs.livekit.io/
- Discord: https://livekit.io/discord
- GitHub: https://github.com/livekit/livekit

**Our Docs:**
- H1 full guide: `docs/H1_VENDOR_CHECKLIST.md`
- H6 wiring guide: `docs/H6_WIRING_GUIDE.md`
- Quick start: `QUICKSTART_P0.md`

---

## 🎯 Success Criteria

**H1 is DONE when:**
- [x] Account created
- [ ] Upgraded to paid
- [ ] KYC submitted
- [ ] KYC approved (2-3 days)
- [ ] Number provisioned
- [ ] Test call rings phone

**After H1:**
- [ ] H6 wired (10 min)
- [ ] First call recorded (2 min)
- [ ] P0 gate passes

---

**Next: Complete the 3 tabs above (9 min total), then check daily for KYC approval.**

**Expected completion: ~18 Sep 2026**
