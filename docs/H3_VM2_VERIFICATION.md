# H3 - VM2 Voice Runtime Verification

**Owner:** Het  
**Status:** Infrastructure complete, needs VM2 and test deploy  
**Time:** 30 min setup + 10 min per test deploy  
**Date:** 13 Sep 2026

---

## What H3 Delivered (Commit 5fa3a46)

✅ Complete voice deployment chain in CI/CD  
✅ `scripts/bootstrap-voice.sh` with Python 3.12 provisioning via uv  
✅ pm2 isolation (`--only callflow-voice[-dev]`)  
✅ Separate VM architecture (no shared state with API/web)  
✅ No port binding (outbound worker, not a server)  
✅ No database connection (reports via HTTP to API)

---

## Prerequisites

### 1. VM2 Must Exist

You need a second VM (Ubuntu 20.04+ recommended) with:
- SSH access for the deploy key
- Outbound internet access (pulls from GitHub, reaches LiveKit Cloud)
- No inbound ports required (worker dials out only)

**Minimum specs:**
- 4 GB RAM (plan says both VMs are 4 GB each)
- 200 GB disk
- 2 vCPU minimum

**Does VM2 exist?**
- [ ] Yes, at: `________________` (hostname/IP)
- [ ] No → Provision it first (cloud provider or physical)

### 2. SSH Access

The same deploy key (`VM_SSH_KEY`) must be authorized on both VMs:

```bash
# Test from your laptop
ssh <VM_USER>@<VOICE_VM_HOST>

# If this fails, add the deploy key:
# On VM2:
mkdir -p ~/.ssh
chmod 700 ~/.ssh
cat >> ~/.ssh/authorized_keys  # paste the public key
chmod 600 ~/.ssh/authorized_keys
```

---

## Step 1: Configure GitHub Environment (10 min)

Navigate to: **Settings → Environments → [dev or main]**

### Required Variables (add these)

```yaml
VOICE_VM_HOST:
  Description: VM2's hostname or IP address
  Value: <voice-vm-hostname-or-ip>
  # Examples: voice.calllflow.com, 203.0.113.42

VOICE_APP_DIR:
  Description: Checkout directory on VM2
  Value: /var/www/callflow-ai-voice-dev  # for dev
  # or: /var/www/callflow-ai-voice       # for production

VOICE_EXTRAS:
  Description: AI provider plugins to install
  Value: sarvam,deepgram,elevenlabs,openai
  # Default is all of them; override only if you need fewer
```

### Required Secrets (add these)

```yaml
VOICE_ENV_FILE_B64:
  Description: base64-encoded .env for voice VM
  Value: <base64-string>
```

**How to generate VOICE_ENV_FILE_B64:**

```bash
# Create the voice .env file locally first
cat > voice.env <<'EOF'
LIVEKIT_URL=wss://placeholder.livekit.cloud
LIVEKIT_API_KEY=placeholder
LIVEKIT_API_SECRET=placeholder
CALLFLOW_PUBLIC_API_URL=https://dev.calllflow.com
CALLFLOW_INTERNAL_API_SECRET=<same-as-API-vm>
LIVEKIT_AGENT_NAME=callflow-voice
EOF

# Verify no forbidden variables
# These must NOT be in voice.env:
# - DATABASE_URL
# - DIRECT_URL
# - PROVIDER_CREDENTIALS_KEY
# - SUPABASE_SERVICE_ROLE_KEY

# Encode
base64 -w0 voice.env

# Copy the output and paste into GitHub secret VOICE_ENV_FILE_B64
```

**CRITICAL:** `CALLFLOW_INTERNAL_API_SECRET` must match the API VM's value **byte-for-byte**.
Get it from: `ssh <VM_USER>@<VM_HOST> "grep CALLFLOW_INTERNAL_API_SECRET <APP_DIR>/.env"`

---

## Step 2: Test Deploy (10 min)

### 2.1 Trigger voice deployment

```bash
# Make a trivial change to voice-runtime
cd CallFlow-AI
git checkout dev

# Touch a file to trigger voice deployment
touch apps/voice-runtime/app/worker.py

git add apps/voice-runtime/app/worker.py
git commit -m "test: trigger voice deployment for H3 verification"
git push origin dev
```

### 2.2 Watch CI/CD

