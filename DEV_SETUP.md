# Running CallFlow AI locally

One command. Everything in containers - Postgres, Supabase auth, storage,
Realtime, Studio, plus the API, the voice worker and the web app.

```bash
npm run local
```

First run pulls images and builds; give it a few minutes. After that:

| | |
| --- | --- |
| Web | http://localhost:3000 |
| API | http://localhost:8000/api/health |
| Studio (browse the database) | http://localhost:54323 |
| Supabase gateway | http://localhost:54321 |

Then **sign up at http://localhost:3000/signup**. Auth runs locally, so the
signup trigger creates your organisation and you land straight in it.

---

## Why containers, and why this replaced the old script

`npm run dev:db` used to start a native Postgres with a hand-written
`auth.users` shim. That could never work end to end, for a reason worth
understanding before you reach for a shortcut:

**Supabase Auth is a separate service from Supabase Postgres.** Signing up talks
to an auth *server* (GoTrue). With a local database but hosted auth, your account
is created in the hosted project and the local database never sees it - so the
`on_auth_user_created` trigger never fires, you have no `public.users` row, no
organisation, and the app tells you your account is not attached to one. Every
developer then needed their user mirrored into the local database by hand.

Running real GoTrue against the local Postgres closes that gap, and GoTrue needs
a container. That is the whole reason this exists.

The second reason is sharper. Pointing `DATABASE_URL` at the shared Supabase
project and running a feature branch's migrations has now corrupted **two**
databases - production in August (`ISSUES.md` #80) and dev again a week later,
which stranded it on a revision that exists in no branch and had to be rebuilt
from scratch. A local stack removes the temptation instead of documenting it.

---

## Requirements

**Docker Desktop** (Windows/macOS) or **Docker Engine + Compose v2** (Linux).
Nothing else - no Python, no Node, no Postgres on your machine.

The stack needs roughly **4 GB of RAM** and about 6 GB of disk.

### Windows: virtualisation must be on

Docker Desktop needs hardware virtualisation. If it starts with *"Virtualization
support not detected"*:

1. **BIOS** - reboot, enter setup (Dell: `F2`), enable **Intel VT-x** /
   **AMD-V**, sometimes listed under Virtualization Support.
2. **Windows features** - in an *admin* PowerShell:
   ```powershell
   wsl --install
   dism /online /Enable-Feature /FeatureName:VirtualMachinePlatform /All /NoRestart
   ```
   then reboot.
3. Check it took:
   ```powershell
   (Get-CimInstance Win32_Processor).VirtualizationFirmwareEnabled   # want True
   ```

On a managed laptop, Credential Guard or a VBS policy can hold the hypervisor
and leave `VirtualizationFirmwareEnabled` at `False` no matter what the BIOS
says. That needs IT, not a setting you can change.

---

## Commands

```bash
npm run local            # start everything
npm run local:down       # stop, keeping data
npm run local:reset -- --yes   # wipe the database and replay migrations
npm run local:logs       # follow everything
npm run local:logs api   # or one service: api, web, voice, db, auth...
npm run local:status     # what is running
npm run local:migrate    # run migrations only
```

Source is bind-mounted, so `uvicorn --reload` and Next fast refresh both work -
edit on the host, the container picks it up. **Rebuild only when a dependency
changes**: `docker compose build api` from `docker/`.

---

## Configuration

`docker/.env` is created from `docker/.env.example` on first run and is
gitignored. Every default in it is local-only and safe: the JWT secret and the
anon/service keys derived from it are the values Supabase's own self-hosting
guide uses, so the key printed here is the key you actually have, and nothing
listens outside localhost.

**To place a real call** you also need a LiveKit project. Fill in `LIVEKIT_URL`,
`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` and `LIVEKIT_SIP_HOST`, then
`npm run local`. Without them everything else works: the API refuses to build a
gateway and the voice worker refuses to start, each naming what is missing.

Carrier, speech and model credentials are **not** environment variables - they
are per-organisation rows you add on **Integrations** in the app.

---

## Where things live

| Service | Port | Notes |
| --- | --- | --- |
| web | 3000 | Next dev server |
| api | 8000 | uvicorn, `--reload` |
| voice | - | worker; health on 8081 inside the network |
| kong | 54321 | one origin for every Supabase service |
| studio | 54323 | database browser |
| db | 55432 | connect directly: `postgres://postgres:postgres@localhost:55432/postgres` |

`db`, `auth`, `rest`, `realtime`, `storage`, `imgproxy`, `meta` and `kong` are
Supabase; `migrate` runs Alembic once and exits before the API starts, so a
failed migration is a failed migration rather than an API that boots and 500s.

Analytics and the vector collector from Supabase's own compose are deliberately
left out - they are the heaviest part of that stack and contribute nothing here.

---

## Running the tests

The suites run against the containerised database:

```bash
docker compose -f docker/docker-compose.yml exec api pytest -q
docker compose -f docker/docker-compose.yml exec voice pytest -q
```

The tenant-isolation tests in `apps/api/tests/test_rls_isolation.py` **only run
with a database** and are skipped without one - which is why CI, which has none,
cannot catch a broken RLS policy. Run them locally before touching any policy.

---

## The one rule

**Never point `DATABASE_URL` at a shared Supabase project.** Not to "just check
something", not to run one migration. That is what broke production and then
dev, and both took a full rebuild to recover. The stack above exists so you
never have a reason to.
