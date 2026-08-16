#!/usr/bin/env bash
#
# Bring one deployment directory to the state the pipeline expects, from
# whatever state it is in - including nothing at all.
#
# Idempotent by construction: every step checks the desired state before acting,
# so this runs on every deploy and is a no-op on the deploys where nothing
# changed. That is the whole point. Anything a human would otherwise have had to
# do on the VM lives here instead, where it is reviewed and repeatable.
#
# Run from the deploy directory, by .github/workflows/ci-cd.yml, which has
# already cloned or updated the checkout. Required in the environment:
#
#   CALLFLOW_ENV       production | dev  - picks the process names and ports
#   PUBLIC_URL         https://dev.calllflow.com
#   ENV_FILE_B64       base64 of the API .env this environment should run with
#   WEB_ENV_FILE_B64   base64 of apps/web/.env.local
#
# Optional:
#
#   ORIGIN_CERT_B64    Cloudflare Origin certificate, base64. Omit if the pair is
#   ORIGIN_KEY_B64     already on the VM at /etc/ssl/cloudflare/calllflow.{pem,key}
#   CERTBOT_EMAIL      Let's Encrypt fallback, for a host not behind Cloudflare
#   VOICE_VM_HOST      the voice runtime's address, allowed to reach /internal/.
#                      Unset closes that location to everyone.
#
# The voice runtime deploys to its own VM and its own script - see
# scripts/bootstrap-voice.sh. Nothing here installs or starts it.
#
set -euo pipefail

: "${CALLFLOW_ENV:?CALLFLOW_ENV is required}"
: "${PUBLIC_URL:?PUBLIC_URL is required}"

log() { printf '\n==> %s\n' "$*"; }

# Non-interactive check. A VM where the deploy user has no sudo still gets
# everything that does not need root; the root-only steps say what they skipped
# rather than failing the deploy.
have_sudo() { sudo -n true 2>/dev/null; }

