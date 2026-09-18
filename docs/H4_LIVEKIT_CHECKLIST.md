# H4 - LiveKit Cloud Setup Checklist

**Owner:** Het  
**Status:** Ready to execute (no blockers)  
**Time:** ~15-20 minutes  
**Date:** 13 Sep 2026

---

## Prerequisites

- [ ] Browser with access to https://cloud.livekit.io/
- [ ] Text editor to capture credentials
- [ ] Access to edit `.env` files on both VMs (or capture for later)
- [ ] H1 vendor account credentials (Twilio or Plivo) - can be placeholder initially

---

## Step 1: Create LiveKit Cloud Project (5 min)

### 1.1 Sign up / Log in
```
Navigate to: https://cloud.livekit.io/
Create account or log in
```

### 1.2 Create new project
```
Click: "Create Project" or "New Project"
Project name: callflow-production  (or callflow-dev for dev environment)
Region: Select closest to India (Singapore recommended)
```

### 1.3 Capture project credentials
```
After creation, note these three values:

1. Project URL: wss://<PROJECT_ID>.livekit.cloud
   └─> This becomes LIVEKIT_URL

2. API Key: lk...
   └─> This becomes LIVEKIT_API_KEY

3. API Secret: <long-string>
   └─> This becomes LIVEKIT_API_SECRET
```

**Save these immediately** - the secret may not be shown again.

---

## Step 2: Create Outbound SIP Trunk (5 min)

### 2.1 Navigate to SIP section
```
In LiveKit dashboard:
Left sidebar → SIP → Trunks → Create Trunk
```

### 2.2 Configure outbound trunk (CallFlow → PSTN)

**For Twilio:**
```yaml
Name: callflow-twilio-out
Type: Outbound
Direction: Egress

SIP Endpoint:
  Host: <TWILIO_ACCOUNT_SID>.pstn.twilio.com
  Port: 5060
  Transport: UDP

Authentication:
  Username: <TWILIO_ACCOUNT_SID>
  Password: <TWILIO_AUTH_TOKEN>
```

**For Plivo:**
```yaml
Name: callflow-plivo-out
Type: Outbound
Direction: Egress

SIP Endpoint:
  Host: sip.plivo.com
  Port: 5060
  Transport: UDP

Authentication:
  Username: <PLIVO_AUTH_ID>
  Password: <PLIVO_AUTH_TOKEN>
```

### 2.3 Capture SIP host
```
After trunk creation, note:

SIP Host: <PROJECT_ID>.sip.livekit.cloud
└─> This becomes LIVEKIT_SIP_HOST (API .env only)
```

---

## Step 3: Configure Inbound Routing (5 min)

**This step can use a placeholder if H1 number doesn't exist yet.**

### 3.1 In Twilio (when number exists)
```
1. Navigate to: Phone Numbers → Active Numbers
2. Select the number from H1
3. Voice & Fax section:
   - Configure With: SIP
   - SIP Domain: <PROJECT_ID>.sip.livekit.cloud
4. Save
```

### 3.2 In Plivo (when number exists)
```
1. Navigate to: Phone Numbers → Your Numbers
2. Select the number from H1
3. Application Type: XML
4. Answer URL: https://<PROJECT_ID>.sip.livekit.cloud/sip/inbound
5. Save
```

**If H1 number doesn't exist yet:**
- Skip this step for now
- Come back when H1 completes
- Outbound trunk can still be tested

---

## Step 4: Update Environment Variables (5 min)

### 4.1 Values to set (both VMs)

**For API VM `.env`:**
```bash
# Add or update these lines
LIVEKIT_URL=wss://<PROJECT_ID>.livekit.cloud
LIVEKIT_API_KEY=<api-key-from-step-1.3>
LIVEKIT_API_SECRET=<api-secret-from-step-1.3>
LIVEKIT_AGENT_NAME=callflow-voice
LIVEKIT_SIP_HOST=<PROJECT_ID>.sip.livekit.cloud
```

**For Voice VM `.env` (must match API VM exactly for these 4):**
```bash
LIVEKIT_URL=wss://<PROJECT_ID>.livekit.cloud
LIVEKIT_API_KEY=<api-key-from-step-1.3>
LIVEKIT_API_SECRET=<api-secret-from-step-1.3>
LIVEKIT_AGENT_NAME=callflow-voice
```

### 4.2 Apply to deployed environments

