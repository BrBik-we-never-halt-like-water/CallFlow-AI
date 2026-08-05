"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthCard } from "@/components/layout/auth-card";
import { AuthNotice } from "@/components/layout/auth-notice";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Enter the email address on your account.");
      return;
    }
    setError(null);
    setSubmitted(true);
  }

  return (
    <AuthCard
      title="Reset your password"
      description="We'll email you a link. It expires in one hour."
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
        <AuthNotice heading="Password reset isn't connected yet">
          There is no account service on this deployment, so no email was sent. Nothing
          about your account has changed.
        </AuthNotice>
      ) : (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <Field label="Email" error={error} required>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              autoFocus
            />
          </Field>

          <Button type="submit" size="lg" className="w-full">
            Send reset link
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
