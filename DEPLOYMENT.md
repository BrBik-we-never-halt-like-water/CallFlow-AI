# Deployment

Bringing up an environment. Written for dev, but production is the same document
with different values - the two differ only in the table in §1.

**The pipeline provisions the machine.** There is no runbook of commands to type on
a VM: the directory, the venv, the `.env`, the nginx site, the TLS certificate and
the pm2 processes are all created by the deploy if they are missing. Configure the
GitHub Environment, push, and the environment builds itself. §4 lists the two things
that genuinely cannot be automated.

---

## 1. What an environment is

One directory on a VM holding a checkout of one branch, with its own `.env`, its own
Supabase project, and its own pm2 processes. Dev and production can share a VM because
the process names and ports differ; nothing in the code knows which one it is beyond
`CALLFLOW_ENV`.

**An environment spans two machines.** The API and the web app share one; the voice
runtime has its own, with its own checkout, `.env` and pm2 daemon — see §3b. The table
below is the API/web VM unless a row says otherwise.

| | production | dev |
| --- | --- | --- |
| Branch | `main` | `dev` |
| Directory | `/var/www/callflow-ai` | `/var/www/callflow-ai-dev` |
| Hostname | `calllflow.com` | `dev.calllflow.com` |
| pm2 processes (API VM) | `callflow-api`, `callflow-web` | `callflow-api-dev`, `callflow-web-dev` |
| pm2 processes (voice VM) | `callflow-voice` | `callflow-voice-dev` |
| Ports | 8000 (api), **3001** (web) | 8001 (api), 3003 (web) |
| Supabase project | the production project | **a separate project** |

The VM hosts other sites, so these are the numbers that were free rather than a tidy
sequence. What nginx currently fronts:

| Port | Serves |
| --- | --- |
| 3000 | `brbik.com` |
| 3001 | `callflow-ai.brbik.com` web - **this app in production** |
| 3002 | `dns.brbik.com` (dnsentinel) |
| 3003 | dev web |
| 8000 | production API |
| 8001 | dev API |

Production is on 3001 because that is what its nginx site has always proxied to; moving
it would be a 502 with nothing in any log explaining why. Confirm with `ss -ltnp` before
claiming another - that table only covers what nginx fronts, not everything listening.

Process names and ports come from `ecosystem.config.js`, keyed on `CALLFLOW_ENV`.
`scripts/bootstrap.sh` reads the ports from that same file when it renders nginx, so
the proxy cannot end up pointing somewhere pm2 is not listening.

---

## 2. The database

**Use a separate Supabase project for dev.** Migrations run as the owner role, which
bypasses RLS - so sharing one project with production means a migration tested on dev
has already run against production data by the time you notice it was wrong.

Follow [`SUPABASE_SETUP.md`](SUPABASE_SETUP.md) against the new project. Two values in
it are per-environment and easy to copy across by accident:

- **§2, Site URL and redirect URLs** must point at the dev hostname, or password-reset
  and invitation links will send dev users into production.
- **§4, `PHONE_HASH_PEPPER`** must be generated fresh. It is the pepper for the
  suppression list's phone hash; reusing production's makes dev's suppression rows
  collide with real ones.

Do **not** run `alembic upgrade head` by hand. The `migrate` job runs it on every push
that touches `apps/api` (or anything shared - see §5), so the first deploy applies the
whole history to the empty project: a first push has no base commit to compare against,
which the change filter treats as "everything changed".

### Capping dev

Supabase is not where dev can cost you money - the Free plan has no overage billing, so
usage stops rather than charges. (If the org moves to Pro, keep **Organization → Billing
→ Spend Cap** on.) The real exposure is outbound calls, which are billed per minute and
reach real strangers.

Four env values cap that, and the defaults are not the safe ones:

| Value | Dev setting | What it does |
| --- | --- | --- |
| `LIVEKIT_SIP_HOST` | **empty** | No connected number, no calls. Every contact is refused with a clear reason |
| `CALLFLOW_ALLOWLIST` | **your own number** | The one that matters - see below |
| `CALLFLOW_MAX_CALLS_PER_RUN` | `2` | Hard stop per run regardless of list length |
| `CALLFLOW_DAILY_BUDGET` | `5` | Shared daily ceiling |

