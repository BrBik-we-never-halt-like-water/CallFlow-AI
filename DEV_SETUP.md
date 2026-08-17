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
| Mail (every auth email lands here) | http://localhost:54324 |

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

---

## Working day to day

You start the stack once and leave it running. Editing code is the normal case
and mostly needs nothing from you; the exceptions are worth knowing before they
cost you an afternoon.

### What reloads on save

`apps/api`, `apps/web` and `apps/voice-runtime` are bind-mounted into their
containers, so the code running inside is the code on your disk - there is no
copy step and no rebuild between an edit and the next request.

| You edit | What happens |
| --- | --- |
| `apps/api/**` | `uvicorn --reload` restarts the app, about a second |
| `apps/web/**` | Next fast-refreshes the route in the browser |
| `apps/voice-runtime/**` | **nothing** - restart it: `npm run local:logs` will show it come back after `docker compose -f docker/docker-compose.yml restart voice` |

The voice worker is the odd one out because `python -m app.worker start` has no
reloader. A LiveKit worker registers with the server on boot and holds the
connection, so restarting it is the honest way to pick up a change rather than
something that could be papered over with a file watcher.

On Windows and macOS the web container sets `WATCHPACK_POLLING=true`: file
change events do not cross the host-to-Linux filesystem boundary, so without
polling you would save a file and watch nothing happen.

### What needs more than a save

| You changed | Do this |
| --- | --- |
| `pyproject.toml` or `package.json` (a dependency) | `docker compose -f docker/docker-compose.yml up -d --build -V <service>` |
| a `docker/*.Dockerfile` | same as above |
| `docker/docker-compose.yml` or `docker/.env` | `npm run local` - compose recreates only what changed |
| pulled a branch with a new migration | `npm run local:migrate` |
| `docker/volumes/kong.yml` | `docker compose -f docker/docker-compose.yml restart kong` |
| `docker/volumes/db/*.sql` | `npm run local:reset -- --yes` - see below |

**`-V` on a dependency change is not optional.** `node_modules` and `.next` are
anonymous volumes mounted over the bind mount, which is what stops your
Windows-built native binaries (SWC, sharp) from shadowing the Linux ones. Compose
deliberately carries an anonymous volume across a recreate so you do not lose
data - which here means a rebuild installs the new package into the image and
then mounts the old `node_modules` straight back over it. You rebuild, nothing
changes, and there is no error to read. `-V` (`--renew-anon-volumes`) is what
tells compose to take the image's copy instead. The same applies in reverse:
`npm install` on the host never reaches the container.

**The database init scripts only run once.** `docker/volumes/db/*.sql` create the
roles and schemas Supabase's services expect, and Postgres runs them against an
empty data directory and never again. Changing one means throwing the volume
away, which is what `npm run local:reset -- --yes` does - and it takes your local
accounts and data with it, so sign up again afterwards.

**Migrations do not run on their own after the first start.** `migrate` is a
one-shot container: it waits for the `auth` schema to exist, runs
`alembic upgrade head`, and exits before the API starts. That ordering is on
purpose - a failed migration is a failed start rather than an API that boots and
then 500s on every query. But it means pulling a branch with a new revision
needs `npm run local:migrate`.

### The loop, in full

```bash
npm run local                       # once, in the morning
# edit apps/api or apps/web         → saved, reloaded, done
# edit apps/voice-runtime           → restart voice
npm run local:logs api web          # when something looks wrong
npm run local:down                  # end of day, data survives
```

Expect the first `/app` request after a start to take around 40 seconds - the web
container runs webpack rather than Turbopack (Turbopack's resolver cannot follow
`node_modules` across the anonymous-volume boundary and panics on every compile).
It is warm after that.

### When it misbehaves

| Symptom | Cause | Fix |
| --- | --- | --- |
| A package you just installed is "not found" | the old anonymous `node_modules` is still mounted | rebuild with `-V` |
| Signing in bounces straight back to `/login` | the middleware cannot reach Supabase | check `callflow-web` logged `localhost:54321 -> kong:8000` on start |
| The API 500s on a column that exists in your branch | migrations have not run | `npm run local:migrate` |
| A service is `unhealthy` and nothing works | look at the one *below* it | `npm run local:logs db auth` - a failed database init surfaces two services away |
| `port is already allocated` | something else holds 3000/8000/54321/55432 | stop it, or set `WEB_PORT`/`API_PORT` in `docker/.env` |
| Studio shows `unhealthy` | its healthcheck expects the analytics service, which this stack leaves out | ignore it - Studio works |
| Chat does not update until you reload; escalations and share requests are stale too | your database predates the `realtime` schema being created at init, so Realtime has no `subscription` table | `npm run local:reset -- --yes` (rebuilds the volume), or apply it in place: `docker compose -f docker/docker-compose.yml exec db psql -U postgres -c "create schema if not exists realtime authorization supabase_admin;" && docker compose -f docker/docker-compose.yml restart realtime` |

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

**Password reset and every other auth email** go to the mailpit container, not
to a real inbox: request a reset at `/forgot-password`, then open
http://localhost:54324 and click the link in the message waiting there. Nothing
is sent off the machine. To deliver for real instead, point the `SMTP_*` block
in `docker/.env` at Resend (`smtp.resend.com`, port 587, user `resend`, pass =
your `RESEND_API_KEY`) and `npm run local`.

These are GoTrue's emails and are unrelated to the Resend key below, which only
sends invitations. Leaving `SMTP_HOST` blank is the one thing to avoid: GoTrue
then discards the mail silently and the reset looks like it worked
(`ISSUES.md` #119).

**To send an invitation** you need a Resend key. Fill in `RESEND_API_KEY` (and
optionally `RESEND_FROM_EMAIL`, which otherwise falls back to the app default),
then `npm run local`. Without it every other feature works and the invite fails
with a message naming the missing key rather than pretending it sent.

Note that `docker/.env` is the only env file compose reads. The **repo-root**
`.env` is a different file, used by Alembic and the `npm run db:*` scripts - a
value set there does not reach any container (`ISSUES.md` #118).

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
