'use client';

import { createBrowserClient } from '@supabase/ssr';
import type { SupabaseClient } from '@supabase/supabase-js';
import { supabaseAnonKey, supabaseUrl } from './config';

let cached: SupabaseClient | null = null;

/**
 * The browser client. Sessions live in cookies, not localStorage, so the server can
 * read them during SSR and middleware can refresh them - `@supabase/ssr` handles the
 * cookie plumbing.
 *
 * Cached because each instance opens its own auth listener; creating one per render
 * leaks listeners and produces duplicate token refreshes.
 */
export function supabaseBrowser(): SupabaseClient {
  cached ??= createBrowserClient(supabaseUrl(), supabaseAnonKey());
  return cached;
}
