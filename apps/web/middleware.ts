import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import { updateSession } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  // Without Supabase configured there is no session to refresh and no way to sign in,
  // so gating /app would lock the dashboard behind a door with no key. Let it through:
  // the auth pages explain what is missing.
  if (!isSupabaseConfigured()) {
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
