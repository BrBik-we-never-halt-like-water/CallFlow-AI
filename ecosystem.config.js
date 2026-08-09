/**
 * pm2 process definitions for a deployed checkout.
 *
 * Both the API and the web app run from this directory, so `__dirname` is the
 * deploy root and every path below is absolute - pm2 resolves a relative script
 * against its own cwd, not the config file's, which is the usual way this breaks.
 *
 * Set CALLFLOW_ENV=dev to get the `-dev` process names and the second port pair,
 * so a dev deployment can sit beside production on one VM without either one
 * having to know the other exists:
 *
 *   CALLFLOW_ENV=dev pm2 startOrRestart ecosystem.config.js --update-env
 *
 * Ports are the only thing nginx needs to know. Override them with API_PORT /
 * WEB_PORT if these two pairs are already taken.
 */

const isDev = process.env.CALLFLOW_ENV === 'dev';
const suffix = isDev ? '-dev' : '';

const apiPort = process.env.API_PORT || (isDev ? '8001' : '8000');
const webPort = process.env.WEB_PORT || (isDev ? '3001' : '3000');

// Also read by scripts/bootstrap.sh, to render the nginx server block against the
// same numbers pm2 binds. pm2 only looks at `apps`, so the extra key is inert.
module.exports = {
  ports: { api: apiPort, web: webPort },

  apps: [
    {
      name: `callflow-api${suffix}`,
      cwd: `${__dirname}/apps/api`,
      // The venv's uvicorn, not whatever is on PATH - pm2 starts from a login
      // shell that has never activated it.
      script: `${__dirname}/.venv/bin/uvicorn`,
      // One worker on purpose. The rate limiter in app/core/rate_limit.py is a
      // per-process dict, so a second worker would silently double every limit.
      // ponytail: single worker; move the limiter to Redis before scaling out.
      args: `app.main:app --host 127.0.0.1 --port ${apiPort}`,
      interpreter: 'none',
      env: { CALLFLOW_ENV: isDev ? 'dev' : 'production' },
    },
    {
      name: `callflow-web${suffix}`,
      cwd: `${__dirname}/apps/web`,
      // next directly rather than `npm run start`: npm adds a wrapper process
      // that does not forward pm2's signals, so restarts leave the old server
      // holding the port.
      script: `${__dirname}/apps/web/node_modules/.bin/next`,
      args: 'start',
      interpreter: 'none',
      env: { NODE_ENV: 'production', PORT: webPort },
    },
  ],
};
