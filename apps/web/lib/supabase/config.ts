/**
 * Supabase connection values, validated once.
 *
 * Reading these through a checked accessor rather than `process.env` at each call
 * site means a missing variable fails with a sentence you can act on, at the point
 * of use, instead of surfacing later as "Invalid API key".
 */

function required(name: string, value: string | undefined): string {
  const trimmed = value?.trim();
  if (!trimmed) {
    throw new Error(
      `${name} is not set. Copy apps/web/.env.example to .env.local and fill it in.`,
    );
  }
  return trimmed;
}

export function supabaseUrl(): string {
  return required("NEXT_PUBLIC_SUPABASE_URL", process.env.NEXT_PUBLIC_SUPABASE_URL);
}

/**
 * The publishable key. Safe in the browser: it grants only what RLS allows, which is
 * why every table in the schema has policies rather than relying on key secrecy.
 */
export function supabaseAnonKey(): string {
  return required("NEXT_PUBLIC_SUPABASE_ANON_KEY", process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
}

export function isSupabaseConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() &&
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim(),
  );
}
