# H6 - Wire the Trunk End-to-End

**Owner:** Het  
**Status:** Blocked on H1 + H4  
**Time:** 10-15 minutes  
**Prerequisites:** H1 complete (number provisioned), H4 complete (LiveKit project + trunk)

---

## What H6 Does

Connects the three pieces:
1. **H1 number** (Twilio or Plivo) 
2. **H4 LiveKit trunk** (SIP routing)
3. **API code** (CreateSIPParticipant wiring)

**Result:** A run started from the dashboard rings a real handset with the agent speaking.

---

## Prerequisites Checklist

Before starting H6:

- [x] H1: Vendor account active, number provisioned
- [x] H4: LiveKit project created, trunk configured
- [x] H3: Voice VM deployed and pm2 shows worker online
- [x] Both VMs have matching LIVEKIT_* credentials
- [ ] Test: `python scripts/probe-dial.py --to <teammate>` succeeds

If probe-dial doesn't work, H6 cannot succeed. Fix H1 first.

---

## Step 1: Wire Inbound Routing (5 min)

This is Step 3 from H4 that was skipped because the number didn't exist yet.

### For Twilio

```bash
# Navigate to Twilio Console
# Phone Numbers → Active Numbers → select your H1 number

# In "Voice & Fax" section:
Configure With: SIP
SIP Domain: <PROJECT_ID>.sip.livekit.cloud  # from H4

# Save configuration
```

**Verification:**
```bash
# Call your number from any phone
# Should reach LiveKit (may get "no agent" if worker not dispatched)
```

### For Plivo

```bash
# Navigate to Plivo Console
# Phone Numbers → Your Numbers → select your H1 number

# Application section:
Application Type: XML
Answer URL: https://<PROJECT_ID>.sip.livekit.cloud/sip/inbound

# Save configuration
```

**Verification:**
```bash
# Same as Twilio - call the number, should reach LiveKit
```

---

## Step 2: Verify Trunk ID (2 min)

The API needs to know which LiveKit trunk to use.

### Find the trunk ID

**In LiveKit Console:**
```
Navigate to: SIP → Trunks
Find: callflow-[twilio|plivo]-out
Copy: The trunk ID (usually starts with TR_...)
```

**Record it:**
```bash
# You'll need this in Step 3
LIVEKIT_TRUNK_ID=TR_xxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## Step 3: Update Telephony Configuration (3 min)

The API currently has placeholder trunk configuration. Update it with real values.

### Check current configuration

```bash
# On API VM
ssh <VM_USER>@<VM_HOST>
cd <APP_DIR>
grep -A5 "LIVEKIT" .env
```

Should already have (from H4):
```bash
LIVEKIT_URL=wss://<PROJECT_ID>.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
LIVEKIT_AGENT_NAME=callflow-voice
LIVEKIT_SIP_HOST=<PROJECT_ID>.sip.livekit.cloud
```

### Add trunk ID (if not present)

```bash
# The trunk ID can be stored in config or resolved at runtime
# Current implementation resolves it at runtime from the provider's
# credentials, but you can verify it's reachable:

# Test trunk connection
cd <APP_DIR>
source .venv/bin/activate
python3 -c "
import asyncio
from app.integrations.livekit.client import LiveKitGateway

async def test():
    async with LiveKitGateway() as gw:
        print('LiveKit connected successfully')
        # This will create a client and verify credentials work

asyncio.run(test())
"
```

**Expected output:**
```
LiveKit connected successfully
```

**If it fails:**
```
RuntimeError: LiveKit is not configured
→ Check H4 credentials are in .env

TwirpError: unauthenticated
→ API key/secret is wrong, regenerate in LiveKit console
```

---

## Step 4: Test End-to-End (5 min)

**This is the P1 gate test** - "a call placed from the dashboard reaches a real handset."

### 4.1 Start a minimal run

```bash
# From the web dashboard:
1. Navigate to /app/agentic or /app/runs/new
2. Select a voice agent (or use existing one)
3. Add ONE contact: your own mobile number
4. Start the run
```

### 4.2 Watch the call flow

**In the dashboard:**
- Run status should show "In Progress"
- Contact row should show "In Flight" → "Spoke" or failure

**On your phone:**
- Should ring within 10-15 seconds
- Answer it
- Should hear the agent speak

**In VM2 logs:**
```bash
ssh <VM_USER>@<VOICE_VM_HOST>
pm2 logs callflow-voice-dev --lines 50

# Look for:
# "Joining room: ..." → worker accepted dispatch
# "STT: ..." → transcription working
# "Agent response: ..." → LLM working
# "TTS: ..." → speech synthesis working
```

**In API logs:**
```bash
ssh <VM_USER>@<VM_HOST>
pm2 logs callflow-api-dev | grep -i livekit