**`CALLFLOW_ALLOWLIST` empty means no restriction, not total restriction.**
`check_dial_allowed` reads `if effective_allowlist and phone not in effective_allowlist`,
so an empty list skips the check entirely and any valid E.164 number is dialable. A
non-empty list is what puts the deployment in development mode. Set it to your own number
in E.164 (`+919876543210`) on dev and leave it that way.

Note the free Supabase plan pauses a project after 7 days idle. A paused project means
`DATABASE_URL` stops answering and dev returns errors until someone un-pauses it in the
dashboard - expected on dev, and the reason production should not be on Free.

---

## 3. Configure the GitHub Environment

**Settings → Environments**, one per branch, named `main` and `dev`. This is the only
place environment configuration lives.

| Name | Kind | Example | Notes |
| --- | --- | --- | --- |
| `APP_DIR` | var | `/var/www/callflow-ai-dev` | Created if absent |
| `PUBLIC_URL` | var | `https://dev.calllflow.com` | Full origin, with scheme |
| `VM_HOST` | var | `203.0.113.10` | Inherited from repo-level if the same box |
| `VM_USER` | var | `deploy` | " |
| `ORIGIN_CERT_B64` | secret | `base64 -w0 origin.pem` | Cloudflare Origin certificate |
| `ORIGIN_KEY_B64` | secret | `base64 -w0 origin.key` | Its private key |
| `CERTBOT_EMAIL` | var | `ops@brbik.com` | Only for a host **not** behind Cloudflare |
| `REPO_URL` | var | `git@github.com:…/CallFlow-AI.git` | Optional, defaults to this repo |
| `VM_SSH_KEY` | secret | private key | Inherited from repo-level if the same box |
| `ENV_FILE_B64` | secret | `base64 -w0 .env` | The API's `.env`, base64'd |
| `WEB_ENV_FILE_B64` | secret | `base64 -w0 apps/web/.env.local` | The web app's, base64'd |
| `VOICE_VM_HOST` | var | `203.0.113.20` | The voice runtime's own VM (§3b). Repo-level, like `VM_HOST` |
| `VOICE_APP_DIR` | var | `/var/www/callflow-voice-dev` | Deploy directory on that VM. Per environment |
| `VOICE_ENV_FILE_B64` | secret | `base64 -w0 voice.env` | The worker's `.env`, base64'd. Per environment |
| `VOICE_EXTRAS` | var | `sarvam,openai` | Optional; defaults to every provider |

The two `_B64` secrets are what remove the last manual step. Write both files locally
from their `.env.example`s, then:

```bash
base64 -w0 .env                    # macOS: base64 -i .env
base64 -w0 apps/web/.env.local
```

Paste each single line in as its secret. Every deploy rewrites the VM's copy, so the
files on the machine are copies of something GitHub holds rather than something someone
edited in place and cannot reproduce. Change a value by updating the secret and re-running
the job - never by editing the file on the VM, which the next deploy overwrites.

**They are two files because they are two different sets of names**, not a subset of one
another. `apps/web/.env.local` is the one that bites: three of its four variables are
inlined into the JavaScript bundle at **build** time, so a missing one is not a runtime
error anyone would see in a log. The site builds clean, `isSupabaseConfigured()` returns
false, the middleware waves every request through, and the dashboard ships with
authentication disabled. `bootstrap.sh` therefore refuses to continue if
`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` or `NEXT_PUBLIC_SITE_URL` is
missing or empty.

Repo-level vars and secrets are inherited, so if dev shares production's VM you only
need `APP_DIR`, `PUBLIC_URL`, `ENV_FILE_B64` and `WEB_ENV_FILE_B64` on the dev environment.

The pipeline fails before connecting if `APP_DIR` or `PUBLIC_URL` is unset, naming the
one that is missing, rather than deploying this branch into the other environment's
directory.

---

## 3a. Cloudflare: DNS and the Origin certificate

`calllflow.com` is on Cloudflare, which changes how TLS works and rules certbot out:
ACME's HTTP-01 challenge cannot validate through a proxied record, so certbot fails on
every run. Use a **Cloudflare Origin CA certificate** instead - a static 15-year pair
with nothing to renew, no challenge to keep reachable, and no rate limit to trip.

The trade is that an Origin certificate is **not publicly trusted**. No browser accepts
it directly; it is only ever presented to Cloudflare. Two things must therefore be true
or the site is broken:

