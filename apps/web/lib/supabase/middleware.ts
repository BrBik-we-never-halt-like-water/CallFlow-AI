import { createServerClient } from "@supabase/ssr";
import { type NextRequest, NextResponse } from "next/server";
import { supabaseAnonKey, supabaseUrl } from "./config";

/** Routes that require a session. Everything else is public. */
const PROTECTED_PREFIXES = ["/app"];

/** Auth pages a signed-in user should not sit on. */
const AUTH_PAGES = ["/login", "/signup", "/forgot-password"];

function matches(pathname: string, prefixes: string[]): boolean {
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/**
 * Refreshes the session cookie and gates protected routes.
 *
 * The response object must be the one carrying the cookies Supabase wrote — building
 * a fresh `NextResponse` after `getUser()` silently discards the refreshed token, and
 * the user is signed out roughly an hour later with no obvious cause.
 */
export async function updateSession(request: NextRequest): Promise<NextResponse> {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(supabaseUrl(), supabaseAnonKey(), {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(items) {
        for (const { name, value } of items) {
          request.cookies.set(name, value);
        }
        response = NextResponse.next({ request });
        for (const { name, value, options } of items) {
          response.cookies.set(name, value, options);
        }
      },
    },
  });

  // getUser, not getSession: this validates the token rather than trusting the cookie.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const { pathname, searchParams } = request.nextUrl;

  if (!user && matches(pathname, PROTECTED_PREFIXES)) {
    const login = request.nextUrl.clone();
    login.pathname = "/login";
    login.search = "";
    // Preserve where they were headed so sign-in can return them there.
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }

  if (user && matches(pathname, AUTH_PAGES)) {
    const target = request.nextUrl.clone();
    const next = searchParams.get("next");
    target.pathname = next && next.startsWith("/app") ? next : "/app";
    target.search = "";
    return NextResponse.redirect(target);
  }

  return response;
}
