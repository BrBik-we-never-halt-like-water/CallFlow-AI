"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthCard } from "@/components/layout/auth-card";
import { AuthNotice, GoogleButton } from "@/components/layout/auth-notice";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  isPasswordValid,
  PasswordStrength,
} from "@/components/ui/password-strength";
import { Rule } from "@/components/ui/rule";

const FREE_EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"];

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [submitted, setSubmitted] = useState(false);

  const domain = email.split("@")[1]?.toLowerCase() ?? "";
  // A nudge, not a rule. Plenty of legitimate small businesses run on a free mailbox,
  // and blocking them at the door to satisfy a lead-scoring preference is a bad trade.
  const showWorkEmailNudge = FREE_EMAIL_DOMAINS.includes(domain);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const next: typeof errors = {};
    if (!email.trim()) next.email = "Add an email address.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      next.email = "That doesn't look like an email address.";
    }
    if (!isPasswordValid(password)) {
      next.password = "Meet all four requirements below before continuing.";
    }
    setErrors(next);
    if (Object.keys(next).length === 0) setSubmitted(true);
  }

  return (
    <AuthCard
      title="Start free"
      description="Unlimited dry runs, no card. Nothing is dialled until you turn dry run off."
      footer={
        <>
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
          >
            Sign in
          </Link>
        </>
      }
    >
      {submitted ? (
        <AuthNotice />
      ) : (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <GoogleButton label="Continue with Google" />

          <div className="flex items-center gap-3">
            <Rule className="flex-1" />
            <span className="eyebrow text-text-mute">or</span>
            <Rule className="flex-1" />
          </div>

          <Field
            label="Work email"
            error={errors.email}
            help={
              showWorkEmailNudge
                ? "A work address makes it easier to add teammates later — but this one is fine."
                : undefined
            }
            required
          >
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              autoFocus
            />
          </Field>

          <Field label="Password" error={errors.password} required>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
          </Field>

          <PasswordStrength value={password} />

          <Button type="submit" size="lg" className="w-full">
            Start free
          </Button>

          <p className="text-small text-text-mute">
            By continuing you agree to the{" "}
            <Link href="/trust" className="underline decoration-rule-strong underline-offset-2">
              terms
            </Link>{" "}
            and{" "}
            <Link href="/trust" className="underline decoration-rule-strong underline-offset-2">
              privacy policy
            </Link>
            .
          </p>
        </form>
      )}
    </AuthCard>
  );
}
