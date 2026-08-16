#!/usr/bin/env bash
#
# Bring the voice-runtime VM to the state the pipeline expects.
#
# The sibling of scripts/bootstrap.sh, for the *other* box. The two deliberately
# share no code: this host runs one long-running outbound worker and nothing
# else - no nginx, no certificate, no port, no database - so almost every step
# in bootstrap.sh is inapplicable here rather than merely unused. `write_env` is
# the one genuinely duplicated function; keep the two copies in step.
#
# Idempotent by construction, same as its sibling: every step checks the desired
# state before acting, so this runs on every deploy and is a no-op when nothing
# changed.
#
# Run from the deploy directory, by .github/workflows/ci-cd.yml, which has
# already cloned or updated the checkout. Required in the environment:
#
#   CALLFLOW_ENV        production | dev  - picks the pm2 process name
#   VOICE_ENV_FILE_B64  base64 of the worker's own .env - see the key list below
#
# Optional:
#
#   VOICE_EXTRAS        pip extras to install, comma-separated. Defaults to every
#                       provider app/pipeline.py's registry knows about.
#
set -euo pipefail

: "${CALLFLOW_ENV:?CALLFLOW_ENV is required}"

# Every provider wired into app/pipeline.py's registry. Each is an optional
# extra because livekit-agents pulls a large tree per plugin, so a deployment
# that only uses Sarvam has no reason to carry Deepgram - but the default here
# is "all of them", since which providers an organisation picks is a runtime
# choice and a MissingPlugin at 3am is worse than a slower deploy.
VOICE_EXTRAS=${VOICE_EXTRAS:-sarvam,deepgram,elevenlabs,openai}

log() { printf '\n==> %s\n' "$*"; }

have_sudo() { sudo -n true 2>/dev/null; }

# ------------------------------------------------------------------ toolchain
# Checked rather than assumed, and named individually: a fresh VM is the normal
# case for this script, and "ModuleNotFoundError" three steps later is a worse
# way to learn the interpreter is too old.
if ! command -v python3 > /dev/null; then
  echo "FATAL: python3 is not installed on this host." >&2
  exit 1
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "FATAL: livekit-agents needs Python 3.11+, found $(python3 -V 2>&1)." >&2
  echo "       Install a newer interpreter and point python3 at it." >&2
  exit 1
fi

if ! python3 -c 'import venv' 2> /dev/null; then
  echo "FATAL: the python3 venv module is missing (Debian/Ubuntu: apt install python3-venv)." >&2
  exit 1
fi

# pm2 starts the worker and ecosystem.config.js is JavaScript, so both are hard
# requirements even though nothing here serves HTTP.
for tool in node pm2; do
  if ! command -v "$tool" > /dev/null; then
    echo "FATAL: $tool is not installed. The worker is started by pm2 from" >&2
    echo "       ecosystem.config.js, which is a node module." >&2
    exit 1
  fi
done

# ---------------------------------------------------------------- python env
if [ ! -x .venv/bin/python ]; then
  log "creating .venv"
  python3 -m venv .venv
fi

log "installing the voice runtime with extras: $VOICE_EXTRAS"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e "./apps/voice-runtime[$VOICE_EXTRAS]"

# --------------------------------------------------------------- env file
# The twin of bootstrap.sh's function of the same name - see the header.
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
  if cmp -s "$path.next" "$path" 2> /dev/null; then
    rm -f "$path.next"
  else
    mv "$path.next" "$path"
    log "$path updated from the GitHub Environment"
  fi
}

# The repo root, because app/config.py resolves `.env` from its own location
# (parents[3]) rather than the working directory - pm2 and pytest start from
# different places and a CWD-relative lookup finds nothing in one of them.
write_env .env "${VOICE_ENV_FILE_B64:-}" VOICE_ENV_FILE_B64

# This host has no database, no Supabase service key and no provider-credential
# key, and must never be handed them - that separation is most of the reason the
# worker runs on its own box. Pasting the API's env here would undo it silently,
# so it is refused loudly instead.
for forbidden_var in DATABASE_URL DIRECT_URL PROVIDER_CREDENTIALS_KEY SUPABASE_SERVICE_ROLE_KEY; do
  if grep -qE "^${forbidden_var}=.+" .env; then
    echo "FATAL: .env on the voice host contains $forbidden_var." >&2
    echo "       This looks like the API's env file. The worker needs only its" >&2
    echo "       own five keys and must not hold database or provider secrets." >&2
    exit 1
  fi
done

# Duplicates app/config.py's own `missing()` check on purpose: caught here the
# deploy fails with a list of names, caught there it is a pm2 crash-loop whose
# reason is buried in a log nobody is watching.
for required_var in LIVEKIT_URL LIVEKIT_API_KEY LIVEKIT_API_SECRET \
  CALLFLOW_PUBLIC_API_URL CALLFLOW_INTERNAL_API_SECRET; do
  if ! grep -qE "^${required_var}=.+" .env; then
    echo "FATAL: $required_var is missing or empty in .env on the voice host." >&2
    echo "       The worker refuses to start without it (app/config.py)." >&2
    exit 1
  fi
done

# The worker reaches the API across the public internet now, not over loopback,
# so a localhost value is a deployment that can never report a transcript.
if grep -qE "^CALLFLOW_PUBLIC_API_URL=https?://(127\.0\.0\.1|localhost)" .env; then
  echo "FATAL: CALLFLOW_PUBLIC_API_URL points at localhost on the voice host." >&2
  echo "       It must be the API's public URL - this VM is not the API VM." >&2
  exit 1
fi

# --------------------------------------------------------- pm2 across reboots
if have_sudo && ! systemctl list-unit-files 2> /dev/null | grep -q '^pm2-'; then
  log "installing the pm2 systemd unit"
  sudo env PATH="$PATH" pm2 startup systemd -u "$USER" --hp "$HOME" \
    || log "pm2 startup skipped - the worker will not survive a reboot."
fi

log "provisioned: voice runtime for $CALLFLOW_ENV"
