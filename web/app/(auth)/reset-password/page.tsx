"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthCard } from "@/components/layout/auth-card";
import { AuthNotice } from "@/components/layout/auth-notice";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { isPasswordValid, PasswordStrength } from "@/components/ui/password-strength";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({});
  const [submitted, setSubmitted] = useState(false);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const next: typeof errors = {};
    if (!isPasswordValid(password)) {
      next.password = "Meet all four requirements below before continuing.";
    }
    if (confirm !== password) next.confirm = "These two don't match.";
    setErrors(next);
    if (Object.keys(next).length === 0) setSubmitted(true);
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
      {submitted ? (
        <AuthNotice heading="Password reset isn't connected yet" />
      ) : (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <Field label="New password" error={errors.password} required>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              autoFocus
            />
          </Field>

          <PasswordStrength value={password} />

          <Field label="Confirm new password" error={errors.confirm} required>
            <Input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
            />
          </Field>

          <Button type="submit" size="lg" className="w-full">
            Set new password
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
