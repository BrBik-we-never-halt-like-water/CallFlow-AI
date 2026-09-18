#!/usr/bin/env bash
#
# P0 Readiness Verification Script
#
# Checks if all prerequisites for P0 gate are in place.
# Run this before attempting H6 or claiming P0 complete.
#
# Usage:
#   bash scripts/verify-p0-readiness.sh
#
set -euo pipefail

# ANSI colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

FAIL_COUNT=0
WARN_COUNT=0
PASS_COUNT=0

log_check() {
    printf "${BLUE}[CHECK]${NC} %s... " "$1"
}

log_pass() {
    printf "${GREEN}✓${NC} %s\n" "${1:-PASS}"
    ((PASS_COUNT++))
}

log_fail() {
    printf "${RED}✗${NC} %s\n" "${1:-FAIL}"
    ((FAIL_COUNT++))
}

log_warn() {
    printf "${YELLOW}⚠${NC} %s\n" "${1:-WARN}"
    ((WARN_COUNT++))
}

log_info() {
    printf "${BLUE}[INFO]${NC} %s\n" "$1"
}

log_section() {
    printf "\n${BLUE}═══ %s ═══${NC}\n" "$1"
}

# ============================================================================
# H1: One number that can dial
# ============================================================================
log_section "H1: Telephony Number"

log_check "probe-dial.py exists"
if [ -f "scripts/probe-dial.py" ]; then
    log_pass
else
    log_fail "scripts/probe-dial.py not found"
fi

log_check "probe-dial-answer.xml exists"
if [ -f "scripts/probe-dial-answer.xml" ]; then
    log_pass
else
    log_fail "scripts/probe-dial-answer.xml not found"
fi

log_check "Twilio credentials in environment"
if [ -n "${TWILIO_ACCOUNT_SID:-}" ] && [ -n "${TWILIO_AUTH_TOKEN:-}" ] && [ -n "${TWILIO_NUMBER:-}" ]; then
    log_pass "Twilio configured"
    H1_PROVIDER="twilio"
elif [ -n "${PLIVO_AUTH_ID:-}" ] && [ -n "${PLIVO_AUTH_TOKEN:-}" ] && [ -n "${PLIVO_NUMBER:-}" ]; then
    log_pass "Plivo configured"
    H1_PROVIDER="plivo"
else
    log_fail "No telephony credentials found (set TWILIO_* or PLIVO_* env vars)"
    H1_PROVIDER=""
fi

if [ -n "${H1_PROVIDER:-}" ]; then
    log_info "To test H1: python scripts/probe-dial.py --to +91XXXXXXXXXX"
fi

# ============================================================================
# H2: DLT/TRAI Documentation
# ============================================================================
log_section "H2: Compliance Documentation"

log_check "TELEPHONY_COMPLIANCE.md exists"
if [ -f "docs/TELEPHONY_COMPLIANCE.md" ]; then
    log_pass
else
    log_fail "docs/TELEPHONY_COMPLIANCE.md not found"
fi

log_check "Issue #209 tracking exists"
if grep -q "#209" ISSUES.md 2>/dev/null; then
    log_pass
else
    log_warn "Issue #209 not found in ISSUES.md"
fi

# ============================================================================
# H3: VM2 Infrastructure
# ============================================================================
log_section "H3: Voice VM Infrastructure"

log_check "bootstrap-voice.sh exists"
if [ -f "scripts/bootstrap-voice.sh" ] && [ -x "scripts/bootstrap-voice.sh" ]; then
    log_pass
else
    log_fail "scripts/bootstrap-voice.sh not found or not executable"
fi

log_check "CI/CD voice deployment configured"
if grep -q "provision-voice:" .github/workflows/ci-cd.yml 2>/dev/null; then
    log_pass
else
    log_fail "provision-voice job not found in CI/CD"
fi

log_check "ecosystem.config.js has voice entry"
if grep -q "callflow-voice" ecosystem.config.js 2>/dev/null; then
    log_pass
else
    log_fail "callflow-voice not found in ecosystem.config.js"
fi

# Can't verify VM2 is actually up without SSH access
log_info "To verify VM2: ssh <VM_USER>@<VOICE_VM_HOST> 'pm2 list | grep callflow-voice'"

# ============================================================================
# H4: LiveKit Configuration
# ============================================================================
log_section "H4: LiveKit Cloud"

log_check "DEPLOYMENT.md §2b exists"
if grep -q "## 2b. LiveKit Cloud" DEPLOYMENT.md 2>/dev/null; then
    log_pass
