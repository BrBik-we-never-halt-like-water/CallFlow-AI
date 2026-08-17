import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import { isProtected, updateSession } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  // Without Supabase configured there is no session to refresh and no way to sign
  // in. Public pages still render - the auth pages explain what is missing - but
  // /app must still be refused: letting it through fails open, and a dev server
  // started before .env.local existed would serve the whole dashboard to anyone.
  // Fail closed, the same rule the API's safety checks follow (CLAUDE.md #2).
  if (!isSupabaseConfigured()) {
    if (isProtected(request.nextUrl.pathname)) {
      const login = request.nextUrl.clone();
      login.pathname = '/login';
      login.search = '';
      return NextResponse.redirect(login);
    }
    return NextResponse.next({ request });
  }

  return updateSession(request);
}

export const config = {
  matcher: [
    // Everything except static assets and the generated icon/OG routes. Those are
    // public by definition and running auth on them is pure latency.
    "/((?!_next/static|_next/image|favicon.ico|icon.svg|apple-icon|opengraph-image|manifest.webmanifest|.*\\.(?:svg|png|jpg|jpeg|gif|webp|woff2?)$).*)",
  ],
};
