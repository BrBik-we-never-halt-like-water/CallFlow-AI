/**
 * Turns Supabase auth errors into sentences a user can act on.
 *
 * The raw messages are written for developers ("Invalid login credentials",
 * "AuthApiError"), and some leak whether an address exists — which is an enumeration
 * vector on a sign-in form. Everything unrecognised falls back to a message that says
 * what to do next rather than what went wrong internally.
 */

interface SupabaseAuthError {
  message?: string;
  code?: string;
  status?: number;
}

const BY_CODE: Record<string, string> = {
  invalid_credentials: "That email and password don't match. Check both and try again.",
  email_not_confirmed:
    "This account hasn't been confirmed yet. Check your inbox for the confirmation link.",
  user_already_exists:
    "An account already exists for that email. Sign in instead, or reset your password.",
  email_exists:
    "An account already exists for that email. Sign in instead, or reset your password.",
  weak_password: "That password is too easy to guess. Use at least 12 characters.",
  over_email_send_rate_limit:
    "Too many emails have been sent recently. Wait a few minutes and try again.",
  over_request_rate_limit: "Too many attempts. Wait a minute and try again.",
  validation_failed: "Check the details above and try again.",
  email_address_invalid:
    "That email address was rejected. Use a real address at a domain that can receive mail.",
  same_password: "That is your current password. Choose a different one.",
};

export function authErrorMessage(error: unknown): string {
  const details = error as SupabaseAuthError | null;

  if (details?.code && BY_CODE[details.code]) {
    return BY_CODE[details.code];
  }

  const message = details?.message?.toLowerCase() ?? "";

  if (message.includes("invalid login credentials")) return BY_CODE.invalid_credentials;
  if (message.includes("already registered") || message.includes("already exists")) {
    return BY_CODE.user_already_exists;
  }
  if (message.includes("email rate limit") || message.includes("rate limit")) {
    return BY_CODE.over_email_send_rate_limit;
  }
  if (message.includes("is invalid")) return BY_CODE.email_address_invalid;
  if (message.includes("password")) return BY_CODE.weak_password;

  if (details?.status === 429) return BY_CODE.over_request_rate_limit;

  // Deliberately not the raw message: it is written for a developer, and on a sign-in
  // form it can reveal whether an address is registered.
  return "That didn't work. Check your details and try again.";
}
