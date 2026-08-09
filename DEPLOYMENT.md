# Deployment

Bringing up an environment. Written for the dev environment, but production is the
same document with different values - the two differ only in the table in §1.

Everything after the one-time steps is automatic: pushing to `dev` deploys dev,
pushing to `main` deploys production. Nothing below needs repeating per deploy.

---

## 0. What an environment is

Each environment is **one directory on a VM** holding a checkout of one branch, with
its own `.env`, its own Supabase project, and its own pair of pm2 processes. Dev and
production can share a VM because the process names and ports differ; nothing in the
code knows which one it is beyond `CALLFLOW_ENV`.

| | production | dev |
| --- | --- | --- |
| Branch | `main` | `dev` |
| Directory | `/var/www/callflow-ai` | `/var/www/callflow-ai-dev` |
| Hostname | `callflow-ai.brbik.com` | `dev.callflow-ai.brbik.com` |
| pm2 processes | `callflow-api`, `callflow-web` | `callflow-api-dev`, `callflow-web-dev` |
| Ports | 8000 (api), 3000 (web) | 8001 (api), 3001 (web) |
| Supabase project | the production project | **a separate project** |

The directory, hostname and ports are the only values you choose. The process names
and ports come from `ecosystem.config.js`, which reads `CALLFLOW_ENV`.

---

## 1. Database

**Use a separate Supabase project for dev.** Sharing one with production means a
migration tested on dev has already run against production data by the time you notice
it was wrong, and RLS gives you no protection against that - migrations run as the
owner role, which bypasses it.

Follow [`SUPABASE_SETUP.md`](SUPABASE_SETUP.md) start to finish against the new
project. Two things in it are per-environment and easy to carry over by accident:

- **§2, Site URL and redirect URLs** must point at the dev hostname, or the
  password-reset and invitation links in email will send dev users to production.
- **§4, `PHONE_HASH_PEPPER`** must be generated fresh. It is the pepper for the
  suppression list's phone hash; reusing production's makes dev's suppression rows
  collide with real ones.

Do **not** run `alembic upgrade head` by hand. The deploy job runs it on every push,
so the first deploy applies the whole migration history to the empty project.

---

## 2. Server

Once per environment, on the VM:

```bash
sudo mkdir -p /var/www/callflow-ai-dev
sudo chown "$USER" /var/www/callflow-ai-dev
git clone git@github.com:BrBik-we-never-halt-like-water/CallFlow-AI.git /var/www/callflow-ai-dev
cd /var/www/callflow-ai-dev
git checkout dev

python3 -m venv .venv
.venv/bin/pip install -e ./apps/api
```

Write `/var/www/callflow-ai-dev/.env` from [`.env.example`](.env.example), with the dev
project's Supabase values, the dev `SITE_URL`, and the fresh `PHONE_HASH_PEPPER`. This
file is what `apps/api/app/core/config.py` loads - it resolves the repo root from its
own path, so it finds this file whatever directory the process starts in.

> Leave `CALLE_API_KEY` empty until dev should place real calls. Every run dials for
> real; there is no dry run. Runs are refused with a clear error while it is unset.

Then nginx, proxying the hostname to the two dev ports:

```nginx
server {
    server_name dev.callflow-ai.brbik.com;

    location /api/ { proxy_pass http://127.0.0.1:8001; }
    location /     { proxy_pass http://127.0.0.1:3001; }

    proxy_set_header Host              $host;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

`sudo certbot --nginx -d dev.callflow-ai.brbik.com` for TLS, then reload nginx.

You do not start pm2 by hand. The first deploy runs `pm2 startOrRestart` against
[`ecosystem.config.js`](ecosystem.config.js), which creates both processes and then
`pm2 save`s them. If pm2 itself has never run on this VM, run `pm2 startup` once and
follow the command it prints, or nothing comes back after a reboot.

---

## 3. CI/CD

[`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) lints, type-checks and
tests both apps on every PR and push to `main` or `dev`, then deploys on push.

One `deploy` job serves both branches. It reads `environment: ${{ github.ref_name }}`,
so GitHub resolves the target from the branch name and the job has no environment
literals in it at all.

In **Settings → Environments**, create one environment per branch:

| Environment | Variables | Secrets |
| --- | --- | --- |
| `main` | `APP_DIR`, `PUBLIC_URL`, `VM_HOST`, `VM_USER` | `VM_SSH_KEY` |
| `dev` | `APP_DIR`, `PUBLIC_URL`, `VM_HOST`, `VM_USER` | `VM_SSH_KEY` |

`PUBLIC_URL` is the full origin with scheme (`https://dev.callflow-ai.brbik.com`) - it
is baked into the frontend build as `NEXT_PUBLIC_API_URL` and used for the post-deploy
health check. Repo-level variables and secrets are inherited, so if dev shares the VM
with production you only need to set `APP_DIR` and `PUBLIC_URL` on the dev environment.

The job fails before connecting if `APP_DIR` or `PUBLIC_URL` is unset, rather than
deploying the dev branch into whatever directory the other environment uses.

### What a deploy does

1. Fetch and hard-set the checkout to the branch being deployed
2. Refuse to continue unless `apps/api` and `apps/web` both exist
3. `pip install -e ./apps/api`
4. `alembic upgrade head`, run **from `apps/api`** - `alembic.ini` resolves
   `script_location` and `prepend_sys_path` against the working directory, so running
   it from the repo root with `-c` finds no migrations
5. Start or restart the API process
6. `npm ci` and `npm run build` in `apps/web`, then start or restart the web process
7. `pm2 save`
8. `curl` `/api/health` and `/` against `PUBLIC_URL`

The frontend is built **on the VM**, not in CI, because `NEXT_PUBLIC_API_URL` is baked
in at build time and differs per environment.

---

## 4. Verifying

```bash
pm2 list                                    # both -dev processes online
curl -fsS https://dev.callflow-ai.brbik.com/api/health
cd /var/www/callflow-ai-dev/apps/api && ../../.venv/bin/alembic current
```

`alembic current` should print the newest revision in `apps/api/alembic/versions`.
If it prints nothing, the migrations never ran against this project - check
`DATABASE_URL` in `.env`.