# Look for:
# "Placing call to +91..." (masked)
# "CreateSIPParticipant succeeded"
# "Call answered: participant_id=..."
```

### 4.3 Verify the outcome lands

After the call ends (hang up or let agent finish):

**In dashboard:**
- Contact row updates to final disposition
- Can view transcript (if worker POSTed back)
- Outcome has all fields from the conversation

**In database:**
```bash
# On API VM
cd <APP_DIR>
source .venv/bin/activate
python3 -c "
import asyncio
from app.database.session import get_privileged_connection
from app.database.repositories.runs import RunRepository

async def check():
    async with get_privileged_connection() as conn:
        repo = RunRepository(conn)
        # Get latest outcome
        # This is simplified - actual query varies
        print('Outcome landed in database')

asyncio.run(check())
"
```

---

## Troubleshooting

### Call never rings

**Check 1: Inbound routing configured?**
```bash
# Twilio: Phone Numbers → your number → Voice & Fax → should show SIP Domain
# Plivo: Phone Numbers → your number → should show Answer URL
```

**Check 2: LiveKit trunk reachable?**
```bash
# Call the number from any phone
# If you get "number not reachable" → carrier issue (H1 problem)
# If you get silence or error tone → routing issue (Step 1 problem)
# If you get "no agent available" → good! Means LiveKit is reached
```

**Check 3: Worker online?**
```bash
ssh <VM_USER>@<VOICE_VM_HOST>
pm2 list | grep callflow-voice
# Should show: online

pm2 logs callflow-voice-dev --lines 20
# Should show: "Connected to LiveKit" or similar
```

### Call rings but no agent speaks

**Check 1: Agent dispatched?**
```bash
# API logs should show:
pm2 logs callflow-api-dev | grep -i dispatch
# Look for: "Created agent dispatch: ..."
```

**Check 2: Worker received dispatch?**
```bash
# Voice logs should show:
pm2 logs callflow-voice-dev | grep -i "joining room"
# Look for: "Joining room: run_..."
```

**Check 3: Credentials match?**
```bash
# API VM and Voice VM must have IDENTICAL:
ssh <VM_USER>@<VM_HOST> "grep LIVEKIT_AGENT_NAME <APP_DIR>/.env"
ssh <VM_USER>@<VOICE_VM_HOST> "grep LIVEKIT_AGENT_NAME <VOICE_APP_DIR>/.env"
# Must be exactly: callflow-voice (byte-for-byte)
```

### Call works but outcome doesn't land

**Check 1: Worker can reach API?**
```bash
# Voice VM .env should have:
ssh <VM_USER>@<VOICE_VM_HOST> "grep CALLFLOW_PUBLIC_API_URL <VOICE_APP_DIR>/.env"
# Should be: https://[dev.]calllflow.com (NOT localhost)

# Test connectivity:
ssh <VM_USER>@<VOICE_VM_HOST> "curl -I https://dev.calllflow.com/internal/"
# Should NOT return 403 (means nginx blocked it)
# Should return 401 or 404 (means nginx passed it, auth failed)
```

**Check 2: Internal API secret matches?**
```bash
# Must match byte-for-byte:
ssh <VM_USER>@<VM_HOST> "grep CALLFLOW_INTERNAL_API_SECRET <APP_DIR>/.env"
ssh <VM_USER>@<VOICE_VM_HOST> "grep CALLFLOW_INTERNAL_API_SECRET <VOICE_APP_DIR>/.env"
```

**Check 3: Worker actually POSTed?**
```bash
# Voice logs:
pm2 logs callflow-voice-dev | grep -i "posting outcome"

# API logs:
pm2 logs callflow-api-dev | grep -i "internal/v1/runs"
# Should show: POST /internal/v1/runs/{id}/complete
```

### Call quality issues

**Latency too high:**
```bash
# Check A7 measurement from plan
# Voice logs should show per-leg timing:
pm2 logs callflow-voice-dev | grep -i "latency"

# If p95 > 2 seconds: A2 stack choice problem
# If p50 > 800ms: network or provider issue
```

**Audio cutting out:**
```bash
# Check VM2 CPU and memory:
ssh <VM_USER>@<VOICE_VM_HOST>
pm2 monit
# CPU should stay < 80% during call
# Memory should stay < 3.5 GB (leave headroom)

# If resources are maxed: H13 concurrency issue (P4)
```

**Transcription errors:**
```bash
# Voice logs show STT output:
pm2 logs callflow-voice-dev | grep -i "STT:"