1. the DNS record is **proxied** (orange cloud), so Cloudflare is the only client that
   ever completes the handshake
2. SSL/TLS mode is **Full (strict)**, so Cloudflare actually verifies it

### 1. DNS records

**DNS → Records.** Both proxied:

| Type | Name | Content | Proxy |
| --- | --- | --- | --- |
| A | `calllflow.com` | `140.245.235.251` | Proxied |
| A | `dev` | `140.245.235.251` | Proxied |

### 2. Issue the certificate

**SSL/TLS → Origin Server → Create Certificate.** Take the defaults (RSA, 15 years) and
set the hostnames to cover both environments with one certificate:

```
calllflow.com
*.calllflow.com
```

Cloudflare shows the certificate and the key **once**. Copy both before closing the
dialog - the key is not recoverable afterwards, and re-issuing means replacing it
everywhere.

### 3. Set the mode

**SSL/TLS → Overview → Full (strict).** Anything less makes the origin leg either
unencrypted (Flexible) or unverified (Full), which is most of the point of doing this.

Turn on **Always Use HTTPS**, and set HSTS here rather than on the origin - Cloudflare
terminates the connection the browser actually sees.

### 4. Get them onto the VM

Either route works, and `bootstrap.sh` treats them identically - every decision it
makes keys on whether `/etc/ssl/cloudflare/calllflow.pem` and `.key` exist, not on
where they came from.

**Route A - place them on the VM directly**, the same way `brbik.pem` already is:

```bash
sudo mkdir -p /etc/ssl/cloudflare
sudo tee /etc/ssl/cloudflare/calllflow.pem > /dev/null   # paste, then Ctrl-D
sudo tee /etc/ssl/cloudflare/calllflow.key > /dev/null
sudo chmod 644 /etc/ssl/cloudflare/calllflow.pem
sudo chmod 600 /etc/ssl/cloudflare/calllflow.key
sudo chown root:root /etc/ssl/cloudflare/callflow.*
```

Simplest, and the private key exists in exactly one place instead of two. The cost is
that it is state no one can reproduce from the repository - if the machine is lost, so
is the arrangement. For a 15-year certificate that is a fair trade; for anything that
rotates it would not be.

**Route B - hand them to the pipeline**, so a rebuilt VM re-provisions itself:

```bash
base64 -w0 origin.pem | gh secret set ORIGIN_CERT_B64
base64 -w0 origin.key | gh secret set ORIGIN_KEY_B64
```

Chain with `&&` and never on separate lines: `gh secret set` reads stdin, and
`base64 missing-file | gh secret set X` still sets `X` to an empty string after
printing its error - a secret that reads as configured in the UI and is empty on the
machine.

Route B can be added later without changing anything: with the secrets set, the
install block simply starts overwriting the files each run.

The same pair serves both environments, since `*.calllflow.com` covers `dev`. With Route B,
set them once at repo level rather than per environment.

`bootstrap.sh` installs them to `/etc/ssl/cloudflare/calllflow.pem` and `.key` on every run
- matching the convention already used on this box for the brbik zone - so
rotating the secret rotates the certificate. It verifies the certificate's modulus
against the key first and leaves the existing pair alone if they do not match - finding
that out from nginx refusing to start, after the working pair has already been
overwritten, is not a good way to learn it.

### Order matters

Point DNS **before** the first push. The health check curls `PUBLIC_URL`, which is
`https://…`, so a first deploy that otherwise worked perfectly reports red if the name
does not resolve yet. If you get the order wrong: fix DNS, then re-run the failed jobs.
`provision` is idempotent.

---

## 3b. The voice runtime's VM

The LiveKit worker runs on a **separate machine** from the API and the web app. It gets
its own bootstrap script (`scripts/bootstrap-voice.sh`), its own pair of pipeline jobs
(`provision-voice` → `deploy-voice`), and its own `.env`. It shares only the SSH
credentials — `VM_USER` and `VM_SSH_KEY` are reused, so the same deploy key must be
authorised on both boxes.

**Why separate, beyond capacity:** this host holds no `DATABASE_URL`, no
`PROVIDER_CREDENTIALS_KEY` and no Supabase service key, and never should. Every per-call
STT/TTS/LLM credential arrives in the job metadata that `apps/api` resolves and sends;
the worker stores none of it. `bootstrap-voice.sh` **refuses to start** if the `.env` it
is handed contains any of those API-only keys, because pasting the wrong secret in is
the one mistake that would quietly undo the separation.

