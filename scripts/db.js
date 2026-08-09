#!/usr/bin/env node
'use strict';

/**
 * Thin wrapper around Alembic (apps/api) so the database can be driven with
 * plain npm scripts instead of remembering to activate the venv first.
 *
 * Resolves the interpreter from the repo-root .venv before falling back to
 * PATH, mirroring .githooks/pre-commit's own find_tool() - same reasoning:
 * a bare `python`/`alembic` only works when the venv happens to be activated,
 * which it usually isn't in a fresh terminal or a GUI client.
 */

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const REPO_ROOT = path.join(__dirname, '..');
const API_DIR = path.join(REPO_ROOT, 'apps', 'api');

function resolvePython() {
  const candidates = [
    path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe'),
    path.join(REPO_ROOT, '.venv', 'bin', 'python'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return 'python';
}

function runAlembic(args) {
  const python = resolvePython();
  const result = spawnSync(python, ['-m', 'alembic', ...args], {
    cwd: API_DIR,
    stdio: 'inherit',
  });
  if (result.error) {
    console.error(`Could not run "${python}": ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}

const [action, ...extraArgs] = process.argv.slice(2);

switch (action) {
  case 'migrate':
    // Applies whatever is pending - safe to run repeatedly, a no-op at head.
    runAlembic(['upgrade', 'head']);
    break;

  case 'generate':
    // Diffs database/models.py against the live schema and writes a new
    // revision file - it does NOT apply it. Review the generated file before
    // running db:migrate, the same as any other Alembic autogenerate: it
    // cannot see RLS policies, triggers, or grants (CLAUDE.md §4b) - those
    // still need to be hand-written into the revision.
    // Pass a message with: npm run db:generate -- -m "add foo column"
    runAlembic(['revision', '--autogenerate', ...extraArgs]);
    break;

  case 'reset':
    // Rewinds every migration to base and replays them from scratch. This is
    // NOT a disposable local database - it's whatever DATABASE_URL/DIRECT_URL
    // the repo-root .env points at, which for this project is the shared
    // Supabase instance. Refuses to run without --yes so a stray keypress
    // can't drop every table the product owns.
    if (!extraArgs.includes('--yes')) {
      console.error('db:reset rewinds EVERY migration to base, then replays them all.');
      console.error('This runs against the database in the repo-root .env - the shared');
      console.error('Supabase instance, unless you have pointed DATABASE_URL somewhere');
      console.error('else. It drops every table Alembic manages: users, organisations,');
      console.error('campaigns, runs, call_outcomes, and everything else.');
      console.error('');
      console.error('Re-run with --yes if that is really what you want:');
      console.error('  npm run db:reset -- --yes');
      process.exit(1);
    }
    runAlembic(['downgrade', 'base']);
    runAlembic(['upgrade', 'head']);
    break;

  default:
    console.error(`Unknown db action: "${action ?? ''}". Expected migrate, generate, or reset.`);
    process.exit(1);
}
