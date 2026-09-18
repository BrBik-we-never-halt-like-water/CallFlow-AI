# Quick Start: Het's P0 Tasks

**Date:** 13 Sep 2026  
**Goal:** Get from here to first real call  
**Time:** ~1 hour active work + 2-5 days vendor wait

---

## TL;DR

```bash
# 1. Check readiness (2 min)
bash scripts/verify-p0-readiness.sh

# 2. Start vendor signup TODAY (10 min + 2-5 day wait)
# Follow: docs/H1_VENDOR_CHECKLIST.md

# 3. Create LiveKit project NOW (15 min)
# Follow: docs/H4_LIVEKIT_CHECKLIST.md

# 4. When both done: wire trunk (10 min)
# Follow: docs/H6_WIRING_GUIDE.md

# 5. Make a phone ring 📞
```

---

## Today's Actions (13 Sep 2026)

### ✅ Already Done

You have 7 commits on `dev` branch with all infrastructure:
- H1 tooling (probe-dial.py)
- H2 compliance docs
- H3 VM2 deployment chain
- H4 LiveKit documentation
- H5 complete (Next.js builds on runner)
- Comprehensive checklists
- Helper scripts

### 🔥 Do Right Now (Critical Path)

#### 1. Start H1 Vendor Signup (10 min + wait)

**Why critical:** This is a 2-5 day vendor queue. Every day it doesn't start adds a day to P1.

```bash
# Open the checklist
cat docs/H1_VENDOR_CHECKLIST.md

# Pick Twilio (recommended) or Plivo
# Go to: https://www.twilio.com/try-twilio
# or: https://www.plivo.com/

# Steps:
1. Create account (5 min)
2. Upgrade to paid (2 min)
3. Submit KYC docs (10 min)
4. Wait 2-5 days for approval
5. When approved: provision number
6. Test: python scripts/probe-dial.py --to +91XXXXXXXXXX
```

**Record progress in ISSUES.md #209 daily.**

---

#### 2. Execute H4 LiveKit (15 min, no blockers)

**Why now:** No dependencies. Takes 15 minutes. Unblocks H6.

```bash
# Open the checklist
cat docs/H4_LIVEKIT_CHECKLIST.md

# Go to: https://cloud.livekit.io/

# Steps:
1. Create project (5 min)
   - Note: project URL, API key, API secret

2. Create SIP trunk (5 min)
   - For Twilio or Plivo (can be placeholder initially)
   - Note: trunk ID, SIP host

3. Update both VMs (5 min)
   - API VM: add LIVEKIT_* to .env
   - Voice VM: add LIVEKIT_* to .env
   - Restart: pm2 restart --update-env

4. Record in DEPLOYMENT.md §2b (2 min)

5. Update ISSUES.md #209: "H4 complete" (1 min)
```

**Done-when:** Both VMs have LiveKit credentials and can connect.

---

### 🟡 Optional Today

#### 3. Set Up GitHub Environments (15 min)

If you have access and the VMs exist:

```bash
# Interactive setup
bash scripts/setup-github-env.sh dev

# It will prompt for:
# - VM_HOST, VM_USER, APP_DIR, PUBLIC_URL
# - VOICE_VM_HOST, VOICE_APP_DIR
# - Paths to .env files
# - SSH private key

# Verifies and sets everything in one go
```

---

#### 4. Verify H3 (30 min)

If VM2 is provisioned and accessible:

```bash
# Open the checklist
cat docs/H3_VM2_VERIFICATION.md

# Prerequisites:
# - VM2 exists at <hostname>
# - SSH access works
# - GitHub env vars set (from step 3)

# Test:
1. touch apps/voice-runtime/app/worker.py
2. git push origin dev
3. Watch CI deploy-voice job
4. ssh to VM2, run: pm2 list
5. Verify callflow-voice-dev is online
```

---

## This Week (14-18 Sep)

### Chase H1 Daily

```bash
# Check vendor dashboard every day:
# Twilio: console.twilio.com → Account → Verification Status
# Plivo: console.plivo.com → Account → Verification

# When KYC approved (target: 18 Sep):
1. Provision Indian number
2. Test: python scripts/probe-dial.py --to <teammate>
3. Update ISSUES.md #209: "H1 complete: +91..."
```

### When H1+H4 Both Done: Execute H6 (10 min)

```bash
# H6 is the final P0 step
cat docs/H6_WIRING_GUIDE.md

# Steps:
1. Wire inbound routing (H1 number → H4 SIP host)
2. Verify trunk ID
3. Test end-to-end
4. **Record video** (P1 gate requirement)

# Expected:
# - Dashboard run → phone rings
# - Answer → agent speaks
# - Hang up → outcome lands in database

# This completes P0 and is 50% of P1 gate
```

---

## Verification Commands

### Check P0 Readiness
```bash
bash scripts/verify-p0-readiness.sh
# Shows: what's done, what's blocked, what's next
```