```
Navigate to: GitHub → Actions → CI/CD workflow
Watch these jobs:
1. changes → should detect voice=true
2. voice (lint & tests) → should pass
3. provision-voice → should succeed
4. deploy-voice → should succeed
```

**Expected provision-voice output:**
```
==> cloning dev into /var/www/callflow-ai-voice-dev
==> using Python 3.12.X at /path/to/python
==> creating .venv
==> installing the voice runtime with extras: sarvam,deepgram,elevenlabs,openai
==> provisioned: voice runtime for dev
```

**Expected deploy-voice output:**
```
pm2 startOrRestart /var/www/callflow-ai-voice-dev/ecosystem.config.js --only callflow-voice-dev --update-env
[PM2] Process launched
pm2 save
```

---

## Step 3: Verify Running (5 min)

### 3.1 SSH to VM2

```bash
ssh <VM_USER>@<VOICE_VM_HOST>
```

### 3.2 Check pm2 status

```bash
pm2 list
```

**Expected output:**
```
┌────┬────────────────────┬──────────┬─────────┬───────────┬────────┬─────────┐
│ id │ name               │ mode     │ status  │ ↺         │ cpu    │ mem     │
├────┼────────────────────┼──────────┼─────────┼───────────┼────────┼─────────┤
│ 0  │ callflow-voice-dev │ fork     │ online  │ 0         │ 0%     │ 120 MB  │
└────┴────────────────────┴──────────┴─────────┴───────────┴────────┴─────────┘
```

**Good signs:**
- status: `online`
- restarts (↺): 0 or low number
- mem: 100-200 MB typical at idle

**Bad signs:**
- status: `errored`, `stopped`, `launching`
- restarts: constantly incrementing (crash loop)

### 3.3 Check logs

```bash
pm2 logs callflow-voice-dev --lines 50
```

**Good output:**
```
INFO:app.worker:Starting voice agent worker
INFO:app.worker:LiveKit URL: wss://placeholder.livekit.cloud
INFO:app.worker:Agent name: callflow-voice
INFO:livekit.agents:Connecting to LiveKit...
```

**Bad output (means env is wrong):**
```
FATAL: LIVEKIT_URL is missing or empty
# or
FATAL: .env on the voice host contains DATABASE_URL
```

---

## Step 4: Test Isolation (5 min)

Verify the worker is properly isolated:

### 4.1 Check environment

```bash
# On VM2
cat /var/www/callflow-ai-voice-dev/.env
```

**Should contain ONLY these 5-6 keys:**
```bash
LIVEKIT_URL=...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
CALLFLOW_PUBLIC_API_URL=...
CALLFLOW_INTERNAL_API_SECRET=...
LIVEKIT_AGENT_NAME=callflow-voice
# Optional: CALLFLOW_ENV=dev
```

**Should NOT contain:**
```bash
DATABASE_URL         # ← bootstrap-voice.sh refuses if present
DIRECT_URL
PROVIDER_CREDENTIALS_KEY
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_URL
SUPABASE_ANON_KEY
```

### 4.2 Verify no database connection

```bash
# Should fail or return nothing
pm2 logs callflow-voice-dev | grep -i postgres
pm2 logs callflow-voice-dev | grep -i supabase
```

### 4.3 Verify separate checkout

```bash
# On VM2
cd /var/www/callflow-ai-voice-dev
git status
git branch  # should be on dev (or main for production)

# Compare to API VM
ssh <VM_USER>@<VM_HOST> "cd <APP_DIR> && git rev-parse HEAD"
ssh <VM_USER>@<VOICE_VM_HOST> "cd <VOICE_APP_DIR> && git rev-parse HEAD"
# Should be the same commit (same deploy)
```

---

## Step 5: Test Independent Restart (3 min)

Verify VM2 can restart without touching VM1:

```bash
# On VM2
pm2 restart callflow-voice-dev

# Watch it come back
pm2 list
# status should return to 'online' within 5-10 seconds

# On VM1 (API VM) - should be unchanged
ssh <VM_USER>@<VM_HOST> "pm2 list | grep callflow-api"
# Should show no restart, same uptime
```

---

## Step 6: Test Redeploy (5 min)

Verify the deploy chain works repeatedly:

