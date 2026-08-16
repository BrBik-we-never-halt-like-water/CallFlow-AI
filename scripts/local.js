#!/usr/bin/env node
/**
 * The local stack, wrapped so nobody has to remember which directory compose
 * lives in or which of ten services to name.
 *
 * Replaces `scripts/dev-db.js`, which gave a native Postgres with a hand-written
 * `auth.users` shim. That could never work end to end: signup goes to an auth
 * *server*, so an account created locally had no row in the local database and
 * no organisation - the trigger fires on `auth.users` inserts that hosted
 * Supabase never makes. Running real GoTrue against the local Postgres is what
 * closes that gap, and it needs containers.
 */

const { spawnSync } = require('node:child_process');
const { existsSync, copyFileSync } = require('node:fs');
const path = require('node:path');

const DOCKER_DIR = path.join(__dirname, '..', 'docker');
const ENV_FILE = path.join(DOCKER_DIR, '.env');
const ENV_EXAMPLE = path.join(DOCKER_DIR, '.env.example');

const SUPABASE_URL = 'http://localhost:54321';
const STUDIO_URL = 'http://localhost:54323';
const WEB_URL = 'http://localhost:3000';
const API_URL = 'http://localhost:8000';

function compose(args, options = {}) {
  return spawnSync('docker', ['compose', ...args], {
    cwd: DOCKER_DIR,
    stdio: options.quiet ? 'pipe' : 'inherit',
    encoding: 'utf8',
    shell: process.platform === 'win32',
    ...options,
  });
}

function fail(message) {
  console.error(`\n${message}\n`);
  process.exit(1);
}

function requireDocker() {
  const probe = spawnSync('docker', ['compose', 'version'], {
    stdio: 'pipe',
    encoding: 'utf8',
    shell: process.platform === 'win32',
  });
  if (probe.error || probe.status !== 0) {
    fail(
      'Docker Compose is not available.\n\n' +
        '  Windows / macOS : install Docker Desktop, then start it\n' +
        '  Linux           : sudo apt install docker.io docker-compose-plugin\n\n' +
        'The whole stack runs in containers, so there is no fallback path.',
    );
  }
}

/** Created from the template on first run, so `up` needs no prior step. */
function ensureEnv() {
  if (existsSync(ENV_FILE)) return;
  copyFileSync(ENV_EXAMPLE, ENV_FILE);
  console.log(`Created docker/.env from the template.`);
  console.log('Add LiveKit credentials to it when you want to place calls.\n');
}

function up() {
  requireDocker();
  ensureEnv();
  console.log('Starting the stack. First run pulls images and builds - give it a few minutes.\n');
  const result = compose(['up', '-d', '--build']);
  if (result.status !== 0) fail('Compose failed to start. The output above says which service.');

  console.log(`
Ready.

  Web        ${WEB_URL}
  API        ${API_URL}/api/health
  Studio     ${STUDIO_URL}          browse the database
  Supabase   ${SUPABASE_URL}

Sign up at ${WEB_URL}/signup - auth runs locally, so the trigger creates
your organisation and you land straight in it. No mirroring step, no shared
project, nothing to ask a teammate for.

  npm run local:logs      follow everything
  npm run local:reset     wipe the database and replay migrations
  npm run local:down      stop, keeping data
`);
}

function down() {
  requireDocker();
  compose(['down']);
  console.log('\nStopped. Data survives - `npm run local:reset` wipes it.\n');
}

function reset() {
  requireDocker();
  if (!process.argv.includes('--yes')) {
    fail(
      'This deletes the local database and storage completely, then rebuilds\n' +
        'from migrations. Re-run with --yes if that is what you want:\n\n' +
        '  npm run local:reset -- --yes',
    );
  }
  compose(['down', '-v']);
  ensureEnv();
  const result = compose(['up', '-d', '--build']);
  if (result.status !== 0) fail('Rebuild failed. The output above says which service.');
  console.log('\nReset. Everything replayed from migrations - sign up again to get an org.\n');
}

function logs() {
  requireDocker();
  const services = process.argv.slice(3).filter((a) => !a.startsWith('-'));
  compose(['logs', '-f', '--tail', '100', ...services]);
}

function status() {
  requireDocker();
  compose(['ps']);
}

function migrate() {
  requireDocker();
  const result = compose(['run', '--rm', 'migrate']);
  if (result.status !== 0) fail('Migration failed. The output above says why.');
}

/** Regenerate the keys in docker/.env after changing JWT_SECRET. */
function keys() {
  console.log(`
The anon and service keys are JWTs signed with JWT_SECRET, so changing the
secret without regenerating them makes every request 401.

Regenerate at https://supabase.com/docs/guides/self-hosting#api-keys, or keep
the defaults - they are local-only and identical on every machine by design.
`);
}

const COMMANDS = { up, down, reset, logs, status, migrate, keys };
const command = process.argv[2];

if (!command || !COMMANDS[command]) {
  console.log(`
CallFlow AI, locally.

  npm run local           start everything
  npm run local:down      stop, keeping data
  npm run local:reset     wipe and rebuild        (needs -- --yes)
  npm run local:logs      follow logs             (optionally name a service)
  npm run local:status    what is running
  npm run local:migrate   run migrations only
`);
  process.exit(command ? 1 : 0);
}

COMMANDS[command]();
