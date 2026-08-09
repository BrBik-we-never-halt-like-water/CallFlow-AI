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
Supabase project, and its own pair of pm2 processes. Dev and production can share a
VM because the process names and ports differ; nothing in the code knows which one it
is beyond `CALLFLOW_ENV`.

| | production | dev |
| --- | --- | --- |
| Branch | `main` | `dev` |
| Directory | `/var/www/callflow-ai` | `/var/www/callflow-ai-dev` |
| Hostname | `callflow.com` | `dev.callflow.com` |
| pm2 processes | `callflow-api`, `callflow-web` | `callflow-api-dev`, `callflow-web-dev` |
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

Do **not** run `alembic upgrade head` by hand. The `migrate` job runs it on every push,
so the first deploy applies the whole history to the empty project.

---

## 3. Configure the GitHub Environment

**Settings → Environments**, one per branch, named `main` and `dev`. This is the only
place environment configuration lives.

| Name | Kind | Example | Notes |
| --- | --- | --- | --- |
| `APP_DIR` | var | `/var/www/callflow-ai-dev` | Created if absent |
| `PUBLIC_URL` | var | `https://dev.callflow.com` | Full origin, with scheme |
| `VM_HOST` | var | `203.0.113.10` | Inherited from repo-level if the same box |
| `VM_USER` | var | `deploy` | " |
| `ORIGIN_CERT_B64` | secret | `base64 -w0 origin.pem` | Cloudflare Origin certificate |
| `ORIGIN_KEY_B64` | secret | `base64 -w0 origin.key` | Its private key |
| `CERTBOT_EMAIL` | var | `ops@brbik.com` | Only for a host **not** behind Cloudflare |
| `REPO_URL` | var | `git@github.com:…/CallFlow-AI.git` | Optional, defaults to this repo |
| `VM_SSH_KEY` | secret | private key | Inherited from repo-level if the same box |
| `ENV_FILE_B64` | secret | `base64 -w0 .env` | The API's `.env`, base64'd |
| `WEB_ENV_FILE_B64` | secret | `base64 -w0 apps/web/.env.local` | The web app's, base64'd |

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

`callflow.com` is on Cloudflare, which changes how TLS works and rules certbot out:
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
| A | `callflow.com` | `140.245.235.251` | Proxied |
| A | `dev` | `140.245.235.251` | Proxied |

### 2. Issue the certificate

**SSL/TLS → Origin Server → Create Certificate.** Take the defaults (RSA, 15 years) and
set the hostnames to cover both environments with one certificate:

```
callflow.com
*.callflow.com
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
makes keys on whether `/etc/ssl/cloudflare/callflow.pem` and `.key` exist, not on
where they came from.

**Route A - place them on the VM directly**, the same way `brbik.pem` already is:

```bash
sudo mkdir -p /etc/ssl/cloudflare
sudo tee /etc/ssl/cloudflare/callflow.pem > /dev/null   # paste, then Ctrl-D
sudo tee /etc/ssl/cloudflare/callflow.key > /dev/null
sudo chmod 644 /etc/ssl/cloudflare/callflow.pem
sudo chmod 600 /etc/ssl/cloudflare/callflow.key
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

The same pair serves both environments, since `*.callflow.com` covers `dev`. With Route B,
set them once at repo level rather than per environment.

`bootstrap.sh` installs them to `/etc/ssl/cloudflare/callflow.pem` and `.key` on every run
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

`.github/workflows/ci-cd.yml`, on PR and push to `main` or `dev`. `api` and `web` lint,
type-check and test. On a push, three more jobs run in order - one per thing that can
independently go wrong:

**`provision`** → `scripts/bootstrap.sh`. Clones if absent, pins the checkout to the
branch being deployed, creates `.venv`, installs the API, writes `.env` and
`apps/web/.env.local` from their secrets, renders the nginx site, requests a
certificate, installs the pm2
systemd unit. Idempotent: every step checks the desired state first, so it is a no-op
on the deploys where nothing changed.

**`migrate`** → `alembic current`, `upgrade head`, `current` again, run from `apps/api`.
`alembic.ini` sets `script_location` and `prepend_sys_path` to `.` and alembic resolves
both against the working directory, so running it from the repo root with `-c` finds no
migrations and silently upgrades nothing.

**`deploy`** → `pm2 startOrRestart` the API, `npm ci && npm run build` the web app with
`NEXT_PUBLIC_API_URL` set to `PUBLIC_URL`, restart it, `pm2 save`, then health-check
`/api/health` and `/`.

The frontend is built on the VM rather than in CI because `NEXT_PUBLIC_API_URL` is baked
in at build time and differs per environment.

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
curl -fsS https://dev.callflow.com/api/health
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
