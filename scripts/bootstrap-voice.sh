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
#   VOICE_ENV_FILE_B64  base64 seed for the worker's own .env - used only when
#                       the file does not exist yet; never rewrites an existing
#                       one. See the key list below
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
# `livekit-agents` needs 3.11+, and this box may not have it: the voice VM runs
# Ubuntu 20.04, whose system python is 3.8, while the API VM runs 24.04 with
# 3.12. Refusing was the old behaviour and it left the deploy dead on a machine
# nobody could fix without a shell - so this now *provisions* an interpreter
# rather than only complaining about the one it found.
#
# `uv` rather than the deadsnakes PPA: it is a single static binary with real
# arm64 builds (this host is aarch64, where deadsnakes coverage is patchy), it
# needs no apt source and no sudo, and the CPython it fetches is a standalone
# build that cannot be disturbed by a later `apt upgrade` of the system python.
PYTHON_MIN_MINOR=11
PYTHON_WANTED=3.12

is_new_enough() {
  "$1" -c "import sys; sys.exit(0 if sys.version_info >= (3, $PYTHON_MIN_MINOR) else 1)" 2>/dev/null
}

find_python() {
  local candidate
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" > /dev/null && is_new_enough "$candidate"; then
      command -v "$candidate"
      return 0
    fi
  done
  # A previous run's uv-managed build, before uv itself is on PATH.
  for candidate in "$HOME/.local/bin/uv" /usr/local/bin/uv; do
    if [ -x "$candidate" ]; then
      local managed
      managed=$("$candidate" python find "$PYTHON_WANTED" 2>/dev/null) || true
      if [ -n "$managed" ] && is_new_enough "$managed"; then
        printf '%s' "$managed"
        return 0
      fi
    fi
  done
  return 1
}

# Everything except the final path goes to stderr: the caller reads this
# function's stdout as the interpreter path, so a stray log line becomes the
# path and the venv step fails with a name nobody recognises.
install_python() {
  log "no Python ${PYTHON_WANTED}+ on this host - installing one with uv" >&2
  if ! command -v uv > /dev/null && [ ! -x "$HOME/.local/bin/uv" ]; then
    if ! curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1; then
      echo "FATAL: could not install uv. Is this host offline?" >&2
      exit 1
    fi
  fi

  local uv_bin="${HOME}/.local/bin/uv"
  command -v uv > /dev/null && uv_bin=$(command -v uv)

  if ! "$uv_bin" python install "$PYTHON_WANTED" >&2; then
    echo "FATAL: uv could not install Python $PYTHON_WANTED." >&2
    exit 1
  fi

  "$uv_bin" python find "$PYTHON_WANTED"
}

PYTHON=$(find_python || true)
if [ -z "${PYTHON:-}" ]; then
  PYTHON=$(install_python)
fi
[ -n "$PYTHON" ] || { echo "FATAL: no usable Python after provisioning." >&2; exit 1; }
log "using $($PYTHON -V 2>&1) at $PYTHON"

if ! "$PYTHON" -c 'import venv' 2> /dev/null; then
  echo "FATAL: $PYTHON has no venv module (Debian/Ubuntu: apt install python3-venv)." >&2
  exit 1
fi

# pm2 starts the worker and ecosystem.config.js is JavaScript, so both are hard
# requirements even though nothing here serves HTTP.
#
# Installed system-wide rather than under $HOME, deliberately. The deploy job
# reaches this box over a non-interactive ssh, which reads neither .bashrc nor
# .profile - so a node in ~/.local would be on PATH for a person and absent for
# the very job that needs to run `pm2 start`. /usr/bin is on the default PATH
# either way.
#
# Node 20 rather than the newest: this host is Ubuntu 20.04, and NodeSource's
# later lines want a glibc it does not have. pm2 asks nothing of the runtime.
NODE_MAJOR=20

if ! command -v node > /dev/null; then
  if ! have_sudo; then
    echo "FATAL: node is not installed and this user cannot sudo." >&2
    echo "       Install Node ${NODE_MAJOR} on this host, then re-run the deploy." >&2
    exit 1
  fi
  log "installing Node ${NODE_MAJOR} (NodeSource)"
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | sudo -E bash - > /dev/null 2>&1 \
    || { echo "FATAL: could not add the NodeSource repository." >&2; exit 1; }
  sudo apt-get install -y nodejs > /dev/null 2>&1 \
    || { echo "FATAL: apt could not install nodejs." >&2; exit 1; }
fi

if ! command -v pm2 > /dev/null; then
  if ! have_sudo; then
    echo "FATAL: pm2 is not installed and this user cannot sudo." >&2
    echo "       Run: npm install -g pm2" >&2
    exit 1
  fi
  log "installing pm2"
  sudo npm install -g pm2 > /dev/null 2>&1 \
    || { echo "FATAL: npm could not install pm2." >&2; exit 1; }
fi

log "node $(node -v), pm2 $(pm2 -v 2>/dev/null | tail -1)"

# ---------------------------------------------------------------- python env
# Rebuilt when the existing venv is too old - a box upgraded from 3.8 keeps a
# 3.8 .venv otherwise, and every install into it fails on the requires-python.
if [ -x .venv/bin/python ] && ! is_new_enough .venv/bin/python; then
  log "existing .venv is $(.venv/bin/python -V 2>&1) - replacing it"
  rm -rf .venv
fi

if [ ! -x .venv/bin/python ]; then
  log "creating .venv"
  "$PYTHON" -m venv .venv
fi

log "installing the voice runtime with extras: $VOICE_EXTRAS"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e "./apps/voice-runtime[$VOICE_EXTRAS]"

# --------------------------------------------------------------- env file
# The twin of bootstrap.sh's function of the same name - see the header there
# for the full policy. Seed-on-first-provision only: an existing .env on this
# VM is the source of truth and is never rewritten; the secret exists to boot
# a bare machine and as the disaster-recovery copy, refreshed by the operator
# after in-place edits (DEPLOYMENT.md §3).
write_env() {
  local path="$1" encoded="$2" secret_name="$3"

  if [ -f "$path" ]; then
    if [ -n "$encoded" ] && ! printf '%s' "$encoded" | base64 -d | cmp -s - "$path"; then
      log "NOTE: $path differs from $secret_name - the file on this VM wins."
      log "      Refresh the seed when convenient:  base64 -w0 $path -> $secret_name"
    fi
    return 0
  fi

  if [ -z "$encoded" ]; then
    echo "FATAL: $path is missing and $secret_name is not set for '$CALLFLOW_ENV'." >&2
    echo "       Set it with:  base64 -w0 $path" >&2
    exit 1
  fi

  umask 077
  printf '%s' "$encoded" | base64 -d > "$path"
  log "$path seeded from $secret_name (first provision only - never rewritten)"
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