```bash
# Make another trivial change
touch apps/voice-runtime/README.md
git add apps/voice-runtime/README.md
git commit -m "test: H3 redeploy verification"
git push origin dev

# Watch CI/CD again
# All three jobs (provision-voice, deploy-voice, health check) should succeed

# On VM2
pm2 list
# Should show recent restart (↺ incremented, uptime reset)
```

---

## Done-When Checklist (from plan)

> "`pm2 list` on VM2 shows the runtime up, and a push to main deploys it without touching VM1."

- [x] Infrastructure complete (commit 5fa3a46)
- [ ] VM2 exists and is SSH-accessible
- [ ] GitHub environment variables set (VOICE_VM_HOST, VOICE_APP_DIR, VOICE_ENV_FILE_B64)
- [ ] Test deploy triggered and succeeds
- [ ] `pm2 list` shows callflow-voice[-dev] online
- [ ] Logs show clean worker startup
- [ ] Environment has 5-6 keys only, no database credentials
- [ ] Independent restart works (VM2 restart doesn't touch VM1)
- [ ] Redeploy works (push → CI → VM2 update)

**When all checked: H3 is COMPLETE.**

---

## Troubleshooting

### Issue: "Host key verification failed"
```bash
# SSH has never connected to VM2 before
# Solution: Add to known_hosts
ssh-keyscan -H <VOICE_VM_HOST> >> ~/.ssh/known_hosts

# Or for GitHub Actions runner
# Add to provision-voice job:
- run: ssh-keyscan -H $VOICE_VM_HOST >> ~/.ssh/known_hosts
```

### Issue: "Permission denied (publickey)"
```bash
# Deploy key not authorized on VM2
# Solution: Add VM_SSH_KEY's public key to VM2's authorized_keys
```

### Issue: "pm2: command not found"
```bash
# Node or pm2 not installed on VM2
# Solution: bootstrap-voice.sh installs both, but needs sudo
# Verify VM2 user has passwordless sudo OR pre-install:
sudo npm install -g pm2
```

### Issue: Worker crash loop with "ModuleNotFoundError"
```bash
# Python version too old (need 3.11+)
# Solution: bootstrap-voice.sh provisions 3.12 via uv
# Verify: pm2 logs | grep "using Python"
# Should show: "using Python 3.12.X"
```

### Issue: "FATAL: LIVEKIT_URL is missing"
```bash
# VOICE_ENV_FILE_B64 is wrong or not set
# Solution:
# 1. Verify secret exists in GitHub → Environments → [dev|main] → Secrets
# 2. Decode locally to check: echo "$VOICE_ENV_FILE_B64" | base64 -d
# 3. Verify all 5 required keys present
```

### Issue: "worker starts but never receives jobs"
```bash
# LIVEKIT_AGENT_NAME mismatch between API and voice VMs
# Solution: Both must be 'callflow-voice' exactly
# Check API VM: grep LIVEKIT_AGENT_NAME <APP_DIR>/.env
# Check voice VM: grep LIVEKIT_AGENT_NAME <VOICE_APP_DIR>/.env
```

---

## Health Check Command

```bash
# One command to verify H3 status
ssh <VM_USER>@<VOICE_VM_HOST> '
  echo "==> pm2 status"
  pm2 list | grep callflow-voice
  echo ""
  echo "==> Recent logs"
  pm2 logs callflow-voice-dev --lines 5 --nostream
  echo ""
  echo "==> Environment keys"
  grep "^[A-Z_]*=" /var/www/callflow-ai-voice-dev/.env | cut -d= -f1
  echo ""
  echo "==> Git status"
  cd /var/www/callflow-ai-voice-dev && git branch && git rev-parse --short HEAD
'
```

**Copy this into a script for quick status checks.**

---

## Next Steps

After H3 verification passes:
1. **H4** - LiveKit Cloud setup (no blockers, do now)
2. **H1** - Chase vendor signup daily
3. **H6** - Wire trunk when H1+H4 complete

---

## Recording Success

Update ISSUES.md #209:

```markdown
**H3 Status:** ✅ COMPLETE (DD MMM 2026)
- VM2 host: <VOICE_VM_HOST>
- Checkout: <VOICE_APP_DIR>
- pm2 process: callflow-voice-dev (online)
- Deploy test: success [commit hash]
- Isolation verified: no database credentials present
- Independent restart: verified
```