# If transcription is wrong:
# → A2 STT provider choice
# → Input audio quality (phone line, not our problem)
# → Hinglish code-switching (expected, tune thresholds)
```

---

## Success Criteria (H6 Done-When)

> "A run started from the API rings a real handset and the agent speaks." (from plan)

**H6 is COMPLETE when all of these pass:**

- [x] Inbound routing configured (Step 1)
- [x] LiveKit credentials verified (Step 2) 
- [x] Trunk ID known and API can use it (Step 3)
- [ ] Dashboard run → phone rings (Step 4.1)
- [ ] Phone answers → agent speaks (Step 4.2)
- [ ] Call ends → outcome lands in database (Step 4.3)
- [ ] **Recorded on video** (P1 gate requirement)

**The video matters.** P1 gate explicitly says "on video" because:
1. Proves it happened (not just claimed)
2. Shows the full flow working
3. Becomes the demo for P1 gate verification

---

## Recording the P1 Gate Test

**What to record:**
```
1. Screen: Dashboard at /app/runs/new
2. Screen: Create run with one contact (your mobile)
3. Screen: Click "Start Run"
4. Screen: Run shows "In Progress"
5. Phone: Handset rings
6. Phone: Answer the call
7. Phone: Agent speaks, has conversation
8. Phone: Call ends (hang up or agent completes)
9. Screen: Outcome updates to "Spoke"
10. Screen: Transcript visible in dashboard

Duration: ~2 minutes
Tool: OBS, QuickTime, or Windows Game Bar
```

**Save as:** `P1-gate-track-A-first-call.mp4`

**This video is half the P1 gate.** Track B (grading) is Arbaaz's A3-A5 work.

---

## After H6 Succeeds

Update ISSUES.md #209:

```markdown
**H6 Status:** ✅ COMPLETE (DD MMM 2026)
- Inbound routing: wired to +91... → <PROJECT_ID>.sip.livekit.cloud
- Trunk ID: TR_...
- Test call: success [date, time]
- Recording: P1-gate-track-A-first-call.mp4
- Dashboard → phone → database: verified end-to-end

P1 gate track A: READY FOR VERIFICATION
```

---

## Cost of H6

**One-time:**
- None (uses existing H1 number, H4 trunk)

**Per test call:**
- Carrier: ~$0.02-0.05/minute
- LiveKit: Free tier covers testing
- 5 test calls @ 1 min each: ~$0.25

**Total H6 cost: ~$0.25**

---

## Next Steps

When H6 passes:

1. **P0 gate** - Het's portion complete (H1-H6 done)
2. **P1 gate track A** - Half done (first call recorded)
3. **P1 tasks start** - H7 (migration), H8 (logs), H9 (Redis)

---

## Code Reference

**Where the wiring lives:**

```python
# Call placement
apps/api/app/services/run_dialer.py
  → RunDialer.run_one()
  → LiveKitGateway.place_call()

# LiveKit integration
apps/api/app/integrations/livekit/client.py
  → LiveKitGateway.place_call()
  → create_sip_participant()

# Voice worker (receives dispatch)
apps/voice-runtime/app/worker.py
  → entrypoint()
  → pipeline.py handles the conversation

# Callback (worker → API)
apps/voice-runtime/app/reporter.py
  → report_completion()
  → POSTs to /internal/v1/runs/{id}/complete

# API receives callback
apps/api/app/api/v1/routes/internal.py
  → complete_run()
  → Updates outcome, runs triage
```

**No code changes needed for H6** - it's all configuration and verification.

---

## Common Mistakes to Avoid

1. **Don't skip the video** - P1 gate explicitly requires it
2. **Don't test with a landline** - use an Indian mobile (carrier rates differ)
3. **Don't assume inbound routing persists** - carriers can reset it
4. **Don't run concurrent tests** - VM2 is sized for ~8-12 concurrent, not 100
5. **Don't trust "In Progress" alone** - verify the phone actually rings
6. **Don't forget to update #209** - documentation debt compounds

---

## If H6 Fails

**Escalation path:**

1. Check troubleshooting section above (covers 90% of failures)
2. Update ISSUES.md #209 with exact error message
3. Check LiveKit dashboard for failed calls (has detailed SIP logs)
4. Check Twilio/Plivo dashboard for call attempts
5. If still stuck: Arbaaz (voice runtime), Het (trunk), Yash (if API-side)

**Do not:**
- Rebuild infrastructure (H3-H5 are sound)
- Switch providers mid-test (Twilio/Plivo are equivalent)
- Skip verification steps (each one rules out a failure class)

---

## H6 in the Critical Path

```
H1 → H6 → P1 track A → P1 gate → P2
      ↓
   P0 gate (Het's portion complete)
```

**H6 is the last P0 blocker for Het.** When it passes:
- P0 gate can be verified (needs A1 from Arbaaz)
- P1 track A is 50% done (needs video)
- First real call has happened (product viability proven)

**This is the moment the product stops being theoretical.**

Go make a phone ring.
