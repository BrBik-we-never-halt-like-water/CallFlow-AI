/**
 * The browser half of an OAuth PKCE connection.
 *
 * PKCE exists so a public client can prove the code it redeemed is the one it
 * asked for, without holding a client secret a browser could never keep. We
 * generate a random verifier, send only its SHA-256 hash to the vendor, and
 * present the original when exchanging - an intercepted code is useless without
 * the verifier, which never leaves this origin.
 *
 * The exchange itself is deliberately *not* done here. It happens server-side
 * (`POST /api/v1/integrations/providers/{id}/oauth/exchange`) because what comes
 * back is a long-lived key, and this product keeps those out of the browser
 * everywhere else.
 *
 * Only OpenRouter uses this today. It is written against `ProviderSpec` rather
 * than hard-coded so a second OAuth vendor needs no changes here.
 */

import type { ProviderSpec } from '@/lib/api';

const STORE_KEY = 'callflow.oauth_pending';

/** Where each vendor's authorize page lives. Keyed by provider id so an
 * unsupported vendor fails loudly rather than redirecting somewhere wrong. */
const AUTHORIZE_URL: Record<string, string> = {
  openrouter: 'https://openrouter.ai/auth',
};

interface PendingOAuth {
  provider: string;
  providerName: string;
  verifier: string;
}

function base64Url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

/** 32 bytes of real entropy - `Math.random()` is not suitable for a value whose
 * whole job is being unguessable. */
function randomVerifier(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return base64Url(bytes);
}

async function challengeFor(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(verifier),
  );
  return base64Url(new Uint8Array(digest));
}

/**
 * Send the operator to the vendor's login, remembering what we'll need on the
 * way back. Returns only if the redirect could not be started.
 */
export async function beginOAuth(spec: ProviderSpec): Promise<void> {
  const authorize = AUTHORIZE_URL[spec.id];
  if (!authorize) {
    throw new Error(`${spec.name} has no login flow configured.`);
  }

  const verifier = randomVerifier();
  const pending: PendingOAuth = {
    provider: spec.id,
    providerName: spec.name,
    verifier,
  };
  // sessionStorage, not localStorage: a half-finished connection should not
  // outlive the tab that started it.
  sessionStorage.setItem(STORE_KEY, JSON.stringify(pending));

  const callback = `${window.location.origin}${window.location.pathname}`;
  const url = new URL(authorize);
  url.searchParams.set('callback_url', callback);
  url.searchParams.set('code_challenge', await challengeFor(verifier));
  url.searchParams.set('code_challenge_method', 'S256');

  window.location.assign(url.toString());
}

/**
 * The code the vendor redirected back with, if this is a return trip.
 *
 * Consumes it: the stored verifier is cleared and `?code=` is stripped from the
 * address bar before returning. An authorization code is single-use, so leaving
 * it in the URL means a refresh replays a spent code and reports a failure for a
 * connection that actually succeeded.
 */
export function takePendingOAuth():
  | (PendingOAuth & { code: string })
  | null {
  if (typeof window === 'undefined') return null;

  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  if (!code) return null;

  const raw = sessionStorage.getItem(STORE_KEY);
  sessionStorage.removeItem(STORE_KEY);

  params.delete('code');
  const query = params.toString();
  window.history.replaceState(
    null,
    '',
    window.location.pathname + (query ? `?${query}` : ''),
  );

  if (!raw) return null;
  try {
    const pending = JSON.parse(raw) as PendingOAuth;
    if (!pending?.provider || !pending?.verifier) return null;
    return { ...pending, code };
  } catch {
    return null;
  }
}
