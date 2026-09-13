# Het's P0 Status - Road to First Pilot

**Gate Captain:** Het (P4)  
**Current Phase:** P0 - Clear the ground  
**Updated:** 13 Sep 2026

---

## P0 Tasks Status

| Task | Status | Blocked By | Next Action |
|------|--------|-----------|-------------|
| **H1** One number that can dial | 🟡 TOOLING DONE | Vendor KYC queue | Start Twilio/Plivo signup TODAY |
| **H2** DLT/TRAI registration | 🟡 DOCS DONE | M10 entity incorporation | Submit PE when entity exists |
| **H3** VM2 provisioned | 🟡 INFRA DONE | VM2 must exist | Verify VM2 accessible, test deploy |
| **H4** LiveKit Cloud + trunk | 🟢 READY TO START | None | Create project NOW |
| **H5** Move Next build off VM1 | ✅ COMPLETE | - | - |
| **H6** Wire the trunk | 🔴 BLOCKED | H1 + H4 | Wait for number and trunk |

**Legend:** ✅ Complete | 🟢 Ready to start | 🟡 In progress | 🔴 Blocked

---

## Completed Work (3 commits on dev branch)

### H1 - Probe dial tooling ✅
**Commit:** `e892103` feat(P0-H1-H2): telephony compliance docs and probe-dial tooling

**Delivered:**
- `scripts/probe-dial.py` - command-line tool to test Twilio/Plivo numbers directly
- `scripts/probe-dial-answer.xml` - Plivo answer file
- Works from laptop, no full stack required

**Usage:**
```bash
# Set credentials
export TWILIO_ACCOUNT_SID=...
export TWILIO_AUTH_TOKEN=...
export TWILIO_NUMBER=...

# Test dial
python scripts/probe-dial.py --to +919876543210
```

**Blocked on:** Twilio or Plivo account (KYC + billing + number provisioning)

**Critical path:** This blocks H6, which blocks ALL of P1 track A.

---

### H2 - DLT/TRAI compliance docs ✅
**Commit:** `e892103` (same)