### Test H1 (when number provisioned)
```bash
export TWILIO_ACCOUNT_SID=AC...
export TWILIO_AUTH_TOKEN=...
export TWILIO_NUMBER=+91...

python scripts/probe-dial.py --to +919876543210
# Expected: "Twilio accepted. Call SID... Rang +91...10 from +91...XX."
# Handset should ring within seconds
```

### Test H3 (VM2 status)
```bash
ssh <VM_USER>@<VOICE_VM_HOST> 'pm2 list | grep callflow-voice'
# Expected: callflow-voice-dev | online | ...
```

### Test H4 (LiveKit connection)
```bash
# From API VM:
cd <APP_DIR>
source .venv/bin/activate
python3 -c "
import asyncio
from app.integrations.livekit.client import LiveKitGateway
async def test():
    async with LiveKitGateway() as gw:
        print('✓ LiveKit connected')
asyncio.run(test())
"
```

---

## Documentation Map

```
QUICKSTART_P0.md         ← YOU ARE HERE (what to do today)
│
├── docs/P0_README.md              # Full P0 overview
├── docs/P0_HET_STATUS.md          # Status tracker (update daily)
│
├── Execution checklists:
│   ├── docs/H1_VENDOR_CHECKLIST.md      # START TODAY
│   ├── docs/H3_VM2_VERIFICATION.md      # When VM2 exists
│   ├── docs/H4_LIVEKIT_CHECKLIST.md     # DO NOW (15 min)
│   └── docs/H6_WIRING_GUIDE.md          # When H1+H4 done
│
├── Reference:
│   ├── docs/TELEPHONY_COMPLIANCE.md     # DLT/TRAI requirements
│   ├── DEPLOYMENT.md                    # Full deployment guide
│   └── .env.voice.template              # Voice VM env template
│
└── Tools:
    ├── scripts/probe-dial.py            # Test telephony
    ├── scripts/verify-p0-readiness.sh   # Check prerequisites
    └── scripts/setup-github-env.sh      # Configure GitHub
```

---

## Timeline

| Date | Milestone | Owner |
|------|-----------|-------|
| **13 Sep** | H1 signup, H4 complete | Het |
| 13 Sep | H3 verified (if VM2 exists) | Het |
| 15 Sep | Check H1 KYC status | Het |
| 16 Sep | Check H1 KYC status | Het |
| 17 Sep | Check H1 KYC status | Het |
| **18 Sep** | H1 approved, number provisioned | Twilio/Plivo |
| **18 Sep** | H6 wired, test call succeeds | Het |
| **20 Sep** | **P0 gate passes** | Team |

---

## Success Criteria

**P0 gate requires:**
- [x] Chat page removed (Jatin J1)
- [x] False claims removed (Jatin J2 + Mridul M8)
- [ ] Number that can dial (Het H1 → H6)
- [ ] VM2 reachable (Het H3)
- [ ] docs/GRADING.md (Arbaaz A1)

**Het's portion: H1-H6, target 18-20 Sep**

---

## If You Get Stuck

### H1 Problems
- KYC rejected → Check docs needed in H1 checklist
- Number can't provision → Try different number type or region
- probe-dial fails → Check credentials, verify paid account

### H3 Problems
- VM2 doesn't exist → Provision it first (4 GB RAM, Ubuntu 20.04+)
- Deploy fails → Check GitHub env vars are set
- Worker crash loop → Check logs, likely env issue

### H4 Problems
- Can't create project → Check LiveKit account
- SIP trunk fails → Verify carrier credentials
- Can't connect → Regenerate API key

### H6 Problems
- Call never rings → Check inbound routing (Step 1 of H6)
- No agent speaks → Check worker logs, verify dispatch
- Outcome doesn't land → Check API URL in voice .env

**For all:** Update ISSUES.md #209 with exact error, date, and what was tried.

---

## After P0

When H1-H6 pass and P0 gate is verified:

**Het's P1 tasks:**
- H7: Ship the additive migration (new columns)
- H8: Log shipping off VM2
- H9: Redis rate limiter (fixes ISSUES.md #5)

**P1 gate (team effort):**
- Track A (Het): First real call recorded ← H6 delivers this
- Track B (Arbaaz): Grading rules working

---

## Summary

**Today (13 Sep):**
1. ✅ Infrastructure is complete (7 commits pushed)
2. 🔥 Start H1 vendor signup (critical path, 10 min)
3. 🔥 Execute H4 LiveKit setup (no blockers, 15 min)
4. 🟡 Optional: H3 verification if VM2 exists

**This week:**
- Chase H1 daily until approved (~18 Sep)
- When H1+H4 done: Execute H6 (10 min)
- Record the first call on video (P1 gate requirement)

**Result:**
- P0 gate passes (~20 Sep)
- P1 track A is 50% done
- Product viability proven (phone actually rings)

**The infrastructure work is done. Now it's execution and vendor timing.**

Start H1 today. Do H4 now. Chase vendors daily. Wire H6 when both complete.

That's the path to first call.
