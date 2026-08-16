#!/usr/bin/env node
'use strict';

/**
 * A disposable local Postgres for development and tests.
 *
 * Exists because the alternative is what actually happened: with no local
 * database, people pointed DATABASE_URL at the shared Supabase project, ran
 * migrations and the RLS suite against it, and left it carrying tables no
 * merged branch described (`ISSUES.md` #80). A local database that takes one
 * command is the only durable fix for that.
 *
 * **No Docker on purpose.** The Supabase CLI gives higher fidelity - real
 * GoTrue, real Storage, Studio - and DEV_SETUP.md documents it as the option
 * for anything touching auth flows. But it needs a running Docker daemon, and
 * an onboarding step that fails when Docker is asleep is an onboarding step
 * people route around. This path needs only the Postgres binaries.
 *
 * What it is not: a Supabase replica. `scripts/local-db/supabase-shim.sql`
 * provides the minimum surface the migrations reference - auth.users,
 * auth.uid(), storage, and the three roles - which is enough for every RLS
 * policy in this schema to evaluate for real.
 */

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const REPO_ROOT = path.join(__dirname, '..');
const API_DIR = path.join(REPO_ROOT, 'apps', 'api');
const SHIM = path.join(__dirname, 'local-db', 'supabase-shim.sql');

// 55432, not 5432: a developer may already have a system Postgres on the
// default port, and silently colliding with it is worse than an explicit port.
const PORT = process.env.CALLFLOW_DEV_DB_PORT || '55432';
const DB = 'callflow_dev';
const SUPERUSER = 'postgres';
const PGDATA = path.join(os.tmpdir(), 'callflow-dev-pgdata');

const URL = `postgresql://${SUPERUSER}:${SUPERUSER}@127.0.0.1:${PORT}/${DB}`;

/** Postgres binaries are rarely on PATH on Windows; probe the usual homes. */
function resolvePgBin(name) {
  const exe = process.platform === 'win32' ? `${name}.exe` : name;
  const roots = [
    process.env.PGBIN,
    path.join(os.homedir(), 'scoop', 'apps', 'postgresql', 'current', 'bin'),
    'C:/Program Files/PostgreSQL/18/bin',
    'C:/Program Files/PostgreSQL/17/bin',
    'C:/Program Files/PostgreSQL/16/bin',
    '/usr/lib/postgresql/17/bin',
    '/usr/lib/postgresql/16/bin',
    '/opt/homebrew/bin',
    '/usr/local/bin',
  ].filter(Boolean);

  for (const root of roots) {
    const candidate = path.join(root, exe);
    if (fs.existsSync(candidate)) return candidate;
  }
  // Fall back to PATH and let the spawn fail with a real message.
  return name;
}

function run(bin, args, options = {}) {
  return spawnSync(resolvePgBin(bin), args, {
    stdio: options.quiet ? 'pipe' : 'inherit',
    encoding: 'utf8',
    env: { ...process.env, PGPASSWORD: SUPERUSER },
    ...options,
  });
}

