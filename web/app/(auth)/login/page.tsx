"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthCard } from "@/components/layout/auth-card";
import { AuthNotice, GoogleButton } from "@/components/layout/auth-notice";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Rule } from "@/components/ui/rule";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!email.trim() || !password) {
      // One message for both fields rather than naming which was wrong: on a sign-in
      // form, saying which half failed tells an attacker whether the email exists.
      setError("Enter your email and password.");
      return;
    }
    setError(null);
    setSubmitted(true);
  }

  return (
    <AuthCard
      title="Sign in"
      footer={
        <>
          New here?{" "}
          <Link
            href="/signup"
            className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
          >
            Start free
          </Link>
        </>
      }
    >
      {submitted ? (
        <AuthNotice heading="Sign-in isn't connected yet" />
      ) : (
        <form onSubmit={submit} noValidate className="flex flex-col gap-4">
          <GoogleButton label="Continue with Google" />

          <div className="flex items-center gap-3">
            <Rule className="flex-1" />
            <span className="eyebrow text-text-mute">or</span>
            <Rule className="flex-1" />
          </div>

          <Field label="Email" error={error} required>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              autoFocus
            />
          </Field>

          <Field label="Password" required>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </Field>

          <div className="flex items-center justify-between gap-3">
            <Checkbox
              checked={remember}
              onCheckedChange={setRemember}
              label="Remember me"
              id="remember"
            />
            <Link
              href="/forgot-password"
              className="text-small text-text-dim underline decoration-rule-strong underline-offset-2 hover:text-text hover:decoration-current"
            >
              Forgot password
            </Link>
          </div>

          <Button type="submit" size="lg" className="w-full">
            Sign in
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