**Delivered:**
- `docs/TELEPHONY_COMPLIANCE.md` - complete compliance checklist
- Documents PE registration, header registration, content templates
- Customer-account checklist for D6 (pilot's real route)
- Issue #209 created to track application status

**What's required:**
1. Entity incorporation (M10's work)
2. PAN, GSTIN, authorised signatory docs
3. Submit to TSP's DLT portal (Airtel/VIL/BSNL/Jio)
4. Header registration (links PE to number)

**Blocked on:** M10 entity incorporation

**Next:** File PE registration the day M10's entity exists. Track ref number in #209.

---

### H3 - VM2 infrastructure ✅
**Commit:** `5fa3a46` feat(P0-H3): VM2 voice-runtime deployment infrastructure

**Delivered:**
- Complete CI/CD voice deployment chain: `provision-voice` → `deploy-voice`
- `scripts/bootstrap-voice.sh` - provisions Python 3.12 via uv on Ubuntu 20.04
- Voice VM deploys independently from API/web VM
- `pm2 --only callflow-voice[-dev]` ensures worker isolation
- No port (outbound worker only), no database connection

**Environment variables required (GitHub Environments):**
```bash
VOICE_VM_HOST=<vm2-hostname-or-ip>
VOICE_APP_DIR=/var/www/callflow-ai-voice[-dev]
VOICE_ENV_FILE_B64=<base64-encoded-.env>
VOICE_EXTRAS=sarvam,deepgram,elevenlabs,openai  # default
```

**VM2's .env (5 keys, never database/provider secrets):**
```bash
LIVEKIT_URL=wss://<project>.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
CALLFLOW_PUBLIC_API_URL=https://[dev.]calllflow.com
CALLFLOW_INTERNAL_API_SECRET=...  # must match API VM byte-for-byte
LIVEKIT_AGENT_NAME=callflow-voice  # must match API VM
```

**Verification needed:**
1. VM2 must exist and be accessible via SSH with VM_SSH_KEY
2. Set the 4 environment variables in GitHub → Settings → Environments → [dev/main]
3. Push a commit that changes `apps/voice-runtime/*` and watch deploy succeed
4. `ssh <VM_USER>@<VOICE_VM_HOST>` then `pm2 list` shows `callflow-voice[-dev]` up

**Done-when (from plan):** `pm2 list` on VM2 shows the runtime up, and a push to main
deploys it without touching VM1.

---

### H4 - LiveKit setup docs ✅
**Commit:** `1e0803a` docs(P0-H4): LiveKit Cloud and SIP trunk setup guide

**Delivered:**
- `DEPLOYMENT.md` §2b - complete LiveKit Cloud setup instructions
- Documents project creation, API key provisioning
- SIP trunk setup for both Twilio and Plivo (inbound + outbound)
- All required environment variables specified

**Ready to execute NOW.** Not blocked on H1 number - can create project and wire trunk
to placeholder, update when number exists.

**Steps:**
1. Go to https://cloud.livekit.io/ and create account
2. Create new project, note:
   - Project URL: `wss://<project-id>.livekit.cloud`
   - API Key
   - API Secret
3. Navigate to SIP → Trunks, create outbound trunk:
   - Name: `callflow-twilio-out` (or `callflow-plivo-out`)
   - Carrier endpoint: `<ACCOUNT_SID>.pstn.twilio.com:5060`
   - Auth: username=ACCOUNT_SID, password=AUTH_TOKEN
4. Note SIP host: `<project-id>.sip.livekit.cloud`
5. Add to both API and voice-runtime `.env`:
   ```bash
   LIVEKIT_URL=wss://<project-id>.livekit.cloud
   LIVEKIT_API_KEY=<key>
   LIVEKIT_API_SECRET=<secret>
   LIVEKIT_AGENT_NAME=callflow-voice
   ```
6. Add to API `.env` only:
   ```bash
   LIVEKIT_SIP_HOST=<project-id>.sip.livekit.cloud
   ```

**Done-when:** Trunk and project IDs recorded in DEPLOYMENT.md, credentials in
deployed `.env` on both VMs.

---

### H5 - Next.js build off VM ✅
**Status:** Already complete per CI/CD (lines 459-467, 469-487)

**Evidence:**
- `.github/workflows/ci-cd.yml` `deploy-web` job builds on GitHub Actions runner
- `npm run build` runs with `NODE_OPTIONS: --max-old-space-size=4096`
- Artifact shipped to VM and unpacked, not built on the box
- Comment on line 23: "still on the GitHub runner, in deploy-web — never on the 4 GB VM (H5)"

**No action needed.**

---

## Critical Path Analysis

```
                    ┌─ H1 (vendor queue) ─┐
                    │                      │
P0 gate depends on: │                      ├─→ H6 ─→ P1 entire track A
                    │                      │
                    └─ H4 (no blocker) ────┘
```

**The bottleneck is H1.** Starting the vendor signup TODAY is the single most important
action because:
- It gates H6 (wire the trunk)
- H6 gates the first real call
- The first real call is half of the P1 gate
- Vendor KYC is someone else's queue, not our work

**H4 can start immediately** and should - LiveKit project creation takes minutes, and
wiring to a placeholder number means H6 is ready the moment H1 completes.

---

## Immediate Action Plan

### Today (13 Sep 2026)

1. **START H1 VENDOR SIGNUP** 🔥
   - Pick Twilio or Plivo (plan says Twilio preferred, Telnyx/Vonage out of maintained path)
   - Begin account creation + entity KYC + billing setup
   - Document blocker in ISSUES.md #209 the day it appears
   
2. **Execute H4** 🟢
   - Create LiveKit Cloud project (15 minutes)
   - Provision SIP trunk (placeholder config, update when H1 number exists)
   - Record project ID and SIP host in DEPLOYMENT.md §2b
   - Update ISSUES.md #209 with "H4 complete: LiveKit project <id>"

3. **Verify H3** 🟡
   - Confirm VM2 exists and is SSH-accessible
   - Set GitHub environment variables (VOICE_VM_HOST, VOICE_APP_DIR, VOICE_ENV_FILE_B64)
   - Test deploy: touch a file in `apps/voice-runtime/` and push
   - Verify `pm2 list` shows callflow-voice running

### This week

4. **Complete H1**
   - Chase vendor KYC daily (external queue)
   - Provision number the day account is approved
   - Test with `scripts/probe-dial.py --to <teammate-number>`
   - Update ISSUES.md #209: "H1 complete: Twilio number +91..."

5. **Wire H6**
   - Connect H1 number to H4 trunk in LiveKit console
   - Update Twilio/Plivo to route to `<project>.sip.livekit.cloud`
   - Wire `CreateSIPParticipant` in `apps/api/app/integrations/livekit/client.py`
   - Test end-to-end: run started from dashboard rings a real handset
   
6. **Verify P0 gate**
   - A number that can dial an Indian mobile ✓
   - VM2 reachable and deployable ✓
   - docs/GRADING.md written and agreed (Arbaaz A1, waiting for Mridul M1 / Shivam S1)

---

## Blockers and Dependencies

| My Task | Blocked By | Who Owns Blocker | ETA |
|---------|-----------|------------------|-----|
| H1 complete | Vendor KYC queue | Twilio/Plivo support | Unknown - start TODAY |
| H2 complete | Entity incorporation | Mridul M10 | Unknown |
| H6 start | H1 + H4 | Het H1, Het H4 | H4 this week, H1 when vendor approves |
| P1 track A | H6 | Het | When H1 unblocks |

---

## Later P0 Tasks (not started)

These are documented in the plan but not yet actionable or blocked on P0 gate passing:

- **H7** (P1) - Ship the additive migration (new columns from section 5)
- **H8** (P1) - Log shipping off VM2
- **H9** (P2) - Redis and real rate limiter
- **H10** (P2) - One metrics endpoint
- **H11** (P3) - Restore the dial gate
- **H12** (P3) - Audit log for dial decisions
- **H13** (P4) - Prove VM2's concurrency ceiling
- **H14** (P4) - Backups, alerts, incident runbook

---

## Notes

- All P0 work committed to `dev` branch (3 commits)
- No merge to `main` until P0 gate verified
- Plan says "no work starts on a phase until the previous gate is verified"
- Two standing exceptions: research (M1/S1) and vendor paperwork (H1/H2) - both ours
  are in flight

**Next checkpoint:** Sunday sync. Report H1 vendor status, H4 completion, H3 verification.