**Option A: Edit on VM (recommended per new policy)**
```bash
# API VM
ssh <VM_USER>@<VM_HOST>
cd <APP_DIR>
nano .env  # or vi, edit the 5 values above
pm2 restart callflow-api[-dev] --update-env

# Voice VM
ssh <VM_USER>@<VOICE_VM_HOST>
cd <VOICE_APP_DIR>
nano .env  # edit the 4 values above
pm2 restart callflow-voice[-dev] --update-env

# Capture back to GitHub secrets
ssh <VM_USER>@<VM_HOST> "cat <APP_DIR>/.env" | base64 -w0 | gh secret set ENV_FILE_B64 --env [main|dev]
ssh <VM_USER>@<VOICE_VM_HOST> "cat <VOICE_APP_DIR>/.env" | base64 -w0 | gh secret set VOICE_ENV_FILE_B64 --env [main|dev]
```

**Option B: Update GitHub secrets first**
```bash
# Encode the full .env file
base64 -w0 /path/to/local/.env | gh secret set ENV_FILE_B64 --env [main|dev]
base64 -w0 /path/to/local/voice.env | gh secret set VOICE_ENV_FILE_B64 --env [main|dev]

# Then redeploy to seed the values
git commit --allow-empty -m "chore: trigger redeploy for LiveKit credentials"
git push origin [main|dev]
```

---

## Step 5: Record in DEPLOYMENT.md (2 min)

Update `DEPLOYMENT.md` §2b with actual values:

```markdown
## 2b. LiveKit Cloud and SIP trunk

**Status:** Provisioned 13 Sep 2026

**Project Details:**
- Project ID: <PROJECT_ID>
- Project URL: wss://<PROJECT_ID>.livekit.cloud
- SIP Host: <PROJECT_ID>.sip.livekit.cloud
- Region: Singapore (or chosen region)

**Trunk Configuration:**
- Name: callflow-[twilio|plivo]-out
- Type: Outbound egress
- Carrier: [Twilio|Plivo]
- Status: ✅ Active

**Inbound Routing:**
- H1 Number: [+91... or "Pending H1"]
- Wired: [Yes/No - date]
```

---

## Step 6: Update Issue Tracker (1 min)

In `ISSUES.md` #209, add:

```markdown
**H4 Status:** ✅ COMPLETE (13 Sep 2026)
- LiveKit project: <PROJECT_ID>
- SIP host: <PROJECT_ID>.sip.livekit.cloud
- Outbound trunk: configured
- Inbound routing: [wired to +91.../pending H1]
- Credentials: deployed to both VMs
```

---

## Verification (Optional - requires H1)

**Can only verify after H1 completes.** This will be done in H6.

```bash
# Quick connection test (from anywhere with curl)
curl -I wss://<PROJECT_ID>.livekit.cloud
# Should return WebSocket handshake or 101 Switching Protocols

# Full test requires:
# - H1 number provisioned
# - H6 wiring complete
# - Actual test call
```

---

## Rollback Plan

If something goes wrong:

```bash
# 1. Revert .env changes on both VMs
git log --oneline  # find commit before LiveKit credentials
ssh <VM_USER>@<VM_HOST> "cd <APP_DIR> && git checkout <commit> -- .env"
ssh <VM_USER>@<VOICE_VM_HOST> "cd <VOICE_APP_DIR> && git checkout <commit> -- .env"
pm2 restart all --update-env

# 2. Or just comment out LIVEKIT_URL in .env
# This makes LIVEKIT_SIP_HOST evaluation return empty
# Which means check_dial_allowed refuses all dials (safe)
```

---

## Common Issues

### Issue: "API Key invalid"
**Solution:** Regenerate key in LiveKit dashboard, update both VMs

### Issue: "SIP trunk unreachable"
**Solution:** Verify carrier credentials are correct, check trunk status in dashboard

### Issue: "Worker not registering"
**Solution:** Verify LIVEKIT_AGENT_NAME matches exactly on both VMs (byte-for-byte)

### Issue: Deploy says "differs from secret"
**Solution:** Expected with new policy - the NOTE is informational, not an error.
Run the capture-back command to sync the seed.

---

## Done-When Checklist

- [x] LiveKit project exists with captured credentials
- [x] SIP trunk created and configured
- [x] Credentials deployed to API VM `.env`
- [x] Credentials deployed to Voice VM `.env`
- [x] Both VMs restarted with `--update-env`
- [x] Values recorded in DEPLOYMENT.md §2b
- [x] ISSUES.md #209 updated with "H4 complete"
- [ ] Inbound routing wired (blocked on H1 - done in H6)

**Estimated total time:** 15-20 minutes (excluding H1 wait)

---

## Next Steps

After H4 completes:
1. **Chase H1 daily** - vendor KYC is the blocker
2. When H1 completes, execute Step 3 (inbound routing)
3. Then proceed to **H6** - wire the trunk end-to-end
