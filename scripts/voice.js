#!/usr/bin/env node
'use strict';

/**
 * Starts the LiveKit voice worker without having to be in the right directory
 * or remember to activate the venv.
 *
 * The worker is the piece that speaks and listens on a call, and it is easy to
 * forget it exists: the API and the web app are what you look at, so a run can
 * dial, connect, and leave the contact hearing silence with nothing on screen
 * saying why (`ISSUES.md` #163). One command alongside the others makes it part
 * of starting the stack rather than a step in a document.
 *
 * Resolves the interpreter from the repo-root .venv before falling back to
 * PATH, exactly as scripts/db.js does and for the same reason - a bare
 * `python` only works when the venv happens to be activated.
 */

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const REPO_ROOT = path.join(__dirname, '..');
const RUNTIME_DIR = path.join(REPO_ROOT, 'apps', 'voice-runtime');

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

const python = resolvePython();
const args = process.argv.slice(2);
const result = spawnSync(python, ['-m', 'app.worker', ...(args.length ? args : ['start'])], {
  cwd: RUNTIME_DIR,
  stdio: 'inherit',
});

if (result.error) {
  console.error(`Could not run "${python}": ${result.error.message}`);
  process.exit(1);
}

// The plugins are optional extras, so a missing one is the likely first failure
// and its ModuleNotFoundError names a package rather than the thing to install.
if (result.status !== 0) {
  console.error(
    '\nIf that failed on a missing livekit plugin, install the vendors your\n' +
      'agents use, from apps/voice-runtime:\n' +
      '  pip install -e ".[sarvam,openai,silero]"\n' +
      'silero is always needed - it is the voice-activity detector.',
  );
}
process.exit(result.status ?? 1);
