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
#   CALLFLOW_ENV    production | dev  - picks the process names and ports
#   PUBLIC_URL      https://dev.callflow-ai.brbik.com
#   ENV_FILE_B64    base64 of the .env this environment should run with
#
# Optional:
#
#   CERTBOT_EMAIL   set to have TLS issued automatically on first bring-up
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

if [ ! -f "$SITE" ] && have_sudo; then
  # Ports come from ecosystem.config.js so the proxy cannot point somewhere pm2
  # is not listening. Read here rather than at the top of the script: node is on
  # PATH for this user in practice, but only the nginx step actually needs it,
  # and `set -e` would otherwise abort a deploy that had no nginx work to do.
  API_PORT=$(node -p "require('$PWD/ecosystem.config.js').ports.api")
  WEB_PORT=$(node -p "require('$PWD/ecosystem.config.js').ports.web")

  log "writing the nginx site for $PUBLIC_HOST (web $WEB_PORT, api $API_PORT)"
  sed -e "s|@HOST@|$PUBLIC_HOST|g" \
      -e "s|@API_PORT@|$API_PORT|g" \
      -e "s|@WEB_PORT@|$WEB_PORT|g" \
      scripts/nginx.conf.template | sudo tee "$SITE" > /dev/null
  sudo ln -sfn "$SITE" "/etc/nginx/sites-enabled/callflow-$CALLFLOW_ENV"
  sudo nginx -t
  sudo systemctl reload nginx
elif [ ! -f "$SITE" ]; then
  log "SKIPPED nginx: no passwordless sudo. Render scripts/nginx.conf.template by hand."
fi

# TLS on first bring-up only. certbot is idempotent, but pointing it at a host
# whose DNS has not propagated yet burns a Let's Encrypt rate limit, and a
# failure here should not fail a deploy that is otherwise fine.
if [ -n "${CERTBOT_EMAIL:-}" ] && [ ! -d "/etc/letsencrypt/live/$PUBLIC_HOST" ] && have_sudo; then
  log "requesting a certificate for $PUBLIC_HOST"
  sudo certbot --nginx -d "$PUBLIC_HOST" -n --agree-tos -m "$CERTBOT_EMAIL" --redirect \
    || log "certbot failed - is DNS for $PUBLIC_HOST pointed here yet? HTTP still serves."
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
