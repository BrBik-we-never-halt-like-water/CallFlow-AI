'use client';

import { supabaseBrowser } from '@/lib/supabase/client';
import { authErrorMessage } from './errors';

export interface AuthResult {
  ok: boolean;
  /** Set when `ok` is false. Already user-facing - render it as-is. */
  error?: string;
}

function siteUrl(): string {
  // window at runtime rather than NEXT_PUBLIC_SITE_URL, so a link generated on a
  // preview deployment returns to that deployment rather than to production.
  if (typeof window !== 'undefined') return window.location.origin;
  return process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000';
}

export async function signUpWithPassword(
  email: string,
  password: string,
  name?: string,
): Promise<AuthResult> {
  const supabase = supabaseBrowser();

  const { error } = await supabase.auth.signUp({
    email: email.trim(),
    password,
    options: {
      // Read by the signup trigger to name the user and their organisation.
      data: name?.trim() ? { full_name: name.trim() } : undefined,
      emailRedirectTo: `${siteUrl()}/app`,
    },
  });

  return error ? { ok: false, error: authErrorMessage(error) } : { ok: true };
}

export async function signInWithPassword(
  email: string,
  password: string,
): Promise<AuthResult> {
  const supabase = supabaseBrowser();

  const { error } = await supabase.auth.signInWithPassword({
    email: email.trim(),
    password,
  });

  return error ? { ok: false, error: authErrorMessage(error) } : { ok: true };
}

export async function requestPasswordReset(email: string): Promise<AuthResult> {
  const supabase = supabaseBrowser();

  const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
    redirectTo: `${siteUrl()}/reset-password`,
  });

  // A missing address is not reported as an error anywhere in this flow - the caller
  // shows the same confirmation either way, so the form cannot be used to discover
  // which addresses are registered.
  return error ? { ok: false, error: authErrorMessage(error) } : { ok: true };
}

export async function updatePassword(password: string): Promise<AuthResult> {
  const supabase = supabaseBrowser();

  const { error } = await supabase.auth.updateUser({ password });

  return error ? { ok: false, error: authErrorMessage(error) } : { ok: true };
}

export async function signOut(): Promise<void> {
  await supabaseBrowser().auth.signOut();
}
