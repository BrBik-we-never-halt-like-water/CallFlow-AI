#!/usr/bin/env bash
#
# GitHub Environment Setup Helper
#
# Interactive script to set up GitHub Environment variables and secrets
# for CallFlow AI deployment.
#
# Prerequisites:
#   - gh CLI installed and authenticated
#   - Access to the repository
#   - The .env files you want to seed from
#
# Usage:
#   bash scripts/setup-github-env.sh [dev|main]
#
set -euo pipefail

REPO="BrBik-we-never-halt-like-water/CallFlow-AI"
ENV_NAME="${1:-dev}"

if [ "$ENV_NAME" != "dev" ] && [ "$ENV_NAME" != "main" ]; then
    echo "Usage: $0 [dev|main]"
    exit 1
fi

echo "Setting up GitHub Environment: $ENV_NAME"
echo "Repository: $REPO"
echo ""

# Check gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "ERROR: gh CLI is not installed"
    echo "Install from: https://cli.github.com/"
    exit 1
fi

# Check authentication
if ! gh auth status &> /dev/null; then
    echo "ERROR: Not authenticated with GitHub"
    echo "Run: gh auth login"
    exit 1
fi

echo "Prerequisites OK"
echo ""

# ============================================================================
# Variables (non-secret)
# ============================================================================
echo "=== Variables (non-secret) ==="
echo ""

read -p "VM_HOST (API VM hostname/IP): " VM_HOST
read -p "VM_USER (SSH user for both VMs): " VM_USER
read -p "APP_DIR (API checkout path, e.g. /var/www/callflow-ai-dev): " APP_DIR
read -p "PUBLIC_URL (API public URL, e.g. https://dev.calllflow.com): " PUBLIC_URL
read -p "VOICE_VM_HOST (Voice VM hostname/IP): " VOICE_VM_HOST
read -p "VOICE_APP_DIR (Voice checkout path, e.g. /var/www/callflow-ai-voice-dev): " VOICE_APP_DIR

echo ""
echo "Setting variables..."

gh variable set VM_HOST --repo "$REPO" --env "$ENV_NAME" --body "$VM_HOST"
gh variable set VM_USER --repo "$REPO" --env "$ENV_NAME" --body "$VM_USER"
gh variable set APP_DIR --repo "$REPO" --env "$ENV_NAME" --body "$APP_DIR"
gh variable set PUBLIC_URL --repo "$REPO" --env "$ENV_NAME" --body "$PUBLIC_URL"
gh variable set VOICE_VM_HOST --repo "$REPO" --env "$ENV_NAME" --body "$VOICE_VM_HOST"
gh variable set VOICE_APP_DIR --repo "$REPO" --env "$ENV_NAME" --body "$VOICE_APP_DIR"

echo "✓ Variables set"
echo ""

# ============================================================================
# Secrets (from files)
# ============================================================================
echo "=== Secrets (from files) ==="
echo ""

# SSH Key
read -p "Path to VM SSH private key (default: ~/.ssh/id_rsa): " SSH_KEY_PATH
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_rsa}"

if [ -f "$SSH_KEY_PATH" ]; then
    echo "Setting VM_SSH_KEY..."
    gh secret set VM_SSH_KEY --repo "$REPO" --env "$ENV_NAME" < "$SSH_KEY_PATH"
    echo "✓ VM_SSH_KEY set"
else
    echo "✗ SSH key not found at $SSH_KEY_PATH"
    echo "  Skipping VM_SSH_KEY"
fi

echo ""

# API .env
read -p "Path to API .env file (or press Enter to skip): " API_ENV_PATH

if [ -n "$API_ENV_PATH" ] && [ -f "$API_ENV_PATH" ]; then
    echo "Setting ENV_FILE_B64..."
    base64 -w0 < "$API_ENV_PATH" | gh secret set ENV_FILE_B64 --repo "$REPO" --env "$ENV_NAME"
    echo "✓ ENV_FILE_B64 set"
else
    echo "  Skipping ENV_FILE_B64 (set manually later)"
