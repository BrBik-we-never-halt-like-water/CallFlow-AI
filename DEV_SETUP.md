# Local setup

Everything needed to run CallFlow on your own machine, including a real
database. Follow it top to bottom on a new checkout; it takes about ten minutes,
most of which is downloads.

> **The one rule.** Never point `DATABASE_URL` at a shared Supabase project.
> That is not a style preference: it is how production ended up carrying six
> tables no merged branch described, ~40 users created by the RLS test suite,
> and a migration pointer naming a revision that existed only on somebody's
> laptop (`ISSUES.md` #80). A local database exists precisely so nobody needs to.

---

## 1. Prerequisites

| Tool | Version | Check |
| --- | --- | --- |
| Node | 20+ | `node --version` |
| Python | 3.11+ | `python --version` |
| PostgreSQL **client + server binaries** | 16+ | `initdb --version` |

You need Postgres *installed*, not *running* — the tooling starts its own
instance on a private port and never touches a system one.

```bash
# Windows
scoop install postgresql        # or the EDB installer

# macOS
brew install postgresql@17

# Debian/Ubuntu
sudo apt install postgresql
```

If the binaries live somewhere unusual, set `PGBIN` to that `bin` directory and
everything below still works.

---

## 2. Install

```bash
git clone git@github.com:BrBik-we-never-halt-like-water/CallFlow-AI.git
cd CallFlow-AI

python -m venv .venv                       # one venv at the repo root, shared by both Python apps
.venv/Scripts/python -m pip install -e "apps/api[dev]"      # Windows
# .venv/bin/python  -m pip install -e "apps/api[dev]"       # macOS / Linux

npm ci --prefix apps/web
```

The voice runtime is optional until you're working on calls:

```bash
cd apps/voice-runtime
../../.venv/Scripts/pip install -e ".[sarvam,openai,silero]"
```

Its STT/TTS/LLM plugins are **extras on purpose** — each pulls a large dependency
tree, and a deployment should install only the vendors its organisations use.

---

## 3. The database

```bash
npm run dev:db
```

That single command creates a cluster, applies a Supabase shim, runs every
migration, and prints the connection string. First run ~15s; after that ~5s.

| Command | What it does |
| --- | --- |
| `npm run dev:db` | Start it and bring the schema to head |
| `npm run dev:db:status` | Which revision, how many tables |
| `npm run dev:db:reset` | Wipe and rebuild — the fast way back to a clean slate |
| `npm run dev:db:down` | Stop it; data survives |
| `npm run dev:db:destroy` | Delete the cluster entirely |

It runs on **127.0.0.1:55432**, not 5432, so it cannot collide with a Postgres
you already have.

### What the shim is, and is not

`scripts/local-db/supabase-shim.sql` provides the minimum Supabase surface the
migrations reference: `auth.users`, `auth.uid()`, `storage.buckets` /
`storage.objects`, and the `anon` / `authenticated` / `service_role` roles.

That is enough for **every RLS policy in this schema to evaluate for real** —
the role switch, `auth.uid()`, and cross-tenant filtering all behave as they do
in production. It is not a Supabase replica: no GoTrue, no Studio, no realtime.

### When you need the real thing

For work that touches signup, password reset, or storage uploads, use the
Supabase CLI instead — it runs actual GoTrue and Storage in Docker:

```bash
npm i -g supabase
supabase start          # needs a running Docker daemon
```

Point `DATABASE_URL` at the URL it prints, then `npm run db:migrate`.

The local-Postgres path above is the default because it needs no Docker, and an
onboarding step that fails when Docker is asleep is one people route around.

---

## 4. Environment

```bash
cp .env.example .env
```

Then fill in the four things nothing works without:

```bash
# from `npm run dev:db` - your own, never a shared project
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55432/callflow_dev
DIRECT_URL=postgresql://postgres:postgres@127.0.0.1:55432/callflow_dev

# encrypts stored provider credentials AND derives every SIP trunk password.
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
PROVIDER_CREDENTIALS_KEY=

# the voice runtime presents this when reporting a finished call
# openssl rand -hex 32
CALLFLOW_INTERNAL_API_SECRET=
```

**Never rotate `PROVIDER_CREDENTIALS_KEY` once a number is connected.** It
decrypts stored credentials *and* derives trunk passwords, so changing it makes
existing credentials unreadable and silently breaks outbound calls.

Supabase auth values (`SUPABASE_URL`, `SUPABASE_JWKS_URL`, …) are only needed to
sign in through the web app. Ask a teammate for a dev project's values, or run
`supabase start` and use its own.

### Before you dial anything

```bash
CALLFLOW_ALLOWLIST=+<your own number in E.164>
```

While the allowlist is non-empty, that is the only number that can be dialled.
**An empty allowlist means no restriction, not total restriction** — see
`DEPLOYMENT.md`. On a full (non-trial) carrier account it is the only thing
between a test run and a stranger's phone.

---

## 5. Run it

Three processes; each is independent.

```bash
# API                      http://127.0.0.1:8000
cd apps/api && ../../.venv/Scripts/uvicorn app.main:app --reload --port 8000

# Web                      http://localhost:3000
cd apps/web && npm run dev

# Voice runtime (only when working on live calls)
cd apps/voice-runtime && ../../.venv/Scripts/python -m app.worker dev
```

The worker refuses to start without its configuration and names every missing
variable, so a wrong `.env` fails immediately rather than at call time.

---

## 6. Tests

```bash
cd apps/api && ../../.venv/Scripts/python -m pytest -q
```

**With no `DATABASE_URL` you get ~186 passed and ~85 skipped.** The skipped ones
are the tenant-isolation tests, and they are the ones that matter most — a
policy that looks right and permits a cross-tenant read is the most expensive
bug this product can ship. Run them:

```bash
npm run dev:db                                   # if it isn't already up
cd apps/api
DATABASE_URL=$(node ../../scripts/dev-db.js url) \
DIRECT_URL=$(node ../../scripts/dev-db.js url) \
  ../../.venv/Scripts/python -m pytest -q        # 355 passed, 0 skipped
```

CI runs without a database, so **these only ever run if you run them.** Do it
before touching RLS, a migration, or anything with `org_id` in it.

Everything else:

```bash
cd apps/api && ../../.venv/Scripts/ruff check app tests
cd apps/voice-runtime && ../../.venv/Scripts/python -m pytest -q   # 35
cd apps/web && npm run lint && npm run type-check && npm run build
```

Enable the pre-commit hook once and it runs the important ones for you:

```bash
git config core.hooksPath .githooks
```

---

## 7. Migrations

```bash
npm run db:generate -- -m "what changed"   # autogenerate a revision
npm run db:migrate                          # upgrade head
```

These drive **whatever `.env` points at** — which is why §4 insists that is your
own database.

Three things autogenerate cannot see, and you must hand-write into the revision:
RLS (`enable` *and* `force`), a policy per operation, and a `grant` for
`authenticated`. A tenant table missing any of them is a data leak, not a
style issue. Copy the shape from
`alembic/versions/202608151200_voice_agents_and_telephony_provisioning.py`.

Then prove it with a cross-tenant test that hits the database — `tests/test_rls_isolation.py`
has the pattern.

### Adding a migration while someone else is

Alembic allows only one head. Before you push, check:

```bash
cd apps/api && ../../.venv/Scripts/python -m alembic heads
```

Two heads means two revisions claim the same parent, and `upgrade head` then
fails for everyone. Set your `down_revision` to whatever is on `dev`, not to
whatever was there when you branched.

---

## 8. When something is wrong

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Could not find the PostgreSQL binaries` | Not installed, or not on PATH | Install per §1, or set `PGBIN` |
| `Can't locate revision identified by …` | The database is on a revision no branch has — usually an unpushed migration applied by hand | Find the file, or rebuild with `npm run dev:db:reset` |
| Tests report `85 skipped` | No `DATABASE_URL` | §6 |
| `test_anonymous_sees_nothing` fails with a permission error | The `anon` grant is missing | `npm run dev:db` reapplies it |
| `Multiple head revisions` | Two migrations share a parent | §7 |
| Frontend can't reach the API | `NEXT_PUBLIC_API_URL` unset or unreachable | Defaults to `http://127.0.0.1:8000`; the client logs when it falls back |
| `PROVIDER_CREDENTIALS_KEY is not set` | Missing from `.env` | §4 — it fails closed rather than deriving a guessable password |

---

## 9. Things that will bite you

- **Alembic uses psycopg; the app uses asyncpg.** asyncpg prepares every
  statement and rejects the multi-statement DDL that RLS policies are written
  as. Don't "simplify" `alembic/env.py` back to the async driver.
- **Use the direct connection, or the session pooler on 5432 — never the
  transaction pooler on 6543.** Every request runs `SET LOCAL ROLE`, which
  transaction pooling does not preserve, and RLS silently stops applying.
- **`postgres` holds BYPASSRLS.** A plain connection sees every organisation's
  rows regardless of policy. RLS is only real because `database.as_user()` drops
  to `authenticated`. A query that skips that helper skips tenancy.
- **Never edit the schema through the Supabase dashboard.** Alembic is the only
  migration system here; a dashboard change is invisible to it and drifts every
  environment apart.