else
    log_fail "DEPLOYMENT.md §2b (LiveKit section) not found"
fi

log_check "LIVEKIT_URL in env"
if [ -n "${LIVEKIT_URL:-}" ]; then
    log_pass "${LIVEKIT_URL}"
else
    log_warn "LIVEKIT_URL not set (check .env)"
fi

log_check "LIVEKIT_API_KEY in env"
if [ -n "${LIVEKIT_API_KEY:-}" ]; then
    log_pass "Set"
else
    log_warn "LIVEKIT_API_KEY not set (check .env)"
fi

log_check "LIVEKIT_SIP_HOST in env"
if [ -n "${LIVEKIT_SIP_HOST:-}" ]; then
    log_pass "${LIVEKIT_SIP_HOST}"
else
    log_warn "LIVEKIT_SIP_HOST not set (check .env)"
fi

# ============================================================================
# H5: Next.js Build Location
# ============================================================================
log_section "H5: Next.js Build"

log_check "deploy-web builds on runner"
if grep -A 20 "deploy-web:" .github/workflows/ci-cd.yml | grep -q "npm run build"; then
    log_pass "Builds in CI, not on VM"
else
    log_warn "Could not verify build location"
fi

# ============================================================================
# H6: Readiness
# ============================================================================
log_section "H6: End-to-End Wiring"

log_check "H6_WIRING_GUIDE.md exists"
if [ -f "docs/H6_WIRING_GUIDE.md" ]; then
    log_pass
else
    log_fail "docs/H6_WIRING_GUIDE.md not found"
fi

# Check if prerequisites are likely met
H6_READY=true
if [ -z "${H1_PROVIDER:-}" ]; then
    log_fail "H6 blocked: H1 not complete (no telephony credentials)"
    H6_READY=false
fi

if [ -z "${LIVEKIT_URL:-}" ]; then
    log_fail "H6 blocked: H4 not complete (no LiveKit URL)"
    H6_READY=false
fi

if $H6_READY; then
    log_pass "H6 prerequisites appear ready"
    log_info "Follow docs/H6_WIRING_GUIDE.md to complete H6"
fi

# ============================================================================
# Documentation
# ============================================================================
log_section "P0 Documentation"

DOCS=(
    "docs/P0_README.md"
    "docs/P0_HET_STATUS.md"
    "docs/H1_VENDOR_CHECKLIST.md"
    "docs/H3_VM2_VERIFICATION.md"
    "docs/H4_LIVEKIT_CHECKLIST.md"
    "docs/H6_WIRING_GUIDE.md"
    "docs/TELEPHONY_COMPLIANCE.md"
)

for doc in "${DOCS[@]}"; do
    log_check "$(basename "$doc")"
    if [ -f "$doc" ]; then
        log_pass
    else
        log_fail "$doc not found"
    fi
done

# ============================================================================
# Summary
# ============================================================================
log_section "Summary"

TOTAL=$((PASS_COUNT + WARN_COUNT + FAIL_COUNT))

printf "\n"
printf "${GREEN}Passed:${NC}  %d/%d\n" "$PASS_COUNT" "$TOTAL"
if [ $WARN_COUNT -gt 0 ]; then
    printf "${YELLOW}Warnings:${NC} %d/%d\n" "$WARN_COUNT" "$TOTAL"
fi
if [ $FAIL_COUNT -gt 0 ]; then
    printf "${RED}Failed:${NC}  %d/%d\n" "$FAIL_COUNT" "$TOTAL"
fi
printf "\n"

if [ $FAIL_COUNT -gt 0 ]; then
    printf "${RED}✗ P0 is NOT ready${NC}\n"
    printf "Fix the failures above before proceeding to H6\n"
    exit 1
elif [ $WARN_COUNT -gt 0 ]; then
    printf "${YELLOW}⚠ P0 has warnings${NC}\n"
    printf "Review warnings - may need attention\n"
    exit 0
else
    printf "${GREEN}✓ P0 infrastructure is ready${NC}\n"
    printf "Next steps:\n"
    printf "  1. If H1 not done: Start vendor signup (docs/H1_VENDOR_CHECKLIST.md)\n"
    printf "  2. If H4 not done: Create LiveKit project (docs/H4_LIVEKIT_CHECKLIST.md)\n"
    printf "  3. When both done: Wire trunk end-to-end (docs/H6_WIRING_GUIDE.md)\n"
    exit 0
fi
