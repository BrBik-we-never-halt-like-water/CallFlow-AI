# Trial Testing Guide - Prove It Works First

**Goal:** Test the full integration on Twilio free trial before upgrading  
**Cost:** $0 (uses $15 trial credit)  
**Time:** 15 minutes  
**Result:** Working demo for team approval

---

## ✅ What Trial Allows

- ✅ Call to verified phone numbers (add yours)
- ✅ One free phone number
- ✅ $15 trial credit (~300 minutes of calls)
- ✅ Full API access (same as paid)
- ❌ Cannot call unverified numbers
- ❌ "Trial Account" announcement on calls

**Perfect for testing!** Upgrade only after proving it works.

---

## 🧪 Trial Test Steps (15 minutes)

### 1. Verify Your Mobile (2 min)

**URL:** https://console.twilio.com/us1/develop/phone-numbers/manage/verified

```
□ Click "Add a new number"
□ Enter YOUR mobile: +91XXXXXXXXXX
□ Choose "Call me" or "Text me"
□ Enter verification code
□ ✅ Your number is now verified
```

---

### 2. Get a Trial Number (2 min)

**URL:** https://console.twilio.com/us1/develop/phone-numbers/manage/search

```
□ Country: India (+91)
□ Capabilities: Voice ✓
□ Search
□ Pick any available number
□ Buy (uses trial credit)
□ Note the number: +91XXXXXXXXXX
```

---

### 3. Configure LiveKit SIP Trunk (2 min)

**URL:** https://cloud.livekit.io/

```
□ SIP → Trunks → Create Trunk

Name: callflow-twilio-trial
Type: Outbound

Host: [YOUR_ACCOUNT_SID].pstn.twilio.com
Port: 5060
Transport: UDP

Username: [YOUR_ACCOUNT_SID]
Password: [YOUR_AUTH_TOKEN]

(Get from temp-twilio-credentials.txt)

□ Create
```

---

### 4. Test with Probe Dial (2 min)

```powershell
# Set environment (get values from temp-twilio-credentials.txt)
$env:TWILIO_ACCOUNT_SID = "AC..."  # Your Account SID
$env:TWILIO_AUTH_TOKEN = "..."     # Your Auth Token
$env:TWILIO_NUMBER = "+91..."      # Your trial number

# Test call to YOUR verified mobile
python scripts/probe-dial.py --to +91XXXXXXXXXX

# Expected output:
# "Twilio accepted. Call SID ACxxxxxx. Rang +91...XX from +91...XX."
# 
# Your phone should ring!
# You'll hear: "This is a CallFlow probe. You can hang up."
```

---

### 5. Configure Inbound Routing (2 min)

**URL:** https://console.twilio.com/us1/develop/phone-numbers/manage/active

```
□ Click your trial number
□ Voice & Fax section:
  Configure With: SIP
  SIP Domain: callflow-dev-odwy9nv9.sip.livekit.cloud
□ Save
```

---

### 6. Test from Dashboard (5 min)

```
□ Open: http://localhost:3000/app/runs/new
□ Select a voice agent
□ Add contact: YOUR verified mobile number
□ Click "Start Run"
□ Watch status: In Progress → Calling → Spoke
□ Your phone should ring with agent speaking!
```

---

## ✅ Success Criteria

**Trial test PASSES when:**
- [x] Probe dial rings your phone
- [x] You hear the "CallFlow probe" message
- [x] Dashboard run rings your phone
- [x] Agent speaks to you
- [x] Transcript appears in dashboard

**If all pass:** Integration is proven working! 🎉

---

## 📊 Present to Team

**After successful test, show the team:**

1. **Working Demo**
   - "Here's a call I just made through the system"
   - Show transcript in dashboard
   - Show outcome data

2. **What Works Now** (FREE trial)
   - ✅ Full integration tested
   - ✅ Twilio → LiveKit → Voice Worker → API
   - ✅ Calls to verified numbers only

3. **What Upgrade Unlocks** ($50/month)
   - ✓ Call ANY number (not just verified)
   - ✓ No "trial account" announcement
   - ✓ India KYC compliance
   - ✓ Production-ready

4. **Cost Breakdown**
   ```
   Trial (now):    $0 (using $15 credit)
   Paid account:   $0/month base
   Phone number:   $1.50/month
   Calls:          $0.02-0.05/minute
   
   Est. for testing: ~$5/month
   ```

5. **Ask for Approval**
   - "Integration proven, ready to upgrade"
   - "Need approval to add payment method"
   - "Then submit India KYC (2-3 days)"

---

## 🚀 After Team Approval

### Upgrade Steps (5 min)

```
□ Twilio Console → Billing → Upgrade
□ Add payment method
□ Set auto-recharge: $50
□ Confirm upgrade
```

### Submit India KYC (5 min)

```
□ Regulatory Compliance → New Bundle
□ Region: India
□ Upload documents:
  □ PAN + Aadhaar + Address proof
  □ (or company docs if available)
□ Submit
□ Wait 2-3 days for approval
```

### When KYC Approved

```
□ Can call ANY Indian number
□ No trial limitations
□ Production ready
```

---

## 💡 Trial Limitations to Know

**Trial account shows:**
- "This call is from a Twilio trial account" (announcement)
- Can only call verified numbers
- Same announcement on inbound calls

**Upgrade removes:**
- All announcements
- Verification requirement
- "Trial" badge in console

**Technical limits:**
- Trial and paid have SAME API capabilities
- Trial and paid have SAME call quality
- ONLY difference: who you can call

---

## 🔍 Troubleshooting

### "Cannot call this number - not verified"
→ Add the number in Verified Caller IDs first

### "Trial account announcement plays"
→ Expected on trial - upgrade to remove

### "Probe dial fails with authentication error"
→ Check credentials in temp-twilio-credentials.txt

### "Dashboard call fails"
→ Check LiveKit trunk is configured
→ Check voice VM is running: `pm2 list | grep callflow-voice`

---

## 📅 Timeline

**Today (13 Sep):**
- Complete trial test (15 min)
- Verify integration works

**Tomorrow (14 Sep):**
- Present working demo to team
- Request upgrade approval

**After Approval:**
- Upgrade account (5 min)
- Submit KYC (5 min)
- Wait 2-3 days

**~18 Sep:**
- KYC approved
- Call any number
- P0 complete!

---

## 📞 Support

**If trial test fails:**
- Check: docs/H1_VENDOR_CHECKLIST.md
- Check: docs/H6_WIRING_GUIDE.md (troubleshooting section)
- Check: NEXT_STEPS.md

**Twilio Support:**
- Help: https://support.twilio.com/
- Docs: https://www.twilio.com/docs/voice

---

**Bottom line:** Trial test proves the integration for FREE. Then get team buy-in before spending money. Smart approach! 👍