/** Blocking sleep. `Atomics.wait` is the only one that needs no async plumbing. */
function sleep(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function isRunning() {
  const result = run('pg_isready', ['-h', '127.0.0.1', '-p', PORT], {
    quiet: true,
  });
  return result.status === 0;
}

function psql(database, args, options = {}) {
  return run(
    'psql',
    ['-h', '127.0.0.1', '-p', PORT, '-U', SUPERUSER, '-d', database, ...args],
    options,
  );
}

function fail(message) {
  console.error(`\n${message}\n`);
  process.exit(1);
}

function requirePostgres() {
  const probe = run('initdb', ['--version'], { quiet: true });
  if (probe.error || probe.status !== 0) {
    fail(
      'Could not find the PostgreSQL binaries (initdb, pg_ctl, psql).\n\n' +
        '  Windows : scoop install postgresql   (or the EDB installer)\n' +
        '  macOS   : brew install postgresql@17\n' +
        '  Linux   : sudo apt install postgresql\n\n' +
        'If they are installed somewhere unusual, set PGBIN to that bin directory.',
    );
  }
}

function start() {
  if (isRunning()) return;

  if (!fs.existsSync(PGDATA)) {
    console.log(`Creating a cluster in ${PGDATA} (first run only, ~20s) ...`);
    const pwfile = path.join(os.tmpdir(), 'callflow-dev-pw.txt');
    fs.writeFileSync(pwfile, SUPERUSER);
    const init = run('initdb', [
      '-D', PGDATA, '-U', SUPERUSER, '--auth=trust', `--pwfile=${pwfile}`, '-E', 'UTF8',
    ], { quiet: true });
    fs.unlinkSync(pwfile);
    if (init.status !== 0) fail(`initdb failed:\n${init.stderr || init.stdout}`);
  }

  console.log(`Starting Postgres on 127.0.0.1:${PORT} ...`);
  const logFile = path.join(PGDATA, 'server.log');
  run('pg_ctl', [
    '-D', PGDATA,
    '-o', `-p ${PORT} -c listen_addresses=127.0.0.1`,
    // Inside the cluster, not a shared temp path: a log file in tmp stays
    // locked by a previous (or half-dead) postmaster and the next start fails
    // with a permission error that says nothing about the real cause.
    '-l', logFile,
    'start',
  ], {
    // `ignore`, never `pipe`. pg_ctl daemonises, but the postmaster inherits
    // whatever stdio it was given and holds it open for its whole life - so a
    // piped spawnSync waits for an EOF that only arrives when the database
    // shuts down. That is a multi-minute hang with no error, and it is exactly
    // what the first version of this script did.
    stdio: 'ignore',
  });

  // `pg_ctl start` already waits for readiness, but a cold cluster can be a
  // moment behind the socket. Poll with a real blocking sleep - spawning a
  // process per tick costs more than the wait it is measuring, which is what
  // made the first version of this appear to hang.
  const deadline = Date.now() + 15000;
  while (!isRunning() && Date.now() < deadline) sleep(250);
  if (!isRunning()) {
    // Read the log rather than the process output: the start above is spawned
    // with stdio ignored (see the comment there), so there is nothing captured
    // to report.
    const log = fs.existsSync(logFile)
      ? fs.readFileSync(logFile, 'utf8').slice(-1500)
      : '(no server.log was written)';
    fail(`Postgres did not start.\n\n${log}`);
  }

  // `pg_isready` answers yes before a freshly-initdb'd cluster will actually
  // serve a query, and the first `create database` against that gap blocks
  // rather than erroring - which is what made the very first run of this script
  // appear to hang forever. Wait for a real query, not just an open socket.
  const queryable = Date.now() + 20000;
  while (Date.now() < queryable) {
    const probe = psql('postgres', ['-qAt', '-c', 'select 1'], { quiet: true, timeout: 5000 });
    if (String(probe.stdout || '').trim() === '1') return;
    sleep(400);
  }
  fail('Postgres started but never began answering queries.');
}

function createDatabase({ fresh }) {
  if (fresh) {
    psql('postgres', ['-q', '-c', `drop database if exists ${DB} with (force)`], {
      quiet: true,
    });
  }
  const exists = psql('postgres', [
    '-qAt', '-c', `select 1 from pg_database where datname='${DB}'`,
  ], { quiet: true });

  if (!String(exists.stdout || '').trim()) {
    const created = psql('postgres', ['-q', '-c', `create database ${DB}`], {
      quiet: true,
    });
    if (created.status !== 0) {
      fail(`Could not create ${DB}:\n${created.stderr || created.stdout}`);
    }
    console.log(`Created database ${DB}.`);
  }

  console.log('Applying the Supabase shim ...');
  const shim = psql(DB, ['-q', '-v', 'ON_ERROR_STOP=1', '-f', SHIM], {
    quiet: true,
  });
  if (shim.status !== 0) fail(`Shim failed:\n${shim.stderr || shim.stdout}`);
}

function resolvePython() {
  for (const candidate of [
    path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe'),
    path.join(REPO_ROOT, '.venv', 'bin', 'python'),
  ]) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return 'python';
}

function migrate() {
  console.log('Running migrations ...');
  const result = spawnSync(resolvePython(), ['-m', 'alembic', 'upgrade', 'head'], {
    cwd: API_DIR,
    stdio: 'inherit',
    // Both are set: alembic uses DIRECT_URL where it exists, and passing only
    // one leaves the other pointing at whatever .env holds - which, on a
    // developer machine, has been the shared Supabase project.
    env: { ...process.env, DATABASE_URL: URL, DIRECT_URL: URL },
  });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function grantAnon() {
  // Supabase's own bootstrap grants `anon` table-level SELECT and relies on RLS
  // to return zero rows. Without this, `test_anonymous_sees_nothing` fails with
  // a permission error instead of the empty result it asserts - a different
  // outcome from the one production actually produces.
  psql(DB, ['-q', '-c', 'grant select on all tables in schema public to anon;'], {
    quiet: true,
  });
}

function printReady() {
  console.log(`
Local database ready.

  DATABASE_URL=${URL}
  DIRECT_URL=${URL}

Put both in your repo-root .env. Never point them at a shared Supabase project -
that is how production ended up carrying tables no branch described (ISSUES.md #80).

  npm run dev:db:status   what revision it is on
  npm run dev:db:reset    wipe and rebuild from scratch
  npm run dev:db:down     stop it (data survives until you reset)
`);
}

function status() {
  if (!isRunning()) {
    console.log(`Not running. Start it with: npm run dev:db`);
    return;
  }
  // Checked, not assumed. An earlier version printed the database name from a
  // constant, so it reported a healthy database that had never been created.
  const present = psql('postgres', [
    '-qAt', '-c', `select 1 from pg_database where datname='${DB}'`,
  ], { quiet: true });
  if (String(present.stdout || '').trim() !== '1') {
    console.log(`Server is up on 127.0.0.1:${PORT}, but the ${DB} database does not exist.
Run: npm run dev:db`);
    return;
  }

  const revision = psql(DB, ['-qAt', '-c', 'select version_num from alembic_version'], {
    quiet: true,
  });
  const tables = psql(DB, [
    '-qAt', '-c', "select count(*) from pg_tables where schemaname='public'",
  ], { quiet: true });

  console.log(`Running on 127.0.0.1:${PORT}
  database  ${DB}
  revision  ${String(revision.stdout || '').trim() || '(none - run npm run dev:db)'}
  tables    ${String(tables.stdout || '0').trim()}
  url       ${URL}`);
}

const action = process.argv[2] || 'up';

switch (action) {
  case 'up': {
    requirePostgres();
    start();
    createDatabase({ fresh: false });
    migrate();
    grantAnon();
    printReady();
    break;
  }
  case 'reset': {
    requirePostgres();
    start();
    createDatabase({ fresh: true });
    migrate();
    grantAnon();
    console.log('\nReset complete - the database is empty and at head.\n');
    break;
  }
  case 'down': {
    if (!isRunning()) {
      console.log('Not running.');
      break;
    }
    run('pg_ctl', ['-D', PGDATA, 'stop', '-m', 'fast'], { quiet: true });
    console.log('Stopped. Data is kept; `npm run dev:db` brings it back.');
    break;
  }
  case 'destroy': {
    if (isRunning()) run('pg_ctl', ['-D', PGDATA, 'stop', '-m', 'fast'], { quiet: true });
    fs.rmSync(PGDATA, { recursive: true, force: true });
    console.log(`Removed ${PGDATA}.`);
    break;
  }
  case 'status': {
    requirePostgres();
    status();
    break;
  }
  case 'url': {
    process.stdout.write(URL);
    break;
  }
  default:
    console.error(`Unknown action "${action}". Use: up | reset | down | destroy | status | url`);
    process.exit(1);
}
