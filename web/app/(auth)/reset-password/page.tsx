"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthCard } from "@/components/layout/auth-card";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Eyebrow, Panel } from "@/components/ui/panel";
import { isPasswordValid, PasswordStrength } from "@/components/ui/password-strength";
import { useToast } from "@/components/ui/toast";
import { supabaseBrowser } from "@/lib/supabase/client";
import { updatePassword } from "@/lib/auth/actions";

type LinkState = "checking" | "valid" | "invalid";

export default function ResetPasswordPage() {
  const router = useRouter();
  const toast = useToast();

  const [linkState, setLinkState] = useState<LinkState>("checking");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({});
  const [submitting, setSubmitting] = useState(false);

  // Supabase turns the recovery link into a session before this page renders, so the
  // presence of a session is what tells us the link was valid. Checking it up front
  // means an expired link says so immediately rather than after the user has typed a
  // new password twice.
  useEffect(() => {
    let cancelled = false;

    supabaseBrowser()
      .auth.getSession()
      .then(({ data }) => {
        if (!cancelled) setLinkState(data.session ? "valid" : "invalid");
      })
      .catch(() => {
        if (!cancelled) setLinkState("invalid");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();

    const found: typeof errors = {};
    if (!isPasswordValid(password)) {
      found.password = "Meet all four requirements below before continuing.";
    }
    if (confirm !== password) found.confirm = "These two don't match.";

    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    const result = await updatePassword(password);

    if (!result.ok) {
      setErrors({ password: result.error });
      setSubmitting(false);
      return;
    }

    toast({ tone: "success", title: "Password updated" });
    router.replace("/app");
    router.refresh();
  }

  if (linkState === "invalid") {
    return (
      <AuthCard
        title="That link has expired"
        description="Reset links are valid for one hour and can only be used once."
        footer={
          <Link
            href="/forgot-password"
            className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
          >
            Request a new link
          </Link>
        }
      >
        <Panel sunken className="flex flex-col gap-2 p-4">
          <Eyebrow>Nothing has changed</Eyebrow>
          <p className="text-small text-text-dim">
            Your existing password still works. Request a fresh link and use it within
            the hour.
          </p>
        </Panel>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Choose a new password"
      description="You'll be signed out everywhere else once this is set."
      footer={
        <Link
          href="/login"
          className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
        >
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Field label="New password" error={errors.password} required>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            autoFocus
            disabled={submitting || linkState === "checking"}
          />
        </Field>

        <PasswordStrength value={password} />

        <Field label="Confirm new password" error={errors.confirm} required>
          <Input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            disabled={submitting || linkState === "checking"}
          />
        </Field>

        <Button
          type="submit"
          size="lg"
          className="w-full"
          loading={submitting}
          disabled={linkState === "checking"}
        >
          Set new password
        </Button>
      </form>
    </AuthCard>
  );
}