fi

echo ""

# Web .env.local
read -p "Path to web .env.local file (or press Enter to skip): " WEB_ENV_PATH

if [ -n "$WEB_ENV_PATH" ] && [ -f "$WEB_ENV_PATH" ]; then
    echo "Setting WEB_ENV_FILE_B64..."
    base64 -w0 < "$WEB_ENV_PATH" | gh secret set WEB_ENV_FILE_B64 --repo "$REPO" --env "$ENV_NAME"
    echo "✓ WEB_ENV_FILE_B64 set"
else
    echo "  Skipping WEB_ENV_FILE_B64 (set manually later)"
fi

echo ""

# Voice .env
read -p "Path to voice .env file (or press Enter to skip): " VOICE_ENV_PATH

if [ -n "$VOICE_ENV_PATH" ] && [ -f "$VOICE_ENV_PATH" ]; then
    echo "Setting VOICE_ENV_FILE_B64..."

    # Verify no forbidden variables
    if grep -qE "^(DATABASE_URL|DIRECT_URL|PROVIDER_CREDENTIALS_KEY|SUPABASE_SERVICE_ROLE_KEY)=" "$VOICE_ENV_PATH"; then
        echo "✗ ERROR: Voice .env contains forbidden variables"
        echo "  Voice VM must NOT have database/provider credentials"
        echo "  See DEPLOYMENT.md §3b for required keys only"
        echo "  Skipping VOICE_ENV_FILE_B64"
    else
        base64 -w0 < "$VOICE_ENV_PATH" | gh secret set VOICE_ENV_FILE_B64 --repo "$REPO" --env "$ENV_NAME"
        echo "✓ VOICE_ENV_FILE_B64 set"
    fi
else
    echo "  Skipping VOICE_ENV_FILE_B64 (set manually later)"
fi

echo ""

# ============================================================================
# Optional Secrets
# ============================================================================
echo "=== Optional Secrets ==="
echo ""

read -p "Do you have Cloudflare Origin Certificate? (y/N): " HAS_CF
if [[ "$HAS_CF" =~ ^[Yy]$ ]]; then
    read -p "Path to origin.pem: " CERT_PATH
    read -p "Path to origin-key.pem: " KEY_PATH

    if [ -f "$CERT_PATH" ] && [ -f "$KEY_PATH" ]; then
        echo "Setting ORIGIN_CERT_B64 and ORIGIN_KEY_B64..."
        base64 -w0 < "$CERT_PATH" | gh secret set ORIGIN_CERT_B64 --repo "$REPO" --env "$ENV_NAME"
        base64 -w0 < "$KEY_PATH" | gh secret set ORIGIN_KEY_B64 --repo "$REPO" --env "$ENV_NAME"
        echo "✓ Origin certificates set"
    fi
fi

echo ""

read -p "Certbot email (or press Enter to skip): " CERTBOT_EMAIL
if [ -n "$CERTBOT_EMAIL" ]; then
    gh secret set CERTBOT_EMAIL --repo "$REPO" --env "$ENV_NAME" --body "$CERTBOT_EMAIL"
    echo "✓ CERTBOT_EMAIL set"
fi

echo ""

# ============================================================================
# Verification
# ============================================================================
echo "=== Verification ==="
echo ""

echo "Variables set:"
gh variable list --repo "$REPO" --env "$ENV_NAME"

echo ""
echo "Secrets set:"
gh secret list --repo "$REPO" --env "$ENV_NAME"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Environment '$ENV_NAME' is configured in GitHub."
echo ""
echo "Next steps:"
echo "  1. Verify the lists above look correct"
echo "  2. If ENV_FILE_B64, WEB_ENV_FILE_B64, or VOICE_ENV_FILE_B64 were skipped,"
echo "     set them manually with:"
echo "       base64 -w0 /path/to/file | gh secret set SECRET_NAME --repo $REPO --env $ENV_NAME"
echo "  3. Push a commit to trigger deployment"
echo "  4. Check Actions tab for deployment status"
echo ""