PUBLIC_HOST=${PUBLIC_URL#*://}
PUBLIC_HOST=${PUBLIC_HOST%%/*}

# The voice runtime posts finished calls to /internal/ from its own VM. Only
# that host may reach it, and an environment with no voice VM configured gets a
# location that refuses everyone rather than one that quietly allows anyone.
if [ -n "${VOICE_VM_HOST:-}" ]; then
  VOICE_ALLOW="allow $VOICE_VM_HOST;"
else
  # A comment, not another `deny all;` - the template already denies everything
  # this does not explicitly allow, and the rendered file should say why the
  # location is shut rather than repeat itself.
  VOICE_ALLOW="# no voice host configured for this environment"
fi

# ---------------------------------------------------------------- python env
if [ ! -x .venv/bin/python ]; then
  log "creating .venv"
  python3 -m venv .venv
fi

log "installing the API"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ./apps/api

# --------------------------------------------------------------- env files
# Written from GitHub Environment secrets, so the files on the VM are copies of
# something GitHub holds rather than something a person edited in place two
# months ago and cannot reproduce. base64 because the values are multi-line and
# would not survive being passed through a shell variable intact.
write_env() {
  local path="$1" encoded="$2" secret_name="$3"

  if [ -z "$encoded" ]; then
    if [ -f "$path" ]; then
      return 0
    fi
    echo "FATAL: $path is missing and $secret_name is not set for '$CALLFLOW_ENV'." >&2
    echo "       Set it with:  base64 -w0 $path" >&2
    exit 1
  fi

  umask 077
  printf '%s' "$encoded" | base64 -d > "$path.next"
  if cmp -s "$path.next" "$path" 2>/dev/null; then
    rm -f "$path.next"
  else
    mv "$path.next" "$path"
    log "$path updated from the GitHub Environment"
  fi
}

write_env .env "${ENV_FILE_B64:-}" ENV_FILE_B64

# The web app's variables are a separate file because Next reads them from its
# own project root, and separate values because they are different names - not a
# subset of the API's. Three of the four are inlined into the bundle at BUILD
# time, so a missing one is not a runtime error you would notice in a log: the
# site builds clean and ships with `isSupabaseConfigured()` false, which makes
# the middleware wave every request through and the dashboard render with no
# auth at all. Hence failing hard here rather than warning.
write_env apps/web/.env.local "${WEB_ENV_FILE_B64:-}" WEB_ENV_FILE_B64

for required_var in NEXT_PUBLIC_SUPABASE_URL NEXT_PUBLIC_SUPABASE_ANON_KEY NEXT_PUBLIC_SITE_URL; do
  if ! grep -qE "^${required_var}=.+" apps/web/.env.local; then
    echo "FATAL: $required_var is missing or empty in apps/web/.env.local." >&2
    echo "       The build would silently ship a dashboard with authentication disabled." >&2
    exit 1
  fi
done

# ---------------------------------------------------------------------- nginx
SITE="/etc/nginx/sites-available/callflow-$CALLFLOW_ENV"

# One Origin certificate covers calllflow.com and *.calllflow.com, so it is not
# per-environment. Path follows the convention already on this box for the other
# zone, /etc/ssl/cloudflare/<zone>.{pem,key}.
CERT_DIR=/etc/ssl/cloudflare
CERT="$CERT_DIR/calllflow.pem"
KEY="$CERT_DIR/calllflow.key"

# A Cloudflare Origin CA certificate is a static 15-year file pair, so unlike ACME
# there is nothing to renew and nothing to keep reachable - it just has to be on
# disk before nginx is told to use it. Installed on every run so rotating the
# secret rotates the certificate.
if [ -n "${ORIGIN_CERT_B64:-}" ] && [ -n "${ORIGIN_KEY_B64:-}" ] && have_sudo; then
  sudo mkdir -p "$CERT_DIR"
  printf '%s' "$ORIGIN_CERT_B64" | base64 -d | sudo tee "$CERT.next" > /dev/null
  printf '%s' "$ORIGIN_KEY_B64"  | base64 -d | sudo tee "$KEY.next"  > /dev/null

  # Refuse to install a pair that does not match, rather than finding out from
  # nginx refusing to start after the old one has already been replaced.
  cert_mod=$(sudo openssl x509 -noout -modulus -in "$CERT.next" | sha256sum)
  key_mod=$(sudo openssl rsa -noout -modulus -in "$KEY.next" 2>/dev/null | sha256sum \
    || sudo openssl ec -noout -text -in "$KEY.next" 2>/dev/null | sha256sum)
  if [ "$cert_mod" != "$key_mod" ]; then
    log "certificate and key do not match - leaving the existing pair in place"
    sudo rm -f "$CERT.next" "$KEY.next"
  else
    sudo mv "$CERT.next" "$CERT"
    sudo mv "$KEY.next" "$KEY"
    sudo chmod 644 "$CERT"
    sudo chmod 600 "$KEY"
    log "Cloudflare Origin certificate installed for $CALLFLOW_ENV"
  fi
fi

# An https PUBLIC_URL with nothing able to produce a certificate is a
# misconfiguration, not a degraded mode. Left alone it renders nginx on port 80
# only, and the first sign of trouble is the deploy job's health check failing
# against a URL the site was never going to answer on.
#
# `gh secret set` will happily store an empty value - `base64 missing-file | gh
# secret set X` prints an error, exits, and still sets X to "" - so a secret can
# look configured in the UI and be empty here. This catches that.
case "$PUBLIC_URL" in
  https://*)
    if [ ! -f "$CERT" ] && [ -z "${CERTBOT_EMAIL:-}" ]; then
      echo "FATAL: PUBLIC_URL is $PUBLIC_URL but no TLS certificate is available." >&2
      if [ -n "${ORIGIN_CERT_B64:-}" ] || [ -n "${ORIGIN_KEY_B64:-}" ]; then
        echo "       ORIGIN_CERT_B64/ORIGIN_KEY_B64 are set but did not yield a" >&2
        echo "       usable pair - check they are not empty and that they match." >&2
      else
        echo "       Set ORIGIN_CERT_B64 and ORIGIN_KEY_B64 from a Cloudflare Origin" >&2
        echo "       certificate, or CERTBOT_EMAIL for a host not behind Cloudflare." >&2
      fi
      exit 1
    fi
    ;;
esac

if [ ! -f "$SITE" ] && have_sudo; then
  # Ports come from ecosystem.config.js so the proxy cannot point somewhere pm2
  # is not listening. Read here rather than at the top of the script: node is on
  # PATH for this user in practice, but only the nginx step actually needs it,
  # and `set -e` would otherwise abort a deploy that had no nginx work to do.
  API_PORT=$(node -p "require('$PWD/ecosystem.config.js').ports.api")
  WEB_PORT=$(node -p "require('$PWD/ecosystem.config.js').ports.web")

  render() {
    sed -e "s|@HOST@|$PUBLIC_HOST|g" \
        -e "s|@ENV@|$CALLFLOW_ENV|g" \
        -e "s|@API_PORT@|$API_PORT|g" \
        -e "s|@WEB_PORT@|$WEB_PORT|g" \
        -e "s|@VOICE_ALLOW@|$VOICE_ALLOW|g" "$1"
  }

  sudo mkdir -p /etc/nginx/snippets
  render scripts/nginx.locations.template \
    | sudo tee "/etc/nginx/snippets/callflow-$CALLFLOW_ENV.conf" > /dev/null

  if [ -f "$CERT" ] && [ -f "$KEY" ]; then
    template=scripts/nginx-tls.conf.template
  else
    template=scripts/nginx.conf.template
  fi

  log "writing the nginx site for $PUBLIC_HOST from ${template##*/} (web $WEB_PORT, api $API_PORT)"
  render "$template" | sudo tee "$SITE" > /dev/null
  sudo ln -sfn "$SITE" "/etc/nginx/sites-enabled/callflow-$CALLFLOW_ENV"
  sudo nginx -t
  sudo systemctl reload nginx
elif [ ! -f "$SITE" ]; then
  log "SKIPPED nginx: no passwordless sudo. Render the templates in scripts/ by hand."
else
  # The site file already exists, so the server blocks are left alone - but the
  # snippet is ours and safe to keep current, which is where the ports live.
  API_PORT=$(node -p "require('$PWD/ecosystem.config.js').ports.api")
  WEB_PORT=$(node -p "require('$PWD/ecosystem.config.js').ports.web")
  if have_sudo; then
    sudo mkdir -p /etc/nginx/snippets
    sed -e "s|@API_PORT@|$API_PORT|g" -e "s|@WEB_PORT@|$WEB_PORT|g" \
      -e "s|@VOICE_ALLOW@|$VOICE_ALLOW|g" \
      scripts/nginx.locations.template \
      | sudo tee "/etc/nginx/snippets/callflow-$CALLFLOW_ENV.conf.next" > /dev/null
    if ! sudo cmp -s "/etc/nginx/snippets/callflow-$CALLFLOW_ENV.conf.next" \
                     "/etc/nginx/snippets/callflow-$CALLFLOW_ENV.conf"; then
      sudo mv "/etc/nginx/snippets/callflow-$CALLFLOW_ENV.conf.next" \
              "/etc/nginx/snippets/callflow-$CALLFLOW_ENV.conf"
      sudo nginx -t && sudo systemctl reload nginx
      log "nginx proxy snippet updated"
    else
      sudo rm -f "/etc/nginx/snippets/callflow-$CALLFLOW_ENV.conf.next"
    fi
  fi
fi

# Let's Encrypt remains the path for a host that is NOT behind Cloudflare. Skipped
# entirely once an Origin certificate is installed - ACME cannot validate through
# a proxied record with HTTP-01 anyway.
if [ ! -f "$CERT" ] && [ -n "${CERTBOT_EMAIL:-}" ] \
   && [ ! -d "/etc/letsencrypt/live/$PUBLIC_HOST" ] && have_sudo; then
  log "requesting a Let's Encrypt certificate for $PUBLIC_HOST"
  sudo certbot --nginx -d "$PUBLIC_HOST" -n --agree-tos -m "$CERTBOT_EMAIL" --redirect \
    || log "certbot failed - is DNS for $PUBLIC_HOST pointed here, unproxied? HTTP still serves."
fi

# --------------------------------------------------------- pm2 across reboots
# `pm2 save` (in the deploy job) records the process list; this records the
# systemd unit that replays it. Without it a reboot comes back to nothing.
if have_sudo && ! systemctl list-unit-files 2>/dev/null | grep -q '^pm2-'; then
  log "installing the pm2 systemd unit"
  sudo env PATH="$PATH" pm2 startup systemd -u "$USER" --hp "$HOME" \
    || log "pm2 startup skipped - processes will not survive a reboot."
fi

log "provisioned: $CALLFLOW_ENV at $PUBLIC_HOST"
