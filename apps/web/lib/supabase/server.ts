import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { supabaseAnonKey, supabaseUrl } from "./config";

/**
 * Server client for Server Components, Server Actions, and route handlers.
 *
 * Not cached: `cookies()` is request-scoped, so a shared instance would serve one
 * request's session to another.
 */
export async function supabaseServer(): Promise<SupabaseClient> {
  const store = await cookies();

  return createServerClient(supabaseUrl(), supabaseAnonKey(), {
    cookies: {
      getAll() {
        return store.getAll();
      },
      setAll(items) {
        try {
          for (const { name, value, options } of items) {
            store.set(name, value, options);
          }
        } catch {
          // Server Components cannot set cookies. That is expected and harmless here:
          // middleware refreshes the session on every request, so a token that could
          // not be written during render is written on the next one.
        }
      },
    },
  });
}

export interface SessionUser {
  id: string;
  email: string;
  accessToken: string;
}

/**
 * The signed-in user, or null.
 *
 * Uses `getUser()` rather than `getSession()` deliberately: `getSession` returns
 * whatever is in the cookie without validating it, so a forged cookie would satisfy
 * it. `getUser` verifies the token against Supabase.
 */
export async function currentSession(): Promise<SessionUser | null> {
  const supabase = await supabaseServer();

  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) return null;

  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) return null;

  return {
    id: user.id,
    email: user.email ?? "",
    accessToken: session.access_token,
  };
}