**What the box needs before the first deploy:** Python 3.11+ (livekit-agents' floor),
`python3-venv`, `node`, and `pm2`. The bootstrap checks each and fails naming the missing
one rather than dying later with a `ModuleNotFoundError`. Passwordless sudo is optional
and used only to install the pm2 systemd unit, without which the worker will not come
back after a reboot.

**The worker's `.env`** is five required keys. Two of them must match the API VM's
byte for byte, and both fail *silently* when they don't:

```
LIVEKIT_URL=wss://<project>.livekit.cloud
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
CALLFLOW_PUBLIC_API_URL=https://dev.calllflow.com
CALLFLOW_INTERNAL_API_SECRET=          # identical to the API's, or every callback 404s
LIVEKIT_AGENT_NAME=callflow-voice      # identical to the API's, or dispatches go unanswered
```

`CALLFLOW_PUBLIC_API_URL` must be the API's **public** URL. On a single VM you could
point it at `127.0.0.1`; from another machine that is a worker which can never report a
transcript, so the bootstrap rejects a localhost value outright.

**How the callback reaches the API.** The worker POSTs to `/internal/v1/runs/{id}/complete`.
nginx on the API VM proxies `/api/` and `/`, so without a rule of its own that path is
answered by Next.js with a 404. `scripts/nginx.locations.template` therefore carries a
`location /internal/` block that is **closed to everything except `VOICE_VM_HOST`** — the
shared secret the endpoint checks is the second lock, not the only one. Leave
`VOICE_VM_HOST` unset and that location denies everyone, which is a 403 in the API's own
nginx log rather than a confusing 404.

**Health check.** The worker serves nothing, so there is no URL to curl. `deploy-voice`
asks pm2 instead, and checks the process has stayed up ~10s — "online" alone is satisfied
by a worker that is crash-looping at the moment pm2 samples it. On failure it prints the
last 50 log lines.

---

## 4. The one thing that is not automated

**A Supabase project.** Creating one, and the dashboard settings in `SUPABASE_SETUP.md`,
are human actions in someone else's UI.

Everything else - the directory, the checkout, the venv, `pip install`, both env files,
the nginx server block, the TLS certificate, the pm2 processes and their systemd unit -
is created by the pipeline on first run and left alone afterwards.

The repository is **public**, so the VM needs no key, deploy key or token to read it:
`provision` clones over HTTPS. If it ever goes private, set a `REPO_URL` variable to the
SSH form and give the machine a read-only deploy key. `provision` also runs
`git remote set-url origin` on every deploy, so a checkout cloned over SSH before this
was automated is repointed rather than failing on a machine with no key.

---

## 5. What the pipeline does

`.github/workflows/ci-cd.yml`, on PR and push to `main` or `dev`. The api and web halves
are checked and deployed **independently**, so most pushes only pay for the half they
touched:

```
changes ─┬─ api  ──┐                  ┌─ migrate ─ deploy-api
         │         ├─ provision ──────┤
         └─ web  ──┘                  └─ deploy-web
```

**`changes`** → decides whether `apps/api` and/or `apps/web` changed, from the compare
API rather than a checkout (it is on every run's critical path, so cloning the repo just
to run `git diff` would cost more than the jobs it skips). Anything **outside** those two
directories - the workflow itself, `ecosystem.config.js`, `scripts/`, the root
`package.json`, a root `.md` - counts as **both**, since any of them can change how
either half deploys.

It fails **open**, which is the opposite of how the product's own safety gates work and
is deliberate: a new branch with no `before` commit, a force-push whose base is gone, or
any API error reports both halves as changed and everything runs. A wrongly-skipped
deploy ships a half-updated VM; a wasted minute costs a minute.

**`api`** / **`web`** → lint, type-check, test. Each runs only if its half changed.

**`provision`** → `scripts/bootstrap.sh`. Clones if absent, pins the checkout to the
branch being deployed, creates `.venv`, installs the API, writes `.env` and
`apps/web/.env.local` from their secrets, renders the nginx site, requests a
certificate, installs the pm2
systemd unit. Idempotent: every step checks the desired state first, so it is a no-op
on the deploys where nothing changed.

**Shared, and first, on purpose.** Both halves deploy out of one checkout on one VM, and
`provision` is what puts the right commit there - two `git checkout -B` against the same
directory concurrently is a race. It is the one job that cannot be split.

**`migrate`** → `alembic current`, `upgrade head`, `current` again, run from `apps/api`.
Skipped entirely when only the frontend changed. `alembic.ini` sets `script_location` and
`prepend_sys_path` to `.` and alembic resolves both against the working directory, so
running it from the repo root with `-c` finds no migrations and silently upgrades nothing.

**`deploy-api`** → `pm2 startOrRestart` the API, `pm2 save`, health-check `/api/health`.

**`callflow-voice`** is the third process, added with the platform pivot. It is a
long-running worker, not a server: it holds a websocket out to LiveKit and waits to be
dispatched into rooms. So it claims **no port**, nginx does not front it, and there is
nothing to add to the port table or to check with `ss -ltnp` before deploying it.

It shares the repo-root `.venv` with the API, but its plugins are optional extras - a
deployment installs only the vendors its organisations actually use, because each
`livekit-plugins-*` package pulls a large dependency tree:

```bash
cd apps/voice-runtime
../../.venv/bin/pip install -e ".[sarvam,openai,silero]"   # plus deepgram/elevenlabs if used
```

Its health check is that it starts at all: `python -m app.worker start` refuses to run
with a clear list of missing variables rather than booting into a state where it answers
calls and cannot report them. `LIVEKIT_AGENT_NAME` must match on both processes - if the
API dispatches a name the worker has not registered, calls connect to silence and nothing
in either log says why.

**`deploy-web`** → `npm ci && npm run build` with `NEXT_PUBLIC_API_URL` set to
`PUBLIC_URL`, restart, `pm2 save`, health-check `/`.

**These two run in parallel** and `deploy-web` deliberately does **not** depend on
`migrate` - a Next build has no relationship to the database schema, and waiting behind
it was pure serial time. An API restart likewise no longer waits behind a frontend build
it has nothing to do with.

The frontend is built on the VM rather than in CI because `NEXT_PUBLIC_API_URL` is baked
in at build time and differs per environment. This is also why the web app is built
twice on a frontend change (once in `web`, once in `deploy-web`) - the CI build proves it
compiles, the VM build produces the artefact that actually serves. Collapsing the two
would mean shipping a CI-built bundle per environment, which is a bigger change than it
looks.

**Every job past `changes` carries a `!cancelled() && needs.X.result != 'failure'`
guard.** Without it a *skipped* dependency skips everything downstream - which is exactly
what a web-only push produces, where the `api` job never runs at all. `provision` treats
`skipped` as fine and `failure` as fatal; the deploy jobs additionally require
`provision.result == 'success'`, so a PR (where `provision` is skipped) deploys nothing.

`cancel-in-progress` applies to pull requests only. A push is never cancelled - killing
a run mid-`migrate` can leave the schema halfway between two revisions.

### The nginx site is written once

`scripts/nginx.conf.template` is rendered only if the site file does not already exist,
because certbot rewrites that file in place to add the TLS block. Re-rendering on every
deploy would strip HTTPS back out. To change it: delete the file, let the next deploy
write it, then re-run certbot.

---

## 6. Verifying

```bash
pm2 list                                    # both processes online
curl -fsS https://dev.calllflow.com/api/health
cd /var/www/callflow-ai-dev/apps/api && ../../.venv/bin/alembic current
```

`alembic current` should print the newest revision in `apps/api/alembic/versions`. If it
prints nothing, migrations never ran against this project - check `DATABASE_URL` in the
`.env`, which means checking `ENV_FILE_B64`.

---

## 7. Known gaps

- **No backup or rollback around the migration.** If `upgrade head` fails partway the
  job stops, but the schema is left halfway and pm2 is still serving the previous code.
  Migrate-then-restart is right for additive changes and wrong for destructive ones.
- **The RLS suite does not run in CI.** `test_rls_isolation.py` skips unless
  `DATABASE_URL` is set, and CI does not set it - so the 31 cross-tenant isolation tests
  guarding the most expensive bug this product can ship run on no pull request. Fixing it
  needs a Supabase-shaped database in CI (`auth` schema, `authenticated`/`anon` roles),
  not a plain Postgres container.
